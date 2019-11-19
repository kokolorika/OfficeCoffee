#!/usr/bin/python2

import thingspeak
import time
import sys
import logging

#thingspeak.requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':ADH-AES128-SHA256'

# Configure log file and level
logging.basicConfig(filename='app.log',level=logging.DEBUG)

# ThingSpeak Stuff
CHANNEL_ID = 762284 # your channel id
WRITE_KEY = "PTS9LJH7XS14MWIP" # channel write key
READ_KEY = "A5FR11R5SATF5TQ2" # channel read key

# Coffee Stuff
EMPTY_POT = 1318 # wigth of the empty pot

# Measurement config params
SAMPLING_RATE = 2 # number of samples per second
AVG_WINDOW_SIZE = 5 # window size of the moving avg

EMULATE_HX711=False

if not EMULATE_HX711:
    import RPi.GPIO as GPIO
    from hx711 import HX711
else:
    from emulated_hx711 import HX711

hx = HX711(5, 6)

# I've found out that, for some reason, the order of the bytes is not always the same between versions of python, numpy and the hx711 itself.
# Still need to figure out why does it change.
# If you're experiencing super random values, change these values to MSB or LSB until to get more stable values.
# There is some code below to debug and log the order of the bits and the bytes.
# The first parameter is the order in which the bytes are used to build the "long" value.
# The second paramter is the order of the bits inside each byte.
# According to the HX711 Datasheet, the second parameter is MSB so you shouldn't need to modify it.
hx.set_reading_format("MSB", "MSB")

# HOW TO CALCULATE THE REFFERENCE UNIT
# To set the reference unit to 1. Put 1kg on your sensor or anything you have and know exactly how much it weights.
# In this case, 92 is 1 gram because, with 1 as a reference unit I got numbers near 0 without any weight
# and I got numbers around 184000 when I added 2kg. So, according to the rule of thirds:
# If 2000 grams is 184000 then 1000 grams is 184000 / 2000 = 92.
hx.set_reference_unit(-102.3)
#hx.set_r5eference_unit(1)

hx.reset()
hx.tare()

print("Tare done! Add weight now...")


def cleanAndExit():
    print("Cleaning...")

    if not EMULATE_HX711:
        GPIO.cleanup()
        
    print("Bye!")
    sys.exit()


def measure():
    try:
        # These three lines are usefull to debug wether to use MSB or LSB in the reading formats
        # for the first parameter of "hx.set_reading_format("LSB", "MSB")".
        # Comment the two lines "val = hx.get_weight(5)" and "print val" and uncomment these three lines to see what it prints.
        
        # np_arr8_string = hx.get_np_arr8_string()
        # binary_string = hx.get_binary_string()
        # print binary_string + " " + np_arr8_string
        
        # Prints the weight. Comment if you're debbuging the MSB and LSB issue.
        #val = hx.get_weight(5)
        val = max(0, int(hx.get_weight(5)))

        # To get weight from both channels (if you have load cells hooked up 
        # to both channel A and B), do something like this
        #val_A = hx.get_weight_A(5)
        #val_B = hx.get_weight_B(5)
        #print "A: %s  B: %s" % ( val_A, val_B )

        hx.power_down()
        hx.power_up()
        
        return val
    except:
        print("could not read value")


def postToThingSpeakChannel(channel, val):
    try:
        return channel.update({'field1': val})
    except:
	err = sys.exc_info()[0]
	logging.exception(repr(err))
        print("connection failed")
        

def measureX(times, rate):
    samples = []

    while len(samples) < times:
        val = measure()
        print("Measured value: %d" % val)
        samples.append(val)
        time.sleep(1/rate)
    
    return samples

def calcLiquidLevel(val):
    return val - EMPTY_POT

def calcAvg(values):
    return int(sum(values) / len(values))

if __name__ == "__main__":
    channel = thingspeak.Channel(id=CHANNEL_ID, write_key=WRITE_KEY, api_key=READ_KEY)
    logging.info(repr(channel))

    avgHistory = []

    try:
        while True:
            samples = measureX(AVG_WINDOW_SIZE, SAMPLING_RATE)
            print(samples)

            avg = calcAvg(samples)
            print("AVG: %d" % avg)

            avgHistory.append(avg)
            print(avgHistory)

            if len(avgHistory) > 1:
                delta = avgHistory[1] - avgHistory[0] # d=b-a
                print("d: %d" % delta)

                if delta < 0:
                    # liquid level decreases
                    liquidLevel = calcLiquidLevel(avg)

                    if liquidLevel < 0:
                        liquidLevel = 0

                    response = postToThingSpeakChannel(channel, liquidLevel)
                    print("Response: " + response)
                    del avgHistory[:]
                elif delta > 10:
                    # liquid level increases
                    # TODO implement
		    print("liquid level increases --> TODO")

    except (KeyboardInterrupt, SystemExit):
        cleanAndExit()
