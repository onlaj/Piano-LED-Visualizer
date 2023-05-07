from lib.functions import midi_note_num_to_string
import mido

#
# def midi_note_num_to_string(note_midi_idx):
#    # Calculate the octave and note number
#    octave = (note_midi_idx // 12) - 1
#    note_num = note_midi_idx % 12
#
#    # Map the note number to a note letter and accidental
#    notes = {0: 'C', 1: 'C#', 2: 'D', 3: 'Eb', 4: 'E', 5: 'F',
#             6: 'F#', 7: 'G', 8: 'G#', 9: 'A', 10: 'Bb', 11: 'B'}
#    return f"{notes[note_num]}{octave}"
#

# notes within this distance are considered part of same chord
THRESHOLD_CHORD_NOTE_DISTANCE = 0.05
DEBUG_MARKERS = False


class MusicSplitter:

    _gaps_array: list[dict[str, dict[int, float]]]

    def __init__(self, midi_messages, notes_time):
        self.midi_messages = midi_messages
        self.notes_time = notes_time

    def calculate_measure_and_split_data(self, ticks_per_beat, song_tempo):
        self.measure_data = self.calculate_measure_data(ticks_per_beat)
        self._gaps_array = self.calculate_note_gaps(self.notes_time)
        self.split_data = self.do_split(song_tempo, ticks_per_beat)

    def find_note_with_same_time(self, notes_to_press, idx):
        channel = self.midi_messages[idx].channel
        for note in notes_to_press:
            for i in range(len(notes_to_press[note])):
                note_index = notes_to_press[note][i]["idx"]
                # ipdb.set_trace()
                if idx != note_index and notes_to_press[note][i]["channel"] == channel and abs(self.notes_time[note_index] - self.notes_time[idx]) < THRESHOLD_CHORD_NOTE_DISTANCE:
                    return self.notes_time[note_index]
        return None

    def get_next_chord(self, index, channel=None):
        time_next_chord = None
        notes = []
        for i in range(index + 1, index + 50):
            if i >= len(self.midi_messages):
                break
            if time_next_chord is not None and self.notes_time[i] - time_next_chord > THRESHOLD_CHORD_NOTE_DISTANCE:
                break
            if self.midi_messages[i].type == "note_on" and (channel is None or self.midi_messages[i].channel == channel) and self.midi_messages[i].velocity > 0:
                if time_next_chord is None:
                    time_next_chord = self.notes_time[i]
                notes.append(i)
        return notes

    def get_highest_chord_note_in_channel(self, channel, index):
        indices = self.get_next_chord(index, channel)
        notes = [self.midi_messages[i].note for i in indices]
        return max(notes) if notes else None

    def get_lowest_chord_note_in_channel(self, channel, index):
        indices = self.get_next_chord(index, channel)
        notes = [self.midi_messages[i].note for i in indices]
        return min(notes) if notes else None

    def calculate_scope_data(self, notes_to_press):
        last_index = None
        this_scope_data = ScopeData()
        # Initialize arrays to hold the lowest and highest notes for channels 0 and 1
        lowest_note_channel = [-1, -1]
        highest_note_channel = [-1, -1]

        # Loop over each note in the dictionary
        for note_number, note_data in notes_to_press.items():
            channel = note_data[0]["channel"]  # Get the channel for the note
            if last_index is None or note_data[0]["idx"] > last_index:
                last_index = note_data[0]["idx"]
            if channel == 0 or channel == 1:
                # If the channel is 0 or 1, update the highest and lowest notes for that channel
                if lowest_note_channel[channel] == -1 or note_number < lowest_note_channel[channel]:
                    lowest_note_channel[channel] = note_number
                if highest_note_channel[channel] == -1 or note_number > highest_note_channel[channel]:
                    highest_note_channel[channel] = note_number

        if highest_note_channel[1] is None:
            higherChannel = 0
            gap_between_channels = 100
        elif highest_note_channel[0] is None:
            higherChannel = 1
            gap_between_channels = 100
        else:
            higherChannel = 1 if highest_note_channel[1] > highest_note_channel[0] else 0
            gap_between_channels = lowest_note_channel[higherChannel] - \
                highest_note_channel[1-higherChannel]
        for channel in range(2):
            next_note = self.get_lowest_chord_note_in_channel(channel, last_index)
            if (lowest_note_channel[channel] != -1
                    and (next_note is None or next_note >= lowest_note_channel[channel])):
                if DEBUG_MARKERS:
                    print("Next note in channel "+str(channel)+" is " +
                          midi_note_num_to_string(next_note))
                    print("   which is higher than the lowest shown note " +
                          midi_note_num_to_string(lowest_note_channel[channel]))
                if higherChannel != channel or gap_between_channels > 5:
                    this_scope_data.channel[channel].low.led_count = 3
                    this_scope_data.channel[channel].low.note = lowest_note_channel[channel]
                elif gap_between_channels > 1:
                    this_scope_data.channel[channel].low.led_count = 1
                    this_scope_data.channel[channel].low.note = lowest_note_channel[channel]
            next_note = self.get_highest_chord_note_in_channel(channel, last_index)
            if (highest_note_channel[channel] != -1
                    and (next_note is None or next_note <= highest_note_channel[channel])):
                if DEBUG_MARKERS:
                    print("Next note in channel "+str(channel)+" is " +
                          midi_note_num_to_string(next_note))
                    print("   which is lower than the highest shown note " +
                          midi_note_num_to_string(highest_note_channel[channel]))
                if higherChannel == channel or gap_between_channels > 5:
                    this_scope_data.channel[channel].high.led_count = 3
                    this_scope_data.channel[channel].high.note = highest_note_channel[channel]
                elif gap_between_channels > 1:
                    this_scope_data.channel[channel].high.led_count = 1
                    this_scope_data.channel[channel].high.note = highest_note_channel[channel]
        return this_scope_data

    def do_split(self, song_tempo, ticks_per_beat):
        accDelay = 0
        tDelay = 0
        msg_index = 0
        notes_to_press = {}
        accumulated_chord = None
        split_data: dict[int, ScopeData] = {}

        for msg in self.midi_messages:
            # Get time delay
            tDelay = mido.tick2second(msg.time, ticks_per_beat, song_tempo)

            accDelay += tDelay

            if not msg.is_meta:
                # Save notes to press
                if msg.type == 'note_on' and msg.velocity > 0:
                    if not notes_to_press:
                        accDelay = 0    # start calculating from now how much time we accumulated
                    if msg.note not in notes_to_press:
                        notes_to_press[msg.note] = [
                            {"idx": msg_index, "channel": msg.channel}]
                    else:
                        notes_to_press[msg.note].append(
                            {"idx": msg_index, "channel": msg.channel})
                    if self.find_note_with_same_time(notes_to_press, msg_index) and accumulated_chord is None:
                        accumulated_chord = self.notes_time[msg_index]

            # Check notes to press
            if not msg.is_meta:
                if msg.channel in (0, 1):
                    current_hand = msg.channel
                    other_hand = 1 - msg.channel

                    gaps = self._gaps_array[msg_index]
                    wait_for_user = False
                    if accDelay >= 0.37:
                        wait_for_user = True
                    elif ((gaps['time_to_next'][current_hand] is None or gaps['time_to_next'][current_hand] > 0.12)
                          and (gaps['time_to_next'][other_hand] is None
                               or (gaps['time_to_next'][other_hand] > 0.05 and gaps['time_to_next'][other_hand] + gaps['time_to_prev'][other_hand] > 0.12))
                          ):
                        wait_for_user = True
                    elif (accumulated_chord is not None and accumulated_chord < self.notes_time[msg_index]
                          and (gaps['time_to_next'][0] is None or gaps['time_to_next'][0] > 0.02)
                          and (gaps['time_to_next'][1] is None or gaps['time_to_next'][1] > 0.02)):
                        chord0 = self.get_next_chord(msg_index, 0)
                        chord1 = self.get_next_chord(msg_index, 1)
                        if chord0 is None:
                            first_chord = chord1
                        elif chord1 is None:
                            first_chord = chord0
                        else:
                            first_chord = chord0 if self.notes_time[chord0[0]] < self.notes_time[chord1[0]] else chord1
                        if first_chord is not None and len(first_chord) > 1:
                            wait_for_user = True

                    if (wait_for_user
                            and msg.type in ['note_on', 'note_off']
                            and notes_to_press
                            and not still_notes_in_chord(self.midi_messages, msg_index)):
                        split_data[msg_index] = self.calculate_scope_data(notes_to_press)
                        notes_to_press.clear()
                        accumulated_chord = None
                        accDelay = 0

            msg_index += 1
        return split_data

    def calculate_measure_data(self, ticks_per_beat):
        measure_data = []
        time_signature = None
        current_ticks = 0
        current_ticks_in_measure = 0

        tweak_measure_offset = 0
        measure_start = 0
        measure_length = None

        # 1. Calculate in which tick measures start taking MeasureOffset tweak into account
        for i, msg in enumerate(self.midi_messages):
            if hasattr(msg, "time"):
                current_ticks += msg.time
                current_ticks_in_measure += msg.time

            if msg.is_meta and msg.type == "text" and msg.text.startswith("MeasureOffset="):
                tweak_measure_offset = int(msg.text[len("MeasureOffset="):])

            if msg.is_meta and msg.type == 'time_signature':
                time_signature = float(msg.numerator/msg.denominator)
                measure_length = int(4 * time_signature * ticks_per_beat)
                measure_data.append(
                    {'start': current_ticks + tweak_measure_offset})
                current_ticks_in_measure = 0
                measure_start = current_ticks

            if measure_length is not None:
                while current_ticks_in_measure > measure_length:
                    current_ticks_in_measure -= measure_length
                    measure_start += measure_length
                    measure_data.append(
                        {'start': measure_start + tweak_measure_offset})

        # 2. Calculate in which note measures start. Snap to measure is taken into account here
        tweak_snap_to_measure = 5
        measure_pointer = 1
        current_ticks = 0
        measure_data[0]['note_index'] = 0

        for i, msg in enumerate(self.midi_messages):
            if hasattr(msg, "time"):
                current_ticks += msg.time
            if msg.is_meta and msg.type == "text" and msg.text.startswith("SnapToMeasure="):
                tweak_snap_to_measure = int(msg.text[len("SnapToMeasure="):])

            if msg.type == "note_on" and msg.velocity > 0:   # snap
                while (measure_pointer < len(measure_data)
                        and current_ticks >= measure_data[measure_pointer]["start"] - tweak_snap_to_measure):
                    measure_data[measure_pointer]['note_index'] = i
                    measure_pointer += 1
        return measure_data

    def calculate_note_gaps(self, notes_time):
        # fill prev and next time gaps
        prev_note_on = {}
        curr_prev_note_on = {i: -1 for i in range(2)}

        for i, msg in enumerate(self.midi_messages):
            prev_note_on[i] = curr_prev_note_on.copy()
            if msg.type == 'note_on':
                channel = msg.channel
                if msg.velocity > 0:
                    curr_prev_note_on[channel] = i

        next_note_on = {}
        curr_next_note_on = {i: -1 for i in range(2)}
        for i in range(len(self.midi_messages)-1, -1, -1):
            msg = self.midi_messages[i]
            next_note_on[i] = curr_next_note_on.copy()
            if msg.type == 'note_on':
                channel = msg.channel
                if msg.velocity > 0:
                    curr_next_note_on[channel] = i

        gaps_array: list[dict[str, dict[int, float]]] = [
            {
                'time_to_prev': {i: float('inf') for i in range(2)},
                'time_to_next': {i: float('inf') for i in range(2)}
            } for i in range(len(self.midi_messages))
        ]

        for i, msg in enumerate(self.midi_messages):
            if i in prev_note_on:
                if i not in next_note_on:
                    raise Exception("SANITY CHECK ERROR _ test")
                for c in prev_note_on[i]:
                    if prev_note_on[i][c] is not None:
                        gaps_array[i]['time_to_prev'][c] = notes_time[i] - \
                            notes_time[prev_note_on[i][c]]
                    else:
                        gaps_array[i]['time_to_prev'][c] = float('inf')
                    if next_note_on[i][c] is not None:
                        gaps_array[i]['time_to_next'][c] = notes_time[next_note_on[i]
                                                                      [c]] - notes_time[i]
                    else:
                        gaps_array[i]['time_to_next'][c] = float('inf')
        return gaps_array


