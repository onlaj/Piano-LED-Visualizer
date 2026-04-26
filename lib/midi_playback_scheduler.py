import threading
import time
from enum import Enum

import mido

from lib.functions import clear_ledstrip_state, fastColorWipe
from lib.log_setup import logger


class PlaybackState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class MidiPlaybackScheduler:
    def __init__(self, midiports, saving, menu, ledsettings, ledstrip):
        self.midiports = midiports
        self.saving = saving
        self.menu = menu
        self.ledsettings = ledsettings
        self.ledstrip = ledstrip
        self.state = PlaybackState.STOPPED
        self.current_song = None
        self.stop_event = threading.Event()
        self._lock = threading.RLock()

    @property
    def is_playing(self):
        return self.state == PlaybackState.RUNNING

    def stop(self):
        with self._lock:
            if self.state == PlaybackState.RUNNING:
                self.state = PlaybackState.STOPPING
            self.stop_event.set()
            self.saving.is_playing_midi.clear()
            self._clear_scheduled_forward(source="midifile")
            self._clear_file_queue()
            self._send_playback_panic()
            self.state = PlaybackState.STOPPED
            self.current_song = None
            logger.info("midi_playback transition=stopped")

    def play(self, song_path):
        with self._lock:
            if self.state == PlaybackState.RUNNING:
                self.menu.render_message(song_path, "Already playing", 2000)
                return False
            self.state = PlaybackState.RUNNING
            self.current_song = song_path
            self.stop_event.clear()
            self.saving.is_playing_midi.clear()
            self.saving.is_playing_midi[song_path] = True
            logger.info("midi_playback transition=running song=%s", song_path)

        if self.menu is not None:
            self.menu.render_message("Playing: ", song_path, 2000)
        if self.ledstrip is not None and self.ledsettings is not None:
            fastColorWipe(self.ledstrip.strip, True, self.ledsettings)

        try:
            mid = mido.MidiFile("Songs/" + song_path)
            t0 = None
            total_delay = 0
            for message in mid:
                if self.stop_event.is_set():
                    logger.info("midi_playback transition=stopping song=%s", song_path)
                    break
                if t0 is None:
                    t0 = time.perf_counter()

                total_delay += message.time
                msg_timestamp = t0 + total_delay
                if not getattr(message, "is_meta", False):
                    self.midiports.schedule_rtp_message(message, due_time=msg_timestamp, source="midifile")

                delay = max(0.0, msg_timestamp - time.perf_counter())
                if delay > 0:
                    time.sleep(delay)

                if not getattr(message, "is_meta", False) and self.midiports.should_process_locally(message):
                    self._enqueue_file_message(message.copy(time=0), msg_timestamp)

            if t0 is not None:
                logger.info("play time: {:.2f} s (expected {:.2f})".format(time.perf_counter() - t0, total_delay))
            return True
        except FileNotFoundError:
            self.state = PlaybackState.ERROR
            if self.menu is not None:
                self.menu.render_message(song_path, "File not found", 2000)
            return False
        except Exception as e:
            self.state = PlaybackState.ERROR
            if self.menu is not None:
                self.menu.render_message(song_path, "Error while playing song " + str(e), 2000)
            logger.warning(e)
            return False
        finally:
            self._clear_file_queue()
            if self.ledstrip is not None:
                try:
                    clear_ledstrip_state(self.ledstrip)
                except Exception as e:
                    logger.debug(f"LED cleanup failed: {e}")
            with self._lock:
                self.saving.is_playing_midi.clear()
                self.current_song = None
                self.stop_event.clear()
                if self.state != PlaybackState.ERROR:
                    self.state = PlaybackState.STOPPED

    def _enqueue_file_message(self, msg, timestamp):
        if hasattr(self.midiports, "enqueue_file_message"):
            self.midiports.enqueue_file_message(msg, timestamp)
            return
        if hasattr(self.midiports, "queues"):
            self.midiports.queues.enqueue_file(msg, timestamp=timestamp)
        else:
            self.midiports.midifile_queue.append((msg, timestamp))

    def _clear_file_queue(self):
        if hasattr(self.midiports, "queues"):
            self.midiports.queues.clear_file()
        else:
            self.midiports.midifile_queue.clear()

    def _clear_scheduled_forward(self, source=None):
        if hasattr(self.midiports, "clear_scheduled_rtp_messages"):
            self.midiports.clear_scheduled_rtp_messages(source=source)
        elif hasattr(self.midiports, "queues"):
            self.midiports.queues.clear_scheduled_forward(source=source)

    def _send_playback_panic(self):
        if hasattr(self.midiports, "send_all_notes_off"):
            try:
                self.midiports.send_all_notes_off()
            except Exception as e:
                logger.debug(f"MIDI panic send failed: {e}")
