class GasServo:
    gasServoId    = ''
    myGasServo    = None

    def __init__(self, gasServoId, driver, delay, max_rotations, \
                    step, direction, ms1, ms2, sleep = 0, enable = 0, reset = 0, \
                    home_low_pin = '', home_high_pin = ''):

        import driver as gasDriver
        self.gasServoId = gasServoId
        self.myGasServo = gasDriver.gasDriver(step,delay,direction,ms1,ms2,sleep,enable,reset,gasServoId)

        print("Constructing %s servo %s"%(driver, gasServoId))
