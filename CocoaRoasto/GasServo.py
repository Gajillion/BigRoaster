class GasServo:
    gasServoId  = ''
    myGasServo  = None
    homeLow     = ''         
    homeHigh    = ''

    def __init__(self, gasServoId, driver, delay, step, direction, ms1, ms2,\
                     home_low_pin = '', home_high_pin = '', \
                    sleep = 0, enable = 0, reset = 0):


        gasDriver = __import__(driver)
        myDriver = getattr(gasDriver,driver)

        if home_low_pin == '' or home_high_pin == '':
            print "Must supply pin for low and high homing switches"
            return None

        self.gasServoId = gasServoId
        self.myGasServo = myDriver(step,delay,direction,ms1,ms2,sleep,enable,reset,gasServoId)
        self.homeLow = home_low_pin
        self.homeHigh = home_high_pin

        print("Constructing %s servo %s"%(driver, gasServoId))
