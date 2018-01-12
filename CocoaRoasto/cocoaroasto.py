#
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
import time, random, serial, os
import sys
from flask import Flask, render_template, request, jsonify
import xml.etree.ElementTree as ET
import Roaster
from multiprocessing import Queue, Pipe, Process, current_process
from Queue import Full
#from subprocess import Popen, PIPE, call
#from datetime import datetime
#from smbus import SMBus
#import RPi.GPIO as GPIO
#from pid import pidpy as PIDController

import Temp1Wire

#global xml_root, template_name, pinHeatList, pinGPIOList
#global brewtime, oneWireDir

global parent_conn
roasterStatusQ = []

app = Flask(__name__, template_folder='templates')
#url_for('static', filename='raspibrew.css')

#Parameters that are used in the temperature control process
class param:
    status = {
        "numTempSensors" : 0,
        "temp" : "0",
        "tempUnits" : "F",
        "elapsed" : "0",
        "mode" : "off",
        "cycle_time" : 2.0,
        "duty_cycle" : 0.0,
        "boil_duty_cycle" : 60,
        "set_point" : 0.0,
        "boil_manage_temp" : 200,
        "num_pnts_smooth" : 5,
        "k_param" : 44,
        "i_param" : 165,
        "d_param" : 4             
    }
                      
# main web page    
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        #render main page
        return render_template(template_name, mode = param.status["mode"], set_point = param.status["set_point"], \
                               duty_cycle = param.status["duty_cycle"], cycle_time = param.status["cycle_time"], \
                               k_param = param.status["k_param"], i_param = param.status["i_param"], \
                               d_param = param.status["d_param"])
        
    else: #request.method == 'POST' (first temp sensor / backwards compatibility)
        # get command from web browser or Android   
        #print request.form
        param.status["mode"] = request.form["mode"] 
        param.status["set_point"] = float(request.form["setpoint"])
        param.status["duty_cycle"] = float(request.form["dutycycle"]) #is boil duty cycle if mode == "boil"
        param.status["cycle_time"] = float(request.form["cycletime"])
        param.status["boil_manage_temp"] = float(request.form.get("boilManageTemp", param.status["boil_manage_temp"])) 
        param.status["num_pnts_smooth"] = int(request.form.get("numPntsSmooth", param.status["num_pnts_smooth"])) 
        param.status["k_param"] = float(request.form["k"])
        param.status["i_param"] = float(request.form["i"])
        param.status["d_param"] = float(request.form["d"])
                
        #send to main temp control process 
        #if did not receive variable key value in POST, the param class default is used
        print pprint.pprint(param.status)
        parent_conn.send(param.status)  
        
        return 'OK'

#post params (selectable temp sensor number)    
@app.route('/postparams/<sensorNum>', methods=['POST'])
def postparams(sensorNum=None):
    print "postparams"    
    param.status["mode"] = request.form["mode"] 
    param.status["set_point"] = float(request.form["setpoint"])
    param.status["duty_cycle"] = float(request.form["dutycycle"]) #is boil duty cycle if mode == "boil"
    param.status["cycle_time"] = float(request.form["cycletime"])
    param.status["boil_manage_temp"] = float(request.form.get("boilManageTemp", param.status["boil_manage_temp"])) 
    param.status["num_pnts_smooth"] = int(request.form.get("numPntsSmooth", param.status["num_pnts_smooth"]))
    param.status["k_param"] = float(request.form["k"])
    param.status["i_param"] = float(request.form["i"])
    param.status["d_param"] = float(request.form["d"])
            
    print pprint.pprint(param.status)
    #send to main temp control process 
    #if did not receive variable key value in POST, the param class default is used
    parent_conn.send(param.status)
        
    return 'OK'

#post GPIO     
@app.route('/GPIO_Toggle/<GPIO_Num>/<onoff>', methods=['GET'])
def GPIO_Toggle(GPIO_Num=None, onoff=None):
    print "GPIO_Toggle"
    if len(pinGPIOList) >= int(GPIO_Num):
        out = {"pin" : pinGPIOList[int(GPIO_Num)-1], "status" : "off"}
        if onoff == "on":
            GPIO.output(pinGPIOList[int(GPIO_Num)-1], ON)
            out["status"] = "on"
            print("GPIO Pin #%s is toggled on" % pinGPIOList[int(GPIO_Num)-1]) 
        else: #off
            GPIO.output(pinGPIOList[int(GPIO_Num)-1], OFF)
            print("GPIO Pin #%s is toggled off" % pinGPIOList[int(GPIO_Num)-1]) 
    else:
        out = {"pin" : 0, "status" : "off"}
        
    return jsonify(**out)
    
