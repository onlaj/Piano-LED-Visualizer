/**
 * Initialize the homepage and set up refresh functionality
 */
function initialize_homepage() {
    clearInterval(homepage_interval);
    refresh_rate = getCookie("refresh_rate") || 3;
    setCookie("refresh_rate", refresh_rate, 365);
    document.getElementById("refresh_rate").value = refresh_rate;
    if (refresh_rate !== 0) {
        homepage_interval = setInterval(get_homepage_data_loop, refresh_rate * 1000)
    } else {
        setTimeout(get_homepage_data_loop, 1000)
    }
    document.getElementById('refresh_rate').onchange = function () {
        setCookie('refresh_rate', this.value, 365);
        clearInterval(homepage_interval)
        if (this.value !== 0) {
            homepage_interval = setInterval(get_homepage_data_loop, this.value * 1000)
        }
    }
    get_logs();
}

function initialize_led_settings() {
    if (document.getElementById('brightness')) {

        document.getElementById('backlightcolors').addEventListener('change', function (event) {
            change_color_input('backlight_', 'backlight_color', 'backlight_color')
        });

        document.getElementById('sidescolors').addEventListener('change', function (event) {
            change_color_input('sides_', 'sides_color', 'sides_color')
        });

        document.getElementById('brightness').onchange = function () {
            change_setting("brightness", this.value)
        }

        document.getElementById('backlight_brightness').onchange = function () {
            change_setting("backlight_brightness", this.value)
        }

        document.getElementById('skipped_notes').onchange = function () {
            change_setting("skipped_notes", this.value)
        }

        document.getElementById('led_count').onchange = function () {
            change_setting("led_count", this.value)
        }

        document.getElementById('leds_per_meter').onchange = function () {
            change_setting("leds_per_meter", this.value)
        }

        document.getElementById('shift').onchange = function () {
            change_setting("shift", this.value)
        }

        document.getElementById('reverse').onchange = function () {
            change_setting("reverse", this.value)
        }

        document.getElementById('sides_color_mode').onchange = function () {
            change_setting("sides_color_mode", this.value)
            document.getElementById('sides_color_choose').hidden = this.value !== "RGB";
        }
    }

    document.getElementById('fading_speed').onchange = function () {
        let value = this.value || "10";
        change_setting("fading_speed", value, false, true)
    }

    document.getElementById('velocity_speed').onchange = function () {
        let value = this.value || "8";
        change_setting("velocity_speed", value, false, true)
    }

    document.getElementById('light_mode').onchange = function () {
        if (this.value === "Fading") {
            document.getElementById('fading').hidden = false;
            document.getElementById('fading_speed').onchange();
        } else {
            document.getElementById('fading').hidden = true;
        }
        if (this.value === "Velocity" || this.value === "Pedal") {
            document.getElementById('velocity').hidden = false;
            document.getElementById('velocity_speed').onchange();
        } else {
            document.getElementById('velocity').hidden = true;
        }
        change_setting("light_mode", this.value, false, true)
    }

    document.getElementById('ledcolors').addEventListener('change', function (event) {
        change_color_input('', 'led_color', 'led_color')
    });

    document.getElementById('speedslowcolors').addEventListener('change', function (event) {
        change_color_input('speed_slowest_', 'speed_slow_color', 'speed_slowest_color')
    });

    document.getElementById('speedfastcolors').addEventListener('change', function (event) {
        change_color_input('speed_fastest_', 'speed_fast_color', 'speed_fastest_color')
    });

    document.getElementById('gradientstartcolors').addEventListener('change', function (event) {
        change_color_input('gradient_start_', 'gradient_start_color', 'gradient_start_color')
    });

    document.getElementById('gradientendcolors').addEventListener('change', function (event) {
        change_color_input('gradient_end_', 'gradient_end_color', 'gradient_end_color')
    });

    document.getElementById('keyinscalecolors').addEventListener('change', function (event) {
        change_color_input('key_in_scale_', 'key_in_scale_color', 'key_in_scale_color')
    });

    document.getElementById('keynotinscalecolors').addEventListener('change', function (event) {
        change_color_input('key_not_in_scale_', 'key_not_in_scale_color', 'key_not_in_scale_color')
    });

    document.getElementById('rainbow_offset').onchange = function () {
        change_setting("rainbow_offset", this.value, false, true)
    }

    document.getElementById('rainbow_scale').onchange = function () {
        change_setting("rainbow_scale", this.value, false, true)
    }

    document.getElementById('rainbow_timeshift').onchange = function () {
        change_setting("rainbow_timeshift", this.value, false, true)
    }

    document.getElementById('rainbow_colormap').onchange = function () {
        change_setting("rainbow_colormap", this.value, false, true)
    }

    document.getElementById('velocityrainbow_offset').onchange = function () {
        change_setting("velocityrainbow_offset", this.value, false, true)
    }

    document.getElementById('velocityrainbow_scale').onchange = function () {
        change_setting("velocityrainbow_scale", this.value, false, true)
    }

    document.getElementById('velocityrainbow_curve').onchange = function () {
        change_setting("velocityrainbow_curve", this.value, false, true)
    }

    document.getElementById('velocityrainbow_colormap').onchange = function () {
        change_setting("velocityrainbow_colormap", this.value, false, true)
    }

    document.getElementById('color_mode').onchange = function () {
        switch (this.value) {
            case "Single":
                remove_color_modes();
                document.getElementById('Single').hidden = false;
                change_setting("color_mode", "Single", false, true);
                document.getElementById("led_color").dispatchEvent(new Event('input'));
                break;
            case "Multicolor":
                remove_color_modes();
                document.getElementById('Multicolor').hidden = false;
                change_setting("color_mode", "Multicolor", false, true);
                break;
            case "Rainbow":
                remove_color_modes();
                document.getElementById('Rainbow').hidden = false;
                change_setting("color_mode", "Rainbow", false, true);
                break;
            case "VelocityRainbow":
                remove_color_modes();
                document.getElementById('VelocityRainbow').hidden = false;
                change_setting("color_mode", "VelocityRainbow", false, true);
                break;
            case "Speed":
                remove_color_modes();
                document.getElementById('Speed').hidden = false;
                change_setting("color_mode", "Speed", false, true);
                document.getElementById("speed_slow_color").dispatchEvent(new Event('input'));
                document.getElementById("speed_fast_color").dispatchEvent(new Event('input'));
                break;
            case "Gradient":
                remove_color_modes();
                document.getElementById('Gradient').hidden = false;
                change_setting("color_mode", "Gradient", false, true);
                document.getElementById("gradient_start_color").dispatchEvent(new Event('input'));
                document.getElementById("gradient_end_color").dispatchEvent(new Event('input'));
                break;
            case "Scale":
                remove_color_modes();
                document.getElementById('Scale').hidden = false;
                change_setting("color_mode", "Scale", false, true);
                document.getElementById("key_in_scale_color").dispatchEvent(new Event('input'));
                document.getElementById("key_not_in_scale_color").dispatchEvent(new Event('input'));
                break;
            default:

        }
    }
    get_settings();
}

