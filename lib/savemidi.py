import time

from mido import MidiFile, MidiTrack, Message


class SaveMIDI:
    def __init__(self):
        self.isrecording = False
        self.is_playing_midi = {}
        self.start_time = time.time()

    def add_instance(self, menu):
        self.menu = menu


    def start_recording(self):
        self.isrecording = True
        self.menu.render_message("Recording started", "", 500)
        self.messages_to_save = dict()
        self.messages_to_save["main"] = []
        self.restart_time()
        self.first_note_time = 0

    def cancel_recording(self):
        self.isrecording = False
        self.menu.render_message("Recording canceled", "", 1500)

    def add_track(self, status, note, velocity, time_value, hex_color="main"):
        if self.first_note_time == 0:
            self.first_note_time = time_value

        if hex_color not in self.messages_to_save:
            self.messages_to_save[str(hex_color)] = []
            self.messages_to_save[str(hex_color)].append(["note", self.first_note_time, "note_off", 0, 0])

        if status == "note_off":
            for key, note_off_message in self.messages_to_save.items():
                self.messages_to_save[key].append(["note", time_value, status, note, velocity])
        else:
            self.messages_to_save[str(hex_color)].append(["note", time_value, status, note, velocity])
            if str(hex_color) != "main":
                self.messages_to_save["main"].append(["note", time_value, status, note, velocity])

    def add_control_change(self, status, channel, control, value, time_value):
        self.messages_to_save["main"].append(["control_change", time_value, status, channel, control, value])

    def save(self, filename):
        for key, multicolor_track in self.messages_to_save.items():
            self.mid = MidiFile(None, None, 0, 20000)  # 20000 is a ticks_per_beat value
            self.track = MidiTrack()
            self.mid.tracks.append(self.track)
            for message in multicolor_track:
                try:
                    time_delay = message[1] - previous_message_time
                except:
                    time_delay = 0
                previous_message_time = message[1]
                if time_delay < 0:
                    time_delay = 0
                if message[0] == "note":
                    self.track.append(Message(message[2], note=int(message[3]), velocity=int(message[4]),
                                              time=int(time_delay * 40000)))
                else:
                    self.track.append(
                        Message(message[2], channel=int(message[3]), control=int(message[4]), value=int(message[5]),
                                time=int(time_delay * 40000)))
                self.last_note_time = message[1]

            self.mid.save('Songs/' + filename + '_' + str(key) + '.mid')

        self.messages_to_save = []
        self.isrecording = False
        self.menu.render_message("File saved", filename + ".mid", 1500)

    def restart_time(self):
        self.start_time = time.time()