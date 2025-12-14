from webinterface import webinterface, app_state
from flask import render_template, send_file, request, jsonify
from werkzeug.security import safe_join
from lib.functions import (get_last_logs, find_between, fastColorWipe, play_midi, clamp, validate_schedule_overlaps)
from lib.led_animations import get_registry
import lib.colormaps as cmap
import psutil
import threading
import webcolors as wc
import mido
from xml.dom import minidom
import xml.etree.ElementTree as ET
import glob
import shutil
from subprocess import call
import subprocess
import datetime
import os
import math
from zipfile import ZipFile
import json
import ast
import re
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
    param = request.args.get('param')  # For Chords and Colormap
    
    # Handle stop command
    if choice == "stop":
        app_state.menu.is_animation_running = False
        app_state.menu.is_idle_animation_running = False
        # Clear running animation name
        if hasattr(app_state.menu, 'current_animation_name'):
            app_state.menu.current_animation_name = None
        return jsonify(success=True)
    
    # Use registry to start animation (always uses global speed)
    registry = get_registry()
    anim_info = registry.get_by_web_id(choice)
    
    if anim_info is None:
        return jsonify(success=False, error="Animation not found")
    
    # Convert param to appropriate type if needed
    processed_param = param
    if param is not None and anim_info.requires_param:
        if anim_info.name == "Chords":
            # Chords expects integer scale index
            try:
                processed_param = int(param)
            except (ValueError, TypeError):
                return jsonify(success=False, error="Invalid chord parameter")
        # colormap_animation expects string, so keep as-is
    
    # Store current animation name for restart on speed change (use web_id for tracking)
    app_state.menu.current_animation_name = choice
    app_state.menu.current_animation_param = processed_param if anim_info.requires_param else None
    
    # Start animation using registry (uses global speed automatically)
    # Use anim_info.name (internal name) not web_id
    success = registry.start_animation(
        name=anim_info.name,
        ledstrip=app_state.ledstrip,
        ledsettings=app_state.ledsettings,
        menu=app_state.menu,
        param=processed_param,
        usersettings=app_state.usersettings,
        is_idle=False
    )
    
    return jsonify(success=success)


@webinterface.route('/api/change_animation_speed', methods=['GET'])
def change_animation_speed():
    speed_value = request.args.get('speed_value')
    if not speed_value:
        return jsonify(success=False, error="Speed value is required")

    app_state.usersettings.change_setting_value("led_animation_speed", speed_value)
    app_state.ledsettings.led_animation_speed = speed_value  # Update live setting

    # Restart current animation if one is running
    if (app_state.menu.is_animation_running or app_state.menu.is_idle_animation_running) and hasattr(app_state.menu, 'current_animation_name') and app_state.menu.current_animation_name:
        registry = get_registry()
        anim_info = registry.get_by_web_id(app_state.menu.current_animation_name)
        if anim_info:
            # Stop current animation
            app_state.menu.is_animation_running = False
            app_state.menu.is_idle_animation_running = False
            import time
            time.sleep(0.2)  # Give time for thread to stop

            # Restart with new speed
            is_idle = getattr(app_state.menu, 'was_idle_animation', False)
            registry.start_animation(
                name=anim_info.name,
                ledstrip=app_state.ledstrip,
                ledsettings=app_state.ledsettings,
                menu=app_state.menu,
                param=getattr(app_state.menu, 'current_animation_param', None),
                usersettings=app_state.usersettings,
                is_idle=is_idle
            )
            return jsonify(success=True, message="Animation speed changed and animation restarted.")
    return jsonify(success=True, message="Animation speed changed.")


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

    # Get system state
    system_state = app_state.state_manager.current_state.value.upper() if app_state.state_manager else 'UNKNOWN'
    
    # Only provide FPS data when in ACTIVE_USE state
    led_fps = round(app_state.ledstrip.current_fps, 2) if system_state == 'ACTIVE_USE' else None

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
        'led_fps': led_fps,
        'system_state': system_state,
        'screen_on': app_state.menu.screen_on,
        'display_type': app_state.menu.args.display if app_state.menu and app_state.menu.args and app_state.menu.args.display else app_state.usersettings.get_setting_value("display_type") or '1in44',
        'led_pin': app_state.usersettings.get_setting_value("led_pin") or '18',
        'timezone': app_state.platform.get_current_timezone() if hasattr(app_state.platform, 'get_current_timezone') else 'UTC',
    }
    return jsonify(homepage_data)


