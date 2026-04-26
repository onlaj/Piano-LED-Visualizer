#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path


def run(command):
    print(f"\n$ {command}")
    completed = subprocess.run(
        command,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = completed.stdout.strip()
    if output:
        print(output)
    print(f"[exit {completed.returncode}]")


def read(path):
    try:
        return Path(path).read_text(errors="replace").strip()
    except OSError:
        return None


def main():
    print("=== Piano LED Visualizer USB MIDI diagnostics ===")
    model = read("/proc/device-tree/model")
    if model:
        print(f"model: {model.replace(chr(0), '')}")
    run("uname -a")
    run("lsusb")
    run("lsusb -t")

    print("\n=== /sys/bus/usb/devices ===")
    for device in sorted(Path("/sys/bus/usb/devices").glob("*")):
        if not device.exists():
            continue
        values = {}
        for name in (
            "busnum",
            "devnum",
            "idVendor",
            "idProduct",
            "manufacturer",
            "product",
            "serial",
            "speed",
            "authorized",
            "bDeviceClass",
        ):
            value = read(device / name)
            if value is not None:
                values[name] = value
        print(f"- {device.name}: {values or 'interface/no descriptor'}")

    run("ls -la /dev/snd 2>/dev/null || true")
    run("cat /proc/asound/cards 2>/dev/null || true")
    run("aconnect -i -l || true")
    run("amidi -l || true")
    run("lsmod | egrep 'snd_usb_audio|snd_usbmidi_lib|snd_rawmidi|snd_seq|usbhid|dwc' || true")

    try:
        import mido

        print("\n=== mido ===")
        print(f"inputs: {mido.get_input_names()}")
        print(f"outputs: {mido.get_output_names()}")
    except Exception as exc:
        print(f"\n=== mido unavailable/error ===\n{exc}")

    run(
        "dmesg --ctime 2>/dev/null | "
        "egrep -i 'usb|dwc|midi|snd|audio|over-current|overcurrent|under-voltage|voltage|device descriptor|enumerat' | "
        "tail -80"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
