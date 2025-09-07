from webinterface import webinterface, app_state
from flask import render_template, send_file, request, jsonify
from werkzeug.security import safe_join
from lib.functions import (get_last_logs, find_between, theaterChase, theaterChaseRainbow, fireplace, sound_of_da_police, scanner,
                           breathing, rainbow, rainbowCycle, chords, colormap_animation, fastColorWipe, play_midi, clamp)
import lib.colormaps as cmap
import psutil
import threading
import webcolors as wc
import mido
from xml.dom import minidom
from subprocess import call
import subprocess
import datetime
import os
import math
from zipfile import ZipFile
import json
import ast
from lib.rpi_drivers import GPIO
from lib.log_setup import logger
from flask import abort

SENSECOVER = 12
GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSECOVER, GPIO.IN, GPIO.PUD_UP)

pid = psutil.Process(os.getpid())


@webinterface.route('/api/start_animation', methods=['GET'])
def start_animation():
    choice = request.args.get('name')
    speed = request.args.get('speed')
    if choice == "theaterchase":
        app_state.menu.is_animation_running = True
        app_state.menu.t = threading.Thread(target=theaterChase, args=(app_state.ledstrip,
                                                                          app_state.ledsettings,
                                                                          app_state.menu))
        app_state.menu.t.start()

    if choice == "theaterchaserainbow":
        app_state.menu.is_animation_running = True
        webinterface.t = threading.Thread(target=theaterChaseRainbow, args=(app_state.ledstrip,
                                                                            app_state.ledsettings,
                                                                            app_state.menu, "Medium"))
        webinterface.t.start()

    if choice == "fireplace":
        app_state.menu.is_animation_running = True
        webinterface.t = threading.Thread(target=fireplace, args=(app_state.ledstrip,
                                                                            app_state.ledsettings,
                                                                            app_state.menu))
        webinterface.t.start()

    if choice == "soundofdapolice":
        app_state.menu.is_animation_running = True
        webinterface.t = threading.Thread(target=sound_of_da_police, args=(app_state.ledstrip,
                                                                           app_state.ledsettings,
                                                                           app_state.menu, 1))
        webinterface.t.start()

    if choice == "scanner":
        app_state.menu.is_animation_running = True
        webinterface.t = threading.Thread(target=scanner, args=(app_state.ledstrip,
                                                                app_state.ledsettings,
                                                                app_state.menu, 1))
        webinterface.t.start()

    if choice == "breathing":
        app_state.menu.is_animation_running = True
        webinterface.t = threading.Thread(target=breathing, args=(app_state.ledstrip,
                                                                  app_state.ledsettings,
                                                                  app_state.menu, speed.capitalize()))
        webinterface.t.start()

    if choice == "rainbow":
        app_state.menu.is_animation_running = True
        webinterface.t = threading.Thread(target=rainbow, args=(
            app_state.ledstrip, app_state.ledsettings, app_state.menu, speed.capitalize()))
        webinterface.t.start()

    if choice == "rainbowcycle":
        app_state.menu.is_animation_running = True
        webinterface.t = threading.Thread(target=rainbowCycle, args=(
            app_state.ledstrip, app_state.ledsettings, app_state.menu, speed.capitalize()))

        webinterface.t.start()

    if choice == "chords":
        app_state.menu.is_animation_running = True
        webinterface.t = threading.Thread(target=chords, args=(
            speed, app_state.ledstrip, app_state.ledsettings, app_state.menu))
        webinterface.t.start()

    if choice == "colormap_animation":
        app_state.menu.is_animation_running = True
        webinterface.t = threading.Thread(target=colormap_animation, args=(
            speed, app_state.ledstrip, app_state.ledsettings, app_state.menu))
        webinterface.t.start()

    if choice == "stop":
        app_state.menu.is_animation_running = False
        app_state.menu.is_idle_animation_running = False

    return jsonify(success=True)


@webinterface.route('/api/get_homepage_data')
def get_homepage_data():
    global pid

    try:
        temp = find_between(str(psutil.sensors_temperatures()["cpu_thermal"]), "current=", ",")
    except:
        temp = 0

    temp = round(float(temp), 1)

    upload = psutil.net_io_counters().bytes_sent
    download = psutil.net_io_counters().bytes_recv

    card_space = psutil.disk_usage('/')

    cover_opened = GPIO.input(SENSECOVER)

    homepage_data = {
        'cpu_usage': psutil.cpu_percent(interval=0.1),
        'cpu_count': psutil.cpu_count(),
        'cpu_pid': pid.cpu_percent(),
        'cpu_freq': psutil.cpu_freq().current,
        'memory_usage_percent': psutil.virtual_memory()[2],
        'memory_usage_total': psutil.virtual_memory()[0],
        'memory_usage_used': psutil.virtual_memory()[3],
        'memory_pid': pid.memory_full_info().rss,
        'cpu_temp': temp,
        'upload': upload,
        'download': download,
        'card_space_used': card_space.used,
        'card_space_total': card_space.total,
        'card_space_percent': card_space.percent,
        'cover_state': 'Opened' if cover_opened else 'Closed',
        'led_fps': round(app_state.ledstrip.current_fps, 2),
        'screen_on': app_state.menu.screen_on,
    }
    return jsonify(homepage_data)