@webinterface.route('/api/get_timezones', methods=['GET'])
def get_timezones():
    """Get list of available timezones."""
    try:
        if hasattr(app_state.platform, 'get_available_timezones'):
            timezones = app_state.platform.get_available_timezones()
            return jsonify(success=True, timezones=timezones)
        else:
            # Return common timezones as fallback
            common_timezones = [
                "UTC",
                "America/New_York",
                "America/Chicago",
                "America/Denver",
                "America/Los_Angeles",
                "Europe/London",
                "Europe/Paris",
                "Europe/Berlin",
                "Asia/Tokyo",
                "Asia/Shanghai",
                "Australia/Sydney"
            ]
            return jsonify(success=True, timezones=common_timezones)
    except Exception as e:
        logger.warning(f"Error getting timezones: {e}")
        return jsonify(success=False, error=str(e))


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

    if setting_name == "fading_speed":
        if not int(value):
            value = 1000
        app_state.ledsettings.fadingspeed = int(value)
        app_state.usersettings.change_setting_value("fadingspeed", app_state.ledsettings.fadingspeed)
    
    if setting_name == "velocity_speed":
        if not int(value):
            value = 1000
        app_state.ledsettings.velocity_speed = int(value)
        app_state.usersettings.change_setting_value("velocity_speed", app_state.ledsettings.velocity_speed)
    
    if setting_name == "pedal_speed":
        if not int(value):
            value = 1000
        app_state.ledsettings.pedal_speed = int(value)
        app_state.usersettings.change_setting_value("pedal_speed", app_state.ledsettings.pedal_speed)

    if setting_name == "pulse_animation_speed":
        if not int(value):
            value = 1000
        app_state.ledsettings.pulse_animation_speed = int(value)
        app_state.usersettings.change_setting_value("pulse_animation_speed", app_state.ledsettings.pulse_animation_speed)

    if setting_name == "pulse_animation_distance":
        if not int(value):
            value = 10
        app_state.ledsettings.pulse_animation_distance = int(value)
        app_state.usersettings.change_setting_value("pulse_animation_distance", app_state.ledsettings.pulse_animation_distance)

    if setting_name == "pulse_flicker_strength":
        if not int(value):
            value = 5
        app_state.ledsettings.pulse_flicker_strength = int(value)
        app_state.usersettings.change_setting_value("pulse_flicker_strength", app_state.ledsettings.pulse_flicker_strength)

    if setting_name == "pulse_flicker_speed":
        # Value is already in radians/sec from JavaScript conversion
        try:
            float_value = float(value)
            if float_value <= 0:
                float_value = 30.0  # Default: ~4.77 Hz in radians/sec
        except (ValueError, TypeError):
            float_value = 30.0  # Default: ~4.77 Hz in radians/sec
        app_state.ledsettings.pulse_flicker_speed = float_value
        app_state.usersettings.change_setting_value("pulse_flicker_speed", app_state.ledsettings.pulse_flicker_speed)

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

        # Save mode-specific speed settings
        if app_state.ledsettings.mode == "Fading":
            fadingspeed = sequences_tree.createElement("fadingspeed")
            fadingspeed.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.fadingspeed)))
            step.appendChild(fadingspeed)
        elif app_state.ledsettings.mode == "Velocity":
            velocity_speed = sequences_tree.createElement("velocity_speed")
            velocity_speed.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.velocity_speed)))
            step.appendChild(velocity_speed)
        elif app_state.ledsettings.mode == "Pedal":
            pedal_speed = sequences_tree.createElement("pedal_speed")
            pedal_speed.appendChild(sequences_tree.createTextNode(str(app_state.ledsettings.pedal_speed)))
            step.appendChild(pedal_speed)

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

    if setting_name == "display_type":
        # Validate the value
        if value in ['1in44', '1in3']:
            app_state.usersettings.change_setting_value("display_type", value)
            # Restart visualizer to apply the LCD type change
            app_state.platform.restart_visualizer()
            return jsonify(success=True, restart_required=True, message="LCD type changed. Restarting visualizer...")
        else:
            return jsonify(success=False, error="Invalid display type")

    if setting_name == "led_pin":
        # Validate the pin value
        valid_pins = ['12', '13', '18', '19', '41', '45', '53']
        pin_value = str(value)
        if pin_value not in valid_pins:
            return jsonify(success=False, error="Invalid LED pin. Valid pins are: " + ", ".join(valid_pins))
        
        # Auto-determine channel based on pin
        # Channel 0: pins 12, 18
        # Channel 1: pins 13, 19, 41, 45, 53
        pin_int = int(pin_value)
        if pin_int in [12, 18]:
            channel_value = 0
        elif pin_int in [13, 19, 41, 45, 53]:
            channel_value = 1
        else:
            return jsonify(success=False, error="Invalid LED pin")
        
        # Save both pin and channel settings
        app_state.usersettings.change_setting_value("led_pin", pin_value)
        app_state.usersettings.change_setting_value("led_channel", channel_value)
        
        # Restart visualizer to apply the LED pin change
        app_state.platform.restart_visualizer()
        return jsonify(success=True, restart_required=True, message="LED pin changed. Restarting visualizer...")

    if setting_name == "reset_to_default":
        app_state.usersettings.reset_to_default()

    if setting_name == "timezone":
        if hasattr(app_state.platform, 'set_timezone'):
            success = app_state.platform.set_timezone(value)
            if success:
                return jsonify(success=True, message="Timezone changed successfully.")
            else:
                return jsonify(success=False, error="Failed to change timezone.")
        else:
            return jsonify(success=False, error="Timezone change not supported on this platform.")

    if setting_name == "practice_tool_url":
        app_state.usersettings.change_setting_value("practice_tool_url", value)

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
        # Update tempo for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "practice", app_state.learning.practice)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")
        return jsonify(success=True)

    if setting_name == "change_tempo":
        value = int(value)
        app_state.learning.set_tempo = value
        app_state.learning.set_tempo = clamp(app_state.learning.set_tempo, 10, 200)
        # Update tempo for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "tempo", app_state.learning.set_tempo)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")

        return jsonify(success=True)

    if setting_name == "change_hands":
        value = int(value)
        app_state.learning.hands = value
        app_state.learning.hands = clamp(app_state.learning.hands, 0, len(app_state.learning.handsList) - 1)
        # Update tempo for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "hands", app_state.learning.hands)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")

        return jsonify(success=True)

    if setting_name == "change_mute_hand":
        value = int(value)
        app_state.learning.mute_hand = value
        app_state.learning.mute_hand = clamp(app_state.learning.mute_hand, 0,
                                                len(app_state.learning.mute_handList) - 1)
        # Update tempo for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "mute_hands", app_state.learning.mute_hand)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")
        return jsonify(success=True)

    if setting_name == "learning_start_point":
        value = int(value)
        app_state.learning.start_point = value
        app_state.learning.start_point = clamp(app_state.learning.start_point, 0,
                                                  app_state.learning.end_point - 1)
        # Update start point for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "start", app_state.learning.start_point)
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "end", app_state.learning.end_point)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")
        app_state.learning.restart_learning()

        return jsonify(success=True)

    if setting_name == "learning_end_point":
        value = int(value)
        app_state.learning.end_point = value
        app_state.learning.end_point = clamp(app_state.learning.end_point, app_state.learning.start_point + 1,
                                                100)
        # Update start point for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "start", app_state.learning.start_point)
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "end", app_state.learning.end_point)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")
        app_state.learning.restart_learning()

        return jsonify(success=True)

    if setting_name == "set_current_time_as_start_point":
        app_state.learning.start_point = round(
            float(app_state.learning.current_idx * 100 / float(len(app_state.learning.song_tracks))), 3)
        app_state.learning.start_point = clamp(app_state.learning.start_point, 0,
                                                  app_state.learning.end_point - 1)
        # Update start point for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "start", app_state.learning.start_point)
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "end", app_state.learning.end_point)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")
        app_state.learning.restart_learning()

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "set_current_time_as_end_point":
        app_state.learning.end_point = round(
            float(app_state.learning.current_idx * 100 / float(len(app_state.learning.song_tracks))), 3)
        app_state.learning.end_point = clamp(app_state.learning.end_point, app_state.learning.start_point + 1,
                                                100)
        # Update start point for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "start", app_state.learning.start_point)
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "end", app_state.learning.end_point)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")
        app_state.learning.restart_learning()

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "change_handL_color":
        value = int(value)
        if app_state.learning.is_led_activeL == 1:
            app_state.learning.hand_colorL += value
            app_state.learning.hand_colorL = clamp(app_state.learning.hand_colorL, 0,
                                                    len(app_state.learning.hand_colorList) - 1)
            # Update LED setting for current song
            try:
                profile_id = getattr(app_state, 'current_profile_id', None)
                # Only update if a profile is selected and we know the song name
                if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                    # Use ProfileManager directly if available
                    pm = getattr(app_state, 'profile_manager', None)
                    if pm:
                        updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "lh_color", app_state.learning.hand_colorL)
            except Exception as e:
                logger.warning(f"Failed to update learning section: {e}")

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "change_handR_color":
        value = int(value)
        if app_state.learning.is_led_activeR == 1:
            app_state.learning.hand_colorR += value
            app_state.learning.hand_colorR = clamp(app_state.learning.hand_colorR, 0,
                                                    len(app_state.learning.hand_colorList) - 1)
            # Update LED setting for current song
            try:
                profile_id = getattr(app_state, 'current_profile_id', None)
                # Only update if a profile is selected and we know the song name
                if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                    # Use ProfileManager directly if available
                    pm = getattr(app_state, 'profile_manager', None)
                    if pm:
                        updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "rh_color", app_state.learning.hand_colorR)
            except Exception as e:
                logger.warning(f"Failed to update learning section: {e}")

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "change_wrong_notes":
        value = int(value)
        app_state.learning.show_wrong_notes = value
        # Update tempo for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "wrong_notes", app_state.learning.show_wrong_notes)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")

    if setting_name == "change_future_notes":
        value = int(value)
        app_state.learning.show_future_notes = value
        # Update tempo for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "future_notes", app_state.learning.show_future_notes)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")

    if setting_name == "change_learning_loop":
        value = int(value == 'true')
        app_state.learning.is_loop_active = value
        # Update tempo for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "loop", app_state.learning.is_loop_active)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")
        return jsonify(success=True)

    if setting_name == "number_of_mistakes":
        value = int(value)
        app_state.learning.number_of_mistakes = value
        # Update tempo for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "mistakes", app_state.learning.number_of_mistakes)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")
        return jsonify(success=True)

    if setting_name == "change_left_led_active":
        value = int(value == 'true')
        app_state.learning.is_led_activeL = value
        if value == 0:
            app_state.learning.prev_hand_colorL = app_state.learning.hand_colorL
            app_state.learning.hand_colorL = 8
        else:
            app_state.learning.hand_colorL = app_state.learning.prev_hand_colorL
        # Update LED setting for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "lh_active", app_state.learning.is_led_activeL)
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "prev_lh_color", app_state.learning.prev_hand_colorL)
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "lh_color", app_state.learning.hand_colorL)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")
        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "change_right_led_active":
        value = int(value == 'true')
        app_state.learning.is_led_activeR = value
        if value == 0:
            app_state.learning.prev_hand_colorR = app_state.learning.hand_colorR
            app_state.learning.hand_colorR = 8
        else:
            app_state.learning.hand_colorR = app_state.learning.prev_hand_colorR
        # Update LED setting for current song
        try:
            profile_id = getattr(app_state, 'current_profile_id', None)
            # Only update if a profile is selected and we know the song name
            if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
                # Use ProfileManager directly if available
                pm = getattr(app_state, 'profile_manager', None)
                if pm:
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "rh_active", app_state.learning.is_led_activeR)
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "prev_rh_color", app_state.learning.prev_hand_colorR)
                    updated = pm.update_learning_setting(int(profile_id), app_state.learning.current_song_name, "rh_color", app_state.learning.hand_colorR)
        except Exception as e:
            logger.warning(f"Failed to update learning section: {e}")
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

    if setting_name == "idle_timeout_minutes":
        value = max(int(value), 1)
        app_state.menu.idle_timeout_minutes = value
        app_state.usersettings.change_setting_value("idle_timeout_minutes", app_state.menu.idle_timeout_minutes)
        # Reload state manager config
        if app_state.state_manager:
            app_state.state_manager.reload_config()
        return jsonify(success=True)

    if setting_name == "screensaver_delay":
        value = max(int(value), 0)
        app_state.menu.screensaver_delay = value
        app_state.usersettings.change_setting_value("screensaver_delay", app_state.menu.screensaver_delay)
        # Reload state manager config
        if app_state.state_manager:
            app_state.state_manager.reload_config()
        return jsonify(success=True)

    if setting_name == "screen_off_delay":
        value = max(int(value), 0)
        app_state.menu.screen_off_delay = value
        app_state.usersettings.change_setting_value("screen_off_delay", app_state.menu.screen_off_delay)
        # Reload state manager config
        if app_state.state_manager:
            app_state.state_manager.reload_config()

        return jsonify(success=True)

    if setting_name == "led_animation":
        app_state.menu.led_animation = value
        app_state.usersettings.change_setting_value("led_animation", value)
        return jsonify(success=True)
    
    if setting_name == "led_animation_speed":
        app_state.usersettings.change_setting_value("led_animation_speed", value)
        # Update ledsettings if it has the attribute
        if hasattr(app_state.ledsettings, 'led_animation_speed'):
            app_state.ledsettings.led_animation_speed = value
        
        # Restart animation if one is running
        if (app_state.menu.is_animation_running or app_state.menu.is_idle_animation_running) and hasattr(app_state.menu, 'current_animation_name'):
            current_name = app_state.menu.current_animation_name
            if current_name:
                # Stop current animation
                app_state.menu.is_animation_running = False
                app_state.menu.is_idle_animation_running = False
                import time
                time.sleep(0.2)  # Brief pause to let animation stop
                
                # Restart with new speed
                registry = get_registry()
                is_idle = getattr(app_state.menu, 'was_idle_animation', False)
                param = getattr(app_state.menu, 'current_animation_param', None)
                
                registry.start_animation(
                    name=current_name,
                    ledstrip=app_state.ledstrip,
                    ledsettings=app_state.ledsettings,
                    menu=app_state.menu,
                    param=param,
                    usersettings=app_state.usersettings,
                    is_idle=is_idle
                )
        
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

    # Get mode-specific speed
    if light_mode == "Fading":
        fading_speed = app_state.ledsettings.fadingspeed
    elif light_mode == "Velocity":
        fading_speed = app_state.ledsettings.velocity_speed
    elif light_mode == "Pedal":
        fading_speed = app_state.ledsettings.pedal_speed
    else:
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
    response["pulse_animation_speed"] = app_state.ledsettings.pulse_animation_speed
    response["pulse_animation_distance"] = app_state.ledsettings.pulse_animation_distance
    response["pulse_flicker_strength"] = app_state.ledsettings.pulse_flicker_strength
    response["pulse_flicker_speed"] = app_state.ledsettings.pulse_flicker_speed
    return jsonify(response)


