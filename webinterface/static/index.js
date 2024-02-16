let scrolldelay;

let animation_timeout_id = '';

let search_song;
let get_songs_timeout;

let beats_per_minute = 160;
let beats_per_measure = 4;
let count = 0;
let is_playing = 0;

let learning_status_timeout = '';
let hand_colorList = '';

let uploadProgress = [];

let advancedMode = false;

let gradients;
let config_settings;
let live_settings;
let current_page = "main";
let rainbow_animation;

const tick1 = new Audio('/static/tick2.mp3');
tick1.volume = 0.2;
const tick2 = new Audio('/static/tick1.mp3');
tick2.volume = 0.2;

function play_tick_sound() {
    if (count >= beats_per_measure) {
        count = 0;
    }
    if (count === 0) {
        tick1.play();
        tick1.currentTime = 0;
    } else {
        tick2.play();
        tick2.currentTime = 0;
    }

    count++;
}

function change_bpm(bpm) {
    beats_per_minute = bpm;
    ticker.interval = 60000 / bpm;
}

function change_volume(value) {
    if (parseInt(value) < -10 || parseInt(value) > 110) {
        return false;
    }
    value = (parseFloat(value) / 100);
    tick1.volume = value;
    tick2.volume = value;
}

function change_beats_per_measure(value) {
    if (parseInt(value) <= 2) {
        return false;
    }
    beats_per_measure = parseInt(value);
}

let ticker = new AdjustingInterval(play_tick_sound, 60000 / beats_per_minute);


function loadAjax(subpage) {
    if (!subpage || subpage === "/") {
        subpage = "home";
    }

    const mainElement = document.getElementById("main");
    mainElement.classList.remove("show");
    setTimeout(() => {
        mainElement.innerHTML = "";
    }, 100);

    const midiPlayerElement = document.getElementById("midi_player");
    if (midiPlayerElement) {
        midiPlayerElement.stop();
    }

    setTimeout(() => {
        const xhttp = new XMLHttpRequest();
        xhttp.timeout = 5000;
        xhttp.onreadystatechange = function () {
            if (this.readyState === 4 && this.status === 200) {
                current_page = subpage;
                mainElement.innerHTML = this.responseText;
                setTimeout(() => {
                    mainElement.classList.add("show");
                }, 100);
                remove_page_indicators();
                document.getElementById(subpage).classList.add("dark:bg-gray-700", "bg-gray-100");
                switch (subpage) {
                    case "home":
                        initialize_homepage();
                        get_homepage_data_loop();
                        get_settings(false);
                        break;
                    case "ledsettings":
                        populate_colormaps(["velocityrainbow_colormap","rainbow_colormap"]);
                        initialize_led_settings();
                        get_current_sequence_setting();
                        clearInterval(homepage_interval);
                        setAdvancedMode(advancedMode);
                        break;
                    case "ledanimations":
                        get_led_idle_animation_settings();
                        clearInterval(homepage_interval);
                        populate_colormaps(["colormap_anim_id"]);
                        break;
                    case "songs":
                        initialize_songs();
                        clearInterval(homepage_interval);
                        break;
                    case "sequences":
                        initialize_sequences();
                        initialize_led_settings();
                        populate_colormaps(["velocityrainbow_colormap","rainbow_colormap"]);
                        clearInterval(homepage_interval);
                        break;
                    case "ports":
                        clearInterval(homepage_interval);
                        initialize_ports_settings();
                        break;
                    case "settings":
                        clearInterval(homepage_interval);
                        break;
                    case "network":
                        clearInterval(homepage_interval);
                        get_wifi_list();
                        break;
                }
            }
            translateStaticContent();
        };
        xhttp.ontimeout = function () {
            mainElement.innerHTML = "REQUEST TIMEOUT";
        };
        xhttp.onerror = function () {
            mainElement.innerHTML = "REQUEST FAILED";
        };
        xhttp.open("GET", `/${subpage}`, true);
        xhttp.send();
    }, 100);
}
loadAjax(window.location.hash.substring(1));



function start_led_animation(name, speed) {
    const xhttp = new XMLHttpRequest();
    xhttp.open("GET", "/api/start_animation?name=" + name + "&speed=" + speed, true);
    xhttp.send();
}