@webinterface.route('/api/change_setting', methods=['GET'])
def change_setting():
    setting_name = request.args.get('setting_name')
    value = request.args.get('value')
    second_value = request.args.get('second_value')
    disable_sequence = request.args.get('disable_sequence')

    reload_sequence = True
    if second_value == "no_reload":
        reload_sequence = False

    if disable_sequence == "true":
        #menu = app_state.ledsettings.menu
        #ledstrip = app_state.ledsettings.ledstrip
        #app_state.ledsettings.__init__(app_state.usersettings)
        #app_state.ledsettings.menu = menu
        #app_state.ledsettings.add_instance(menu, ledstrip)
        #app_state.ledsettings.ledstrip = ledstrip
        app_state.ledsettings.sequence_active = False

    if setting_name == "clean_ledstrip":
        fastColorWipe(app_state.ledstrip.strip, True, app_state.ledsettings)

    if setting_name == "led_color":
        rgb = wc.hex_to_rgb("#" + value)

        app_state.ledsettings.color_mode = "Single"

        app_state.ledsettings.red = rgb[0]
        app_state.ledsettings.green = rgb[1]
        app_state.ledsettings.blue = rgb[2]

        app_state.usersettings.change_setting_value("color_mode", app_state.ledsettings.color_mode)
        app_state.usersettings.change_setting_value("red", rgb[0])
        app_state.usersettings.change_setting_value("green", rgb[1])
        app_state.usersettings.change_setting_value("blue", rgb[2])
        app_state.ledsettings.incoming_setting_change = True
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "light_mode":
        app_state.ledsettings.mode = value
        app_state.usersettings.change_setting_value("mode", value)

    if setting_name == "fading_speed" or setting_name == "velocity_speed":
        if not int(value):
            value = 1000
        app_state.ledsettings.fadingspeed = int(value)
        app_state.usersettings.change_setting_value("fadingspeed", app_state.ledsettings.fadingspeed)

    if setting_name == "brightness":
        app_state.usersettings.change_setting_value("brightness_percent", int(value))
        app_state.ledstrip.change_brightness(int(value), True)

    if setting_name == "led_animation_brightness_percent":
        app_state.usersettings.change_setting_value("led_animation_brightness_percent", int(value))
        app_state.ledsettings.led_animation_brightness_percent = int(value)

    if setting_name == "backlight_brightness":
        app_state.ledsettings.backlight_brightness_percent = int(value)
        app_state.ledsettings.backlight_brightness = 255 * app_state.ledsettings.backlight_brightness_percent / 100
        app_state.usersettings.change_setting_value("backlight_brightness",
                                                       int(app_state.ledsettings.backlight_brightness))
        app_state.usersettings.change_setting_value("backlight_brightness_percent",
                                                       app_state.ledsettings.backlight_brightness_percent)
        fastColorWipe(app_state.ledstrip.strip, True, app_state.ledsettings)

    if setting_name == "disable_backlight_on_idle":
        value = int(value == 'true')
        app_state.ledsettings.disable_backlight_on_idle = int(value)
        app_state.usersettings.change_setting_value("disable_backlight_on_idle", app_state.ledsettings.disable_backlight_on_idle)

    if setting_name == "backlight_color":
        rgb = wc.hex_to_rgb("#" + value)

        app_state.ledsettings.backlight_red = rgb[0]
        app_state.ledsettings.backlight_green = rgb[1]
        app_state.ledsettings.backlight_blue = rgb[2]

        app_state.usersettings.change_setting_value("backlight_red", rgb[0])
        app_state.usersettings.change_setting_value("backlight_green", rgb[1])
        app_state.usersettings.change_setting_value("backlight_blue", rgb[2])

        fastColorWipe(app_state.ledstrip.strip, True, app_state.ledsettings)

    if setting_name == "sides_color":
        rgb = wc.hex_to_rgb("#" + value)

        app_state.ledsettings.adjacent_red = rgb[0]
        app_state.ledsettings.adjacent_green = rgb[1]
        app_state.ledsettings.adjacent_blue = rgb[2]

        app_state.usersettings.change_setting_value("adjacent_red", rgb[0])
        app_state.usersettings.change_setting_value("adjacent_green", rgb[1])
        app_state.usersettings.change_setting_value("adjacent_blue", rgb[2])

    if setting_name == "sides_color_mode":
        app_state.ledsettings.adjacent_mode = value
        app_state.usersettings.change_setting_value("adjacent_mode", value)

    if setting_name == "input_port":
        app_state.usersettings.change_setting_value("input_port", value)
        app_state.midiports.change_port("inport", value)

    if setting_name == "secondary_input_port":
        app_state.usersettings.change_setting_value("secondary_input_port", value)

    if setting_name == "play_port":
        app_state.usersettings.change_setting_value("play_port", value)
        app_state.midiports.change_port("playport", value)

    if setting_name == "skipped_notes":
        app_state.usersettings.change_setting_value("skipped_notes", value)
        app_state.ledsettings.skipped_notes = value

    if setting_name == "add_note_offset":
        app_state.ledsettings.add_note_offset()
        return jsonify(success=True, reload=True)

    if setting_name == "append_note_offset":
        app_state.ledsettings.append_note_offset()
        return jsonify(success=True, reload=True)

    if setting_name == "remove_note_offset":
        app_state.ledsettings.del_note_offset(int(value) + 1)
        return jsonify(success=True, reload=True)

    if setting_name == "note_offsets":
        app_state.usersettings.change_setting_value("note_offsets", value)

    if setting_name == "update_note_offset":
        app_state.ledsettings.update_note_offset(int(value) + 1, second_value)
        return jsonify(success=True, reload=True)

    if setting_name == "led_count":
        app_state.usersettings.change_setting_value("led_count", int(value))
        app_state.ledstrip.change_led_count(int(value), True)

    if setting_name == "leds_per_meter":
        app_state.usersettings.change_setting_value("leds_per_meter", int(value))
        app_state.ledstrip.leds_per_meter = int(value)

    if setting_name == "shift":
        app_state.usersettings.change_setting_value("shift", int(value))
        app_state.ledstrip.change_shift(int(value), True)

    if setting_name == "reverse":
        app_state.usersettings.change_setting_value("reverse", int(value))
        app_state.ledstrip.change_reverse(int(value), True)

    if setting_name == "color_mode":
        reload_sequence = True
        if second_value == "no_reload":
            reload_sequence = False

        app_state.ledsettings.color_mode = value
        app_state.usersettings.change_setting_value("color_mode", app_state.ledsettings.color_mode)
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "add_multicolor":
        app_state.ledsettings.addcolor()
        return jsonify(success=True, reload=True)

    if setting_name == "add_multicolor_and_set_value":
        settings = json.loads(value)

        app_state.ledsettings.multicolor.clear()
        app_state.ledsettings.multicolor_range.clear()

        for key, value in settings.items():
            rgb = wc.hex_to_rgb("#" + value["color"])

            app_state.ledsettings.multicolor.append([int(rgb[0]), int(rgb[1]), int(rgb[2])])
            app_state.ledsettings.multicolor_range.append([int(value["range"][0]), int(value["range"][1])])

        app_state.usersettings.change_setting_value("multicolor", app_state.ledsettings.multicolor)
        app_state.usersettings.change_setting_value("multicolor_range",
                                                       app_state.ledsettings.multicolor_range)

        cmap.update_multicolor(app_state.ledsettings.multicolor_range, app_state.ledsettings.multicolor)

        return jsonify(success=True)

    if setting_name == "remove_multicolor":
        app_state.ledsettings.deletecolor(int(value) + 1)
        cmap.update_multicolor(app_state.ledsettings.multicolor_range, app_state.ledsettings.multicolor)
        return jsonify(success=True, reload=True)

    if setting_name == "multicolor":
        rgb = wc.hex_to_rgb("#" + value)
        app_state.ledsettings.multicolor[int(second_value)][0] = rgb[0]
        app_state.ledsettings.multicolor[int(second_value)][1] = rgb[1]
        app_state.ledsettings.multicolor[int(second_value)][2] = rgb[2]

        app_state.usersettings.change_setting_value("multicolor", app_state.ledsettings.multicolor)

        cmap.update_multicolor(app_state.ledsettings.multicolor_range, app_state.ledsettings.multicolor)

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "multicolor_range_left":
        app_state.ledsettings.multicolor_range[int(second_value)][0] = int(value)
        app_state.usersettings.change_setting_value("multicolor_range", app_state.ledsettings.multicolor_range)

        cmap.update_multicolor(app_state.ledsettings.multicolor_range, app_state.ledsettings.multicolor)

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "multicolor_range_right":
        app_state.ledsettings.multicolor_range[int(second_value)][1] = int(value)
        app_state.usersettings.change_setting_value("multicolor_range", app_state.ledsettings.multicolor_range)

        cmap.update_multicolor(app_state.ledsettings.multicolor_range, app_state.ledsettings.multicolor)

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "remove_all_multicolors":
        app_state.ledsettings.multicolor.clear()
        app_state.ledsettings.multicolor_range.clear()

        app_state.usersettings.change_setting_value("multicolor", app_state.ledsettings.multicolor)
        app_state.usersettings.change_setting_value("multicolor_range", app_state.ledsettings.multicolor_range)
        return jsonify(success=True)

    if setting_name == "rainbow_offset":
        app_state.ledsettings.rainbow_offset = int(value)
        app_state.usersettings.change_setting_value("rainbow_offset",
                                                       int(app_state.ledsettings.rainbow_offset))
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "rainbow_scale":
        app_state.ledsettings.rainbow_scale = int(value)
        app_state.usersettings.change_setting_value("rainbow_scale",
                                                       int(app_state.ledsettings.rainbow_scale))
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "rainbow_timeshift":
        app_state.ledsettings.rainbow_timeshift = int(value)
        app_state.usersettings.change_setting_value("rainbow_timeshift",
                                                       int(app_state.ledsettings.rainbow_timeshift))
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "rainbow_colormap":
        app_state.ledsettings.rainbow_colormap = value
        app_state.usersettings.change_setting_value("rainbow_colormap",
                                                       app_state.ledsettings.rainbow_colormap)
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "velocityrainbow_offset":
        app_state.ledsettings.velocityrainbow_offset = int(value)
        app_state.usersettings.change_setting_value("velocityrainbow_offset",
                                                       int(app_state.ledsettings.velocityrainbow_offset))
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "velocityrainbow_scale":
        app_state.ledsettings.velocityrainbow_scale = int(value)
        app_state.usersettings.change_setting_value("velocityrainbow_scale",
                                                       int(app_state.ledsettings.velocityrainbow_scale))
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "velocityrainbow_curve":
        app_state.ledsettings.velocityrainbow_curve = int(value)
        app_state.usersettings.change_setting_value("velocityrainbow_curve",
                                                       int(app_state.ledsettings.velocityrainbow_curve))
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "velocityrainbow_colormap":
        app_state.ledsettings.velocityrainbow_colormap = value
        app_state.usersettings.change_setting_value("velocityrainbow_colormap",
                                                       app_state.ledsettings.velocityrainbow_colormap)
        return jsonify(success=True, reload_sequence=reload_sequence)


    if setting_name == "speed_slowest_color":
        rgb = wc.hex_to_rgb("#" + value)
        app_state.ledsettings.speed_slowest["red"] = rgb[0]
        app_state.ledsettings.speed_slowest["green"] = rgb[1]
        app_state.ledsettings.speed_slowest["blue"] = rgb[2]

        app_state.usersettings.change_setting_value("speed_slowest_red", rgb[0])
        app_state.usersettings.change_setting_value("speed_slowest_green", rgb[1])
        app_state.usersettings.change_setting_value("speed_slowest_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "speed_fastest_color":
        rgb = wc.hex_to_rgb("#" + value)
        app_state.ledsettings.speed_fastest["red"] = rgb[0]
        app_state.ledsettings.speed_fastest["green"] = rgb[1]
        app_state.ledsettings.speed_fastest["blue"] = rgb[2]

        app_state.usersettings.change_setting_value("speed_fastest_red", rgb[0])
        app_state.usersettings.change_setting_value("speed_fastest_green", rgb[1])
        app_state.usersettings.change_setting_value("speed_fastest_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "gradient_start_color":
        rgb = wc.hex_to_rgb("#" + value)
        app_state.ledsettings.gradient_start["red"] = rgb[0]
        app_state.ledsettings.gradient_start["green"] = rgb[1]
        app_state.ledsettings.gradient_start["blue"] = rgb[2]

        app_state.usersettings.change_setting_value("gradient_start_red", rgb[0])
        app_state.usersettings.change_setting_value("gradient_start_green", rgb[1])
        app_state.usersettings.change_setting_value("gradient_start_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "gradient_end_color":
        rgb = wc.hex_to_rgb("#" + value)
        app_state.ledsettings.gradient_end["red"] = rgb[0]
        app_state.ledsettings.gradient_end["green"] = rgb[1]
        app_state.ledsettings.gradient_end["blue"] = rgb[2]

        app_state.usersettings.change_setting_value("gradient_end_red", rgb[0])
        app_state.usersettings.change_setting_value("gradient_end_green", rgb[1])
        app_state.usersettings.change_setting_value("gradient_end_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "speed_max_notes":
        app_state.ledsettings.speed_max_notes = int(value)
        app_state.usersettings.change_setting_value("speed_max_notes", int(value))

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "speed_period_in_seconds":
        app_state.ledsettings.speed_period_in_seconds = float(value)
        app_state.usersettings.change_setting_value("speed_period_in_seconds", float(value))

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "key_in_scale_color":
        rgb = wc.hex_to_rgb("#" + value)
        app_state.ledsettings.key_in_scale["red"] = rgb[0]
        app_state.ledsettings.key_in_scale["green"] = rgb[1]
        app_state.ledsettings.key_in_scale["blue"] = rgb[2]

        app_state.usersettings.change_setting_value("key_in_scale_red", rgb[0])
        app_state.usersettings.change_setting_value("key_in_scale_green", rgb[1])
        app_state.usersettings.change_setting_value("key_in_scale_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "key_not_in_scale_color":
        rgb = wc.hex_to_rgb("#" + value)
        app_state.ledsettings.key_not_in_scale["red"] = rgb[0]
        app_state.ledsettings.key_not_in_scale["green"] = rgb[1]
        app_state.ledsettings.key_not_in_scale["blue"] = rgb[2]

        app_state.usersettings.change_setting_value("key_not_in_scale_red", rgb[0])
        app_state.usersettings.change_setting_value("key_not_in_scale_green", rgb[1])
        app_state.usersettings.change_setting_value("key_not_in_scale_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "scale_key":
        app_state.ledsettings.scale_key = int(value)
        app_state.usersettings.change_setting_value("scale_key", int(value))

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "next_step":
        app_state.ledsettings.set_sequence(0, 1, False)
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "set_sequence":
        if int(value) == 0:
            menu = app_state.ledsettings.menu
            ledstrip = app_state.ledsettings.ledstrip
            app_state.ledsettings.__init__(app_state.usersettings)
            app_state.ledsettings.menu = menu
            app_state.ledsettings.ledstrip = ledstrip
            app_state.ledsettings.sequence_active = False
        else:
            app_state.ledsettings.set_sequence(int(value) - 1, 0)
        app_state.ledsettings.incoming_setting_change = True
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "change_sequence_name":
        sequences_tree = minidom.parse("config/sequences.xml")
        sequence_to_edit = "sequence_" + str(value)

        sequences_tree.getElementsByTagName(sequence_to_edit)[
            0].getElementsByTagName("settings")[
            0].getElementsByTagName("sequence_name")[0].firstChild.nodeValue = str(second_value)

        pretty_save("config/sequences.xml", sequences_tree)

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "change_step_value":
        sequences_tree = minidom.parse("config/sequences.xml")
        sequence_to_edit = "sequence_" + str(value)

        sequences_tree.getElementsByTagName(sequence_to_edit)[
            0].getElementsByTagName("settings")[
            0].getElementsByTagName("next_step")[0].firstChild.nodeValue = str(second_value)

        pretty_save("config/sequences.xml", sequences_tree)

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "change_step_activation_method":
        sequences_tree = minidom.parse("config/sequences.xml")
        sequence_to_edit = "sequence_" + str(value)

        sequences_tree.getElementsByTagName(sequence_to_edit)[
            0].getElementsByTagName("settings")[
            0].getElementsByTagName("control_number")[0].firstChild.nodeValue = str(second_value)

        pretty_save("config/sequences.xml", sequences_tree)

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "add_sequence":
        sequences_tree = minidom.parse("config/sequences.xml")

        sequences_amount = 1
        while True:
            if len(sequences_tree.getElementsByTagName("sequence_" + str(sequences_amount))) == 0:
                break
            sequences_amount += 1

        settings = sequences_tree.createElement("settings")

        control_number = sequences_tree.createElement("control_number")
        control_number.appendChild(sequences_tree.createTextNode("0"))
        settings.appendChild(control_number)

        next_step = sequences_tree.createElement("next_step")
        next_step.appendChild(sequences_tree.createTextNode("1"))
        settings.appendChild(next_step)

        sequence_name = sequences_tree.createElement("sequence_name")
        sequence_name.appendChild(sequences_tree.createTextNode("Sequence " + str(sequences_amount)))
        settings.appendChild(sequence_name)

        step = sequences_tree.createElement("step_1")

        color = sequences_tree.createElement("color")
        color.appendChild(sequences_tree.createTextNode("RGB"))
        step.appendChild(color)

        red = sequences_tree.createElement("Red")
        red.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(red)

        green = sequences_tree.createElement("Green")
        green.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(green)

        blue = sequences_tree.createElement("Blue")
        blue.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(blue)

        light_mode = sequences_tree.createElement("light_mode")
        light_mode.appendChild(sequences_tree.createTextNode("Normal"))
        step.appendChild(light_mode)

        element = sequences_tree.createElement("sequence_" + str(sequences_amount))
        element.appendChild(settings)
        element.appendChild(step)

        sequences_tree.getElementsByTagName("list")[0].appendChild(element)

        pretty_save("config/sequences.xml", sequences_tree)
        app_state.ledsettings.incoming_setting_change = True
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "remove_sequence":
        sequences_tree = minidom.parse("config/sequences.xml")

        # removing sequence node
        nodes = sequences_tree.getElementsByTagName("sequence_" + str(value))
        for node in nodes:
            parent = node.parentNode
            parent.removeChild(node)

        # changing nodes tag names
        i = 1
        for sequence in sequences_tree.getElementsByTagName("list")[0].childNodes:
            if sequence.nodeType == 1:
                sequences_tree.getElementsByTagName(sequence.nodeName)[0].tagName = "sequence_" + str(i)
                i += 1

        pretty_save("config/sequences.xml", sequences_tree)
        app_state.ledsettings.incoming_setting_change = True
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "add_step":
        sequences_tree = minidom.parse("config/sequences.xml")

        step_amount = 1
        while True:
            if (len(sequences_tree.getElementsByTagName("sequence_" + str(value))[0].getElementsByTagName(
                    "step_" + str(step_amount))) == 0):
                break
            step_amount += 1

        step = sequences_tree.createElement("step_" + str(step_amount))

        color = sequences_tree.createElement("color")

        color.appendChild(sequences_tree.createTextNode("RGB"))
        step.appendChild(color)

        red = sequences_tree.createElement("Red")
        red.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(red)

        green = sequences_tree.createElement("Green")
        green.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(green)

        blue = sequences_tree.createElement("Blue")
        blue.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(blue)

        light_mode = sequences_tree.createElement("light_mode")
        light_mode.appendChild(sequences_tree.createTextNode("Normal"))
        step.appendChild(light_mode)

        sequences_tree.getElementsByTagName("sequence_" + str(value))[0].appendChild(step)

        pretty_save("config/sequences.xml", sequences_tree)
        app_state.ledsettings.incoming_setting_change = True
        return jsonify(success=True, reload_sequence=reload_sequence, reload_steps_list=True,
                       set_sequence_step_number=step_amount)

    # remove node list with a tag name "step_" + str(value), and change tag names to maintain order
    if setting_name == "remove_step":

        second_value = int(second_value)
        second_value += 1

        sequences_tree = minidom.parse("config/sequences.xml")

        # removing step node
        nodes = sequences_tree.getElementsByTagName("sequence_" + str(value))[0].getElementsByTagName(
            "step_" + str(second_value))
        for node in nodes:
            parent = node.parentNode
            parent.removeChild(node)

        # changing nodes tag names
        i = 1
        for step in sequences_tree.getElementsByTagName("sequence_" + str(value))[0].childNodes:
            if step.nodeType == 1 and step.tagName != "settings":
                sequences_tree.getElementsByTagName("sequence_" + str(value))[0].getElementsByTagName(step.nodeName)[
                    0].tagName = "step_" + str(i)
                i += 1

        pretty_save("config/sequences.xml", sequences_tree)
        app_state.ledsettings.incoming_setting_change = True
        return jsonify(success=True, reload_sequence=reload_sequence, reload_steps_list=True)

    # saving current led settings as sequence step
    if setting_name == "save_led_settings_to_step" and second_value != "":

        # remove node and child under "sequence_" + str(value) and "step_" + str(second_value)
        sequences_tree = minidom.parse("config/sequences.xml")

        second_value = int(second_value)
        second_value += 1

        nodes = sequences_tree.getElementsByTagName("sequence_" + str(value))[0].getElementsByTagName(
            "step_" + str(second_value))
        for node in nodes:
            parent = node.parentNode
            parent.removeChild(node)

        # create new step node
        step = sequences_tree.createElement("step_" + str(second_value))

        # load color mode from app_state.ledsettings and put it into step node
        color_mode = sequences_tree.createElement("color")
        color_mode.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.color_mode)))
        step.appendChild(color_mode)

        # load mode from app_state.ledsettings and put it into step node
        mode = sequences_tree.createElement("light_mode")
        mode.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.mode)))
        step.appendChild(mode)

        # if mode is equal "Fading" or "Velocity", load fadingspeed from ledsettings and put it into step node
        if app_state.ledsettings.mode in ["Fading", "Velocity"]:
            fadingspeed = sequences_tree.createElement("fadingspeed")
            fadingspeed.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.fadingspeed)))
            step.appendChild(fadingspeed)

        # if color_mode is equal to "Single" load color from app_state.ledsettings and put it into step node
        if app_state.ledsettings.color_mode == "Single":
            red = sequences_tree.createElement("Red")
            red.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.red)))
            step.appendChild(red)

            green = sequences_tree.createElement("Green")
            green.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.green)))
            step.appendChild(green)

            blue = sequences_tree.createElement("Blue")
            blue.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.blue)))
            step.appendChild(blue)

        # if color_mode is equal to "Multicolor" load colors from app_state.ledsettings and put it into step node
        if app_state.ledsettings.color_mode == "Multicolor":
            # load value from app_state.ledsettings.multicolor
            multicolor = app_state.ledsettings.multicolor

            # loop through multicolor object and add each color to step node
            # under "sequence_"+str(value) with tag name "color_"+str(i)
            for i in range(len(multicolor)):
                color = sequences_tree.createElement("color_" + str(i + 1))
                new_multicolor = str(multicolor[i])
                new_multicolor = new_multicolor.replace("[", "")
                new_multicolor = new_multicolor.replace("]", "")

                color.appendChild(sequences_tree.createTextNode(new_multicolor))
                step.appendChild(color)

            # same as above but with multicolor_range and "color_range_"+str(i)
            multicolor_range = app_state.ledsettings.multicolor_range
            for i in range(len(multicolor_range)):
                color_range = sequences_tree.createElement("color_range_" + str(i + 1))
                new_multicolor_range = str(multicolor_range[i])

                new_multicolor_range = new_multicolor_range.replace("[", "")
                new_multicolor_range = new_multicolor_range.replace("]", "")
                color_range.appendChild(sequences_tree.createTextNode(new_multicolor_range))
                step.appendChild(color_range)

        # if color_mode is equal to "Rainbow" load colors from app_state.ledsettings and put it into step node
        if app_state.ledsettings.color_mode == "Rainbow":
            # load values rainbow_offset, rainbow_scale and rainbow_timeshift from app_state.ledsettings and put them into step node under Offset, Scale and Timeshift
            rainbow_offset = sequences_tree.createElement("Offset")
            rainbow_offset.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.rainbow_offset)))
            step.appendChild(rainbow_offset)

            rainbow_scale = sequences_tree.createElement("Scale")
            rainbow_scale.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.rainbow_scale)))
            step.appendChild(rainbow_scale)

            rainbow_timeshift = sequences_tree.createElement("Timeshift")
            rainbow_timeshift.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.rainbow_timeshift)))
            step.appendChild(rainbow_timeshift)

            rainbow_colormap = sequences_tree.createElement("Colormap")
            rainbow_colormap.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.rainbow_colormap)))
            step.appendChild(rainbow_colormap)

        # if color_mode is equal to "VelocityRainbow" load colors from app_state.ledsettings and put it into step node
        if app_state.ledsettings.color_mode == "VelocityRainbow":
            velocityrainbow_offset = sequences_tree.createElement("Offset")
            velocityrainbow_offset.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.velocityrainbow_offset)))
            step.appendChild(velocityrainbow_offset)

            velocityrainbow_scale = sequences_tree.createElement("Scale")
            velocityrainbow_scale.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.velocityrainbow_scale)))
            step.appendChild(velocityrainbow_scale)

            velocityrainbow_curve = sequences_tree.createElement("Curve")
            velocityrainbow_curve.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.velocityrainbow_curve)))
            step.appendChild(velocityrainbow_curve)

            velocityrainbow_colormap = sequences_tree.createElement("Colormap")
            velocityrainbow_colormap.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.velocityrainbow_colormap)))
            step.appendChild(velocityrainbow_colormap)

        # if color_mode is equal to "Speed" load colors from app_state.ledsettings and put it into step node
        if app_state.ledsettings.color_mode == "Speed":
            # load values speed_slowest["red"] etc. from app_state.ledsettings and put them under speed_slowest_red etc
            speed_slowest_red = sequences_tree.createElement("speed_slowest_red")
            speed_slowest_red.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.speed_slowest["red"])))
            step.appendChild(speed_slowest_red)

            speed_slowest_green = sequences_tree.createElement("speed_slowest_green")
            speed_slowest_green.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.speed_slowest["green"])))
            step.appendChild(speed_slowest_green)

            speed_slowest_blue = sequences_tree.createElement("speed_slowest_blue")
            speed_slowest_blue.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.speed_slowest["blue"])))
            step.appendChild(speed_slowest_blue)

            # same as above but with "fastest"
            speed_fastest_red = sequences_tree.createElement("speed_fastest_red")
            speed_fastest_red.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.speed_fastest["red"])))
            step.appendChild(speed_fastest_red)

            speed_fastest_green = sequences_tree.createElement("speed_fastest_green")
            speed_fastest_green.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.speed_fastest["green"])))
            step.appendChild(speed_fastest_green)

            speed_fastest_blue = sequences_tree.createElement("speed_fastest_blue")
            speed_fastest_blue.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.speed_fastest["blue"])))
            step.appendChild(speed_fastest_blue)

            # load "speed_max_notes" and "speed_period_in_seconds" values from app_state.ledsettings
            # and put them under speed_max_notes and speed_period_in_seconds

            speed_max_notes = sequences_tree.createElement("speed_max_notes")
            speed_max_notes.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.speed_max_notes)))
            step.appendChild(speed_max_notes)

            speed_period_in_seconds = sequences_tree.createElement("speed_period_in_seconds")
            speed_period_in_seconds.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.speed_period_in_seconds)))
            step.appendChild(speed_period_in_seconds)

        # if color_mode is equal to "Gradient" load colors from app_state.ledsettings and put it into step node
        if app_state.ledsettings.color_mode == "Gradient":
            # load values gradient_start_red etc from app_state.ledsettings and put them under gradient_start_red etc
            gradient_start_red = sequences_tree.createElement("gradient_start_red")
            gradient_start_red.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.gradient_start["red"])))
            step.appendChild(gradient_start_red)

            gradient_start_green = sequences_tree.createElement("gradient_start_green")
            gradient_start_green.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.gradient_start["green"])))
            step.appendChild(gradient_start_green)

            gradient_start_blue = sequences_tree.createElement("gradient_start_blue")
            gradient_start_blue.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.gradient_start["blue"])))
            step.appendChild(gradient_start_blue)

            # same as above but with gradient_end
            gradient_end_red = sequences_tree.createElement("gradient_end_red")
            gradient_end_red.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.gradient_end["red"])))
            step.appendChild(gradient_end_red)

            gradient_end_green = sequences_tree.createElement("gradient_end_green")
            gradient_end_green.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.gradient_end["green"])))
            step.appendChild(gradient_end_green)

            gradient_end_blue = sequences_tree.createElement("gradient_end_blue")
            gradient_end_blue.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.gradient_end["blue"])))
            step.appendChild(gradient_end_blue)

        # if color_mode is equal to "Scale" load colors from app_state.ledsettings and put it into step node
        if app_state.ledsettings.color_mode == "Scale":
            # load values key_in_scale_red etc from app_state.ledsettings and put them under key_in_scale_red etc
            key_in_scale_red = sequences_tree.createElement("key_in_scale_red")
            key_in_scale_red.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.key_in_scale["red"])))
            step.appendChild(key_in_scale_red)

            key_in_scale_green = sequences_tree.createElement("key_in_scale_green")
            key_in_scale_green.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.key_in_scale["green"])))
            step.appendChild(key_in_scale_green)

            key_in_scale_blue = sequences_tree.createElement("key_in_scale_blue")
            key_in_scale_blue.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.key_in_scale["blue"])))
            step.appendChild(key_in_scale_blue)

            # same as above but with key_not_in_scale
            key_not_in_scale_red = sequences_tree.createElement("key_not_in_scale_red")
            key_not_in_scale_red.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.key_not_in_scale["red"])))
            step.appendChild(key_not_in_scale_red)

            key_not_in_scale_green = sequences_tree.createElement("key_not_in_scale_green")
            key_not_in_scale_green.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.key_not_in_scale["green"])))
            step.appendChild(key_not_in_scale_green)

            key_not_in_scale_blue = sequences_tree.createElement("key_not_in_scale_blue")
            key_not_in_scale_blue.appendChild(
                sequences_tree.createTextNode(str(app_state.ledsettings.key_not_in_scale["blue"])))
            step.appendChild(key_not_in_scale_blue)

            scale_key = sequences_tree.createElement("scale_key")
            scale_key.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.scale_key)))
            step.appendChild(scale_key)

        try:
            sequences_tree.getElementsByTagName("sequence_" + str(value))[
                0].insertBefore(step,
                                sequences_tree.getElementsByTagName("sequence_" + str(value))[
                                    0].getElementsByTagName("step_" + str(second_value + 1))[0])
        except:
            sequences_tree.getElementsByTagName("sequence_" + str(value))[0].appendChild(step)

        pretty_save("config/sequences.xml", sequences_tree)

        app_state.ledsettings.incoming_setting_change = True

        return jsonify(success=True, reload_sequence=reload_sequence, reload_steps_list=True)

    if setting_name == "screen_on":
        if int(value) == 0:
            app_state.menu.disable_screen()
        else:
            app_state.menu.enable_screen()

    if setting_name == "reset_to_default":
        app_state.usersettings.reset_to_default()

    if setting_name == "restart_rpi":
        app_state.platform.reboot()

    if setting_name == "restart_visualizer":
        app_state.platform.restart_visualizer()

    if setting_name == "turnoff_rpi":
        app_state.platform.shutdown()

    if setting_name == "update_rpi":
        app_state.platform.update_visualizer()

    if setting_name == "connect_ports":
        app_state.midiports.connectall()
        return jsonify(success=True, reload_ports=True)

    if setting_name == "disconnect_ports":
        call("sudo aconnect -x", shell=True)
        return jsonify(success=True, reload_ports=True)

    if setting_name == "restart_rtp":
        app_state.platform.restart_rtpmidid()

    if setting_name == "show_midi_events":
        value = int(value == 'true')
        app_state.usersettings.change_setting_value("midi_logging", value)

    if setting_name == "multicolor_iteration":
        value = int(value == 'true')
        app_state.usersettings.change_setting_value("multicolor_iteration", value)
        app_state.ledsettings.multicolor_iteration = value

    if setting_name == "start_recording":
        app_state.saving.start_recording()
        return jsonify(success=True, reload_songs=True)

    if setting_name == "cancel_recording":
        app_state.saving.cancel_recording()
        return jsonify(success=True, reload_songs=True)

    if setting_name == "save_recording":
        now = datetime.datetime.now()
        current_date = now.strftime("%Y-%m-%d %H:%M")
        app_state.saving.save(current_date)
        return jsonify(success=True, reload_songs=True)

    if setting_name == "songs_per_page":
        value = int(value)
        app_state.usersettings.change_setting_value("songs_per_page", value)
        app_state.learning.songs_per_page = value
        return jsonify(success=True)

    if setting_name == "sort_by":
        new_sort = str(value)
        app_state.usersettings.change_setting_value("sort_by", new_sort)
        app_state.learning.sort_by = new_sort
        return jsonify(success=True)

    if setting_name == "change_song_name":
        if os.path.exists("Songs/" + second_value):
            return jsonify(success=False, reload_songs=True, error=second_value + " already exists")

        if "_main" in value:
            search_name = value.replace("_main.mid", "")
            for fname in os.listdir('Songs'):
                if search_name in fname:
                    new_name = second_value.replace(".mid", "") + fname.replace(search_name, "")
                    os.rename('Songs/' + fname, 'Songs/' + new_name)
        else:
            os.rename('Songs/' + value, 'Songs/' + second_value)
            os.rename('Songs/cache/' + value + ".p", 'Songs/cache/' + second_value + ".p")

        return jsonify(success=True, reload_songs=True)

    if setting_name == "remove_song":
        if "_main" in value:
            name_no_suffix = value.replace("_main.mid", "")
            for fname in os.listdir('Songs'):
                if name_no_suffix in fname:
                    os.remove("Songs/" + fname)
        else:
            os.remove("Songs/" + value)

            file_types = [".musicxml", ".xml", ".mxl", ".abc"]
            for file_type in file_types:
                try:
                    os.remove("Songs/" + value.replace(".mid", file_type))
                except:
                    pass

            try:
                os.remove("Songs/cache/" + value + ".p")
            except:
                logger.info("No cache file for " + value)

        return jsonify(success=True, reload_songs=True)

    if setting_name == "download_song":
        if "_main" in value:
            zipObj = ZipFile("Songs/" + value.replace(".mid", "") + ".zip", 'w')
            name_no_suffix = value.replace("_main.mid", "")
            songs_count = 0
            for fname in os.listdir('Songs'):
                if name_no_suffix in fname and ".zip" not in fname:
                    songs_count += 1
                    zipObj.write("Songs/" + fname)
            zipObj.close()
            if songs_count == 1:
                os.remove("Songs/" + value.replace(".mid", "") + ".zip")
                return send_file(safe_join("../Songs/" + value), mimetype='application/x-csv',
                                 download_name=value,
                                 as_attachment=True)
            else:
                return send_file(safe_join("../Songs/" + value.replace(".mid", "")) + ".zip",
                                 mimetype='application/x-csv',
                                 download_name=value.replace(".mid", "") + ".zip", as_attachment=True)
        else:
            return send_file(safe_join("../Songs/" + value), mimetype='application/x-csv', download_name=value,
                             as_attachment=True)

    if setting_name == "download_sheet_music":
        file_types = [".musicxml", ".xml", ".mxl", ".abc"]
        i = 0
        while i < len(file_types):
            try:
                new_name = value.replace(".mid", file_types[i])
                return send_file(safe_join("../Songs/" + new_name), mimetype='application/x-csv',
                                 download_name=new_name,
                                 as_attachment=True)
            except:
                i += 1
        app_state.learning.convert_midi_to_abc(value)
        try:
            return send_file(safe_join("../Songs/", value.replace(".mid", ".abc")), mimetype='application/x-csv',
                             download_name=value.replace(".mid", ".abc"), as_attachment=True)
        except:
            logger.warning("Converting failed")

    if setting_name == "start_midi_play":
        app_state.saving.t = threading.Thread(target=play_midi, args=(value, app_state.midiports,
                                                                         app_state.saving, app_state.menu,
                                                                         app_state.ledsettings,
                                                                         app_state.ledstrip))
        app_state.saving.t.start()

        return jsonify(success=True, reload_songs=True)

    if setting_name == "stop_midi_play":
        app_state.saving.is_playing_midi.clear()
        fastColorWipe(app_state.ledstrip.strip, True, app_state.ledsettings)

        return jsonify(success=True, reload_songs=True)

    if setting_name == "learning_load_song":
        app_state.learning.t = threading.Thread(target=app_state.learning.load_midi, args=(value,))
        app_state.learning.t.start()

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "start_learning_song":
        app_state.learning.t = threading.Thread(target=app_state.learning.learn_midi)
        app_state.learning.t.start()

        return jsonify(success=True)

    if setting_name == "stop_learning_song":
        app_state.learning.is_started_midi = False
        fastColorWipe(app_state.ledstrip.strip, True, app_state.ledsettings)

        return jsonify(success=True)

    if setting_name == "change_practice":
        value = int(value)
        app_state.learning.practice = value
        app_state.learning.practice = clamp(app_state.learning.practice, 0,
                                               len(app_state.learning.practiceList) - 1)
        app_state.usersettings.change_setting_value("practice", app_state.learning.practice)

        return jsonify(success=True)

    if setting_name == "change_tempo":
        value = int(value)
        app_state.learning.set_tempo = value
        app_state.learning.set_tempo = clamp(app_state.learning.set_tempo, 10, 200)
        app_state.usersettings.change_setting_value("set_tempo", app_state.learning.set_tempo)

        return jsonify(success=True)

    if setting_name == "change_hands":
        value = int(value)
        app_state.learning.hands = value
        app_state.learning.hands = clamp(app_state.learning.hands, 0, len(app_state.learning.handsList) - 1)
        app_state.usersettings.change_setting_value("hands", app_state.learning.hands)

        return jsonify(success=True)

    if setting_name == "change_mute_hand":
        value = int(value)
        app_state.learning.mute_hand = value
        app_state.learning.mute_hand = clamp(app_state.learning.mute_hand, 0,
                                                len(app_state.learning.mute_handList) - 1)
        app_state.usersettings.change_setting_value("mute_hand", app_state.learning.mute_hand)

        return jsonify(success=True)

    if setting_name == "learning_start_point":
        value = int(value)
        app_state.learning.start_point = value
        app_state.learning.start_point = clamp(app_state.learning.start_point, 0,
                                                  app_state.learning.end_point - 1)
        app_state.usersettings.change_setting_value("start_point", app_state.learning.start_point)
        app_state.learning.restart_learning()

        return jsonify(success=True)

    if setting_name == "learning_end_point":
        value = int(value)
        app_state.learning.end_point = value
        app_state.learning.end_point = clamp(app_state.learning.end_point, app_state.learning.start_point + 1,
                                                100)
        app_state.usersettings.change_setting_value("end_point", app_state.learning.end_point)
        app_state.learning.restart_learning()

        return jsonify(success=True)

    if setting_name == "set_current_time_as_start_point":
        app_state.learning.start_point = round(
            float(app_state.learning.current_idx * 100 / float(len(app_state.learning.song_tracks))), 3)
        app_state.learning.start_point = clamp(app_state.learning.start_point, 0,
                                                  app_state.learning.end_point - 1)
        app_state.usersettings.change_setting_value("start_point", app_state.learning.start_point)
        app_state.learning.restart_learning()

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "set_current_time_as_end_point":
        app_state.learning.end_point = round(
            float(app_state.learning.current_idx * 100 / float(len(app_state.learning.song_tracks))), 3)
        app_state.learning.end_point = clamp(app_state.learning.end_point, app_state.learning.start_point + 1,
                                                100)
        app_state.usersettings.change_setting_value("end_point", app_state.learning.end_point)
        app_state.learning.restart_learning()

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "change_handL_color":
        value = int(value)
        if app_state.learning.is_led_activeL == 1:
            app_state.learning.hand_colorL += value
            app_state.learning.hand_colorL = clamp(app_state.learning.hand_colorL, 0,
                                                    len(app_state.learning.hand_colorList) - 1)
            app_state.usersettings.change_setting_value("hand_colorL", app_state.learning.hand_colorL)

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "change_handR_color":
        value = int(value)
        if app_state.learning.is_led_activeR == 1:
            app_state.learning.hand_colorR += value
            app_state.learning.hand_colorR = clamp(app_state.learning.hand_colorR, 0,
                                                    len(app_state.learning.hand_colorList) - 1)
            app_state.usersettings.change_setting_value("hand_colorR", app_state.learning.hand_colorR)

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "change_wrong_notes":
        value = int(value)
        app_state.learning.show_wrong_notes = value
        app_state.usersettings.change_setting_value("show_wrong_notes", app_state.learning.show_wrong_notes)

    if setting_name == "change_future_notes":
        value = int(value)
        app_state.learning.show_future_notes = value
        app_state.usersettings.change_setting_value("show_future_notes", app_state.learning.show_future_notes)

    if setting_name == "change_learning_loop":
        value = int(value == 'true')
        app_state.learning.is_loop_active = value
        app_state.usersettings.change_setting_value("is_loop_active", app_state.learning.is_loop_active)

        return jsonify(success=True)

    if setting_name == "number_of_mistakes":
        value = int(value)
        app_state.learning.number_of_mistakes = value
        app_state.usersettings.change_setting_value("number_of_mistakes", app_state.learning.number_of_mistakes)

        return jsonify(success=True)

    if setting_name == "change_left_led_active":
        value = int(value == 'true')
        app_state.learning.is_led_activeL = value
        app_state.usersettings.change_setting_value("is_led_activeL", app_state.learning.is_led_activeL)
        if value == 0:
            app_state.learning.prev_hand_colorL = app_state.learning.hand_colorL
            app_state.usersettings.change_setting_value("prev_hand_colorL", app_state.learning.hand_colorL)
            app_state.learning.hand_colorL = 8
            app_state.usersettings.change_setting_value("hand_colorL", 8)
        else:
            app_state.usersettings.change_setting_value("hand_colorL", app_state.learning.prev_hand_colorL)
            app_state.learning.hand_colorL = app_state.learning.prev_hand_colorL
        
        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "change_right_led_active":
        value = int(value == 'true')
        app_state.learning.is_led_activeR = value
        app_state.usersettings.change_setting_value("is_led_activeR", app_state.learning.is_led_activeR)
        if value == 0:
            app_state.learning.prev_hand_colorR = app_state.learning.hand_colorR
            app_state.usersettings.change_setting_value("prev_hand_colorR", app_state.learning.hand_colorR)
            app_state.learning.hand_colorR = 8
            app_state.usersettings.change_setting_value("hand_colorR", 8)
        else:
            app_state.usersettings.change_setting_value("hand_colorR", app_state.learning.prev_hand_colorR)
            app_state.learning.hand_colorR = app_state.learning.prev_hand_colorR
        
        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "connect_to_wifi":
        logger.info("Controller: connecting to wifi")
        try:
            response = app_state.platform.connect_to_wifi(value, second_value, app_state.hotspot, app_state.usersettings)
        except:
            response = False

        return jsonify(success=response)

    if setting_name == "disconnect_wifi":
        try:
            app_state.platform.disconnect_from_wifi(app_state.hotspot, app_state.usersettings)
        except:
            return jsonify(success=False)

    if setting_name == "animation_delay":
        value = max(int(value), 0)
        app_state.menu.led_animation_delay = value
        if app_state.menu.led_animation_delay < 0:
            app_state.menu.led_animation_delay = 0
        app_state.usersettings.change_setting_value("led_animation_delay", app_state.menu.led_animation_delay)

        return jsonify(success=True)

    if setting_name == "led_animation":
        app_state.menu.led_animation = value
        app_state.usersettings.change_setting_value("led_animation", value)

        return jsonify(success=True)

    if setting_name == "led_gamma":
        app_state.usersettings.change_setting_value("led_gamma", value)
        app_state.ledstrip.change_gamma(float(value))

        return jsonify(success=True)

    if setting_name == "hotspot_password":
        new_password = str(value)
        if len(new_password) < 8:
            return jsonify(success=False, error="Password must be at least 8 characters long")
        success = app_state.platform.change_hotspot_password(new_password)
        if success:
            app_state.usersettings.change_setting_value("hotspot_password", new_password)
            return jsonify(success=True)
        else:
            return jsonify(success=False, error="Failed to change hotspot password")

    return jsonify(success=True)


