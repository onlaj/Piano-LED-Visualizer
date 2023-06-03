import threading
import mido
import time


class CasioPiano:
    def __init__(self, midiports, menuLCD):
        self.midiports = midiports
        self.midicmd_instrument = bytearray.fromhex('f0 44 7e 7e 7f 0f 01 10 10 01 02 01 00 02 00 00 00 00 f7')
        self.midicmd_hall = bytearray.fromhex('f0 44 7e 7e 7f 0f 01 52 00 01 02 01 00 04 00 00 00 00 f7')
        self.midicmd_touch_response = bytearray.fromhex('f0 44 7e 7e 7f 0f 01 02 00 01 02 01 00 05 00 00 00 00 f7')
        self.touch_response_str = ["off", "lt2", "lt1", "nrm", "hv1", "hv2"]
        self.midicmd_traspose_pos = bytearray.fromhex('f0 44 7e 7e 7f 0f 01 03 00 01 02 01 00 01 00 00 00 00 f7')
        self.midicmd_traspose_neg = bytearray.fromhex('f0 44 7e 7e 7f 0f 01 03 00 01 02 01 00 7d 7f 7f 7f 0f f7')
        self.midicmd_metronome_rate = bytearray.fromhex('f0 44 7e 7e 7f 0f 01 0a 00 01 02 01 00 11 00 00 00 00 f7')
        self.midicmd_metronome_beat_type = bytearray.fromhex('f0 44 7e 7e 7f 0f 01 0b 01 01 02 01 00 11 00 00 00 00 f7')
        self.midicmd_metronome_volume = bytearray.fromhex('f0 44 7e 7e 7f 0f 01 0b 03 01 02 01 00 11 00 00 00 00 f7')
        self.midicmd_metronome_onOff = bytearray.fromhex('f0 44 7e 7e 7f 0f 01 0b 00 01 00 01 00 66 00 f7')
        self.midicmd_query_metronome_rate = bytearray.fromhex('f0 44 7e 7e 7f 0f 00 0a 00 01 02 01 00 11 00 00 00 00 f7')
        self.midicmd_query_metronome_beat_type = bytearray.fromhex('f0 44 7e 7e 7f 0f 00 0b 01 01 02 01 00 11 00 00 00 00 f7')
        self.midicmd_query_metronome_volume = bytearray.fromhex('f0 44 7e 7e 7f 0f 00 0b 03 01 02 01 00 11 00 00 00 00 f7')
        self.midicmd_query_metronome_onOff = bytearray.fromhex('f0 44 7e 7e 7f 0f 00 0b 00 01 00 01 00 01 00 f7')
        self.metronome_tempo = 20
        self.metronome_volume = 20
        self.metronome_beat_type = -1
        self.hall_type = 0
        self.traspose = 0
        self.instrument = 0
        self.metronome_active = 0
        self.queryTimer = None
        self.query_piano_changes()
        self.updateMenu = None
        self.menuLCD = menuLCD
        self.touch_response = 3

    def query_piano_changes(self):
        # Send MIDI commands to query the piano for changes
        self.send_midi(self.midicmd_query_metronome_onOff)
        self.send_midi(self.midicmd_query_metronome_beat_type)
        self.send_midi(self.midicmd_query_metronome_volume)
        self.send_midi(self.midicmd_query_metronome_rate)
        self.queryTimer = None

    def update_menu(self):
        if self.updateMenu is not None:
            # If a timer is active, cancel it and reset the timer
            self.updateMenu.cancel()
        self.updateMenu = threading.Timer(0.25, self.update_menu_now)
        self.updateMenu.start()

    def update_menu_now(self):
        self.menuLCD.show()
        self.updateMenu = None

    def process_midi(self, msg):
        # "sysex data=(68,126,126,127,15,1,8,0,1,0,1,0,2,0) time=0"
        if msg.type == 'sysex':
            strmsg = str(msg.data)
            if strmsg.startswith('(68, 126, 126, 127, 15, 1,'):
                if strmsg == '(68, 126, 126, 127, 15, 1, 8, 0, 1, 0, 1, 0, 2, 0)':
                    if self.queryTimer is not None:
                        # If a timer is active, cancel it
                        self.queryTimer.cancel()
                    # Start a new timer for 500 milliseconds
                    self.queryTimer = threading.Timer(0.25, self.query_piano_changes)
                    self.queryTimer.start()
                elif strmsg.startswith('(68, 126, 126, 127, 15, 1, 11, 0, 1, 0, 1, 0,'):
                    self.metronome_active = msg.data[12] == 1
                    if not self.metronome_active:
                        self.metronome_beat_type = -1
                    self.update_menu()
                elif strmsg.startswith('(68, 126, 126, 127, 15, 1, 10, 0, 1, 2, 1, 0,'):
                    self.metronome_tempo = msg.data[12]
                    if msg.data[13] == 1:
                        self.metronome_tempo = self.metronome_tempo + 128
                    self.update_menu()
                elif strmsg.startswith('(68, 126, 126, 127, 15, 1, 11, 3, 1, 2, 1, 0,'):
                    self.metronome_volume = msg.data[12]
                elif strmsg.startswith('(68, 126, 126, 127, 15, 1, 11, 1, 1, 2, 1, 0,'):
                    if self.metronome_active:
                        self.metronome_beat_type = msg.data[12]
                    else:
                        self.metronome_beat_type = -1
                    self.update_menu()
                # else:
                 #   print("Unknown : ",str(msg.data))
        if msg.type == 'program_change' and hasattr(msg, "program"):
            # print("Change instrument to "+str(msg.program))
            self.instrument = msg.program
            self.update_menu()

    def send_midi(self, data):
        msg = mido.Message.from_bytes(data)
        self.midiports.playport.send(msg)

    def set_instrument(self, instrument):
        self.instrument = instrument
        self.midicmd_instrument[13] = instrument
        self.send_midi(self.midicmd_instrument)

    def set_touch_response(self, touch_response):
        self.touch_response = touch_response
        self.midicmd_touch_response[13] = touch_response
        self.send_midi(self.midicmd_touch_response)

    def set_hall_type(self, hall_type):
        self.midicmd_hall[13] = hall_type
        self.hall_type = hall_type
        self.send_midi(self.midicmd_hall)

    def set_metronome_tempo(self, value):
        self.metronome_tempo = int(value)
        self.send_metronome_data()

    def set_metronome_volume(self, value):
        self.metronome_volume = int(value)
        self.send_metronome_data()

    def set_metronome_beat_type(self, value):
        self.metronome_beat_type = int(value)
        self.send_metronome_data()

    def set_metronome_active(self, value):
        self.midicmd_metronome_onOff[13] = 1 if value else 0
        self.send_midi(self.midicmd_metronome_onOff)

    def send_metronome_data(self):
        if self.metronome_tempo < 10:
            self.metronome_tempo = 10
        if self.metronome_tempo > 240:
            self.metronome_tempo = 240
        if self.metronome_volume < 2:
            self.metronome_volume = 2
        if self.metronome_volume > 42:
            self.metronome_volume = 42
        if self.metronome_beat_type < -1:
            self.metronome_beat_type = -1
        if self.metronome_beat_type > 10:
            self.metronome_beat_type = 10
        self.midicmd_metronome_rate[14] = 0
        if self.metronome_tempo > 127:
            self.midicmd_metronome_rate[14] = 1
        self.midicmd_metronome_rate[13] = self.metronome_tempo % 128
        self.midicmd_metronome_volume[13] = self.metronome_volume
        if self.metronome_beat_type < 0:
            self.set_metronome_active(False)
        else:
            self.set_metronome_active(True)
            self.midicmd_metronome_beat_type[13] = self.metronome_beat_type
            self.send_midi(self.midicmd_metronome_beat_type)
        self.send_midi(self.midicmd_metronome_rate)
        self.send_midi(self.midicmd_metronome_volume)

    def modify_metronome_tempo(self, delta):
        self.metronome_tempo = int(self.metronome_tempo) + delta
        self.send_metronome_data()

    def modify_metronome_volume(self, delta):
        self.metronome_volume = int(self.metronome_volume) + delta
        self.send_metronome_data()

    def modify_beat_type(self, delta):
        self.metronome_beat_type = int(self.metronome_beat_type) + delta
        self.send_metronome_data()

    def modify_touch_response(self, delta):
        self.touch_response = int(self.touch_response) + delta
        if self.touch_response < 0:
            self.touch_response = 0
        if self.touch_response >= len(self.touch_response_str):
            self.touch_response = len(self.touch_response_str)-1
        self.set_touch_response(self.touch_response)

    def set_traspose(self, traspose):
        self.traspose = traspose
        if self.traspose < -12:
            self.traspose = -12
        if self.traspose > 12:
            self.traspose = 12

        if self.traspose >= 0:
            self.midicmd_traspose_pos[13] = self.traspose
            self.send_midi(self.midicmd_traspose_pos)
        else:
            self.midicmd_traspose_neg[13] = 128 + self.traspose
            self.send_midi(self.midicmd_traspose_neg)

    def modify_traspose(self, delta):
        self.traspose = self.traspose + delta
        self.set_traspose(self.traspose)

    def metronome_beat_type_string(self):
        if self.metronome_beat_type < 0:
            return "OFF"
        elif self.metronome_beat_type == 0:
            return "click"
        elif self.metronome_beat_type == 1:
            return "bell"
        elif self.metronome_beat_type == 2:
            return "b/cl"
        else:
            return "b/"+str(self.metronome_beat_type-1)+"cl"
