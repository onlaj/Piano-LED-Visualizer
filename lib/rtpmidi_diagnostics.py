from __future__ import annotations

import json
import re
import subprocess


_TRAILING_ALSA_ID_RE = re.compile(r"\s+\d+:\d+$")


def _default_diagnostics(error_reason=None):
    return {
        "play_network_ready": None,
        "rtpmidi_peer_status": None,
        "rtpmidi_remote_host": None,
        "rtpmidi_error_reason": error_reason,
    }


def _session_name_from_play_port(play_port):
    if not play_port or not str(play_port).startswith("rtpmidid:"):
        return None
    name = str(play_port).split(":", 1)[1]
    name = _TRAILING_ALSA_ID_RE.sub("", name).strip()
    return name or None


def _extract_result(status_payload):
    if not isinstance(status_payload, dict):
        return {}
    result = status_payload.get("result", status_payload)
    return result if isinstance(result, dict) else {}


def _remote_host_from_announcement(result, session_name):
    mdns = result.get("mdns") if isinstance(result, dict) else {}
    announcements = mdns.get("remote_announcements", []) if isinstance(mdns, dict) else []
    for announcement in announcements:
        if announcement.get("name") == session_name:
            hostname = announcement.get("hostname")
            port = announcement.get("port")
            if hostname and port:
                return f"{hostname}:{port}"
            return hostname or None
    return None


def _remote_host_from_peer(peer):
    remote = (peer.get("peer") or {}).get("remote") or {}
    hostname = remote.get("hostname")
    port = remote.get("port")
    if hostname and hostname != "null" and port:
        return f"{hostname}:{port}"
    return None


def _peer_is_ready(peer):
    peer_info = peer.get("peer") or {}
    remote = peer_info.get("remote") or {}
    status = str(peer_info.get("status", "")).upper()
    remote_name = str(remote.get("name") or "").strip()
    remote_ssrc = int(remote.get("ssrc") or 0)
    sent = int((peer.get("stats") or {}).get("sent") or 0)

    if status in {"CONNECTED", "ESTABLISHED", "2"}:
        return True
    if status in {"0", "", "DISCONNECTED", "CONNECTING"}:
        return False
    return bool(remote_name and remote_ssrc and sent >= 0)


def parse_rtpmidid_status(status_payload, play_port=None):
    session_name = _session_name_from_play_port(play_port)
    if not session_name:
        return _default_diagnostics()

    result = _extract_result(status_payload)
    router = result.get("router", []) if isinstance(result, dict) else []
    peers_by_id = {peer.get("id"): peer for peer in router if isinstance(peer, dict)}
    remote_host = _remote_host_from_announcement(result, session_name)

    local_listener = None
    for peer in router:
        if not isinstance(peer, dict):
            continue
        if peer.get("type") != "local_alsa_listener_t":
            continue
        if session_name in str(peer.get("name") or ""):
            local_listener = peer
            break

    if local_listener is None:
        return {
            "play_network_ready": False,
            "rtpmidi_peer_status": None,
            "rtpmidi_remote_host": remote_host,
            "rtpmidi_error_reason": f"{session_name} is not connected to rtpmidid",
        }

    network_peer = None
    for peer_id in local_listener.get("send_to", []) or []:
        candidate = peers_by_id.get(peer_id)
        if candidate and str(candidate.get("type", "")).startswith("network_rtpmidi"):
            network_peer = candidate
            break

    if network_peer is None:
        return {
            "play_network_ready": False,
            "rtpmidi_peer_status": local_listener.get("status"),
            "rtpmidi_remote_host": remote_host,
            "rtpmidi_error_reason": f"{session_name} has no RTP network peer",
        }

    peer_info = network_peer.get("peer") or {}
    peer_status = peer_info.get("status")
    remote_host = _remote_host_from_peer(network_peer) or remote_host
    ready = _peer_is_ready(network_peer)
    error_reason = None
    if not ready:
        error_reason = (
            f"{session_name} ALSA playport is open but the RTP network session is not connected"
        )

    return {
        "play_network_ready": ready,
        "rtpmidi_peer_status": peer_status,
        "rtpmidi_remote_host": remote_host,
        "rtpmidi_error_reason": error_reason,
    }


def parse_rtpmidid_cli_output(output):
    text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">>>"))
    start = text.find("{")
    if start < 0:
        raise ValueError("rtpmidid-cli did not return JSON")
    return json.loads(text[start:])


def get_rtpmidid_network_diagnostics(play_port, *, timeout=1.5):
    try:
        output = subprocess.check_output(
            ["rtpmidid-cli", "status"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return parse_rtpmidid_status(parse_rtpmidid_cli_output(output), play_port=play_port)
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        return _default_diagnostics(f"Unable to read rtpmidid status: {exc}")
