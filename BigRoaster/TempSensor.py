class TempSensor:
    tempSensorId    = ''
    tempSensorName  = ''
    myTempSensor    = None
    myPipe          = None

    def __init__(self, tempSensorId, tempSensorName='', driver='', spi='', clk='', cs='', do=''):
        self.tempSensorId = tempSensorId
        self.tempSensorName = tempSensorName

        if not driver == '':
            tempDriver = __import__(driver)
            myDriver = getattr(tempDriver,driver)

        if spi == "hardware":
            import Adafruit_GPIO.SPI as SPI

            # Raspberry Pi hardware SPI configuration.
            SPI_PORT   = 0
            SPI_DEVICE = 0
            self.myTempSensor = myDriver(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE))
        elif spi == "gpio":
            self.myTempSensor = myDriver(int(tempSensor.find('clk').text), \
                                            int(tempSensor.find('cs').text), \
                                            int(tempSensor.find('do').text))
        else:
            # Doing this until we eliminate this class entirely
            self.myTempSensor = None

        print("Constructing %s sensor %s"%(driver,tempSensorId))

    def addTempPipe(self, pipe):
        self.myPipe = pipe

    def getTempPipe(self):
        return self.myPipe

    def getTempSensorName(self):
        return self.tempSensorName

    def getTempSensorId(self):
        return self.tempSensorId

    def readTempC(self):
        return self.myTempSensor.readTempC()