@webinterface.route('/api/get_sequence_setting', methods=['GET'])
def get_sequence_setting():
    response = {}

    color_mode = app_state.ledsettings.color_mode

    light_mode = app_state.ledsettings.mode

    fading_speed = app_state.ledsettings.fadingspeed

    red = app_state.ledsettings.red
    green = app_state.ledsettings.green
    blue = app_state.ledsettings.blue
    led_color = wc.rgb_to_hex((int(red), int(green), int(blue)))

    multicolor = app_state.ledsettings.multicolor
    multicolor_range = app_state.ledsettings.multicolor_range

    rainbow_scale = app_state.ledsettings.rainbow_scale
    rainbow_offset = app_state.ledsettings.rainbow_offset
    rainbow_timeshift = app_state.ledsettings.rainbow_timeshift
    rainbow_colormap = app_state.ledsettings.rainbow_colormap

    velocityrainbow_scale = app_state.ledsettings.velocityrainbow_scale
    velocityrainbow_offset = app_state.ledsettings.velocityrainbow_offset
    velocityrainbow_curve = app_state.ledsettings.velocityrainbow_curve
    velocityrainbow_colormap = app_state.ledsettings.velocityrainbow_colormap

    speed_slowest_red = app_state.ledsettings.speed_slowest["red"]
    speed_slowest_green = app_state.ledsettings.speed_slowest["green"]
    speed_slowest_blue = app_state.ledsettings.speed_slowest["blue"]
    speed_slowest_color = wc.rgb_to_hex((int(speed_slowest_red), int(speed_slowest_green), int(speed_slowest_blue)))
    response["speed_slowest_color"] = speed_slowest_color

    speed_fastest_red = app_state.ledsettings.speed_fastest["red"]
    speed_fastest_green = app_state.ledsettings.speed_fastest["green"]
    speed_fastest_blue = app_state.ledsettings.speed_fastest["blue"]
    speed_fastest_color = wc.rgb_to_hex((int(speed_fastest_red), int(speed_fastest_green), int(speed_fastest_blue)))
    response["speed_fastest_color"] = speed_fastest_color

    gradient_start_red = app_state.ledsettings.gradient_start["red"]
    gradient_start_green = app_state.ledsettings.gradient_start["green"]
    gradient_start_blue = app_state.ledsettings.gradient_start["blue"]
    gradient_start_color = wc.rgb_to_hex((int(gradient_start_red), int(gradient_start_green), int(gradient_start_blue)))
    response["gradient_start_color"] = gradient_start_color

    gradient_end_red = app_state.ledsettings.gradient_end["red"]
    gradient_end_green = app_state.ledsettings.gradient_end["green"]
    gradient_end_blue = app_state.ledsettings.gradient_end["blue"]
    gradient_end_color = wc.rgb_to_hex((int(gradient_end_red), int(gradient_end_green), int(gradient_end_blue)))
    response["gradient_end_color"] = gradient_end_color

    key_in_scale_red = app_state.ledsettings.key_in_scale["red"]
    key_in_scale_green = app_state.ledsettings.key_in_scale["green"]
    key_in_scale_blue = app_state.ledsettings.key_in_scale["blue"]
    key_in_scale_color = wc.rgb_to_hex((int(key_in_scale_red), int(key_in_scale_green), int(key_in_scale_blue)))
    response["key_in_scale_color"] = key_in_scale_color

    key_not_in_scale_red = app_state.ledsettings.key_not_in_scale["red"]
    key_not_in_scale_green = app_state.ledsettings.key_not_in_scale["green"]
    key_not_in_scale_blue = app_state.ledsettings.key_not_in_scale["blue"]
    key_not_in_scale_color = wc.rgb_to_hex(
        (int(key_not_in_scale_red), int(key_not_in_scale_green), int(key_not_in_scale_blue)))
    response["key_not_in_scale_color"] = key_not_in_scale_color

    response["scale_key"] = app_state.ledsettings.scale_key

    response["led_color"] = led_color
    response["color_mode"] = color_mode
    response["light_mode"] = light_mode
    response["fading_speed"] = fading_speed
    response["multicolor"] = multicolor
    response["multicolor_range"] = multicolor_range
    response["rainbow_scale"] = rainbow_scale
    response["rainbow_offset"] = rainbow_offset
    response["rainbow_timeshift"] = rainbow_timeshift
    response["rainbow_colormap"] = rainbow_colormap
    response["velocityrainbow_scale"] = velocityrainbow_scale
    response["velocityrainbow_offset"] = velocityrainbow_offset
    response["velocityrainbow_curve"] = velocityrainbow_curve
    response["velocityrainbow_colormap"] = velocityrainbow_colormap
    response["speed_max_notes"] = app_state.ledsettings.speed_max_notes
    response["speed_period_in_seconds"] = app_state.ledsettings.speed_period_in_seconds
    return jsonify(response)


