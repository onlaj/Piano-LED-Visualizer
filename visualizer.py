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

import mido
from mido import MidiFile, Message, tempo2bpm, MidiTrack,MetaMessage

from neopixel import *
import argparse

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

KEYRIGHT = 26
KEYLEFT = 5
KEYUP = 6
KEYDOWN = 19
KEY1 = 21
KEY2 = 20
# pin numbers are interpreted as BCM pin numbers.
GPIO.setmode(GPIO.BCM)
# Sets the pin as input and sets Pull-up mode for the pin.
GPIO.setup(KEYRIGHT,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEYLEFT,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEYUP,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEYDOWN,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEY1,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEY2,GPIO.IN,GPIO.PUD_UP)

#LED animations
def colorWipe(strip, color, wait_ms=50):
    """Wipe color across display a pixel at a time."""
    for i in range(strip.numPixels()):
        if GPIO.input(KEY2) == 0:
            break
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)
 
def theaterChase(strip, color, wait_ms=50, iterations=10):
    """Movie theater light style chaser animation."""
    for j in range(iterations):
        if GPIO.input(KEY2) == 0:
            break
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
            break
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)
 
def rainbowCycle(strip, wait_ms=20, iterations=5000):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    for j in range(256*iterations):
        if GPIO.input(KEY2) == 0:
            break
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)
 
def theaterChaseRainbow(strip, wait_ms=50):
    """Rainbow movie theater light style chaser animation."""
    for j in range(256):
        if GPIO.input(KEY2) == 0:
            break
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
    
    def update_songs(self):
        songs_list = os.listdir("Songs")       
        self.DOMTree = minidom.parse(self.xml_file_name)
        for song in songs_list:            
            element = self.DOMTree.createElement("Choose_song")        
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , song)       
            mc = self.DOMTree.getElementsByTagName("Play_MIDI")[0]
            mc.appendChild(element)
            
    def update_ports(self):
        ports = mido.get_input_names()
        self.update_songs()
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
            
        if(location == "Fading"):
            ledsettings.mode = "Fading"
            if(choice == "Fast"):
                ledsettings.fadingspeed = 125
            elif(choice == "Medium"):
                ledsettings.fadingspeed = 100
            elif(choice == "Slow"):
                ledsettings.fadingspeed = 50
            elif(choice == "Very slow"):
                ledsettings.fadingspeed = 10
        
        if(location == "Velocity"):
            ledsettings.mode = "Velocity"
            if(choice == "Fast"):
                ledsettings.fadingspeed = 5
            elif(choice == "Medium"):
                ledsettings.fadingspeed = 4
            elif(choice == "Slow"):
                ledsettings.fadingspeed = 3
            elif(choice == "Very slow"):
                ledsettings.fadingspeed = 2
                
        if(location == "Light_mode"):
            ledsettings.mode = "Normal"
            
        if(location == "Input"):
            midiports.change_port("inport", choice)
        if(location == "Output"):
            midiports.change_port("outport", choice)
        if(location == "Playback"):
            midiports.change_port("playport", choice)
            
        if(location == "Ports_Settings"):
            menu.update_ports()
            menu.render_message("Refreshing ports", "", 1500)
        
        if(location == "Reset_Bluetooth_service"):
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
                            
    def change_value(self, value):
        if(value == "LEFT"):
            value = -1
        elif(value == "RIGHT"):
            value = 1
        if(self.currentlocation == "RGB"):
            ledsettings.change_color(self.current_choice, value)              
    
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
        if GPIO.input(KEY2) == 0:
            midiports.inport.callback = None
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
    def change_color(self, color, value):
        if(color == "Red"):
            if(self.red <= 255 and self.red >= 0):
                self.red += int(value)*10
                if(self.red < 0):
                    self.red = 0
                if(self.red > 255):
                    self.red = 255
        elif(color == "Green"):
            if(self.green <= 255 and self.green >= 0):
                self.green += int(value)*10
                if(self.green < 0):
                    self.green = 0
                if(self.green > 255):
                    self.green = 255
        elif(color == "Blue"):
            if(self.blue <= 255 and self.blue >= 0):
                self.blue += int(value)*10
                if(self.blue < 0):
                    self.blue = 0
                if(self.blue > 255):
                    self.blue = 255
    def change_color_name(self, color):       
        self.red = find_between(str(color), "red=", ",")
        self.green = find_between(str(color), "green=", ",")
        self.blue = find_between(str(color), "blue=", ")")
    def get_color(self, color):
        if(color == "Red"):
            return self.red
        elif(color == "Green"):
            return self.green
        elif(color == "Blue"):
            return self.blue
    def get_colors(self):
        return str(self.red)+", "+str(self.green)+", "+str(self.blue)

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