#get status from RasPiBrew using firefox web browser (selectable temp sensor)
@app.route('/getstatus/<roasterNum>') #only GET
def getstatus(roasterNum=None):          
    print "getstatus"
    global roasterStatusQ
    # blocking receive - current status
    roasterN = int(roasterNum)
    if roasterN > len(roasterStatusQ):
        print("Sensor doesn't exist (GET)")
        param.status["temp"] = "-999"
    else:
        param.status = roasterStatusQ[roasterN-1].get()

    return jsonify(**param.status)

def getbrewtime():
    return (time.time() - brewtime)    
       
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
def getonofftime(cycle_time, duty_cycle):
    duty = duty_cycle/100.0
    on_time = cycle_time*(duty)
    off_time = cycle_time*(1.0-duty)   
    return [on_time, off_time]
        
# Stand Alone Heat Process using GPIO
def heatProcGPIO(conn, cycle_time, duty_cycle, myGasServo):
    p = current_process()
    print('Starting:', p.name, p.pid)
    while (True):
        print "Looping"
        while (conn.poll()): #get last
            cycle_time, duty_cycle = conn.recv()
        conn.send([cycle_time, duty_cycle])
#            if duty_cycle == 0:
#                GPIO.output(pinNum, OFF)
#                time.sleep(cycle_time)
#            elif duty_cycle == 100:
#                GPIO.output(pinNum, ON)
#                time.sleep(cycle_time)
#            else:
        print "HERE!"
        on_time, off_time = getonofftime(cycle_time, duty_cycle)

        print "on_time = ", on_time, " and duty_cycle = ", duty_cycle
#        setValve(servo, int(duty_cycle))
#        GPIO.output(pinNum, ON)
#        time.sleep(on_time)
#        GPIO.output(pinNum, OFF)
        time.sleep(off_time)

def unPackParamInitAndPost(paramStatus):
    print "unPackParamInitAndPost"           
    #temp = paramStatus["temp"]
    #tempUnits = paramStatus["tempUnits"]
    #elapsed = paramStatus["elapsed"]
    mode = paramStatus["mode"]
    cycle_time = paramStatus["cycle_time"]
    duty_cycle = paramStatus["duty_cycle"]
    boil_duty_cycle = paramStatus["boil_duty_cycle"]
    set_point = paramStatus["set_point"]
    boil_manage_temp = paramStatus["boil_manage_temp"]
    num_pnts_smooth = paramStatus["num_pnts_smooth"]
    k_param = paramStatus["k_param"]
    i_param = paramStatus["i_param"]
    d_param = paramStatus["d_param"]

    return mode, cycle_time, duty_cycle, boil_duty_cycle, set_point, boil_manage_temp, num_pnts_smooth, \
           k_param, i_param, d_param

def packParamGet(numTempSensors, myTempSensorNum, temp, tempUnits, elapsed, mode, cycle_time, duty_cycle, boil_duty_cycle, set_point, \
                                 boil_manage_temp, num_pnts_smooth, k_param, i_param, d_param):
    
#    print "packParamGet"
    param.status["numTempSensors"] = numTempSensors
    param.status["myTempSensorNum"] = myTempSensorNum
    param.status["temp"] = temp
    param.status["tempUnits"] = tempUnits
    param.status["elapsed"] = elapsed
    param.status["mode"] = mode
    param.status["cycle_time"] = cycle_time
    param.status["duty_cycle"] = duty_cycle
    param.status["boil_duty_cycle"] = boil_duty_cycle
    param.status["set_point"] = set_point
    param.status["boil_manage_temp"] = boil_manage_temp
    param.status["num_pnts_smooth"] = num_pnts_smooth
    param.status["k_param"] = k_param
    param.status["i_param"] = i_param
    param.status["d_param"] = d_param

    return param.status


