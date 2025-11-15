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
            print("ERROR: Could not read settings file from any location, using defaults")
            input_port = "default"
            secondary_input_port = "default"
    
    # Check if both ports are set and not default
    if input_port == "default" or secondary_input_port == "default":
        print("INFO: Input port or secondary input port not set, skipping connection")
        return
    
    if input_port == secondary_input_port:
        print("INFO: Input and secondary input ports are the same, skipping connection")
        return
    
    # Get available ports
    ports = subprocess.check_output(["aconnect", "-i", "-l"], text=True)
    port_list = []
    client = "0"
    for line in str(ports).splitlines():
        if line.startswith("client "):
            client = line[7:].split(":", 2)[0]
            if client == "0" or "Through" in line or "RtMidi" in line:
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
        print("ERROR: Failed to parse configured port names")
        return
    
    # Verify the ports exist in the available port list
    if input_port_id not in port_list:
        print(f"ERROR: Input port ID '{input_port_id}' not found in available ports")
        input_port_id = None
    
    if secondary_input_port_id not in port_list:
        print(f"ERROR: Secondary input port ID '{secondary_input_port_id}' not found in available ports")
        secondary_input_port_id = None
    
    # Connect the ports if both are found
    if input_port_id and secondary_input_port_id:
        # Check if the desired connection already exists before doing anything
        aconnect_output = subprocess.check_output(["aconnect", "-l"], text=True)
        connection_exists = _check_connection_exists(aconnect_output, input_port_id, secondary_input_port_id)
        
        if connection_exists:
            print(f"SUCCESS: Connection between {input_port} and {secondary_input_port} already exists, skipping")
        else:
            print(f"INFO: Attempting to connect {input_port} ({input_port_id}) to {secondary_input_port} ({secondary_input_port_id})")
            # Two-way connection: input -> secondary and secondary -> input
            result1 = subprocess.run(f"aconnect {input_port_id} {secondary_input_port_id}", shell=True, capture_output=True, text=True)
            result2 = subprocess.run(f"aconnect {secondary_input_port_id} {input_port_id}", shell=True, capture_output=True, text=True)
            
            # Check results and provide detailed feedback
            success1 = result1.returncode == 0 or "Connection is already subscribed" in result1.stderr
            success2 = result2.returncode == 0 or "Connection is already subscribed" in result2.stderr
            
            if success1 and success2:
                if result1.returncode == 0 and result2.returncode == 0:
                    print("SUCCESS: Connection established successfully")
                else:
                    print("SUCCESS: Connection already exists (both directions)")
            else:
                # Report specific failures
                if not success1:
                    print(f"ERROR: Failed to connect {input_port_id} -> {secondary_input_port_id}: {result1.stderr.strip()}")
                if not success2:
                    print(f"ERROR: Failed to connect {secondary_input_port_id} -> {input_port_id}: {result2.stderr.strip()}")
                print("WARNING: Some connections may have failed")
    else:
        print(f"ERROR: Could not find ports: input_port='{input_port}', secondary_input_port='{secondary_input_port}'")
        if not input_port_id:
            print(f"ERROR: Input port '{input_port}' not found")
        if not secondary_input_port_id:
            print(f"ERROR: Secondary input port '{secondary_input_port}' not found")


def _check_connection_exists(aconnect_output, input_port_id, secondary_input_port_id):
    """Check if the desired two-way connection already exists"""
    try:
        lines = aconnect_output.splitlines()
        input_to_secondary = False
        secondary_to_input = False
        
        for line in lines:
            # Look for "Connecting To:" lines that contain both port IDs
            if "Connecting To:" in line:
                if input_port_id in line and secondary_input_port_id in line:
                    # This line shows a connection between our two ports
                    input_to_secondary = True
                    secondary_to_input = True
                    break
            # Also check for "Connected From:" lines for completeness
            elif "Connected From:" in line:
                if input_port_id in line and secondary_input_port_id in line:
                    input_to_secondary = True
                    secondary_to_input = True
                    break
        
        return input_to_secondary and secondary_to_input
        
    except Exception as e:
        print(f"ERROR: Failed to check connection existence: {e}")
        return False


if __name__ == '__main__':
    connectall()
