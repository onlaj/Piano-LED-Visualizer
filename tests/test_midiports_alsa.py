#!/usr/bin/env python3
"""Closes real ALSA MIDI inputs while their callback is still running.

Closing an rtmidi input joins its ALSA thread while holding the GIL. If a
callback is in flight at that moment it can never take the GIL back, and
the whole process hangs (LEDs and web interface freeze). A hang cannot be
caught inside the test process, so each scenario runs in a subprocess with
a timeout.

Needs the ALSA sequencer (/dev/snd/seq) and python-rtmidi; skipped
otherwise.
"""

import os
import subprocess
import sys
import textwrap
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TIMEOUT = 15

SETUP = """
import os
import sys
import threading
import time
sys.path.insert(0, {root!r})
import mido
from lib.midiports import MidiPorts, _close_input_safely, _refresh_port_cache, _get_cached_input_names

entered = threading.Event()


def slow_callback(msg, *args):
    entered.set()
    time.sleep(0.01)  # still in flight when close() is called


source_name = "plv-test-source-" + str(os.getpid())
source = mido.open_output(source_name, virtual=True)
_refresh_port_cache()
port_name = [name for name in _get_cached_input_names() if source_name in name][0]


def wait_for_callback(port_out):
    entered.clear()
    port_out.send(mido.Message("note_on", note=60, velocity=10))
    if not entered.wait(5):
        print("callback never ran")
        sys.exit(2)
"""


def alsa_available():
    if not os.path.exists("/dev/snd/seq"):
        return False
    try:
        import mido
        port = mido.open_output("plv-test-probe-{}".format(os.getpid()), virtual=True)
        port.close()
        return True
    except Exception:
        return False


@unittest.skipUnless(alsa_available(), "ALSA sequencer and python-rtmidi required")
class TestCloseInputWithCallbackInFlight(unittest.TestCase):
    def run_scenario(self, body):
        script = textwrap.dedent(SETUP).format(root=ROOT) + textwrap.dedent(body)
        try:
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            self.fail("process hung while closing a MIDI input with a callback in flight")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("closed", result.stdout)

    def test_close_input_safely(self):
        self.run_scenario("""
            port_in = mido.open_input(port_name, callback=slow_callback)
            time.sleep(0.1)
            wait_for_callback(source)
            _close_input_safely(port_in)
            source.close()
            print("closed")
        """)

    def test_close_input_safely_while_messages_keep_arriving(self):
        self.run_scenario("""
            stop = threading.Event()

            def send_notes():
                while not stop.is_set():
                    source.send(mido.Message("note_on", note=60, velocity=10))
                    time.sleep(0.001)

            sender = threading.Thread(target=send_notes, daemon=True)
            sender.start()
            for _ in range(20):
                port_in = mido.open_input(port_name, callback=slow_callback)
                entered.clear()
                if not entered.wait(5):
                    print("callback never ran")
                    sys.exit(2)
                _close_input_safely(port_in)
            stop.set()
            sender.join()
            source.close()
            print("closed")
        """)

    def test_piano_input_reopen(self):
        self.run_scenario("""
            class Settings:
                def get_setting_value(self, name):
                    return port_name

            midiports = MidiPorts.__new__(MidiPorts)
            midiports.usersettings = Settings()
            midiports.piano_in = None
            midiports.piano_in_name = None
            midiports.inport = None
            midiports.route_midi_message = slow_callback

            for _ in range(5):
                assert midiports._open_piano_input(port_name, sync_settings=False)
                time.sleep(0.1)
                wait_for_callback(source)
            _close_input_safely(midiports.piano_in)
            source.close()
            print("closed")
        """)


if __name__ == "__main__":
    unittest.main()
