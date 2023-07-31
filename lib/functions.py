import threading
from lib.neopixel import *
import mido
import datetime
import psutil
import time
import socket
import RPi.GPIO as GPIO
import math
import subprocess

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


def get_current_connections():
    try:
        output = subprocess.check_output(['iwconfig'], text=True)
        for line in output.splitlines():
            if "ESSID:" in line:
                ssid = line.split("ESSID:")[-1].strip().strip('"')
                if ssid != "off/any":
                    return ssid
                else:
                    return "Not connected to any Wi-Fi network."
        return "No Wi-Fi interface found."
    except subprocess.CalledProcessError:
        return "Error occurred while getting Wi-Fi information."


def disconnect_from_wifi(ssid):
    try:
        # Disconnect from the given Wi-Fi network using the 'nmcli' command
        # TODO test if it's working
        subprocess.run(['nmcli', 'con', 'down', ssid], check=True)

        return True
    except subprocess.CalledProcessError as e:
        return False


def get_wifi_networks():
    try:
        output = subprocess.check_output(['sudo', 'iwlist', 'wlan0', 'scan'], stderr=subprocess.STDOUT)
        networks = output.decode().split('Cell ')

        def calculate_signal_strength(level):
            # Map the signal level to a percentage (0% to 100%) linearly.
            # -50 dBm or higher -> 100%
            # -90 dBm or lower -> 0%
            if level >= -50:
                return 100
            elif level <= -90:
                return 0
            else:
                return 100 - (100 / 40) * (level + 90)

        wifi_list = []
        for network in networks[1:]:
            wifi_data = {}

            ssid_line = [line for line in network.split('\n') if 'ESSID:' in line]
            if ssid_line:
                wifi_data['ESSID'] = ssid_line[0].split('ESSID:')[1].strip('"')

            freq_line = [line for line in network.split('\n') if 'Frequency:' in line]
            if freq_line:
                wifi_data['Frequency'] = freq_line[0].split('Frequency:')[1].split(' (')[0]

            signal_line = [line for line in network.split('\n') if 'Signal level=' in line]
            if signal_line:
                signal_level = int(signal_line[0].split('Signal level=')[1].split(' dBm')[0])
                wifi_data['Signal Strength'] = calculate_signal_strength(signal_level)

            signal_dbm = [line for line in network.split('\n') if 'Signal level=' in line]
            if signal_dbm:
                signal_dbm = signal_dbm[0].split('Signal level=')[1].split(' dBm')[0]
                wifi_data['Signal dBm'] = int(signal_dbm)

            wifi_list.append(wifi_data)

        return wifi_list

    except subprocess.CalledProcessError as e:
        print("Error while scanning Wi-Fi networks:", e.output)
        return []


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
    midiports.pending_queue.append(mido.Message('note_on'))

    if song_path in saving.is_playing_midi.keys():
        menu.render_message(song_path, "Already playing", 2000)
        return

    saving.is_playing_midi.clear()

    saving.is_playing_midi[song_path] = True
    menu.render_message("Playing: ", song_path, 2000)
    saving.t = threading.currentThread()

    try:
        mid = mido.MidiFile("Songs/" + song_path)
        fastColorWipe(ledstrip.strip, True, ledsettings)
        # length = mid.length
        t0 = False
        total_delay = 0
        delay = 0
        for message in mid:
            if song_path in saving.is_playing_midi.keys():
                if not t0:
                    t0 = time.time()

                total_delay += message.time
                current_time = (time.time() - t0) + message.time
                drift = total_delay - current_time

                if drift < 0:
                    delay = message.time + drift
                else:
                    delay = message.time
                if delay < 0:
                    delay = 0

                if delay > 0:
                    time.sleep(delay)
                if not message.is_meta:
                    midiports.playport.send(message)
                    midiports.pending_queue.append(message.copy(time=0))

            else:
                break
        print('play time: {:.2f} s (expected {:.2f})'.format(time.time() - t0, total_delay))
        # print('play time: {:.2f} s (expected {:.2f})'.format(time.time() - t0, length))
        # saving.is_playing_midi = False
    except FileNotFoundError:
        menu.render_message(song_path, "File not found", 2000)
    except Exception as e:
        menu.render_message(song_path, "Error while playing song "+str(e), 2000)
        print(e)
    saving.is_playing_midi.clear()


