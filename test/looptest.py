#!/usr/bin/python
import time
import datetime
from pprint import pprint

num_pnts_smooth = 5
tempMovingAverageList = []
tempMovingAverage = 0.0
slopeMovingAverageList = []
slopeMovingAverage = 0.0

for temp in range(6):
    time.sleep(10)
    tempMovingAverageList.append({"temp":temp,"timestamp":time.time()})
    tempMovingAverage = 0.0
    while (len(tempMovingAverageList) > num_pnts_smooth):
        tempMovingAverageList.pop(0) # remove oldest elements in list

    for temp_pnt in tempMovingAverageList:
        tempMovingAverage += temp_pnt["temp"]
    tempMovingAverage /= len(tempMovingAverageList)

    if len(tempMovingAverageList) > 1:
        i = 0
        while i < len(tempMovingAverageList)-1:
            diff = tempMovingAverageList[i+1]["temp"] - tempMovingAverageList[i]["temp"]
            timediff = tempMovingAverageList[i+1]["timestamp"] - tempMovingAverageList[i]["timestamp"]
            print 'timediff before is ', timediff
            timediff /= 300
            #timediff = int(timediff)
            print 'timediff is ', timediff
            slope = diff / timediff
            slopeMovingAverage =+ slope
            i += 1
        slopeMovingAverage /= len(tempMovingAverageList)

    print tempMovingAverage, " : ", slopeMovingAverage

