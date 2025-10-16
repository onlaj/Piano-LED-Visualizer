#!/usr/bin/python3
import subprocess
import sys
import os
from xml.etree import ElementTree as ET


def connectall(usersettings=None):
    """
    Connect input and secondary input ports if they are both set and not 'default'.
    If usersettings is provided, use it. Otherwise, read settings from config file.
    """
    # Get settings
    if usersettings is not None:
        input_port = usersettings.get_setting_value("input_port")
        secondary_input_port = usersettings.get_setting_value("secondary_input_port")
    else:
        # Read settings from config file directly
        # Try multiple possible locations for the settings file
        settings_paths = [
            "config/settings.xml",  # When called from app directory
            "/home/Piano-LED-Visualizer/config/settings.xml",  # When called from system
            "/opt/Piano-LED-Visualizer/config/settings.xml",  # Alternative system path
        ]
        
        settings_found = False
        for settings_path in settings_paths:
            try:
                if os.path.exists(settings_path):
                    tree = ET.parse(settings_path)
                    root = tree.getroot()
                    input_port = root.find("./input_port").text if root.find("./input_port") is not None else "default"
                    secondary_input_port = root.find("./secondary_input_port").text if root.find("./secondary_input_port") is not None else "default"
                    settings_found = True
                    print(f"Using settings from: {settings_path}")
                    break
            except:
                continue
        
        if not settings_found:
            print("Error reading settings file from any location, using defaults")
            input_port = "default"
            secondary_input_port = "default"
    
    # Check if both ports are set and not default
    if input_port == "default" or secondary_input_port == "default":
        print("Input port or secondary input port not set, skipping connection")
        return
    
    if input_port == secondary_input_port:
        print("Input and secondary input ports are the same, skipping connection")
        return
    
    # Get available ports
    ports = subprocess.check_output(["aconnect", "-i", "-l"], text=True)
    port_list = []
    client = "0"
    for line in str(ports).splitlines():
        if line.startswith("client "):
            client = line[7:].split(":", 2)[0]
            if client == "0" or "Through" in line:
                client = "0"
        else:
            if client == "0" or line.startswith('\t'):
                continue
            port = line.split()[0]
            port_list.append(client + ":" + port)
    
    # Find the actual port IDs for the configured ports
    input_port_id = None
    secondary_input_port_id = None
    
    # Extract the port ID from the configured port names
    # Format: "client_name:port_name client_id:port_id"
    try:
        input_port_id = input_port.split()[-1]  # Get the last part (client_id:port_id)
        secondary_input_port_id = secondary_input_port.split()[-1]  # Get the last part (client_id:port_id)
    except:
        print("Error parsing configured port names")
        return
    
    # Verify the ports exist in the available port list
    if input_port_id not in port_list:
        print(f"Input port ID '{input_port_id}' not found in available ports")
        input_port_id = None
    
    if secondary_input_port_id not in port_list:
        print(f"Secondary input port ID '{secondary_input_port_id}' not found in available ports")
        secondary_input_port_id = None
    
    # Connect the ports if both are found
    if input_port_id and secondary_input_port_id:
        print(f"Disconnecting all existing MIDI connections...")
        # First disconnect all existing connections
        subprocess.call("aconnect -x", shell=True)
        
        print(f"Connecting {input_port} ({input_port_id}) to {secondary_input_port} ({secondary_input_port_id})")
        # Two-way connection: input -> secondary and secondary -> input
        result1 = subprocess.call(f"aconnect {input_port_id} {secondary_input_port_id}", shell=True)
        result2 = subprocess.call(f"aconnect {secondary_input_port_id} {input_port_id}", shell=True)

        # Get available output ports
        out_ports = subprocess.check_output(["aconnect", "-o"], text=True)
        rt_midi_in_port = None
        for line in str(out_ports).splitlines():
            if line.startswith("client "):
                client = line[7:].split(":", 2)[0]
            elif "RtMidi input" in line:
                rt_midi_in_port = client + ":" + line.split()[0]  # Get the client_id:port_id
                print("Found RtMidi input port:", rt_midi_in_port)
                break
        
        if rt_midi_in_port:
            result3 = subprocess.call(f"aconnect {input_port_id} {rt_midi_in_port}", shell=True)
            result4 = subprocess.call(f"aconnect {secondary_input_port_id} {rt_midi_in_port}", shell=True)
        else:
            result3 = 0
            result4 = 0

        if result1 == 0 and result2 == 0 and result3 == 0 and result4 == 0:
            print("Connection established successfully")
        else:
            print("Warning: Some connections may have failed")
    else:
        print(f"Could not find ports: input_port='{input_port}', secondary_input_port='{secondary_input_port}'")
        if not input_port_id:
            print(f"Input port '{input_port}' not found")
        if not secondary_input_port_id:
            print(f"Secondary input port '{secondary_input_port}' not found")


if __name__ == '__main__':
    connectall()
