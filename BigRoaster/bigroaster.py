#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
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
# or impLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR 
# IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import time, random, os
import sys
from flask import Flask, render_template, request, jsonify, json
import xml.etree.ElementTree as ET
import Roaster
from multiprocessing import Queue, Pipe, Process, current_process
from Queue import Full
from pid import pidpy as PIDController

import logging
from logging.handlers import RotatingFileHandler

global paramConn    # pipe between tempControlProc and web server for passing POST'd params
global myRoasterObj


roastTime = 0
posted = False
statusQ = None      # Queue to pass temp readings and settings between browser and us
tempQueue = Queue(2)    # Queue to pass temp sensor data between tempControlProc and us
DEBUG = 0

app = Flask(__name__, template_folder='templates')

#Parameters that are used in the temperature control process
class param:
    status = {
        "tempSensors" : [],
        "gasValve" : [],
        "temp" : "0",
        "tempUnits" : "F",
        "elapsed" : "0",
        "mode" : "off",
        "sampleTime" : 2.0,
        "gasOutput" : 0.0,
        "set_point" : 0.0,
        "num_pnts_smooth" : 5,
      #  "k_param" : 44,
      #  "i_param" : 165,
      #  "d_param" : 4             
        "k_param" : 1.2,
        "i_param" : 1,
        "d_param" : 0.001,
        "sampleRate" : 500,             
        "checkInRate" : 20,             
        "roasterRotation" : 0,             
        "roasterTilt" : 0,             
        "roasterFullness" : 50,             
    }
    roast = {
        "ambient" : { "ramp": '', "finaltemp": 70, "time": '' },
        "drying" : { "ramp": '', "finaltemp": '', "time": '' },
        "development" : { "ramp": '', "finaltemp": '', "time": '' },
        "finish" : { "ramp": '', "finaltemp": 267, "time": '' },
    }
    config = {
        "tempUnits" : "F",
        "template": '',
        "rootDir": '',
        "roasterId": -1,
        "servoId": -1,
        "servoDriver": '',
        "servoDelay": 0.1,
        "servoStepPin": -1,
        "servoDirPin": -1,
        "servoMS1Pin": -1,
        "servoMS2Pin": -1,
        "servoHomePin": -1,
        "servoSteps": -1,
        "servoStepsPer": -1,
        "valveMaxTurns": -1,
        "valveSafeLow": -1,
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
                                d_param = param.status["d_param"], \
                                tempSensors = param.status["tempSensors"], gasValve = param.status["gasValve"],\
                                sampleRate = param.status["sampleRate"], checkInRate = param.status["checkInRate"],\
                                ambient_finaltemp = param.roast["ambient"]["finaltemp"],\
                                drying_ramp = param.roast["drying"]["ramp"],\
                                drying_finaltemp = param.roast["drying"]["finaltemp"],\
                                drying_time = param.roast["drying"]["time"],\
                                development_ramp = param.roast["development"]["ramp"],\
                                development_finaltemp = param.roast["development"]["finaltemp"],\
                                development_time = param.roast["development"]["time"],\
                                finish_ramp = param.roast["finish"]["ramp"],\
                                finish_finaltemp = param.roast["finish"]["finaltemp"],\
                                finish_time = param.roast["finish"]["time"])
    else:
        return 'OK'

#post roasting profiles
@app.route('/postprofile', methods=['POST'])
def postprofile():
    if request.json is not None:
        param.roast = request.json

    for val in request.form:
        print val, " ", request.form[val]

    print "ME SHARTS!"
    return 'OK'

# make sure our temp board is doing what we want
@app.route('/checkin', methods=['GET'])
def checkin():
    return jsonify({"sampleRate": str(param.status["sampleRate"]), "checkInRate": str(param.status["checkInRate"])})

# check-in with the temperature probe
@app.route('/postsensors', methods=['POST'])
def postsensors():
    global posted

    content = request.get_json()
    if not posted:
        initialize(content)
        posted = True

    if tempQueue.full():
        print "Queue full. Scrapping data"
        tempQueue.get()
    tempQueue.put(content)

    #print "Posting to tempQueue: ", content, " and now queue length is ", tempQueue.qsize()

    return 'JSON posted'

#post params (selectable temp sensor number)    
@app.route('/postparams/<sensorNum>', methods=['POST'])
def postparams(sensorNum=None):
    global paramConn
    param.status["mode"] = request.form["mode"] 
    param.status["set_point"] = float(request.form["setpoint"])
    param.status["gasOutput"] = float(request.form["dutycycle"]) #is boil duty cycle if mode == "boil"
    param.status["sampleTime"] = float(request.form["cycletime"])
    param.status["num_pnts_smooth"] = int(request.form.get("numPntsSmooth", param.status["num_pnts_smooth"]))
    param.status["k_param"] = float(request.form["k"])
    param.status["i_param"] = float(request.form["i"])
    param.status["d_param"] = float(request.form["d"])

            
    #send to main temp control process 
    #if did not receive variable key value in POST, the param class default is used
    paramConn.send(param.status)
        
    return 'OK'
    
