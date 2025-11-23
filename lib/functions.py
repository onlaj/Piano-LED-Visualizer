import threading
from lib.rpi_drivers import Color
import lib.colormaps as cmap
import mido
import datetime
import psutil
import time
import socket
from lib.rpi_drivers import GPIO
import math
import subprocess
import random
from lib.log_setup import logger
import os
import json

SENSECOVER = 12
GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSECOVER, GPIO.IN, GPIO.PUD_UP)


def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
    except OSError:
        return "0.0.0.0"
    local_ip = s.getsockname()[0]
    s.close()
    return local_ip


def get_last_logs(n=100):
    file_path = 'visualizer.log'
    # If the file does not exist, create it with write permissions
    if not os.path.exists(file_path):
        open(file_path, 'w').close()
        os.chmod(file_path, 0o777)

    try:
        # Use the 'tail' command to get the last N lines of the log file
        tail_command = ["tail", f"-n{n}", file_path]
        result = subprocess.run(tail_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)

        # Split the output into lines and return as a list
        lines = result.stdout.splitlines()
        string = ""
        for line in lines:
            string += "\r\n" + line
        return string
    except subprocess.CalledProcessError as e:
        # Handle any errors that occur during the 'tail' command execution
        return [f"Error: {e.stderr}"]


def find_between(s, start, end):
    try:
        return (s.split(start))[1].split(end)[0]
    except IndexError:
        return False


def clamp(val, val_min, val_max):
    return max(val_min, min(val, val_max))


def shift(lst, num_shifts):
    return lst[num_shifts:] + lst[:num_shifts]


def play_midi(song_path, midiports, saving, menu, ledsettings, ledstrip):
    midiports.midifile_queue.append((mido.Message('note_on'), time.perf_counter()))
    strip = ledstrip.strip

    if song_path in saving.is_playing_midi.keys():
        menu.render_message(song_path, "Already playing", 2000)
        return

    saving.is_playing_midi.clear()

    saving.is_playing_midi[song_path] = True
    menu.render_message("Playing: ", song_path, 2000)
    saving.t = threading.currentThread()

    try:
        mid = mido.MidiFile("Songs/" + song_path)
        fastColorWipe(strip, True, ledsettings)
        # length = mid.length
        t0 = False
        total_delay = 0
        delay = 0
        for message in mid:
            if song_path in saving.is_playing_midi.keys():
                if not t0:
                    t0 = time.perf_counter()

                total_delay += message.time
                current_time = (time.perf_counter() - t0) + message.time
                drift = total_delay - current_time

                if drift < 0:
                    delay = message.time + drift
                else:
                    delay = message.time
                if delay < 0:
                    delay = 0

                msg_timestamp = time.perf_counter() + delay
                if delay > 0:
                    time.sleep(delay)
                if not message.is_meta:
                    if midiports.playport is not None:
                        midiports.playport.send(message)
                    else:
                        logger.debug("Skipping playport send: no output port configured")
                    midiports.midifile_queue.append((message.copy(time=0), msg_timestamp))

            else:
                midiports.midifile_queue.clear()
                clear_ledstrip_state(ledstrip)
                break
        logger.info('play time: {:.2f} s (expected {:.2f})'.format(time.perf_counter() - t0, total_delay))
        # print('play time: {:.2f} s (expected {:.2f})'.format(time.perf_counter() - t0, length))
        # saving.is_playing_midi = False
    except FileNotFoundError:
        menu.render_message(song_path, "File not found", 2000)
    except Exception as e:
        menu.render_message(song_path, "Error while playing song " + str(e), 2000)
        logger.warning(e)
    finally:
        midiports.midifile_queue.clear()
        try:
            clear_ledstrip_state(ledstrip)
        except Exception as e:
            logger.debug(f"LED cleanup failed: {e}")
    saving.is_playing_midi.clear()


def is_within_schedule(schedule_list):
    """
    Check if current time is within any of the scheduled intervals.
    Schedule list is a list of dicts with:
    - enabled: bool
    - startTime: "HH:MM"
    - endTime: "HH:MM"
    - days: list of ints (0=Monday, 6=Sunday)
    """
    if not schedule_list:
        return True

    now = datetime.datetime.now()
    current_weekday = now.weekday()
    current_time = now.time()

    # If no enabled schedules, it's always allowed (default behavior)
    enabled_schedules = [s for s in schedule_list if s.get('enabled', True)]
    if not enabled_schedules:
        return True

    for schedule in enabled_schedules:
        # Check day of week
        if current_weekday not in schedule.get('days', []):
            continue

        # Parse start and end times
        try:
            start_hour, start_minute = map(int, schedule.get('startTime', '00:00').split(':'))
            end_hour, end_minute = map(int, schedule.get('endTime', '23:59').split(':'))
            
            start_time = datetime.time(start_hour, start_minute)
            end_time = datetime.time(end_hour, end_minute)

            # Check time range
            if start_time <= end_time:
                if start_time <= current_time <= end_time:
                    return True
            else:
                # Crosses midnight
                if current_time >= start_time or current_time <= end_time:
                    return True
        except ValueError:
            continue

    return False


