import mido
from mido import MidiFile, Message, tempo2bpm, MidiTrack,MetaMessage

from neopixel import *
import argparse

import RPi.GPIO as GPIO

def find_between(s, start, end):
    try:
        return (s.split(start))[1].split(end)[0]
    except:
        return False

class LedStrip:
    def __init__(self):
        # LED strip configuration:
        LED_COUNT      = 176     # Number of LED pixels.
        LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
        #LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
        LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
        LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
        LED_BRIGHTNESS = 110     # Set to 0 for darkest and 255 for brightest
        LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
        LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
        args = parser.parse_args()

        # Create NeoPixel object with appropriate configuration.
        self.strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        # Intialize the library (must be called once before other functions).
        self.strip.begin()

ledstrip = LedStrip()

ports = mido.get_input_names()

for port in ports:
	if "Through" not in port and "RPi" not in port and "RtMidOut" not in port:
		try:
			inport =  mido.open_input(port)
			print("Inport set to "+port)
		except:
			print ("Failed to set "+port+" as inport")

green = 255
red = 255
blue = 255

while True:
	for msg in inport.iter_pending():
		note = find_between(str(msg), "note=", " ")
		original_note = note
		note = int(note)
		if "note_off" in str(msg):
			velocity = 0
		else:
			velocity = find_between(str(msg), "velocity=", " ")
		#changing offset to adjust the distance between the LEDs to the key spacing
		if(note > 92):
			note_offset = 2
		elif(note > 55):
			note_offset = 1
		else:
			note_offset = 0
			
		if(int(velocity) == 0 and int(note) > 0):
			ledstrip.strip.setPixelColor(((note - 20)*2 - note_offset), Color(0, 0, 0)) 
		elif(int(velocity) > 0 and int(note) > 0):
			ledstrip.strip.setPixelColor(((note - 20)*2 - note_offset), Color(green,red,blue))
	ledstrip.strip.show()
