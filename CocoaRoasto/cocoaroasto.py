#!/usr/bin/python
#
# Copyright (c) 2017-2018 Mark Juric
# Copyright (c) 2012-2015 Stephen P. Smith
#
# Permission is hereby granted, free of charge, to any person obtaining 
# a copy of this software and associated documentation files 
# (the "Software"), to deal in the Software without restriction, 
# including without limitation the rights to use, copy, modify, 
# merge, publish, distribute, sublicense, and/or sell copies of the Software, 
# and to permit persons to whom the Software is furnished to do so, 
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included 
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS 
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR 
# IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import pprint
from inspect import getmembers
import time, random, serial, os
import sys
from flask import Flask, render_template, request, jsonify
import xml.etree.ElementTree as ET
import Roaster
from multiprocessing import Queue, Pipe, Process, current_process
from Queue import Full
from pid import pidpy as PIDController

import logging
from logging.handlers import RotatingFileHandler

global parent_conn
roastTime = 0
roasterStatusQ = []
DEBUG = 0

app = Flask(__name__, template_folder='templates')
#url_for('static', filename='raspibrew.css')

#Parameters that are used in the temperature control process
class param:
    status = {
        "tempSensors" : [],
        "gasValve" : [],
        "numTempSensors" : 0,
        "temp" : "0",
        "tempUnits" : "F",
        "elapsed" : "0",
        "mode" : "off",
        "sampleTime" : 2.0,
        "gasOutput" : 0.0,
        "boil_gasOutput" : 60,
        "set_point" : 0.0,
        "boil_manage_temp" : 200,
        "num_pnts_smooth" : 5,
      #  "k_param" : 44,
      #  "i_param" : 165,
      #  "d_param" : 4             
        "k_param" : 1.2,
        "i_param" : 1,
        "d_param" : 0.001             
    }
                      
class profile:
    roast = {
        "ambient" : { "ramp": '', "finaltemp": 70, "time": '' },
        "drying" : { "ramp": '', "finaltemp": '', "time": '' },
        "development" : { "ramp": '', "finaltemp": '', "time": '' },
        "finish" : { "ramp": '', "finaltemp": 267, "time": '' },
    }

# main web page    
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        #render main page
        print param.status
        return render_template(template_name, mode = param.status["mode"], set_point = param.status["set_point"], \
                                gasOutput = param.status["gasOutput"], sampleTime = param.status["sampleTime"], \
                                k_param = param.status["k_param"], i_param = param.status["i_param"], \
                                d_param = param.status["d_param"], numTempSensors = param.status["numTempSensors"], \
                                tempSensors = param.status["tempSensors"], gasValve = param.status["gasValve"],\
                                ambient_finaltemp = profile.roast["ambient"]["finaltemp"],\
                                drying_ramp = profile.roast["drying"]["ramp"],\
                                drying_finaltemp = profile.roast["drying"]["finaltemp"],\
                                drying_time = profile.roast["drying"]["time"],\
                                development_ramp = profile.roast["development"]["ramp"],\
                                development_finaltemp = profile.roast["development"]["finaltemp"],\
                                development_time = profile.roast["development"]["time"],\
                                finish_ramp = profile.roast["finish"]["ramp"],\
                                finish_finaltemp = profile.roast["finish"]["finaltemp"],\
                                finish_time = profile.roast["finish"]["time"])
    else:
        return 'OK'

#post roasting profiles
@app.route('/postprofile', methods=['POST'])
def postprofile():
    if request.json is not None:
        profile.roast = request.json

    for val in request.form:
        print val, " ", request.form[val]

    print "ME SHARTS!"
    return 'OK'

# check-in with the temperature probe
@app.route('/postsensors', methods=['POST'])
def postsensors():
    content = request.get_json()
    print (content)
    return 'JSON posted'

