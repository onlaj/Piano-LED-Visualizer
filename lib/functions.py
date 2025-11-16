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


def manage_idle_animation(ledstrip, ledsettings, menu, midiports, state_manager=None):
    animation_delay_minutes = int(menu.led_animation_delay)
    if animation_delay_minutes == 0:
        return

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
        
    menu.is_idle_animation_running = True

    if menu.led_animation == "Theater Chase":
            menu.t = threading.Thread(target=theaterChase, args=(ledstrip,
                                                                 Color(127, 127, 127),
                                                                 ledsettings,
                                                                 menu))
            menu.t.start()
    if menu.led_animation == "Fireplace":
            menu.t = threading.Thread(target=theaterChase, args=(ledstrip,
                                                                 Color(127, 127, 127),
                                                                 ledsettings,
                                                                 menu))
            menu.t.start()
    if menu.led_animation == "Breathing Slow":
            menu.t = threading.Thread(target=breathing, args=(ledstrip,
                                                              ledsettings,
                                                              menu, "Slow"))
            menu.t.start()
    if menu.led_animation == "Rainbow Slow":
            menu.t = threading.Thread(target=rainbow, args=(ledstrip,
                                                            ledsettings,
                                                            menu, 50))
            menu.t.start()
    if menu.led_animation == "Rainbow Cycle Slow":
            menu.t = threading.Thread(target=rainbowCycle, args=(ledstrip,
                                                                 ledsettings,
                                                                 menu, 50))
            menu.t.start()
    if menu.led_animation == "Theater Chase Rainbow":
            menu.t = threading.Thread(target=theaterChaseRainbow, args=(ledstrip,
                                                                        ledsettings,
                                                                        menu, 5))
            menu.t.start()
    if menu.led_animation == "Sound of da police":
            menu.t = threading.Thread(target=sound_of_da_police, args=(ledstrip,
                                                                       ledsettings,
                                                                       menu, 1))
            menu.t.start()
    if menu.led_animation == "Scanner":
            menu.t = threading.Thread(target=scanner, args=(ledstrip,
                                                            ledsettings,
                                                            menu, 1))
            menu.t.start()
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

def theaterChase(ledstrip, ledsettings, menu, wait_ms=20):
    """Movie theater light style chaser animation."""
    stop_animations(menu)
    strip = ledstrip.strip
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

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

    if pos < 85:
        return Color(int((pos * 3) * brightness), int((255 - pos * 3) * brightness), 0)
    elif pos < 170:
        pos -= 85
        return Color(int((255 - pos * 3) * brightness), 0, int((pos * 3) * brightness))
    else:
        pos -= 170
        return Color(0, int((pos * 3) * brightness), int((255 - pos * 3) * brightness))


def rainbow(ledstrip, ledsettings, menu, speed="Medium"):
    stop_animations(menu)

    speed_map = {
        "Slow": 50,
        "Fast": 2,
    }

    wait_ms = speed_map.get(speed, 20)

    """Draw rainbow that fades across all pixels at once."""
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

        for i in range(strip.numPixels()):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, wheel(j & 255, ledsettings))
        j += 1
        if j >= 256:
            j = 0
        strip.show()
        time.sleep(wait_ms / 1000.0)
    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)

def fireplace(ledstrip, ledsettings, menu):
    stop_animations(menu)


    wait_ms = 20

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


def rainbowCycle(ledstrip, ledsettings, menu, speed="Medium"):
    stop_animations(menu)
    speed_map = {
        "Slow": 50,
        "Fast": 1,
    }

    wait_ms = speed_map.get(speed, 20)

    """Draw rainbow that uniformly distributes itself across all pixels."""
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

        for i in range(strip.numPixels()):
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255, ledsettings))
        j += 1
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


def theaterChaseRainbow(ledstrip, ledsettings, menu, speed="Medium"):
    stop_animations(menu)
    speed_map = {
        "Slow": 10,
        "Fast": 2,
    }

    wait_ms = speed_map.get(speed, 5)

    """Rainbow movie theater light style chaser animation."""
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


def breathing(ledstrip, ledsettings, menu, speed="Medium"):
    stop_animations(menu)
    speed_map = {
        "Slow": 25,
        "Fast": 5,
    }

    wait_ms = speed_map.get(speed, 10)

    strip = ledstrip.strip

    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    multiplier = 24
    direction = 2
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


def sound_of_da_police(ledstrip, ledsettings, menu, wait_ms=5):
    stop_animations(menu)

    strip = ledstrip.strip

    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    middle = strip.numPixels() / 2
    r_start = 0
    l_start = 196
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

        r_start += 14
        l_start -= 14

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


def scanner(ledstrip, ledsettings, menu, wait_ms=1):
    stop_animations(menu)

    strip = ledstrip.strip

    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()

    position = 0
    direction = 3
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
        time.sleep(0.05)
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
        time.sleep(0.1)

    menu.is_idle_animation_running = False
    fastColorWipe(strip, True, ledsettings)
