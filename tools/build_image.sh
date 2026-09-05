#!/bin/bash
#
# Build a ready-to-flash Piano LED Visualizer .img from a stock Raspberry Pi OS
# Lite image.
#
# The script takes a clean Raspberry Pi OS Lite image, grows its root
# filesystem, chroots into it through qemu-user-static, performs the same
# install that autoinstall.sh performs on a running Pi, and finally shrinks the
# result so it fits a small SD card and flashes quickly.
#
# Run it on an x86_64 Debian/Ubuntu host (a WSL2 Ubuntu shell works) as root:
#
#     sudo tools/build_image.sh --arch armhf
#
# Output: build/PianoLEDVisualizer-<arch>-<date>.img.xz
#
set -euo pipefail

# --- defaults ---------------------------------------------------------------

ARCH="armhf"                 # armhf = Pi Zero / Zero W; arm64 = Zero 2 W or newer
HOSTNAME_="pianoledvisualizer"
USERNAME="plv"
PASSWORD="visualizer"
GROW_MB=2560                 # extra room for apt, the venv and pip wheels
SOURCE="local"               # "local" = this checkout, or a git URL
BRANCH=""
WITH_RTPMIDI="auto"          # auto | yes | no
OUTDIR="build"
KEEP_MOUNTS="no"
SHRINK="yes"

# Stock Raspberry Pi OS Lite (Trixie) images.
IMG_URL_ARMHF="https://downloads.raspberrypi.com/raspios_lite_armhf_latest"
IMG_URL_ARM64="https://downloads.raspberrypi.com/raspios_lite_arm64_latest"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="/home/Piano-LED-Visualizer"   # must match systemd/visualizer.service

usage() {
  cat <<'USAGE'
Usage: sudo tools/build_image.sh [options]

  --arch armhf|arm64     Target architecture. armhf for Pi Zero / Zero W,
                         arm64 for Pi Zero 2 W and newer.   (default: armhf)
  --base <file|url>      Use this base image instead of downloading the latest
                         Raspberry Pi OS Lite. Accepts .img, .img.xz or a URL.
  --source local|<url>   Install this checkout, or clone the given git URL.
                         (default: local)
  --branch <name>        Branch to clone when --source is a git URL.
  --hostname <name>      Image hostname.               (default: pianoledvisualizer)
  --user <name>          Account to create.            (default: plv)
  --password <pass>      Password for that account.    (default: visualizer)
  --grow-mb <n>          Megabytes to add to the root partition. (default: 2560)
  --with-rtpmidi         Always install rtpmidid. On armhf this builds from
                         source under emulation and can take hours.
  --without-rtpmidi      Never install rtpmidid.
  --no-shrink            Skip PiShrink and keep the full-size .img.
  --out <dir>            Output directory.             (default: build)
  -h, --help             Show this help.

The default (auto) installs rtpmidid from the prebuilt .deb on arm64 and skips
it on armhf, where it would have to be compiled under emulation.
USAGE
}

# --- argument parsing -------------------------------------------------------

BASE_IMAGE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --arch)            ARCH="$2"; shift 2 ;;
    --base)            BASE_IMAGE="$2"; shift 2 ;;
    --source)          SOURCE="$2"; shift 2 ;;
    --branch)          BRANCH="$2"; shift 2 ;;
    --hostname)        HOSTNAME_="$2"; shift 2 ;;
    --user)            USERNAME="$2"; shift 2 ;;
    --password)        PASSWORD="$2"; shift 2 ;;
    --grow-mb)         GROW_MB="$2"; shift 2 ;;
    --with-rtpmidi)    WITH_RTPMIDI="yes"; shift ;;
    --without-rtpmidi) WITH_RTPMIDI="no"; shift ;;
    --no-shrink)       SHRINK="no"; shift ;;
    --out)             OUTDIR="$2"; shift 2 ;;
    --keep-mounts)     KEEP_MOUNTS="yes"; shift ;;
    -h|--help)         usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$ARCH" in
  armhf) QEMU_BIN="qemu-arm-static";     DEFAULT_URL="$IMG_URL_ARMHF" ;;
  arm64) QEMU_BIN="qemu-aarch64-static"; DEFAULT_URL="$IMG_URL_ARM64" ;;
  *) echo "Error: --arch must be armhf or arm64 (got: $ARCH)" >&2; exit 2 ;;