function change_setting(setting_name, value, second_value = false, disable_sequence = false) {
    const xhttp = new XMLHttpRequest();
    try {
        value = value.replaceAll('#', '');
    } catch {
    }
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            response = JSON.parse(this.responseText);
            if (response.reload === true) {
                get_settings();
                get_current_sequence_setting();
            }
            if (response["reload_ports"] === true) {
                get_ports();
            }
            if (response["reload_songs"] === true) {
                get_recording_status();
                get_songs();
            }
            if (response["reload_sequence"] === true) {
                get_current_sequence_setting();
                get_sequences();
            }
            if (response["reload_steps_list"] === true) {
                document.getElementById("sequence_edit_block").classList.add("animate-pulse", "pointer-events-none")
                get_steps_list();
                setTimeout(function () {
                    document.getElementById("sequence_step").dispatchEvent(new Event('change'));
                    document.getElementById("sequence_edit_block").classList.remove("animate-pulse", "pointer-events-none")
                }, 2000);
            }
            if (response["reload_learning_settings"] === true) {
                get_learning_status();
            }

            // called when adding step
            if (response["set_sequence_step_number"]) {
                document.getElementById("sequence_edit_block").classList.add("animate-pulse", "pointer-events-none")
                let step = response["set_sequence_step_number"] - 1;
                setTimeout(function () {
                    let sequenceStepElement = document.getElementById("sequence_step");
                    sequenceStepElement.value = step;
                    sequenceStepElement.dispatchEvent(new Event('change'));
                    document.getElementById("sequence_edit_block").classList.remove("animate-pulse", "pointer-events-none")
                }, 2000);
            }

            multicolor_settings = ["multicolor", "multicolor_range_left", "multicolor_range_right", "remove_multicolor"];
            if (multicolor_settings.includes(setting_name)) {
                get_colormap_gradients();
            }
        }
    }
    xhttp.open("GET", "/api/change_setting?setting_name=" + setting_name + "&value=" + value
        + "&second_value=" + second_value + "&disable_sequence=" + disable_sequence, true);
    xhttp.send();
}



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
            if (this.value === "RGB") {
                document.getElementById('sides_color_choose').hidden = false;
            } else {
                document.getElementById('sides_color_choose').hidden = true;
            }
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

function press_button(element) {
    element.classList.add("pressed");
    setTimeout(function () {
        element.classList.remove("pressed");
    }, 150);
}

