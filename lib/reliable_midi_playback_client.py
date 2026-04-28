import json
import socket
import struct
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import mido


PROTOCOL_VERSION = 1
DEFAULT_RELIABLE_MIDI_HOST = "oscmidi-rtp.local"
DEFAULT_RELIABLE_MIDI_PORT = 5056
DEFAULT_START_DELAY_MS = 500
MAX_FRAME_BYTES = 64 * 1024 * 1024


class ReliablePlaybackError(RuntimeError):
    pass


@dataclass
class CompiledMidiPlayback:
    events: list
    local_messages: list
    total_delay_s: float

    @property
    def total(self):
        return len(self.events)


class ReliablePlaybackHandle:
    def __init__(self, sock, session_id, start_perf):
        self.sock = sock
        self.session_id = session_id
        self.start_perf = start_perf
        self._closed = False

    def wait_completed(self, timeout=None):
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            response = _recv_frame(self.sock)
            if response.get("type") != "completed":
                raise ReliablePlaybackError(f"Unexpected reliable playback response: {response!r}")
            if response.get("sessionId") != self.session_id:
                raise ReliablePlaybackError("Reliable playback completed response has wrong session id")
            return response
        finally:
            self.close()

    def stop(self):
        if self._closed:
            return
        try:
            _send_frame(self.sock, {"type": "stop", "sessionId": self.session_id})
        except OSError:
            pass
        self.close()

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.sock.close()
        except OSError:
            pass


class ReliableMidiPlaybackClient:
    def __init__(self, host=DEFAULT_RELIABLE_MIDI_HOST, port=DEFAULT_RELIABLE_MIDI_PORT, timeout=5.0):
        self.host = host or DEFAULT_RELIABLE_MIDI_HOST
        self.port = int(port or DEFAULT_RELIABLE_MIDI_PORT)
        self.timeout = float(timeout)

    @classmethod
    def from_settings(cls, usersettings):
        if usersettings is None:
            return cls()
        host = usersettings.get_setting_value("reliable_midi_host") or DEFAULT_RELIABLE_MIDI_HOST
        port = usersettings.get_setting_value("reliable_midi_port") or DEFAULT_RELIABLE_MIDI_PORT
        return cls(host=host, port=port)

    def play_events(self, song, compiled, start_delay_ms=DEFAULT_START_DELAY_MS):
        session_id = uuid.uuid4().hex
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        try:
            _send_frame(
                sock,
                {
                    "type": "prepare",
                    "version": PROTOCOL_VERSION,
                    "sessionId": session_id,
                    "song": song,
                    "total": compiled.total,
                    "events": compiled.events,
                },
            )
            response = _recv_frame(sock)
            if response.get("type") != "prepared":
                raise ReliablePlaybackError(f"Unexpected reliable playback response: {response!r}")
            if response.get("sessionId") != session_id:
                raise ReliablePlaybackError("Reliable playback prepared response has wrong session id")
            if int(response.get("received", -1)) != compiled.total:
                raise ReliablePlaybackError(
                    f"Reliable playback prepared {response.get('received')} events, expected {compiled.total}"
                )

            _send_frame(
                sock,
                {
                    "type": "start",
                    "sessionId": session_id,
                    "startDelayMs": int(start_delay_ms),
                },
            )
            return ReliablePlaybackHandle(
                sock,
                session_id,
                time.perf_counter() + (int(start_delay_ms) / 1000.0),
            )
        except Exception:
            try:
                sock.close()
            except OSError:
                pass
            raise


def compile_midi_file(path):
    return compile_midi_messages(mido.MidiFile(str(Path(path))))


def compile_midi_messages(mid):
    total_delay = 0.0
    events = []
    local_messages = []
    seq = 0
    for message in mid:
        total_delay += float(getattr(message, "time", 0.0) or 0.0)
        if getattr(message, "is_meta", False):
            continue
        data = list(message.bytes())
        if not data:
            continue
        due_us = int(round(total_delay * 1_000_000))
        events.append({"seq": seq, "dueUs": due_us, "data": data})
        local_messages.append((due_us, message.copy(time=0)))
        seq += 1
    return CompiledMidiPlayback(events=events, local_messages=local_messages, total_delay_s=total_delay)


def _send_frame(sock, payload):
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sock.sendall(struct.pack(">I", len(data)))
    sock.sendall(data)


def _recv_frame(sock):
    header = _recv_exact(sock, 4)
    if not header:
        raise ReliablePlaybackError("Reliable playback connection closed")
    size = struct.unpack(">I", header)[0]
    if size > MAX_FRAME_BYTES:
        raise ReliablePlaybackError(f"Reliable playback frame too large: {size}")
    return json.loads(_recv_exact(sock, size).decode("utf-8"))


def _recv_exact(sock, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ReliablePlaybackError("Reliable playback connection closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
