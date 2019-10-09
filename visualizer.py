from xml.dom import minidom

import LCD_1in44
import LCD_Config

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageColor

import RPi.GPIO as GPIO
import time
import random

import webcolors as wc

import sys
import os
import datetime
import psutil

os.chdir(sys.path[0])

import mido
from mido import MidiFile, Message, tempo2bpm, MidiTrack,MetaMessage

from neopixel import *
import argparse

class LedStrip:
    def __init__(self):
        
        self.brightness_percent = 50
        self.brightness = 255 * self.brightness_percent / 100
        
        # LED strip configuration:
        self.LED_COUNT      = 176     # Number of LED pixels.
        self.LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
        #LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
        self.LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
        self.LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
        self.LED_BRIGHTNESS = int(self.brightness)    # Set to 0 for darkest and 255 for brightest
        self.LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
        self.LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
        args = parser.parse_args()

        # Create NeoPixel object with appropriate configuration.
        self.strip = Adafruit_NeoPixel(self.LED_COUNT, self.LED_PIN, self.LED_FREQ_HZ, self.LED_DMA, self.LED_INVERT, self.LED_BRIGHTNESS, self.LED_CHANNEL)
        # Intialize the library (must be called once before other functions).
        self.strip.begin()
        
    def change_brightness(self, value):
        self.brightness_percent += value
        if(self.brightness_percent <= 0):
            self.brightness_percent = 1
        elif(self.brightness_percent > 100):
            self.brightness_percent = 100
        self.brightness = 255 * self.brightness_percent / 100
        
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
        args = parser.parse_args()
        self.strip = Adafruit_NeoPixel(self.LED_COUNT, self.LED_PIN, self.LED_FREQ_HZ, self.LED_DMA, self.LED_INVERT, int(self.brightness), self.LED_CHANNEL)
        # Intialize the library (must be called once before other functions).
        self.strip.begin()
        fastColorWipe(ledstrip.strip, True)

KEYRIGHT = 26
KEYLEFT = 5
KEYUP = 6
KEYDOWN = 19
KEY1 = 21
KEY2 = 20
KEY3 = 16
JPRESS = 13
# pin numbers are interpreted as BCM pin numbers.
GPIO.setmode(GPIO.BCM)
# Sets the pin as input and sets Pull-up mode for the pin.
GPIO.setup(KEYRIGHT,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEYLEFT,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEYUP,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEYDOWN,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEY1,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEY2,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEY3,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(JPRESS,GPIO.IN,GPIO.PUD_UP)

#LED animations
def fastColorWipe(strip, update):
    red = int(ledsettings.get_backlight_color("Red"))* (ledsettings.backlight_brightness_percent) / 100
    green = int(ledsettings.get_backlight_color("Green")) * (ledsettings.backlight_brightness_percent) / 100
    blue = int(ledsettings.get_backlight_color("Blue")) * float(ledsettings.backlight_brightness_percent) / 100
    color = Color(int(green),int(red),int(blue))
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    if(update == True):
        strip.show()        

def colorWipe(strip, color, wait_ms=50):
    """Wipe color across display a pixel at a time."""
    for i in range(strip.numPixels()):
        if GPIO.input(KEY2) == 0:
            fastColorWipe(strip, True)
            return
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)
 
def theaterChase(strip, color, wait_ms=50, iterations=10):
    """Movie theater light style chaser animation."""
    for j in range(iterations):
        if GPIO.input(KEY2) == 0:
            fastColorWipe(strip, True)
            return
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, color)
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)
 
def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)
 
def rainbow(strip, wait_ms=20, iterations=1000):
    """Draw rainbow that fades across all pixels at once."""
    for j in range(256*iterations):
        if GPIO.input(KEY2) == 0:
            fastColorWipe(strip, True)
            return
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)
 
def rainbowCycle(strip, wait_ms=20, iterations=5000):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    for j in range(256*iterations):
        if GPIO.input(KEY2) == 0:
            fastColorWipe(strip, True)
            return
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)
 
def theaterChaseRainbow(strip, wait_ms=50):
    """Rainbow movie theater light style chaser animation."""
    for j in range(256):
        if GPIO.input(KEY2) == 0:
            fastColorWipe(strip, True)
            return
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, wheel((i+j) % 255))
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)

def breathing(strip, wait_ms=2, iterations = 1000):    
    multiplier = 2
    direction = 2
    for i in range(256*iterations):
        if GPIO.input(KEY2) == 0:
            fastColorWipe(strip, True)
            break
        if(multiplier >= 98 or multiplier < 2):
            direction *= -1
        multiplier += direction
        divide = multiplier / float(100)        
        red = int(round(float(ledsettings.get_color("Red")) * float(divide)))
        green = int(round(float(ledsettings.get_color("Green")) * float(divide)))
        blue = int(round(float(ledsettings.get_color("Blue")) * float(divide)))
      
        for i in range(strip.numPixels()):            
            strip.setPixelColor(i, Color(green, red, blue))
        strip.show()
        if(wait_ms > 0):
            time.sleep(wait_ms/1000.0) 
            
def get_rainbow_colors(pos, color):
    pos = int(pos)
    if pos < 85:
        if(color == "green"):
            return pos * 3
        elif(color == "red"):
            return 255 - pos * 3
        elif(color == "blue"):
            return 0        
    elif pos < 170:
        pos -= 85
        if(color == "green"):
            return 255 - pos * 3
        elif(color == "red"):
            return 0
        elif(color == "blue"):
            return pos * 3        
    else:
        pos -= 170
        if(color == "green"):
            return 0
        elif(color == "red"):
            return pos * 3
        elif(color == "blue"):
            return 255 - pos * 3        

