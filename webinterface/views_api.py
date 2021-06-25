from webinterface import webinterface
from flask import render_template, flash, redirect, request, url_for, jsonify
from lib.functions import find_between, theaterChase, theaterChaseRainbow, sound_of_da_police, scanner, breathing, \
    rainbow, rainbowCycle, fastColorWipe
import psutil
import threading
from neopixel import *
import webcolors as wc
import mido


@webinterface.route('/api/start_animation', methods=['GET'])
def start_animation():
    choice = request.args.get('name')
    speed = request.args.get('speed')
    if choice == "theaterchase":
        webinterface.menu.t = threading.Thread(target=theaterChase, args=(webinterface.ledstrip.strip,
                                                                          Color(127, 127, 127),
                                                                          webinterface.ledsettings,
                                                                          webinterface.menu))
        webinterface.menu.t.start()

    if choice == "theaterchaserainbow":
        webinterface.t = threading.Thread(target=theaterChaseRainbow, args=(webinterface.ledstrip.strip,
                                                                            webinterface.ledsettings,
                                                                            webinterface.menu, 5))
        webinterface.t.start()

    if choice == "soundofdapolice":
        webinterface.t = threading.Thread(target=sound_of_da_police, args=(webinterface.ledstrip.strip,
                                                                           webinterface.ledsettings,
                                                                           webinterface.menu, 1))
        webinterface.t.start()

    if choice == "scanner":
        webinterface.t = threading.Thread(target=scanner, args=(webinterface.ledstrip.strip,
                                                                webinterface.ledsettings,
                                                                webinterface.menu, 1))
        webinterface.t.start()

    if choice == "breathing":
        if speed == "fast":
            webinterface.t = threading.Thread(target=breathing, args=(webinterface.ledstrip.strip,
                                                                      webinterface.ledsettings,
                                                                      webinterface.menu, 5))
            webinterface.t.start()
        if speed == "medium":
            webinterface.t = threading.Thread(target=breathing, args=(webinterface.ledstrip.strip,
                                                                      webinterface.ledsettings,
                                                                      webinterface.menu, 10))
            webinterface.t.start()
        if speed == "slow":
            webinterface.t = threading.Thread(target=breathing, args=(webinterface.ledstrip.strip,
                                                                      webinterface.ledsettings,
                                                                      webinterface.menu, 25))
            webinterface.t.start()

    if choice == "rainbow":
        if speed == "fast":
            webinterface.t = threading.Thread(target=rainbow, args=(webinterface.ledstrip.strip,
                                                                    webinterface.ledsettings,
                                                                    webinterface.menu, 2))
            webinterface.t.start()
        if speed == "medium":
            webinterface.t = threading.Thread(target=rainbow, args=(webinterface.ledstrip.strip,
                                                                    webinterface.ledsettings,
                                                                    webinterface.menu, 20))
            webinterface.t.start()
        if speed == "slow":
            webinterface.t = threading.Thread(target=rainbow, args=(webinterface.ledstrip.strip,
                                                                    webinterface.ledsettings,
                                                                    webinterface.menu, 50))
            webinterface.t.start()

    if choice == "rainbowcycle":
        if speed == "fast":
            webinterface.t = threading.Thread(target=rainbowCycle, args=(webinterface.ledstrip.strip,
                                                                         webinterface.ledsettings,
                                                                         webinterface.menu, 1))
            webinterface.t.start()
        if speed == "medium":
            webinterface.t = threading.Thread(target=rainbowCycle, args=(webinterface.ledstrip.strip,
                                                                         webinterface.ledsettings,
                                                                         webinterface.menu, 20))
            webinterface.t.start()
        if speed == "slow":
            webinterface.t = threading.Thread(target=rainbowCycle, args=(webinterface.ledstrip.strip,
                                                                         webinterface.ledsettings,
                                                                         webinterface.menu, 50))
            webinterface.t.start()

    if choice == "stop":
        webinterface.menu.screensaver_is_running = False

    return jsonify(success=True)


