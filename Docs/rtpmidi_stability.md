# RTP-MIDI Stability On Raspberry Pi

This project now avoids auto-switching to hotspot mode when an RTP-MIDI session is configured on the playback side, but the Raspberry Pi still benefits from a few OS-level hardening steps.

## Apply the bundled system tuning

Run on the Raspberry Pi:

```bash
cd /home/Piano-LED-Visualizer
sudo bash scripts/configure_rtpmidi_stability.sh
```

The script applies:

- a `systemd` override for `rtpmidid` with `Restart=always`
- `After=network-online.target` and `Wants=network-online.target`
- Wi-Fi power save disabled through NetworkManager
- an immediate `iw` power-save-off call when available

## Expected RTP-MIDI setup with oscMIDI

- `oscMIDI` session name should stay fixed, for example `OSCMidiRobin64!`
- `oscMIDI` should keep RTP control/data on `5004/5005`
- PLV `play_port` should resolve to the real session port, never `rtpmidid:Network Export` or `rtpmidid:Announcements`

## Validation checklist

- Start `oscMIDI` first and confirm its RTP session is visible.
- Start PLV and verify `actual_play_port` in `/api/get_ports`.
- Restart `oscMIDI`; PLV should reconnect to the same named RTP session.
- Restart `rtpmidid`; PLV should recover without falling back to a fake RTP port.