#post params (selectable temp sensor number)    
@app.route('/postparams/<sensorNum>', methods=['POST'])
def postparams(sensorNum=None):
    param.status["mode"] = request.form["mode"] 
    param.status["set_point"] = float(request.form["setpoint"])
    param.status["gasOutput"] = float(request.form["dutycycle"]) #is boil duty cycle if mode == "boil"
    param.status["sampleTime"] = float(request.form["cycletime"])
    param.status["boil_manage_temp"] = float(request.form.get("boilManageTemp", param.status["boil_manage_temp"])) 
    param.status["num_pnts_smooth"] = int(request.form.get("numPntsSmooth", param.status["num_pnts_smooth"]))
    param.status["k_param"] = float(request.form["k"])
    param.status["i_param"] = float(request.form["i"])
    param.status["d_param"] = float(request.form["d"])

            
    #send to main temp control process 
    #if did not receive variable key value in POST, the param class default is used
    parent_conn.send(param.status)
        
    return 'OK'
    
#get status from RasPiBrew using firefox web browser (selectable temp sensor)
@app.route('/getstatus/<roasterNum>') #only GET
def getstatus(roasterNum=None):          
    global roasterStatusQ
    # blocking receive - current status
    roasterN = int(roasterNum)
    if roasterN > len(roasterStatusQ):
        print("Sensor doesn't exist (GET)")
        param.status["temp"] = "-999"
    else:
        param.status = roasterStatusQ[roasterN-1].get()

    return jsonify(**param.status)

def getRoastTime():
    return (time.time() - roastTime)    
       
# Stand Alone Get Temperature Process               
def getTempProc(conn, myTempSensor):
    p = current_process()
    print('Starting:', p.name, p.pid)
    
    while (True):
        t = time.time()
        time.sleep(.5) #.1+~.83 = ~1.33 seconds
        num = myTempSensor.readTempC()
        elapsed = "%.2f" % (time.time() - t)
        conn.send([num, myTempSensor.getTempSensorId(), elapsed])
        
#Get time heating element is on and off during a set cycle time
def getonofftime(sampleTime, gasOutput):
    duty = gasOutput/100.0
    on_time = sampleTime*(duty)
    off_time = sampleTime*(1.0-duty)   
    return [on_time, off_time]
        
# Stand Alone Heat Process using GPIO
def heatProcGPIO(conn, sampleTime, gasOutput, myGasServo):
    p = current_process()
    print('Starting:', p.name, p.pid)
    while (True):
        while (conn.poll()): #get last
            sampleTime, gasOutput = conn.recv()
            myGasServo.setGasOutput(gasOutput)
        conn.send([sampleTime, gasOutput])
        time.sleep(sampleTime)

def unPackParamInitAndPost(paramStatus):
    #temp = paramStatus["temp"]
    #tempUnits = paramStatus["tempUnits"]
    #elapsed = paramStatus["elapsed"]
    mode = paramStatus["mode"]
    sampleTime = paramStatus["sampleTime"]
    gasOutput = paramStatus["gasOutput"]
    boil_gasOutput = paramStatus["boil_gasOutput"]
    set_point = paramStatus["set_point"]
    boil_manage_temp = paramStatus["boil_manage_temp"]
    num_pnts_smooth = paramStatus["num_pnts_smooth"]
    k_param = paramStatus["k_param"]
    i_param = paramStatus["i_param"]
    d_param = paramStatus["d_param"]

    return mode, sampleTime, gasOutput, boil_gasOutput, set_point, boil_manage_temp, num_pnts_smooth, \
           k_param, i_param, d_param

