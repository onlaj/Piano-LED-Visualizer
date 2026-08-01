import os

from lib.log_setup import logger
from lib.null_drivers import GPIOnull


def _hat_disabled():
    try:
        from xml.etree import ElementTree as ET
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "settings.xml")
        return ET.parse(path).getroot().findtext("disable_hat") == "1"
    except Exception:
        return False


# disable_hat=1: no LCD control HAT is attached, and the pins PLV would drive for
# it belong to other hardware (Geekworm X735: GPIO5 shutdown signal, GPIO12
# boot-ok, GPIO13 fan PWM, GPIO20 software power button — a stray pull-up on
# GPIO20 reads as a held power button and the HAT cuts power).
HAT_DISABLED = _hat_disabled()

# GPIO — null the driver outright when the HAT is disabled so no code path,
# gated or not, can touch a physical pin.
if HAT_DISABLED:
    RPiException = None
    GPIO = GPIOnull()
    logger.info("disable_hat=1: GPIO null driver active, physical pins untouched.")
else:
    try:
        import RPi.GPIO as GPIO
        RPiException = None
    except Exception as e:
        logger.warning("RPi GPIO failed, using null driver.")
        RPiException = e
        GPIO = GPIOnull()

# rpi_ws281x
try:
    from rpi_ws281x import PixelStrip, ws, Color
except ModuleNotFoundError as e:
    logger.warning("Module rpi_ws281x not found, using null driver.")
    from lib.null_drivers import Color
    PixelStrip = None
    ws = None

# spidev
try:
    import spidev
except ModuleNotFoundError as e:
    logger.warning("Module spidev not found.")
    spidev = None