def screensaver(menu, midiports, saving, ledstrip, ledsettings):
    last_cpu_average = 0

    KEY2 = 20
    GPIO.setup(KEY2, GPIO.IN, GPIO.PUD_UP)

    delay = 0.1
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
        menu.render_message("Error while getting ports " + str(e), 2000)
        print("Error while getting ports " + str(e))
    while True:
        if (time.time() - saving.start_time) > 3600 and delay < 0.5 and menu.screensaver_is_running is False:
            delay = 0.9
            interval = 5 / float(delay)
            cpu_history = [None] * int(interval)
            cpu_average = 0
            i = 0

        if int(menu.screen_off_delay) > 0 and ((time.time() - saving.start_time) > (int(menu.screen_off_delay) * 60)):
            menu.screen_status = 0
            GPIO.output(24, 0)

        if int(menu.led_animation_delay) > 0 and ((time.time() - saving.start_time) > (
                int(menu.led_animation_delay) * 60)) and menu.screensaver_is_running is False:
            menu.screensaver_is_running = True
            if menu.led_animation == "Theater Chase":
                menu.t = threading.Thread(target=theaterChase, args=(ledstrip.strip,
                                                                     Color(127, 127, 127),
                                                                     ledsettings,
                                                                     menu))
                menu.t.start()
            if menu.led_animation == "Breathing Slow":
                menu.t = threading.Thread(target=breathing, args=(ledstrip.strip,
                                                                  ledsettings,
                                                                  menu, "Slow"))
                menu.t.start()
            if menu.led_animation == "Rainbow Slow":
                menu.t = threading.Thread(target=rainbow, args=(ledstrip.strip,
                                                                ledsettings,
                                                                menu, 50))
                menu.t.start()
            if menu.led_animation == "Rainbow Cycle Slow":
                menu.t = threading.Thread(target=rainbowCycle, args=(ledstrip.strip,
                                                                     ledsettings,
                                                                     menu, 50))
                menu.t.start()
            if menu.led_animation == "Theater Chase Rainbow":
                menu.t = threading.Thread(target=theaterChaseRainbow, args=(ledstrip.strip,
                                                                            ledsettings,
                                                                            menu, 5))
                menu.t.start()
            if menu.led_animation == "Sound of da police":
                menu.t = threading.Thread(target=sound_of_da_police, args=(ledstrip.strip,
                                                                           ledsettings,
                                                                           menu, 1))
                menu.t.start()
            if menu.led_animation == "Scanner":
                menu.t = threading.Thread(target=scanner, args=(ledstrip.strip,
                                                                ledsettings,
                                                                menu, 1))
                menu.t.start()

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
                temp = find_between(str(psutil.sensors_temperatures()["cpu-thermal"]), "current=", ",")
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
            if str(midiports.inport.poll()) != "None":
                menu.screensaver_is_running = False
                saving.start_time = time.time()
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
            saving.start_time = time.time()
            menu.screen_status = 1
            GPIO.output(24, 1)
            midiports.reconnect_ports()
            menu.show()
            break


# Get note position on the strip
def get_note_position(note, ledstrip, ledsettings):
    note_offsets = ledsettings.note_offsets
    note_offset = 0
    for i in range(0, len(note_offsets)):
        if note > note_offsets[i][0]:
            note_offset = note_offsets[i][1]
            break
    note_offset -= ledstrip.shift

    density = ledstrip.leds_per_meter / 72

    note_pos_raw = int(density * (note - 20) - note_offset)
    if ledstrip.reverse:
        return max(0, ledstrip.led_number - note_pos_raw)
    else:
        return max(0, note_pos_raw)


