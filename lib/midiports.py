import threading
import time
from collections import deque

import mido

from lib import connectall
from lib.log_setup import logger
from lib.midiport_resolver import (
    PortResolutionStatus,
    descriptive_port_name,
    pick_default_input_port,
    pick_default_output_port,
    port_is_present,
    refresh_runtime_port_name,
    resolve_input_port,
    resolve_output_port,
)

# Cache for MIDI port names to avoid repeated slow scans
_cached_input_names = None
_cached_output_names = None
_cache_lock = threading.Lock()


def _get_cached_input_names():
    """Get input port names, using cache if available."""
    global _cached_input_names
    with _cache_lock:
        if _cached_input_names is None:
            try:
                _cached_input_names = mido.get_input_names()
            except Exception as e:
                logger.warning(f"Failed to get input names: {e}")
                _cached_input_names = []
        return _cached_input_names.copy()


def _get_cached_output_names():
    """Get output port names, using cache if available."""
    global _cached_output_names
    with _cache_lock:
        if _cached_output_names is None:
            try:
                _cached_output_names = mido.get_output_names()
            except Exception as e:
                logger.warning(f"Failed to get output names: {e}")
                _cached_output_names = []
        return _cached_output_names.copy()


def _refresh_port_cache():
    """Refresh the cached port names."""
    global _cached_input_names, _cached_output_names
    with _cache_lock:
        try:
            _cached_input_names = mido.get_input_names()
        except Exception as e:
            logger.warning(f"Failed to refresh input names: {e}")
            _cached_input_names = []
        try:
            _cached_output_names = mido.get_output_names()
        except Exception as e:
            logger.warning(f"Failed to refresh output names: {e}")
            _cached_output_names = []