function initialize_songs() {
    get_recording_status();
    if (getCookie("sort_by") !== null) {
        document.getElementById("sort_by").value = getCookie("sort_by");
    } else {
        document.getElementById("sort_by").value = "dateAsc";
    }
    get_songs();
    initialize_upload();
    window.addEventListener('resize', function (event) {
        const note_width = document.getElementById('player_and_songs').offsetWidth / 54;
        document.getElementById('myVisualizer').config.whiteNoteWidth = note_width;
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



function AdjustingInterval(workFunc, interval, errorFunc) {
    const that = this;
    let expected, timeout;
    this.interval = interval;

    this.start = function () {
        workFunc();
        expected = Date.now() + this.interval;
        timeout = setTimeout(step, this.interval);
    }

    this.stop = function () {
        clearTimeout(timeout);
    }

    function step() {
        const drift = Date.now() - expected;
        if (drift > that.interval) {
            // You could have some default stuff here too...
            if (errorFunc) errorFunc();
        }
        workFunc();
        expected += that.interval;
        timeout = setTimeout(step, Math.max(0, that.interval - drift));
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

function preventDefaults(e) {
    e.preventDefault()
    e.stopPropagation()
}

function initializeProgress(numFiles) {
    document.getElementById("progress-bar").style.width = "0%";
    uploadProgress = []
    for (let i = numFiles; i > 0; i--) {
        uploadProgress.push(0)
    }
}

function updateProgress(fileNumber, percent) {
    uploadProgress[fileNumber] = percent
    let total = uploadProgress.reduce((tot, curr) => tot + curr, 0) / uploadProgress.length
    document.getElementById("progress-bar").style.width = total + "%";
    if (total >= 100 || total <= 0) {
        document.getElementById("progress-bar-group").classList.add("hidden");
    } else {
        document.getElementById("progress-bar-group").classList.remove("hidden");
    }
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;

    handleFiles(files)
}

function handleFiles(files) {
    document.getElementById("gallery").innerHTML = "";
    files = [...files]
    initializeProgress(files.length)
    files.forEach(uploadFile)
    files.forEach(previewFile)
}

function previewFile(file) {
    let reader = new FileReader()
    reader.readAsDataURL(file)

    reader.onloadend = function () {
        const name = document.createElement('div');
        name.setAttribute("id", file.name);
        name.innerHTML = file.name;
        name.className = "flex";
        document.getElementById('gallery').appendChild(name);
    }
}

function uploadFile(file, i) {
    const url = '/upload';
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    xhr.open('POST', url, true)
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest')

    // Update progress (can be used to show progress indicator)
    xhr.upload.addEventListener("progress", function (e) {
        updateProgress(i, (e.loaded * 100.0 / e.total) || 100)
    })

    xhr.addEventListener('readystatechange', function () {
        if (xhr.readyState === 4 && xhr.status === 200) {
            let response = JSON.parse(this.responseText);

            updateProgress(i, 100);

            if (response.success === true) {
                clearTimeout(get_songs_timeout);
                get_songs_timeout = setTimeout(function () {
                    get_songs();
                }, 2000);
                document.getElementById(response["song_name"]).innerHTML += "<svg xmlns=\"http://www.w3.org/2000/svg\" class=\"h-6 w-6 ml-2 text-green-400\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\">\n" +
                    "  <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M5 13l4 4L19 7\" />\n" +
                    "</svg>";
            } else {
                document.getElementById(response["song_name"]).innerHTML += "<svg xmlns=\"http://www.w3.org/2000/svg\" class=\"h-6 w-6 ml-2 text-red-500\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\">\n" +
                    "  <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M6 18L18 6M6 6l12 12\" />\n" +
                    "</svg>" + "<div class='text-red-400'>" + response.error + "</div>";
            }
        }
    })
    formData.append('file', file)
    xhr.send(formData)
}

function removeOptions(selectElement) {
    let i;
    const L = selectElement.options.length - 1;
    for (i = L; i >= 0; i--) {
        selectElement.remove(i);
    }
}

function remove_color_modes() {
    const slides = document.getElementsByClassName("color_mode");
    for (let i = 0; i < slides.length; i++) {
        slides.item(i).hidden = true;
    }
}

function temporary_show_chords_animation(force_start = false) {
    if(!animation_timeout_id || force_start){
        start_led_animation('chords', '0');
    }
    const stopAnimation = () => {
        start_led_animation('stop', 'normal');
        animation_timeout_id = '';
    };

    // Start or restart the timer whenever this function is called
    if (animation_timeout_id) {
        clearTimeout(animation_timeout_id);
    }

    animation_timeout_id = setTimeout(stopAnimation, 10000); // 10 seconds in milliseconds
}

//"waterfall" visualizer only updates the view when new note is played, this function makes the container scroll slowly
//to simulate smooth animation
function pageScroll() {
    document.getElementsByClassName("waterfall-notes-container")[0].scrollBy(0, -1);
    scrolldelay = setTimeout(pageScroll, 33);
}

function setAdvancedMode(mode) {
    advancedMode = mode;
    const advancedContentElements = document.querySelectorAll('.advanced-content');
    const newDisplayStyle = advancedMode ? 'block' : 'none';

    advancedContentElements.forEach(element => {
        element.style.display = newDisplayStyle;
    });

    // Save the user's choice in a cookie
    const modeValue = advancedMode ? 'advanced' : 'normal';
    setCookie('mode', modeValue, 365)
}

// Function to check the user's saved choice from cookies
function checkSavedMode() {
    const mode = getCookie('mode')
    if (mode) {
        const modeSwitch = document.getElementById('modeSwitch');

        if (mode === 'advanced') {
            modeSwitch.checked = true;
            setAdvancedMode(true);
        }
    }
}

function translate(key) {
    let lang = getLanguage();
    if (translations[lang] && translations[lang][key]) {
        return translations[lang][key];
    }
    // Return the original text if no translation found
    return key;
}

function translateStaticContent(lang) {
    let language = getLanguage();
    const elements = document.querySelectorAll('[data-translate]');
    elements.forEach((element) => {
        const key = element.getAttribute('data-translate');
        if (translations[language] && translations[language][key]) {
            element.textContent = translations[language][key];
        }
    });
}

function getLanguage() {
    let language = getCookie('lang');
    if (!language) {
        const browserLanguage = navigator.language.slice(0, 2);
        // Map supported languages to their respective codes
        const languageMap = {
            'pl': 'pl',
            'en': 'en',
            'de': 'de',
            'fr': 'fr',
            'es': 'es',
            'zh': 'zh',
            'hi': 'hi',
            'pt': 'pt',
            'ja': 'ja',
        };
        // If the browser language is supported, set it; otherwise, set to 'en'
        language = languageMap[browserLanguage] || "en";
    }
    return language;
}
