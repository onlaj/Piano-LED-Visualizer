import ast
import threading
import time
import json

import mido
import subprocess

import os

from lib.functions import clamp, fastColorWipe, find_between, get_note_position
from lib.rpi_drivers import Color

import numpy as np
import pickle
from lib.log_setup import logger
from lib.score_manager import ScoreManager
from webinterface import app_state

import logging

# Create a score logger
score_logger = logging.getLogger("score_logger")
score_logger.setLevel(logging.DEBUG)
score_logger.propagate = False
file_handler = logging.FileHandler("score_log.txt")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
score_logger.addHandler(file_handler)
score_logger.info("Score logger initialized.")


def find_nearest(array, target):
    array = np.asarray(array)
    idx = (np.abs(array - target)).argmin()
    return idx


# Get midi song tempo
def get_tempo(mid):
    for msg in mid:  # Search for tempo
        if msg.type == 'set_tempo':
            return msg.tempo
    return 500000  # If not found return default tempo


class LearnMIDI:
    def __init__(self, usersettings, ledsettings, midiports, ledstrip):
        self.menu = None
        self.usersettings = usersettings
        self.ledsettings = ledsettings
        self.midiports = midiports
        self.ledstrip = ledstrip
        
        # Initialize the score manager

        self.loading = 0
        self.songs_per_page = int(usersettings.get_setting_value("songs_per_page"))
        self.sort_by = usersettings.get_setting_value("sort_by")
        self.practice = int(usersettings.get_setting_value("practice"))
        self.hands = int(usersettings.get_setting_value("hands"))
        self.mute_hand = int(usersettings.get_setting_value("mute_hand"))
        self.start_point = float(usersettings.get_setting_value("start_point"))
        self.end_point = float(usersettings.get_setting_value("end_point"))
        self.set_tempo = int(usersettings.get_setting_value("set_tempo"))
        self.hand_colorR = int(usersettings.get_setting_value("hand_colorR"))
        self.hand_colorL = int(usersettings.get_setting_value("hand_colorL"))
        self.prev_hand_colorR = int(usersettings.get_setting_value("prev_hand_colorR"))
        self.prev_hand_colorL = int(usersettings.get_setting_value("prev_hand_colorL"))

        self.show_wrong_notes = int(usersettings.get_setting_value("show_wrong_notes"))
        self.show_future_notes = int(usersettings.get_setting_value("show_future_notes"))

        self.notes_time = []
        self.socket_send = []

        # Store software's notes that need to be played when user presses their key
        self.pending_software_notes = []
        # Store the next note's timing information
        self.next_note_time = None
        self.next_note_delay = None

        self.is_loop_active = int(usersettings.get_setting_value("is_loop_active"))
        
        self.is_led_activeL = int(usersettings.get_setting_value("is_led_activeL"))
        self.is_led_activeR = int(usersettings.get_setting_value("is_led_activeR"))

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
        self.t = None

        self.current_idx = 0

        self.mistakes_count = 0
        self.number_of_mistakes = int(usersettings.get_setting_value("number_of_mistakes"))
        self.delay_countR = 0
        self.delay_countL = 0
        self.awaiting_restart_loop = False
        self.score_manager = ScoreManager()
        self.right_hand_timing = []
        self.left_hand_timing = []
        self.right_hand_mistakes = []
        self.left_hand_mistakes = []


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

    def restart_loop(self):
        self.awaiting_restart_loop = True

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

    def change_show_wrong_notes(self, value):
        self.show_wrong_notes += value
        self.show_wrong_notes = clamp(self.show_wrong_notes, 0, 1)
        self.usersettings.change_setting_value("show_wrong_notes", self.show_wrong_notes)

    def change_show_future_notes(self, value):
        self.show_future_notes += value
        self.show_future_notes = clamp(self.show_future_notes, 0, 1)
        self.usersettings.change_setting_value("show_future_notes", self.show_future_notes)

    def change_number_of_mistakes(self, value):
        self.number_of_mistakes += value
        self.number_of_mistakes = clamp(self.number_of_mistakes, 0, 255)
        self.usersettings.change_setting_value("number_of_mistakes", self.number_of_mistakes)

    def change_hand_color(self, value, hand):
        if hand == 'RIGHT':
            self.hand_colorR += value
            self.hand_colorR = clamp(self.hand_colorR, 0, len(self.hand_colorList) - 1)
            self.usersettings.change_setting_value("hand_colorR", self.hand_colorR)
        elif hand == 'LEFT':
            self.hand_colorL += value
            self.hand_colorL = clamp(self.hand_colorL, 0, len(self.hand_colorList) - 1)
            self.usersettings.change_setting_value("hand_colorL", self.hand_colorL)

    def load_song_from_cache(self, song_path):
        # Load song from cache
        try:
            if os.path.isfile('Songs/cache/' + song_path + '.p'):
                logger.info("Loading song from cache")
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
            logger.warning(e)

    def load_midi(self, song_path):
        while 4 > self.loading > 0:
            time.sleep(1)

        if song_path in self.is_loaded_midi.keys():
            return

        self.is_loaded_midi.clear()
        self.is_loaded_midi[song_path] = True
        # Remember currently loaded song for highscore tracking
        try:
            self.current_song_name = song_path
        except Exception:
            self.current_song_name = song_path
        self.loading = 1  # 1 = Load..
        self.is_started_midi = False  # Stop current learning song
        self.t = threading.currentThread()

        # Load song from cache
        if self.load_song_from_cache(song_path):
            return
        logger.info("Cache not found")

        try:
            # Load the midi file
            mid = mido.MidiFile('Songs/' + song_path, clip=True)  # clip=True fixes some midi files

            # Get tempo and Ticks per beat
            self.song_tempo = get_tempo(mid)
            self.ticks_per_beat = mid.ticks_per_beat

            # Assign Tracks to different channels before merging to know the message origin
            self.loading = 2  # 2 = Proces
            if len(mid.tracks) == 2:  # check if the midi file has only 2 Tracks
                offset = 1
            else:
                offset = 0
            for k in range(len(mid.tracks)):
                for msg in mid.tracks[k]:
                    if not msg.is_meta and msg.type in ['note_on', 'note_off']:
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
                         'notes_time': self.notes_time, 'song_tracks': self.song_tracks, }
                pickle.dump(cache, handle, protocol=pickle.HIGHEST_PROTOCOL)

            self.loading = 4  # 4 = Done
        except Exception as e:
            logger.warning(e)
            self.loading = 5  # 5 = Error!
            self.is_loaded_midi.clear()

    # predict future notes in MIDI messages
    def predict_future_notes(self, starting_note, ending_note, notes_to_press):

        if self.show_future_notes != 1:
            return

        predicted_future_notes = []
        current_note = starting_note
        for msg in self.song_tracks[starting_note:ending_note]:
            # Get time delay
            tDelay = mido.tick2second(msg.time, self.ticks_per_beat, self.song_tempo * 100 / self.set_tempo)

            if not msg.is_meta and tDelay > 0 and (
                    msg.type == 'note_on' or msg.type == 'note_off') and predicted_future_notes and self.practice == 0:
                self.light_up_predicted_future_notes(predicted_future_notes)
                return

            if msg.type == 'note_on' and msg.velocity > 0:
                # make sure msg.note is not in notes_to_press list
                if msg.note not in notes_to_press:
                    predicted_future_notes.append(msg)

            current_note += 1

    def light_up_predicted_future_notes(self, notes):
        dim = 10
        for msg in notes:
            # Light-up LEDs with the notes to press
            if not msg.is_meta:
                # Calculate note position on the strip and display
                if msg.type == 'note_on' or msg.type == 'note_off':
                    note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)

                    brightness = 0.5
                    brightness /= dim
                    red, green, blue = [0, 0, 0]
                    if msg.channel == 1:
                        # red = int(self.hand_colorList[self.hand_colorR][0] * brightness)
                        # green = int(self.hand_colorList[self.hand_colorR][1] * brightness)
                        # blue = int(self.hand_colorList[self.hand_colorR][2] * brightness)
                        red, green, blue = [int(c * brightness) for c in self.hand_colorList[self.hand_colorR]]
                    if msg.channel == 2:
                        # red = int(self.hand_colorList[self.hand_colorL][0] * brightness)
                        # green = int(self.hand_colorList[self.hand_colorL][1] * brightness)
                        # blue = int(self.hand_colorList[self.hand_colorL][2] * brightness)
                        red, green, blue = [int(c * brightness) for c in self.hand_colorList[self.hand_colorL]]

                    self.ledstrip.strip.setPixelColor(note_position, Color(red, green, blue))
                    self.ledstrip.strip.show()

    def handle_wrong_notes(self, wrong_notes, hand_hint_notesL, hand_hint_notesR):

        if self.show_wrong_notes != 1:
            return

        brightness = 0.05
        # loop through wrong_notes and light them up
        for msg in wrong_notes:
            note = int(find_between(str(msg), "note=", " "))

            if "note_off" in str(msg):
                velocity = 0
            else:
                velocity = int(find_between(str(msg), "velocity=", " "))

            note_position = get_note_position(note, self.ledstrip, self.ledsettings)
            if velocity > 0:
                self.ledstrip.strip.setPixelColor(note_position, Color(255, 0, 0))
                self.mistakes_count += 1
                if self.is_led_activeL == 0:
                    for expected_note in hand_hint_notesL:
                        red, green, blue = [int(c * brightness) for c in self.hand_colorList[self.prev_hand_colorL]]
                        self.ledstrip.strip.setPixelColor(expected_note, Color(red, green, blue))
                if self.is_led_activeR == 0:
                    for expected_note in hand_hint_notesR:
                        red, green, blue = [int(c * brightness) for c in self.hand_colorList[self.prev_hand_colorR]]
                        self.ledstrip.strip.setPixelColor(expected_note, Color(red, green, blue))
                 
                # Wrong note penalty
                self.score_manager.penalize_for_wrong_note()
                score_logger.debug("wrong note - score:" +str(self.score_manager.get_score()))
                score_logger.debug("panelty:" +str(self.score_manager.get_last_score_update()))

                # # Send score update to frontend
                self.socket_send.append(json.dumps({
                    "type": "score_update",
                    "score": self.score_manager.get_score(),
                    "combo": self.score_manager.get_combo(),
                    "multiplier": self.score_manager.get_multiplier(),
                    "last_update": self.score_manager.get_last_score_update()
                }))
            else:
                self.ledstrip.strip.setPixelColor(note_position, Color(0, 0, 0))

        if self.mistakes_count > self.number_of_mistakes > 0:
            self.mistakes_count = 0
            self.restart_loop()

        self.ledstrip.strip.show()

    def learn_midi(self):
        loops_count = 0
        # Preliminary checks
        if self.is_started_midi:
            return
        if self.loading == 0:
            self.menu.render_message("Load song to start", "", 1500)
            return
        elif 0 < self.loading < 4:
            self.is_started_midi = True  # Prevent restarting the Thread
            while 0 < self.loading < 4:
                time.sleep(0.1)
        if self.loading == 4:
            self.is_started_midi = True  # Prevent restarting the Thread
            # Reset the score when starting a new learning session
            self.score_manager.reset()
            self.right_hand_timing.clear()
            self.left_hand_timing.clear()
            self.right_hand_mistakes.clear()
            self.left_hand_mistakes.clear()
            midi_time = 0
            self.delay_countR = 0
            self.delay_countL = 0
            score_logger.debug("score reset" +str(self.score_manager.get_score()))
                  
            # Send score update to frontend
            self.socket_send.append(json.dumps({
                "type": "score_update",
                "score": self.score_manager.get_score(),
                "combo": self.score_manager.get_combo(),
                "multiplier": self.score_manager.get_multiplier(),
                "last_update": 0 # Reset last update as well
            }))
        elif self.loading == 5:
            self.is_started_midi = False  # Allow restarting the Thread
            return

        self.t = threading.currentThread()
        hand_hint_notesL = []
        hand_hint_notesR = []

        keep_looping = True
        while keep_looping:
            time.sleep(1)
            self.score_manager.reset()
            self.right_hand_timing.clear()
            self.left_hand_timing.clear()
            self.right_hand_mistakes.clear()
            self.left_hand_mistakes.clear()
            self.delay_countR = 0
            self.delay_countL = 0
            midi_time = 0
            score_logger.debug("midi_time  - reset" +str(midi_time))
            score_logger.debug("score reset keep looping" +str(self.score_manager.get_score()))
            self.socket_send.append(json.dumps({
                "type": "score_update",
                "score": self.score_manager.get_score(),
                "combo": self.score_manager.get_combo(),
                "multiplier": self.score_manager.get_multiplier(),
                "last_update": 0
            }))
            try:
                fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
                time_prev = time.time()
                notes_to_press = []

                start_idx = int(self.start_point * len(self.song_tracks) / 100)
                end_idx = int(self.end_point * len(self.song_tracks) / 100)

                # self.current_idx does not count meta messages (used for sheet music sync in web interface)
                # absolute_idx counts all messages (used for predicting messages)

                self.current_idx = start_idx
                absolute_idx = start_idx

                for msg in self.song_tracks[start_idx:end_idx]:
                    self.midiports.last_activity = time.time()
                    # Exit thread if learning is stopped
                    if not self.is_started_midi:
                        break

                    # Get time delay
                    tDelay = mido.tick2second(msg.time, self.ticks_per_beat, self.song_tempo * 100 / self.set_tempo)

                    # Check notes to press
                    if not msg.is_meta:
                        try:
                            self.socket_send.append(self.notes_time[self.current_idx])
                        except Exception as e:
                            logger.warning(e)

                        self.current_idx += 1

                        if tDelay > 0 and (
                                msg.type == 'note_on' or msg.type == 'note_off') and notes_to_press and self.practice == 0:
                            notes_pressed = []
                            wrong_notes = []
                            self.predict_future_notes(absolute_idx, end_idx, notes_to_press)

                            # Store timing information for next note
                            self.next_note_time = time.time() + tDelay
                            self.next_note_delay = tDelay
                            midi_time += tDelay

                            while not set(notes_to_press).issubset(notes_pressed) and self.is_started_midi:
                                if self.awaiting_restart_loop:
                                    break
                                while self.midiports.midi_queue:
                                    msg_in, msg_timestamp = self.midiports.midi_queue.popleft()
                                    if msg_in.type not in ("note_on", "note_off"):
                                        continue

                                    note = int(find_between(str(msg_in), "note=", " "))

                                    if "note_off" in str(msg_in):
                                        velocity = 0
                                    else:
                                        velocity = int(find_between(str(msg_in), "velocity=", " "))

                                    # check if note is NOT in the list of notes to press
                                    if note not in notes_to_press:
                                        wrong_notes.append(msg_in)
                                        # Clear pending software notes if wrong key is pressed
                                        if velocity > 0:
                                            if msg.channel == 1:
                                                self.right_hand_mistakes.append(midi_time)
                                                score_logger.debug("right hand mistakes: %s", self.right_hand_mistakes)
                                            if msg.channel == 2:
                                                self.left_hand_mistakes.append(midi_time)
                                                score_logger.debug("left hand mistakes: %s", self.left_hand_mistakes)
                                            self.pending_software_notes.clear()
                                        continue
                                    
                                    # check if note is in the list of notes to press
                                    if velocity > 0:
                                        if note not in notes_pressed:
                                            notes_pressed.append(note)
 
                                            # Calculate delay from ideal hit time
                                            current_time = time.time()
                                            if self.next_note_time:
                                                # Get delay in seconds
                                                delay = current_time - self.next_note_time
                                                
                                                # Add score for correct note
                                                self.score_manager.add_score_for_correct_note(delay)

                                                note_timing = (midi_time, delay)
                                               
                                                score_logger.debug("midi_time" +str(midi_time))
                                                if msg.channel == 1: 
                                                    score_logger.debug("channel 1")
                                                    score_logger.debug("right hand timing note timimg: %s", self.right_hand_timing)
                                                    self.right_hand_timing.append(note_timing)
                                                    if delay >= self.score_manager.max_delay:
                                                        self.delay_countR += 1
                                                if msg.channel == 2:
                                                    score_logger.debug("channel- 2")
                                                    score_logger.debug("left hand timing note timimg: %s", self.left_hand_timing)
                                                    self.left_hand_timing.append(note_timing)
                                                    if delay >= self.score_manager.max_delay:
                                                        self.delay_countR += 1

                                                # send score update to frontend
                                                self.socket_send.append(json.dumps({
                                                    "type": "score_update",
                                                    "score": self.score_manager.get_score(),
                                                    "combo": self.score_manager.get_combo(),
                                                    "multiplier": self.score_manager.get_multiplier(),
                                                    "last_update": self.score_manager.get_last_score_update()
                                                }))



                                    else:
                                        try:
                                            notes_pressed.remove(note)
                                        except ValueError:
                                            pass  # do nothing

                                self.handle_wrong_notes(wrong_notes, hand_hint_notesL, hand_hint_notesR)
                                wrong_notes.clear()

                                # light up predicted future notes again in case the future note was pressed
                                # and color was overwritten
                                self.predict_future_notes(absolute_idx, end_idx, notes_to_press)
                            
                            hand_hint_notesL = []
                            hand_hint_notesR = []
                            # Play any pending software notes only after all required notes have been pressed
                            if set(notes_to_press).issubset(notes_pressed) and self.pending_software_notes:
                                for software_note in self.pending_software_notes:
                                    self.midiports.playport.send(software_note)
                                self.pending_software_notes.clear()

                            # Turn off the pressed LEDs
                            fastColorWipe(self.ledstrip.strip, True,
                                          self.ledsettings)  # ideally clear only pressed notes!
                            notes_to_press.clear()

                    # Realize time delay, consider also the time lost during computation
                    delay = max(0, tDelay - (
                            time.time() - time_prev) - 0.003)  # 0.003 sec calibratable to account for extra time loss
                    time.sleep(delay)
                    time_prev = time.time()

                    # Light-up LEDs with the notes to press
                    if not msg.is_meta:
                        # Calculate note position on the strip and display
                        if msg.type == 'note_on' or msg.type == 'note_off':
                            note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                            if msg.velocity == 0:
                                brightness = 0
                            else:
                                brightness = 0.5

                            red, green, blue = [0, 0, 0]
                            if msg.channel == 1:
                                red, green, blue = [int(c * brightness) for c in self.hand_colorList[self.hand_colorR]]
                                if self.is_led_activeR == 0:
                                    if brightness > 0:
                                        hand_hint_notesR.append(note_position)
                                    else:
                                        try:
                                            hand_hint_notesR.remove(note_position)
                                        except ValueError:
                                            pass  # do nothing
                            if msg.channel == 2:
                                red, green, blue = [int(c * brightness) for c in self.hand_colorList[self.hand_colorL]]
                                if self.is_led_activeL == 0:
                                    if brightness > 0:
                                        hand_hint_notesL.append(note_position)
                                    else:
                                        try:
                                            hand_hint_notesL.remove(note_position)
                                        except ValueError:
                                            pass  # do nothing
                            self.ledstrip.strip.setPixelColor(note_position, Color(red, green, blue))
                            self.ledstrip.strip.show()
                        # Save notes to press
                        if msg.type == 'note_on' and msg.velocity > 0 and (
                                msg.channel == self.hands or self.hands == 0):
                            notes_to_press.append(msg.note)

                        # Handle software's notes
                        if ((
                                self.hands == 1 and self.mute_hand != 2 and msg.channel == 2) or
                                # Left hand notes
                                (
                                        self.hands == 2 and self.mute_hand != 1 and msg.channel == 1) or
                                # Right hand notes
                                self.practice == 2):  # Listen mode
                            if self.practice == 2:
                                # In Listen mode, play immediately
                                self.midiports.playport.send(msg)
                            else:
                                # Check if there are any user notes to press at this moment
                                if notes_to_press:
                                    # If there are user notes to press, store this software note to play when user presses their key
                                    self.pending_software_notes.append(msg)
                                else:
                                    # If no user notes to press, play the software note immediately
                                    self.midiports.playport.send(msg)

                    absolute_idx += 1

                    # If we have pending software notes but no user notes to press,
                    # and we've reached the next note's time, play and clear the pending notes
                    if (self.pending_software_notes and not notes_to_press and
                            self.next_note_time and time.time() >= self.next_note_time):
                        for software_note in self.pending_software_notes:
                            self.midiports.playport.send(software_note)
                        self.pending_software_notes.clear()
                        self.next_note_time = None
                        self.next_note_delay = None

                    if self.awaiting_restart_loop:
                        self.awaiting_restart_loop = False
                        break


            except Exception as e:
                logger.warning(e)
                self.is_started_midi = False

            if not self.is_loop_active or self.is_started_midi is False:
                keep_looping = False

            # Update profile highscore
            try:
                profile_id = getattr(app_state, 'current_profile_id', None)
                # Only update if a profile is selected and we know the song name
                if profile_id and hasattr(self, 'current_song_name') and self.current_song_name:
                    # new_score is the final session score
                    new_score = int(self.score_manager.get_score())
                    # Use ProfileManager directly if available
                    pm = getattr(app_state, 'profile_manager', None)
                    if pm:
                        updated = pm.update_highscore(int(profile_id), self.current_song_name, new_score)
                        if updated:
                            # Notify UI via websocket to update the highscore cell dynamically
                            self.socket_send.append(json.dumps({
                                "type": "highscore_update",
                                "song_name": self.current_song_name,
                                "score": new_score,
                                "profile_id": int(profile_id)
                            }))
            except Exception as e:
                logger.warning(f"Failed to update highscore: {e}")

            # Send session summary data
            if not keep_looping:
                try:
                    # Get actual RGB colors
                    color_r_rgb = self.hand_colorList[self.hand_colorR]
                    color_l_rgb = self.hand_colorList[self.hand_colorL]

                    summary_data = {
                        "type": "session_summary",
                        # Basic stats
                        "delay_r": self.delay_countR,
                        "delay_l": self.delay_countL,
                        "mistakes_r_count": len(self.right_hand_mistakes),
                        "mistakes_l_count": len(self.left_hand_mistakes),
                        # Data for graph
                        "timing_r": self.right_hand_timing,
                        "timing_l": self.left_hand_timing,
                        "mistakes_r_times": self.right_hand_mistakes,
                        "mistakes_l_times": self.left_hand_mistakes,
                        "max_delay": self.score_manager.max_delay,
                        "color_r": f'rgb({color_r_rgb[0]}, {color_r_rgb[1]}, {color_r_rgb[2]})',
                        "color_l": f'rgb({color_l_rgb[0]}, {color_l_rgb[1]}, {color_l_rgb[2]})'
                    }
                    self.socket_send.append(json.dumps(summary_data))
                    score_logger.info(f"Sent session summary (length: {len(json.dumps(summary_data))})") # Log length for debugging if needed
                except Exception as e:
                    score_logger.error(f"Error preparing/sending session summary: {e}")

    def convert_midi_to_abc(self, midi_file):
        if not os.path.isfile('Songs/' + midi_file.replace(".mid", ".abc")):
            # subprocess.call(['midi2abc',  'Songs/' + midi_file, '-o', 'Songs/' + midi_file.replace(".mid", ".abc")])
            try:
                subprocess.check_output(
                    ['midi2abc', 'Songs/' + midi_file, '-o', 'Songs/' + midi_file.replace(".mid", ".abc")])
            except Exception as e:
                # check if e contains the string 'No such file or directory'
                if 'No such file or directory' in str(e):
                    logger.info("midi2abc not found")
        else:
            logger.info("file already converted")