@webinterface.route('/api/get_idle_animation_settings', methods=['GET'])
def get_idle_animation_settings():
    # Get schedule and parse JSON if it exists
    schedule_json = app_state.usersettings.get_setting_value("idle_animation_schedule")
    schedule_list = []
    if schedule_json:
        try:
            schedule_list = json.loads(schedule_json)
        except (json.JSONDecodeError, TypeError):
            schedule_list = []
    
    response = {"led_animation_delay": app_state.usersettings.get_setting_value("led_animation_delay"),
                "led_animation": app_state.usersettings.get_setting_value("led_animation"),
                "led_animation_brightness_percent": app_state.ledsettings.led_animation_brightness_percent,
                "led_animation_speed": app_state.usersettings.get_setting_value("led_animation_speed") or "",
                "idle_timeout_minutes": app_state.usersettings.get_setting_value("idle_timeout_minutes"),
                "screensaver_delay": app_state.usersettings.get_setting_value("screensaver_delay"),
                "screen_off_delay": app_state.usersettings.get_setting_value("screen_off_delay"),
                "idle_animation_schedule": schedule_list}
    return jsonify(response)

@webinterface.route('/api/save_idle_animation_schedule', methods=['POST'])
def save_idle_animation_schedule():
    try:
        data = request.get_json()
        if data is None:
            return jsonify(success=False, error="Invalid JSON data")
        
        schedule_list = data.get('schedule', [])
        
        # Validate schedule list structure
        if not isinstance(schedule_list, list):
            return jsonify(success=False, error="Schedule must be a list")
        
        # Validate each schedule entry
        for schedule in schedule_list:
            if not isinstance(schedule, dict):
                return jsonify(success=False, error="Each schedule entry must be a dictionary")
            if 'startTime' not in schedule or 'endTime' not in schedule:
                return jsonify(success=False, error="Each schedule must have startTime and endTime")
            if 'days' not in schedule or not isinstance(schedule['days'], list):
                return jsonify(success=False, error="Each schedule must have a days list")
            if not schedule['days']:
                return jsonify(success=False, error="Each schedule must have at least one weekday selected")
        
        # Validate for overlaps
        is_valid, error_msg = validate_schedule_overlaps(schedule_list)
        if not is_valid:
            return jsonify(success=False, error=error_msg)
        
        # Save schedule as JSON string
        schedule_json = json.dumps(schedule_list)
        app_state.usersettings.change_setting_value("idle_animation_schedule", schedule_json)
        app_state.usersettings.save_changes()
        
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error saving idle animation schedule: {e}")
        return jsonify(success=False, error=f"Error saving schedule: {str(e)}")

