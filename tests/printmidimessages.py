import mido
from mido import MidiFile, Message, tempo2bpm, MidiTrack,MetaMessage

ports = mido.get_input_names()
ports_list = []
i = 1
print("List of ports: \n")
for port in ports:
	ports_list.append(port)
	print(str(i)+". "+str(port))
	i += 1
user_input = input('\n Choose port by typing corresponding number \n')
inport = mido.open_input(ports_list[int(user_input) - 1])

while True:
	for msg in inport.iter_pending():
		print(msg)
