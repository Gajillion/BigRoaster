import TempSensor
import GasServo

class Roaster:
    roasterId   = ''
    gasServo    = None
    tempProbes  = []
    statusQueue = None

    def __init__(self, roasterId):
        self.roasterId = roasterId

    def addTempSensor(self,tempSensorId,driver,spi,clk='',cs='',do=''):
        if spi == 'hardware':
            self.tempProbes.append(TempSensor.TempSensor(tempSensorId,driver,spi))
        else:
            self.tempProbes.append(TempSensor.TempSensor(tempSensorId,driver,spi,clk,cs,do))

    def addGasServo(self,servoId,driver,delay,step,direction,ms1,ms2,\
                    home_low_pin='',home_high_pin='',sleep=0,enable=0,reset=0):
        gasServo = GasServo.GasServo(servoId,driver,delay,step,direction,ms1,ms2,\
                    home_low_pin,home_high_pin,sleep,enable,reset)

    def addStatusQ(self,statusQ):
        statusQueue = statusQ

    def getStatusQ(self):
        return statusQueue