@webinterface.route('/api/get_system_time', methods=['GET'])
def get_system_time():
    """Get current system time from Linux date command."""
    try:
        result = subprocess.run(['date'], capture_output=True, text=True, check=True)
        return jsonify(success=True, time=result.stdout.strip())
    except Exception as e:
        # Fallback to Python datetime if date command fails
        now = datetime.datetime.now()
        return jsonify(success=True, time=now.strftime("%a %b %d %H:%M:%S %Z %Y"))

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
    # Get mode-specific speed
    if light_mode == "Fading":
        fading_speed = app_state.usersettings.get_setting_value("fadingspeed")
    elif light_mode == "Velocity":
        fading_speed = app_state.usersettings.get_setting_value("velocity_speed")
        if not fading_speed:
            fading_speed = app_state.usersettings.get_setting_value("fadingspeed")  # Fallback
    elif light_mode == "Pedal":
        fading_speed = app_state.usersettings.get_setting_value("pedal_speed")
        if not fading_speed:
            fading_speed = app_state.usersettings.get_setting_value("fadingspeed")  # Fallback
    else:
        fading_speed = app_state.usersettings.get_setting_value("fadingspeed")

    brightness = app_state.usersettings.get_setting_value("brightness_percent")
    backlight_brightness = app_state.usersettings.get_setting_value("backlight_brightness_percent")
    disable_backlight_on_idle = app_state.usersettings.get_setting_value("disable_backlight_on_idle")

    response["led_color"] = led_color
    response["light_mode"] = light_mode
    response["fading_speed"] = fading_speed
    response["pulse_animation_speed"] = app_state.usersettings.get_setting_value("pulse_animation_speed")
    response["pulse_animation_distance"] = app_state.usersettings.get_setting_value("pulse_animation_distance")
    response["pulse_flicker_strength"] = app_state.usersettings.get_setting_value("pulse_flicker_strength")
    response["pulse_flicker_speed"] = app_state.usersettings.get_setting_value("pulse_flicker_speed")

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
    response["practice_tool_url"] = app_state.usersettings.get_setting_value("practice_tool_url") or "https://piano-visualizer.pages.dev"

    return jsonify(response)