def validate_schedule_overlaps(schedule_list):
    """
    Validate that schedules don't overlap when they share common weekdays.
    
    Args:
        schedule_list: List of dicts with enabled, startTime, endTime, days
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not schedule_list:
        return True, None
    
    # Only check enabled schedules
    enabled_schedules = [s for s in schedule_list if s.get('enabled', True)]
    if len(enabled_schedules) <= 1:
        return True, None
    
    # Compare each pair of schedules
    for i in range(len(enabled_schedules)):
        for j in range(i + 1, len(enabled_schedules)):
            schedule1 = enabled_schedules[i]
            schedule2 = enabled_schedules[j]
            
            # Get weekdays for each schedule
            days1 = set(schedule1.get('days', []))
            days2 = set(schedule2.get('days', []))
            
            # Only check for overlaps if they share at least one common weekday
            common_days = days1 & days2
            if not common_days:
                continue
            
            # Parse times
            try:
                start1_h, start1_m = map(int, schedule1.get('startTime', '00:00').split(':'))
                end1_h, end1_m = map(int, schedule1.get('endTime', '23:59').split(':'))
                start2_h, start2_m = map(int, schedule2.get('startTime', '00:00').split(':'))
                end2_h, end2_m = map(int, schedule2.get('endTime', '23:59').split(':'))
                
                start1 = datetime.time(start1_h, start1_m)
                end1 = datetime.time(end1_h, end1_m)
                start2 = datetime.time(start2_h, start2_m)
                end2 = datetime.time(end2_h, end2_m)
            except (ValueError, AttributeError):
                continue
            
            # Check for overlap
            overlap = False
            
            # Helper function to check if two time ranges overlap
            def time_ranges_overlap(s1, e1, s2, e2):
                """Check if two time ranges overlap, handling midnight crossing."""
                # Case 1: Neither range crosses midnight
                if s1 <= e1 and s2 <= e2:
                    return not (e1 < s2 or e2 < s1)
                # Case 2: First range crosses midnight
                elif s1 > e1 and s2 <= e2:
                    return s2 <= e1 or s1 <= e2
                # Case 3: Second range crosses midnight
                elif s1 <= e1 and s2 > e2:
                    return s1 <= e2 or s2 <= e1
                # Case 4: Both cross midnight
                else:  # s1 > e1 and s2 > e2
                    return True  # Always overlap if both cross midnight
            
            if time_ranges_overlap(start1, end1, start2, end2):
                overlap = True
            
            if overlap:
                # Format days for error message
                day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                common_days_str = ', '.join([day_names[d] for d in sorted(common_days)])
                time1_str = f"{schedule1.get('startTime', '00:00')}-{schedule1.get('endTime', '23:59')}"
                time2_str = f"{schedule2.get('startTime', '00:00')}-{schedule2.get('endTime', '23:59')}"
                error_msg = f"Schedule overlap detected on {common_days_str}: {time1_str} overlaps with {time2_str}"
                return False, error_msg
    
    return True, None


def manage_idle_animation(ledstrip, ledsettings, menu, midiports, state_manager=None):
    from lib.led_animations import get_registry
    
    animation_delay_minutes = int(menu.led_animation_delay)
    if animation_delay_minutes == 0:
        return

    # Check schedule
    try:
        schedule_json = menu.usersettings.get_setting_value("idle_animation_schedule")
        if schedule_json:
            schedule_list = json.loads(schedule_json)
            if not is_within_schedule(schedule_list):
                # Stop animation if running
                if menu.is_idle_animation_running:
                    menu.is_idle_animation_running = False
                return
    except Exception as e:
        logger.warning(f"Error checking idle animation schedule: {e}")

    # Use state manager if available
    if state_manager:
        # Only run idle animation in IDLE state
        if not state_manager.is_idle():
            if menu.is_idle_animation_running:
                menu.is_idle_animation_running = False
            return
        
        # In IDLE state, check animation delay
        time_since_last_activity_minutes = state_manager.get_state_info()['time_since_user'] / 60
        if time_since_last_activity_minutes < animation_delay_minutes:
            return
    else:
        # Fallback to original logic if state_manager not available
        time_since_last_activity_minutes = (time.time() - menu.last_activity) / 60
        time_since_last_ports_activity_minutes = (time.time() - midiports.last_activity) / 60

        if time_since_last_ports_activity_minutes < animation_delay_minutes:
            menu.is_idle_animation_running = False
            return

        # Check conditions
        if not (0 < animation_delay_minutes < time_since_last_activity_minutes
                and not menu.is_idle_animation_running
                and 0 < animation_delay_minutes < time_since_last_ports_activity_minutes):
            return
    
    # Start animation if not already running
    if menu.is_idle_animation_running:
        return
    
    # Get animation name (handle backward compatibility with old format)
    animation_name = menu.led_animation
    
    # Handle old format: "Animation Name Speed" (e.g., "Rainbow Slow", "Breathing Slow")
    # Extract speed keyword from animation name if present (for backward compatibility)
    speed_keywords = ["Slow", "Medium", "Fast"]
    for keyword in speed_keywords:
        if animation_name.endswith(" " + keyword):
            animation_name = animation_name[:-len(" " + keyword)].strip()
            break
    
    # Track animation for speed change restart
    menu.current_animation_name = animation_name
    menu.current_animation_param = None
    menu.was_idle_animation = True
    
    # Use registry to start animation (always uses global speed)
    registry = get_registry()
    success = registry.start_animation(
        name=animation_name,
        ledstrip=ledstrip,
        ledsettings=ledsettings,
        menu=menu,
        usersettings=ledsettings.usersettings,
        is_idle=True
    )
    
    if not success:
        # Fallback: try to find animation by partial match
        # This handles edge cases and backward compatibility
        all_animations = registry.get_all()
        for anim_info in all_animations:
            if anim_info.name.lower() in animation_name.lower() or animation_name.lower() in anim_info.name.lower():
                if not anim_info.requires_param:  # Only use animations without parameters for IDLE
                    menu.current_animation_name = anim_info.name
                    registry.start_animation(
                        name=anim_info.name,
                        ledstrip=ledstrip,
                        ledsettings=ledsettings,
                        menu=menu,
                        usersettings=ledsettings.usersettings,
                        is_idle=True
                    )
                    break
    
    time.sleep(1)


def screensaver(menu, midiports, saving, ledstrip, ledsettings, state_manager=None):
    last_cpu_average = 0

    KEY2 = 20
    GPIO.setup(KEY2, GPIO.IN, GPIO.PUD_UP)

    # Use state manager to determine initial delay
    if state_manager and state_manager.is_idle():
        delay = 1.0  # 1Hz in IDLE state
    else:
        delay = 0.2  # 5Hz in NORMAL state for smooth animations
    
    interval = 3 / float(delay)
    i = 0
    cpu_history = [None] * int(interval)
    cpu_chart = [0] * 28
    cpu_average = 0

    upload = 0
    download = 0
    upload_start = 0
    download_start = 0
    local_ip = 0

    if menu.screensaver_settings["local_ip"] == "1":
        local_ip = get_ip_address()

    try:
        midiports.inport.poll()
    except Exception as e:
        menu.render_message("Error while getting ports", "", 2000)
        logger.warning("Error while getting ports " + str(e))

    while True:
        manage_idle_animation(ledstrip, ledsettings, menu, midiports, state_manager)

        # Update state manager in screensaver loop
        if state_manager:
            state_manager.update_state(midiports, menu)
        
        # Adjust delay based on state
        if state_manager:
            if state_manager.is_idle():
                new_delay = 1.0  # 1Hz in IDLE
            else:
                new_delay = 0.2  # 5Hz in NORMAL
            
            # If delay changed, recalculate interval and reset cpu_history
            if abs(new_delay - delay) > 0.01:
                delay = new_delay
                interval = 3 / float(delay)
                cpu_history = [None] * int(interval)
                cpu_average = 0
                i = 0
        elif (time.perf_counter() - saving.start_time) > 3600 and delay < 0.5 and menu.screensaver_is_running is False:
            # Fallback: old behavior if no state manager
            delay = 0.9
            interval = 5 / float(delay)
            cpu_history = [None] * int(interval)
            cpu_average = 0
            i = 0

        if int(menu.screen_off_delay) > 0 and ((time.perf_counter() - saving.start_time) > (int(menu.screen_off_delay) * 60)):
            menu.screen_status = 0
            GPIO.output(24, 0)

        menu.screensaver_is_running = True

        hour = datetime.datetime.now().strftime("%H:%M:%S")
        date = datetime.datetime.now().strftime("%d-%m-%Y")
        cpu_usage = psutil.cpu_percent()
        cpu_history[i] = cpu_usage
        cpu_chart.append(cpu_chart.pop(0))
        cpu_chart[27] = cpu_usage

        if i >= (int(interval) - 1):
            i = 0
            try:
                cpu_average = sum(cpu_history) / (float(len(cpu_history) + 1))
                last_cpu_average = cpu_average
            except:
                cpu_average = last_cpu_average

        if menu.screensaver_settings["ram"] == "1":
            ram_usage = psutil.virtual_memory()[2]
        else:
            ram_usage = 0

        if menu.screensaver_settings["temp"] == "1":
            try:
                temp = find_between(str(psutil.sensors_temperatures()["cpu_thermal"]), "current=", ",")
            except:
                temp = 0
            temp = round(float(temp), 1)
        else:
            temp = 0

        if menu.screensaver_settings["network_usage"] == "1":
            upload_end = psutil.net_io_counters().bytes_sent
            download_end = psutil.net_io_counters().bytes_recv

            if upload_start:
                upload = upload_end - upload_start
                upload = upload * (1 / delay)
                upload = upload / 1000000
                upload = round(upload, 2)

            if download_start:
                download = download_end - download_start
                download = download * (1 / delay)
                download = download / 1000000
                download = round(download, 2)

            upload_start = upload_end
            download_start = download_end
        else:
            upload = 0
            download = 0
        if menu.screensaver_settings["sd_card_space"] == "1":
            card_space = psutil.disk_usage('/')
        else:
            card_space = 0

        menu.render_screensaver(hour, date, cpu_usage, round(cpu_average, 1), ram_usage, temp, cpu_chart, upload,
                                download, card_space, local_ip)
        time.sleep(delay)
        i += 1
        try:
            # Exit screensaver if MIDI activity or state changed to active use
            if len(midiports.midi_queue) != 0 or (state_manager and state_manager.is_active_use()):
                menu.screensaver_is_running = False
                saving.start_time = time.perf_counter()
                menu.screen_status = 1
                GPIO.output(24, 1)
                midiports.reconnect_ports()
                midiports.last_activity = time.time()
                menu.show()
                break
        except:
            pass
        if GPIO.input(KEY2) == 0:
            menu.screensaver_is_running = False
            saving.start_time = time.perf_counter()
            menu.screen_status = 1
            GPIO.output(24, 1)
            midiports.reconnect_ports()
            menu.show()
            break


# Get note position on the strip
def get_note_position(note, ledstrip, ledsettings):
    note_offsets = ledsettings.note_offsets
    note_offset = 0

    for threshold, offset in note_offsets: # Iterate through ALL offsets
        if note > threshold:
            note_offset += offset  # Add the offset for each matching range

    note_offset -= ledstrip.shift  # Apply global shift

    density = ledstrip.leds_per_meter / 72
    note_pos_raw = int(density * (note - 20) - note_offset)

    if ledstrip.reverse:
        return max(0, ledstrip.led_number - note_pos_raw)
    else:
        return max(0, note_pos_raw)


# scale: 1 means in C, scale: 2 means in C#, scale: 3 means in D, etc...
# and scale: 1 means in C m, scale: 2 means in C# m, scale: 3 means in D m, etc...
def get_scale_color(scale, note_position, key_in_scale, key_not_in_scale):
    scale = int(scale)
    if scale < 12:
        notes_in_scale = [0, 2, 4, 5, 7, 9, 11]
    else:
        notes_in_scale = [0, 2, 3, 5, 7, 8, 10]
    note_position = (note_position - scale) % 12

    if note_position in notes_in_scale:
        return list(key_in_scale.values())
    else:
        return list(key_not_in_scale.values())


def get_rainbow_colors(pos, color):
    pos = int(pos)
    if pos < 85:
        if color == "green":
            return pos * 3
        elif color == "red":
            return 255 - pos * 3
        elif color == "blue":
            return 0
    elif pos < 170:
        pos -= 85
        if color == "green":
            return 255 - pos * 3
        elif color == "red":
            return 0
        elif color == "blue":
            return pos * 3
    else:
        pos -= 170
        if color == "green":
            return 0
        elif color == "red":
            return pos * 3
        elif color == "blue":
            return 255 - pos * 3


def powercurve(x, p):
    if p == 0:
        return x
    return (math.exp(-p * x) - 1) / (math.exp(-p) - 1)


def gammacurve(x, p):
    if p != 0:
        return x ** (1 / p)
    else:
        return 1


def check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
    if ledsettings.adjacent_mode == "Off":
        if i < len(ledstrip.keylist_status) and i < len(ledstrip.keylist):
            if ledstrip.keylist_status[i] == 0 and ledstrip.keylist[i] == 0:
                return True
        return False
    else:
        if 1 < i < (ledstrip.led_number - 1):
            if ledstrip.keylist[i + 1] == ledstrip.keylist[i - 1] == ledstrip.keylist[i] \
                    == ledstrip.keylist_status[i + 1] == ledstrip.keylist_status[i - 1] == ledstrip.keylist_status[i]:
                return True
        else:
            return True
    return False


# LED animations
def fastColorWipe(strip, update, ledsettings):
    if ledsettings.backlight_stopped:
        color = Color(0, 0, 0)
    else:
        brightness = ledsettings.backlight_brightness_percent / 100
        red = int(ledsettings.get_backlight_color("Red") * brightness)
        green = int(ledsettings.get_backlight_color("Green") * brightness)
        blue = int(ledsettings.get_backlight_color("Blue") * brightness)
        color = Color(red, green, blue)
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    if update:
        strip.show()


def clear_ledstrip_state(ledstrip, *, show=True):
    """Force-clear LED pixels and reset key state tracking."""
    strip = ledstrip.strip
    total = strip.numPixels()
    for i in range(total):
        strip.setPixelColor(i, Color(0, 0, 0))
    if show:
        strip.show()

    # Reset internal note tracking so fade logic cannot relight pixels.
    ledstrip.keylist = [0] * ledstrip.led_number
    ledstrip.keylist_status = [0] * ledstrip.led_number
    ledstrip.keylist_sustained = [0] * ledstrip.led_number
    ledstrip.keylist_color = [0] * ledstrip.led_number


def calculate_brightness(ledsettings):
    brightness = ledsettings.led_animation_brightness_percent
    brightness /= 100
    return brightness


def stop_animations(menu):
    temp_is_idle_animation_running = menu.is_idle_animation_running
    temp_is_animation_running = menu.is_animation_running
    menu.is_idle_animation_running = False
    menu.is_animation_running = False
    time.sleep(0.3)
    menu.is_idle_animation_running = temp_is_idle_animation_running
    menu.is_animation_running = temp_is_animation_running

def theaterChase(ledstrip, ledsettings, menu, speed_ms=None):
    """Movie theater light style chaser animation."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)
    strip = ledstrip.strip
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    brightness = calculate_brightness(ledsettings)

    red = int(ledsettings.get_backlight_color("Red") * brightness)
    green = int(ledsettings.get_backlight_color("Green") * brightness)
    blue = int(ledsettings.get_backlight_color("Blue") * brightness)

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        for q in range(5):
            for i in range(0, strip.numPixels(), 5):
                if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                    strip.setPixelColor(i + q, Color(red, green, blue))
            strip.show()
            time.sleep(wait_ms / 1000.0)
            for i in range(0, strip.numPixels(), 5):
                if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                    strip.setPixelColor(i + q, 0)

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)