class MenuLCD:    
    def __init__(self, xml_file_name):        
        self.LCD = LCD_1in44.LCD()
        self.Lcd_ScanDir = LCD_1in44.SCAN_DIR_DFT
        self.LCD.LCD_Init(self.Lcd_ScanDir)
        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), "GREEN")
        self.draw = ImageDraw.Draw(self.image)
        self.LCD.LCD_ShowImage(self.image,0,0)        
        self.xml_file_name = xml_file_name        
        self.DOMTree = minidom.parse(xml_file_name)
        self.currentlocation = "menu";        
        self.scroll_hold = 0
        self.cut_count = 0
        self.pointer_position = 0
        self.background_color = "BLACK"
        self.text_color = "WHITE"
        self.update_songs()
        self.update_ports()        
        self.speed_multiplier = 1
    
    def update_songs(self):
        songs_list = os.listdir("Songs")       
        self.DOMTree = minidom.parse(self.xml_file_name)
        for song in songs_list:            
            element = self.DOMTree.createElement("Choose_song")        
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , song)       
            mc = self.DOMTree.getElementsByTagName("Play_MIDI")[0]
            mc.appendChild(element)
            
                    
    def update_sequence_list(self):
        try:      
            sequences_tree = minidom.parse("sequences.xml")
            self.update_songs()
            i = 0
            while(True):
                try:                
                    i += 1                
                    sequence_name = sequences_tree.getElementsByTagName("sequence_"+str(i))[0].getElementsByTagName("sequence_name")[0].firstChild.nodeValue
                    element = self.DOMTree.createElement("Sequences")        
                    element.appendChild(self.DOMTree.createTextNode(""))
                    element.setAttribute("text"  , str(sequence_name))       
                    mc = self.DOMTree.getElementsByTagName("LED_Strip_Settings")[0]
                    mc.appendChild(element)
                    
                except:                             
                    break
        except:
            self.render_message("Something went wrong", "Check your sequences file", 1500)
            
    def update_ports(self):
        ports = mido.get_input_names()
        self.update_sequence_list()
        for port in ports:            
            element = self.DOMTree.createElement("Input")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , port)
            mc = self.DOMTree.getElementsByTagName("Ports_Settings")[0]
            mc.appendChild(element)
            element = self.DOMTree.createElement("Output")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , port)
            mc = self.DOMTree.getElementsByTagName("Ports_Settings")[1]
            mc.appendChild(element)
            element = self.DOMTree.createElement("Playback")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , port)
            mc = self.DOMTree.getElementsByTagName("Ports_Settings")[2]
            mc.appendChild(element)
            
    def update_multicolor(self, colors_list):        
        i = 0
        self.update_ports()
        rgb_names = []
        rgb_names = ["Red", "Green", "Blue"]
        #self.DOMTree = minidom.parse(self.xml_file_name)
        for color in colors_list:
            i = i + 1

            element = self.DOMTree.createElement("Multicolor")        
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , "Color"+str(i))     
            mc = self.DOMTree.getElementsByTagName("LED_Color")[0]
            mc.appendChild(element)
            
            element = self.DOMTree.createElement("Color"+str(i))        
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , "RGB Color"+str(i))     
            mc = self.DOMTree.getElementsByTagName("Multicolor")[0]
            mc.appendChild(element)         
            
            element = self.DOMTree.createElement("Color"+str(i))        
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , "Delete")     
            mc = self.DOMTree.getElementsByTagName("Multicolor")[0]
            mc.appendChild(element)
            
            for rgb_name in rgb_names:            
                element = self.DOMTree.createElement("RGB_Color"+str(i))        
                element.appendChild(self.DOMTree.createTextNode(""))
                element.setAttribute("text"  , rgb_name)     
                mc = self.DOMTree.getElementsByTagName("Color"+str(i))[0]
                mc.appendChild(element)    

        
 
    def show(self, position = "default", back_pointer_location = False):     
        if(position == "default" and  self.currentlocation):
            position = self.currentlocation
            refresh = 1
        elif(position == "default" and not self.currentlocation):
            position = "menu"
            refresh = 1
        else:
            position = position.replace(" ", "_")
            self.currentlocation = position;
            refresh = 0            
            
        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)        
        self.draw.text((2, 5), position.replace("_", " "), fill = self.text_color) 
        #getting list of items in current menu    
        staffs = self.DOMTree.getElementsByTagName(position)        
        text_margin_top = 15
        i = 0
        list_count = len(staffs)
        list_count -= 1    
        
        if(self.pointer_position > 9):
            self.menu_offset = self.pointer_position - 9
        else:
            self.menu_offset = -1;        
        
        #looping through menu list
        for staff in staffs:
            if(self.pointer_position > list_count):
                self.pointer_position = list_count
            elif(self.pointer_position < 0):
                self.pointer_position = 0
            #drawing little arrow to show there are more items above
            if(self.pointer_position > 9 and i < self.menu_offset):
                self.draw.line([(119,20),(125,20)], fill = self.text_color,width = 2)
                self.draw.line([(119,20),(122,17)], fill = self.text_color,width = 2)
                self.draw.line([(119,20),(122, 17)], fill = self.text_color,width = 2)
                i += 1                
                continue
                           
            sid = staff.getAttribute("text")   
            
            if(not back_pointer_location):
                if(i == self.pointer_position):
                    try:
                        self.parent_menu = staff.parentNode.tagName
                    except:
                        self.parent_menu = "end"             
                    self.draw.rectangle([(0,text_margin_top),(128,text_margin_top + 11)],fill = "Crimson")
                    self.draw.text((3, text_margin_top), ">", fill = self.text_color)
                    self.current_choice =  sid                   
            else:             
                if(sid == back_pointer_location):
                    try:
                        self.parent_menu = staff.parentNode.tagName
                    except:
                        self.parent_menu = "data"
                    self.draw.rectangle([(0,text_margin_top),(128,text_margin_top + 11)],fill = "Crimson")
                    self.draw.text((3, text_margin_top), ">", fill = self.text_color)
                    self.current_choice =  sid
                    self.pointer_position = i                    
            #drawing little arrow to show there are more items below
            if(i == 10 and self.pointer_position < list_count and list_count > 10):
                self.draw.line([(119,120),(125,120)], fill = self.text_color,width = 2)
                self.draw.line([(119,120),(122,123)], fill = self.text_color,width = 2)
                self.draw.line([(122,123),(125,120)], fill = self.text_color,width = 2)
                
            #scrolling text if too long
            if(self.pointer_position == i and len(sid) > 18):                
                tobecontinued = ".."
                if(refresh == 1):
                    try:
                        self.cut_count += 1                            
                    except:
                        self.cut_count = -6                        
                else:
                    cut = 0
                    self.cut_count = -6
                if(self.cut_count > (len(sid) - 16)):
                    #hold scrolling on end
                    if(self.scroll_hold < 8):
                        self.cut_count -= 1
                        self.scroll_hold += 1
                        tobecontinued = ""
                    else:                        
                        self.cut_count = -6
                        self.scroll_hold = 0
                    cut = self.cut_count
                if(self.cut_count >= 0):
                   cut = self.cut_count
                else:
                    cut = 0
            else:
                cut = 0
                tobecontinued = ""                
                        
            i += 1
            self.draw.text((10, text_margin_top), sid[cut:(18 + cut)]+tobecontinued, fill = self.text_color)
            text_margin_top += 10
            
        #displaying color example
        if(self.currentlocation == "RGB"):
            self.draw.text((10, 70), str(ledsettings.get_colors()), fill = self.text_color)
            self.draw.rectangle([(0,80),(128,128)],fill = "rgb("+str(ledsettings.get_colors())+")")
            
        if("RGB_Color" in self.currentlocation):            
            self.draw.text((10, 70), str(ledsettings.get_multicolors(self.currentlocation.replace('RGB_Color',''))), fill = self.text_color)
            self.draw.rectangle([(0,80),(128,128)],fill = "rgb("+str(ledsettings.get_multicolors(self.currentlocation.replace('RGB_Color','')))+")")
            
        if("Backlight_Color" in self.currentlocation):            
            self.draw.text((10, 70), str(ledsettings.get_backlight_colors()), fill = self.text_color)
            self.draw.rectangle([(0,80),(128,128)],fill = "rgb("+str(ledsettings.get_backlight_colors())+")")
        
        if("Multicolor" in self.currentlocation):
            try:
                self.draw.rectangle([(115,50),(128,80)],fill = "rgb("+str(ledsettings.get_multicolors(self.current_choice.replace('Color','')))+")")
            except:
                pass
            
        #displaying rainbow offset value
        if(self.current_choice == "Offset"):
            self.draw.text((10, 70), str(ledsettings.rainbow_offset), fill = self.text_color)
            
        if(self.current_choice == "Scale"):
            self.draw.text((10, 70), str(ledsettings.rainbow_scale)+"%", fill = self.text_color)
            
        if(self.current_choice == "Timeshift"):
            self.draw.text((10, 70), str(ledsettings.rainbow_timeshift), fill = self.text_color)        
        
        #displaying brightness value
        if(self.currentlocation == "Brightness"):
            self.draw.text((10, 35), str(ledstrip.brightness_percent)+"%", fill = self.text_color)            
            miliamps = int(ledstrip.LED_COUNT) * (60 / (100 / float(ledstrip.brightness_percent)))
            amps = round(float(miliamps) / float(1000),2)            
            self.draw.text((10, 50), "Amps needed to "+"\n"+"power "+str(ledstrip.LED_COUNT)+" LEDS with "+"\n"+"white color: "+str(amps), fill = self.text_color)
        
        if(self.currentlocation == "Backlight_Brightness"):
            self.draw.text((10, 35), str(ledsettings.backlight_brightness_percent)+"%", fill = self.text_color)       
            
        
        self.LCD.LCD_ShowImage(self.image,0,0)

    def change_pointer(self, direction):
        if(direction == 0):
            self.pointer_position -= 1
        elif(direction == 1):
            self.pointer_position += 1
        menu.cut_count = -6
        menu.show()
        
    def enter_menu(self): 
        position = self.current_choice.replace(" ", "_")
        if(not self.DOMTree.getElementsByTagName(position) ):
            menu.change_settings(self.current_choice, self.currentlocation)
        else:
            self.currentlocation = self.current_choice
            self.pointer_position = 0
            menu.cut_count = -6
            menu.show(self.current_choice)
        
    def go_back(self):            
        if(self.parent_menu != "data"):
            location_readable = self.currentlocation.replace("_", " ")
            menu.cut_count = -6
            menu.show(self.parent_menu, location_readable)
            
    def render_message(self, title, message, delay = 500):
        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((3, 55), title, fill = self.text_color)
        self.draw.text((3, 65), message, fill = self.text_color)
        self.LCD.LCD_ShowImage(self.image,0,0)
        LCD_Config.Driver_Delay_ms(delay)  
        
    def render_screensaver(self, hour, date, cpu, cpu_average, ram, temp, cpu_history = []):
        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)     
        fonthour = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSansBold.ttf', 31)
        font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSansBold.ttf', 13)
        self.draw.text((4, 5), hour, fill = self.text_color, font=fonthour)
        self.draw.text((34, 35), date, fill = self.text_color, font=font)
        
        previous_height = 0
        c = -5
        for cpu_chart in cpu_history:
            height = ((100 - cpu_chart) * 35) / float(100)            
            self.draw.line([(c,45+previous_height),(c+5,45+height)], fill = "Red",width = 1)            
            previous_height = height
            c += 5            
        
        self.draw.text((3, 80), "CPU: "+str(cpu)+"% ("+str(cpu_average)+"%)", fill = self.text_color, font=font)
        self.draw.text((3, 95), "RAM usage: "+str(ram)+"%", fill = self.text_color, font=font)
        self.draw.text((3, 110), "Temp: "+str(temp)+" C", fill = self.text_color, font=font)
        self.LCD.LCD_ShowImage(self.image,0,0)
            
    def change_settings(self, choice, location):
        if(location == "Text_Color"):
            self.text_color = choice
        if(location == "Background_Color"):
            self.background_color = choice
        if(self.text_color == self.background_color):
            self.text_color = "Red"
            
        if(location == "Choose_song"):
            play_midi(choice)            
        if(location == "Play_MIDI"):
            if(choice == "Save MIDI"):
                now = datetime.datetime.now()
                current_date = now.strftime("%Y-%m-%d %H:%M")
                menu.render_message("Recording stopped", "Saved as "+current_date, 2000)  
                saving.save(current_date)
                menu.update_songs()
            if(choice =="Start recording"):                
                menu.render_message("Recording started", "", 2000)             
                saving.start_recording()
            if(choice == "Cancel recording"):
                menu.render_message("Recording canceled", "", 2000) 
                saving.cancel_recording()
                
        if(location == "Solid"):
            ledsettings.change_color_name(wc.name_to_rgb(choice))
            ledsettings.color_mode = "Single"
            
        if(location == "Fading"):
            ledsettings.mode = "Fading"
            if(choice == "Fast"):
                ledsettings.fadingspeed = 40
            elif(choice == "Medium"):
                ledsettings.fadingspeed = 20
            elif(choice == "Slow"):
                ledsettings.fadingspeed = 10
            elif(choice == "Very slow"):
                ledsettings.fadingspeed = 2
        
        if(location == "Velocity"):
            ledsettings.mode = "Velocity"
            if(choice == "Fast"):
                ledsettings.fadingspeed = 10
            elif(choice == "Medium"):
                ledsettings.fadingspeed = 8
            elif(choice == "Slow"):
                ledsettings.fadingspeed = 6
            elif(choice == "Very slow"):
                ledsettings.fadingspeed = 3
                
        if(location == "Light_mode"):
            ledsettings.mode = "Normal"
            fastColorWipe(ledstrip.strip, True)
            
        if(location == "Input"):
            midiports.change_port("inport", choice)
        if(location == "Output"):
            midiports.change_port("outport", choice)
        if(location == "Playback"):
            midiports.change_port("playport", choice)
            
        if(location == "Ports_Settings"):
            if(choice == "Refresh ports"):
                menu.update_ports()
                menu.render_message("Refreshing ports", "", 1500)
        
            if(choice == "Reset Bluetooth service"):
                menu.render_message("Reseting BL service", "", 1000)
                os.system("sudo systemctl restart btmidi.service")        
            
        if(location == "LED_animations"):
            if(choice == "Theater Chase"):
                theaterChase(ledstrip.strip, Color(127, 127, 127))  # White theater chase
                theaterChase(ledstrip.strip, Color(127,   0,   0))  # Red theater chase
                theaterChase(ledstrip.strip, Color(  0,   0, 127))  # Blue theater chase
            if(choice == "Theater Chase Rainbow"):
                theaterChaseRainbow(ledstrip.strip)
            if(choice == "Color Wipe"):
                colorWipe(ledstrip.strip, Color(0, 0, 255))
            if(choice == "Clear"):
                colorWipe(ledstrip.strip, Color(0,0,0), 1)
        if(location == "Breathing"):
            if(choice == "Fast"):
                breathing(ledstrip.strip, 5)
            if(choice == "Medium"):
                breathing(ledstrip.strip, 10)
            if(choice == "Slow"):
                breathing(ledstrip.strip, 25)
        if(location == "Rainbow"):
            if(choice == "Fast"):
                rainbow(ledstrip.strip, 2)
            if(choice == "Medium"):
                rainbow(ledstrip.strip, 20)
            if(choice == "Slow"):
                rainbow(ledstrip.strip, 50)
        if(location == "Rainbow_Cycle"):
            if(choice == "Fast"):
                rainbowCycle(ledstrip.strip, 1)
            if(choice == "Medium"):
                rainbowCycle(ledstrip.strip, 20)
            if(choice == "Slow"):
                rainbowCycle(ledstrip.strip, 50)
                
        if(location == "Other_Settings"):
            if(choice == "System Info"):
                screensaver()
                
        if(location == "Rainbow_Colors"):
            ledsettings.color_mode = "Rainbow"
            
        if(choice == "Add Color"):                    
            ledsettings.addcolor()
            
        if(choice == "Delete"):            
            ledsettings.deletecolor(location.replace('Color',''))
            
        if(choice == "Confirm"):
            ledsettings.color_mode = "Multicolor"
            
        if(location == "Sequences"):
            if(choice == "Update"):
                refresh_result = menu.update_sequence_list()
                if(refresh_result == False):
                    menu.render_message("Something went wrong", "Make sure your sequence file is correct", 1500)                
            else:
                ledsettings.set_sequence(self.pointer_position, 0)    
                    
                            
    def change_value(self, value):
        if(value == "LEFT"):
            value = -1
        elif(value == "RIGHT"):
            value = 1
            
        if(self.currentlocation == "Brightness"):
            ledstrip.change_brightness(value*self.speed_multiplier)  
            
        if(self.currentlocation == "Backlight_Brightness"):
            if(self.current_choice == "Power"):
                ledsettings.change_backlight_brightness(value*self.speed_multiplier)                
        if(self.currentlocation == "Backlight_Color"):
            ledsettings.change_backlight_color(self.current_choice, value*self.speed_multiplier)
        
        if(self.currentlocation == "RGB"):
            ledsettings.change_color(self.current_choice, value*self.speed_multiplier)
            ledsettings.color_mode = "Single"
        
        if("RGB_Color" in self.currentlocation):
            ledsettings.change_multicolor(self.current_choice, self.currentlocation, value*self.speed_multiplier)
        
        if(self.current_choice == "Offset"):
            ledsettings.rainbow_offset = ledsettings.rainbow_offset + value * 5 *self.speed_multiplier
        if(self.current_choice == "Scale"):
            ledsettings.rainbow_scale = ledsettings.rainbow_scale + value * 5 *self.speed_multiplier
        if(self.current_choice == "Timeshift"):
            ledsettings.rainbow_timeshift = ledsettings.rainbow_timeshift + value *self.speed_multiplier
        menu.show()
        
    def speed_change(self):
        if(self.speed_multiplier == 10):
            self.speed_multiplier = 1
        elif(self.speed_multiplier == 1):
            self.speed_multiplier = 10
    