@webinterface.route('/api/get_homepage_data')
def get_homepage_data():
    try:
        temp = find_between(str(psutil.sensors_temperatures()["cpu_thermal"]), "current=", ",")
    except:
        temp = find_between(str(psutil.sensors_temperatures()["cpu-thermal"]), "current=", ",")

    temp = round(float(temp), 1)

    upload = psutil.net_io_counters().bytes_sent
    download = psutil.net_io_counters().bytes_recv

    card_space = psutil.disk_usage('/')

    homepage_data = {
        'cpu_usage': psutil.cpu_percent(interval=0.1),
        'memory_usage_percent': psutil.virtual_memory()[2],
        'memory_usage_total': psutil.virtual_memory()[0],
        'memory_usage_used':  psutil.virtual_memory()[3],
        'cpu_temp': temp,
        'upload': upload,
        'download': download,
        'card_space_used': card_space.used,
        'card_space_total': card_space.total,
        'card_space_percent': card_space.percent
    }
    return jsonify(homepage_data)


@webinterface.route('/api/change_setting', methods=['GET'])
def change_setting():
    setting_name = request.args.get('setting_name')
    value = request.args.get('value')

    if setting_name == "led_color":
        rgb = wc.hex_to_rgb("#"+value)

        webinterface.ledsettings.color_mode = "Single"

        webinterface.ledsettings.red = rgb[0]
        webinterface.ledsettings.green = rgb[1]
        webinterface.ledsettings.blue = rgb[2]

        webinterface.usersettings.change_setting_value("color_mode", webinterface.ledsettings.color_mode)
        webinterface.usersettings.change_setting_value("red", rgb[0])
        webinterface.usersettings.change_setting_value("green", rgb[1])
        webinterface.usersettings.change_setting_value("blue", rgb[2])

    if setting_name == "light_mode":
        webinterface.ledsettings.mode = value
        webinterface.usersettings.change_setting_value("mode", value)

    if setting_name == "fading_speed" or setting_name == "velocity_speed":
        webinterface.ledsettings.fadingspeed = int(value)
        webinterface.usersettings.change_setting_value("fadingspeed", webinterface.ledsettings.fadingspeed)

    if setting_name == "brightness":
        webinterface.usersettings.change_setting_value("brightness_percent", int(value))
        webinterface.ledstrip.change_brightness(int(value), True)

    if setting_name == "backlight_brightness":
        webinterface.ledsettings.backlight_brightness_percent = int(value)
        webinterface.ledsettings.backlight_brightness = 255 * webinterface.ledsettings.backlight_brightness_percent / 100
        webinterface.usersettings.change_setting_value("backlight_brightness",
                                                       int(webinterface.ledsettings.backlight_brightness))
        webinterface.usersettings.change_setting_value("backlight_brightness_percent",
                                                       webinterface.ledsettings.backlight_brightness_percent)
        fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

    if setting_name == "backlight_color":
        rgb = wc.hex_to_rgb("#" + value)

        webinterface.ledsettings.backlight_red = rgb[0]
        webinterface.ledsettings.backlight_green = rgb[1]
        webinterface.ledsettings.backlight_blue = rgb[2]

        webinterface.usersettings.change_setting_value("backlight_red", rgb[0])
        webinterface.usersettings.change_setting_value("backlight_green", rgb[1])
        webinterface.usersettings.change_setting_value("backlight_blue", rgb[2])

        fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

    if setting_name == "sides_color":
        rgb = wc.hex_to_rgb("#" + value)

        webinterface.ledsettings.adjacent_red = rgb[0]
        webinterface.ledsettings.adjacent_green = rgb[1]
        webinterface.ledsettings.adjacent_blue = rgb[2]

        webinterface.usersettings.change_setting_value("adjacent_red", rgb[0])
        webinterface.usersettings.change_setting_value("adjacent_green", rgb[1])
        webinterface.usersettings.change_setting_value("adjacent_blue", rgb[2])

    if setting_name == "sides_color_mode":
        webinterface.ledsettings.adjacent_mode = value
        webinterface.usersettings.change_setting_value("adjacent_mode", value)


    if setting_name == "input_port":
        webinterface.usersettings.change_setting_value("input_port", value)
        webinterface.midiports.change_port("inport", value)

    if setting_name == "secondary_input_port":
        webinterface.usersettings.change_setting_value("secondary_input_port", value)

    if setting_name == "play_port":
        webinterface.usersettings.change_setting_value("play_port", value)
        webinterface.midiports.change_port("playport", value)

    if setting_name == "skipped_notes":
        webinterface.usersettings.change_setting_value("skipped_notes", value)
        webinterface.ledsettings.skipped_notes = value

    if setting_name == "led_count":
        webinterface.usersettings.change_setting_value("led_count", int(value))
        webinterface.ledstrip.change_led_count(int(value), True)

    if setting_name == "shift":
        webinterface.usersettings.change_setting_value("shift", int(value))
        webinterface.ledstrip.change_shift(int(value), True)

    if setting_name == "reverse":
        webinterface.usersettings.change_setting_value("reverse", int(value))
        webinterface.ledstrip.change_reverse(int(value), True)

    return jsonify(success=True)