def wheel(pos, ledsettings):
    """Generate rainbow colors across 0-255 positions."""

    brightness = calculate_brightness(ledsettings)

    # Ensure pos is within 0-255 range
    pos = pos % 255

    if pos < 85:
        r = (pos * 3) * brightness
        g = (255 - pos * 3) * brightness
        b = 0
    elif pos < 170:
        pos -= 85
        r = (255 - pos * 3) * brightness
        g = 0
        b = (pos * 3) * brightness
    else:
        pos -= 170
        r = 0
        g = (pos * 3) * brightness
        b = (255 - pos * 3) * brightness

    return Color(int(clamp(r, 0, 255)), int(clamp(g, 0, 255)), int(clamp(b, 0, 255)))


def rainbow(ledstrip, ledsettings, menu, speed_ms=None):
    """Draw rainbow that fades across all pixels at once."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    # Smooth animation logic
    step = 1.0
    target_wait_ms = 10.0
    if wait_ms > target_wait_ms:
        step = step * (target_wait_ms / wait_ms)
        wait_ms = target_wait_ms

    strip = ledstrip.strip

    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    j = 0.0

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        for i in range(strip.numPixels()):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, wheel(j, ledsettings))
        j += step
        if j >= 256:
            j = 0
        strip.show()
        time.sleep(wait_ms / 1000.0)
    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)

def fireplace(ledstrip, ledsettings, menu, speed_ms=None):
    """Fireplace flickering animation."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    strip = ledstrip.strip
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)

        while not cover_opened:
            if last_state != cover_opened:
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        brightness = calculate_brightness(ledsettings)

        # Simulate the flickering flames
        for i in range(strip.numPixels()):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                # Generate a random brightness to imitate flickering
                fireplace_brightness = int(brightness * random.randint(150, 255))
                strip.setPixelColor(i, Color(fireplace_brightness, int(brightness * 50), 0))  # Reddish color for fire
        strip.show()

        # Pause to create the flickering effect
        time.sleep(random.uniform(wait_ms / 500.0, wait_ms / 1000.0))

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def rainbowCycle(ledstrip, ledsettings, menu, speed_ms=None):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    # Smooth animation logic
    step = 1.0
    target_wait_ms = 10.0
    if wait_ms > target_wait_ms:
        step = step * (target_wait_ms / wait_ms)
        wait_ms = target_wait_ms

    strip = ledstrip.strip
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    j = 0.0

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        for i in range(strip.numPixels()):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, wheel((i * 256 / strip.numPixels() + j), ledsettings))
        j += step
        if j >= 256:
            j = 0
        strip.show()
        time.sleep(wait_ms / 1000.0)
    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def startup_animation(ledstrip, ledsettings, duration_ms=2000, max_leds=30):
    strip = ledstrip.strip
    total_pixels = strip.numPixels()

    num_red_leds = max_leds // 3
    num_blue_leds = max_leds // 3
    num_green_leds = max_leds - num_red_leds - num_blue_leds

    start_red_led = (total_pixels - max_leds) // 2
    start_blue_led = start_red_led + num_red_leds
    start_green_led = start_blue_led + num_blue_leds

    brightness = 0.0

    num_steps = 200

    step_delay = duration_ms / num_steps / 1000.0

    brightness_increment = 1.0 / num_steps

    for step in range(num_steps):
        if brightness < 0:
            break
        red = int(255 * brightness)
        blue = int(255 * brightness)
        green = int(255 * brightness)

        for i in range(start_red_led, start_blue_led):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, Color(red, 0, 0))
        for i in range(start_blue_led, start_green_led):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, Color(0, 0, blue))
        for i in range(start_green_led, start_green_led + num_green_leds):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, Color(0, green, 0))

        strip.show()
        brightness += brightness_increment

        if brightness > 0.5:
            brightness_increment *= -1

        time.sleep(int(step_delay))

    for i in range(total_pixels):
        strip.setPixelColor(i, 0)

    strip.show()