@webinterface.route('/api/get_idle_animation_settings', methods=['GET'])
def get_idle_animation_settings():
    response = {"led_animation_delay": app_state.usersettings.get_setting_value("led_animation_delay"),
                "led_animation": app_state.usersettings.get_setting_value("led_animation"),
                "led_animation_brightness_percent": app_state.ledsettings.led_animation_brightness_percent}
    return jsonify(response)

@webinterface.route('/api/get_settings', methods=['GET'])
def get_settings():
    response = {}

    red = app_state.usersettings.get_setting_value("red")
    green = app_state.usersettings.get_setting_value("green")
    blue = app_state.usersettings.get_setting_value("blue")
    led_color = wc.rgb_to_hex((int(red), int(green), int(blue)))

    backlight_red = app_state.usersettings.get_setting_value("backlight_red")
    backlight_green = app_state.usersettings.get_setting_value("backlight_green")
    backlight_blue = app_state.usersettings.get_setting_value("backlight_blue")
    backlight_color = wc.rgb_to_hex((int(backlight_red), int(backlight_green), int(backlight_blue)))

    sides_red = app_state.usersettings.get_setting_value("adjacent_red")
    sides_green = app_state.usersettings.get_setting_value("adjacent_green")
    sides_blue = app_state.usersettings.get_setting_value("adjacent_blue")
    sides_color = wc.rgb_to_hex((int(sides_red), int(sides_green), int(sides_blue)))

    light_mode = app_state.usersettings.get_setting_value("mode")
    fading_speed = app_state.usersettings.get_setting_value("fadingspeed")

    brightness = app_state.usersettings.get_setting_value("brightness_percent")
    backlight_brightness = app_state.usersettings.get_setting_value("backlight_brightness_percent")
    disable_backlight_on_idle = app_state.usersettings.get_setting_value("disable_backlight_on_idle")

    response["led_color"] = led_color
    response["light_mode"] = light_mode
    response["fading_speed"] = fading_speed

    response["brightness"] = brightness
    response["backlight_brightness"] = backlight_brightness
    response["backlight_color"] = backlight_color
    response["disable_backlight_on_idle"] = disable_backlight_on_idle
    response["led_gamma"] = app_state.usersettings.get_setting_value("led_gamma")

    response["sides_color_mode"] = app_state.usersettings.get_setting_value("adjacent_mode")
    response["sides_color"] = sides_color

    response["input_port"] = app_state.usersettings.get_setting_value("input_port")
    response["play_port"] = app_state.usersettings.get_setting_value("play_port")

    response["skipped_notes"] = app_state.usersettings.get_setting_value("skipped_notes")
    response["note_offsets"] = app_state.usersettings.get_setting_value("note_offsets")
    response["led_count"] = app_state.usersettings.get_setting_value("led_count")
    response["leds_per_meter"] = app_state.usersettings.get_setting_value("leds_per_meter")
    response["led_shift"] = app_state.usersettings.get_setting_value("shift")
    response["led_reverse"] = app_state.usersettings.get_setting_value("reverse")

    response["color_mode"] = app_state.usersettings.get_setting_value("color_mode")

    response["multicolor"] = app_state.usersettings.get_setting_value("multicolor")
    response["multicolor_range"] = app_state.usersettings.get_setting_value("multicolor_range")
    response["multicolor_iteration"] = app_state.usersettings.get_setting_value("multicolor_iteration")

    response["rainbow_offset"] = app_state.usersettings.get_setting_value("rainbow_offset")
    response["rainbow_scale"] = app_state.usersettings.get_setting_value("rainbow_scale")
    response["rainbow_timeshift"] = app_state.usersettings.get_setting_value("rainbow_timeshift")
    response["rainbow_colormap"] = app_state.usersettings.get_setting_value("rainbow_colormap")

    response["velocityrainbow_offset"] = app_state.usersettings.get_setting_value("velocityrainbow_offset")
    response["velocityrainbow_scale"] = app_state.usersettings.get_setting_value("velocityrainbow_scale")
    response["velocityrainbow_curve"] = app_state.usersettings.get_setting_value("velocityrainbow_curve")
    response["velocityrainbow_colormap"] = app_state.usersettings.get_setting_value("velocityrainbow_colormap")

    speed_slowest_red = app_state.usersettings.get_setting_value("speed_slowest_red")
    speed_slowest_green = app_state.usersettings.get_setting_value("speed_slowest_green")
    speed_slowest_blue = app_state.usersettings.get_setting_value("speed_slowest_blue")
    speed_slowest_color = wc.rgb_to_hex((int(speed_slowest_red), int(speed_slowest_green), int(speed_slowest_blue)))
    response["speed_slowest_color"] = speed_slowest_color

    speed_fastest_red = app_state.usersettings.get_setting_value("speed_fastest_red")
    speed_fastest_green = app_state.usersettings.get_setting_value("speed_fastest_green")
    speed_fastest_blue = app_state.usersettings.get_setting_value("speed_fastest_blue")
    speed_fastest_color = wc.rgb_to_hex((int(speed_fastest_red), int(speed_fastest_green), int(speed_fastest_blue)))
    response["speed_fastest_color"] = speed_fastest_color

    gradient_start_red = app_state.usersettings.get_setting_value("gradient_start_red")
    gradient_start_green = app_state.usersettings.get_setting_value("gradient_start_green")
    gradient_start_blue = app_state.usersettings.get_setting_value("gradient_start_blue")
    gradient_start_color = wc.rgb_to_hex((int(gradient_start_red), int(gradient_start_green), int(gradient_start_blue)))
    response["gradient_start_color"] = gradient_start_color

    gradient_end_red = app_state.usersettings.get_setting_value("gradient_end_red")
    gradient_end_green = app_state.usersettings.get_setting_value("gradient_end_green")
    gradient_end_blue = app_state.usersettings.get_setting_value("gradient_end_blue")
    gradient_end_color = wc.rgb_to_hex((int(gradient_end_red), int(gradient_end_green), int(gradient_end_blue)))
    response["gradient_end_color"] = gradient_end_color

    key_in_scale_red = app_state.usersettings.get_setting_value("key_in_scale_red")
    key_in_scale_green = app_state.usersettings.get_setting_value("key_in_scale_green")
    key_in_scale_blue = app_state.usersettings.get_setting_value("key_in_scale_blue")
    key_in_scale_color = wc.rgb_to_hex((int(key_in_scale_red), int(key_in_scale_green), int(key_in_scale_blue)))
    response["key_in_scale_color"] = key_in_scale_color

    key_not_in_scale_red = app_state.usersettings.get_setting_value("key_not_in_scale_red")
    key_not_in_scale_green = app_state.usersettings.get_setting_value("key_not_in_scale_green")
    key_not_in_scale_blue = app_state.usersettings.get_setting_value("key_not_in_scale_blue")
    key_not_in_scale_color = wc.rgb_to_hex(
        (int(key_not_in_scale_red), int(key_not_in_scale_green), int(key_not_in_scale_blue)))
    response["key_not_in_scale_color"] = key_not_in_scale_color

    response["scale_key"] = app_state.usersettings.get_setting_value("scale_key")

    response["speed_max_notes"] = app_state.usersettings.get_setting_value("speed_max_notes")
    response["speed_period_in_seconds"] = app_state.usersettings.get_setting_value("speed_period_in_seconds")
    response["hotspot_password"] = app_state.usersettings.get_setting_value("hotspot_password")

    return jsonify(response)