z = 0
display_cycle = 0
colorWipe(ledstrip.strip, Color(0,0,0), 1)

last_activity = time.time()

last_control_change = 0
pedal_deadzone = 10
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
        if(elapsed_time > 3):
            menu.show()        
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
    if GPIO.input(KEYLEFT) == 0:
        last_activity = time.time()
        menu.change_value("LEFT")
        while GPIO.input(KEYLEFT) == 0:
            time.sleep(0.01)
    if GPIO.input(KEYRIGHT) == 0:
        last_activity = time.time()
        menu.change_value("RIGHT")
        while GPIO.input(KEYRIGHT) == 0:
            time.sleep(0.01)
    
    red = ledsettings.get_color("Red")
    green = ledsettings.get_color("Green")
    blue = ledsettings.get_color("Blue")    
      
    if(ledsettings.mode == "Fading" or ledsettings.mode == "Velocity"):
        n = 0
        for note in keylist:            
            if(int(note) != 1001):                
                if(int(note) >= 0):
                    fading = (note / float(100)) / 10
                    ledstrip.strip.setPixelColor((n), Color(int(int(green) * fading), int(int(red) * fading), int(int(blue) * fading)))
                    if(int(note) == 0):
                        ledstrip.strip.setPixelColor((0), Color(0, 0, 0))
                    keylist[n] = keylist[n] - ledsettings.fadingspeed
                else:
                    keylist[n] = 0
            if(ledsettings.mode == "Velocity"):
                if(int(last_control_change) < pedal_deadzone):
                    if(int(keylist_status[n]) == 0):
                        ledstrip.strip.setPixelColor((n), Color(0, 0, 0))
                        keylist[n] = 0                    
            n += 1
        #ledstrip.strip.show()  
    
    midipending = midiports.inport.iter_pending()
    #loop through incoming midi messages
    for msg in midipending:       
        last_activity = time.time()     
        note = find_between(str(msg), "note=", " ")
        original_note = note
        note = int(note)
        velocity = find_between(str(msg), "velocity=", " ")
        control_change = find_between(str(msg), "value=", " ")
        if(control_change != False):
            last_control_change = control_change

        #changing offset to adjust the distance between the LEDs to the key spacing
        if(note > 92):
            note_offset = 2
        elif(note > 55):
            note_offset = 1
        else:
            note_offset = 0
        if(int(velocity) == 0 and int(note) > 0):
            keylist_status[(note - 20)*2 - note_offset] = 0
            if(ledsettings.mode == "Fading"):
                keylist[(note - 20)*2 - note_offset] = 1000
            elif(ledsettings.mode == "Velocity"):
                if(int(last_control_change) < pedal_deadzone):
                    keylist[(note - 20)*2 - note_offset] = 0
            else:
                ledstrip.strip.setPixelColor(((note - 20)*2 - note_offset), Color(0, 0, 0))            
            elapsed_time = time.time() - saving.start_time
            if(saving.isrecording == True):
                saving.add_track("note_off", original_note, velocity, elapsed_time*1000)
            saving.restart_time()
        elif(int(velocity) > 0 and int(note) > 0):
            keylist_status[(note - 20)*2 - note_offset] = 1
            if(ledsettings.mode == "Velocity"):
                brightness = (100 / (float(velocity) / 127 ) )/ 100 
                brightness = brightness
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
            elapsed_time = time.time() - saving.start_time
            if(saving.isrecording == True):
                saving.add_track("note_on", original_note, velocity, elapsed_time*1000)            
            saving.restart_time()
        else:
            control = find_between(str(msg), "control=", " ")
            value = find_between(str(msg), "value=", " ")
            elapsed_time = time.time() - saving.start_time
            if(saving.isrecording == True):
                saving.add_control_change("control_change", 0, control, value, elapsed_time*1000)
            saving.restart_time()
            
    ledstrip.strip.show()
