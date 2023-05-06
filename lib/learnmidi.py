import ast
import threading
import time
import traceback

import mido
import subprocess
import re
import os

DEBUG = True
DEBUG_MARKERS = False

if DEBUG:
    import ipdb


from lib.functions import clamp, fastColorWipe, changeAllLedsColor, setLedPattern, find_between, get_note_position, get_key_color, touch_file, read_only_fs
from lib.neopixel import getRGB, Color

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
PRACTICE_PERFECTION = 5

# notes within this distance are considered part of same chord
THRESHOLD_CHORD_NOTE_DISTANCE = 0.05

LOWEST_LED_BRIGHT = 5
MIDDLE_LED_BRIGHT = 32
MAX_LED_BRIGHT = 255

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
        self.start_point = int(usersettings.get_setting_value("start_point"))
        self.end_point = int(usersettings.get_setting_value("end_point"))
        self.set_tempo = int(usersettings.get_setting_value("set_tempo"))
        self.hand_colorR = int(usersettings.get_setting_value("hand_colorR"))
        self.hand_colorL = int(usersettings.get_setting_value("hand_colorL"))
        self.learn_step = int(usersettings.get_setting_value("learn_step"))

        self.notes_time = []
        self.socket_send = []

        self.is_loop_active = int(usersettings.get_setting_value("is_loop_active"))

        self.loadingList = ['', 'Load..', 'Proces', 'Merge', 'Done', 'Error!']
        self.learningList = ['Start', 'Stop']
        self.practiceList = ['Melody', 'Rhythm', 'Listen', 'Arcade', 'Progressive', 'Perfection']
        self.learnStepList = ['1/2', '1/3', '2/1', '2/2', '2/3', '2/4', '3/1', '3/2', '3/3', '3/4']
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
        self.blind_mode = False
        self.is_read_only_fs = read_only_fs()
        if self.is_read_only_fs:
            print("Read only FS");

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

    def change_learn_step(self, value):
        self.learn_step += value
        self.learn_step = clamp(self.learn_step, 1, len(self.learnStepList) - 1)
        self.usersettings.change_setting_value("learn_step", self.learn_step)
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
        # return False
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
                    self.measure_data = cache['measure_data']
                    self.gaps_array = cache['gaps']
                    self.loading = 4
                    return True
            else:
                return False
        except Exception as e:
            print(e)

    def init_measure_data(self, midi_messages):
        measure_data = []
        time_signature = None
        current_ticks = 0
        current_ticks_in_measure = 0
        
        tweak_measure_offset = 0
        measure_start = 0

        # 1. Calculate in which tick measures start taking MeasureOffset tweak into account        
        for i, msg in enumerate(midi_messages):
            if hasattr(msg,"time"):
                current_ticks += msg.time
                current_ticks_in_measure += msg.time
                
            if msg.is_meta and msg.type == "text" and msg.text.startswith("MeasureOffset="):
                tweak_measure_offset = int(msg.text[len("MeasureOffset="):])

            if msg.is_meta and msg.type == 'time_signature':
                time_signature = float(msg.numerator/msg.denominator)
                measure_length = int(4 * time_signature * self.ticks_per_beat)
                measure_data.append({'start':current_ticks + tweak_measure_offset })
                current_ticks_in_measure = 0
                measure_start = current_ticks
                
            if time_signature is not None:                
                while current_ticks_in_measure > measure_length:
                    current_ticks_in_measure -= measure_length
                    measure_start += measure_length
                    measure_data.append({'start':measure_start + tweak_measure_offset })
                        
        # 2. Calculate in which note measures start. Snap to measure is taken into account here
        tweak_snap_to_measure = 5
        measure_pointer = 1
        current_ticks = 0
        measure_data[0]['note_index'] = 0
        
        for i, msg in enumerate(midi_messages):
            if hasattr(msg,"time"):
                current_ticks += msg.time
            if msg.is_meta and msg.type == "text" and msg.text.startswith("SnapToMeasure="):
                tweak_snap_to_measure = int(msg.text[len("SnapToMeasure="):])
                
            if msg.type == "note_on" and msg.velocity>0:   # snap
                while (measure_pointer < len(measure_data) 
                           and current_ticks >= measure_data[measure_pointer]["start"] - tweak_snap_to_measure):
                    measure_data[measure_pointer]['note_index'] = i
                    measure_pointer += 1
        
        return measure_data

    def load_midi(self, song_path):
        while self.loading < 4 and self.loading > 0:
            time.sleep(1)

        if not self.is_read_only_fs:
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
            self.loading = 2  # 2 = Process
            if len(mid.tracks) == 2:  # check if the midi file has only 2 Tracks
                offset = 1
            else:
                offset = 0

            for k in range(len(mid.tracks)):
                for msg in mid.tracks[k]:
                    if not msg.is_meta:
                        if len(mid.tracks) == 2:
                           msg.channel = k
                        else:
                            if msg.channel in (0,1,2,3,4,5):
                               msg.channel = msg.channel % 2
                            if mid.tracks[k].name == 'LH':
                               msg.channel = 0
                            if mid.tracks[k].name == 'RH':
                               msg.channel = 1
                        if msg.type == 'note_off':
                            msg.velocity = 0

            # Merge tracks
            self.loading = 3  # 3 = Merge
            time_passed = 0
            notes_on = set()
            ignore_note_idx = set()
            note_idx = 0
            unfiltered_song_tracks = mido.merge_tracks(mid.tracks)
            unfiltered_notes_time = []
            note_gaps = []


            for msg in mid:
                if hasattr(msg, 'time'):
                    time_passed += msg.time
                    if msg.time > 0:
                        notes_on.clear()
                if not msg.is_meta:
                    if msg.type == 'note_on' and msg.velocity > 0:
                        if msg.note in notes_on:
                            ignore_note_idx.add(note_idx)

                        notes_on.add(msg.note)
                unfiltered_notes_time.append(time_passed)
                note_idx += 1

            self.notes_time.clear()
            self.song_tracks.clear()
            for i in range(len(unfiltered_song_tracks)):
                if not i in ignore_note_idx:
                    self.song_tracks.append(unfiltered_song_tracks[i])
                    self.notes_time.append(unfiltered_notes_time[i])

            # fill prev and next time gaps
            prev_note_on = {}
            curr_prev_note_on = {i: None for i in range(2)}

            for i, msg in enumerate(self.song_tracks):
                prev_note_on[i] = curr_prev_note_on.copy()
                if msg.type == 'note_on':
                    channel = msg.channel
                    if msg.velocity > 0:
                        curr_prev_note_on[channel] = i

            next_note_on = {}
            curr_next_note_on = {i: None for i in range(2)}
            for i in range(len(self.song_tracks)-1, -1, -1):
                msg = self.song_tracks[i]
                next_note_on[i] = curr_next_note_on.copy()
                if msg.type == 'note_on':
                    channel = msg.channel
                    if msg.velocity > 0:
                        curr_next_note_on[channel] = i

            gaps_array = [
                {
                    'time_to_prev': {i: None for i in range(2)},
                    'time_to_next': {i: None for i in range(2)}
                } for i in range(len(self.song_tracks))
            ]

            for i, msg in enumerate(self.song_tracks):
                if i in prev_note_on:
                    if i not in next_note_on:
                        print("SANITY CHECK ERROR")
                        six=notex
                    for c in prev_note_on[i]:
                        if prev_note_on[i][c] is not None:
                            gaps_array[i]['time_to_prev'][c] = self.notes_time[i] - self.notes_time[prev_note_on[i][c]]
                        else:
                            gaps_array[i]['time_to_prev'][c] = 10000
                        if next_note_on[i][c] is not None:
                            gaps_array[i]['time_to_next'][c] = self.notes_time[next_note_on[i][c]] - self.notes_time[i]
                        else:
                            gaps_array[i]['time_to_next'][c] = 10000

            self.measure_data = self.init_measure_data(self.song_tracks)

            self.gaps_array = gaps_array

            fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
            self.readonly(False)
            # Save to cache
            with open('Songs/cache/' + song_path + '.p', 'wb') as handle:
                cache = {'song_tempo': self.song_tempo, 'ticks_per_beat': self.ticks_per_beat,
                         'notes_time': self.notes_time, 'song_tracks': self.song_tracks,
                         'measure_data': self.measure_data, 'gaps': self.gaps_array}
                pickle.dump(cache, handle, protocol=pickle.HIGHEST_PROTOCOL)
                
            self.readonly(True)

            self.loading = 4  # 4 = Done
        except Exception as e:
            print(e)
            traceback.print_exc()
            self.loading = 5  # 5 = Error!
            self.is_loaded_midi.clear()

    def darken_color(self, red, green, blue, factor):
        new_red = int(max(0, red * (1 - factor)))
        new_green = int(max(0, green * (1 - factor)))
        new_blue = int(max(0, blue * (1 - factor)))
        return (new_red, new_green, new_blue)

    def show_notes_to_press(self,notes_to_press):
        self.switch_off_all_leds()
        for note in notes_to_press:
            note_position = get_note_position(note, self.ledstrip, self.ledsettings)
            isWhite = get_key_color(note)

            red = 255
            green = 255
            blue = 255
            if notes_to_press[note][0]["channel"] == 0:
                red = int(self.hand_colorList[self.hand_colorR][0])
                green = int(self.hand_colorList[self.hand_colorR][1])
                blue = int(self.hand_colorList[self.hand_colorR][2])
            if notes_to_press[note][0]["channel"] == 1:
                red = int(self.hand_colorList[self.hand_colorL][0])
                green = int(self.hand_colorList[self.hand_colorL][1])
                blue = int(self.hand_colorList[self.hand_colorL][2])

            count = len(notes_to_press[note])
            rb = 1 if red>0 else 0
            gb = 1 if green>0 else 0
            bb = 1 if blue>0 else 0

            brightness = LOWEST_LED_BRIGHT
            if count>1:
                brightness = MAX_LED_BRIGHT
            elif isWhite:
                brightness = MIDDLE_LED_BRIGHT
            red =   clamp(rb * brightness, 0, 255)
            green = clamp(gb * brightness, 0, 255)
            blue =  clamp(bb * brightness, 0, 255)

            self.ledstrip.strip.setPixelColor(note_position, Color(green,red,blue))

        # Initialize arrays to hold the lowest and highest notes for channels 0 and 1
        lowest_note_channel = [None, None]
        highest_note_channel = [None, None]

        last_index = None

        # Loop over each note in the dictionary
        for note_number, note_data in notes_to_press.items():
            channel = note_data[0]["channel"] # Get the channel for the note
            if last_index is None or note_data[0]["idx"] > last_index:
                last_index = note_data[0]["idx"]
            if channel == 0 or channel == 1:
                # If the channel is 0 or 1, update the highest and lowest notes for that channel
                if lowest_note_channel[channel] is None or note_number < lowest_note_channel[channel]:
                    lowest_note_channel[channel] = note_number
                if highest_note_channel[channel] is None or note_number > highest_note_channel[channel]:
                    highest_note_channel[channel] = note_number

        markerColor = Color(LOWEST_LED_BRIGHT,LOWEST_LED_BRIGHT,0)
        if highest_note_channel[1] is None:
            higherChannel = 0
            gap_between_channels = 100
        elif highest_note_channel[0] is None:
            higherChannel = 1
            gap_between_channels = 100
        else:
            higherChannel = 1 if highest_note_channel[1] > highest_note_channel[0] else 0
            gap_between_channels = lowest_note_channel[higherChannel] - highest_note_channel[1-higherChannel]
        for channel in range(2):
            next_note = self.get_lowest_chord_note_in_channel(channel, last_index)
            if (lowest_note_channel[channel] is not None
                      and (next_note is None or next_note >= lowest_note_channel[channel])):
                if DEBUG_MARKERS:
                    print("Next note in channel "+str(channel)+" is "+self.midi_note_num_to_string(next_note))
                    print("   which is higher than the lowest shown note "+self.midi_note_num_to_string(lowest_note_channel[channel]))
                note_position = get_note_position(lowest_note_channel[channel], self.ledstrip, self.ledsettings)
                if higherChannel != channel or gap_between_channels > 5:
                    self.ledstrip.strip.setPixelColor(note_position -3, markerColor)
                    self.ledstrip.strip.setPixelColor(note_position -4, markerColor)
                    self.ledstrip.strip.setPixelColor(note_position -5, markerColor)
                elif gap_between_channels > 1:
                    self.ledstrip.strip.setPixelColor(note_position -1, markerColor)
            next_note = self.get_highest_chord_note_in_channel(channel, last_index)
            if (highest_note_channel[channel] is not None
                      and (next_note is None or next_note <= highest_note_channel[channel])):
                if DEBUG_MARKERS:
                    print("Next note in channel "+str(channel)+" is "+self.midi_note_num_to_string(next_note))
                    print("   which is lower than the highest shown note "+self.midi_note_num_to_string(highest_note_channel[channel]))
                note_position = get_note_position(highest_note_channel[channel], self.ledstrip, self.ledsettings)
                if higherChannel == channel or gap_between_channels > 5:
                    self.ledstrip.strip.setPixelColor(note_position +3, markerColor)
                    self.ledstrip.strip.setPixelColor(note_position +4, markerColor)
                    self.ledstrip.strip.setPixelColor(note_position +5, markerColor)
                elif gap_between_channels > 1:
                    self.ledstrip.strip.setPixelColor(note_position +1, markerColor)


        self.ledstrip.strip.show()


    def get_next_chord(self, index, channel=None):
        time_next_chord = None
        notes = []
        for i in range(index + 1, index + 50):
            if i >= len(self.song_tracks):
                break
            if time_next_chord is not None and self.notes_time[i] - time_next_chord > THRESHOLD_CHORD_NOTE_DISTANCE:
                break
            if self.song_tracks[i].type == "note_on" and (channel is None or self.song_tracks[i].channel == channel) and self.song_tracks[i].velocity > 0:
                if time_next_chord is None:
                    time_next_chord = self.notes_time[i]
                notes.append(i)
        return notes

    def get_highest_chord_note_in_channel(self, channel, index):
        indices = self.get_next_chord(index, channel)
        notes = [self.song_tracks[i].note for i in indices]
        return max(notes) if notes else None

    def get_lowest_chord_note_in_channel(self, channel, index):
        indices = self.get_next_chord(index, channel)
        notes = [self.song_tracks[i].note for i in indices]
        return min(notes) if notes else None
    
    def still_notes_in_chord(self, start_idx):
        for idx in range(start_idx + 1, start_idx + 100):
            if idx >= len(self.song_tracks):
                return False
            msg = self.song_tracks[idx]
            if hasattr(msg,"time") and msg.time > 0:
                return False
            if msg.type in ('note_on', 'note_off') and msg.velocity > 0:
                return True
        return False
        
    def midi_note_num_to_string(self, note_midi_idx):
        # Calculate the octave and note number
        octave = (note_midi_idx // 12) - 1
        note_num = note_midi_idx % 12

        # Map the note number to a note letter and accidental
        notes = {0: 'C', 1: 'C#', 2: 'D', 3: 'Eb', 4: 'E', 5: 'F',
                 6: 'F#', 7: 'G', 8: 'G#', 9: 'A', 10: 'Bb', 11: 'B'}
        return f"{notes[note_num]}{octave}"

    def midi_note_to_notation(self, msg):
        if msg.type == 'note_on' or msg.type == 'note_off':
            notestr = self.midi_note_num_to_string(msg.note)
            if msg.type == 'note_on' and msg.velocity>0:
                on_off = "ON"
            else:
                on_off = "OFF"
            offset = ""
            if msg.time>0:
                offset = "+"+str(msg.time);

            # Construct the notation string
            return f"{notestr} {on_off}  {offset}"
        else:
            return str(msg)

    def switch_off_all_leds(self):
        fastColorWipe(self.ledstrip.strip, True, self.ledsettings)        
        self.switch_off_leds.clear()
    
    def switch_off_due_leds(self):
        now = time.time()
        remove = []
        for led_idx in self.switch_off_leds:
            if now - self.switch_off_leds[led_idx] > 1:
                self.ledstrip.strip.setPixelColor(led_idx, Color(0,0,0))
                remove.append(led_idx)
        
        if remove:
            self.ledstrip.strip.show()
            for led_idx in remove:
                del self.switch_off_leds[led_idx]        

    def wait_notes_to_press(self, start_score, notes_to_press, ignore_first_delay):
        if not notes_to_press:
            return
        notes_pressed = []
        if not self.blind_mode:
            self.switch_off_all_leds()
            self.show_notes_to_press(notes_to_press)

        start_waiting = time.time()

        start_wrong_keys = self.wrong_keys

        while notes_to_press and self.is_started_midi:
            elapsed_already = max(0,time.time()-start_waiting - 0.25)
            if ignore_first_delay:
                elapsed_already = 0
            if elapsed_already > 1:
                elapsed_already = 1
            if self.practice == PRACTICE_ARCADE:
                self.current_score = start_score - (self.wrong_keys * 10 + self.total_wait_time + elapsed_already)
                if self.current_score <= 0:
                    # print("Score reached zero")
                    notes_to_press.clear()
                    self.total_wait_time = 10000
                    break
            elif self.practice == PRACTICE_PERFECTION:
                self.current_score = (self.total_wait_time + elapsed_already) * 3 + self.wrong_keys * 10
                if self.wrong_keys - start_wrong_keys > 15:
                   self.blind_mode = False

            self.switch_off_due_leds()
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
                        if note in notes_to_press:
                            if len(notes_to_press[note]) == 1:
                                notes_to_press.pop(note)
                                self.ledstrip.strip.setPixelColor(note_position, Color(32,0,0))
                                self.switch_off_leds[note_position] = time.time()
                            else:
                                notes_to_press[note].pop(0)
                                if self.blind_mode:
                                    self.ledstrip.strip.setPixelColor(note_position, Color(32,0,0))
                                    self.switch_off_leds[note_position] = time.time()
                                else:
                                    fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
                                    self.show_notes_to_press(notes_to_press)
                                    

                        else:
                            self.wrong_keys += 1
                            self.ledstrip.strip.setPixelColor(note_position, Color(0,32,0))
                            self.switch_off_leds[note_position] = time.time()
                            if (self.wrong_keys - start_wrong_keys == 16 and self.blind_mode):
                                self.blind_mode = False
                                self.show_notes_to_press(notes_to_press)
                                self.ledstrip.strip.show()
                if msg_in.type == 'sysex' and self.blind_mode:
                    strmsg = str(msg_in.data)
                    if strmsg == '(68, 126, 126, 127, 15, 1, 8, 0, 1, 0, 1, 0, 2, 0)':
                        self.restart_blind = True
                        return        

                else:
                    try:
                        notes_pressed.remove(note)
                    except ValueError:
                        pass  # do nothing

        elapsed_already = max(0,time.time()-start_waiting - 0.25)
        if elapsed_already > 1:
            elapsed_already = 1
        if ignore_first_delay:
            elapsed_already = 0
        self.total_wait_time += elapsed_already

    def is_pedal_command(self, msg):
        return msg.type == 'control_change' and msg.control == 64

    def dump_note(self, note_idx):
        msg = self.song_tracks[note_idx]
        if msg.type == "note_on" or msg.type == "note_off":
            gaps = self.gaps_array[note_idx]
            output = "[{:.2f},{:.2f}] << N >> [{:.2f},{:.2f}]".format(
                gaps['time_to_prev'][0],
                gaps['time_to_prev'][1],
                gaps['time_to_next'][0],
                gaps['time_to_next'][1]
            )
        else:
            output = ""
        if DEBUG:    
            print("      note ["+str(msg.channel)+"] : "+str(note_idx)+"@"+format(self.notes_time[note_idx],'.2f')+"  " +self.midi_note_to_notation(msg)+"   "+output)

    def modify_brightness(self, color, new_brightness):
        green, red, blue = getRGB(color)
        rb = 1 if red>0 else 0
        gb = 1 if green>0 else 0
        bb = 1 if blue>0 else 0
        return Color(gb * new_brightness, rb * new_brightness, bb * new_brightness)

    def listen_measures(self, start, end):
        try:
            self.switch_off_all_leds()            
            time_prev = time.time()

            end_idx = self.measure_data[end]['note_index']

            start_idx = self.measure_data[start]['note_index']

            self.current_idx = start_idx
            msg_index = start_idx
            self.current_measure = start

            for msg in self.song_tracks[start_idx:end_idx]:
                # Exit thread if learning is stopped
                if not self.is_started_midi:
                    break

                # Get time delay
                tDelay = mido.tick2second(msg.time, self.ticks_per_beat, self.song_tempo * 100 / self.set_tempo)

                # Realize time delay, consider also the time lost during computation
                delay = max(0, tDelay - (
                        time.time() - time_prev) - 0.003)  # 0.003 sec calibratable to acount for extra time loss
                if msg_index>start_idx and self.notes_time[msg_index]>self.notes_time[msg_index-1]:
                    self.ledstrip.strip.show()

                time.sleep(delay)
                time_prev = time.time()
                while (self.current_measure+1 < len(self.measure_data) and
                    self.measure_data[self.current_measure+1]['note_index']<=msg_index):
                        self.current_measure += 1

                # Light-up LEDs with the notes to press
                if not msg.is_meta:
                    # Calculate note position on the strip and display
                    if msg.type == 'note_on' or msg.type == 'note_off':
                        note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                        isBlack = get_key_color(msg.note)
                        if msg.velocity == 0 or msg.type == 'note_off':
                            red = 0
                            green = 0
                            blue = 0
                        elif msg.channel == 0:
                            red = int(self.hand_colorList[self.hand_colorR][0])                            
                            green = int(self.hand_colorList[self.hand_colorR][1])
                            blue = int(self.hand_colorList[self.hand_colorR][2])
                        elif msg.channel == 1:
                            red = int(self.hand_colorList[self.hand_colorL][0])
                            green = int(self.hand_colorList[self.hand_colorL][1])
                            blue = int(self.hand_colorList[self.hand_colorL][2])
                        else:
                            red = 0
                            green = 0
                            blue = 0

                        brightness = LOWEST_LED_BRIGHT if isBlack else MIDDLE_LED_BRIGHT
            
                        self.ledstrip.strip.setPixelColor(note_position, self.modify_brightness(Color(green, red, blue),brightness))

                    # Play selected Track
                    if not self.is_pedal_command(msg):
                        self.midiports.playport.send(msg)
                msg_index += 1
            self.ledstrip.strip.show()
            time.sleep(0.5)
            for channel in range(16):
                self.midiports.playport.send(mido.Message('control_change', channel=channel, control=123, value=0))

        except Exception as e:
            print(e);
            traceback.print_exc()
            self.is_started_midi = False

    
    def get_measures_per_exercise(self):
        return int(self.learnStepList[self.learn_step].split("/")[0])
    
    def get_repetitions(self):
        return int(self.learnStepList[self.learn_step].split("/")[1])
        
    def find_note_with_same_time(self, notes_to_press, idx):
        channel = self.song_tracks[idx].channel
        for note in notes_to_press:
            for i in range(len(notes_to_press[note])):
                note_index = notes_to_press[note][i]["idx"]
                #ipdb.set_trace()
                if idx != note_index and notes_to_press[note][i]["channel"] == channel and abs(self.notes_time[note_index] - self.notes_time[idx]) < THRESHOLD_CHORD_NOTE_DISTANCE:
                    return self.notes_time[note_index]
        return None

    def learn_midi(self):
        loops_count = 0
        self.switch_off_leds = {}
        self.blind_mode = False
        self.restart_blind = False
        self.repetition_count = 0
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

        start_measure = int(self.start_point - 1)
        start_measure = clamp(start_measure, 0, len(self.measure_data)-1)
        end_measure = int(self.end_point)
        end_measure = clamp(end_measure, start_measure, len(self.measure_data)-1)

        if self.practice == PRACTICE_PERFECTION:
            end_measure = clamp(start_measure + self.get_measures_per_exercise(), start_measure, len(self.measure_data)-1)

        last_played_measure = -1

        while(keep_looping):
            self.learning_midi = True
            ignore_first_delay = True
            if self.practice in (PRACTICE_MELODY, PRACTICE_ARCADE, PRACTICE_PROGRESSIVE, PRACTICE_PERFECTION) and not self.blind_mode:
                red1 = int(self.hand_colorList[self.hand_colorR][0])                            
                green1 = int(self.hand_colorList[self.hand_colorR][1])
                blue1 = int(self.hand_colorList[self.hand_colorR][2])
                red2 = int(self.hand_colorList[self.hand_colorL][0])
                green2 = int(self.hand_colorList[self.hand_colorL][1])
                blue2 = int(self.hand_colorList[self.hand_colorL][2])               
            
                pattern = []
                pattern.append(self.modify_brightness(Color(green1, red1, blue1),LOWEST_LED_BRIGHT))
                pattern.append(self.modify_brightness(Color(green2, red2, blue2),LOWEST_LED_BRIGHT))
                setLedPattern(self.ledstrip.strip, pattern)
            elif self.blind_mode:
                pattern = []
                if self.repetition_count == 0:
                    pattern.append(Color(LOWEST_LED_BRIGHT, LOWEST_LED_BRIGHT, LOWEST_LED_BRIGHT))
                    for i in range(self.get_repetitions() - 1):
                            pattern.append(Color(0, 0, 0))
                else:
                    ignore_first_delay = False
                    for i in range(self.get_repetitions()):
                        if self.repetition_count>i:
                            pattern.append(Color(LOWEST_LED_BRIGHT, 0, 0))
                        else:
                            pattern.append(Color(0, 0, 0))
                pattern.append(Color(0, 0, 0))
                setLedPattern(self.ledstrip.strip, pattern)
            else:
                changeAllLedsColor(self.ledstrip.strip, LOWEST_LED_BRIGHT, LOWEST_LED_BRIGHT, MIDDLE_LED_BRIGHT)
            time.sleep(0.25)
            self.restart_blind = False
            if self.practice == PRACTICE_PERFECTION and last_played_measure!=start_measure:
                last_played_measure = start_measure
                self.listen_measures(start_measure, end_measure)                            

            led_strip_dirty = False
            accumulated_chord = None
            try:
                self.switch_off_all_leds()
                time_prev = time.time()
                notes_to_press = {}

                end_idx = self.measure_data[end_measure]['note_index']
                start_idx = self.measure_data[start_measure]['note_index']
                self.current_measure = start_measure - 1

                self.current_idx = start_idx
                msg_index = start_idx

                first_note = True

                self.total_wait_time = 0.0
                self.wrong_keys = 0
                start_score = 100
                self.current_score = start_score

                accDelay = 0

                if not self.blind_mode or self.repetition_count == 0:
                    # Flush pending notes
                    for msg_in in self.midiports.inport.iter_pending():
                        note = int(find_between(str(msg_in), "note=", " "))

                for msg in self.song_tracks[start_idx:end_idx]:
                    # Exit thread if learning is stopped
                    if not self.is_started_midi:
                        break

                    # Get time delay
                    tDelay = mido.tick2second(msg.time, self.ticks_per_beat, self.song_tempo * 100 / self.set_tempo)

                    accDelay += tDelay

                    while (self.current_measure+1 < len(self.measure_data) and
                        self.measure_data[self.current_measure+1]['note_index']<=msg_index):
                            self.current_measure += 1
                            if DEBUG:
                                print("--------------   Measure "+str(self.current_measure))
                            if self.practice == PRACTICE_PROGRESSIVE:
                                # Wait for accumulated notes before going to next measure
                                self.wait_notes_to_press(start_score, notes_to_press, ignore_first_delay)

                                self.switch_off_all_leds()
                                self.listen_measures(self.current_measure, self.current_measure + 1)
                                # Flush pending notes
                                for msg_in in self.midiports.inport.iter_pending():
                                    note = int(find_between(str(msg_in), "note=", " "))

                                ignore_first_delay = True
                                accDelay = 0

                    if self.practice == PRACTICE_ARCADE:
                        self.current_score = start_score - (self.wrong_keys * 10 + self.total_wait_time)
                        if self.current_score<0:
                            # print("Score reached zero")
                            break
                    elif self.practice == PRACTICE_PERFECTION :
                        self.current_score = self.total_wait_time * 3 + self.wrong_keys * 10
                        if self.restart_blind:
                            break

                    self.switch_off_due_leds()

                    # Light-up LEDs with the notes to press
                    if not msg.is_meta:
                        # Calculate note position on the strip and display
                        if ((msg.type == 'note_on' or msg.type == 'note_off') and msg.velocity > 0 and
                             not self.blind_mode) :
                            note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                            if led_strip_dirty:
                                fastColorWipe(self.ledstrip.strip, False, self.ledsettings)
                                self.switch_off_leds.clear()                                
                                led_strip_dirty = False

                            self.ledstrip.strip.setPixelColor(note_position, Color(16, 16, 16))
                            
                            # skip show, if there are note_on events
                            if not self.still_notes_in_chord(msg_index):
                                self.ledstrip.strip.show()

                        # Save notes to press
                        if msg.type == 'note_on' and msg.velocity > 0 and (
                                msg.channel == self.hands or self.hands == 0):
                            if not notes_to_press:
                                accDelay = 0    # start calculating from now how much time we accumulated

                            if msg.note not in notes_to_press:
                                notes_to_press[msg.note] = [{"idx": msg_index,"channel":msg.channel}]
                            else:
                                notes_to_press[msg.note].append({"idx": msg_index,"channel":msg.channel})
                            #ipdb.set_trace()
                            if self.find_note_with_same_time(notes_to_press, msg_index) and accumulated_chord is None:
                                accumulated_chord = self.notes_time[msg_index]
                                print("Start chord")

                        # Play selected Track
                        if ((
                                self.hands == 1 and self.mute_hand != 2 and msg.channel == 2) or
                                # send midi sound for Left hand
                                (
                                        self.hands == 2 and self.mute_hand != 1 and msg.channel == 1) or
                                # send midi sound for Right hand
                                self.practice == PRACTICE_LISTEN):  # send midi sound for Listen only
                            self.midiports.playport.send(msg)

                    # Realize time delay, consider also the time lost during computation
                    delay = max(0, tDelay - (
                            time.time() - time_prev) - 0.003)  # 0.003 sec calibratable to acount for extra time loss
                    time.sleep(delay)
                    time_prev = time.time()

                    # Check notes to press
                    if not msg.is_meta:
                        try:
                            self.socket_send.append(self.notes_time[msg_index])
                        except Exception as e:
                            print(e)
                        self.current_idx += 1

                        wait_for_user = False

                        self.dump_note(msg_index)

                        if msg.channel in (0,1):
                            current_hand = msg.channel
                            other_hand = 1 - msg.channel

                            gaps = self.gaps_array[msg_index]
                            if accDelay >= 0.37:
                                wait_for_user = True
                                if DEBUG:
                                    print("accDelay :"+str(accDelay))                                   
                            elif ( (gaps['time_to_next'][current_hand] is None or gaps['time_to_next'][current_hand] > 0.12)
                                     and (gaps['time_to_next'][other_hand] is None
                                          or (gaps['time_to_next'][other_hand] > 0.05 and gaps['time_to_next'][other_hand] + gaps['time_to_prev'][other_hand] > 0.12))
                                     ):
                                wait_for_user = True
                                if DEBUG:
                                    print("Gap [" + str(current_hand) + "] > 0.12 && Gap[" + str(other_hand) +
                                          "] = " + str(gaps['time_to_next'][other_hand]) + "+"
                                          + str(gaps['time_to_prev'][other_hand]) )
                            elif (accumulated_chord is not None and accumulated_chord < self.notes_time[msg_index] 
                                     and (gaps['time_to_next'][0] is None or gaps['time_to_next'][0] > 0.02) 
                                     and (gaps['time_to_next'][1] is None or gaps['time_to_next'][1] > 0.02)): 
                                chord0 = self.get_next_chord(msg_index,0)
                                chord1 = self.get_next_chord(msg_index,1)
                                if chord0 is None:
                                    first_chord = chord1
                                elif chord1 is None:
                                    first_chord = chord0
                                else:
                                    first_chord = chord0 if self.notes_time[chord0[0]]<self.notes_time[chord1[0]] else chord1
                                if first_chord is not None and len(first_chord) > 1:
                                    wait_for_user = True
                                    if DEBUG:
                                        print("Next chord [" + str(first_chord) + "] has more than one key" )


                        if (wait_for_user 
                              and msg.type in ['note_on','note_off']
                              and notes_to_press 
                              and not self.still_notes_in_chord(msg_index)
                              and self.practice in (PRACTICE_MELODY, PRACTICE_ARCADE, PRACTICE_PROGRESSIVE, PRACTICE_PERFECTION)):
                            self.wait_notes_to_press(start_score, notes_to_press, ignore_first_delay)
                            ignore_first_delay = False
                            led_strip_dirty = True
                            accumulated_chord = None
                            accDelay = 0


                    # Switch off LEDs with the notes to press
                    if (not msg.is_meta
                        and self.practice not in (PRACTICE_MELODY, PRACTICE_ARCADE, PRACTICE_PROGRESSIVE, PRACTICE_PERFECTION)):
                        # Calculate note position on the strip and display
                        if ((msg.type == 'note_on' and msg.velocity == 0) and not self.blind_mode) :
                            note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                            self.ledstrip.strip.setPixelColor(note_position, Color(0,0,0))
                            self.ledstrip.strip.show()
                    msg_index += 1

                if self.practice in (PRACTICE_MELODY, PRACTICE_ARCADE, PRACTICE_PROGRESSIVE, PRACTICE_PERFECTION):
                    self.wait_notes_to_press(start_score, notes_to_press, ignore_first_delay)

            except Exception as e:
                print(e);
                traceback.print_exc()
                self.is_started_midi = False
            if self.is_started_midi:
                if not self.blind_mode:
                    if self.practice == PRACTICE_ARCADE and self.current_score < 0:
                        changeAllLedsColor(self.ledstrip.strip, 0, 16, 0)
                    elif self.practice == PRACTICE_PERFECTION and (self.current_score >= 10 or self.restart_blind):
                        changeAllLedsColor(self.ledstrip.strip, 0, 16, 0)
                    else:
                        changeAllLedsColor(self.ledstrip.strip, 16, 0, 0)

                if self.practice == PRACTICE_PERFECTION:
                    if self.current_score < 10 and not self.restart_blind:
                        if self.blind_mode:
                            self.repetition_count += 1
                            if self.repetition_count == self.get_repetitions():
                                start_measure += 1
                                self.blind_mode = False
                                changeAllLedsColor(self.ledstrip.strip, 16, 0, 0)
                                time.sleep(1)
                        else:
                            self.blind_mode = True
                            self.repetition_count = 0
                            time.sleep(1)
                    if self.current_score >= 10 and self.blind_mode:
                        changeAllLedsColor(self.ledstrip.strip, 0, 16, 0)
                        self.repetition_count = 0
                        time.sleep(1)
                    end_measure = clamp(start_measure + self.get_measures_per_exercise(), start_measure, len(self.measure_data)-1)
                else:
                    time.sleep(3)

            self.switch_off_all_leds()
            self.learning_midi = False
            if(not self.is_loop_active or self.is_started_midi == False):
                keep_looping = False


    def convert_midi_to_abc(self, midi_file):
        if not os.path.isfile('Songs/' + midi_file.replace(".mid", ".abc")):
            #subprocess.call(['midi2abc',  'Songs/' + midi_file, '-o', 'Songs/' + midi_file.replace(".mid", ".abc")])
            self.readonly(False)
            try:
                subprocess.check_output(['midi2abc',  'Songs/' + midi_file, '-o', 'Songs/' + midi_file.replace(".mid", ".abc")])
            except Exception as e:
                #check if e contains the string 'No such file or directory'
                if 'No such file or directory' in str(e):
                    print("Midiabc not found, installing...")
                    self.install_midi2abc()
                    self.convert_midi_to_abc(midi_file)
            self.readonly(True)
        else:
            print("file already converted")

    def readonly(self, enable):
        if self.is_read_only_fs:
            if enable:
                subprocess.call(["/bin/bash", '-c', '-i', 'ro && exit'])
            else:
                subprocess.call(["/bin/bash", '-c', '-i', 'rw && exit'])

    def install_midi2abc(self):
        print("Installing abcmidi")
        subprocess.call(['sudo', 'apt-get', 'install', 'abcmidi', '-y'])