@webinterface.route('/api/get_recording_status', methods=['GET'])
def get_recording_status():
    response = {"input_port": app_state.usersettings.get_setting_value("input_port"),
                "play_port": app_state.usersettings.get_setting_value("play_port"),
                "isrecording": app_state.saving.is_recording, "isplaying": app_state.saving.is_playing_midi}

    return jsonify(response)


@webinterface.route('/api/get_learning_status', methods=['GET'])
def get_learning_status():
    response = {"loading": app_state.learning.loading,
                "practice": app_state.usersettings.get_setting_value("practice"),
                "hands": app_state.usersettings.get_setting_value("hands"),
                "mute_hand": app_state.usersettings.get_setting_value("mute_hand"),
                "start_point": app_state.usersettings.get_setting_value("start_point"),
                "end_point": app_state.usersettings.get_setting_value("end_point"),
                "set_tempo": app_state.usersettings.get_setting_value("set_tempo"),
                "hand_colorR": app_state.usersettings.get_setting_value("hand_colorR"),
                "hand_colorL": app_state.usersettings.get_setting_value("hand_colorL"),
                "prev_hand_colorR": app_state.usersettings.get_setting_value("prev_hand_colorR"),
                "prev_hand_colorL": app_state.usersettings.get_setting_value("prev_hand_colorL"),
                "show_wrong_notes": app_state.usersettings.get_setting_value("show_wrong_notes"),
                "show_future_notes": app_state.usersettings.get_setting_value("show_future_notes"),
                "hand_colorList": ast.literal_eval(app_state.usersettings.get_setting_value("hand_colorList")),
                "is_loop_active": ast.literal_eval(app_state.usersettings.get_setting_value("is_loop_active")),
                "number_of_mistakes": ast.literal_eval(app_state.usersettings.get_setting_value("number_of_mistakes")),
                "is_led_activeL": ast.literal_eval(app_state.usersettings.get_setting_value("is_led_activeL")),
                "is_led_activeR": ast.literal_eval(app_state.usersettings.get_setting_value("is_led_activeR"))}

    return jsonify(response)