# scale: 1 means in C, scale: 2 means in C#, scale: 3 means in D, etc...
# and scale: 1 means in C m, scale: 2 means in C# m, scale: 3 means in D m, etc...
def get_scale_color(scale, note_position, ledsettings):
    scale = int(scale)
    if scale < 12:
        notes_in_scale = [0, 2, 4, 5, 7, 9, 11]
    else:
        notes_in_scale = [0, 2, 3, 5, 7, 8, 10]
    note_position = (note_position - scale) % 12

    if note_position in notes_in_scale:
        return list(ledsettings.key_in_scale.values())
    else:
        return list(ledsettings.key_not_in_scale.values())


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
    return (math.exp(-p*x)-1) / (math.exp(-p)-1)


def gammacurve(x, p):
    if p != 0:
        return x**(1/p)
    else:
        return 1


def check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
    if ledsettings.adjacent_mode == "Off":
        if ledstrip.keylist_status[i] == 0 and ledstrip.keylist[i] == 0:
            return True
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
    brightness = ledsettings.backlight_brightness_percent / 100
    red = int(ledsettings.get_backlight_color("Red") * brightness)
    green = int(ledsettings.get_backlight_color("Green") * brightness)
    blue = int(ledsettings.get_backlight_color("Blue") * brightness)
    color = Color(green, red, blue)
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    if update:
        strip.show()


def calculate_brightness(ledsettings):
    if ledsettings.backlight_brightness_percent == 0:
        brightness = 100
    else:
        brightness = ledsettings.backlight_brightness_percent

    brightness /= 100

    return brightness


def theaterChase(ledstrip, ledsettings, menu, wait_ms=25):
    """Movie theater light style chaser animation."""
    menu.screensaver_is_running = False
    time.sleep(0.5)
    strip = ledstrip.strip
    if menu.screensaver_is_running:
        return
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    j = 0
    menu.screensaver_is_running = True

    while menu.screensaver_is_running:
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

        red = int(ledsettings.get_backlight_color("Red") * brightness)
        green = int(ledsettings.get_backlight_color("Green") * brightness)
        blue = int(ledsettings.get_backlight_color("Blue") * brightness)

        for q in range(5):
            for i in range(0, strip.numPixels(), 5):
                if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                    strip.setPixelColor(i + q, Color(green, red, blue))
            strip.show()
            time.sleep(wait_ms / 1000.0)
            for i in range(0, strip.numPixels(), 5):
                if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                    strip.setPixelColor(i + q, 0)
        j += 1
        if j > 256:
            j = 0
    menu.screensaver_is_running = False
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
    speed_map = {
        "Slow": 50,
        "Fast": 2,
    }

    wait_ms = speed_map.get(speed, 20)

    """Draw rainbow that fades across all pixels at once."""
    menu.screensaver_is_running = False
    time.sleep(0.2)
    strip = ledstrip.strip
    if menu.screensaver_is_running:
        return
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    j = 0
    menu.screensaver_is_running = True
    while menu.screensaver_is_running:
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
    menu.screensaver_is_running = False
    fastColorWipe(strip, True, ledsettings)


def rainbowCycle(ledstrip, ledsettings, menu, speed="Medium"):
    speed_map = {
        "Slow": 50,
        "Fast": 1,
    }

    wait_ms = speed_map.get(speed, 20)

    """Draw rainbow that uniformly distributes itself across all pixels."""
    menu.screensaver_is_running = False
    time.sleep(0.2)
    strip = ledstrip.strip
    if menu.screensaver_is_running:
        return
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    j = 0
    menu.screensaver_is_running = True
    while menu.screensaver_is_running:
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
    menu.screensaver_is_running = False
    fastColorWipe(strip, True, ledsettings)


def theaterChaseRainbow(ledstrip, ledsettings, menu, speed="Medium"):
    speed_map = {
        "Slow": 10,
        "Fast": 2,
    }

    wait_ms = speed_map.get(speed, 5)

    """Rainbow movie theater light style chaser animation."""
    menu.screensaver_is_running = False
    time.sleep(0.5)
    strip = ledstrip.strip
    if menu.screensaver_is_running:
        return
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    j = 0
    menu.screensaver_is_running = True

    while menu.screensaver_is_running:
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
    menu.screensaver_is_running = False
    fastColorWipe(strip, True, ledsettings)