def play_midi(song_path):
    menu.render_message("Playing: ", song_path)
    try:
        mid = mido.MidiFile("Songs/"+song_path)        
        for msg in mid.play():            
            midiports.playport.send(msg)            
            if GPIO.input(KEY2) == 0:
                break
    except:
        menu.render_message("Can't play this file", "", 2000)
    
def find_between(s, start, end):
    try:
        return (s.split(start))[1].split(end)[0]
    except:
        return False

def shift(l, n):
    return l[n:] + l[:n]    

def screensaver():
    delay = 0.1
    interval  = 3 / float(delay)
    i = 0
    cpu_history = [None] * int(interval)
    cpu_chart = [0] * 28
    cpu_average = 0
    midiports.inport.poll()
    while True:
        if((time.time() - saving.start_time) > 3600  and delay < 0.5):            
            delay = 0.9
            interval  = 5 / float(delay)
            cpu_history = [None] * int(interval)
            cpu_average = 0
            i = 0
        hour = datetime.datetime.now().strftime("%H:%M:%S")
        date = datetime.datetime.now().strftime("%d-%m-%Y")
        cpu_usage = psutil.cpu_percent()
        cpu_history[i] = cpu_usage             
        cpu_chart.append(cpu_chart.pop(0))
        cpu_chart[27] = cpu_usage   
        
        if(i>=(int(interval) - 1)):
            i = 0
            try:
                cpu_average = sum(cpu_history) / (float(len(cpu_history) +1))
                last_cpu_average = cpu_average
            except:
                cpu_average = last_cpu_average
                     
        ram_usage = psutil.virtual_memory()[2]        
        temp = find_between(str(psutil.sensors_temperatures()["cpu-thermal"]), "current=", ",")
        temp = round(float(temp), 1)
        
        menu.render_screensaver(hour, date, cpu_usage, round(cpu_average,1), ram_usage, temp, cpu_chart)
        time.sleep(delay)
        i += 1
        if (midiports.inport.poll() != None):
            break
        if GPIO.input(KEY2) == 0:            
            break
        
