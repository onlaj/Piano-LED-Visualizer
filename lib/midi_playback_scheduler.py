import threading
import time
from enum import Enum

import mido

from lib.functions import clear_ledstrip_state, fastColorWipe
from lib.log_setup import logger
from lib.reliable_midi_playback_client import (
    DEFAULT_START_DELAY_MS,
    ReliableMidiPlaybackClient,
    ReliablePlaybackError,
    compile_midi_messages,
)


class PlaybackState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class MidiPlaybackScheduler:
    def __init__(self, midiports, saving, menu, ledsettings, ledstrip, reliable_client_factory=None):
        self.midiports = midiports
        self.saving = saving
        self.menu = menu
        self.ledsettings = ledsettings
        self.ledstrip = ledstrip
        self.state = PlaybackState.STOPPED
        self.current_song = None
        self.stop_event = threading.Event()
        self._lock = threading.RLock()
        self.reliable_client_factory = reliable_client_factory or ReliableMidiPlaybackClient.from_settings
        self._reliable_handle = None

    @property
    def is_playing(self):
        return self.state == PlaybackState.RUNNING

    def stop(self):
        handle = None
        with self._lock:
            was_active = self.state in (PlaybackState.RUNNING, PlaybackState.STOPPING)
            if self.state == PlaybackState.RUNNING:
                self.state = PlaybackState.STOPPING
            self.stop_event.set()
            self.saving.is_playing_midi.clear()
            self._clear_scheduled_forward(source="midifile")
            self._clear_file_queue()
            handle = self._reliable_handle
            self._reliable_handle = None
            self.current_song = None

        if handle is not None:
            handle.stop()

        self._send_playback_panic()

        with self._lock:
            if not was_active:
                self.stop_event.clear()
                self.state = PlaybackState.STOPPED
            logger.info("midi_playback transition=stopped")

    def play(self, song_path):
        with self._lock:
            if self.state in (PlaybackState.RUNNING, PlaybackState.STOPPING):
                if self.menu is not None:
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
            compiled = compile_midi_messages(mid)
            return self._play_reliable(song_path, compiled)
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
                self._reliable_handle = None
                self.saving.is_playing_midi.clear()
                self.current_song = None
                self.stop_event.clear()
                if self.state != PlaybackState.ERROR:
                    self.state = PlaybackState.STOPPED

    def _play_reliable(self, song_path, compiled):
        try:
            client = self.reliable_client_factory(self._usersettings())
            handle = client.play_events(song_path, compiled, start_delay_ms=DEFAULT_START_DELAY_MS)
            with self._lock:
                if self.stop_event.is_set() or self.state != PlaybackState.RUNNING:
                    handle.stop()
                    return False
                self._reliable_handle = handle
        except Exception as e:
            if not isinstance(e, ReliablePlaybackError):
                e = ReliablePlaybackError(str(e))
            logger.warning(f"Reliable MIDI playback unavailable: {e}")
            with self._lock:
                if self.stop_event.is_set():
                    return False
                self.state = PlaybackState.ERROR
            if self.menu is not None:
                self.menu.render_message(song_path, "Reliable MIDI unavailable", 2000)
            return False

        t0 = handle.start_perf
        self._play_local_events(song_path, compiled, t0)
        if self.stop_event.is_set():
            handle.stop()
            with self._lock:
                if self._reliable_handle is handle:
                    self._reliable_handle = None
            return False

        completion_timeout = max(5.0, compiled.total_delay_s + 5.0)
        try:
            completed = handle.wait_completed(timeout=completion_timeout)
        except Exception:
            with self._lock:
                if self._reliable_handle is handle:
                    self._reliable_handle = None
            if self.stop_event.is_set():
                return False
            raise
        with self._lock:
            if self._reliable_handle is handle:
                self._reliable_handle = None
        processed = int(completed.get("processed", -1))
        dropped = int(completed.get("dropped", -1))
        if processed != compiled.total or dropped != 0:
            with self._lock:
                self.state = PlaybackState.ERROR
            logger.warning(
                "Reliable MIDI playback incomplete: processed=%s expected=%s dropped=%s",
                processed,
                compiled.total,
                dropped,
            )
            return False
        logger.info(
            "reliable_midi_playback complete song=%s processed=%s max_late_us=%s",
            song_path,
            processed,
            completed.get("maxLateUs"),
        )
        return True

    def _play_local_events(self, song_path, compiled, start_perf):
        index = 0
        local_messages = compiled.local_messages
        while index < len(local_messages):
            if self.stop_event.is_set():
                logger.info("midi_playback transition=stopping song=%s", song_path)
                break
            due_us = local_messages[index][0]
            due_time = start_perf + (due_us / 1_000_000.0)
            delay = max(0.0, due_time - time.perf_counter())
            if delay > 0:
                if self.stop_event.wait(delay):
                    logger.info("midi_playback transition=stopping song=%s", song_path)
                    break
            if self.stop_event.is_set():
                logger.info("midi_playback transition=stopping song=%s", song_path)
                break

            while index < len(local_messages) and local_messages[index][0] == due_us:
                _, message = local_messages[index]
                if self.stop_event.is_set():
                    break
                if self.midiports.should_process_locally(message):
                    self._enqueue_file_message(message.copy(time=0), due_time)
                index += 1

    def _usersettings(self):
        return getattr(self.midiports, "usersettings", None)

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