def breathing(ledstrip, ledsettings, menu, speed="Medium"):

    speed_map = {
        "Slow": 25,
        "Fast": 5,
    }

    wait_ms = speed_map.get(speed, 10)

    menu.screensaver_is_running = False
    time.sleep(0.1)
    strip = ledstrip.strip
    if menu.screensaver_is_running:
        return
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    menu.screensaver_is_running = True

    multiplier = 24
    direction = 2
    while menu.screensaver_is_running:
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
                strip.setPixelColor(i, Color(green, red, blue))
        strip.show()
        if wait_ms > 0:
            time.sleep(wait_ms / 1000.0)
    menu.screensaver_is_running = False
    fastColorWipe(strip, True, ledsettings)


def sound_of_da_police(ledstrip, ledsettings, menu, wait_ms=5):
    menu.screensaver_is_running = False
    time.sleep(0.1)
    strip = ledstrip.strip
    if menu.screensaver_is_running:
        return
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    menu.screensaver_is_running = True
    middle = strip.numPixels() / 2
    r_start = 0
    l_start = 196
    while menu.screensaver_is_running:
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
                    strip.setPixelColor(i, Color(0, int(255 * brightness), 0))
                elif (i < middle) and l_start > i > (l_start - 40):
                    strip.setPixelColor(i, Color(0, 0, int(255 * brightness)))
                else:
                    strip.setPixelColor(i, Color(0, 0, 0))
        if r_start > 150:
            r_start = 0
            l_start = 175
        strip.show()
        time.sleep(wait_ms / 1000.0)
    menu.screensaver_is_running = False
    fastColorWipe(strip, True, ledsettings)


def scanner(ledstrip, ledsettings, menu, wait_ms=1):
    menu.screensaver_is_running = False
    time.sleep(0.1)
    strip = ledstrip.strip
    if menu.screensaver_is_running:
        return
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    menu.screensaver_is_running = True

    position = 0
    direction = 3
    scanner_length = 20

    red_fixed = ledsettings.get_backlight_color("Red")
    green_fixed = ledsettings.get_backlight_color("Green")
    blue_fixed = ledsettings.get_backlight_color("Blue")
    while menu.screensaver_is_running:
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
                        strip.setPixelColor(i, Color(green, red, blue))
                    else:
                        strip.setPixelColor(i, Color(0, 0, 0))

        if position >= strip.numPixels() or position <= 1:
            direction *= -1
        strip.show()
        time.sleep(wait_ms / 1000.0)

    menu.screensaver_is_running = False
    fastColorWipe(strip, True, ledsettings)


def chords(scale, ledstrip, ledsettings, menu):
    menu.screensaver_is_running = False
    time.sleep(0.2)
    strip = ledstrip.strip
    if menu.screensaver_is_running:
        return
    fastColorWipe(strip, True, ledsettings)
    menu.t = threading.currentThread()
    menu.screensaver_is_running = True
    while menu.screensaver_is_running:
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
            c = get_scale_color(scale, note, ledsettings)
            try:
                leds_to_update.remove(note_position)
            except ValueError:
                pass

            if check_if_led_can_be_overwrite(note_position, ledstrip, ledsettings):
                strip.setPixelColor(note_position,
                                    Color(int(c[1] * brightness), int(c[0] * brightness), int(c[2] * brightness)))

        for i in leds_to_update:
            if check_if_led_can_be_overwrite(i, ledstrip, ledsettings):
                strip.setPixelColor(i, Color(0, 0, 0))

        strip.show()
        time.sleep(0.05)
    menu.screensaver_is_running = False
    fastColorWipe(strip, True, ledsettings)


def calculate_rainbow_colors(ledsettings, note_position, timeshift):
    rainbow_value = int((int(note_position) + ledsettings.rainbow_offset + int(timeshift)) * (
            float(ledsettings.rainbow_scale) / 100)) & 255
    red = get_rainbow_colors(rainbow_value, "red")
    green = get_rainbow_colors(rainbow_value, "green")
    blue = get_rainbow_colors(rainbow_value, "blue")
    return red, green, blue


def calculate_speed_colors(ledsettings):
    speed_colors = ledsettings.speed_get_colors()
    return speed_colors


def calculate_gradient_colors(ledsettings, note_position):
    gradient_colors = ledsettings.gradient_get_colors(note_position)
    return gradient_colors