@webinterface.route('/api/get_recording_status', methods=['GET'])
def get_recording_status():
    response = {"input_port": app_state.usersettings.get_setting_value("input_port"),
                "play_port": app_state.usersettings.get_setting_value("play_port"),
                "isrecording": app_state.saving.is_recording, "isplaying": app_state.saving.is_playing_midi}

    return jsonify(response)


@webinterface.route('/api/get_learning_status', methods=['GET'])
def get_learning_status():
    # Update learning settings for current song from DB in case we changed the song
    try:
        profile_id = getattr(app_state, 'current_profile_id', None)
        # Only update if a profile is selected and we know the song name
        if profile_id and hasattr(app_state.learning, 'current_song_name') and app_state.learning.current_song_name:
            # Use ProfileManager directly if available
            pm = getattr(app_state, 'profile_manager', None)
            if pm:
                section_list = pm.get_learning_settings(int(profile_id), app_state.learning.current_song_name)
                app_state.learning.is_loop_active = section_list["loop"]
                app_state.learning.practice = section_list["practice"]
                app_state.learning.hands = section_list["hands"]
                app_state.learning.mute_hand = section_list["mute_hands"]
                app_state.learning.show_wrong_notes = section_list["wrong_notes"]
                app_state.learning.show_future_notes = section_list["future_notes"]
                app_state.learning.number_of_mistakes = section_list["mistakes"]
                app_state.learning.start_point = section_list["start"]
                app_state.learning.end_point = section_list["end"]
                app_state.learning.hand_colorR = section_list["rh_color"]
                app_state.learning.hand_colorL = section_list["lh_color"]
                app_state.learning.prev_hand_colorR = section_list["prev_rh_color"]
                app_state.learning.prev_hand_colorL = section_list["prev_lh_color"]
                app_state.learning.is_led_activeR = section_list["rh_active"]
                app_state.learning.is_led_activeL = section_list["lh_active"]
    except Exception as e:
        logger.warning(f"Failed to get learning status: {e}")
    response = {"loading": app_state.learning.loading,
                "is_loop_active": app_state.learning.is_loop_active,
                "practice": app_state.learning.practice,
                "hands": app_state.learning.hands,
                "mute_hand": app_state.learning.mute_hand,
                "show_wrong_notes": app_state.learning.show_wrong_notes,
                "show_future_notes": app_state.learning.show_future_notes,
                "number_of_mistakes": app_state.learning.number_of_mistakes,
                "start_point": app_state.learning.start_point,
                "end_point": app_state.learning.end_point,
                "set_tempo": app_state.learning.set_tempo,
                "hand_colorR": app_state.learning.hand_colorR,
                "hand_colorL": app_state.learning.hand_colorL,
                "prev_hand_colorR": app_state.learning.prev_hand_colorR,
                "prev_hand_colorL": app_state.learning.prev_hand_colorL,
                "is_led_activeL": app_state.learning.is_led_activeL,
                "is_led_activeR": app_state.learning.is_led_activeR,
                "hand_colorList": ast.literal_eval(app_state.usersettings.get_setting_value("hand_colorList"))}

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

# ========== Port Manager Helper Functions ==========

def parse_aconnect_ports(output, port_type="input"):
    """
    Parse aconnect output to extract port information.
    Returns a list of dicts with port info: {id, client_id, port_id, name, full_name}
    """
    ports = []
    current_client = None
    current_client_name = ""
    
    for line in output.split('\n'):
        line = line.strip()
        
        # Match client lines: "client 20: 'Midi Through' [type=kernel]"
        client_match = re.match(r"client (\d+):\s+'([^']+)'", line)
        if client_match:
            current_client = client_match.group(1)
            current_client_name = client_match.group(2)
            
            # Skip special clients
            if current_client == "0" or "Through" in current_client_name or "RtMidi" in current_client_name:
                current_client = None
            continue
        
        # Match port lines: "    0 'Midi Through Port-0'"
        if current_client and line and not line.startswith('client'):
            port_match = re.match(r"(\d+)\s+'([^']+)'", line)
            if port_match:
                port_id = port_match.group(1)
                port_name = port_match.group(2)
                full_id = f"{current_client}:{port_id}"
                
                ports.append({
                    'id': full_id,
                    'client_id': current_client,
                    'port_id': port_id,
                    'name': port_name,
                    'client_name': current_client_name,
                    'full_name': f"{current_client_name} - {port_name}"
                })
    
    return ports