class SaveMIDI:
    def __init__(self):
        self.isrecording = False
        self.start_time = time.time()
    def start_recording(self):
        self.mid = MidiFile()
        self.track = MidiTrack()
        self.mid.tracks.append(self.track)
        self.isrecording = True
        menu.render_message("Recording started", "", 1500)
        self.restart_time()
        
    def cancel_recording(self):
        self.isrecording = False
        menu.render_message("Recording canceled", "", 1500)
        
    def add_track(self, status, note, velocity, time):
        self.track.append(Message(status, note=int(note), velocity=int(velocity), time=int(time)))
        
    def add_control_change(self, status, channel, control, value, time):
            self.track.append(Message(status, channel=int(channel), control=int(control),  value=int(value), time=int(time)))
      
    def save(self, filename):
        self.isrecording = False
        self.mid.save('Songs/'+filename+'.mid')
        menu.render_message("File saved", filename+".mid", 1500)
        
    def restart_time(self):
        self.start_time = time.time()

class LedSettings:
    def __init__(self):
        self.red = 255
        self.green = 255
        self.blue = 255
        self.mode = "Normal"
        self.fadingspeed = 1
        self.color_mode = "Single"
        self.rainbow_offset = 0
        self.rainbow_scale = 100
        self.rainbow_timeshift = 0
        
        self.multicolor = []
        self.multicolor.append([255, 255, 255])
        self.multicolor.append([0, 0, 255])
        self.multicolor.append([0, 255, 0])
        
        menu.update_multicolor(self.multicolor)
        
        self.sequence_active = False        
        
        self.backlight_brightness = 0
        self.backlight_brightness_percent = 0
        
        self.backlight_red = 255
        self.backlight_green = 255
        self.backlight_blue = 255        
        
    def addcolor(self):  
        self.multicolor.append([0, 255, 0])
        menu.update_multicolor(self.multicolor)
        
    def deletecolor(self, key):
        del self.multicolor[int(key) - 1]
        menu.update_multicolor(self.multicolor)
        menu.go_back()
    
    def change_multicolor(self, choice, location, value):
        self.sequence_active = False
        location = location.replace('RGB_Color','')
        location = int(location) - 1
        if(choice == "Red"):
            choice = 0
        elif(choice == "Green"):
            choice = 1
        else:
            choice = 2        
        self.multicolor[int(location)][choice] += int(value)
        if(self.multicolor[int(location)][choice] < 0):
            self.multicolor[int(location)][choice] = 0
        elif(self.multicolor[int(location)][choice] > 255):
            self.multicolor[int(location)][choice] = 255
            
    def get_multicolors(self, number):
        number = int(number) - 1
        return str(self.multicolor[int(number)][0])+", "+str(self.multicolor[int(number)][1])+", "+str(self.multicolor[int(number)][2])
        
        
    def change_color(self, color, value):
        self.sequence_active = False
        self.color_mode = "Single"
        if(color == "Red"):
            if(self.red <= 255 and self.red >= 0):
                self.red += int(value)
                if(self.red < 0):
                    self.red = 0
                if(self.red > 255):
                    self.red = 255
        elif(color == "Green"):
            if(self.green <= 255 and self.green >= 0):
                self.green += int(value)
                if(self.green < 0):
                    self.green = 0
                if(self.green > 255):
                    self.green = 255
        elif(color == "Blue"):
            if(self.blue <= 255 and self.blue >= 0):
                self.blue += int(value)
                if(self.blue < 0):
                    self.blue = 0
                if(self.blue > 255):
                    self.blue = 255
    def change_color_name(self, color):
        self.sequence_active = False
        self.color_mode = "Single"      
        self.red = int(find_between(str(color), "red=", ","))
        self.green = int(find_between(str(color), "green=", ","))
        self.blue = int(find_between(str(color), "blue=", ")"))
    def get_color(self, color):
        if(color == "Red"):
            return self.red
        elif(color == "Green"):
            return self.green
        elif(color == "Blue"):
            return self.blue
    def get_colors(self):
        return str(self.red)+", "+str(self.green)+", "+str(self.blue)
        
    def get_backlight_color(self, color):
        if(color == "Red"):
            return self.backlight_red
        elif(color == "Green"):
            return self.backlight_green
        elif(color == "Blue"):
            return self.backlight_blue
    def get_backlight_colors(self):
        return str(self.backlight_red)+", "+str(self.backlight_green)+", "+str(self.backlight_blue)
        
    def set_sequence(self, sequence, step):
        try:
            if(step != 1):
                self.step_number = 1
                self.sequences_tree = minidom.parse("sequences.xml")
            
                self.sequence_number = str(sequence + 1)        
                
                self.next_step = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("next_step")[0].firstChild.nodeValue
                self.control_number = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("control_number")[0].firstChild.nodeValue
                self.count_steps = 1
                self.sequence_active = True
                while(True):                
                    try:
                        temp_step = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.count_steps))[0].getElementsByTagName("color")[0].firstChild.nodeValue
                        self.count_steps += 1
                    except:
                        self.count_steps -= 1
                        break
                
            else:
                #print("step_number: "+str(self.step_number)+" count steps: "+str(self.count_steps))
                self.step_number += 1
                if(self.step_number > self.count_steps):
                    self.step_number = 1

            self.color_mode = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("color")[0].firstChild.nodeValue
            self.mode = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("light_mode")[0].firstChild.nodeValue
            
            if(self.mode == "Velocity" or self.mode == "Fading"):
                self.fadingspeed = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("speed")[0].firstChild.nodeValue
                if(self.mode == "Fading"):            
                    if(self.fadingspeed == "Fast"):
                        self.fadingspeed = 125
                    elif(self.fadingspeed == "Medium"):
                        self.fadingspeed = 100
                    elif(self.fadingspeed == "Slow"):
                        ledsetselftings.fadingspeed = 50
                    elif(self.fadingspeed == "Very slow"):
                        self.fadingspeed = 10
            
                if(self.mode == "Velocity"):                
                    if(self.fadingspeed == "Fast"):
                        self.fadingspeed = 10
                    elif(self.fadingspeed == "Medium"):
                        self.fadingspeed = 8
                    elif(self.fadingspeed == "Slow"):
                        self.fadingspeed = 6
                    elif(self.fadingspeed == "Very slow"):
                        self.fadingspeed = 3
            if(self.color_mode == "RGB"):            
                self.color_mode = "Single"
                self.red = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Red")[0].firstChild.nodeValue)
                self.green = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Green")[0].firstChild.nodeValue)
                self.blue = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Blue")[0].firstChild.nodeValue)
                                        
            if(self.color_mode == "Rainbow"):
                self.rainbow_offset = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Offset")[0].firstChild.nodeValue)
                self.rainbow_scale = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Scale")[0].firstChild.nodeValue)
                self.rainbow_timeshift = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Timeshift")[0].firstChild.nodeValue)
            
            if(self.color_mode == "Multicolor"):
                self.multicolor = []
                multicolor_number = 1
                while(True):
                    try:
                        colors = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("color_"+str(multicolor_number))[0].firstChild.nodeValue
                        colors = colors.split(',')
                        red = colors[0].replace(" ", "")
                        green = colors[1].replace(" ", "")
                        blue = colors[2].replace(" ", "")
                        self.multicolor.append([int(red), int(green), int(blue)])                     
                        multicolor_number += 1
                    except:                    
                        break            
        except:                
            return False  
            
    def change_backlight_brightness(self, value):        
        self.backlight_brightness_percent += value
        if(self.backlight_brightness_percent < 0):
            self.backlight_brightness_percent = 0
        elif(self.backlight_brightness_percent > 100):
            self.backlight_brightness_percent = 100
        self.backlight_brightness = 255 * self.backlight_brightness_percent / 100     
        fastColorWipe(ledstrip.strip, True)
    def change_backlight_color(self, color, value):
        if(color == "Red"):
            if(self.backlight_red <= 255 and self.backlight_red >= 0):
                self.backlight_red += int(value)
                if(self.backlight_red < 0):
                    self.backlight_red = 0
                if(self.backlight_red > 255):
                    self.backlight_red = 255
        elif(color == "Green"):
            if(self.backlight_green <= 255 and self.backlight_green >= 0):
                self.backlight_green += int(value)
                if(self.backlight_green < 0):
                    self.backlight_green = 0
                if(self.backlight_green > 255):
                    self.backlight_green = 255
        elif(color == "Blue"):
            if(self.backlight_blue <= 255 and self.backlight_blue >= 0):
                self.backlight_blue += int(value)
                if(self.backlight_blue < 0):
                    self.backlight_blue = 0
                if(self.backlight_blue > 255):
                    self.backlight_blue = 255
        fastColorWipe(ledstrip.strip, True)