@webinterface.route('/api/get_song_list_setting', methods=['GET'])
def get_song_list_setting():
    response = {"songs_per_page": app_state.usersettings.get_setting_value("songs_per_page"),
                "sort_by": app_state.usersettings.get_setting_value("sort_by")
    }
    return jsonify(response)

@webinterface.route('/api/get_songs', methods=['GET'])
def get_songs():
    page = request.args.get('page')
    page = int(page) - 1
    length = request.args.get('length')
    sortby = request.args.get('sortby')
    search = request.args.get('search')

    start = int(page) * int(length)

    songs_list_dict = {}

    path = 'Songs/'
    songs_list = os.listdir(path)
    songs_list = [os.path.join(path, i) for i in songs_list]

    songs_list = sorted(songs_list, key=os.path.getmtime)

    if sortby == "dateAsc":
        songs_list.reverse()

    if sortby == "nameAsc":
        songs_list.sort()

    if sortby == "nameDesc":
        songs_list.sort(reverse=True)

    i = 0
    total_songs = 0

    for song in songs_list:
        if "_#" in song or not song.endswith('.mid'):
            continue
        if search:
            if search.lower() not in song.lower():
                continue
        total_songs += 1

    max_page = int(math.ceil(total_songs / int(length)))

    for song in songs_list:
        song = song.replace("Songs/", "")
        date = os.path.getmtime("Songs/" + song)
        if "_#" in song or not song.endswith('.mid'):
            continue

        if search:
            if search.lower() not in song.lower():
                continue

        i += 1
        if i > int(start):
            songs_list_dict[song] = date

        if len(songs_list_dict) >= int(length):
            break

    return render_template('songs_list.html', len=len(songs_list_dict), songs_list_dict=songs_list_dict, page=page,
                           max_page=max_page, total_songs=total_songs)


