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


import time, random, serial, os
import sys
from flask import Flask, render_template, request, jsonify
import xml.etree.ElementTree as ET
import Roaster
from multiprocessing import Queue, Pipe, Process, current_process
#from Queue import Full
#from subprocess import Popen, PIPE, call
#from datetime import datetime
#from smbus import SMBus
#import RPi.GPIO as GPIO
#from pid import pidpy as PIDController

import Temp1Wire
import Display

#global xml_root, template_name, pinHeatList, pinGPIOList
#global brewtime, oneWireDir

parent_conn = None
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
        parent_conn.send(param.status)  
        
        return 'OK'

#post params (selectable temp sensor number)    
@app.route('/postparams/<sensorNum>', methods=['POST'])
def postparams(sensorNum=None):
    
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
    parent_conn.send(param.status)
        
    return 'OK'

#post GPIO     
@app.route('/GPIO_Toggle/<GPIO_Num>/<onoff>', methods=['GET'])
def GPIO_Toggle(GPIO_Num=None, onoff=None):
    
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
    global roasterStatusQ
    #blocking receive - current status
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
def gettempProc(conn, myTempSensor):
    p = current_process()
    print('Starting:', p.name, p.pid)
    
    while (True):
        t = time.time()
        time.sleep(.5) #.1+~.83 = ~1.33 seconds
        num = myTempSensor.readTempC()
        elapsed = "%.2f" % (time.time() - t)
        conn.send([num, myTempSensor.sensorNum, elapsed])
        
#Get time heating element is on and off during a set cycle time
def getonofftime(cycle_time, duty_cycle):
    duty = duty_cycle/100.0
    on_time = cycle_time*(duty)
    off_time = cycle_time*(1.0-duty)   
    return [on_time, off_time]
        
# Stand Alone Heat Process using GPIO
def heatProcGPIO(cycle_time, duty_cycle, pinNum, conn):
    print "heatProcGPIO"

def unPackParamInitAndPost(paramStatus):
    print "unPackParamInitAndPost"           

def packParamGet(numTempSensors, myTempSensorNum, temp, tempUnits, elapsed, mode, cycle_time, duty_cycle, boil_duty_cycle, set_point, \
                                 boil_manage_temp, num_pnts_smooth, k_param, i_param, d_param):
    
    print "packParamGet"
        
# Main Temperature Control Process
def tempControlProc(myRoaster, paramStatus, conn):
    print "tempControlProc"
    mode, cycle_time, duty_cycle, boil_duty_cycle, set_point, boil_manage_temp, num_pnts_smooth, \
    k_param, i_param, d_param = unPackParamInitAndPost(paramStatus)

    p = current_process()
    print('Starting:', p.name, p.pid)

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
            roasterStatusQ.append(Queue(2)) #blocking queue        

            parent_conn, child_conn = Pipe()
            readOnly = False
            pinNum = step # CHANGE THIS. We need to pass in all of the servo information to the tempControlProc which passes it to the heat control
            p = Process(name = "tempControlProc", target=tempControlProc, args=(myRoaster, param.status, child_conn))
            p.start()



    app.debug = True 
    app.run(use_reloader=False, host='0.0.0.0')