class MidiPorts():
    def __init__(self):
        ports = mido.get_input_names()
        try:
            for port in ports:
                if "Through" not in port and "RPi" not in port and "RtMidOut" not in port:
                    self.inport =  mido.open_input(port)
                    print("Inport set to "+port)
        except:
            print ("no input port")
        try:            
            for port in ports:
                if "Through" not in port and "RPi" not in port and "RtMidOut" not in port:
                    self.playport =  mido.open_output(port)
                    print("playport set to "+port)
        except:
            print("no playback port")
        try:
            for port in ports:
                if "RPi" in port:
                    self.outport =  mido.open_output(port)
                    print("outport set to "+port)
        except:
            print("no output port")
            
        self.portname = "inport"
            
    def change_port(self, port, portname):
        try:
            if(port == "inport"):                
                self.inport =  mido.open_input(portname)
            elif(port == "playport"):
                self.playport =  mido.open_output(portname)
            elif(port == "outport"):
                self.outport = mido.open_output(portname)
            menu.render_message("Changing "+port+" to:", portname, 1500)
        except:
            menu.render_message("Can't change "+port+" to:", portname, 1500)

midiports = MidiPorts()
ledstrip = LedStrip()
menu = MenuLCD("menu.xml")
menu.show()
saving = SaveMIDI()
ledsettings = LedSettings()