def theaterChaseRainbow(ledstrip, ledsettings, menu, speed_ms=None):
    """Rainbow movie theater light style chaser animation."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    strip = ledstrip.strip

    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    j = 0

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        for q in range(5):
            for i in range(0, strip.numPixels(), 5):
                if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                    strip.setPixelColor(i + q, wheel((i + j) % 255, ledsettings))
            strip.show()
            time.sleep(wait_ms / 1000.0)
            for i in range(0, strip.numPixels(), 5):
                if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                    strip.setPixelColor(i + q, 0)
        j += 1

        if j > 256:
            j = 0
    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def breathing(ledstrip, ledsettings, menu, speed_ms=None):
    """Breathing/pulsing animation."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    # Smooth animation logic
    step_size = 2.0
    target_wait_ms = 10.0
    if wait_ms > target_wait_ms:
        step_size = step_size * (target_wait_ms / wait_ms)
        wait_ms = target_wait_ms

    strip = ledstrip.strip

    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    multiplier = 24.0
    direction = step_size
    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        if multiplier >= 98 or multiplier < 24:
            direction *= -1
        multiplier += direction

        brightness = calculate_brightness(ledsettings)

        divide = (multiplier / float(100)) * brightness
        red = int(round(float(ledsettings.get_backlight_color("Red")) * float(divide)))
        green = int(round(float(ledsettings.get_backlight_color("Green")) * float(divide)))
        blue = int(round(float(ledsettings.get_backlight_color("Blue")) * float(divide)))

        for i in range(strip.numPixels()):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, Color(red, green, blue))
        strip.show()
        if wait_ms > 0:
            time.sleep(wait_ms / 1000.0)
    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def sound_of_da_police(ledstrip, ledsettings, menu, speed_ms=None):
    """Police-style alternating red/blue animation."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    # Smooth animation logic
    step = 14.0
    target_wait_ms = 10.0
    if wait_ms > target_wait_ms:
        step = step * (target_wait_ms / wait_ms)
        wait_ms = target_wait_ms

    strip = ledstrip.strip

    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    middle = strip.numPixels() / 2
    r_start = 0.0
    l_start = 196.0
    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        r_start += step
        l_start -= step

        brightness = calculate_brightness(ledsettings)

        for i in range(strip.numPixels()):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                if (i > middle) and r_start < i < (r_start + 40):
                    strip.setPixelColor(i, Color(int(255 * brightness), 0, 0))
                elif (i < middle) and l_start > i > (l_start - 40):
                    strip.setPixelColor(i, Color(0, 0, int(255 * brightness)))
                else:
                    strip.setPixelColor(i, Color(0, 0, 0))
        if r_start > 150:
            r_start = 0
            l_start = 175
        strip.show()
        time.sleep(wait_ms / 1000.0)
    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def scanner(ledstrip, ledsettings, menu, speed_ms=None):
    """Scanner beam animation."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    # Smooth animation logic
    step_size = 3.0
    target_wait_ms = 10.0
    if wait_ms > target_wait_ms:
        step_size = step_size * (target_wait_ms / wait_ms)
        wait_ms = target_wait_ms

    strip = ledstrip.strip

    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    position = 0.0
    direction = step_size
    scanner_length = 20

    red_fixed = ledsettings.get_backlight_color("Red")
    green_fixed = ledsettings.get_backlight_color("Green")
    blue_fixed = ledsettings.get_backlight_color("Blue")
    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        position += direction
        for i in range(strip.numPixels()):
            if (position - scanner_length) < i < (position + scanner_length):
                distance_from_position = position - i
                if distance_from_position < 0:
                    distance_from_position *= -1

                brightness = calculate_brightness(ledsettings)

                divide = ((scanner_length / 2) - distance_from_position) / float(scanner_length / 2)

                red = int(float(red_fixed) * float(divide) * brightness)
                green = int(float(green_fixed) * float(divide) * brightness)
                blue = int(float(blue_fixed) * float(divide) * brightness)

                if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                    if divide > 0:
                        strip.setPixelColor(i, Color(red, green, blue))
                    else:
                        strip.setPixelColor(i, Color(0, 0, 0))

        if position >= strip.numPixels() or position <= 1:
            direction *= -1
        strip.show()
        time.sleep(wait_ms / 1000.0)

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def chords(scale, ledstrip, ledsettings, menu):
    stop_animations(menu)

    time.sleep(0.2)
    strip = ledstrip.strip

    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        brightness = calculate_brightness(ledsettings)

        density = ledstrip.leds_per_meter / 72
        leds_to_update = list(range(strip.numPixels()))

        for i in range(int(strip.numPixels() / density)):
            note = i + 21
            note_position = get_note_position(note, ledstrip, ledsettings)
            c = get_scale_color(scale, note, ledsettings.key_in_scale, ledsettings.key_not_in_scale)
            try:
                leds_to_update.remove(note_position)
            except ValueError:
                pass

            if check_if_led_can_be_overwrite(note_position, ledstrip, ledsettings):
                strip.setPixelColor(note_position,
                                    Color(int(c[0] * brightness), int(c[1] * brightness), int(c[2] * brightness)))

        for i in leds_to_update:
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, Color(0, 0, 0))

        strip.show()
        time.sleep(0.01)
    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)

