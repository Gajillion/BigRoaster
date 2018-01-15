class GasServo:
    gasServoId  = ''
    myGasServo  = None
    homeLow     = ''         
    homeHigh    = ''
    gasOutput   = 0
    stepValue   = 'full_step'
    stepsInFull = 200
    maxTurns    = 0

    def __init__(self, gasServoId, driver, delay, step, direction, ms1, ms2,\
                    home_low_pin = '', home_high_pin = '', stepValue = 'full_step',\
                    stepsInFull = 200, sleep = 0, enable = 0, reset = 0):


        gasDriver = __import__(driver)
        myDriver = getattr(gasDriver,driver)

        if home_low_pin == '' or home_high_pin == '':
            print "Must supply pin for low and high homing switches"
            return None

        self.gasServoId     = gasServoId
        
        self.myGasServo     = myDriver(step,delay,direction,ms1,ms2,sleep,enable,reset,gasServoId)
        self.homeLow        = home_low_pin
        self.homeHigh       = home_high_pin
        self.stepsInFull    = stepsInFull
        self.stepValue      = stepValue
        
        stepset = getattr(myDriver,'set_'+stepValue)

        print("Constructing %s servo %s"%(driver, gasServoId))

    def setGasOutput(self,valvePercent):
        if valvePercent == self.gasOutput:
            return
        else:
            # find out how many steps we are away
            diff = self.gasOutput - valvePercent
            print "Moving gas output %s turns" % diff
            # turn the servo that many steps +/-
            self.gasOutput = valvePercent 

    def setMaxTurns(self,maxTurns):
        self.maxTurns = maxTurns

    def getMaxTurns(self):
        return self.maxTurns