keylist = [0] * 176
keylist_status = [0] * 176
keylist_color = [0] * 176

z = 0
display_cycle = 0
colorWipe(ledstrip.strip, Color(0,0,0), 1)

last_activity = time.time()

last_control_change = 0
pedal_deadzone = 10
timeshift_start = time.time()
while True:    
    #screensaver
    if((time.time() - last_activity) > 600):
        screensaver()    
    try:
            elapsed_time = time.time() - saving.start_time
    except:
            elapsed_time = 0
    if(display_cycle >= 60):
        display_cycle = 0
        if(saving.isrecording == True):
            screen_hold_time = 12
        else:
            screen_hold_time = 3
        if(elapsed_time > screen_hold_time):
            menu.show()
            timeshift_start = time.time()     
    display_cycle += 1
    
    if GPIO.input(KEYUP) == 0:
        last_activity = time.time()
        menu.change_pointer(0)
        while GPIO.input(KEYUP) == 0:
            time.sleep(0.01)
    if GPIO.input(KEYDOWN) == 0:
        last_activity = time.time()
        menu.change_pointer(1)
        while GPIO.input(KEYDOWN) == 0:
            time.sleep(0.01)
    if GPIO.input(KEY1) == 0:
        last_activity = time.time()
        menu.enter_menu()
        while GPIO.input(KEY1) == 0:
            time.sleep(0.01)
    if GPIO.input(KEY2) == 0:
        last_activity = time.time()
        menu.go_back()
        while GPIO.input(KEY2) == 0:
            time.sleep(0.01)
    if GPIO.input(KEY3) == 0:
        last_activity = time.time()
        if(ledsettings.sequence_active == True):
            ledsettings.set_sequence(0, 1)
        while GPIO.input(KEY3) == 0:
            time.sleep(0.01)
    if GPIO.input(KEYLEFT) == 0:
        last_activity = time.time()
        menu.change_value("LEFT")
        time.sleep(0.02)
    if GPIO.input(KEYRIGHT) == 0:
        last_activity = time.time()
        menu.change_value("RIGHT")
        time.sleep(0.02)
    if GPIO.input(JPRESS) == 0:
        last_activity = time.time()
        menu.speed_change()
        while GPIO.input(JPRESS) == 0:
            time.sleep(0.01)
        
    #if(ledsettings.color_mode == "Single"):
    red = ledsettings.get_color("Red")
    green = ledsettings.get_color("Green")
    blue = ledsettings.get_color("Blue")
                
    timeshift = (time.time() - timeshift_start) * ledsettings.rainbow_timeshift
      
    if(ledsettings.mode == "Fading" or ledsettings.mode == "Velocity"):                
        n = 0
        for note in keylist:            
            if(ledsettings.color_mode == "Multicolor"):
                try:
                    red = keylist_color[n][0]
                    green = keylist_color[n][1]
                    blue = keylist_color[n][2]
                except:
                    pass
            
            if(ledsettings.color_mode == "Rainbow"):
                red = get_rainbow_colors(int((int(n) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale)/ 100)) & 255, "red")
                green = get_rainbow_colors(int((int(n) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale) / 100)) & 255, "green")
                blue = get_rainbow_colors(int((int(n) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale)/ 100)) & 255, "blue")  

            if(int(note) != 1001):                
                if(int(note) > 0):                    
                    fading = (note / float(100)) / 10
                    ledstrip.strip.setPixelColor((n), Color(int(int(green) * fading), int(int(red) * fading), int(int(blue) * fading)))
 
                    keylist[n] = keylist[n] - ledsettings.fadingspeed
                    if(keylist[n] <= 0):
                        red_fading = int(ledsettings.get_backlight_color("Red"))* float(ledsettings.backlight_brightness_percent) / 100
                        green_fading = int(ledsettings.get_backlight_color("Green")) * float(ledsettings.backlight_brightness_percent) / 100
                        blue_fading = int(ledsettings.get_backlight_color("Blue")) * float(ledsettings.backlight_brightness_percent) / 100
                        color = Color(int(green_fading),int(red_fading),int(blue_fading))                  
                        ledstrip.strip.setPixelColor((n), color)  
                else:                    
                    keylist[n] = 0                   
                    
            if(ledsettings.mode == "Velocity"):
                if(int(last_control_change) < pedal_deadzone):
                    if(int(keylist_status[n]) == 0):
                        red_fading = int(ledsettings.get_backlight_color("Red"))* float(ledsettings.backlight_brightness_percent) / 100
                        green_fading = int(ledsettings.get_backlight_color("Green")) * float(ledsettings.backlight_brightness_percent) / 100
                        blue_fading = int(ledsettings.get_backlight_color("Blue")) * float(ledsettings.backlight_brightness_percent) / 100
                        color = Color(int(green_fading),int(red_fading),int(blue_fading))                  
                        ledstrip.strip.setPixelColor((n), color) 
                        keylist[n] = 0                    
            n += 1        
    try:
        midipending = midiports.inport.iter_pending()
    except:
        continue
    #loop through incoming midi messages
    for msg in midipending: 
        last_activity = time.time()     
        note = find_between(str(msg), "note=", " ")
        original_note = note
        note = int(note)        
        if "note_off" in str(msg):
            velocity = 0
        else:
            velocity = find_between(str(msg), "velocity=", " ")
                        
        control_change = find_between(str(msg), "value=", " ")
        if(control_change != False):
            last_control_change = control_change
            
            if(ledsettings.sequence_active == True):
            
                control = find_between(str(msg), "control=", " ")
                value = find_between(str(msg), "value=", " ")            
                try:
                    if("+" in ledsettings.next_step):
                        if(int(value) > int(ledsettings.next_step) and control == ledsettings.control_number):
                            ledsettings.set_sequence(0, 1)                            
                    else:
                        if(int(value) < int(ledsettings.next_step) and control == ledsettings.control_number):
                            ledsettings.set_sequence(0, 1)                            
                except:
                    pass        

        #changing offset to adjust the distance between the LEDs to the key spacing
        if(note > 92):
            note_offset = 2
        elif(note > 55):
            note_offset = 1
        else:
            note_offset = 0
        elapsed_time = time.time() - saving.start_time
                
        if(ledsettings.color_mode == "Rainbow"):
            red = get_rainbow_colors(int((int(((note - 20)*2 - note_offset)) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale)/ 100)) & 255, "red")
            green = get_rainbow_colors(int((int(((note - 20)*2 - note_offset)) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale) / 100)) & 255, "green")
            blue = get_rainbow_colors(int((int(((note - 20)*2 - note_offset)) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale)/ 100)) & 255, "blue") 
        
        if(int(velocity) == 0 and int(note) > 0):
            keylist_status[(note - 20)*2 - note_offset] = 0
            if(ledsettings.mode == "Fading"):
                keylist[(note - 20)*2 - note_offset] = 1000
            elif(ledsettings.mode == "Velocity"):
                if(int(last_control_change) < pedal_deadzone):
                    keylist[(note - 20)*2 - note_offset] = 0
            else:
                if(ledsettings.backlight_brightness > 0):
                    red = int(ledsettings.get_backlight_color("Red"))* (ledsettings.backlight_brightness_percent) / 100
                    green = int(ledsettings.get_backlight_color("Green")) * (ledsettings.backlight_brightness_percent) / 100
                    blue = int(ledsettings.get_backlight_color("Blue")) * float(ledsettings.backlight_brightness_percent) / 100
                    color = Color(int(green),int(red),int(blue))
                    ledstrip.strip.setPixelColor(((note - 20)*2 - note_offset), color)    
                else:
                    ledstrip.strip.setPixelColor(((note - 20)*2 - note_offset), Color(0, 0, 0))            
            if(saving.isrecording == True):
                saving.add_track("note_off", original_note, velocity, elapsed_time*1000)
        elif(int(velocity) > 0 and int(note) > 0):
            
            if(ledsettings.color_mode == "Multicolor"):
                choosen_color = random.choice(ledsettings.multicolor)
                red = choosen_color[0]
                green = choosen_color[1]
                blue = choosen_color[2]
                keylist_color[(note - 20)*2 - note_offset] = [red, green, blue]
            
            keylist_status[(note - 20)*2 - note_offset] = 1
            if(ledsettings.mode == "Velocity"):
                brightness = (100 / (float(velocity) / 127 ) )/ 100                 
            else:
                brightness = 1
            if(ledsettings.mode == "Fading"):
                keylist[(note - 20)*2 - note_offset] = 1001
            if(ledsettings.mode == "Velocity"):
                keylist[(note - 20)*2 - note_offset] = 1000/float(brightness)
            if(find_between(str(msg), "channel=", " ") == "12"):
                ledstrip.strip.setPixelColor(((note - 20)*2 - note_offset), Color(255, 0, 0))
            elif(find_between(str(msg), "channel=", " ") == "11"):
                ledstrip.strip.setPixelColor(((note - 20)*2 - note_offset), Color(0, 0, 255))
            else:                        
                ledstrip.strip.setPixelColor(((note - 20)*2 - note_offset), Color(int(int(green)/float(brightness)), int(int(red)/float(brightness)), int(int(blue)/float(brightness))))
            if(saving.isrecording == True):
                saving.add_track("note_on", original_note, velocity, elapsed_time*1000)            
        else:
            control = find_between(str(msg), "control=", " ")
            value = find_between(str(msg), "value=", " ")
            if(saving.isrecording == True):
                saving.add_control_change("control_change", 0, control, value, elapsed_time*1000)
        saving.restart_time()
            
    ledstrip.strip.show()