def parse_aconnect_connections(output):
    """
    Parse aconnect -l output to extract current connections.
    Returns a list of dicts: {source, destination, source_name, dest_name}
    """
    connections = []
    current_client = None
    current_port = None
    current_client_name = ""
    current_port_name = ""
    
    for line in output.split('\n'):
        line_stripped = line.strip()
        
        # Match client lines
        client_match = re.match(r"client (\d+):\s+'([^']+)'", line_stripped)
        if client_match:
            current_client = client_match.group(1)
            current_client_name = client_match.group(2)
            current_port = None
            continue
        
        # Match port lines with connections: "    0 'port name'"
        if current_client and line.startswith('    ') and not line.startswith('\t'):
            port_match = re.match(r"\s+(\d+)\s+'([^']+)'", line)
            if port_match:
                current_port = port_match.group(1)
                current_port_name = port_match.group(2)
                continue
        
        # Match connection lines: "\tConnecting To: 130:0" or "\tConnecting To: 130:0, 131:0, 132:0"
        if current_client and current_port and '\t' in line:
            # Only process "Connecting To:" to avoid duplicates
            if "Connecting To:" in line:
                # Find all port connections in the line (handles multiple connections)
                conn_matches = re.findall(r"(\d+):(\d+)", line_stripped)
                source_id = f"{current_client}:{current_port}"
                
                for conn_match in conn_matches:
                    dest_id = f"{conn_match[0]}:{conn_match[1]}"
                    connections.append({
                        'source': source_id,
                        'destination': dest_id,
                        'source_name': f"{current_client_name} - {current_port_name}",
                    })
    
    return connections


def get_all_available_ports():
    """
    Get all available MIDI input and output ports.
    Returns dict with 'inputs' and 'outputs' lists.
    """
    try:
        input_output = subprocess.check_output(["aconnect", "-l"], text=True)
        input_ports = subprocess.check_output(["aconnect", "-i", "-l"], text=True)
        output_ports = subprocess.check_output(["aconnect", "-o", "-l"], text=True)
        
        return {
            'inputs': parse_aconnect_ports(input_ports, "input"),
            'outputs': parse_aconnect_ports(output_ports, "output"),
            'all': parse_aconnect_ports(input_output, "all")
        }
    except subprocess.CalledProcessError as e:
        return {'inputs': [], 'outputs': [], 'all': []}


def get_all_current_connections():
    """
    Get all current MIDI port connections.
    Returns list of connection dicts.
    """
    try:
        output = subprocess.check_output(["aconnect", "-l"], text=True)
        return parse_aconnect_connections(output)
    except subprocess.CalledProcessError:
        return []


def create_midi_port_connection(source, destination):
    """
    Create a connection between two MIDI ports.
    Args:
        source: Source port in format "client:port" (e.g., "20:0")
        destination: Destination port in format "client:port"
    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.call(["aconnect", source, destination])
        return result == 0
    except Exception as e:
        print(f"Error creating connection: {e}")
        return False


def delete_midi_port_connection(source, destination):
    """
    Delete a connection between two MIDI ports.
    Args:
        source: Source port in format "client:port"
        destination: Destination port in format "client:port"
    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.call(["aconnect", "-d", source, destination])
        return result == 0
    except Exception as e:
        print(f"Error deleting connection: {e}")
        return False


# ========== Port Connection API Endpoints ==========

@webinterface.route('/api/get_available_ports', methods=['GET'])
def get_available_ports():
    """Get all available MIDI ports (inputs and outputs)"""
    ports = get_all_available_ports()
    return jsonify(ports)


@webinterface.route('/api/get_port_connections', methods=['GET'])
def get_port_connections():
    """Get all current MIDI port connections"""
    connections = get_all_current_connections()
    return jsonify({'connections': connections})


@webinterface.route('/api/create_port_connection', methods=['POST'])
def create_port_connection():
    """Create a connection between two MIDI ports"""
    data = request.get_json()
    source = data.get('source')
    destination = data.get('destination')
    
    if not source or not destination:
        return jsonify({'success': False, 'error': 'Missing source or destination'}), 400
    
    # Prevent self-connection
    if source == destination:
        return jsonify({'success': False, 'error': 'Cannot connect a port to itself'}), 400
    
    success = create_midi_port_connection(source, destination)
    return jsonify({'success': success})


@webinterface.route('/api/delete_port_connection', methods=['POST'])
def delete_port_connection():
    """Delete a connection between two MIDI ports"""
    data = request.get_json()
    source = data.get('source')
    destination = data.get('destination')
    
    if not source or not destination:
        return jsonify({'success': False, 'error': 'Missing source or destination'}), 400
    
    success = delete_midi_port_connection(source, destination)
    return jsonify({'success': success})


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
# Presets API
PRESETS_DIR = "config/presets"

# LED settings that should be included in presets (Color Modes, Light Modes, Brightness only)
LED_SETTINGS_ALLOWLIST = {
    # Color Mode Settings
    'color_mode', 'red', 'green', 'blue',
    'rainbow_offset', 'rainbow_scale', 'rainbow_timeshift', 'rainbow_colormap',
    'velocityrainbow_offset', 'velocityrainbow_scale', 'velocityrainbow_curve', 'velocityrainbow_colormap',
    'multicolor', 'multicolor_range', 'multicolor_iteration',
    'gradient_start_red', 'gradient_start_green', 'gradient_start_blue',
    'gradient_end_red', 'gradient_end_green', 'gradient_end_blue',
    'key_in_scale_red', 'key_in_scale_green', 'key_in_scale_blue',
    'key_not_in_scale_red', 'key_not_in_scale_green', 'key_not_in_scale_blue',
    'scale_key',
    'speed_slowest_red', 'speed_slowest_green', 'speed_slowest_blue',
    'speed_fastest_red', 'speed_fastest_green', 'speed_fastest_blue',
    'speed_max_notes', 'speed_period_in_seconds',
    # Light Mode Settings
    'mode', 'fadingspeed', 'velocity_speed', 'pedal_speed',
    'pulse_animation_speed', 'pulse_animation_distance', 'pulse_flicker_strength', 'pulse_flicker_speed',
    'fadepedal_notedrop',
    # Brightness Settings
    'backlight_brightness', 'backlight_brightness_percent',
    'led_animation_brightness_percent',
    # Other LED Settings
    'backlight_red', 'backlight_green', 'backlight_blue',
    'adjacent_mode', 'adjacent_red', 'adjacent_green', 'adjacent_blue',
    'led_animation', 'led_animation_delay', 'led_animation_speed',
    'animation_speed_slow', 'animation_speed_medium', 'animation_speed_fast',
    'led_gamma',
    'sequence_active'
}

