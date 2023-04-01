#!/usr/bin/env python3

import RPi.GPIO as GPIO
import configparser
import os
import schedule
import time

# config file should be the same folder.
os.chdir('/home/pi/inky/weather-impression')
project_root = os.getcwd()
configFilePath = project_root + '/config.txt'


# Gpio pins for each button (from top to bottom)
BUTTONS = [5, 6, 16, 24]

# These correspond to buttons A, B, C and D respectively
LABELS = ['A', 'B', 'C', 'D']

# Set up RPi.GPIO with the "BCM" numbering scheme
GPIO.setmode(GPIO.BCM)

# Buttons connect to ground when pressed, so we should set them up
# with a "PULL UP", which weakly pulls the input signal to 3.3V.
GPIO.setup(BUTTONS, GPIO.IN, pull_up_down=GPIO.PUD_UP)


# refresh inky impression screen
def refreshScreen():
    import weather
    weather.update()



# "handle_button" will be called every time a button is pressed
# It receives one argument: the associated input pin.
def handle_button(pin):

    config = configparser.ConfigParser()
    config.read_file(open(configFilePath))

    # Top button(Forecasts)
    if pin == 5:
        config.set("openweathermap", "one_time_message", "MODE:Forecast")
        config.set("openweathermap", "mode", "0")
        with open(configFilePath, 'w') as configfile:
            config.write(configfile)

    # Second button(Graph mode)
    if pin == 6:
        config.set("openweathermap", "one_time_message", "MODE:Graph")
        config.set("openweathermap", "mode", "2")
        with open(configFilePath, 'w') as configfile:
            config.write(configfile)

    # Second button( mode)
    if pin == 16:
        config.set("openweathermap", "one_time_message", "MODE:Alert")
        config.set("openweathermap", "mode", "1")
        with open(configFilePath, 'w') as configfile:
            config.write(configfile)

    # 4th button(C/F)
    if pin == 24:
        unit = config.get('openweathermap', 'TEMP_UNIT', raw=False)
        if unit == 'imperial':
            config.set("openweathermap", "one_time_message", "Unit:Metric")
            config.set("openweathermap", "TEMP_UNIT", "metric")
        else:
            config.set("openweathermap", "one_time_message", "Unit:Imperial")
            config.set("openweathermap", "TEMP_UNIT", "imperial")
        
        with open(configFilePath, 'w') as configfile:
            config.write(configfile)

    # refresh the screen
    try:
        refreshScreen()
    except:
        print("Weather update failed.")
        pass



# Loop through out buttons and attach the "handle_button" function to each
# We're watching the "FALLING" edge (transition from 3.3V to Ground) and
# picking a generous bouncetime of 250ms to smooth out button presses.
for pin in BUTTONS:
    GPIO.add_event_detect(pin, GPIO.FALLING, handle_button, bouncetime=250)

#schedule.every().minute.at(":23").do(refreshScreen)
schedule.every().hour.at(":01").do(refreshScreen)

while True:
    schedule.run_pending()
    time.sleep(1)