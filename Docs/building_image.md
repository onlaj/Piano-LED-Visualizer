# Building a flashable `.img`

There is no single file in this repository that is an SD-card image. An image is
*built*: a stock Raspberry Pi OS Lite image is taken, this project and its
dependencies are installed into it, and the result is shrunk back down. That is
exactly what [`tools/build_image.sh`](../tools/build_image.sh) does, and what the
**Build Piano LED Visualizer Image** GitHub Actions workflow runs.

You have three ways to get a `.img`, in increasing order of effort.

## 1. Download a prebuilt image

The easiest path, and the right one unless you have changed the code:
grab the latest zip from
[Releases](https://github.com/onlaj/Piano-LED-Visualizer/releases), unzip it and
flash it. Skip the rest of this document.

## 2. Build in GitHub Actions

Best if you have forked the repository and want an image of *your* code without
setting up a Linux build host.

1. Push your changes to your fork.
2. Open **Actions → Build Piano LED Visualizer Image → Run workflow**.
3. Pick the architecture:
   - `armhf` — Pi Zero, Pi Zero W
   - `arm64` — Pi Zero 2 W and newer
4. When it finishes, download the `PianoLEDVisualizer-<arch>` artifact. It
   contains the `.img.xz`.

The job installs packages inside an emulated ARM root filesystem, so expect it
to take a while — roughly 40–90 minutes for `armhf`.

## 3. Build locally

You need an x86_64 Linux host with root. A WSL2 Ubuntu shell works; so does any
Debian or Ubuntu machine, or a VM.

```bash
sudo apt-get install -y qemu-user-static binfmt-support parted e2fsprogs xz-utils wget
```

Then, from the repository root:

```bash
sudo tools/build_image.sh --arch armhf
```

The result lands in `build/PianoLEDVisualizer-armhf-<date>.img.xz`.

### What the script does

1. Downloads the latest Raspberry Pi OS Lite (Trixie) image for the chosen
   architecture — or uses the one you pass with `--base`.
2. Grows the image file and its root partition (`--grow-mb`, 2560 MB by
   default) so there is room for apt, the virtualenv and pip wheels.
3. Attaches it to a loop device and mounts both partitions.
4. Copies in `qemu-arm-static` / `qemu-aarch64-static` so `chroot` can run ARM
   binaries on your x86 host, then binds `/proc`, `/sys` and `/dev`.
5. Copies this checkout to `/home/Piano-LED-Visualizer` (or clones a git URL
   with `--source`).
6. Sets the hostname, creates the user, enables SSH, enables SPI and blacklists
   the onboard audio driver.
7. Installs the apt dependencies, creates the `.venv` and installs
   `requirements.txt` — the same steps `autoinstall.sh` performs on a live Pi.
8. Installs and enables `systemd/visualizer.service`.
9. Unmounts, then runs [PiShrink](https://github.com/Drewsif/PiShrink) so the
   image is as small as possible and expands on first boot.

### Useful options

| Option | Purpose |
| --- | --- |
| `--arch armhf\|arm64` | Target architecture. `armhf` for Pi Zero / Zero W. |
| `--base <file\|url>` | Build on a specific base image instead of downloading the latest. |
| `--source <git-url>` | Clone from git instead of shipping the local checkout. |
| `--branch <name>` | Branch to use with `--source`. |
| `--hostname` / `--user` / `--password` | Image identity. Defaults: `pianoledvisualizer` / `plv` / `visualizer`. |
| `--with-rtpmidi` | Install network MIDI. See the note below. |
| `--no-shrink` | Keep the full-size `.img` (useful when debugging a build). |
| `--grow-mb <n>` | More headroom if `pip install` runs out of space. |

### A note on rtpmidid (network MIDI)

`rtpmidid` ships a prebuilt `.deb` for `arm64` only. On `armhf` it has to be
compiled from source, and under emulation that can take hours — so the script
skips it by default on `armhf`. Network MIDI is optional; everything else works
without it. If you want it on a Pi Zero, the practical route is to flash the
image, boot the Pi, and run `autoinstall.sh`'s rtpmidid step natively.

## Flashing

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) (choose "Use
custom" and select the `.img.xz` — it decompresses on the fly),
[balenaEtcher](https://www.balena.io/etcher/), or `dd`.

First boot takes several minutes while the filesystem expands. After that:

- hostname: `pianoledvisualizer.local`
- user / password: `plv` / `visualizer`
- web interface: `http://pianoledvisualizer.local`

If the Pi is not on your network yet, it brings up a `PianoLEDVisualizer`
Wi-Fi hotspot (password `visualizer`); connect to it and use the **Wi-Fi** tab
in the web interface to join your own network.

## Troubleshooting

**`losetup: cannot find an unused loop device`** — your host has no loop
devices. Under WSL2 run `sudo modprobe loop`; in a container add
`--privileged`.

**`Exec format error` inside the chroot** — the qemu binfmt handlers are not
registered. Run:

```bash
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

**`No space left on device` during `pip install`** — rerun with a larger
`--grow-mb`, for example `--grow-mb 4096`.

**The build fails midway and you want to inspect the image** — rerun with
`--keep-mounts`; the mounted root filesystem stays at `build/work/rootfs`.
Unmount it yourself afterwards.
