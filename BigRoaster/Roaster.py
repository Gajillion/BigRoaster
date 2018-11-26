import TempSensor
import GasServo
import pprint

class Roaster:
    roasterId   = ''
    gasServo    = None
    tempProbes  = []
    statusQueue = None

    def __init__(self, roasterId):
        self.roasterId = roasterId

    def addTempSensor(self,tempSensorId,name='',driver='',spi='',clk='',cs='',do=''):
        if spi == 'hardware':
            self.tempProbes.append(TempSensor.TempSensor(tempSensorId,name,driver,spi))
        elif spi == "gpio":
            self.tempProbes.append(TempSensor.TempSensor(tempSensorId,name,driver,spi,clk,cs,do))
        else:
            self.tempProbes.append(TempSensor.TempSensor(tempSensorId,name))
        
    def getTempSensors(self):
        return self.tempProbes

    def addGasServo(self,servoId,driver,delay,step,direction,ms1,ms2,\
                    homePin='',maxTurns=0,safeLow=20,sleep=0,enable=0,reset=0):
        self.gasServo = GasServo.GasServo(servoId,driver,delay,step,direction,ms1,ms2,\
                    homePin,maxTurns,safeLow,sleep,enable,reset)

    def getGasServo(self):
        return self.gasServo