esac

if [ "$WITH_RTPMIDI" = "auto" ]; then
  [ "$ARCH" = "arm64" ] && WITH_RTPMIDI="yes" || WITH_RTPMIDI="no"
fi

[ "$(id -u)" -eq 0 ] || { echo "Error: run this script as root (sudo)." >&2; exit 1; }

log() { echo -e "\n\033[1;36m==> $*\033[0m"; }

# --- host prerequisites -----------------------------------------------------

log "Checking host tools"
MISSING=()
for tool in losetup parted e2fsck resize2fs wget xz truncate; do
  command -v "$tool" >/dev/null 2>&1 || MISSING+=("$tool")
done
command -v "$QEMU_BIN" >/dev/null 2>&1 || MISSING+=("$QEMU_BIN")
if [ ${#MISSING[@]} -gt 0 ]; then
  echo "Error: missing host tools: ${MISSING[*]}" >&2
  echo "On Debian/Ubuntu install them with:" >&2
  echo "  sudo apt-get install -y qemu-user-static binfmt-support parted e2fsprogs xz-utils wget coreutils" >&2
  exit 1
fi
if [ ! -e "/proc/sys/fs/binfmt_misc/register" ]; then
  echo "Error: binfmt_misc is not available, so ARM binaries cannot be run." >&2
  echo "  sudo modprobe binfmt_misc && sudo mount -t binfmt_misc none /proc/sys/fs/binfmt_misc" >&2
  exit 1
fi
if ! ls /proc/sys/fs/binfmt_misc/ 2>/dev/null | grep -qi "qemu-\(arm\|aarch64\)"; then
  echo "Warning: no qemu binfmt handler registered. Registering via multiarch/qemu-user-static..."
  if command -v docker >/dev/null 2>&1; then
    docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
  else
    echo "Error: register the handlers first, e.g. 'sudo apt-get install -y binfmt-support qemu-user-static'" >&2
    exit 1
  fi
fi

mkdir -p "$OUTDIR"
WORK="$OUTDIR/work"
ROOTFS="$WORK/rootfs"
mkdir -p "$WORK" "$ROOTFS"

# --- cleanup ----------------------------------------------------------------

LOOPDEV=""
cleanup() {
  local rc=$?
  [ "$KEEP_MOUNTS" = "yes" ] && return $rc
  set +e
  for m in dev/pts dev sys proc boot/firmware boot ""; do
    mountpoint -q "$ROOTFS/$m" && umount -lf "$ROOTFS/$m"
  done
  [ -n "$LOOPDEV" ] && losetup -d "$LOOPDEV" 2>/dev/null
  return $rc
}
trap cleanup EXIT

# --- fetch and prepare the base image ---------------------------------------

IMG="$WORK/plv.img"

log "Preparing base image"
if [ -n "$BASE_IMAGE" ]; then
  case "$BASE_IMAGE" in
    http*://*) wget -O "$WORK/base.download" "$BASE_IMAGE" ;;
    *)         cp -f "$BASE_IMAGE" "$WORK/base.download" ;;
  esac
else
  wget -O "$WORK/base.download" "$DEFAULT_URL"
fi

# The download is either a raw .img or xz-compressed; sniff rather than trust
# the file name, since the "latest" URLs carry no extension.
if xz -t "$WORK/base.download" >/dev/null 2>&1; then
  echo "Decompressing base image..."
  xz -dc "$WORK/base.download" > "$IMG"
else
  cp -f "$WORK/base.download" "$IMG"
fi

log "Growing the root filesystem by ${GROW_MB} MB"
truncate -s "+${GROW_MB}M" "$IMG"

LOOPDEV="$(losetup --find --show --partscan "$IMG")"
echo "Loop device: $LOOPDEV"
parted -s "$LOOPDEV" resizepart 2 100%
partprobe "$LOOPDEV" 2>/dev/null || true
e2fsck -pf "${LOOPDEV}p2" || true
resize2fs "${LOOPDEV}p2"

# --- mount ------------------------------------------------------------------

log "Mounting image"
mount "${LOOPDEV}p2" "$ROOTFS"
# Trixie/Bookworm mount the FAT partition at /boot/firmware; older images use /boot.
if [ -d "$ROOTFS/boot/firmware" ]; then
  BOOTDIR="boot/firmware"
else
  BOOTDIR="boot"
fi
mount "${LOOPDEV}p1" "$ROOTFS/$BOOTDIR"
CONFIG_TXT="$ROOTFS/$BOOTDIR/config.txt"

cp "$(command -v "$QEMU_BIN")" "$ROOTFS/usr/bin/"
mount -t proc  /proc "$ROOTFS/proc"
mount -t sysfs /sys  "$ROOTFS/sys"
mount --bind   /dev  "$ROOTFS/dev"
mount --bind   /dev/pts "$ROOTFS/dev/pts"
cp -f /etc/resolv.conf "$ROOTFS/etc/resolv.conf"

in_chroot() { chroot "$ROOTFS" /bin/bash -e -o pipefail -c "$1"; }

# --- copy the application in ------------------------------------------------

log "Staging Piano LED Visualizer sources"
rm -rf "${ROOTFS:?}${INSTALL_DIR}"
mkdir -p "${ROOTFS}${INSTALL_DIR}"
if [ "$SOURCE" = "local" ]; then
  # Ship the working tree, minus build artefacts and local state.
  tar -C "$REPO_ROOT" \
      --exclude=.git --exclude=build --exclude=.venv --exclude=node_modules \
      --exclude=config/settings.xml --exclude='*.pyc' --exclude=__pycache__ \
      -cf - . | tar -C "${ROOTFS}${INSTALL_DIR}" -xf -
else
  CLONE_ARGS="--depth 1"
  [ -n "$BRANCH" ] && CLONE_ARGS="$CLONE_ARGS --branch $BRANCH"
  in_chroot "apt-get update && apt-get install -y git"
  in_chroot "rm -rf ${INSTALL_DIR} && git clone $CLONE_ARGS '$SOURCE' ${INSTALL_DIR}"
fi

# --- system configuration ---------------------------------------------------

log "Configuring hostname, user and services"
echo "$HOSTNAME_" > "$ROOTFS/etc/hostname"
sed -i "s/raspberrypi/$HOSTNAME_/g" "$ROOTFS/etc/hosts"

in_chroot "id -u '$USERNAME' >/dev/null 2>&1 || useradd -m -G sudo,audio,gpio,spi,i2c,video -s /bin/bash '$USERNAME' || useradd -m -G sudo -s /bin/bash '$USERNAME'"
in_chroot "echo '$USERNAME:$PASSWORD' | chpasswd"
# Raspberry Pi OS's first-boot check refuses to proceed without a configured
# user; userconf.txt satisfies it even though useradd already ran above.
if PW_HASH="$(in_chroot "openssl passwd -6 '$PASSWORD'" 2>/dev/null)" && [ -n "$PW_HASH" ]; then
  echo "$USERNAME:$PW_HASH" > "$ROOTFS/$BOOTDIR/userconf.txt"
else
  echo "Warning: openssl unavailable in the image; skipping userconf.txt."
fi

# Enable SSH on first boot.
touch "$ROOTFS/$BOOTDIR/ssh"

log "Enabling SPI and disabling onboard audio"
grep -q '^dtparam=spi=on' "$CONFIG_TXT" || echo 'dtparam=spi=on' >> "$CONFIG_TXT"
sed -i 's/^dtparam=audio=on/#dtparam=audio=on/' "$CONFIG_TXT"
echo 'blacklist snd_bcm2835' > "$ROOTFS/etc/modprobe.d/snd-blacklist.conf"

# --- packages ---------------------------------------------------------------

log "Installing system packages (this is the slow part — emulated ARM)"
in_chroot "DEBIAN_FRONTEND=noninteractive apt-get update"
in_chroot "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    git python3 python3-pip python3-venv python3-dev \
    libopenblas-dev libavahi-client-dev libasound2-dev \
    libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev \
    libical-dev libreadline-dev libopenjp2-7 libtiff6 \
    libjack0 libjack-dev autoconf libtool make gcc build-essential \
    scons swig abcmidi fonts-freefont-ttf libfreetype6"

if [ "$WITH_RTPMIDI" = "yes" ] && [ "$ARCH" = "arm64" ]; then
  log "Installing rtpmidid (arm64 prebuilt)"
  in_chroot "cd /tmp && \
    wget -q https://github.com/davidmoreno/rtpmidid/releases/download/v26.01/rtpmidid-debian-trixie-arm64-26.01.deb && \
    apt-get install -y libasound2t64 libavahi-client3 libavahi-common3 && \
    dpkg -i rtpmidid-debian-trixie-arm64-26.01.deb && apt-get -f install -y && \
    systemctl enable rtpmidid && rm -f rtpmidid-debian-trixie-arm64-26.01.deb"
elif [ "$WITH_RTPMIDI" = "yes" ]; then
  log "Building rtpmidid from source (armhf) — this takes a long time under emulation"
  in_chroot "DEBIAN_FRONTEND=noninteractive apt-get install -y cmake pkg-config ninja-build libfmt-dev"
  in_chroot "cd /home && rm -rf rtpmidid-src && \
    git clone --depth 1 --branch v26.01 https://github.com/davidmoreno/rtpmidid.git rtpmidid-src && \
    cd rtpmidid-src && \
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DENABLE_TESTS=OFF -DENABLE_PCH=OFF -DUSE_FMT=ON -DCPP_VERSION=17 -GNinja && \
    cmake --build build && \
    install -m 755 build/src/rtpmidid /usr/bin/rtpmidid && \
    mkdir -p /etc/rtpmidid && cp default.ini /etc/rtpmidid/default.ini && \
    cp debian/rtpmidid.service /lib/systemd/system/rtpmidid.service && \
    (useradd -r -s /usr/sbin/nologin -G audio rtpmidid || true) && \
    systemctl enable rtpmidid"
else
  echo "Skipping rtpmidid (network MIDI). Install it later with autoinstall.sh on the Pi."
fi

# --- python environment -----------------------------------------------------

log "Creating the Python virtualenv and installing requirements"
in_chroot "cd ${INSTALL_DIR} && python3 -m venv .venv"
in_chroot "cd ${INSTALL_DIR} && .venv/bin/pip install --upgrade pip wheel"
in_chroot "cd ${INSTALL_DIR} && .venv/bin/pip install -r requirements.txt"

# --- service ----------------------------------------------------------------

log "Installing the visualizer service"
# The unit ships in the repo and already points at ${INSTALL_DIR}/.venv.
in_chroot "cp ${INSTALL_DIR}/systemd/visualizer.service /lib/systemd/system/visualizer.service"
in_chroot "systemctl enable visualizer.service"
in_chroot "chmod a+rwxX -R ${INSTALL_DIR}"
# Boot to console with autologin, matching autoinstall.sh (raspi-config B2).
in_chroot "systemctl set-default multi-user.target"
mkdir -p "$ROOTFS/etc/systemd/system/getty@tty1.service.d"
cat > "$ROOTFS/etc/systemd/system/getty@tty1.service.d/autologin.conf" <<AUTOLOGIN
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USERNAME --noclear %I \$TERM
AUTOLOGIN

# --- shrink and package -----------------------------------------------------

log "Cleaning up inside the image"
in_chroot "apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*"
rm -f "$ROOTFS/usr/bin/$QEMU_BIN"
: > "$ROOTFS/etc/machine-id"

log "Unmounting"
umount "$ROOTFS/dev/pts"
umount "$ROOTFS/dev"
umount "$ROOTFS/sys"
umount "$ROOTFS/proc"
umount "$ROOTFS/$BOOTDIR"
umount "$ROOTFS"
losetup -d "$LOOPDEV"
LOOPDEV=""

STAMP="$(date +%Y-%m-%d)"
OUT="$OUTDIR/PianoLEDVisualizer-${ARCH}-${STAMP}.img"

if [ "$SHRINK" = "yes" ]; then
  log "Shrinking with PiShrink"
  if [ ! -x "$WORK/pishrink.sh" ]; then
    wget -qO "$WORK/pishrink.sh" https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
    chmod +x "$WORK/pishrink.sh"
  fi
  # -Z compresses with xz and leaves <out>.xz
  "$WORK/pishrink.sh" -Z "$IMG" "$OUT"
else
  mv -f "$IMG" "$OUT"
fi

log "Done"
ls -lh "$OUT"* 2>/dev/null || true
cat <<DONE

Flash the result with Raspberry Pi Imager, balenaEtcher or dd.
First boot expands the filesystem and can take several minutes.

  hostname: $HOSTNAME_.local
  user:     $USERNAME
  password: $PASSWORD
  web UI:   http://$HOSTNAME_.local
DONE