class MidiPorts:
    def __init__(self, usersettings):
        self.usersettings = usersettings

        # midi queues contain tuples (midi_msg, timestamp)
        self.midifile_queue = deque(maxlen=500)
        self.midi_queue = deque(maxlen=1000)
        self.websocket_midi_queue = deque(maxlen=1000)
        self.live_forward_queue = deque(maxlen=2048)
        self.websocket_publish_queue = deque(maxlen=512)

        self.queue_reserved_noteoff_slots = max(1, min(32, self.midi_queue.maxlen // 8))
        self.drop_counter = 0
        self.drop_counts = {}
        self.ignored_counts = {}
        self.forward_stats = {
            "live_sent": 0,
            "live_send_errors": 0,
            "websocket_sent": 0,
            "websocket_dropped": 0,
            "send_time_total_ms": 0.0,
            "send_time_max_ms": 0.0,
        }

        self.last_activity = 0
        self.inport = None
        self.playport = None
        self.actual_input_port = None
        self.actual_play_port = None
        self.last_resolved_input_port = None
        self.last_resolved_play_port = None
        self.last_resolution_reason = {}
        self.last_reconnect_time = None
        self.reconnect_count = 0
        self.midipending = None
        self.midi_monitor_thread = None
        self.monitor_running = False
        self.worker_running = False
        self.live_forward_thread = None
        self.websocket_publish_thread = None
        self.ignored_message_types = {"clock", "active_sensing"}

        # Known python-rtmidi first-access quirk on some systems.
        try:
            _get_cached_input_names()
        except Exception:
            logger.warning(
                "First access to mido failed. Possibly from known issue: "
                "https://github.com/SpotlightKid/python-rtmidi/issues/138"
            )

        self.setup_ports()
        self.start_background_workers()
        self.portname = "inport"

    def _increment_drop(self, key):
        self.drop_counter += 1
        self.drop_counts[key] = self.drop_counts.get(key, 0) + 1

    def _increment_ignored(self, key):
        self.ignored_counts[key] = self.ignored_counts.get(key, 0) + 1

    def _classify_message(self, msg):
        msg_type = getattr(msg, "type", None)
        if msg_type == "note_off":
            return "note_off"
        if msg_type == "note_on":
            if getattr(msg, "velocity", 0) == 0:
                return "note_off"
            return "note_on"
        if msg_type == "control_change":
            return "control_change"
        return "other"

    def _queue_with_policy(self, queue, item, source, reserve_slots=0):
        msg = item[0] if isinstance(item, tuple) else item
        event_type = self._classify_message(msg)
        soft_limit = queue.maxlen - reserve_slots if queue.maxlen else None

        if queue.maxlen:
            if event_type == "note_off":
                if len(queue) >= queue.maxlen:
                    self._increment_drop(f"{source}_{event_type}")
                    return False
            elif soft_limit is not None and len(queue) >= max(0, soft_limit):
                key = f"{source}_{event_type if event_type == 'note_on' else 'noncritical'}"
                self._increment_drop(key)
                return False

        queue.append(item)
        return True

    def _should_ignore_live_message(self, msg):
        return getattr(msg, "type", None) in self.ignored_message_types

    def _format_websocket_midi_message(self, msg):
        msg_type = getattr(msg, "type", "")
        if msg_type not in ("note_on", "note_off"):
            return None
        channel = getattr(msg, "channel", 0)
        note = getattr(msg, "note", 0)
        velocity = getattr(msg, "velocity", 0)
        time_val = getattr(msg, "time", 0)
        return f"midi_event{msg_type} channel={channel} note={note} velocity={velocity} time={time_val}"

    def _flush_live_forward_queue_once(self):
        if not self.live_forward_queue:
            return False

        msg, _ = self.live_forward_queue.popleft()
        port = self.playport
        if port is None:
            return False

        send_started = time.perf_counter()
        try:
            port.send(msg)
            elapsed_ms = (time.perf_counter() - send_started) * 1000.0
            self.forward_stats["live_sent"] += 1
            self.forward_stats["send_time_total_ms"] += elapsed_ms
            if elapsed_ms > self.forward_stats["send_time_max_ms"]:
                self.forward_stats["send_time_max_ms"] = elapsed_ms
            return True
        except Exception as e:
            self.forward_stats["live_send_errors"] += 1
            logger.debug(f"Skipping playport send: {e}")
            return False

    def _flush_websocket_publish_queue_once(self):
        if not self.websocket_publish_queue:
            return False

        msg, _ = self.websocket_publish_queue.popleft()
        try:
            from webinterface import app_state, webinterface

            if not getattr(app_state, "practice_active", False):
                return False

            midi_string = self._format_websocket_midi_message(msg)
            if midi_string is None:
                return False

            if len(webinterface.websocket_midi_send) >= webinterface.websocket_midi_send.maxlen:
                self.forward_stats["websocket_dropped"] += 1
                return False

            webinterface.websocket_midi_send.append(midi_string)
            self.forward_stats["websocket_sent"] += 1
            return True
        except Exception:
            return False

    def _live_forward_loop(self):
        while self.worker_running:
            if not self._flush_live_forward_queue_once():
                time.sleep(0.001)

    def _websocket_publish_loop(self):
        while self.worker_running:
            if not self._flush_websocket_publish_queue_once():
                time.sleep(0.01)

    def start_background_workers(self):
        if self.worker_running:
            return

        self.worker_running = True
        self.live_forward_thread = threading.Thread(target=self._live_forward_loop, daemon=True)
        self.websocket_publish_thread = threading.Thread(target=self._websocket_publish_loop, daemon=True)
        self.live_forward_thread.start()
        self.websocket_publish_thread.start()

    def _safe_close_port(self, port_handle):
        if port_handle is None:
            return
        try:
            port_handle.close()
        except Exception:
            pass

    def _resolve_input_target(self, requested_port, available_inputs):
        if requested_port and requested_port != "default":
            resolution = resolve_input_port(requested_port, available_inputs)
            self.last_resolved_input_port = resolution.selected_port
            self.last_resolution_reason["input"] = resolution.reason
            return resolution

        selected = pick_default_input_port(available_inputs)
        self.last_resolved_input_port = selected
        self.last_resolution_reason["input"] = "Auto-selected first safe input port"
        return {
            "selected_port": selected,
            "status": PortResolutionStatus.AUTO_SELECTED,
            "reason": self.last_resolution_reason["input"],
        }

    def _resolve_output_target(self, requested_port, available_outputs):
        if requested_port and requested_port != "default":
            resolution = resolve_output_port(requested_port, available_outputs)
            self.last_resolved_play_port = resolution.selected_port
            self.last_resolution_reason["play"] = resolution.reason
            return resolution

        selected = pick_default_output_port(available_outputs)
        self.last_resolved_play_port = selected
        self.last_resolution_reason["play"] = "Auto-selected first safe output port"
        return {
            "selected_port": selected,
            "status": PortResolutionStatus.AUTO_SELECTED,
            "reason": self.last_resolution_reason["play"],
        }

    def _resolve_selected_port(self, resolution):
        if isinstance(resolution, dict):
            return resolution["selected_port"]
        return resolution.selected_port

    def _should_keep_current_port(self, requested_port, actual_port, port_handle, available_ports, selected_port, force):
        if force or port_handle is None or actual_port is None:
            return False
        if not port_is_present(actual_port, available_ports):
            return False
        if requested_port and requested_port != "default":
            return selected_port == actual_port
        return selected_port == actual_port

    def _refresh_runtime_port_labels(self, available_inputs=None, available_outputs=None):
        if available_inputs is None:
            available_inputs = _get_cached_input_names()
        if available_outputs is None:
            available_outputs = _get_cached_output_names()

        self.actual_input_port = refresh_runtime_port_name(self.actual_input_port, available_inputs)
        self.actual_play_port = refresh_runtime_port_name(self.actual_play_port, available_outputs)

    def _reconnect_input(self, force=False):
        available_inputs = _get_cached_input_names()
        self._refresh_runtime_port_labels(available_inputs=available_inputs, available_outputs=_get_cached_output_names())
        requested_port = self.usersettings.get_setting_value("input_port")
        resolution = self._resolve_input_target(requested_port, available_inputs)
        selected_port = self._resolve_selected_port(resolution)

        if self._should_keep_current_port(
            requested_port,
            self.actual_input_port,
            self.inport,
            available_inputs,
            selected_port,
            force,
        ):
            return False

        old_port = self.inport
        self.inport = None
        self.actual_input_port = None

        if selected_port is None:
            self._safe_close_port(old_port)
            return old_port is not None

        try:
            self.inport = mido.open_input(selected_port, callback=self.msg_callback)
            self.actual_input_port = selected_port
            logger.info("Input port active: %s", selected_port)
        except Exception as e:
            logger.info("Can't load input port '%s': %s", selected_port, e)
            self.inport = None
            self.actual_input_port = None

        self._safe_close_port(old_port)
        return True

    def _reconnect_output(self, force=False):
        available_outputs = _get_cached_output_names()
        self._refresh_runtime_port_labels(available_inputs=_get_cached_input_names(), available_outputs=available_outputs)
        requested_port = self.usersettings.get_setting_value("play_port")
        resolution = self._resolve_output_target(requested_port, available_outputs)
        selected_port = self._resolve_selected_port(resolution)

        if self._should_keep_current_port(
            requested_port,
            self.actual_play_port,
            self.playport,
            available_outputs,
            selected_port,
            force,
        ):
            return False

        old_port = self.playport
        self.playport = None
        self.actual_play_port = None

        if selected_port is None:
            self._safe_close_port(old_port)
            return old_port is not None

        try:
            self.playport = mido.open_output(selected_port)
            self.actual_play_port = selected_port
            logger.info("Play port active: %s", selected_port)
        except Exception as e:
            logger.info("Can't load play port '%s': %s", selected_port, e)
            self.playport = None
            self.actual_play_port = None

        self._safe_close_port(old_port)
        return True

    def setup_ports(self):
        """Try to open the configured or first available ports."""
        _refresh_port_cache()
        self._reconnect_input(force=True)
        self._reconnect_output(force=True)

    def _extract_device_name(self, port_string):
        """Extract device name from a port string."""
        descriptive_name = descriptive_port_name(port_string)
        if not descriptive_name:
            return None

        parts = descriptive_name.split()
        if not parts:
            return None

        device_part = parts[0]
        if ":" in device_part:
            device_part = device_part.split(":")[0]
        return device_part

    def _extract_descriptive_port_name(self, port_string):
        return descriptive_port_name(port_string)

    def connectall(self):
        """Reconnect mido ports and then manage aconnect connections."""
        self.reconnect_ports(force=False)
        connectall.connectall(self.usersettings)

    def add_instance(self, menu):
        self.menu = menu

    def change_port(self, port, portname):
        try:
            if port == "inport":
                self.usersettings.change_setting_value("input_port", portname)
                self._reconnect_input(force=True)
                if self.actual_input_port is None:
                    raise RuntimeError(f"Unable to activate input port '{portname}'")
            elif port == "playport":
                self.usersettings.change_setting_value("play_port", portname)
                self._reconnect_output(force=True)
                if self.actual_play_port is None:
                    raise RuntimeError(f"Unable to activate play port '{portname}'")
            self.menu.render_message("Changing " + port + " to:", portname, 1500)
            self.menu.show()
        except Exception:
            self.menu.render_message("Can't change " + port + " to:", portname, 1500)
            self.menu.show()

    def reconnect_ports(self, force=False):
        """Reconnect input and output ports deterministically."""
        _refresh_port_cache()
        changed_input = self._reconnect_input(force=force)
        changed_output = self._reconnect_output(force=force)
        if force or changed_input or changed_output:
            self.reconnect_count += 1
            self.last_reconnect_time = time.time()

    def ports_need_reconnect(self):
        _refresh_port_cache()
        available_inputs = _get_cached_input_names()
        available_outputs = _get_cached_output_names()
        self._refresh_runtime_port_labels(available_inputs=available_inputs, available_outputs=available_outputs)

        requested_input = self.usersettings.get_setting_value("input_port")
        requested_output = self.usersettings.get_setting_value("play_port")

        input_resolution = self._resolve_input_target(requested_input, available_inputs)
        output_resolution = self._resolve_output_target(requested_output, available_outputs)

        selected_input = self._resolve_selected_port(input_resolution)
        selected_output = self._resolve_selected_port(output_resolution)

        if selected_input != self.actual_input_port:
            return True
        if selected_output != self.actual_play_port:
            return True
        if selected_input and not port_is_present(self.actual_input_port, available_inputs):
            return True
        if selected_output and not port_is_present(self.actual_play_port, available_outputs):
            return True
        return False

    def ensure_ports_ready(self):
        if self.ports_need_reconnect():
            self.reconnect_ports(force=False)
            return True
        return False

    def get_rtp_diagnostics(self):
        self._refresh_runtime_port_labels()
        send_count = self.forward_stats["live_sent"]
        avg_send_ms = (
            self.forward_stats["send_time_total_ms"] / send_count
            if send_count else 0.0
        )
        return {
            "drop_counter": self.drop_counter,
            "drop_counts": dict(self.drop_counts),
            "ignored_counts": dict(self.ignored_counts),
            "queue_depths": {
                "live_input": len(self.midi_queue),
                "midi_file": len(self.midifile_queue),
                "websocket_input": len(self.websocket_midi_queue),
                "live_forward": len(self.live_forward_queue),
                "websocket_publish": len(self.websocket_publish_queue),
            },
            "actual_input_port": self.actual_input_port,
            "actual_play_port": self.actual_play_port,
            "last_resolved_input_port": self.last_resolved_input_port,
            "last_resolved_play_port": self.last_resolved_play_port,
            "last_resolution_reason": dict(self.last_resolution_reason),
            "last_reconnect_time": self.last_reconnect_time,
            "reconnect_count": self.reconnect_count,
            "live_sent": self.forward_stats["live_sent"],
            "live_send_errors": self.forward_stats["live_send_errors"],
            "websocket_sent": self.forward_stats["websocket_sent"],
            "websocket_dropped": self.forward_stats["websocket_dropped"],
            "avg_send_ms": round(avg_send_ms, 4),
            "max_send_ms": round(self.forward_stats["send_time_max_ms"], 4),
        }

    def msg_callback(self, msg):
        if self._should_ignore_live_message(msg):
            self._increment_ignored(getattr(msg, "type", "unknown"))
            return

        ts = time.perf_counter()
        self.last_activity = time.time()
        self._queue_with_policy(
            self.midi_queue,
            (msg, ts),
            "live",
            reserve_slots=self.queue_reserved_noteoff_slots,
        )
        self._queue_with_policy(
            self.live_forward_queue,
            (msg, ts),
            "forward",
            reserve_slots=self.queue_reserved_noteoff_slots,
        )

        if self._classify_message(msg) in ("note_on", "note_off"):
            self._queue_with_policy(
                self.websocket_publish_queue,
                (msg, ts),
                "websocket_publish",
                reserve_slots=0,
            )

    def add_websocket_midi_message(self, msg_string):
        """
        Parse a MIDI message string from websocket and add to websocket_midi_queue.
        """
        try:
            if msg_string.startswith("midi_event"):
                msg_string = msg_string[10:]

            parts = msg_string.strip().split()
            if not parts:
                return

            msg_type = parts[0]
            if msg_type not in ("note_on", "note_off"):
                logger.debug(f"Unsupported MIDI message type from websocket: {msg_type}")
                return

            channel = 0
            note = 0
            velocity = 0
            time_val = 0

            for part in parts[1:]:
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                try:
                    if key == "channel":
                        channel = int(value)
                    elif key == "note":
                        note = int(value)
                    elif key == "velocity":
                        velocity = int(value)
                    elif key == "time":
                        time_val = float(value)
                except ValueError:
                    logger.warning(f"Invalid value in websocket MIDI message: {part}")

            msg = mido.Message(msg_type, channel=channel, note=note, velocity=velocity, time=time_val)
            ts = time.perf_counter()
            self.last_activity = time.time()
            self._queue_with_policy(
                self.websocket_midi_queue,
                (msg, ts),
                "websocket_input",
                reserve_slots=self.queue_reserved_noteoff_slots,
            )
            self._queue_with_policy(
                self.live_forward_queue,
                (msg, ts),
                "forward",
                reserve_slots=self.queue_reserved_noteoff_slots,
            )
        except Exception as e:
            logger.warning(f"Error parsing websocket MIDI message: {msg_string}, error: {e}")

    def clear_websocket_midi_queue(self):
        """Clear the websocket MIDI queue."""
        self.websocket_midi_queue.clear()

    def start_midi_monitor(self):
        """Start monitoring for MIDI device changes and auto-connect."""
        if self.midi_monitor_thread is None or not self.midi_monitor_thread.is_alive():
            self.monitor_running = True
            self.midi_monitor_thread = threading.Thread(target=self.auto_reconnect_loop, daemon=True)
            self.midi_monitor_thread.start()
            logger.info("MIDI device monitor started")

    def stop_midi_monitor(self):
        """Stop monitoring for MIDI device changes."""
        self.monitor_running = False
        if self.midi_monitor_thread and self.midi_monitor_thread.is_alive():
            self.midi_monitor_thread.join(timeout=1)
        logger.info("MIDI device monitor stopped")

    def auto_reconnect_loop(self):
        """
        Monitor configured input/secondary/play ports by name.
        Reconnect only when a previously missing compatible port becomes available.
        """
        last_input_present = None
        last_secondary_present = None
        last_play_present = None

        while self.monitor_running:
            try:
                _refresh_port_cache()
                input_names = _get_cached_input_names()
                output_names = _get_cached_output_names()

                input_port = self.usersettings.get_setting_value("input_port")
                secondary_input_port = self.usersettings.get_setting_value("secondary_input_port")
                play_port = self.usersettings.get_setting_value("play_port")

                input_present = bool(self._resolve_selected_port(self._resolve_input_target(input_port, input_names)))
                secondary_present = bool(
                    self._resolve_selected_port(self._resolve_input_target(secondary_input_port, input_names))
                ) if secondary_input_port and secondary_input_port != "default" else False
                play_present = bool(self._resolve_selected_port(self._resolve_output_target(play_port, output_names)))

                input_restored = input_present and (last_input_present is False)
                secondary_restored = secondary_present and (last_secondary_present is False)
                play_restored = play_present and (last_play_present is False)

                if input_restored or secondary_restored:
                    logger.info("MIDI input port restored. Triggering connectall()")
                    try:
                        self.connectall()
                    except Exception as e:
                        logger.info("connectall() raised: {}".format(e))
                elif play_restored:
                    logger.info("MIDI play port restored. Reconnecting ports.")
                    self.reconnect_ports(force=False)

                last_input_present = input_present
                last_secondary_present = secondary_present
                last_play_present = play_present
                time.sleep(3)
            except Exception as e:
                logger.info("auto_reconnect_loop error: {}".format(e))
                time.sleep(5)
