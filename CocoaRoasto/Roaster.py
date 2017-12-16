import TempSensor
import GasServo

class Roaster:
    roasterId   = ''
    gasServo    = None
    tempProbes  = []

    def __init__(self, roasterId):
        self.roasterId = roasterId

    def addTempSensor(self,tempSensorId,driver,spi,clk='',cs='',do=''):
        if spi == 'hardware':
            self.tempProbes.append(TempSensor.TempSensor(tempSensorId,driver,spi))
        else:
            self.tempProbes.append(TempSensor.TempSensor(tempSensorId,driver,spi,clk,cs,do))

    def addGasServo(self,servoId,driver,step,dir,ms1,ms2):
        gasServo = GasServo.GasServo(servoId,driver,step,dir,ms1,ms2)

