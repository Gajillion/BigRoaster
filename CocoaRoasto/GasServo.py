import RPi.GPIO as GPIO
import time

# Direction of rotation is dependent on how the motor is connected.
# If the motor runs the wrong way swap the values of cw and ccw.
CW = True
CCW = False

class GasServo:
    gasServoId      = ''
    myGasServo      = None
    homePin         = ''         
    gasOutput       = 0
    gasOutputTurns  = 0
    stepValue       = 'full_step'
    stepsInFull     = 200
    maxTurns        = ''
    safeLowSteps    = ''

    def __init__(self, gasServoId, driver, delay, step, direction, ms1, ms2,\
                    homePin='', maxTurns=0, safeLow=20, stepValue='full_step',\
                    stepsInFull=200, sleep=0, enable=0, reset=0):


        gasDriver = __import__(driver)
        myDriver = getattr(gasDriver,driver)

        if homePin == '' :
            print "Must supply pin for low and high homing switches"
            return None
        else:
            self.homePin        = homePin
            # Should have copied this information in via params
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.homePin, GPIO.IN, pull_up_down=GPIO.PUD_UP)


        self.gasServoId     = gasServoId
        self.myGasServo     = myDriver(step,delay,direction,ms1,ms2,sleep,enable,reset,gasServoId)
        self.stepsInFull    = stepsInFull
        self.stepValue      = stepValue
        self.maxTurns       = maxTurns
        # safeLowSteps is the number of steps in the percentage of a single turn passed in safe Low 
        self.safeLowSteps   = int(stepsInFull * (safeLow * 0.01))
        
        stepset = getattr(myDriver,'set_'+stepValue)


        print("Constructing %s servo %s"%(driver, gasServoId))

    def setGasOutput(self,valvePercent):
        if valvePercent == self.gasOutput:
            return
        else:
            # find out how many steps we are away
            diff = valvePercent - self.gasOutput
            print "Moving gas output %s steps" % diff
            if diff < 0:
                self.myGasServo.set_direction(CCW)
            else:
                self.myGasServo.set_direction(CW)

            print "My max turns is %s " % self.maxTurns
            # turn the servo that many steps +/-
            # we're ignorning non-full steps
            totalTurns = (self.maxTurns * self.stepsInFull)
            totalStepsF = totalTurns * (diff * 0.01)
            totalSteps = abs(int(totalStepsF))
            print "A diff of %s is %s totalTurns, %s totalFloatSteps, and %s totalSteps" % (diff,totalTurns,totalStepsF,totalSteps)
            for s in range(0,totalSteps):
                self.myGasServo.step()
            self.gasOutput = valvePercent 
            self.gasOutputTurns = self.gasOutputTurns + int(totalStepsF)

    def getMaxTurns(self):
        return self.maxTurns

    def setOff(self):
        self.home()

    # set our gas valve to the lowest setting without putting out the flame
    def setToSafeLow(self):
        # just to be sure
        self.home()
        time.sleep(0.5)
        for s in range(0,self.safeLowSteps):
            self.myGasServo.step()
        # safeLow is our floor, the lowest we'll ever go. Consider output and location 0
        self.gasOutput = 0
        self.gasOutputTurns = 0

    # Turn the valve all the way off
    def home(self):
        print("Homing servo %s" % self.gasServoId)
        self.myGasServo.set_direction(CCW)
        while(GPIO.input(self.homePin) == True):
            self.myGasServo.step()
        self.myGasServo.set_direction(CW)
        print("Servo %s is homed" % self.gasServoId)
        self.gasOutput = 0
        self.gasOutputTurns = 0
