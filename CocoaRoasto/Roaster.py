import TempSensor
import GasServo

class Roaster:
    roasterId   = ''
    gasServo    = None
    tempProbes  = []
    statusQueue = None
    maxTurns    = 0

    def __init__(self, roasterId):
        self.roasterId = roasterId

    def addTempSensor(self,tempSensorId,driver,spi,clk='',cs='',do=''):
        if spi == 'hardware':
            self.tempProbes.append(TempSensor.TempSensor(tempSensorId,driver,spi))
        else:
            self.tempProbes.append(TempSensor.TempSensor(tempSensorId,driver,spi,clk,cs,do))

    def getTempSensors(self):
        return self.tempProbes

    def addGasServo(self,servoId,driver,delay,step,direction,ms1,ms2,\
                    home_low_pin='',home_high_pin='',sleep=0,enable=0,reset=0):
        self.gasServo = GasServo.GasServo(servoId,driver,delay,step,direction,ms1,ms2,\
                    home_low_pin,home_high_pin,sleep,enable,reset)

    def getGasServo(self):
        return self.gasServo

    def addStatusQ(self,statusQ):
        self.statusQueue = statusQ

    def getStatusQ(self):
        return self.statusQueue

    def setMaxTurns(self,maxTurns):
        self.maxTurns = maxTurns
        try:
            gasServo.setMaxTurns(maxTurns)
        except:
            print "Must instantiate gas servo before setting max turns"

    def getMaxTurns(self):
        return self.maxTurns
