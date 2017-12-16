class TempSensor:
    tempSensorId    = ''
    myTempSensor    = None

    def __init__(self, tempSensorId, driver, spi, clk='', cs='', do=''):
        tempDriver = __import__(driver)
        self.tempSensorId = tempSensorId
        if spi == "hardware":
            import Adafruit_GPIO.SPI as SPI

            # Raspberry Pi hardware SPI configuration.
            SPI_PORT   = 0
            SPI_DEVICE = 0
            self.myTempSensor = tempDriver.tempDriver(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE))
        elif spi == "gpio":
            self.myTempSensor = tempDriver.tempDriver(int(tempSensor.find('clk').text), \
                                            int(tempSensor.find('cs').text), \
                                            int(tempSensor.find('do').text))
        else:
            print "ABORT!!!"

        print("Constructing %s sensor %s"%(driver,tempSensorId))
