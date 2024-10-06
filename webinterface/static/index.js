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
                        getCurrentLocalAddress();
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


function press_button(element) {
    element.classList.add("pressed");
    setTimeout(function () {
        element.classList.remove("pressed");
    }, 150);
}



function preventDefaults(e) {
    e.preventDefault()
    e.stopPropagation()
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
