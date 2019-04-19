import mido
from mido import MidiFile, Message, tempo2bpm, MidiTrack,MetaMessage

mido.get_output_names()

inport =  mido.open_input('mio:mio MIDI 1 20:0')

while True:
	for msg in inport.iter_pending():
		print(msg)