@webinterface.route('/api/get_ports', methods=['GET'])
def get_ports():
    ports = mido.get_input_names()
    ports = list(dict.fromkeys(ports))
    response = {"ports_list": ports, "input_port": app_state.usersettings.get_setting_value("input_port"),
                "secondary_input_port": app_state.usersettings.get_setting_value("secondary_input_port"),
                "play_port": app_state.usersettings.get_setting_value("play_port"),
                "connected_ports": str(subprocess.check_output(["aconnect", "-i", "-l"])),
                "midi_logging": app_state.usersettings.get_setting_value("midi_logging")}

    return jsonify(response)


@webinterface.route('/api/switch_ports', methods=['GET'])
def switch_ports():
    active_input = app_state.usersettings.get_setting_value("input_port")
    secondary_input = app_state.usersettings.get_setting_value("secondary_input_port")
    app_state.midiports.change_port("inport", secondary_input)
    app_state.usersettings.change_setting_value("secondary_input_port", active_input)
    app_state.usersettings.change_setting_value("input_port", secondary_input)

    fastColorWipe(app_state.ledstrip.strip, True, app_state.ledsettings)

    return jsonify(success=True)


@webinterface.route('/api/get_sequences', methods=['GET'])
def get_sequences():
    response = {}
    sequences_list = []
    sequences_tree = minidom.parse("config/sequences.xml")
    i = 0
    while True:
        try:
            i += 1
            sequences_list.append(
                sequences_tree.getElementsByTagName("sequence_" + str(i))[0].getElementsByTagName(
                    "sequence_name")[
                    0].firstChild.nodeValue)
        except:
            break
    response["sequences_list"] = sequences_list
    response["sequence_number"] = app_state.ledsettings.sequence_number

    return jsonify(response)