def colormap_animation(colormap, ledstrip, ledsettings, menu):
    stop_animations(menu)

    time.sleep(0.2)
    strip = ledstrip.strip

    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    while menu.is_idle_animation_running or menu.is_animation_running:
        if colormap not in cmap.colormaps:
            break

        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)
        
        brightness = calculate_brightness(ledsettings)

        led_a0 = get_note_position(21, ledstrip, ledsettings)
        led_c8 = get_note_position(108, ledstrip, ledsettings)
        step = 1 if led_c8 >= led_a0 else -1
        num_leds = abs(led_c8 - led_a0) + 1

        for i, led in enumerate(range(led_a0, led_c8 + step, step)):
            index = round(i * 255 / num_leds)
            red, green, blue = cmap.colormaps[colormap][index]
            strip.setPixelColor(led, Color(round(red * brightness), round(green * brightness), round(blue * brightness)))

        strip.show()
        time.sleep(0.01)

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def wave(ledstrip, ledsettings, menu, speed_ms=None):
    """Smooth traveling wave with gradient trail effect."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    # Smooth animation logic
    wave_speed = 0.1  # radians per frame
    target_wait_ms = 10.0
    if wait_ms > target_wait_ms:
        wave_speed = wave_speed * (target_wait_ms / wait_ms)
        wait_ms = target_wait_ms

    strip = ledstrip.strip
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    num_pixels = strip.numPixels()
    # Trail length is approximately 30% of strip length, but at least 10 pixels
    trail_length = max(10, int(num_pixels * 0.3))
    
    # Wave position (0 to 2*pi for one complete cycle)
    wave_position = 0.0

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        brightness = calculate_brightness(ledsettings)
        
        # Get base colors from backlight settings
        red_base = ledsettings.get_backlight_color("Red")
        green_base = ledsettings.get_backlight_color("Green")
        blue_base = ledsettings.get_backlight_color("Blue")

        # Clear all pixels first
        for i in range(num_pixels):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, Color(0, 0, 0))

        # Calculate wave effect for each pixel
        for i in range(num_pixels):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                # Normalize pixel position to 0-1 range
                pixel_pos = float(i) / float(num_pixels)
                
                # Map pixel position to wave phase (0 to 2*pi)
                pixel_phase = pixel_pos * 2 * math.pi
                
                # Calculate phase difference from current wave position
                phase_diff = pixel_phase - wave_position
                # Normalize to -pi to pi range
                phase_diff = ((phase_diff + math.pi) % (2 * math.pi)) - math.pi
                
                # Create smooth wave using sine function (creates wave peaks)
                # Shift by pi/2 so peak is at phase_diff = 0
                wave_value = (math.sin(phase_diff + math.pi / 2) + 1.0) / 2.0  # 0 to 1
                
                # Create gradient trail effect
                # Convert phase distance to approximate pixel distance
                phase_distance = abs(phase_diff)
                pixel_distance = (phase_distance / (2 * math.pi)) * num_pixels
                
                # Calculate fade factor based on distance from wave peak
                # Trail extends in both directions from the peak
                normalized_distance = min(pixel_distance / trail_length, 1.0)
                fade_factor = max(0.0, 1.0 - normalized_distance)
                
                # Combine wave pattern with trail fade for final brightness
                pixel_brightness = wave_value * fade_factor
                
                # Apply brightness to colors
                red = int(red_base * pixel_brightness * brightness)
                green = int(green_base * pixel_brightness * brightness)
                blue = int(blue_base * pixel_brightness * brightness)
                
                strip.setPixelColor(i, Color(red, green, blue))

        strip.show()
        
        # Update wave position for next frame
        wave_position += wave_speed
        if wave_position >= 2 * math.pi:
            wave_position -= 2 * math.pi
        
        time.sleep(wait_ms / 1000.0)

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def lava_lamp(ledstrip, ledsettings, menu, speed_ms=None):
    """Lava lamp animation with slow-moving organic blobs."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    # Smooth animation logic
    base_speed = 0.3  # Base movement speed per frame
    target_wait_ms = 10.0
    if wait_ms > target_wait_ms:
        base_speed = base_speed * (target_wait_ms / wait_ms)
        wait_ms = target_wait_ms

    strip = ledstrip.strip
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    num_pixels = strip.numPixels()
    
    # Create 4 blobs with different properties
    class Blob:
        def __init__(self, position, velocity, size, intensity):
            self.position = position  # Current position (0 to num_pixels)
            self.velocity = velocity  # Movement speed (pixels per frame)
            self.size = size  # Blob radius/size
            self.intensity = intensity  # Intensity multiplier (0.5 to 1.0)
    
    # Initialize blobs with varied properties
    blobs = [
        Blob(position=num_pixels * 0.2, velocity=base_speed * 0.8, size=num_pixels * 0.15, intensity=0.9),
        Blob(position=num_pixels * 0.5, velocity=-base_speed * 1.2, size=num_pixels * 0.12, intensity=0.7),
        Blob(position=num_pixels * 0.7, velocity=base_speed * 1.0, size=num_pixels * 0.18, intensity=0.85),
        Blob(position=num_pixels * 0.9, velocity=-base_speed * 0.6, size=num_pixels * 0.14, intensity=0.75),
    ]

    # Get base colors from backlight settings
    red_base = ledsettings.get_backlight_color("Red")
    green_base = ledsettings.get_backlight_color("Green")
    blue_base = ledsettings.get_backlight_color("Blue")
    
    brightness = calculate_brightness(ledsettings)

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        # Clear all pixels first
        pixel_colors = [[0, 0, 0] for _ in range(num_pixels)]

        # Update blob positions and calculate their contributions
        for blob in blobs:
            # Move blob
            blob.position += blob.velocity
            
            # Bounce at edges
            if blob.position <= 0:
                blob.position = 0
                blob.velocity = abs(blob.velocity)  # Reverse direction
            elif blob.position >= num_pixels - 1:
                blob.position = num_pixels - 1
                blob.velocity = -abs(blob.velocity)  # Reverse direction
            
            # Add slight random variation to velocity for organic feel
            if random.random() < 0.02:  # 2% chance per frame
                blob.velocity += random.uniform(-0.05, 0.05) * base_speed
                blob.velocity = clamp(blob.velocity, -base_speed * 2, base_speed * 2)
            
            # Calculate blob contribution to each pixel
            for i in range(num_pixels):
                distance = abs(i - blob.position)
                
                # Use Gaussian-like falloff for smooth blob edges
                # Normalize distance by blob size
                normalized_dist = distance / blob.size
                
                # Gaussian falloff: exp(-0.5 * (x/sigma)^2)
                # Using sigma = 0.5 for nice falloff
                falloff = math.exp(-2.0 * (normalized_dist ** 2))
                
                # Apply blob intensity
                contribution = falloff * blob.intensity
                
                # Add to pixel color (blend multiple blobs)
                pixel_colors[i][0] += red_base * contribution
                pixel_colors[i][1] += green_base * contribution
                pixel_colors[i][2] += blue_base * contribution

        # Render pixels with color blending
        for i in range(num_pixels):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                # Clamp and apply brightness
                red = int(clamp(pixel_colors[i][0] * brightness, 0, 255))
                green = int(clamp(pixel_colors[i][1] * brightness, 0, 255))
                blue = int(clamp(pixel_colors[i][2] * brightness, 0, 255))
                
                strip.setPixelColor(i, Color(red, green, blue))

        strip.show()
        time.sleep(wait_ms / 1000.0)

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def aurora(ledstrip, ledsettings, menu, speed_ms=None):
    """Aurora (Northern Lights) animation with flowing, undulating colors."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    # Smooth animation logic
    base_speed = 0.05  # Base movement speed per frame
    target_wait_ms = 20.0
    if wait_ms > target_wait_ms:
        base_speed = base_speed * (target_wait_ms / wait_ms)
        wait_ms = target_wait_ms

    strip = ledstrip.strip
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    num_pixels = strip.numPixels()
    brightness = calculate_brightness(ledsettings)

    # Aurora wave parameters - multiple overlapping waves for depth
    # Each wave has: phase (current position), speed, frequency, color_hue
    class AuroraWave:
        def __init__(self, phase, speed, frequency, color_hue, amplitude):
            self.phase = phase  # Current phase (0 to 2*pi)
            self.speed = speed  # Phase increment per frame
            self.frequency = frequency  # Spatial frequency (how many waves across strip)
            self.color_hue = color_hue  # Base hue (0-360 for HSV)
            self.amplitude = amplitude  # Wave amplitude (0-1)

    # Create multiple waves with different properties for rich aurora effect
    waves = [
        AuroraWave(phase=0.0, speed=base_speed * 0.8, frequency=2.0, color_hue=140, amplitude=0.7),  # Green wave
        AuroraWave(phase=math.pi, speed=base_speed * 1.2, frequency=1.5, color_hue=180, amplitude=0.6),  # Blue wave
        AuroraWave(phase=math.pi / 2, speed=base_speed * 0.6, frequency=2.5, color_hue=280, amplitude=0.5),  # Purple wave
        AuroraWave(phase=math.pi * 1.5, speed=base_speed * 1.0, frequency=1.8, color_hue=160, amplitude=0.4),  # Cyan-green wave
    ]

    # Time counter for color variation
    time_counter = 0.0

    def hsv_to_rgb(h, s, v):
        """Convert HSV to RGB (0-255 range)."""
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60.0) % 2 - 1))
        m = v - c

        if 0 <= h < 60:
            r, g, b = c, x, 0
        elif 60 <= h < 120:
            r, g, b = x, c, 0
        elif 120 <= h < 180:
            r, g, b = 0, c, x
        elif 180 <= h < 240:
            r, g, b = 0, x, c
        elif 240 <= h < 300:
            r, g, b = x, 0, c
        else:  # 300 <= h < 360
            r, g, b = c, 0, x

        return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        # Update wave phases
        for wave in waves:
            wave.phase += wave.speed
            if wave.phase >= 2 * math.pi:
                wave.phase -= 2 * math.pi

        # Update time counter for color variation
        time_counter += base_speed * 0.3

        # Calculate color for each pixel by blending all waves
        for i in range(num_pixels):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                # Normalize pixel position to 0-1 range
                pixel_pos = float(i) / float(num_pixels)

                # Initialize accumulated color (RGB)
                total_r, total_g, total_b = 0.0, 0.0, 0.0

                # Blend contributions from all waves
                for wave in waves:
                    # Calculate wave value at this pixel position
                    # Use sine wave for smooth undulation
                    wave_value = math.sin(pixel_pos * wave.frequency * 2 * math.pi + wave.phase)
                    
                    # Normalize to 0-1 range
                    wave_value = (wave_value + 1.0) / 2.0
                    
                    # Apply wave amplitude
                    wave_intensity = wave_value * wave.amplitude
                    
                    # Add slight time-based variation to hue for dynamic color shifts
                    hue_variation = math.sin(time_counter * 0.1) * 20  # ±20 degrees
                    current_hue = (wave.color_hue + hue_variation) % 360
                    
                    # Convert to RGB using HSV
                    # Saturation varies with wave intensity (more intense = more saturated)
                    saturation = 0.6 + wave_intensity * 0.4  # 0.6 to 1.0
                    # Value (brightness) varies with wave intensity
                    value = 0.3 + wave_intensity * 0.7  # 0.3 to 1.0
                    
                    r, g, b = hsv_to_rgb(current_hue, saturation, value)
                    
                    # Add to total (blend waves)
                    total_r += r * wave_intensity
                    total_g += g * wave_intensity
                    total_b += b * wave_intensity

                # Clamp and apply global brightness
                red = int(clamp(total_r * brightness, 0, 255))
                green = int(clamp(total_g * brightness, 0, 255))
                blue = int(clamp(total_b * brightness, 0, 255))

                strip.setPixelColor(i, Color(red, green, blue))

        strip.show()
        time.sleep(wait_ms / 1000.0)

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def stardust(ledstrip, ledsettings, menu, speed_ms=None):
    """Stardust/Sparkle animation - random LEDs twinkle and fade like stars."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    strip = ledstrip.strip
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    num_pixels = strip.numPixels()
    brightness = calculate_brightness(ledsettings)

    # Star class to track individual twinkling LEDs
    class Star:
        def __init__(self, led_index, fade_duration):
            self.led_index = led_index
            self.brightness = 1.0  # Start at full brightness
            self.fade_duration = fade_duration  # Total fade time in seconds
            self.age = 0.0  # Current age in seconds
            self.spawn_time = time.time()

    # Active stars list
    stars = []
    
    # Calculate spawn rate and fade duration based on speed
    # Faster speed = more stars, shorter fade time
    base_spawn_rate = 0.3  # Probability of spawning a new star per frame (0-1)
    base_fade_duration = 1.5  # Base fade duration in seconds
    
    # Adjust based on wait_ms (inverse relationship - faster wait = faster animation)
    speed_factor = max(0.3, min(3.0, 50.0 / max(wait_ms, 1)))  # Normalize to reasonable range
    spawn_rate = base_spawn_rate * speed_factor
    fade_duration = base_fade_duration / speed_factor
    
    # Maximum concurrent stars (10-20% of total LEDs)
    max_stars = max(1, int(num_pixels * 0.15))
    
    # Use warm white/yellow color for stars, or backlight color
    # Warm white: (255, 255, 200) with slight variation
    use_backlight_color = True
    base_red = int(ledsettings.get_backlight_color("Red")) if use_backlight_color else 255
    base_green = int(ledsettings.get_backlight_color("Green")) if use_backlight_color else 255
    base_blue = int(ledsettings.get_backlight_color("Blue")) if use_backlight_color else 200

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        current_time = time.time()
        frame_duration = wait_ms / 1000.0

        # Spawn new stars randomly
        if len(stars) < max_stars:
            # Chance to spawn 1-3 new stars per frame
            num_to_spawn = 0
            if random.random() < spawn_rate:
                num_to_spawn = random.randint(1, min(3, max_stars - len(stars)))
            
            for _ in range(num_to_spawn):
                # Find a random LED that can be overwritten
                attempts = 0
                led_index = None
                while attempts < 20:  # Try up to 20 times to find a valid LED
                    candidate = random.randint(0, num_pixels - 1)
                    if check_if_led_can_be_overwrite(candidate, ledstrip, ledsettings):
                        # Check if this LED is already a star
                        if not any(star.led_index == candidate for star in stars):
                            led_index = candidate
                            break
                    attempts += 1
                
                if led_index is not None:
                    # Add slight variation to fade duration for natural effect
                    star_fade_duration = fade_duration * random.uniform(0.7, 1.3)
                    stars.append(Star(led_index, star_fade_duration))

        # Update and fade existing stars
        stars_to_remove = []
        for star in stars:
            star.age += frame_duration
            
            # Calculate brightness (linear fade from 1.0 to 0.0)
            if star.age >= star.fade_duration:
                star.brightness = 0.0
                stars_to_remove.append(star)
            else:
                star.brightness = 1.0 - (star.age / star.fade_duration)
            
            # Apply star color with brightness scaling
            if star.brightness > 0 and check_if_led_can_be_overwrite(star.led_index, ledstrip, ledsettings):
                # Add slight color variation for each star (warm white with slight tint variation)
                color_variation = random.uniform(0.9, 1.1)
                red = int(clamp(base_red * star.brightness * brightness * color_variation, 0, 255))
                green = int(clamp(base_green * star.brightness * brightness * color_variation, 0, 255))
                blue = int(clamp(base_blue * star.brightness * brightness * color_variation, 0, 255))
                
                strip.setPixelColor(star.led_index, Color(red, green, blue))
        
        # Remove fully faded stars
        for star in stars_to_remove:
            stars.remove(star)
            # Clear the LED
            if check_if_led_can_be_overwrite(star.led_index, ledstrip, ledsettings):
                strip.setPixelColor(star.led_index, 0)

        strip.show()
        time.sleep(frame_duration)

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def kaleidoscope(ledstrip, ledsettings, menu, speed_ms=None):
    """Kaleidoscope animation - symmetric rotating patterns with colorful reflections."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    # Smooth animation logic
    rotation_speed = 0.05  # radians per frame
    target_wait_ms = 10.0
    if wait_ms > target_wait_ms:
        rotation_speed = rotation_speed * (target_wait_ms / wait_ms)
        wait_ms = target_wait_ms

    strip = ledstrip.strip
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    num_pixels = strip.numPixels()
    brightness = calculate_brightness(ledsettings)

    # Number of symmetric segments (4-way symmetry creates nice kaleidoscope effect)
    num_segments = 4
    segment_size = num_pixels / num_segments

    # Rotation angle (0 to 2*pi)
    rotation_angle = 0.0

    # Base pattern parameters
    pattern_wavelength = segment_size * 0.5  # Wavelength of the base pattern
    color_shift_speed = 0.02  # Speed of color shifting

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        # Clear all pixels first
        for i in range(num_pixels):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, Color(0, 0, 0))

        # Generate base pattern for first segment, then mirror to others
        for i in range(num_pixels):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                # Determine which segment this pixel belongs to
                segment_index = int(i / segment_size)
                
                # Position within the segment (0 to segment_size)
                pos_in_segment = (i % segment_size) / segment_size
                
                # For symmetric reflection, we need to map positions
                # Segment 0: normal (0 to 1)
                # Segment 1: reversed (1 to 0)
                # Segment 2: normal (0 to 1)
                # Segment 3: reversed (1 to 0)
                
                # Calculate mirrored position based on segment
                if segment_index % 2 == 0:
                    # Even segments: normal direction
                    normalized_pos = pos_in_segment
                else:
                    # Odd segments: reversed direction
                    normalized_pos = 1.0 - pos_in_segment
                
                # Apply rotation to the pattern
                rotated_pos = (normalized_pos + rotation_angle / (2 * math.pi)) % 1.0
                
                # Create wave pattern using sine
                wave_value = (math.sin(rotated_pos * 2 * math.pi * 2) + 1.0) / 2.0  # 0 to 1
                
                # Add secondary pattern for more complexity
                secondary_wave = (math.sin(rotated_pos * 2 * math.pi * 3 + rotation_angle) + 1.0) / 2.0
                pattern_intensity = (wave_value * 0.7 + secondary_wave * 0.3)
                
                # Calculate color based on position and rotation
                # Use rainbow colors that shift over time
                color_hue = (rotated_pos + rotation_angle / (2 * math.pi) + color_shift_speed * time.time()) % 1.0
                
                # Convert HSV to RGB (hue-based rainbow)
                # Hue: 0=red, 1/3=green, 2/3=blue, 1=red
                if color_hue < 1.0/3:
                    # Red to Green
                    r = 1.0 - color_hue * 3
                    g = color_hue * 3
                    b = 0.0
                elif color_hue < 2.0/3:
                    # Green to Blue
                    r = 0.0
                    g = 1.0 - (color_hue - 1.0/3) * 3
                    b = (color_hue - 1.0/3) * 3
                else:
                    # Blue to Red
                    r = (color_hue - 2.0/3) * 3
                    g = 0.0
                    b = 1.0 - (color_hue - 2.0/3) * 3
                
                # Apply pattern intensity to colors
                red = int(clamp(r * 255 * pattern_intensity * brightness, 0, 255))
                green = int(clamp(g * 255 * pattern_intensity * brightness, 0, 255))
                blue = int(clamp(b * 255 * pattern_intensity * brightness, 0, 255))
                
                strip.setPixelColor(i, Color(red, green, blue))

        strip.show()
        
        # Update rotation angle for next frame
        rotation_angle += rotation_speed
        if rotation_angle >= 2 * math.pi:
            rotation_angle -= 2 * math.pi
        
        time.sleep(wait_ms / 1000.0)

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def color_ripple(ledstrip, ledsettings, menu, speed_ms=None):
    """Color Ripple animation - expanding ripples of color from random points, like dropping stones in water."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    # Smooth animation logic - ensure at least 15 FPS (66.67ms max wait)
    # For smooth animation, cap frame time but adjust expansion speed based on user speed preference
    target_wait_ms = 66.67  # Maximum wait for 15 FPS minimum
    base_expansion_speed = 1.5  # pixels per frame (increased for smoother motion)
    
    # If user wants slower animation, scale expansion speed but keep frame rate smooth
    if wait_ms > target_wait_ms:
        # Scale expansion speed proportionally, but cap wait time for smoothness
        speed_scale = target_wait_ms / wait_ms
        base_expansion_speed = base_expansion_speed * speed_scale
        wait_ms = target_wait_ms
    elif wait_ms < 20.0:
        # If very fast, don't go below 20ms (50 FPS max) to avoid excessive CPU usage
        wait_ms = 20.0

    strip = ledstrip.strip
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    num_pixels = strip.numPixels()
    brightness = calculate_brightness(ledsettings)

    # Ripple class to track each active ripple
    class Ripple:
        def __init__(self, center_position, expansion_speed, max_radius):
            self.center = center_position  # Center position of the ripple
            self.radius = 0.0  # Current radius (how far it has expanded)
            self.expansion_speed = expansion_speed  # How fast it expands (pixels per frame)
            self.max_radius = max_radius  # Maximum radius before it fades out
            self.intensity = 1.0  # Current intensity (fades as radius increases)

    # Active ripples list
    ripples = []
    
    # Calculate spawn rate based on speed
    # Adjust spawn rate to work with smooth frame timing
    # Use original wait_ms (before capping) to determine spawn frequency
    original_wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)
    base_spawn_rate = 0.08  # Probability of spawning a new ripple per frame (adjusted for smooth animation)
    # Scale spawn rate based on user's speed preference (slower speed = fewer ripples)
    speed_factor = max(0.3, min(2.0, 100.0 / max(original_wait_ms, 1)))
    spawn_rate = base_spawn_rate * speed_factor
    
    # Maximum concurrent ripples (3-5 ripples work well)
    max_ripples = 4
    
    # Maximum radius for ripples (about 40% of strip length)
    max_ripple_radius = num_pixels * 0.4
    
    # Get base colors from backlight settings
    red_base = ledsettings.get_backlight_color("Red")
    green_base = ledsettings.get_backlight_color("Green")
    blue_base = ledsettings.get_backlight_color("Blue")
    
    # Pre-calculate which LEDs can be overwritten (cache for performance)
    overwritable_leds = [i for i in range(num_pixels) if check_if_led_can_be_overwrite(i, ledstrip, ledsettings)]
    
    # Pre-calculate brightness multiplier
    brightness_mult = brightness

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        # Spawn new ripples randomly
        if len(ripples) < max_ripples:
            if random.random() < spawn_rate:
                # Find a random position that can be overwritten
                if overwritable_leds:
                    center_pos = random.choice(overwritable_leds)
                    # Add slight variation to expansion speed for natural effect
                    expansion_speed = base_expansion_speed * random.uniform(0.8, 1.2)
                    ripples.append(Ripple(center_pos, expansion_speed, max_ripple_radius))

        # Use pixel buffer for efficient rendering (avoid reading from strip)
        pixel_buffer = [[0, 0, 0] for _ in range(num_pixels)]

        # Update and render ripples
        ripples_to_remove = []
        for ripple in ripples:
            # Update ripple radius
            ripple.radius += ripple.expansion_speed
            
            # Calculate intensity based on radius (fade out as it expands)
            normalized_radius = ripple.radius / ripple.max_radius
            if normalized_radius >= 1.0:
                # Ripple has fully expanded, mark for removal
                ripples_to_remove.append(ripple)
                continue
            
            # Smooth fade using sine curve (starts at 1.0, fades to 0.0)
            ripple.intensity = math.sin((1.0 - normalized_radius) * math.pi / 2.0)
            
            # Calculate affected LED range (only iterate through affected LEDs)
            start_led = max(0, int(ripple.center - ripple.radius))
            end_led = min(num_pixels - 1, int(ripple.center + ripple.radius))
            ripple_radius_sq = ripple.radius * ripple.radius  # Pre-calculate for distance check
            
            # Render ripple effect on LEDs
            for led_index in range(start_led, end_led + 1):
                if led_index not in overwritable_leds:
                    continue
                
                # Calculate distance from ripple center (using squared distance for efficiency)
                distance = abs(led_index - ripple.center)
                
                # Only affect LEDs within current radius
                if distance > ripple.radius:
                    continue
                
                # Calculate brightness based on distance from center
                # Use simplified calculation for better performance
                if ripple.radius > 0:
                    normalized_distance = distance / ripple.radius
                else:
                    normalized_distance = 0
                
                # Simplified ring pattern using triangle wave (much faster than sine)
                # Creates similar visual effect with better performance
                ring_phase = (normalized_distance * 4.0) % 2.0
                if ring_phase > 1.0:
                    ring_phase = 2.0 - ring_phase
                ring_pattern = 0.7 + ring_phase * 0.3
                
                # Combine distance falloff with ring pattern and overall intensity
                distance_falloff = 1.0 - normalized_distance * 0.5
                pixel_brightness = distance_falloff * ring_pattern * ripple.intensity
                if pixel_brightness > 1.0:
                    pixel_brightness = 1.0
                elif pixel_brightness < 0.0:
                    continue  # Skip if too dim to save calculations
                
                # Calculate new color for this ripple (pre-multiply for efficiency)
                new_red = int(red_base * pixel_brightness * brightness_mult)
                new_green = int(green_base * pixel_brightness * brightness_mult)
                new_blue = int(blue_base * pixel_brightness * brightness_mult)
                
                # Additive blending in buffer (much faster than reading from strip)
                pixel_buffer[led_index][0] = min(255, pixel_buffer[led_index][0] + new_red)
                pixel_buffer[led_index][1] = min(255, pixel_buffer[led_index][1] + new_green)
                pixel_buffer[led_index][2] = min(255, pixel_buffer[led_index][2] + new_blue)
        
        # Remove fully expanded ripples
        for ripple in ripples_to_remove:
            ripples.remove(ripple)

        # Write pixel buffer to strip (single pass, much faster)
        for led_index in overwritable_leds:
            strip.setPixelColor(led_index, Color(
                pixel_buffer[led_index][0],
                pixel_buffer[led_index][1],
                pixel_buffer[led_index][2]
            ))

        strip.show()
        time.sleep(wait_ms / 1000.0)

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)


