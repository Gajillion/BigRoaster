import Adafruit_GPIO.SPI as SPI
import Adafruit_MAX31855.MAX31855 as MAX31855

class TempMAX31855:
    numSensor = 0

    def __init__(self, spi, tempSensorId,clk=None, cs=None, do=None):
        if spi == "hardware":
            # Raspberry Pi hardware SPI configuration.
            SPI_PORT   = 0
            SPI_DEVICE = 0
            self.sensor = MAX31855.MAX31855(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE))
        elif spi == "gpio":
           self.sensor = MAX31855.MAX31855(clk, cs, do)
        else:
            print "ABORT!!!"

        self.tempSensorId = tempSensorId
        self.sensorNum = TempMAX31855.numSensor
        TempMAX31855.numSensor += 1
        print("Constructing MAX31855 sensor %s"%(tempSensorId))

    def readTempC(self):
        temp_C = self.sensor.readTempC()
          
        return temp_C
