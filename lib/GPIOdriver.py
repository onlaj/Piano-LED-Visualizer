try:
    import RPi.GPIO as GPIO
    RPiException = None
except Exception as e:
    print("RPi GPIO failed, using null driver.")
    RPiException = e
    from lib.null_drivers import GPIOnull
    GPIO = GPIOnull()
