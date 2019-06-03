import mido
from mido import MidiFile, Message, tempo2bpm, MidiTrack,MetaMessage

ports = mido.get_input_names()

for port in ports:
	if "Through" not in port and "RPi" not in port and "RtMidOut" not in port:
		try:
			inport =  mido.open_input(port)
			print("Inport set to "+port)
		except:
			print ("Failed to set "+port+" as inport")

while True:
	for msg in inport.iter_pending():
		print(msg)