def still_notes_in_chord(midi_messages, start_idx):
    for idx in range(start_idx + 1, start_idx + 100):
        if idx >= len(midi_messages):
            return False
        msg = midi_messages[idx]
        if hasattr(msg, "time") and msg.time > 0:
            return False
        if msg.type in ('note_on', 'note_off') and msg.velocity > 0:
            return True
    return False


class ScopeData:
    def __init__(self):
        self.channel = [ScopeDataPerChannel(), ScopeDataPerChannel()]

    def isEmpty(self):
        return self.channel[0].isEmpty() and self.channel[1].isEmpty()


class ScopeDataPerChannel:
    def __init__(self):
        self.low = ScopeDataPerDirection()
        self.high = ScopeDataPerDirection()

    def isEmpty(self):
        return self.low.led_count == 0 and self.high.led_count == 0


class ScopeDataPerDirection:
    led_count: int = 0
    note: int = 0


def get_tempo(mid):
    for msg in mid:  # Search for tempo
        if msg.type == 'set_tempo':
            return msg.tempo
    return 500000  # If not found return default tempo


def test():
    mid = mido.MidiFile('E:\\albeniz_cuba_notturno.mid')

    # Get tempo and Ticks per beat
    song_tempo = get_tempo(mid)
    ticks_per_beat = mid.ticks_per_beat

    for k in range(len(mid.tracks)):
        for msg in mid.tracks[k]:
            if not msg.is_meta:
                if len(mid.tracks) == 2:
                    msg.channel = k
                else:
                    if msg.channel in (0, 1, 2, 3, 4, 5):
                        msg.channel = msg.channel % 2
                    if mid.tracks[k].name == 'LH':
                        msg.channel = 0
                    if mid.tracks[k].name == 'RH':
                        msg.channel = 1
                if msg.type == 'note_off':
                    msg.velocity = 0

    # Merge tracks
    time_passed = 0
    notes_on = set()
    ignore_note_idx = set()
    note_idx = 0
    unfiltered_song_tracks = mido.merge_tracks(mid.tracks)
    unfiltered_notes_time = []

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

    notes_time = []
    song_tracks = []
    for i in range(len(unfiltered_song_tracks)):
        if not i in ignore_note_idx:
            song_tracks.append(unfiltered_song_tracks[i])
            notes_time.append(unfiltered_notes_time[i])

    music_splitter = MusicSplitter(ticks_per_beat, song_tracks, notes_time, song_tempo)