#get status from from roaster
@app.route('/getstatus') #only GET
def getstatus(roasterNum=1):          
    global statusQ
    # blocking receive - current status
    #print "param.status: ", param.status
    try:
        param.status = statusQ.get(timeout=param.status["sampleRate"]/1000.0)
    except:
        pass

    return jsonify(**param.status)

def initialize(sensorPost):
    global statusQ
    global paramConn
    # We've never checked in before. Do some work
    ## Is it possible to change this on the fly? Do we care?
    numSensors = len(sensorPost["probes"])
    param.status["tempSensors"] = []

    param.status["tempUnits"] = param.config["tempUnits"]

    # Look for roasters
    myRoasterObj = Roaster.Roaster(param.config["roasterId"])
    for i in range(numSensors):
        tempSensorId = sensorPost["probes"][i]["number"]
        myRoasterObj.addTempSensor(tempSensorId,str(tempSensorId),"MAX31855","hardware")
        #myRoasterObj.addTempSensor(tempSensorId)
        param.status["tempSensors"].append([tempSensorId,str(tempSensorId),0])

    # grab our gas servo
    servoId     = param.config["servoId"]
    driver      = param.config["servoDriver"]
    delay       = param.config["servoDelay"]
    step        = param.config["servoStepPin"]
    direction   = param.config["servoDirPin"]
    ms1         = param.config["servoMS1Pin"]
    ms2         = param.config["servoMS2Pin"]
    home        = param.config["servoHomePin"]
    steps       = param.config["servoSteps"]
    stepsPer    = param.config["servoStepsPer"]

    # get our valve info
    maxTurns = param.config["valveMaxTurns"]
    safeLow  = param.config["valveSafeLow"]

    param.status["gasValve"] = [servoId,safeLow,0]

    myRoasterObj.addGasServo(servoId,driver,delay,step,direction,ms1,ms2,home,maxTurns,safeLow,steps,stepsPer)
    myGasServo = myRoasterObj.getGasServo()
    
    statusQ = Queue(2) # blocking queue
    paramConn, childParamConn = Pipe()
    p = Process(name = "tempControlProc", target=tempControlProc, args=(tempQueue, myRoasterObj, param.status, childParamConn))
    p.start()

    myGasServo.home()


def getRoastTime():
    return (time.time() - roastTime)    
       
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
    tempUnits = paramStatus["tempUnits"]
    #elapsed = paramStatus["elapsed"]
    mode = paramStatus["mode"]
    sampleTime = paramStatus["sampleTime"]
    gasOutput = paramStatus["gasOutput"]
    set_point = paramStatus["set_point"]
    num_pnts_smooth = paramStatus["num_pnts_smooth"]
    k_param = paramStatus["k_param"]
    i_param = paramStatus["i_param"]
    d_param = paramStatus["d_param"]

    return tempUnits, mode, sampleTime, gasOutput,  set_point, num_pnts_smooth, \
           k_param, i_param, d_param

def packParamGet(temp, tempUnits, elapsed, mode, sampleTime, gasOutput,  set_point, \
                                 num_pnts_smooth, k_param, i_param, d_param, tempSensors, gasValve, rotation):
    
    param.status["temp"] = temp
    param.status["tempUnits"] = tempUnits
    param.status["elapsed"] = elapsed
    param.status["mode"] = mode
    param.status["sampleTime"] = sampleTime
    param.status["gasOutput"] = gasOutput
    param.status["set_point"] = set_point
    param.status["num_pnts_smooth"] = num_pnts_smooth
    param.status["k_param"] = k_param
    param.status["i_param"] = i_param
    param.status["d_param"] = d_param
    param.status["tempSensors"] = tempSensors
    param.status["gasValve"] = gasValve
    param.status["roasterRotation"] = rotation

    return param.status


