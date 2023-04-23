import ast
import threading
import time
import traceback

import mido
import subprocess
import re
import os

from lib.functions import clamp, fastColorWipe, changeAllLedsColor, find_between, get_note_position, get_key_color, touch_file
from lib.neopixel import Color

from mido import MetaMessage

import numpy as np
import pickle


def find_nearest(array, target):
    array = np.asarray(array)
    idx = (np.abs(array - target)).argmin()
    return idx

PRACTICE_MELODY = 0
PRACTICE_RHYTHM = 1
PRACTICE_LISTEN = 2
PRACTICE_ARCADE = 3
PRACTICE_PROGRESSIVE = 4

class LearnMIDI:
    def __init__(self, usersettings, ledsettings, midiports, ledstrip):
        self.usersettings = usersettings
        self.ledsettings = ledsettings
        self.midiports = midiports
        self.ledstrip = ledstrip

        self.loading = 0
        self.practice = int(usersettings.get_setting_value("practice"))
        self.hands = int(usersettings.get_setting_value("hands"))
        self.mute_hand = int(usersettings.get_setting_value("mute_hand"))
        self.start_point = float(usersettings.get_setting_value("start_point"))
        self.end_point = float(usersettings.get_setting_value("end_point"))
        self.set_tempo = int(usersettings.get_setting_value("set_tempo"))
        self.hand_colorR = int(usersettings.get_setting_value("hand_colorR"))
        self.hand_colorL = int(usersettings.get_setting_value("hand_colorL"))

        self.notes_time = []
        self.socket_send = []

        self.is_loop_active = int(usersettings.get_setting_value("is_loop_active"))

        self.loadingList = ['', 'Load..', 'Proces', 'Merge', 'Done', 'Error!']
        self.learningList = ['Start', 'Stop']
        self.practiceList = ['Melody', 'Rhythm', 'Listen', 'Arcade', 'Progressive']
        self.handsList = ['Both', 'Right', 'Left']
        self.mute_handList = ['Off', 'Right', 'Left']
        self.hand_colorList = ast.literal_eval(usersettings.get_setting_value("hand_colorList"))

        self.song_tempo = 500000
        self.song_tracks = []
        self.ticks_per_beat = 240
        self.is_loaded_midi = {}
        self.is_started_midi = False
        self.t = 0
        self.current_measure = -1
        self.total_wait_time = 0.0
        self.wrong_keys = 0
        self.learning_midi = False
        self.current_score = 0
        self.current_idx = 0

    def add_instance(self, menu):
        self.menu = menu

    def change_practice(self, value):
        self.practice += value
        self.practice = clamp(self.practice, 0, len(self.practiceList) - 1)
        self.usersettings.change_setting_value("practice", self.practice)

    def change_hands(self, value):
        self.hands += value
        self.hands = clamp(self.hands, 0, len(self.handsList) - 1)
        self.usersettings.change_setting_value("hands", self.hands)

    def change_mute_hand(self, value):
        self.mute_hand += value
        self.mute_hand = clamp(self.mute_hand, 0, len(self.mute_handList) - 1)
        self.usersettings.change_setting_value("mute_hand", self.mute_hand)

    def restart_learning(self):
        if self.is_started_midi:
            self.is_started_midi = False
            self.t.join()
            self.t = threading.Thread(target=self.learn_midi)
            self.t.start()

    def change_start_point(self, value):
        self.start_point += value
        self.start_point = clamp(self.start_point, 1, self.end_point - 2)
        self.usersettings.change_setting_value("start_point", self.start_point)
        self.restart_learning()

    def change_end_point(self, value):
        self.end_point += value
        self.end_point = clamp(self.end_point, self.start_point + 2, 300)
        self.usersettings.change_setting_value("end_point", self.end_point)
        self.restart_learning()

    def change_set_tempo(self, value):
        self.set_tempo += 5 * value
        self.set_tempo = clamp(self.set_tempo, 10, 200)
        self.usersettings.change_setting_value("set_tempo", self.set_tempo)

    def change_hand_color(self, value, hand):
        if hand == 'RIGHT':
            self.hand_colorR += value
            self.hand_colorR = clamp(self.hand_colorR, 0, len(self.hand_colorList) - 1)
            self.usersettings.change_setting_value("hand_colorR", self.hand_colorR)
        elif hand == 'LEFT':
            self.hand_colorL += value
            self.hand_colorL = clamp(self.hand_colorL, 0, len(self.hand_colorList) - 1)
            self.usersettings.change_setting_value("hand_colorL", self.hand_colorL)


    # Get midi song tempo
    def get_tempo(self, mid):
        for msg in mid:  # Search for tempo
            if msg.type == 'set_tempo':
                return msg.tempo
        return 500000  # If not found return default tempo

    def load_song_from_cache(self, song_path):
        # Load song from cache
        try:
            if os.path.isfile('Songs/cache/' + song_path + '.p'):
                print("Loading song from cache")
                with open('Songs/cache/' + song_path + '.p', 'rb') as handle:
                    cache = pickle.load(handle)
                    self.song_tempo = cache['song_tempo']
                    self.ticks_per_beat = cache['ticks_per_beat']
                    self.song_tracks = cache['song_tracks']
                    self.notes_time = cache['notes_time']
                    self.loading = 4
                    return True
            else:
                return False
        except Exception as e:
            print(e)


    def load_midi(self, song_path):
        while self.loading < 4 and self.loading > 0:
            time.sleep(1)
            
        touch_file(song_path)    

        if song_path in self.is_loaded_midi.keys():
            return

        self.is_loaded_midi.clear()
        self.is_loaded_midi[song_path] = True
        self.loading = 1  # 1 = Load..
        self.is_started_midi = False  # Stop current learning song
        self.t = threading.currentThread()

        # Load song from cache
        if self.load_song_from_cache(song_path):
            return
        print("Cache not found")

        try:
            # Load the midi file
            mid = mido.MidiFile('Songs/' + song_path)

            # Get tempo and Ticks per beat
            self.song_tempo = self.get_tempo(mid)
            self.ticks_per_beat = mid.ticks_per_beat

            # Assign Tracks to different channels before merging to know the message origin
            self.loading = 2  # 2 = Proces
            if len(mid.tracks) == 2:  # check if the midi file has only 2 Tracks
                offset = 1
            else:
                offset = 0
            for k in range(len(mid.tracks)):
                for msg in mid.tracks[k]:
                    if not msg.is_meta:
                        msg.channel = k + offset
                        if msg.type == 'note_off':
                            msg.velocity = 0

            # Merge tracks
            self.loading = 3  # 3 = Merge
            self.song_tracks = mido.merge_tracks(mid.tracks)
            time_passed = 0
            self.notes_time.clear()
            for msg in mid:
                if not msg.is_meta:
                    time_passed += msg.time
                self.notes_time.append(time_passed)

            fastColorWipe(self.ledstrip.strip, True, self.ledsettings)

            # Save to cache
            with open('Songs/cache/' + song_path + '.p', 'wb') as handle:
                cache = {'song_tempo': self.song_tempo, 'ticks_per_beat': self.ticks_per_beat,
                         'notes_time': self.notes_time, 'song_tracks': self.song_tracks,}
                pickle.dump(cache, handle, protocol=pickle.HIGHEST_PROTOCOL)

            self.loading = 4  # 4 = Done
        except Exception as e:
            print(e)
            self.loading = 5  # 5 = Error!
            self.is_loaded_midi.clear()

    def darken_color(self, red, green, blue, factor):
        new_red = int(max(0, red * (1 - factor)))
        new_green = int(max(0, green * (1 - factor)))
        new_blue = int(max(0, blue * (1 - factor)))
        return (new_red, new_green, new_blue)

    def show_notes_to_press(self,notes_to_press):
        for note in range(100):
            note_position = get_note_position(note, self.ledstrip, self.ledsettings)
            if note in notes_to_press:
                isWhite = get_key_color(note)
                brightness = 1
                red = 255
                green = 255
                blue = 255
                if notes_to_press[note] == 1:
                    red = int(self.hand_colorList[self.hand_colorR][0] * brightness)
                    green = int(self.hand_colorList[self.hand_colorR][1] * brightness)
                    blue = int(self.hand_colorList[self.hand_colorR][2] * brightness)
                if notes_to_press[note] == 2:
                    red = int(self.hand_colorList[self.hand_colorL][0] * brightness)
                    green = int(self.hand_colorList[self.hand_colorL][1] * brightness)
                    blue = int(self.hand_colorList[self.hand_colorL][2] * brightness)

                if isWhite:
                    red = clamp(int((red + 128)/2), 0, 255)
                    green = clamp(int((green + 128)/2), 0, 255)
                    blue = clamp(int((blue + 128)/2), 0, 255)
                else:
                    red = clamp(int(red / 6), 0, 255)
                    green = clamp(int(green / 6), 0, 255)
                    blue = clamp(int(blue / 6), 0, 255)

                self.ledstrip.strip.setPixelColor(note_position, Color(green,red,blue))
            else:
                self.ledstrip.strip.setPixelColor(note_position, Color(0, 0, 0))
        self.ledstrip.strip.show()

    def init_measure_data(self):
        # Find the first index whose time is equal or bigger than the start value
        self.measure_data = []
        time_signature = None
        measure_started_at = 0
        self.measure_data.append({'note_index':0, 'start':0, 'time_signature':None})
        for i in range(len(self.song_tracks)):
            msg = self.song_tracks[i]
            if isinstance(msg, MetaMessage) and msg.type == 'time_signature':
                time_signature = float(msg.numerator/msg.denominator)
                measure_length = 4 * time_signature
            if time_signature is not None:
                measure_delta = int((self.notes_time[i]-measure_started_at)/measure_length)
                while measure_delta > 0:
                    measure_delta -= 1
                    measure_started_at += measure_length
                    self.measure_data.append({'note_index':i, 'start':measure_started_at, 'time_signature':time_signature})

    def midi_note_to_notation(self, msg):
        if msg.type == 'note_on' or msg.type == 'note_off':
            # Calculate the octave and note number
            octave = (msg.note // 12) - 1
            note_num = msg.note % 12

            # Map the note number to a note letter and accidental
            notes = {0: 'C', 1: 'C#', 2: 'D', 3: 'Eb', 4: 'E', 5: 'F',
                     6: 'F#', 7: 'G', 8: 'G#', 9: 'A', 10: 'Bb', 11: 'B'}
                     
            if msg.type == 'note_on' and msg.velocity>0:                 
                on_off = "ON"
            else:
                on_off = "OFF"
            offset = ""
            if msg.time>0:
                offset = "+"+str(msg.time);

            # Construct the notation string
            return f"{notes[note_num]}{octave} {on_off}  {offset}"
        else:
            return str(msg)
    
    def wait_notes_to_press(self, start_score, notes_to_press, notes_to_show, ignore_first_delay):
        notes_pressed = []
        set_notes_to_press = set(notes_to_press)
        self.show_notes_to_press(notes_to_show)
        start_waiting = time.time()

        while not set_notes_to_press.issubset(notes_pressed) and self.is_started_midi:
            if self.practice == PRACTICE_ARCADE:
                elapsed_already = max(0,time.time()-start_waiting - 0.25)
                if ignore_first_delay:
                    elapsed_already = 0
                if elapsed_already > 1:
                    elapsed_already = 1
                self.current_score = start_score - (self.wrong_keys * 10 + self.total_wait_time + elapsed_already)
                if self.current_score <= 0:
                    # print("Score reached zero")
                    notes_to_press.clear()
                    notes_to_show.clear()        
                    self.total_wait_time = 10000
                    break
            
            for msg_in in self.midiports.inport.iter_pending():
                note = int(find_between(str(msg_in), "note=", " "))
                if "note_off" in str(msg_in):
                    velocity = 0
                else:
                    velocity = int(find_between(str(msg_in), "velocity=", " "))
                if velocity > 0:
                    if note not in notes_pressed:
                        notes_pressed.append(note)
                        note_position = get_note_position(note, self.ledstrip, self.ledsettings)
                        if note in set_notes_to_press:
                            set_notes_to_press.remove(note)
                            self.ledstrip.strip.setPixelColor(note_position, Color(32,0,0))
                        else:
                            self.wrong_keys += 1
                            self.ledstrip.strip.setPixelColor(note_position, Color(0,32,0))
                        self.ledstrip.strip.show()

                else:
                    try:
                        notes_pressed.remove(note)
                    except ValueError:
                        pass  # do nothing
       
        if self.practice == PRACTICE_ARCADE:
            if self.current_score <= 0:
                notes_to_press.clear()
                notes_to_show.clear()                
                return
            elapsed_already = max(0,time.time()-start_waiting - 0.25)
            if elapsed_already > 1:
                elapsed_already = 1
            if ignore_first_delay:
                elapsed_already = 0
            self.total_wait_time += elapsed_already
        # Turn off the pressed LEDs                           
        fastColorWipe(self.ledstrip.strip, True, self.ledsettings)  # ideally clear only pressed notes!
        notes_to_press.clear()
        notes_to_show.clear();
        
    def listen_measures(self, start, end):
        try:
            fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
            time_prev = time.time()

            end_idx = self.measure_data[end+1]['note_index']

            start_idx = self.measure_data[start]['note_index']

            self.current_idx = start_idx
            msg_index = start_idx
            
            for msg in self.song_tracks[start_idx:end_idx]:
                # Exit thread if learning is stopped
                if not self.is_started_midi:
                    break

                # Get time delay
                tDelay = mido.tick2second(msg.time, self.ticks_per_beat, self.song_tempo * 100 / self.set_tempo)
                
                # Realize time delay, consider also the time lost during computation
                delay = max(0, tDelay - (
                        time.time() - time_prev) - 0.003)  # 0.003 sec calibratable to acount for extra time loss
                time.sleep(delay)
                time_prev = time.time()

                # Light-up LEDs with the notes to press
                if not msg.is_meta:
                    # Calculate note position on the strip and display
                    if msg.type == 'note_on' or msg.type == 'note_off':
                        note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                        isBlack = get_key_color(msg.note)
                        brightness = msg.velocity / 127
                        if msg.channel == 1:
                            red = int(self.hand_colorList[self.hand_colorR][0] * brightness)
                            green = int(self.hand_colorList[self.hand_colorR][1] * brightness)
                            blue = int(self.hand_colorList[self.hand_colorR][2] * brightness)
                        if msg.channel == 2:
                            red = int(self.hand_colorList[self.hand_colorL][0] * brightness)
                            green = int(self.hand_colorList[self.hand_colorL][1] * brightness)
                            blue = int(self.hand_colorList[self.hand_colorL][2] * brightness)

                        self.ledstrip.strip.setPixelColor(note_position, Color(green, red, blue))
                        self.ledstrip.strip.show()
                    # Play selected Track
                    self.midiports.playport.send(msg)
                msg_index += 1 
            time.sleep(0.5)
            for i in range(end_idx, min(len(self.song_tracks)-1,end_idx+40)):
                msg = self.song_tracks[i]
                if (msg.type == 'note_off' or 
                       (msg.type == 'note_on' and msg.velocity==0) ):
                    self.midiports.playport.send(msg)
        except Exception as e:
            print(e);
            traceback.print_exc()
            self.is_started_midi = False
    
    def learn_midi(self):
        loops_count = 0
        # Preliminary checks
        if self.is_started_midi:
            return
        if self.loading == 0:
            self.menu.render_message("Load song to start", "", 1500)
            return
        elif self.loading > 0 and self.loading < 4:
            self.is_started_midi = True  # Prevent restarting the Thread
            while self.loading > 0 and self.loading < 4:
                time.sleep(0.1)
        if self.loading == 4:
            self.is_started_midi = True  # Prevent restarting the Thread
        elif self.loading == 5:
            self.is_started_midi = False  # Allow restarting the Thread
            return

        self.t = threading.currentThread()
        self.init_measure_data()
        keep_looping = True


        while(keep_looping):
            changeAllLedsColor(self.ledstrip.strip, 32, 32, 32)
            time.sleep(1)
            try:
                fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
                time_prev = time.time()
                notes_to_press = []
                notes_to_show = {}

                start_idx = int(self.start_point-1)
                start_idx = clamp(start_idx, 0, len(self.measure_data)-1)

                end_idx = int(self.end_point)
                end_idx = clamp(end_idx, start_idx, len(self.measure_data)-1)
                end_idx = self.measure_data[end_idx]['note_index']

                self.current_measure = start_idx - 1
                start_idx = self.measure_data[start_idx]['note_index']

                self.current_idx = start_idx
                msg_index = start_idx
                
                accDelay = 0
                first_note = True
                
                self.total_wait_time = 0.0
                self.wrong_keys = 0
                self.learning_midi = True
                start_score = 100
                self.current_score = start_score                
                ignore_first_delay = True
                
                # Flush pending notes
                for msg_in in self.midiports.inport.iter_pending():
                    note = int(find_between(str(msg_in), "note=", " "))

                for msg in self.song_tracks[start_idx:end_idx]:
                    # Exit thread if learning is stopped
                    if not self.is_started_midi:
                        break

                    # Get time delay
                    tDelay = mido.tick2second(msg.time, self.ticks_per_beat, self.song_tempo * 100 / self.set_tempo)
                    
                    if first_note and msg.type == 'note_on' and msg.velocity>0:
                        first_note = False
                        
                    if not first_note:
                        accDelay += tDelay

                    while (self.current_measure+1 < len(self.measure_data) and
                        self.measure_data[self.current_measure+1]['note_index']<=msg_index):
                            self.current_measure += 1
                            print(str(self.measure_data[self.current_measure]))
                            print("--------------   Measure "+str(self.current_measure))
                            if self.practice == PRACTICE_PROGRESSIVE:
                                self.wait_notes_to_press(start_score, notes_to_press, notes_to_show, ignore_first_delay)
                                self.listen_measures(self.current_measure,self.current_measure)
                                ignore_first_delay = True
                                accDelay = 0
                            
                    position_within_measure = int(100*(self.notes_time[msg_index] - self.measure_data[self.current_measure]['start']))
                    print("      note : "+str(msg_index)+"@"+format(self.notes_time[msg_index],'.2f')+"   "+
                        str(tDelay)+"  " +str(position_within_measure)+"  "+self.midi_note_to_notation(msg))
                        
                    if self.practice == PRACTICE_ARCADE:
                        self.current_score = start_score - (self.wrong_keys * 10 + self.total_wait_time)                   
                        if self.current_score<0:
                            print("Score reached zero")
                            break

                    # Check notes to press
                    if not msg.is_meta:
                        try:
                            self.socket_send.append(self.notes_time[msg_index])
                        except Exception as e:
                            print(e)
                        self.current_idx += 1

                        if (accDelay > 0.1 and (msg.type == 'note_on' or msg.type == 'note_off') 
                              and notes_to_press and 
                              self.practice in (PRACTICE_MELODY, PRACTICE_ARCADE, PRACTICE_PROGRESSIVE)):
                            self.wait_notes_to_press(start_score, notes_to_press, notes_to_show, ignore_first_delay)
                            ignore_first_delay = False
                            accDelay = 0

                    # Realize time delay, consider also the time lost during computation
                    delay = max(0, tDelay - (
                            time.time() - time_prev) - 0.003)  # 0.003 sec calibratable to acount for extra time loss
                    time.sleep(delay)
                    time_prev = time.time()

                    # Light-up LEDs with the notes to press
                    if not msg.is_meta:
                        # Calculate note position on the strip and display
                        if msg.type == 'note_on' or msg.type == 'note_off':
                            note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                            isBlack = get_key_color(msg.note)
                            brightness = msg.velocity / 127
                            if msg.channel == 1:
                                red = int(self.hand_colorList[self.hand_colorR][0] * brightness)
                                green = int(self.hand_colorList[self.hand_colorR][1] * brightness)
                                blue = int(self.hand_colorList[self.hand_colorR][2] * brightness)
                            if msg.channel == 2:
                                red = int(self.hand_colorList[self.hand_colorL][0] * brightness)
                                green = int(self.hand_colorList[self.hand_colorL][1] * brightness)
                                blue = int(self.hand_colorList[self.hand_colorL][2] * brightness)

                            self.ledstrip.strip.setPixelColor(note_position, Color(green, red, blue))
                            self.ledstrip.strip.show()

                        # Save notes to press
                        if msg.type == 'note_on' and msg.velocity > 0 and (
                                msg.channel == self.hands or self.hands == 0):
                            notes_to_press.append(msg.note)
                            notes_to_show[msg.note] = msg.channel

                        # Play selected Track
                        if ((
                                self.hands == 1 and self.mute_hand != 2 and msg.channel == 2) or
                                # send midi sound for Left hand
                                (
                                        self.hands == 2 and self.mute_hand != 1 and msg.channel == 1) or
                                # send midi sound for Right hand
                                self.practice == PRACTICE_LISTEN):  # send midi sound for Listen only
                            self.midiports.playport.send(msg)
                    msg_index += 1 
                if self.practice in (PRACTICE_MELODY, PRACTICE_ARCADE, PRACTICE_PROGRESSIVE):
                    self.wait_notes_to_press(start_score, notes_to_press, notes_to_show, ignore_first_delay)
            except Exception as e:
                print(e);
                traceback.print_exc()
                self.is_started_midi = False
            if self.is_started_midi:
                if self.practice == PRACTICE_ARCADE and self.current_score < 0:
                    changeAllLedsColor(self.ledstrip.strip, 0, 16, 0)
                else:
                    changeAllLedsColor(self.ledstrip.strip, 16, 0, 0)
                time.sleep(3)
            fastColorWipe(self.ledstrip.strip, True, self.ledsettings)  # ideally clear only pressed notes!
            self.learning_midi = False
            if(not self.is_loop_active or self.is_started_midi == False):
                keep_looping = False


    def convert_midi_to_abc(self, midi_file):
        if not os.path.isfile('Songs/' + midi_file.replace(".mid", ".abc")):
            #subprocess.call(['midi2abc',  'Songs/' + midi_file, '-o', 'Songs/' + midi_file.replace(".mid", ".abc")])
            try:
                subprocess.check_output(['midi2abc',  'Songs/' + midi_file, '-o', 'Songs/' + midi_file.replace(".mid", ".abc")])
            except Exception as e:
                #check if e contains the string 'No such file or directory'
                if 'No such file or directory' in str(e):
                    print("Midiabc not found, installing...")
                    self.install_midi2abc()
                    self.convert_midi_to_abc(midi_file)
        else:
            print("file already converted")

    def install_midi2abc(self):
        print("Installing abcmidi")
        subprocess.call(['sudo', 'apt-get', 'install', 'abcmidi', '-y'])