@webinterface.route('/api/presets', methods=['GET'])
def list_presets():
    files = glob.glob(os.path.join(PRESETS_DIR, "*.xml"))
    presets = [os.path.basename(f) for f in files]
    presets.sort()
    return jsonify(success=True, presets=presets)

@webinterface.route('/api/presets', methods=['POST'])
def save_preset():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify(success=False, error="Name is required")
    
    if not name.endswith('.xml'):
        name += '.xml'
        
    # Sanitize name
    name = os.path.basename(name)
    path = os.path.join(PRESETS_DIR, name)
    
    # Ensure presets directory exists
    try:
        if not os.path.exists(PRESETS_DIR):
            os.makedirs(PRESETS_DIR, exist_ok=True)
    except Exception as e:
        return jsonify(success=False, error=f"Failed to create directory: {e}")
    
    try:
        # Ensure pending changes are written to disk
        app_state.usersettings.save_changes()
        
        # Load current settings
        current_tree = ET.parse("config/settings.xml")
        current_root = current_tree.getroot()
        
        # Create new preset XML with only LED settings
        preset_root = ET.Element("settings")
        
        # Copy only LED settings from current settings
        for elem in current_root:
            if elem.tag in LED_SETTINGS_ALLOWLIST:
                # Create a copy of the element
                new_elem = ET.SubElement(preset_root, elem.tag)
                new_elem.text = elem.text
                
        # Write the minimal preset file
        preset_tree = ET.ElementTree(preset_root)
        preset_tree.write(path)
        
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e))

@webinterface.route('/api/presets/load', methods=['POST'])
def load_preset():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify(success=False, error="Name is required")
        
    path = os.path.join(PRESETS_DIR, os.path.basename(name))
    if not os.path.exists(path):
        return jsonify(success=False, error="Preset not found")
        
    try:
        # Load preset
        preset_tree = ET.parse(path)
        preset_root = preset_tree.getroot()
        
        # Load current settings
        current_tree = ET.parse("config/settings.xml")
        current_root = current_tree.getroot()
        
        # Helper to find or create element in current root
        def get_or_create(root, tag):
            elem = root.find(tag)
            if elem is None:
                elem = ET.SubElement(root, tag)
            return elem
            
        # Update only LED settings from preset
        for preset_elem in preset_root:
            # Only update settings that are in the LED allowlist
            if preset_elem.tag in LED_SETTINGS_ALLOWLIST:
                current_elem = get_or_create(current_root, preset_elem.tag)
                current_elem.text = preset_elem.text
            
        current_tree.write("config/settings.xml")
        
        # Reload application state
        reload_app_state()
        
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error loading preset: {e}")
        return jsonify(success=False, error=str(e))

@webinterface.route('/api/presets/delete', methods=['POST'])
def delete_preset():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify(success=False, error="Name is required")
        
    path = os.path.join(PRESETS_DIR, os.path.basename(name))
    if os.path.exists(path):
        os.remove(path)
        return jsonify(success=True)
    return jsonify(success=False, error="Preset not found")

@webinterface.route('/api/presets/rename', methods=['POST'])
def rename_preset():
    data = request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')
    
    if not old_name or not new_name:
        return jsonify(success=False, error="Both names required")
        
    if not new_name.endswith('.xml'):
        new_name += '.xml'
        
    old_path = os.path.join(PRESETS_DIR, os.path.basename(old_name))
    new_path = os.path.join(PRESETS_DIR, os.path.basename(new_name))
    
    if os.path.exists(old_path):
        if os.path.exists(new_path):
             return jsonify(success=False, error="New name already exists")
        os.rename(old_path, new_path)
        return jsonify(success=True)
    return jsonify(success=False, error="Preset not found")

@webinterface.route('/api/presets/upload', methods=['POST'])
def upload_preset():
    if 'file' not in request.files:
        return jsonify(success=False, error="No file part")
    file = request.files['file']
    if file.filename == '':
        return jsonify(success=False, error="No selected file")
    if file and file.filename.endswith('.xml'):
        filename = os.path.basename(file.filename)
        
        # Ensure presets directory exists
        try:
            if not os.path.exists(PRESETS_DIR):
                os.makedirs(PRESETS_DIR, exist_ok=True)
        except Exception as e:
            return jsonify(success=False, error=f"Failed to create directory: {e}")
            
        file.save(os.path.join(PRESETS_DIR, filename))
        return jsonify(success=True)
    return jsonify(success=False, error="Invalid file type")

@webinterface.route('/api/presets/download', methods=['GET'])
def download_preset():
    name = request.args.get('name')
    if not name:
        return abort(404)
    path = os.path.join(PRESETS_DIR, os.path.basename(name))
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return abort(404)