def packParamGet(numTempSensors, myTempSensorNum, temp, tempUnits, elapsed, mode, sampleTime, gasOutput, boil_gasOutput, set_point, \
                                 boil_manage_temp, num_pnts_smooth, k_param, i_param, d_param, tempSensors, gasValve):
    
    param.status["numTempSensors"] = numTempSensors
    param.status["myTempSensorNum"] = myTempSensorNum
    param.status["temp"] = temp
    param.status["tempUnits"] = tempUnits
    param.status["elapsed"] = elapsed
    param.status["mode"] = mode
    param.status["sampleTime"] = sampleTime
    param.status["gasOutput"] = gasOutput
    param.status["boil_gasOutput"] = boil_gasOutput
    param.status["set_point"] = set_point
    param.status["boil_manage_temp"] = boil_manage_temp
    param.status["num_pnts_smooth"] = num_pnts_smooth
    param.status["k_param"] = k_param
    param.status["i_param"] = i_param
    param.status["d_param"] = d_param
    param.status["tempSensors"] = tempSensors
    param.status["gasValve"] = gasValve

    return param.status


# Main Temperature Control Process
def tempControlProc(myRoaster, paramStatus, conn):
    parentTemps = []
    oldMode = ''

    mode, sampleTime, gasOutput, boil_gasOutput, set_point, boil_manage_temp, num_pnts_smooth, \
    k_param, i_param, d_param = unPackParamInitAndPost(paramStatus)
    oldMode = mode

    p = current_process()
    print('Starting:', p.name, p.pid)

    tempSensors = myRoaster.getTempSensors()
    numTempSensors = len(tempSensors)
    for tempSensor in tempSensors:
        parentTemp, c = Pipe()
        tempSensor.addTempPipe(parentTemp)
    
        # Start Get Temperature Process        
        ptemp = Process(name = "getTempProc", target=getTempProc, args=(c, tempSensor))
        ptemp.daemon = True
        print ('Starting:', tempSensor.getTempSensorName())
        ptemp.start()

    # Pipe to communicate with "Heat Process"
    parentHeat, c = Pipe()
    # Start Heat Process      
    # Fix this. What do sampleTime and gasOutput do here?
    pheat = Process(name = "heatProcGPIO", target=heatProcGPIO, args=(c, sampleTime, gasOutput, myRoaster.getGasServo()))
    pheat.daemon = True
    pheat.start()

    tempUnits = xml_root.find('Temp_Units').text.strip()

    # Get our PID ready
    readyPIDcalc = False

    # Temperature smoothing list
    tempMovingAverageList = []
    tempMovingAverage = 0.0

    slopeMovingAverageList = []
    slopeMovingAverage = 0.0

    while(True):
        readytemp = False
        tempSensorsParam = []
        gasServoParam = []
 
        for tempSensor in tempSensors:
            parentTemp = tempSensor.getTempPipe()
            while parentTemp.poll(): # Poll Get Temperature Process Pipe
                temp_C, tempSensorNum, elapsed = parentTemp.recv() # non blocking receive from Get Temperature Process

                if temp_C == -99:
                    print("Bad Temp Reading - retry")
                    continue

                if (tempUnits == 'F'):
                    temp = (9.0/5.0)*temp_C + 32
                else:
                    temp = temp_C

                temp_str = "%3.2f" % temp
                
                readytemp = True
                
            if readytemp == True:
                if mode == "auto":
                    tempMovingAverageList.append({"temp":temp,"timestamp":time.time()})

                    # smooth data
                    tempMovingAverage = 0.0 # moving avg init
                    slopeMovingAverage = 0.0
                    while (len(tempMovingAverageList) > num_pnts_smooth):
                        tempMovingAverageList.pop(0) # remove oldest elements in list
                    while (len(slopeMovingAverageList) > num_pnts_smooth-1):
                        slopeMovingAverageList.pop(0) # slopeMovingAverage is one less because it's a diff 

                    for temp_pnt in tempMovingAverageList:
                        tempMovingAverage += temp_pnt["temp"]
                    tempMovingAverage /= len(tempMovingAverageList)

                    # Now, compute the moving average of the slope
                    # We need at least two values to compute a difference
                    if len(tempMovingAverageList) > 1:
                        i = 0
                        while i < len(tempMovingAverageList):
                            diff = tempMovingAverageList[i+1]["temp"] - tempMovingAverageList[i]["temp"]
                            slope = diff / (tempMovingAverageList[i+1]["timestamp"] - tempMovingAverageList[i]["timestamp"])
                            slopeMovingAverage =+ slope
                            i += 1
                        slopeMovingAverage /= len(tempMovingAverageList)
 
            #        print "len(tempMovingAverageList) = %d" % len(tempMovingAverageList)
            #        print "Num Points smooth = %d" % num_pnts_smooth
            #        print "tempMovingAverage = %.2f" % tempMovingAverage
            #        print tempMovingAverageList

                    # calculate PID every cycle
                    if (readyPIDcalc == True):
                        gasOutput = pid.calcPID_reg4(slopMovingAverage, set_point, True)
                        # send to heat process every cycle
                        if not oldMode == mode:
                            myRoaster.getGasServo().setToSafeLow()
                            print "%s changing to %s" %(oldMode,mode)
                        oldMode = mode
                        parentHeat.send([sampleTime, gasOutput])
                        readyPIDcalc = False

                tempSensorsParam.append([tempSensor.getTempSensorId(),tempSensor.getTempSensorName(),temp_str])
                gasServoParam = [myRoaster.getGasServo().getServoId(),myRoaster.getGasServo().getSafeLow(),gasOutput]
                # put current status in queue
                try:
                    paramStatus = packParamGet(numTempSensors, tempSensor.getTempSensorId(), temp_str, tempUnits, elapsed, mode, sampleTime, gasOutput, \
                            boil_gasOutput, set_point, boil_manage_temp, num_pnts_smooth, k_param, i_param, d_param,tempSensorsParam, gasServoParam) 