def fireworks(ledstrip, ledsettings, menu, speed_ms=None):
    """Fireworks animation - colorful particle bursts that explode and fade away."""
    from lib.animation_speed import get_global_speed_ms
    stop_animations(menu)

    # Use global speed from settings
    wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)

    # Smooth animation logic - ensure at least 15 FPS (66.67ms max wait)
    target_wait_ms = 66.67  # Maximum wait for 15 FPS minimum
    base_particle_speed = 0.8  # pixels per frame
    
    # If user wants slower animation, scale particle speed but keep frame rate smooth
    if wait_ms > target_wait_ms:
        speed_scale = target_wait_ms / wait_ms
        base_particle_speed = base_particle_speed * speed_scale
        wait_ms = target_wait_ms
    elif wait_ms < 20.0:
        # If very fast, don't go below 20ms (50 FPS max) to avoid excessive CPU usage
        wait_ms = 20.0

    strip = ledstrip.strip
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    num_pixels = strip.numPixels()
    brightness = calculate_brightness(ledsettings)

    # Particle class to track individual particles in a burst
    class Particle:
        def __init__(self, start_pos, velocity, color, lifetime):
            self.position = float(start_pos)  # Current position (float for smooth movement)
            self.velocity = velocity  # Velocity in pixels per frame
            self.color = color  # RGB tuple (0-255 each)
            self.age = 0.0  # Current age in frames
            self.lifetime = lifetime  # Total lifetime in frames
            self.brightness = 1.0  # Current brightness (fades over time)

    # Burst class to track firework bursts
    class Burst:
        def __init__(self, center_position, particles):
            self.center = center_position
            self.particles = particles  # List of Particle objects
            self.age = 0.0

    # Active bursts list
    bursts = []
    
    # Calculate spawn rate based on speed
    original_wait_ms = speed_ms if speed_ms is not None else get_global_speed_ms(ledsettings.usersettings)
    base_spawn_rate = 0.06  # Probability of spawning a new burst per frame
    speed_factor = max(0.3, min(2.0, 100.0 / max(original_wait_ms, 1)))
    spawn_rate = base_spawn_rate * speed_factor
    
    # Maximum concurrent bursts (2-4 bursts work well)
    max_bursts = 3
    
    # Particle lifetime based on speed (faster speed = shorter lifetime)
    base_lifetime = 60.0  # frames
    lifetime_factor = max(0.5, min(2.0, 50.0 / max(original_wait_ms, 1)))
    particle_lifetime = base_lifetime / lifetime_factor
    
    # Number of particles per burst
    particles_per_burst = 8
    
    # Pre-calculate which LEDs can be overwritten (cache for performance)
    overwritable_leds = [i for i in range(num_pixels) if check_if_led_can_be_overwrite(i, ledstrip, ledsettings)]
    
    # Pre-calculate brightness multiplier
    brightness_mult = brightness

    def hsv_to_rgb(h, s, v):
        """Convert HSV to RGB (0-1 range for h, s, v)."""
        if s == 0.0:
            return (v, v, v)
        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        i = i % 6
        if i == 0:
            return (v, t, p)
        elif i == 1:
            return (q, v, p)
        elif i == 2:
            return (p, v, t)
        elif i == 3:
            return (p, q, v)
        elif i == 4:
            return (t, p, v)
        else:
            return (v, p, q)

    def get_random_color():
        """Generate a random vibrant color."""
        # Use rainbow colors with high saturation
        hue = random.random()  # 0.0 to 1.0
        saturation = random.uniform(0.7, 1.0)  # High saturation for vibrant colors
        value = random.uniform(0.8, 1.0)  # High value for bright colors
        r, g, b = hsv_to_rgb(hue, saturation, value)
        return (int(r * 255), int(g * 255), int(b * 255))

    while menu.is_idle_animation_running or menu.is_animation_running:
        last_state = 1
        cover_opened = GPIO.input(SENSECOVER)
        while not cover_opened:
            if last_state != cover_opened:
                # clear if changed
                fastColorWipe(strip, True, ledsettings)
            time.sleep(.1)
            last_state = cover_opened
            cover_opened = GPIO.input(SENSECOVER)

        # Spawn new bursts randomly
        if len(bursts) < max_bursts:
            if random.random() < spawn_rate:
                # Find a random position that can be overwritten
                if overwritable_leds:
                    center_pos = random.choice(overwritable_leds)
                    
                    # Create particles for this burst
                    particles = []
                    base_color = get_random_color()
                    
                    for _ in range(particles_per_burst):
                        # Random velocity direction (spread outward)
                        angle = random.uniform(0, 2 * math.pi)
                        speed = base_particle_speed * random.uniform(0.5, 1.5)
                        velocity = speed * math.cos(angle)  # Horizontal component
                        
                        # Slight color variation for each particle
                        color_variation = random.uniform(0.7, 1.0)
                        particle_color = (
                            int(base_color[0] * color_variation),
                            int(base_color[1] * color_variation),
                            int(base_color[2] * color_variation)
                        )
                        
                        # Random lifetime variation
                        lifetime = particle_lifetime * random.uniform(0.8, 1.2)
                        
                        particles.append(Particle(center_pos, velocity, particle_color, lifetime))
                    
                    bursts.append(Burst(center_pos, particles))

        # Use pixel buffer for efficient rendering
        pixel_buffer = [[0, 0, 0] for _ in range(num_pixels)]

        # Update and render bursts
        bursts_to_remove = []
        for burst in bursts:
            burst.age += 1.0
            
            # Update particles in this burst
            particles_to_remove = []
            for particle in burst.particles:
                particle.age += 1.0
                
                # Update position
                particle.position += particle.velocity
                
                # Calculate brightness based on age (fade out)
                if particle.age >= particle.lifetime:
                    particle.brightness = 0.0
                    particles_to_remove.append(particle)
                else:
                    # Linear fade from 1.0 to 0.0
                    particle.brightness = 1.0 - (particle.age / particle.lifetime)
                
                # Only render if particle is still visible and within bounds
                if particle.brightness > 0.01 and 0 <= particle.position < num_pixels:
                    led_index = int(particle.position)
                    if led_index in overwritable_leds:
                        # Calculate final color with brightness
                        final_red = int(particle.color[0] * particle.brightness * brightness_mult)
                        final_green = int(particle.color[1] * particle.brightness * brightness_mult)
                        final_blue = int(particle.color[2] * particle.brightness * brightness_mult)
                        
                        # Additive blending in buffer
                        pixel_buffer[led_index][0] = min(255, pixel_buffer[led_index][0] + final_red)
                        pixel_buffer[led_index][1] = min(255, pixel_buffer[led_index][1] + final_green)
                        pixel_buffer[led_index][2] = min(255, pixel_buffer[led_index][2] + final_blue)
            
            # Remove dead particles
            for particle in particles_to_remove:
                burst.particles.remove(particle)
            
            # Remove burst if all particles are dead
            if len(burst.particles) == 0:
                bursts_to_remove.append(burst)
        
        # Remove empty bursts
        for burst in bursts_to_remove:
            bursts.remove(burst)

        # Write pixel buffer to strip
        for led_index in overwritable_leds:
            strip.setPixelColor(led_index, Color(
                pixel_buffer[led_index][0],
                pixel_buffer[led_index][1],
                pixel_buffer[led_index][2]
            ))

        strip.show()
        time.sleep(wait_ms / 1000.0)

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)
