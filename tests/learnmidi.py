##########################################################################
#
# INFO:
# - The purpose of this file is to test or improve the implementation
#   for learn MIDI functionality in visualizer.py.
# - This file can be run both on PC or within the Raspberry Pi Zero
#
# Author: Emanuel Feru
# Year:   2021
#
##########################################################################

import mido
import time

# Get midi song tempo
def get_tempo(mid):
    for msg in mid:     # Search for tempo
        if msg.type == 'set_tempo':
            return msg.tempo
    return 500000       # If not found return default tempo

# Open port
outport = mido.open_output()
print(outport)

# Load midi file
# mid = mido.MidiFile('Songs/'+'La Campanella.mid')
mid = mido.MidiFile('Songs/'+'Everything_I_do.mid')
# mid = mido.MidiFile('Songs/'+'Right_Here_Waiting.mid')
print("TYPE: " + str(mid.type))
print("LENGTH: " + str(mid.length))
print("TICKS PER BEAT: " + str(mid.ticks_per_beat))

class LearnMIDI:
    def __init__(self):
        self.loading            = 0
        self.practice           = 0
        self.hands              = 0
        self.mute_hand          = 0
        self.start_point        = 0
        self.set_tempo          = 100
        self.hand_colorR        = 0
        self.hand_colorL        = 1

        self.loadingList        = ['', 'Load..', 'Proces', 'Merge', 'Done', 'Error!']
        self.learningList       = ['Start', 'Stop']
        self.practiceList       = ['Melody', 'Rhythm', 'Listen']
        self.handsList          = ['Both', 'Right', 'Left']
        self.mute_handList      = ['Off', 'Right', 'Left']

        self.song_tempo         = 500000
        self.song_tracks        = []
        self.ticks_per_beat     = 240
        self.is_loaded_midi     = {}
        self.is_started_midi    = False
        self.t                  = 0

# Assign Tracks to different channels before merging to know the message origin
if len(mid.tracks) == 2:    # check if the midi file has only 2 Tracks
    offset = 1
else:
    offset = 0
for k in range(len(mid.tracks)):
    for msg in mid.tracks[k]:
        if not msg.is_meta:
            msg.channel = k + offset
            if (msg.type == 'note_off'):
                msg.velocity = 0

learning = LearnMIDI()

# Merge tracks 
learning.song_tracks  = mido.merge_tracks(mid.tracks)

# Get tempo
learning.song_tempo     =  get_tempo(mid)
learning.ticks_per_beat = mid.ticks_per_beat


# Input
learning.practice       = 0
learning.hands          = 0
learning.mute_handList  = 0
learning.set_tempo      = 100

led_R = []
led_L = []
notes_to_press = []
for msg in learning.song_tracks:

    # Get time delay
    tDelay = mido.tick2second(msg.time, learning.ticks_per_beat, learning.song_tempo * 100 / learning.set_tempo)

    # Check notes to press
    if not msg.is_meta:
        if (tDelay > 0 and (msg.type == 'note_on' or msg.type == 'note_off') and notes_to_press and learning.practice == 0):
            print("led_R:" + str(led_R))
            print("led_L:" + str(led_L))
            
            # Mimic notes to press with a key input
            print("Notes to press: ", notes_to_press)
            input()

            # Turn off the pressed LEDs
            notes_to_press.clear()
            # fastColorWipe(ledstrip.strip, True)

    # Realize time delay
    time.sleep(tDelay)

    if not msg.is_meta:
        # Calculate note position on the strip and display
        if (msg.type == 'note_on' or msg.type == 'note_off'):
            # note_position = get_note_position(msg.note)
            if (msg.channel == 1):
                if (msg.velocity == 0):
                    try:
                        led_R.remove(msg.note)
                    except ValueError:
                        pass
                else:
                    if (msg.note not in led_R):
                        led_R.append(msg.note)
                # red     = int(learning.hand_colorList[learning.hand_colorR][0] * msg.velocity / 127)
                # green   = int(learning.hand_colorList[learning.hand_colorR][1] * msg.velocity / 127)
                # blue    = int(learning.hand_colorList[learning.hand_colorR][2] * msg.velocity / 127)
            if (msg.channel == 2):
                if (msg.velocity == 0):
                    try:
                        led_L.remove(msg.note)
                    except ValueError:
                        pass
                else:
                    if (msg.note not in led_L):
                        led_L.append(msg.note)
                # red     = int(learning.hand_colorList[learning.hand_colorL][0] * msg.velocity / 127)
                # green   = int(learning.hand_colorList[learning.hand_colorL][1] * msg.velocity / 127)
                # blue    = int(learning.hand_colorList[learning.hand_colorL][2] * msg.velocity / 127)
            # ledstrip.strip.setPixelColor(note_position, Color(green, red, blue))
            # ledstrip.strip.show()

        # Save notes to press
        if (msg.type == 'note_on' and msg.velocity > 0 and (msg.channel == learning.hands or learning.hands == 0)):
            notes_to_press.append(msg.note)

        # Play selected Track
        if ((learning.hands == 1 and learning.mute_hand != 2 and msg.channel == 2) or   # send midi sound for Left hand
            (learning.hands == 2 and learning.mute_hand != 1 and msg.channel == 1) or   # send midi sound for Right hand
            learning.practice == 2):                                                    # send midi sound for Listen only
            outport.send(msg)
            print(msg)