def reload_app_state():
    from lib.usersettings import UserSettings
    
    # Reload UserSettings
    app_state.usersettings = UserSettings()
    
    # Update existing LedSettings object properties instead of creating new one
    # This ensures VisualizerApp.ci.ledsettings still references the same object
    ls = app_state.ledsettings
    
    # Update usersettings reference and reload all settings
    ls.usersettings = app_state.usersettings
    ls.reload_settings()
    
    # Trigger color mode refresh in VisualizerApp main loop
    ls.incoming_setting_change = True
    
    # Update component references to use new UserSettings and LedSettings instances
    app_state.ledstrip.usersettings = app_state.usersettings
    app_state.ledstrip.ledsettings = app_state.ledsettings
    
    app_state.menu.usersettings = app_state.usersettings
    app_state.menu.ledsettings = app_state.ledsettings
    
    # Update menu multicolor if it exists
    if hasattr(ls, 'menu') and ls.menu:
        ls.menu.update_multicolor(ls.multicolor)
    
    app_state.midiports.usersettings = app_state.usersettings
    
    if hasattr(app_state, 'learning') and app_state.learning:
        app_state.learning.usersettings = app_state.usersettings
        app_state.learning.ledsettings = app_state.ledsettings


@webinterface.route('/api/set_practice_active', methods=['POST'])
def set_practice_active():
    """Set the practice_active flag to enable/disable websocket MIDI priority."""
    try:
        data = request.get_json()
        if data and 'active' in data:
            app_state.practice_active = bool(data['active'])
            logger.info(f"Practice mode {'activated' if app_state.practice_active else 'deactivated'}")
            return jsonify(success=True, practice_active=app_state.practice_active)
        else:
            return jsonify(success=False, error="Missing 'active' parameter"), 400
    except Exception as e:
        logger.error(f"Error setting practice active: {e}")
        return jsonify(success=False, error=str(e)), 500


@webinterface.route('/api/clear_websocket_midi_queue', methods=['POST'])
def clear_websocket_midi_queue():
    """Clear the websocket MIDI queue."""
    try:
        if app_state.midiports:
            app_state.midiports.clear_websocket_midi_queue()
            logger.info("Websocket MIDI queue cleared")
            return jsonify(success=True)
        else:
            return jsonify(success=False, error="midiports not available"), 500
    except Exception as e:
        logger.error(f"Error clearing websocket MIDI queue: {e}")
        return jsonify(success=False, error=str(e)), 500


PRACTICE_BACKUP_FOLDER = "config/practice-backup"

@webinterface.route('/api/save_practice_backup', methods=['POST'])
def save_practice_backup():
    import time
    try:
        if not os.path.exists(PRACTICE_BACKUP_FOLDER):
            os.makedirs(PRACTICE_BACKUP_FOLDER)

        data = request.json
        if not data:
            return jsonify(success=False, error="No data received")

        backup_data = data.get('data')
        config = data.get('config', {})
        
        if not backup_data:
             return jsonify(success=False, error="No backup data received")

        timestamp = config.get('timestamp', int(time.time() * 1000))
        is_auto = config.get('isAuto', False)
        backup_type = "auto" if is_auto else "manual"
        
        filename = f"practice_backup_{timestamp}_{backup_type}.json"
        filepath = os.path.join(PRACTICE_BACKUP_FOLDER, filename)
        
        with open(filepath, 'w') as f:
            json.dump(data, f)

        # Retention policy
        retention_count = config.get('retentionCount', 5)
        if is_auto:
            files = glob.glob(os.path.join(PRACTICE_BACKUP_FOLDER, "practice_backup_*_*.json"))
            
            def get_timestamp(f):
                try:
                    parts = os.path.basename(f).split('_')
                    return int(parts[2])
                except:
                    return 0
            
            files.sort(key=get_timestamp)
            
            auto_files = [f for f in files if "_auto.json" in f]
            while len(auto_files) > retention_count:
                oldest = auto_files.pop(0)
                try:
                    os.remove(oldest)
                except OSError as e:
                    logger.error(f"Error deleting old backup {oldest}: {e}")

        return jsonify(success=True, id=filename)
    except Exception as e:
        logger.error(f"Error saving practice backup: {e}")
        return jsonify(success=False, error=str(e))

@webinterface.route('/api/get_practice_backup_list', methods=['GET'])
def get_practice_backup_list():
    try:
        if not os.path.exists(PRACTICE_BACKUP_FOLDER):
             return jsonify(success=True, data=[])

        backups = []
        files = glob.glob(os.path.join(PRACTICE_BACKUP_FOLDER, "practice_backup_*_*.json"))
        
        for f in files:
            try:
                basename = os.path.basename(f)
                parts = basename.split('_')
                timestamp = int(parts[2])
                type_part = parts[3].replace('.json', '')
                is_auto = (type_part == 'auto')
                size = os.path.getsize(f)
                
                backups.append({
                    "id": basename,
                    "timestamp": timestamp,
                    "isAuto": is_auto,
                    "size": size
                })
            except Exception as e:
                logger.error(f"Error parsing backup file {f}: {e}")
                continue
                
        # Sort by timestamp descending
        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify(success=True, data=backups)
    except Exception as e:
        logger.error(f"Error listing practice backups: {e}")
        return jsonify(success=False, error=str(e))

@webinterface.route('/api/get_practice_backup', methods=['GET'])
def get_practice_backup():
    backup_id = request.args.get('id')
    if not backup_id:
        return jsonify(success=False, error="No backup ID provided")
        
    try:
        # Sanitize backup_id to prevent directory traversal
        if os.path.sep in backup_id or '..' in backup_id:
             return jsonify(success=False, error="Invalid backup ID")
             
        filepath = os.path.join(PRACTICE_BACKUP_FOLDER, backup_id)
        if not os.path.exists(filepath):
             return jsonify(success=False, error="Backup not found")
             
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        return jsonify(success=True, data=data.get('data'))
    except Exception as e:
        logger.error(f"Error retrieving practice backup: {e}")
        return jsonify(success=False, error=str(e))

