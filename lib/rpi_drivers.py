# GPIO
try:
    import RPi.GPIO as GPIO
    RPiException = None
except Exception as e:
    print("RPi GPIO failed, using null driver.")
    RPiException = e
    from lib.null_drivers import GPIOnull
    GPIO = GPIOnull()

# rpi_ws281x
try:
    from rpi_ws281x import PixelStrip, ws, Color
except ModuleNotFoundError as e:
    print("Module rpi_ws281x not found, using null driver.")
    from lib.null_drivers import Color
    PixelStrip = None
    ws = None

# spidev
try:
    import spidev
except ModuleNotFoundError as e:
    print("Module spidev not found.")
    spidev = None
