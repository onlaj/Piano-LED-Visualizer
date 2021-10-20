from webinterface import webinterface
from flask import render_template, send_file, redirect, request, url_for, jsonify
from lib.functions import find_between, theaterChase, theaterChaseRainbow, sound_of_da_police, scanner, breathing, \
    rainbow, rainbowCycle, fastColorWipe, play_midi
import psutil
import threading
from neopixel import *
import webcolors as wc
import mido
from xml.dom import minidom
from subprocess import call
import subprocess
import datetime
import os
import math
from zipfile import ZipFile


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
        'memory_usage_used': psutil.virtual_memory()[3],
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
    second_value = request.args.get('second_value')
    disable_sequence = request.args.get('disable_sequence')

    if(disable_sequence == "true"):
        webinterface.ledsettings.__init__(webinterface.usersettings)
        webinterface.ledsettings.sequence_active = False

    if setting_name == "clean_ledstrip":
        fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

    if setting_name == "led_color":
        rgb = wc.hex_to_rgb("#" + value)

        webinterface.ledsettings.color_mode = "Single"

        webinterface.ledsettings.red = rgb[0]
        webinterface.ledsettings.green = rgb[1]
        webinterface.ledsettings.blue = rgb[2]

        webinterface.usersettings.change_setting_value("color_mode", webinterface.ledsettings.color_mode)
        webinterface.usersettings.change_setting_value("red", rgb[0])
        webinterface.usersettings.change_setting_value("green", rgb[1])
        webinterface.usersettings.change_setting_value("blue", rgb[2])

        return jsonify(success=True, reload_sequence=True)

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

    if setting_name == "color_mode":
        reload_sequence = True
        if(second_value == "no_reload"):
            reload_sequence = False

        webinterface.ledsettings.color_mode = value
        webinterface.usersettings.change_setting_value("color_mode", webinterface.ledsettings.color_mode)
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "add_multicolor":
        webinterface.ledsettings.addcolor()
        return jsonify(success=True, reload=True)

    if setting_name == "remove_multicolor":
        webinterface.ledsettings.deletecolor(int(value) + 1)
        return jsonify(success=True, reload=True)

    if setting_name == "multicolor":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.multicolor[int(second_value)][0] = rgb[0]
        webinterface.ledsettings.multicolor[int(second_value)][1] = rgb[1]
        webinterface.ledsettings.multicolor[int(second_value)][2] = rgb[2]

        webinterface.usersettings.change_setting_value("multicolor", webinterface.ledsettings.multicolor)

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "multicolor_range_left":
        webinterface.ledsettings.multicolor_range[int(second_value)][0] = int(value)
        webinterface.usersettings.change_setting_value("multicolor_range", webinterface.ledsettings.multicolor_range)

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "multicolor_range_right":
        webinterface.ledsettings.multicolor_range[int(second_value)][1] = int(value)
        webinterface.usersettings.change_setting_value("multicolor_range", webinterface.ledsettings.multicolor_range)

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "rainbow_offset":
        webinterface.ledsettings.rainbow_offset = int(value)
        webinterface.usersettings.change_setting_value("rainbow_offset",
                                                       int(webinterface.ledsettings.rainbow_offset))
        return jsonify(success=True, reload_sequence=True)

    if setting_name == "rainbow_scale":
        webinterface.ledsettings.rainbow_scale = int(value)
        webinterface.usersettings.change_setting_value("rainbow_scale",
                                                       int(webinterface.ledsettings.rainbow_scale))
        return jsonify(success=True, reload_sequence=True)

    if setting_name == "rainbow_timeshift":
        webinterface.ledsettings.rainbow_timeshift = int(value)
        webinterface.usersettings.change_setting_value("rainbow_timeshift",
                                                       int(webinterface.ledsettings.rainbow_timeshift))
        return jsonify(success=True, reload_sequence=True)

    if setting_name == "speed_slowest_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.speed_slowest["red"] = rgb[0]
        webinterface.ledsettings.speed_slowest["green"] = rgb[1]
        webinterface.ledsettings.speed_slowest["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("speed_slowest_red", rgb[0])
        webinterface.usersettings.change_setting_value("speed_slowest_green", rgb[1])
        webinterface.usersettings.change_setting_value("speed_slowest_blue", rgb[2])

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "speed_fastest_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.speed_fastest["red"] = rgb[0]
        webinterface.ledsettings.speed_fastest["green"] = rgb[1]
        webinterface.ledsettings.speed_fastest["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("speed_fastest_red", rgb[0])
        webinterface.usersettings.change_setting_value("speed_fastest_green", rgb[1])
        webinterface.usersettings.change_setting_value("speed_fastest_blue", rgb[2])

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "gradient_start_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.gradient_start["red"] = rgb[0]
        webinterface.ledsettings.gradient_start["green"] = rgb[1]
        webinterface.ledsettings.gradient_start["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("gradient_start_red", rgb[0])
        webinterface.usersettings.change_setting_value("gradient_start_green", rgb[1])
        webinterface.usersettings.change_setting_value("gradient_start_blue", rgb[2])

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "gradient_end_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.gradient_end["red"] = rgb[0]
        webinterface.ledsettings.gradient_end["green"] = rgb[1]
        webinterface.ledsettings.gradient_end["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("gradient_end_red", rgb[0])
        webinterface.usersettings.change_setting_value("gradient_end_green", rgb[1])
        webinterface.usersettings.change_setting_value("gradient_end_blue", rgb[2])

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "speed_max_notes":
        webinterface.ledsettings.speed_max_notes = int(value)
        webinterface.usersettings.change_setting_value("speed_max_notes", int(value))

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "speed_period_in_seconds":
        webinterface.ledsettings.speed_period_in_seconds = float(value)
        webinterface.usersettings.change_setting_value("speed_period_in_seconds", float(value))

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "key_in_scale_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.key_in_scale["red"] = rgb[0]
        webinterface.ledsettings.key_in_scale["green"] = rgb[1]
        webinterface.ledsettings.key_in_scale["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("key_in_scale_red", rgb[0])
        webinterface.usersettings.change_setting_value("key_in_scale_green", rgb[1])
        webinterface.usersettings.change_setting_value("key_in_scale_blue", rgb[2])

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "key_not_in_scale_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.key_not_in_scale["red"] = rgb[0]
        webinterface.ledsettings.key_not_in_scale["green"] = rgb[1]
        webinterface.ledsettings.key_not_in_scale["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("key_not_in_scale_red", rgb[0])
        webinterface.usersettings.change_setting_value("key_not_in_scale_green", rgb[1])
        webinterface.usersettings.change_setting_value("key_not_in_scale_blue", rgb[2])

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "scale_key":
        webinterface.ledsettings.scale_key = int(value)
        webinterface.usersettings.change_setting_value("scale_key", int(value))

        return jsonify(success=True, reload_sequence=True)

    if setting_name == "next_step":
        webinterface.ledsettings.set_sequence(0, 1, False)
        return jsonify(success=True, reload_sequence=True)

    if setting_name == "set_sequence":
        if (int(value) == 0):
            webinterface.ledsettings.__init__(webinterface.usersettings)
            webinterface.ledsettings.sequence_active = False
        else:
            webinterface.ledsettings.set_sequence(int(value) - 1, 0)
        return jsonify(success=True, reload_sequence=True)

    if setting_name == "screen_on":
        if (int(value) == 0):
            webinterface.menu.disable_screen()
        else:
            webinterface.menu.enable_screen()

    if setting_name == "reset_to_default":
        webinterface.usersettings.reset_to_default()

    if setting_name == "restart_rpi":
        call("sudo reboot now", shell=True)

    if setting_name == "turnoff_rpi":
        call("sudo shutdown -h now", shell=True)

    if setting_name == "update_rpi":
        call("sudo git reset --hard HEAD", shell=True)
        call("sudo git checkout .", shell=True)
        call("sudo git clean -fdx", shell=True)
        call("sudo git pull origin master", shell=True)

    if setting_name == "connect_ports":
        call("sudo ruby /usr/local/bin/connectall.rb", shell=True)
        return jsonify(success=True, reload_ports=True)

    if setting_name == "disconnect_ports":
        call("sudo aconnect -x", shell=True)
        return jsonify(success=True, reload_ports=True)

    if setting_name == "restart_rtp":
        call("sudo systemctl restart rtpmidid", shell=True)

    if setting_name == "start_recording":
        webinterface.saving.start_recording()
        return jsonify(success=True, reload_songs=True)

    if setting_name == "cancel_recording":
        webinterface.saving.cancel_recording()
        return jsonify(success=True, reload_songs=True)

    if setting_name == "save_recording":
        now = datetime.datetime.now()
        current_date = now.strftime("%Y-%m-%d %H:%M")
        webinterface.saving.save(current_date)
        return jsonify(success=True, reload_songs=True)

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

        return jsonify(success=True, reload_songs=True)

    if setting_name == "remove_song":
        if "_main" in value:
            name_no_suffix = value.replace("_main.mid", "")
            for fname in os.listdir('Songs'):
                if name_no_suffix in fname:
                    os.remove("Songs/" + fname)
        else:
            os.remove("Songs/" + value)
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
                return send_file("../Songs/" + value, mimetype='application/x-csv', attachment_filename=value,
                                 as_attachment=True)
            else:
                return send_file("../Songs/" + value.replace(".mid", "") + ".zip", mimetype='application/x-csv',
                                 attachment_filename=value.replace(".mid", "") + ".zip", as_attachment=True)
        else:
            return send_file("../Songs/" + value, mimetype='application/x-csv', attachment_filename=value,
                             as_attachment=True)

    if setting_name == "start_midi_play":
        webinterface.saving.t = threading.Thread(target=play_midi, args=(value, webinterface.midiports,
                                                                         webinterface.saving, webinterface.menu,
                                                                         webinterface.ledsettings,
                                                                         webinterface.ledstrip))
        webinterface.saving.t.start()

        return jsonify(success=True, reload_songs=True)

    if setting_name == "stop_midi_play":
        webinterface.saving.is_playing_midi.clear()
        fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

        return jsonify(success=True, reload_songs=True)

    return jsonify(success=True)


@webinterface.route('/api/get_sequence_setting', methods=['GET'])
def get_sequence_setting():
    response = {}

    color_mode = webinterface.ledsettings.color_mode

    light_mode = webinterface.ledsettings.mode

    red = webinterface.ledsettings.red
    green = webinterface.ledsettings.green
    blue = webinterface.ledsettings.blue
    led_color = wc.rgb_to_hex((int(red), int(green), int(blue)))

    multicolor = webinterface.ledsettings.multicolor
    multicolor_range = webinterface.ledsettings.multicolor_range

    rainbow_scale = webinterface.ledsettings.rainbow_scale
    rainbow_offset = webinterface.ledsettings.rainbow_offset
    rainbow_timeshift = webinterface.ledsettings.rainbow_timeshift

    speed_slowest_red = webinterface.ledsettings.speed_slowest["red"]
    speed_slowest_green = webinterface.ledsettings.speed_slowest["green"]
    speed_slowest_blue = webinterface.ledsettings.speed_slowest["blue"]
    speed_slowest_color = wc.rgb_to_hex((int(speed_slowest_red), int(speed_slowest_green), int(speed_slowest_blue)))
    response["speed_slowest_color"] = speed_slowest_color

    speed_fastest_red = webinterface.ledsettings.speed_fastest["red"]
    speed_fastest_green = webinterface.ledsettings.speed_fastest["green"]
    speed_fastest_blue = webinterface.ledsettings.speed_fastest["blue"]
    speed_fastest_color = wc.rgb_to_hex((int(speed_fastest_red), int(speed_fastest_green), int(speed_fastest_blue)))
    response["speed_fastest_color"] = speed_fastest_color

    gradient_start_red = webinterface.ledsettings.gradient_start["red"]
    gradient_start_green = webinterface.ledsettings.gradient_start["green"]
    gradient_start_blue = webinterface.ledsettings.gradient_start["blue"]
    gradient_start_color = wc.rgb_to_hex((int(gradient_start_red), int(gradient_start_green), int(gradient_start_blue)))
    response["gradient_start_color"] = gradient_start_color

    gradient_end_red = webinterface.ledsettings.gradient_end["red"]
    gradient_end_green = webinterface.ledsettings.gradient_end["green"]
    gradient_end_blue = webinterface.ledsettings.gradient_end["blue"]
    gradient_end_color = wc.rgb_to_hex((int(gradient_end_red), int(gradient_end_green), int(gradient_end_blue)))
    response["gradient_end_color"] = gradient_end_color

    key_in_scale_red = webinterface.ledsettings.key_in_scale["red"]
    key_in_scale_green = webinterface.ledsettings.key_in_scale["green"]
    key_in_scale_blue = webinterface.ledsettings.key_in_scale["blue"]
    key_in_scale_color = wc.rgb_to_hex((int(key_in_scale_red), int(key_in_scale_green), int(key_in_scale_blue)))
    response["key_in_scale_color"] = key_in_scale_color

    key_not_in_scale_red = webinterface.ledsettings.key_not_in_scale["red"]
    key_not_in_scale_green = webinterface.ledsettings.key_not_in_scale["green"]
    key_not_in_scale_blue = webinterface.ledsettings.key_not_in_scale["blue"]
    key_not_in_scale_color = wc.rgb_to_hex(
        (int(key_not_in_scale_red), int(key_not_in_scale_green), int(key_not_in_scale_blue)))
    response["key_not_in_scale_color"] = key_not_in_scale_color

    response["scale_key"] = webinterface.ledsettings.scale_key

    response["led_color"] = led_color
    response["color_mode"] = color_mode
    response["light_mode"] = light_mode
    response["multicolor"] = multicolor
    response["multicolor_range"] = multicolor_range
    response["rainbow_scale"] = rainbow_scale
    response["rainbow_offset"] = rainbow_offset
    response["rainbow_timeshift"] = rainbow_timeshift
    return jsonify(response)


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

    response["color_mode"] = webinterface.usersettings.get_setting_value("color_mode")

    response["multicolor"] = webinterface.usersettings.get_setting_value("multicolor")
    response["multicolor_range"] = webinterface.usersettings.get_setting_value("multicolor_range")

    response["rainbow_offset"] = webinterface.usersettings.get_setting_value("rainbow_offset")
    response["rainbow_scale"] = webinterface.usersettings.get_setting_value("rainbow_scale")
    response["rainbow_timeshift"] = webinterface.usersettings.get_setting_value("rainbow_timeshift")

    speed_slowest_red = webinterface.usersettings.get_setting_value("speed_slowest_red")
    speed_slowest_green = webinterface.usersettings.get_setting_value("speed_slowest_green")
    speed_slowest_blue = webinterface.usersettings.get_setting_value("speed_slowest_blue")
    speed_slowest_color = wc.rgb_to_hex((int(speed_slowest_red), int(speed_slowest_green), int(speed_slowest_blue)))
    response["speed_slowest_color"] = speed_slowest_color

    speed_fastest_red = webinterface.usersettings.get_setting_value("speed_fastest_red")
    speed_fastest_green = webinterface.usersettings.get_setting_value("speed_fastest_green")
    speed_fastest_blue = webinterface.usersettings.get_setting_value("speed_fastest_blue")
    speed_fastest_color = wc.rgb_to_hex((int(speed_fastest_red), int(speed_fastest_green), int(speed_fastest_blue)))
    response["speed_fastest_color"] = speed_fastest_color

    gradient_start_red = webinterface.usersettings.get_setting_value("gradient_start_red")
    gradient_start_green = webinterface.usersettings.get_setting_value("gradient_start_green")
    gradient_start_blue = webinterface.usersettings.get_setting_value("gradient_start_blue")
    gradient_start_color = wc.rgb_to_hex((int(gradient_start_red), int(gradient_start_green), int(gradient_start_blue)))
    response["gradient_start_color"] = gradient_start_color

    gradient_end_red = webinterface.usersettings.get_setting_value("gradient_end_red")
    gradient_end_green = webinterface.usersettings.get_setting_value("gradient_end_green")
    gradient_end_blue = webinterface.usersettings.get_setting_value("gradient_end_blue")
    gradient_end_color = wc.rgb_to_hex((int(gradient_end_red), int(gradient_end_green), int(gradient_end_blue)))
    response["gradient_end_color"] = gradient_end_color

    key_in_scale_red = webinterface.usersettings.get_setting_value("key_in_scale_red")
    key_in_scale_green = webinterface.usersettings.get_setting_value("key_in_scale_green")
    key_in_scale_blue = webinterface.usersettings.get_setting_value("key_in_scale_blue")
    key_in_scale_color = wc.rgb_to_hex((int(key_in_scale_red), int(key_in_scale_green), int(key_in_scale_blue)))
    response["key_in_scale_color"] = key_in_scale_color

    key_not_in_scale_red = webinterface.usersettings.get_setting_value("key_not_in_scale_red")
    key_not_in_scale_green = webinterface.usersettings.get_setting_value("key_not_in_scale_green")
    key_not_in_scale_blue = webinterface.usersettings.get_setting_value("key_not_in_scale_blue")
    key_not_in_scale_color = wc.rgb_to_hex(
        (int(key_not_in_scale_red), int(key_not_in_scale_green), int(key_not_in_scale_blue)))
    response["key_not_in_scale_color"] = key_not_in_scale_color

    response["scale_key"] = webinterface.usersettings.get_setting_value("scale_key")

    response["speed_max_notes"] = webinterface.usersettings.get_setting_value("speed_max_notes")
    response["speed_period_in_seconds"] = webinterface.usersettings.get_setting_value("speed_period_in_seconds")

    return jsonify(response)


@webinterface.route('/api/get_recording_status', methods=['GET'])
def get_recording_status():
    response = {}
    response["input_port"] = webinterface.usersettings.get_setting_value("input_port")
    response["play_port"] = webinterface.usersettings.get_setting_value("play_port")

    response["isrecording"] = webinterface.saving.isrecording

    response["isplaying"] = webinterface.saving.is_playing_midi

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
        if (i > int(start)):
            songs_list_dict[song] = date

        if len(songs_list_dict) >= int(length):
            break

    return render_template('songs_list.html', len=len(songs_list_dict), songs_list_dict=songs_list_dict, page=page,
                           max_page=max_page, total_songs=total_songs)


@webinterface.route('/api/get_ports', methods=['GET'])
def get_ports():
    ports = mido.get_input_names()
    ports = list(dict.fromkeys(ports))
    response = {}
    response["ports_list"] = ports
    response["input_port"] = webinterface.usersettings.get_setting_value("input_port")
    response["secondary_input_port"] = webinterface.usersettings.get_setting_value("secondary_input_port")
    response["play_port"] = webinterface.usersettings.get_setting_value("play_port")
    response["connected_ports"] = str(subprocess.check_output(["aconnect", "-i", "-l"]))

    return jsonify(response)


@webinterface.route('/api/switch_ports', methods=['GET'])
def switch_ports():
    active_input = webinterface.usersettings.get_setting_value("input_port")
    secondary_input = webinterface.usersettings.get_setting_value("secondary_input_port")
    webinterface.midiports.change_port("inport", secondary_input)
    webinterface.usersettings.change_setting_value("secondary_input_port", active_input)

    fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

    return jsonify(success=True)


@webinterface.route('/api/get_sequences', methods=['GET'])
def get_sequences():
    response = {}
    sequences_list = []
    sequences_tree = minidom.parse("sequences.xml")
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
    response["sequence_number"] = webinterface.ledsettings.sequence_number

    return jsonify(response)

@webinterface.route('/api/get_steps_list', methods=['GET'])
def get_steps_list():
    response = {}
    sequence = request.args.get('sequence')
    sequences_tree = minidom.parse("sequences.xml")
    steps_list = []
    i = 0

    for step in sequences_tree.getElementsByTagName("sequence_" + str(sequence))[0].childNodes:
        if(step.nodeType == 1):
            if(step.nodeName == "settings"):
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
    webinterface.ledsettings.set_sequence(sequence, step, True)

    return jsonify(success=True)