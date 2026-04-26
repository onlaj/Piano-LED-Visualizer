from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


_TRAILING_ALSA_ID_RE = re.compile(r"\s+\d+:\d+$")
_TRAILING_ALSA_ID_CAPTURE_RE = re.compile(r"(\d+:\d+)$")
_TRAILING_INSTANCE_RE = re.compile(r"\s+\(\d+\)$")
_TRAILING_SIMPLE_PORT_RE = re.compile(r":\d+$")
_MULTISPACE_RE = re.compile(r"\s+")

_FAKE_RTP_NAMES = {
    "rtpmidid:announcements",
    "rtpmidid:network export",
}


class PortResolutionStatus(str, Enum):
    EXACT = "exact"
    RESOLVED_COMPATIBLE = "resolved_compatible"
    AUTO_SELECTED = "auto_selected"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class PortResolution:
    requested_port: str | None
    selected_port: str | None
    status: PortResolutionStatus
    reason: str


def descriptive_port_name(port_name: str | None) -> str | None:
    if not port_name:
        return None

    normalized = port_name.strip()
    normalized = _TRAILING_ALSA_ID_RE.sub("", normalized)
    normalized = _TRAILING_INSTANCE_RE.sub("", normalized)

    if " " not in normalized:
        normalized = _TRAILING_SIMPLE_PORT_RE.sub("", normalized)

    normalized = _MULTISPACE_RE.sub(" ", normalized).strip()
    return normalized or None


def _stable_port_key(port_name: str | None) -> str:
    descriptive = descriptive_port_name(port_name) or ""
    return _MULTISPACE_RE.sub(" ", descriptive).strip().lower()


def _relaxed_port_key(port_name: str | None) -> str:
    key = _stable_port_key(port_name)
    key = key.replace("!", "")
    return key


def _alsa_slot(port_name: str | None) -> str | None:
    if not port_name:
        return None
    match = _TRAILING_ALSA_ID_CAPTURE_RE.search(port_name.strip())
    if not match:
        return None
    return match.group(1)


def is_fake_rtp_port(port_name: str | None) -> bool:
    return _stable_port_key(port_name) in _FAKE_RTP_NAMES


def is_internal_rtmidi_port(port_name: str | None) -> bool:
    key = _stable_port_key(port_name)
    return "rtmidiin client" in key or "rtmdiout client" in key or "rtmidiout client" in key


def is_valid_input_port(port_name: str | None) -> bool:
    if not port_name:
        return False

    lowered = _stable_port_key(port_name)
    if "through" in lowered or "rpi" in lowered:
        return False
    if is_fake_rtp_port(port_name):
        return False
    if is_internal_rtmidi_port(port_name):
        return False

    return True


def is_valid_output_port(port_name: str | None, available_inputs: list[str] | None = None) -> bool:
    if not port_name:
        return False

    lowered = _stable_port_key(port_name)
    if "through" in lowered or "rpi" in lowered:
        return False
    if is_fake_rtp_port(port_name):
        return False
    if is_internal_rtmidi_port(port_name):
        return False

    if available_inputs:
        input_keys = {_stable_port_key(candidate) for candidate in available_inputs}
        if lowered in input_keys and "rtpmidid:" not in lowered:
            return False

    return True


def filter_valid_output_ports(available_ports: list[str], available_inputs: list[str] | None = None) -> list[str]:
    return [
        port_name for port_name in available_ports
        if is_valid_output_port(port_name, available_inputs=available_inputs)
    ]


def port_is_present(actual_port: str | None, available_ports: list[str]) -> bool:
    if not actual_port:
        return False

    actual_stable = _stable_port_key(actual_port)
    actual_relaxed = _relaxed_port_key(actual_port)
    actual_slot = _alsa_slot(actual_port)

    for candidate in available_ports:
        if candidate == actual_port:
            return True
        if actual_slot and _alsa_slot(candidate) == actual_slot:
            return True
        if _stable_port_key(candidate) == actual_stable:
            return True
        if _relaxed_port_key(candidate) == actual_relaxed:
            return True
    return False