@webinterface.route('/api/get_settings', methods=['GET'])
def get_settings():
    response = {}

    red = webinterface.usersettings.get_setting_value("red")
    green = webinterface.usersettings.get_setting_value("green")
    blue = webinterface.usersettings.get_setting_value("blue")
    led_color = wc.rgb_to_hex((int(red), int(green), int(blue)))

    backlight_red = webinterface.usersettings.get_setting_value("backlight_red")
    backlight_green = webinterface.usersettings.get_setting_value("backlight_green")
    backlight_blue = webinterface.usersettings.get_setting_value("backlight_blue")
    backlight_color = wc.rgb_to_hex((int(backlight_red), int(backlight_green), int(backlight_blue)))

    sides_red = webinterface.usersettings.get_setting_value("adjacent_red")
    sides_green = webinterface.usersettings.get_setting_value("adjacent_green")
    sides_blue = webinterface.usersettings.get_setting_value("adjacent_blue")
    sides_color = wc.rgb_to_hex((int(sides_red), int(sides_green), int(sides_blue)))

    light_mode = webinterface.usersettings.get_setting_value("mode")

    brightness = webinterface.usersettings.get_setting_value("brightness_percent")
    backlight_brightness = webinterface.usersettings.get_setting_value("backlight_brightness_percent")

    response["led_color"] = led_color
    response["light_mode"] = light_mode
    response["brightness"] = brightness
    response["backlight_brightness"] = backlight_brightness
    response["backlight_color"] = backlight_color

    response["sides_color_mode"] = webinterface.usersettings.get_setting_value("adjacent_mode")
    response["sides_color"] = sides_color

    response["input_port"] = webinterface.usersettings.get_setting_value("input_port")
    response["play_port"] = webinterface.usersettings.get_setting_value("play_port")

    response["skipped_notes"] = webinterface.usersettings.get_setting_value("skipped_notes")
    response["led_count"] = webinterface.usersettings.get_setting_value("led_count")
    response["led_shift"] = webinterface.usersettings.get_setting_value("shift")
    response["led_reverse"] = webinterface.usersettings.get_setting_value("reverse")

    return jsonify(response)


@webinterface.route('/api/get_ports', methods=['GET'])
def get_ports():
    ports = mido.get_input_names()
    ports = list(dict.fromkeys(ports))
    response = {}
    response["ports_list"] = ports
    response["input_port"] = webinterface.usersettings.get_setting_value("input_port")
    response["secondary_input_port"] = webinterface.usersettings.get_setting_value("secondary_input_port")
    response["play_port"] = webinterface.usersettings.get_setting_value("play_port")

    return jsonify(response)

@webinterface.route('/api/switch_ports', methods=['GET'])
def switch_ports():
    active_input = webinterface.usersettings.get_setting_value("input_port")
    secondary_input = webinterface.usersettings.get_setting_value("secondary_input_port")
    webinterface.midiports.change_port("inport", secondary_input)
    webinterface.usersettings.change_setting_value("secondary_input_port", active_input)

    fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

    return jsonify(success=True)