@webinterface.route('/api/get_steps_list', methods=['GET'])
def get_steps_list():
    response = {}
    sequence = request.args.get('sequence')
    sequences_tree = minidom.parse("config/sequences.xml")
    steps_list = []
    i = 0

    for step in sequences_tree.getElementsByTagName("sequence_" + str(sequence))[0].childNodes:
        if step.nodeType == 1:
            if step.nodeName == "settings":
                response["control_number"] = step.getElementsByTagName("control_number")[0].firstChild.nodeValue
                response["next_step"] = step.getElementsByTagName("next_step")[0].firstChild.nodeValue
            else:
                steps_list.append(step.nodeName)

    response["steps_list"] = steps_list
    return jsonify(response)


@webinterface.route('/api/set_step_properties', methods=['GET'])
def set_step_properties():
    sequence = request.args.get('sequence')
    step = request.args.get('step')
    app_state.ledsettings.set_sequence(sequence, step, True)
    app_state.ledsettings.incoming_setting_change = True
    return jsonify(success=True)


@webinterface.route('/api/get_wifi_list', methods=['GET'])
def get_wifi_list():
    wifi_list = app_state.platform.get_wifi_networks()
    success, wifi_ssid, address = app_state.platform.get_current_connections()

    response = {"wifi_list": wifi_list,
                "connected_wifi": wifi_ssid,
                "connected_wifi_address": address}
    return jsonify(response)

@webinterface.route('/api/get_local_address', methods=['GET'])
def get_local_address():
    result = app_state.platform.get_local_address()
    if result["success"]:
        return jsonify({
            "success": True,
            "local_address": result["local_address"],
            "ip_address": result["ip_address"]
        })
    else:
        return jsonify({
            "success": False,
            "error": result["error"]
        }), 500

@webinterface.route('/api/change_local_address', methods=['POST'])
def change_local_address():
    new_name = request.json.get('new_name')
    if not new_name:
        return jsonify({"success": False, "error": "No name provided"}), 400

    try:
        success = app_state.platform.change_local_address(new_name)
        if success:
            return jsonify({"success": True, "new_address": f"{new_name}.local"})
        else:
            return jsonify({"success": False, "error": "Failed to change address"}), 500
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@webinterface.route('/api/get_logs', methods=['GET'])
def get_logs():
    last_logs = request.args.get('last_logs')
    return get_last_logs(last_logs)

@webinterface.route('/api/get_colormap_gradients', methods=['GET'])
def get_colormap_gradients():
    return jsonify(cmap.colormaps_preview)

# ---------------------- Profiles & Highscores API ----------------------
@webinterface.route('/api/get_profiles', methods=['GET'])
def api_get_profiles():
    if not hasattr(app_state, 'profile_manager'):
        return jsonify({"profiles": []})
    profiles = app_state.profile_manager.get_profiles()
    return jsonify({"profiles": profiles})

@webinterface.route('/api/create_profile', methods=['POST'])
def api_create_profile():
    if not hasattr(app_state, 'profile_manager'):
        abort(500, description="Profile manager not initialized")
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify(success=False, error="Name required"), 400
    try:
        profile_id = app_state.profile_manager.create_profile(name)
    except ValueError as ve:
        return jsonify(success=False, error=str(ve)), 400
    except Exception as e:
        logger.warning(f"Failed creating profile: {e}")
        return jsonify(success=False, error="Internal error"), 500
    return jsonify(success=True, profile={"id": profile_id, "name": name})

@webinterface.route('/api/delete_profile', methods=['POST'])
def api_delete_profile():
    if not hasattr(app_state, 'profile_manager'):
        abort(500, description="Profile manager not initialized")
    data = request.get_json(silent=True) or {}
    try:
        profile_id = int(data.get('profile_id'))
    except (TypeError, ValueError):
        return jsonify(success=False, error="profile_id must be integer"), 400
    try:
        app_state.profile_manager.delete_profile(profile_id)
        # If the deleted profile was the current one, clear it
        if getattr(app_state, 'current_profile_id', None) == profile_id:
            app_state.current_profile_id = None
        return jsonify(success=True)
    except Exception as e:
        logger.warning(f"Failed deleting profile {profile_id}: {e}")
        return jsonify(success=False, error="Internal error"), 500

@webinterface.route('/api/get_highscores', methods=['GET'])
def api_get_highscores():
    if not hasattr(app_state, 'profile_manager'):
        abort(500, description="Profile manager not initialized")
    profile_id = request.args.get('profile_id')
    if not profile_id:
        return jsonify(success=False, error="profile_id required"), 400
    try:
        profile_id = int(profile_id)
    except ValueError:
        return jsonify(success=False, error="profile_id must be integer"), 400
    highscores = app_state.profile_manager.get_highscores(profile_id)
    return jsonify(success=True, highscores=highscores)

@webinterface.route('/api/update_highscore', methods=['POST'])
def api_update_highscore():
    if not hasattr(app_state, 'profile_manager'):
        abort(500, description="Profile manager not initialized")
    data = request.get_json(silent=True) or {}
    try:
        profile_id = int(data.get('profile_id'))
        song_name = data.get('song_name', '')
        new_score = int(data.get('score'))
    except (TypeError, ValueError):
        return jsonify(success=False, error="Invalid payload"), 400
    changed = app_state.profile_manager.update_highscore(profile_id, song_name, new_score)
    return jsonify(success=True, updated=changed)
def pretty_print(dom):
    return '\n'.join([line for line in dom.toprettyxml(indent=' ' * 4).split('\n') if line.strip()])


def pretty_save(file_path, sequences_tree):
    with open(file_path, "w", encoding="utf8") as outfile:
        outfile.write(pretty_print(sequences_tree))

# Track currently selected profile on the backend for use by learning logic
@webinterface.route('/api/set_current_profile', methods=['POST'])
def api_set_current_profile():
    data = request.get_json(silent=True) or {}
    pid = data.get('profile_id')
    try:
        app_state.current_profile_id = int(pid) if pid is not None and pid != '' else None
    except (TypeError, ValueError):
        return jsonify(success=False, error="profile_id must be integer or empty"), 400
    return jsonify(success=True, profile_id=app_state.current_profile_id)

@webinterface.route('/api/get_current_profile', methods=['GET'])
def api_get_current_profile():
    return jsonify(success=True, profile_id=app_state.current_profile_id)