def refresh_runtime_port_name(actual_port: str | None, available_ports: list[str]) -> str | None:
    if not actual_port:
        return None

    if actual_port in available_ports:
        return actual_port

    actual_slot = _alsa_slot(actual_port)
    if actual_slot:
        for candidate in available_ports:
            if _alsa_slot(candidate) == actual_slot:
                return candidate

    actual_stable = _stable_port_key(actual_port)
    for candidate in available_ports:
        if _stable_port_key(candidate) == actual_stable:
            return candidate

    actual_relaxed = _relaxed_port_key(actual_port)
    for candidate in available_ports:
        if _relaxed_port_key(candidate) == actual_relaxed:
            return candidate

    return actual_port


def pick_default_input_port(available_ports: list[str]) -> str | None:
    for port_name in available_ports:
        if is_valid_input_port(port_name):
            return port_name
    return None


def pick_default_output_port(
    available_ports: list[str],
    available_inputs: list[str] | None = None,
) -> str | None:
    for port_name in available_ports:
        if is_valid_output_port(port_name, available_inputs=available_inputs):
            return port_name
    return None


def _resolve_port(
    requested_port: str | None,
    available_ports: list[str],
    *,
    exclude_fake_rtp: bool,
    available_inputs: list[str] | None = None,
) -> PortResolution:
    if not requested_port or requested_port == "default":
        return PortResolution(
            requested_port=requested_port,
            selected_port=None,
            status=PortResolutionStatus.UNAVAILABLE,
            reason="No explicit port requested",
        )

    filtered_ports = [
        candidate for candidate in available_ports
        if not (exclude_fake_rtp and not is_valid_output_port(candidate, available_inputs=available_inputs))
    ]

    if exclude_fake_rtp and requested_port not in filtered_ports and not is_valid_output_port(
        requested_port,
        available_inputs=available_inputs,
    ):
        return PortResolution(
            requested_port=requested_port,
            selected_port=None,
            status=PortResolutionStatus.UNAVAILABLE,
            reason="Requested output port is invalid for playback",
        )

    if requested_port in filtered_ports:
        return PortResolution(
            requested_port=requested_port,
            selected_port=requested_port,
            status=PortResolutionStatus.EXACT,
            reason="Exact ALSA port match",
        )

    requested_stable = _stable_port_key(requested_port)
    requested_relaxed = _relaxed_port_key(requested_port)

    stable_matches = [candidate for candidate in filtered_ports if _stable_port_key(candidate) == requested_stable]
    if stable_matches:
        return PortResolution(
            requested_port=requested_port,
            selected_port=stable_matches[0],
            status=PortResolutionStatus.RESOLVED_COMPATIBLE,
            reason="Matched stable descriptive ALSA name",
        )

    relaxed_matches = [candidate for candidate in filtered_ports if _relaxed_port_key(candidate) == requested_relaxed]
    if relaxed_matches:
        return PortResolution(
            requested_port=requested_port,
            selected_port=relaxed_matches[0],
            status=PortResolutionStatus.RESOLVED_COMPATIBLE,
            reason="Matched relaxed RTP session name",
        )

    contains_matches = [
        candidate for candidate in filtered_ports
        if requested_relaxed and (
            requested_relaxed in _relaxed_port_key(candidate)
            or _relaxed_port_key(candidate) in requested_relaxed
        )
    ]
    if len(contains_matches) == 1:
        return PortResolution(
            requested_port=requested_port,
            selected_port=contains_matches[0],
            status=PortResolutionStatus.RESOLVED_COMPATIBLE,
            reason="Matched unique compatible RTP/ALSA port",
        )

    return PortResolution(
        requested_port=requested_port,
        selected_port=None,
        status=PortResolutionStatus.UNAVAILABLE,
        reason="Requested port is unavailable and no compatible runtime match was found",
    )


def resolve_input_port(requested_port: str | None, available_ports: list[str]) -> PortResolution:
    if requested_port and requested_port != "default" and not is_valid_input_port(requested_port):
        return PortResolution(
            requested_port=requested_port,
            selected_port=None,
            status=PortResolutionStatus.UNAVAILABLE,
            reason="Requested input port is invalid for MIDI input",
        )
    return _resolve_port(
        requested_port,
        [port_name for port_name in available_ports if is_valid_input_port(port_name)],
        exclude_fake_rtp=False,
    )


def resolve_output_port(
    requested_port: str | None,
    available_ports: list[str],
    available_inputs: list[str] | None = None,
) -> PortResolution:
    return _resolve_port(
        requested_port,
        available_ports,
        exclude_fake_rtp=True,
        available_inputs=available_inputs,
    )