# Main Temperature Control Process
def tempControlProc(myRoaster, paramStatus, conn):
    print "tempControlProc"
    parentTemps = []

    mode, cycle_time, duty_cycle, boil_duty_cycle, set_point, boil_manage_temp, num_pnts_smooth, \
    k_param, i_param, d_param = unPackParamInitAndPost(paramStatus)

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
    # Fix this. What do cycle_time and duty_cycle do here?
    pheat = Process(name = "heatProcGPIO", target=heatProcGPIO, args=(c, cycle_time, duty_cycle, myRoaster.getGasServo()))
    pheat.daemon = True
    pheat.start()

    tempUnits = xml_root.find('Temp_Units').text.strip()

    # Get our PID ready
    readyPIDcalc = False
    # Temperature smoothing list
    temp_ma_list = []
    while(True):
        readytemp = False
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
                    temp_ma_list.append(temp)

                    # smooth data
                    temp_ma = 0.0 # moving avg init
                    while (len(temp_ma_list) > num_pnts_smooth):
                        temp_ma_list.pop(0) # remove oldest elements in list

                    if (len(temp_ma_list) < num_pnts_smooth):
                        for temp_pnt in temp_ma_list:
                            temp_ma += temp_pnt
                        temp_ma /= len(temp_ma_list)
                    else: # len(temp_ma_list) == num_pnts_smooth
                        for temp_idx in range(num_pnts_smooth):
                            temp_ma += temp_ma_list[temp_idx]
                        temp_ma /= num_pnts_smooth

                    print "len(temp_ma_list) = %d" % len(temp_ma_list)
                    print "Num Points smooth = %d" % num_pnts_smooth
                    print "temp_ma = %.2f" % temp_ma
                    print temp_ma_list

                    # calculate PID every cycle
                    if (readyPIDcalc == True):
                        print temp_ma, set_point
                        duty_cycle = pid.calcPID_reg4(temp_ma, set_point, True)
                        # send to heat process every cycle
                        parentHeat.send([cycle_time, duty_cycle])
                        readyPIDcalc = False

                # put current status in queue
                try:
                    paramStatus = packParamGet(numTempSensors, tempSensor.getTempSensorId(), temp_str, tempUnits, elapsed, mode, cycle_time, duty_cycle, \
                            boil_duty_cycle, set_point, boil_manage_temp, num_pnts_smooth, k_param, i_param, d_param)
                    statusQ.put(paramStatus) #GET request
                except Full:
                    pass

                while (statusQ.qsize() >= 2):
                    statusQ.get() #remove old status

                print("Current Temp: %3.2f deg %s, Heat Output: %3.1f%%" \
                                                        % (temp, tempUnits, duty_cycle))

        while parentHeat.poll(): # Poll Heat Process Pipe
            print "buttocksy"
            cycle_time, duty_cycle = parentHeat.recv() #non blocking receive from Heat Process
            readyPIDcalc = True


        time.sleep(0.01)


def logdata(tank, temp, heat):
    f = open("brewery" + str(tank) + ".csv", "ab")
    if sys.version_info >= (3, 0):
        f.write("%3.1f;%3.3f;%3.3f\n".encode("utf8") % (getbrewtime(), temp, heat))
    else:
        f.write("%3.1f;%3.3f;%3.3f\n" % (getbrewtime(), temp, heat))
    f.close()


if __name__ == '__main__':
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

            # grab our gas servo
            servo       = roaster.find('Servo')
            servoId     = servo.find('Servo_Id').text
            driver      = servo.find('Servo_Driver').text
            delay       = float(servo.find('Servo_Delay').text)
            step        = int(servo.find('Step_Pin').text)
            direction   = int(servo.find('Dir_Pin').text)
            ms1         = int(servo.find('MS1_Pin').text)
            ms2         = int(servo.find('MS2_Pin').text)
            homeLow     = int(servo.find('Home_Low_Pin').text)
            homeHigh    = int(servo.find('Home_High_Pin').text)

            myRoaster.addGasServo(servoId,driver,delay,step,direction,ms1,ms2,homeLow,homeHigh)

            statusQ = Queue(2) # blocking queue
            myRoaster.addStatusQ(statusQ)

            # Ugly, but we need to make access to the status queue global
            roasterStatusQ.append(statusQ) #blocking queue        

            parent_conn, child_conn = Pipe()
            p = Process(name = "tempControlProc", target=tempControlProc, args=(myRoaster, param.status, child_conn))
            p.start()



    app.debug = True 
    app.run(use_reloader=False, host='0.0.0.0')