function initialize_songs() {
    get_recording_status();
    if (getCookie("sort_by") !== null) {
        document.getElementById("sort_by").value = getCookie("sort_by");
    } else {
        document.getElementById("sort_by").value = "dateAsc";
    }
    // Restore current profile ASAP to avoid races when loading highscores
    try {
        if (!window.currentProfileId && typeof getCookie === 'function') {
            const cid = getCookie('currentProfileId');
            if (cid) {
                window.currentProfileId = parseInt(cid);
                // Non-blocking sync to backend
                try { fetch('/api/set_current_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: window.currentProfileId})}); } catch(e) {}
            }
        }
    } catch (e) {}
    // Initialize profiles UI (defined in profiles.js) before fetching songs
    if (typeof window.initProfilesOnSongsPage === 'function') {
        window.initProfilesOnSongsPage();
    }
    // Now load songs (highscores fetch will use the restored profile id)
    get_songs();
    initialize_upload();
    window.addEventListener('resize', function (event) {
        document.getElementById('myVisualizer').config.whiteNoteWidth = document.getElementById('player_and_songs').offsetWidth / 54;
    }, true);

    if (is_playing) {
        document.getElementById("metronome_start").classList.add("hidden");
        document.getElementById("metronome_stop").classList.remove("hidden");
    } else {
        document.getElementById("metronome_start").classList.remove("hidden");
        document.getElementById("metronome_stop").classList.add("hidden");
    }
    document.getElementById("beats_per_minute").innerHTML = beats_per_minute;
    document.getElementById("bpm_slider").value = beats_per_minute;

    document.getElementById("beats_per_measure").value = beats_per_measure;
}


function initialize_sequences() {
    clearInterval(homepage_interval);
    document.getElementById('next_step_button').addEventListener("mousedown", function (e) {
        press_button(document.getElementById('next_step_button'));
    });

    window.addEventListener('keydown', function (e) {
        if (e.keyCode === 32 && e.target === document.body) {
            change_setting('next_step', '0');
            press_button(document.getElementById('next_step_button'));
            e.preventDefault();
        }
    });
    get_sequences();
    get_current_sequence_setting();
}

function initialize_ports_settings() {
    get_ports()
    document.getElementById('switch_ports').onclick = function () {
        document.getElementById('switch_ports').disabled = true;
        document.getElementById('switch_ports_sidebar').disabled = true;
        switch_ports()
    }
    document.getElementById('active_input').onchange = function () {
        change_setting("input_port", this.value)
    }
    document.getElementById('secondary_input').onchange = function () {
        change_setting("secondary_input_port", this.value)
    }
    document.getElementById('playback_input').onchange = function () {
        change_setting("play_port", this.value)
    }
}


function initialize_upload() {

// Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        document.getElementById("drop-area").addEventListener(eventName, preventDefaults, false)
        document.body.addEventListener(eventName, preventDefaults, false)
    })
    document.getElementById("drop-area").addEventListener('drop', handleDrop, false)
}