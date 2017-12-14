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


from multiprocessing import Process, Pipe, Queue, current_process
from Queue import Full
from subprocess import Popen, PIPE, call
from datetime import datetime
import time, random, serial, os
import sys
from smbus import SMBus
import RPi.GPIO as GPIO
from pid import pidpy as PIDController
import xml.etree.ElementTree as ET
from flask import Flask, render_template, request, jsonify

import Temp1Wire
import Display

global parent_conn, parent_connB, parent_connC, statusQ, statusQ_B, statusQ_C
global xml_root, template_name, pinHeatList, pinGPIOList
global brewtime, oneWireDir

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
    if sensorNum == "1":
        print("got post to temp sensor 1")
        parent_conn.send(param.status)
    elif sensorNum == "2":
        print("got post to temp sensor 2")
        if len(pinHeatList) >= 2:
            parent_connB.send(param.status)
        else:
            param.status["mode"] = "No Temp Control"
            param.status["set_point"] = 0.0
            param.status["duty_cycle"] = 0.0 
            parent_connB.send(param.status)
            print("no heat GPIO pin assigned")
    elif sensorNum == "3":
        print("got post to temp sensor 3")
        if len(pinHeatList) >= 3:
            parent_connC.send(param.status)
        else:
            param.status["mode"] = "No Temp Control"
            param.status["set_point"] = 0.0
            param.status["duty_cycle"] = 0.0 
            parent_connC.send(param.status)
            print("no heat GPIO pin assigned")
    else:
        print("Sensor doesn't exist (POST)")
        
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
    
#get status from RasPiBrew using firefox web browser (first temp sensor / backwards compatibility)
@app.route('/getstatus') #only GET
def getstatusB():          
    #blocking receive - current status    
    param.status = statusQ.get()        
    return jsonify(**param.status)

#get status from RasPiBrew using firefox web browser (selectable temp sensor)
@app.route('/getstatus/<sensorNum>') #only GET
def getstatus(sensorNum=None):          
    #blocking receive - current status
    if sensorNum == "1":
        param.status = statusQ.get()
    elif sensorNum == "2":
        param.status = statusQ_B.get()
    elif sensorNum == "3":
        param.status = statusQ_C.get()
    else:
        print("Sensor doesn't exist (GET)")
        param.status["temp"] = "-999"
        
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
def tempControlProc(myTempSensor, display, pinNum, readOnly, paramStatus, statusQ, conn):
    print "tempControlProc"

def logdata(tank, temp, heat):
    f = open("brewery" + str(tank) + ".csv", "ab")
    if sys.version_info >= (3, 0):
        f.write("%3.1f;%3.3f;%3.3f\n".encode("utf8") % (getbrewtime(), temp, heat))
    else:
        f.write("%3.1f;%3.3f;%3.3f\n" % (getbrewtime(), temp, heat))
    f.close()


if __name__ == '__main__':
    app.debug = True 
    app.run(use_reloader=False, host='0.0.0.0')
