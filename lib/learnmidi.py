import ast
import threading
import time

import mido
import subprocess

import os

from lib.functions import clamp, fastColorWipe, find_between, get_note_position
from neopixel import Color

import numpy as np
import pickle


def find_nearest(array, target):
    array = np.asarray(array)
    idx = (np.abs(array - target)).argmin()
    return idx


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
        self.practiceList = ['Melody', 'Rhythm', 'Listen']
        self.handsList = ['Both', 'Right', 'Left']
        self.mute_handList = ['Off', 'Right', 'Left']
        self.hand_colorList = ast.literal_eval(usersettings.get_setting_value("hand_colorList"))

        self.song_tempo = 500000
        self.song_tracks = []
        self.ticks_per_beat = 240
        self.is_loaded_midi = {}
        self.is_started_midi = False
        self.t = 0

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
        self.start_point += 5 * value
        self.start_point = clamp(self.start_point, 0, self.end_point - 10)
        self.usersettings.change_setting_value("start_point", self.start_point)
        self.restart_learning()

    def change_end_point(self, value):
        self.end_point += 5 * value
        self.end_point = clamp(self.end_point, self.start_point + 10, 100)
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

        keep_looping = True
        while(keep_looping):
            time.sleep(1)
            try:
                fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
                time_prev = time.time()
                notes_to_press = []

                start_idx = int(self.start_point * len(self.song_tracks) / 100)
                end_idx = int(self.end_point * len(self.song_tracks) / 100)

                self.current_idx = start_idx

                for msg in self.song_tracks[start_idx:end_idx]:
                    # Exit thread if learning is stopped
                    self.socket_send.append(self.notes_time[self.current_idx])
                    if not self.is_started_midi:
                        break

                    # Get time delay
                    tDelay = mido.tick2second(msg.time, self.ticks_per_beat, self.song_tempo * 100 / self.set_tempo)

                    # Check notes to press
                    if not msg.is_meta:
                        if tDelay > 0 and (
                                msg.type == 'note_on' or msg.type == 'note_off') and notes_to_press and self.practice == 0:
                            notes_pressed = []
                            while not set(notes_to_press).issubset(notes_pressed) and self.is_started_midi:
                                for msg_in in self.midiports.inport.iter_pending():
                                    note = int(find_between(str(msg_in), "note=", " "))
                                    if "note_off" in str(msg_in):
                                        velocity = 0
                                    else:
                                        velocity = int(find_between(str(msg_in), "velocity=", " "))
                                    if velocity > 0:
                                        if note not in notes_pressed:
                                            notes_pressed.append(note)
                                    else:
                                        try:
                                            notes_pressed.remove(note)
                                        except ValueError:
                                            pass  # do nothing

                            # Turn off the pressed LEDs
                            fastColorWipe(self.ledstrip.strip, True, self.ledsettings)  # ideally clear only pressed notes!
                            notes_to_press.clear()

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

                        # Play selected Track
                        if ((
                                self.hands == 1 and self.mute_hand != 2 and msg.channel == 2) or
                                # send midi sound for Left hand
                                (
                                        self.hands == 2 and self.mute_hand != 1 and msg.channel == 1) or
                                # send midi sound for Right hand
                                self.practice == 2):  # send midi sound for Listen only
                            self.midiports.playport.send(msg)

                    self.current_idx += 1
            except Exception as e:
                self.is_started_midi = False

            if(not self.is_loop_active or self.is_started_midi == False):
                keep_looping = False

    def convert_midi_to_abc(self, midi_file):
        if not os.path.isfile('Songs/' + midi_file.replace(".mid", ".abc")):
            subprocess.call(['midi2abc',  'Songs/' + midi_file, '-o', 'Songs/' + midi_file.replace(".mid", ".abc")])
        else:
            print("file already converted")

    def install_midi2abc(self):
        print("Installing abcmidi")
        subprocess.call(['sudo', 'apt-get', 'install', 'abcmidi'])