#        "tempSensors" : [],
#        "gasValve" : [],

                    statusQ.put(paramStatus) #GET request
                except Full:
                    pass

                while (statusQ.qsize() >= 2):
                    statusQ.get() #remove old status

                logdata(tempSensorNum, temp, gasOutput)
                if DEBUG:
                    print("Current Temp: %3.2f deg %s, Heat Output: %3.1f%%" \
                                                        % (temp, tempUnits, gasOutput))

        while parentHeat.poll(): # Poll Heat Process Pipe
            sampleTime, gasOutput = parentHeat.recv() #non blocking receive from Heat Process
            readyPIDcalc = True

        # Pick up any environment changes
        readyPOST = False
        while conn.poll(): #POST settings - Received POST from web browser or Android device
            paramStatus = conn.recv()
            mode, sampleTime, gasOutput_temp, boil_gasOutput, set_point, boil_manage_temp, num_pnts_smooth, \
            k_param, i_param, d_param = unPackParamInitAndPost(paramStatus)

            readyPOST = True
        if readyPOST == True:
            if mode == "auto":
                print("auto selected")
                pid = PIDController.pidpy(sampleTime, k_param, i_param, d_param) #init pid
                gasOutput = pid.calcPID_reg4(tempMovingAverage, set_point, True)
                # always zero out to lowest safe low before enabled modes
                if not oldMode == mode:
                    myRoaster.getGasServo().setToSafeLow()
                parentHeat.send([sampleTime, gasOutput])
            if mode == "manual":
                print("manual selected (%s and %s)" % (oldMode,mode))
                gasOutput = gasOutput_temp
                # always zero out to lowest safe low before enabled modes
                if not oldMode == mode:
                    print "setting to safeLow"
                    myRoaster.getGasServo().setToSafeLow()
                parentHeat.send([sampleTime, gasOutput])
            if mode == "off":
                print("off selected")
                # We don't care. Off is off. Always set to off.
                myRoaster.getGasServo().setOff()

            oldMode = mode
            readyPOST = False


        time.sleep(0.01)