# Main Temperature Control Process
def tempControlProc(tempQ, myRoaster, paramStatus, childParamConn):
    oldMode = ''

    tempUnits, mode, sampleTime, gasOutput,  set_point, num_pnts_smooth, \
    k_param, i_param, d_param = unPackParamInitAndPost(paramStatus)
    oldMode = mode

    p = current_process()
    print('Starting:', p.name, p.pid)

    # Pipe to communicate with "Heat Process"
    parentHeat, c = Pipe()
    # Start Heat Process      
    # Fix this. What do sampleTime and gasOutput do here?
    pheat = Process(name = "heatProcGPIO", target=heatProcGPIO, args=(c, sampleTime, gasOutput, myRoaster.getGasServo()))
    pheat.daemon = True
    pheat.start()

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
 
        while not tempQ.empty():
            try:
                sensorInfo = tempQ.get()
            except e:
                print "tempQ was empty even when we said it wasn't. WTF."

            # This loop is not done. In here is where we have to figure out
            # which probe to pay attention to.
    
            # Rotation applies to probe 1. 
            # Face down: π
            # Face up: 0..2*π
            # Battery side (esp8266 up): π/2
            # Back side (esp8266 up): 1.5*π
            rotation = sensorInfo["position"]["rotation"]
            for sensor in sensorInfo["probes"]:
                temp_C = sensor["temp"]
                elapsed = sensor["elapsed"] / 1000.0
                tempSensorNum = sensor["number"]
                if temp_C == -99:
                    print("Bad Temp Reading - retry")
                    continue

                if (tempUnits == 'F'):
                    temp = (9.0/5.0)*temp_C + 32
                else:
                    temp = temp_C

                temp_str = "%3.2f" % temp
                
                readytemp = True
                tempSensorsParam.append([tempSensorNum,tempSensorNum,temp_str])
            
        if readytemp == True:
            if mode == "auto":
                tempMovingAverageList.append({"temp":temp,"timestamp":time.time()})
                print "tempMovingAverageList: ", tempMovingAverageList

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
                    while i < len(tempMovingAverageList)-1:
                        diff = tempMovingAverageList[i+1]["temp"] - tempMovingAverageList[i]["temp"]
                        timeDiff = tempMovingAverageList[i+1]["timestamp"] - tempMovingAverageList[i]["timestamp"]
                        slope = diff / (tempMovingAverageList[i+1]["timestamp"] - tempMovingAverageList[i]["timestamp"])
                        slopeMovingAverage =+ slope
                        i += 1
                    print "slopeMovingAverage before division: ", slopeMovingAverage
                    slopeMovingAverage /= (len(tempMovingAverageList)-1)
                    slopeMovingAverage *= 100
                    print "slopeMovingAverage after division: ", slopeMovingAverage

        #        print "len(tempMovingAverageList) = %d" % len(tempMovingAverageList)
        #        print "Num Points smooth = %d" % num_pnts_smooth
        #        print "tempMovingAverage = %.2f" % tempMovingAverage
        #        print tempMovingAverageList

                # calculate PID every cycle
                if (readyPIDcalc == True):
                    gasOutput = pid.calcPID_reg4(slopeMovingAverage, set_point, True)
                    gasOutput = pid.calcPID_reg4(tempMovingAverage, set_point, True)
                    # send to heat process every cycle
                    if not oldMode == mode:
                        myRoaster.getGasServo().setToSafeLow()
                        print "%s changing to %s" %(oldMode,mode)
                    oldMode = mode
                    parentHeat.send([sampleTime, gasOutput])
                    readyPIDcalc = False

            gasServoParam = [myRoaster.getGasServo().getServoId(),myRoaster.getGasServo().getSafeLow(),gasOutput]
            # put current status in queue
            try:
                paramStatus = packParamGet(temp_str, tempUnits, elapsed, mode, sampleTime, gasOutput, \
                         set_point, num_pnts_smooth, k_param, i_param, d_param,tempSensorsParam, gasServoParam, rotation) 

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
        while childParamConn.poll(): #POST settings - Received POST from web browser or Android device
            paramStatus = childParamConn.recv()
            tempUnits, mode, sampleTime, gasOutput_temp,  set_point, num_pnts_smooth, \
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

    # Load up our config
    tree = ET.parse('config.xml')
    xml_root = tree.getroot()
    template_name = xml_root.find('Template').text.strip()
    root_dir_elem = xml_root.find('RootDir')
    if root_dir_elem is not None:
        param.config["rootDir"] = root_dir_elem.text.strip()
        os.chdir(param.config["rootDir"])
    else:
        print("No RootDir tag found in config.xml, running from current directory")

    # Retrieve root element from config.xml for parsing
    param.config["tempUnits"] = xml_root.find('Temp_Units').text.strip()

    # Look for roasters
    for roasters in xml_root.iter('Roasters'):
        print ("found roasters")
        for roaster in roasters:
            param.config["roasterId"] = roaster.find('Roaster_Id').text

            # grab our gas servo
            servo       = roaster.find('Servo')
            param.config["servoId"]         = servo.find('Servo_Id').text
            param.config["servoDriver"]     = servo.find('Servo_Driver').text
            param.config["servoDelay"]      = float(servo.find('Servo_Delay').text)
            param.config["servoStepPin"]     = int(servo.find('Step_Pin').text)
            param.config["servoDirPin"]     = int(servo.find('Dir_Pin').text)
            param.config["servoMS1Pin"]     = int(servo.find('MS1_Pin').text)
            param.config["servoMS2Pin"]     = int(servo.find('MS2_Pin').text)
            param.config["servoHomePin"]    = int(servo.find('Home_Pin').text)
            param.config["servoSteps"]      = servo.find('Step').text
            param.config["servoStepsPer"]   = int(servo.find('Steps_Per_Rotation_Full').text)

            # get our valve info
            valve    = roaster.find('Valve')
            param.config["valveMaxTurns"]   = int(valve.find('Max_Turns_Ceil').text)
            param.config["valveSafeLow"]    = int(valve.find('Safe_Low_Percent').text)

    logger = logging.getLogger('werkzeug')
    handler = logging.FileHandler('access.log')
    logger.addHandler(handler)
    app.debug = True
    app.run(use_reloader=False, host='0.0.0.0')