def logdata(tank, temp, heat):
    f = open("roasting" + str(tank) + ".csv", "ab")
    if sys.version_info >= (3, 0):
        f.write("%3.1f;%3.3f;%3.3f\n".encode("utf8") % (getRoastTime(), temp, heat))
    else:
        f.write("%3.1f;%3.3f;%3.3f\n" % (getRoastTime(), temp, heat))
    f.close()


if __name__ == '__main__':
    roastTime = time.time()

    # Retrieve root element from config.xml for parsing
    tree = ET.parse('config.xml')
    xml_root = tree.getroot()
    template_name = xml_root.find('Template').text.strip()

    root_dir_elem = xml_root.find('RootDir')
    if root_dir_elem is not None:
        os.chdir(root_dir_elem.text.strip())
    else:
        print("No RootDir tag found in config.xml, running from current directory")

    # Look for roasters
    for roasters in xml_root.iter('Roasters'):
        print ("found roasters")
        for roaster in roasters:
            roasterId = roaster.find('Roaster_Id').text
            myRoaster = Roaster.Roaster(roasterId)

            tempSensors = roaster.find('Temp_Sensors')
            # A roaster can have more than one temperature probe
            for tempSensor in tempSensors.iter('Temp_Sensor'):
                # These need to be appended to a list so we can have more than one, but for now
                # just leave this
                tempSensorId        = tempSensor.find('Temp_Sensor_Id').text
                tempSensorName      = tempSensor.find('Temp_Sensor_Name').text
                tempSensorSPI       = tempSensor.find('SPI').text
                tempSensorDriver    = tempSensor.find('Temp_Sensor_Driver').text

                if tempSensorSPI == "hardware":
                    myRoaster.addTempSensor(tempSensorId,tempSensorName,tempSensorDriver,tempSensorSPI)
                elif tempSensorSPI == "gpio":
                    myRoaster.addTempSensor(tempSensorId,tempSensorName,tempSensorDriver,tempSensorSPI,\
                                                    int(tempSensor.find('clk').text), \
                                                    int(tempSensor.find('cs').text), \
                                                    int(tempSensor.find('do').text))
                
                # hackity hack hack hack. why isn't param updated in the first call of index()?
                param.status["tempSensors"].append([tempSensorId,tempSensorName,0])

            param.status["numTempSensors"] = len(myRoaster.getTempSensors())

            # grab our gas servo
            servo       = roaster.find('Servo')
            servoId     = servo.find('Servo_Id').text
            driver      = servo.find('Servo_Driver').text
            delay       = float(servo.find('Servo_Delay').text)
            step        = int(servo.find('Step_Pin').text)
            direction   = int(servo.find('Dir_Pin').text)
            ms1         = int(servo.find('MS1_Pin').text)
            ms2         = int(servo.find('MS2_Pin').text)
            home        = int(servo.find('Home_Pin').text)
            steps       = servo.find('Step').text
            stepsPer    = int(servo.find('Steps_Per_Rotation_Full').text)


            # get our valve info
            valve    = roaster.find('Valve')
            maxTurns = int(valve.find('Max_Turns_Ceil').text)
            safeLow  = int(valve.find('Safe_Low_Percent').text)
        
            param.status["gasValve"] = [servoId,safeLow,0]

            myRoaster.addGasServo(servoId,driver,delay,step,direction,ms1,ms2,home,maxTurns,safeLow,steps,stepsPer)
            myGasServo = myRoaster.getGasServo()
            
            statusQ = Queue(2) # blocking queue
            myRoaster.addStatusQ(statusQ)

            # Ugly, but we need to make access to the status queue global
            roasterStatusQ.append(statusQ) #blocking queue        

            parent_conn, child_conn = Pipe()
            p = Process(name = "tempControlProc", target=tempControlProc, args=(myRoaster, param.status, child_conn))
            p.start()

            myGasServo.home()

    logger = logging.getLogger('werkzeug')
    handler = logging.FileHandler('access.log')
    logger.addHandler(handler)
    app.debug = True
    app.run(use_reloader=False, host='0.0.0.0')
