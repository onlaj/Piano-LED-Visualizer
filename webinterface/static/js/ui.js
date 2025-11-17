get_colormap_gradients();

function remove_page_indicators() {
    document.getElementById("home").classList.remove("glass-light");
    document.getElementById("ledsettings").classList.remove("glass-light");
    document.getElementById("songs").classList.remove("glass-light");
    document.getElementById("sequences").classList.remove("glass-light");
    document.getElementById("ports").classList.remove("glass-light");
    document.getElementById("ledanimations").classList.remove("glass-light");
    document.getElementById("network").classList.remove("glass-light");
}

function get_homepage_data_loop() {
    const xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            let refresh_rate = getCookie("refresh_rate");
            if (refresh_rate === 0) {
                refresh_rate = 1
            }
            const response_pc_stats = JSON.parse(this.responseText);

            let download = (response_pc_stats.download - download_start) / refresh_rate;
            let upload = (response_pc_stats.upload - upload_start) / refresh_rate;
            if (download_start === 0) {
                download = 0;
                upload = 0;
            }
            animateValue(document.getElementById("cpu_number"), last_cpu_usage,
                response_pc_stats["cpu_usage"], refresh_rate * 500, false);
            document.getElementById("memory_usage_percent").innerHTML = response_pc_stats["memory_usage_percent"] + "%";
            document.getElementById("memory_usage").innerHTML =

                formatBytes(response_pc_stats["memory_usage_used"], 2, false) + "/" +
                formatBytes(response_pc_stats["memory_usage_total"]);
            document.getElementById("cpu_temp").innerHTML = response_pc_stats["cpu_temp"];

            document.getElementById("card_usage").innerHTML =
                formatBytes(response_pc_stats["card_space_used"], 2, false) + "/" +
                formatBytes(response_pc_stats["card_space_total"]);
            document.getElementById("card_usage_percent").innerHTML = response_pc_stats["card_space_percent"] + "%";
            animateValue(document.getElementById("download_number"), last_download, download, refresh_rate * 500, true);
            animateValue(document.getElementById("upload_number"), last_upload, upload, refresh_rate * 500, true);

            document.getElementById("cover_state").innerHTML = response_pc_stats["cover_state"];

            document.getElementById("led_fps").innerHTML = response_pc_stats.led_fps;
            if (document.getElementById("system_state")) {
                document.getElementById("system_state").innerHTML = response_pc_stats.system_state || 'UNKNOWN';
            }
            document.getElementById("cpu_count").innerHTML = response_pc_stats.cpu_count;
            document.getElementById("cpu_pid").innerHTML = response_pc_stats.cpu_pid;
            document.getElementById("cpu_freq").innerHTML = response_pc_stats.cpu_freq;
            document.getElementById("memory_pid").innerHTML =
                formatBytes(response_pc_stats.memory_pid, 2, false);

            document.getElementById("cover_state").innerHTML = response_pc_stats.cover_state;

            // change value of select based on response_pc_stats.screen_on
            document.getElementById("screen_on").value = response_pc_stats.screen_on;

            // change value of select based on response_pc_stats.display_type
            if (response_pc_stats.display_type) {
                const displayTypeSelect = document.getElementById("display_type");
                if (displayTypeSelect) {
                    displayTypeSelect.value = response_pc_stats.display_type;
                    // Store current value for confirmation handler
                    displayTypeSelect.setAttribute('data-current-value', response_pc_stats.display_type);
                }
            }

            // change value of select based on response_pc_stats.led_pin
            if (response_pc_stats.led_pin) {
                const ledPinSelect = document.getElementById("led_pin");
                if (ledPinSelect) {
                    ledPinSelect.value = response_pc_stats.led_pin;
                    // Store current value for confirmation handler
                    ledPinSelect.setAttribute('data-current-value', response_pc_stats.led_pin);
                }
            }

            document.getElementById("cover_state").innerHTML = response_pc_stats.cover_state;


            download_start = response_pc_stats.download;
            upload_start = response_pc_stats.upload;

            last_cpu_usage = response_pc_stats["cpu_usage"];
            last_download = download;
            last_upload = upload;

            checkSavedMode();
        }
    };
    xhttp.open("GET", "/api/get_homepage_data", true);
    xhttp.send();
}
function get_colormap_gradients() {
    const xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            gradients = JSON.parse(this.responseText);
        }
    };
    xhttp.open("GET", "/api/get_colormap_gradients", true);
    xhttp.send();
}

function populate_colormaps(select_ids) {
    if (!gradients)
        return;

    for (const id of select_ids) {
        const select = document.getElementById(id);
        var options = [];
        for (const key in gradients)
            options.push(new Option(key, key));
        const value = select.value;
        select.replaceChildren(...options);
        select.value = value;
    }
}

function switch_ports() {
    const xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            get_ports()
            if (document.getElementById('switch_ports') != null) {
                document.getElementById('switch_ports').disabled = false;
            }
            document.getElementById('switch_ports_sidebar').disabled = false;
        }
    };
    xhttp.open("GET", "/api/switch_ports", true);
    xhttp.send();
}

function disable_wifi_refresh_button() {
    if (document.getElementById('refresh-wifi-button') != null) {
        document.getElementById('refresh-wifi-button').disabled = true;
        document.getElementById('refresh-wifi-button').classList.add("pointer-events-none", "animate-spin");
    }
    if (document.getElementById('wifi-list') != null) {
        document.getElementById('wifi-list').disabled = true;
        document.getElementById('wifi-list').classList.add("pointer-events-none", "opacity-50", "animate-pulse");
    }
}

function enable_wifi_refresh_button() {
    if (document.getElementById('refresh-wifi-button') != null) {
        document.getElementById('refresh-wifi-button').disabled = false;
        document.getElementById('refresh-wifi-button').classList.remove("pointer-events-none", "animate-spin");
    }
    if (document.getElementById('wifi-list') != null) {
        document.getElementById('wifi-list').disabled = false;
        document.getElementById('wifi-list').classList.remove("pointer-events-none", "opacity-50", "animate-pulse");
    }
}


function get_wifi_list() {
    disable_wifi_refresh_button();
    const xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        let response;
        if (this.readyState === 4 && this.status === 200) {
            response = JSON.parse(this.responseText);
            update_wifi_list(response);
        }
    };
    xhttp.open("GET", "/api/get_wifi_list", true);
    xhttp.send();
}


function update_wifi_list(response) {
    const wifiListElement = document.getElementById("wifi-list");
    wifiListElement.innerHTML = '';


    let wifi_list = response["wifi_list"]
    let connected_wifi = response["connected_wifi"]
    let connected_wifi_address = response["connected_wifi_address"]

    document.getElementById("connected-wifi").innerHTML = connected_wifi;
    document.getElementById("connected_wifi_address").innerHTML = "BSSID: " + connected_wifi_address;

    // Loop through wifi_list
    wifi_list.forEach(wifi => {
        const listItem = document.createElement("div");
        listItem.className = "glass-light mb-4 p-2 rounded-glass transition-smooth-fast";

        const partial_icon = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" ' +
            'stroke-width="1.5" stroke="currentColor" class="w-6 h-6 absolute">' + getWifiIcon(wifi["Signal Strength"]) + '</svg>';

        const full_wifi_icon = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" ' +
            'stroke-width="1.5" stroke="currentColor" class="w-6 h-6 opacity-30">' +
            '<path d="M8.288 15.038a5.25 5.25 0 017.424 0M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0M1.924 ' +
            '8.674c5.565-5.565 14.587-5.565 20.152 0M12.53 18.22l-.53.53-.53-.53a.75.75 0 011.06 0z" /></svg>'

        const wifi_icon = "<div class='relative inline-block'>" + partial_icon + full_wifi_icon + "</div>";

        listItem.innerHTML =
            `<div class="rounded-md flex items-center justify-between">
                ${wifi_icon}
                <div class="block">
                    <div class="ml-4 truncate w-40">${wifi["ESSID"]}</div>
                    <div class="ml-4 text-xs text-center opacity-50">${wifi["Address"]}</div>
                </div>
                <button onclick="this.classList.add('hidden');                            
                            document.getElementById('wifi_${wifi["ESSID"]}').classList.remove('hidden');
                            document.getElementById('wifi_password_${wifi["ESSID"]}').focus()"
                    class="w-20 outline-none bg-blue-500 dark:bg-blue-500 py-2 font-bold rounded-glass transition-smooth-fast" data-translate="connect">
                    ${translate("connect")}
                </button>            
            
            </div>
            <div id="wifi_${wifi["ESSID"]}" class="hidden ">
                <div class="relative">
                    <input id="wifi_password_${wifi["ESSID"]}" class="mt-4 h-10 block a w-full dark:text-black glass-light py-2 px-2 rounded-glass leading-tight transition-smooth-fast" type="password" placeholder="Type Wi-Fi password here">
                    <button class="absolute top-1/4 right-2" onclick="togglePasswordVisibility(this, 'wifi_password_${wifi["ESSID"]}');">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6" id="toggle-eye-${wifi["ESSID"]}">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                        </svg>
                    </button>
                </div>
                <div class="text-xs text-red-400">
                <div data-translate="incorrect_password">${translate("incorrect_password")}</div>
                <br>
                <div data-translate="if_the_hotspot">${translate("if_the_hotspot")}</div>
                </div>
                <button onclick="change_setting('connect_to_wifi', '${wifi["ESSID"]}', document.getElementById('wifi_password_${wifi["ESSID"]}').value);
                    temporary_disable_button(this, 5000);"
                    class="m-auto flex mt-2 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-md">
                <span class="w-20" data-translate="connect">${translate("connect")}</span></button>
            </div>
            `;

        wifiListElement.appendChild(listItem);
        if (connected_wifi !== "No Wi-Fi interface found." && connected_wifi !== "Running as hotspot") {
            document.getElementById("disconnect-button").classList.remove("hidden");
            document.getElementById("connected_wifi_address").classList.remove("hidden");
        }

    });
    enable_wifi_refresh_button();
}

function togglePasswordVisibility(button, inputId) {
    const passwordInput = document.getElementById(inputId);
    const eyeIcon = button.querySelector('svg:not(.hidden)'); // Get the currently visible icon
    const eyeSlashIcon = button.querySelector('svg.hidden'); // Get the currently hidden icon

    if (passwordInput.type === "password") {
        passwordInput.type = "text";
        eyeIcon.classList.add("hidden");
        eyeSlashIcon.classList.remove("hidden");
        button.setAttribute('aria-label', translate('hide_password'));
        // Update the button text if it's not an icon-only button
        if (button.textContent.trim() === translate('show_password')) {
            button.innerHTML = button.innerHTML.replace(translate('show_password'), translate('hide_password'));
        }
    } else {
        passwordInput.type = "password";
        eyeIcon.classList.add("hidden");
        eyeSlashIcon.classList.remove("hidden");
        button.setAttribute('aria-label', translate('show_password'));
        // Update the button text if it's not an icon-only button
        if (button.textContent.trim() === translate('hide_password')) {
            button.innerHTML = button.innerHTML.replace(translate('hide_password'), translate('show_password'));
        }
    }
}

function updatePasswordStrength(inputId, strengthBarId, strengthTextId) {
    const password = document.getElementById(inputId).value;
    const strengthBar = document.getElementById(strengthBarId);
    const strengthText = document.getElementById(strengthTextId);

    let score = 0;
    if (!password) {
        strengthBar.style.width = "0%";
        strengthText.textContent = "";
        return;
    }

    // Award every unique letter either uppercase or lowercase
    let letters = {};
    for (let i = 0; i < password.length; i++) {
        letters[password[i]] = (letters[password[i]] || 0) + 1;
        score += 5.0 / letters[password[i]];
    }

    // Bonus points for mixing it up
    let variations = {
        digits: /\d/.test(password),
        lower: /[a-z]/.test(password),
        upper: /[A-Z]/.test(password),
        nonWords: /\W/.test(password), // Special characters
    };

    let variationCount = 0;
    for (let check in variations) {
        variationCount += (variations[check] === true) ? 1 : 0;
    }
    score += (variationCount - 1) * 10;

    let strength = "";
    let color = "#EF4444"; // Default to weak (red)
    let percentage = Math.min(Math.max(score, 0), 100); // Cap score between 0 and 100

    if (score < 30) {
        strength = translate("password_strength_weak");
        color = "#EF4444"; // Red
    } else if (score < 60) {
        strength = translate("password_strength_medium");
        color = "#F59E0B"; // Amber
    } else if (score < 85) {
        strength = translate("password_strength_strong");
        color = "#10B981"; // Green
    } else {
        strength = translate("password_strength_very_strong");
        color = "#059669"; // Darker Green for very strong
    }

    strengthBar.style.width = percentage + "%";
    strengthBar.style.backgroundColor = color;
    strengthText.textContent = strength;
    if (password.length < 8 && password.length > 0) {
        strengthText.textContent = translate("password_too_short_strength");
        strengthBar.style.backgroundColor = "#EF4444"; // Red
        strengthBar.style.width = Math.min(percentage, 25) + "%"; // Keep bar small for too short
    } else if (password.length === 0) {
         strengthText.textContent = "";
    }
}

function getWifiIcon(signalStrength) {
    // Map the signal strength percentage to icons
    if (signalStrength >= 75) {
        return '<path d="M8.288 15.038a5.25 5.25 0 017.424 0M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0M1.924 8.674c5.565-5.565 14.587-5.565 20.152 0M12.53 18.22l-.53.53-.53-.53a.75.75 0 011.06 0z" />';
    } else if (signalStrength >= 50) {
        return '<path d="M8.288 15.038a5.25 5.25 0 017.424 0M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0M12.53 18.22l-.53.53-.53-.53a.75.75 0 011.06 0z" />';
    } else if (signalStrength >= 25) {
        return '<path d="M8.288 15.038a5.25 5.25 0 017.424 0M12.53 18.22l-.53.53-.53-.53a.75.75 0 011.06 0z" />';
    } else if (signalStrength >= 0) {
        return '<path d="M12.53 18.22l-.53.53-.53-.53a.75.75 0 011.06 0z" />';
    } else {
        return ''; // Empty string for no icon
    }
}

function getCurrentLocalAddress() {
    const xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            const response = JSON.parse(this.responseText);
            document.getElementById("current-local-address").innerText = response.local_address;
        }
    };
    xhttp.open("GET", "/api/get_local_address", true);
    xhttp.send();
}

function changeLocalAddress() {
    const newAddress = document.getElementById("new-local-address").value;
    if (!newAddress) {
        showAddressChangeMessage("Please enter a new address", "text-red-500");
        return;
    }

    const xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4) {
            const response = JSON.parse(this.responseText);
            if (this.status === 200 && response.success) {
                showAddressChangeMessage(`Address changed to ${response.new_address}. Please reconnect using the new address.`, "text-green-500");
                document.getElementById("current-local-address").innerText = response.new_address;
            } else {
                showAddressChangeMessage(response.error || "Failed to change address", "text-red-500");
            }
        }
    };
    xhttp.open("POST", "/api/change_local_address", true);
    xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
    xhttp.send(JSON.stringify({ new_name: newAddress }));
}

function showAddressChangeMessage(message, className) {
    const messageDiv = document.getElementById('address-change-message');
    messageDiv.textContent = message;
    messageDiv.className = 'text-sm text-center ' + className;
    setTimeout(() => {
        messageDiv.className = 'text-sm text-center hidden';
    }, 5000);
}

function changeHotspotPassword() {
    const newPassword = document.getElementById('hotspot-password').value;
    const messageDiv = document.getElementById('hotspot-password-message');

    if (newPassword.length < 8) {
        messageDiv.textContent = translate('password_too_short');
        messageDiv.className = 'text-sm text-center text-red-500';
         setTimeout(() => {
            messageDiv.className = 'text-sm text-center hidden';
        }, 3000);
        return;
    }

    messageDiv.textContent = translate('changing_hotspot_password_message');
    messageDiv.className = 'text-sm text-center text-blue-500';

    fetch(`/api/change_setting?setting_name=hotspot_password&value=${encodeURIComponent(newPassword)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                messageDiv.textContent = translate('hotspot_password_changed_success');
                messageDiv.className = 'text-sm text-center text-green-500';
                document.getElementById('hotspot-password').value = ''; // Clear input
            } else {
                messageDiv.textContent = translate('hotspot_password_changed_fail') + (data.error ? ": " + data.error : "");
                messageDiv.className = 'text-sm text-center text-red-500';
            }
            setTimeout(() => {
                messageDiv.className = 'text-sm text-center hidden';
            }, 5000);
        })
        .catch(error => {
            console.error('Error changing hotspot password:', error);
            messageDiv.textContent = translate('hotspot_password_changed_fail_error');
            messageDiv.className = 'text-sm text-center text-red-500';
            setTimeout(() => {
                messageDiv.className = 'text-sm text-center hidden';
            }, 5000);
        });
}

function get_settings(home = true) {
    const xhttp = new XMLHttpRequest();
    xhttp.timeout = 5000;
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            let response = JSON.parse(this.responseText);
            config_settings = response;

            if (home) {

                if (document.getElementById("backlight_color")) {
                    document.getElementById("backlight_color").value = response["backlight_color"];
                    document.getElementById("sides_color").value = response["sides_color"];
                    document.getElementById("sides_color_mode").value = response["sides_color_mode"];

                    if (response["sides_color_mode"] !== "RGB") {
                        document.getElementById('sides_color_choose').hidden = true;
                    }

                    document.getElementById("brightness").value = response["brightness"];
                    document.getElementById("brightness_percent").value = response["brightness"] + "%";
                    document.getElementById("gamma_correction").value = response["led_gamma"];
                    document.getElementById("backlight_brightness").value = response["backlight_brightness"];
                    document.getElementById("backlight_brightness_percent").value = response["backlight_brightness"] + "%";
                    if (response["disable_backlight_on_idle"] === "1") {
                        document.getElementById("disable_backlight").checked = true;
                    }
                    document.getElementById("skipped_notes").value = response["skipped_notes"];
                    document.getElementById("led_count").value = response["led_count"];
                    document.getElementById("leds_per_meter").value = response["leds_per_meter"];
                    document.getElementById("shift").value = response["led_shift"];
                    document.getElementById("reverse").value = response["led_reverse"];
                    document.getElementById("sides_color").dispatchEvent(new Event('input'));
                    document.getElementById("backlight_color").dispatchEvent(new Event('input'));
                }

                document.getElementById("light_mode").value = response["light_mode"];
                if (response["light_mode"] === "Fading") {
                    document.getElementById('fading').hidden = false;
                    document.getElementById('fading_speed').value = response["fading_speed"];
                }
                if (response.light_mode === "Velocity") {
                    document.getElementById('velocity').hidden = false;
                    document.getElementById('velocity_speed').value = response.fading_speed;
                }
                if (response.light_mode === "Pedal") {
                    document.getElementById('velocity').hidden = false;
                    document.getElementById('velocity_speed').value = response.fading_speed;
                }

                document.getElementById("led_color").value = response["led_color"];

                document.getElementById("color_mode").value = response["color_mode"];

                show_multicolors(response["multicolor"], response["multicolor_range"], response["multicolor_iteration"]);

                show_note_offsets(response["note_offsets"]);

                document.getElementById("rainbow_offset").value = response["rainbow_offset"];
                document.getElementById("rainbow_scale").value = response["rainbow_scale"];
                document.getElementById("rainbow_timeshift").value = response.rainbow_timeshift;
                document.getElementById("rainbow_colormap").value = response.rainbow_colormap;

                document.getElementById("velocityrainbow_offset").value = response["velocityrainbow_offset"];
                document.getElementById("velocityrainbow_scale").value = response["velocityrainbow_scale"];
                document.getElementById("velocityrainbow_curve").value = response["velocityrainbow_curve"];
                document.getElementById("velocityrainbow_colormap").value = response["velocityrainbow_colormap"];

                document.getElementById("speed_slow_color").value = response["speed_slowest_color"];
                document.getElementById("speed_fast_color").value = response["speed_fastest_color"];

                document.getElementById("speed_max_notes").value = response["speed_max_notes"];
                document.getElementById("speed_period_in_seconds").value = response["speed_period_in_seconds"];

                document.getElementById("gradient_start_color").value = response["gradient_start_color"];
                document.getElementById("gradient_end_color").value = response["gradient_end_color"];

                document.getElementById("key_in_scale_color").value = response["key_in_scale_color"];
                document.getElementById("key_not_in_scale_color").value = response["key_not_in_scale_color"];

                document.getElementById("scale_key").value = response["scale_key"];

                document.getElementById('color_mode').onchange();
            } else {
                document.getElementById("color_mode").innerHTML = response["color_mode"];
                document.getElementById("light_mode").innerHTML = response["light_mode"];
                document.getElementById("brightness_percent").innerHTML = response["brightness"] + "%";
                document.getElementById("backlight_brightness_percent").innerHTML = response["backlight_brightness"] + "%";
                document.getElementById("input_port").innerHTML = response["input_port"];
                document.getElementById("playback_port").innerHTML = response["play_port"];
            }

        }
    };
    xhttp.open("GET", "/api/get_settings", true);
    xhttp.send();
}


function get_led_idle_animation_settings(){
    const xhttp = new XMLHttpRequest();
    xhttp.timeout = 5000;
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            let response = JSON.parse(this.responseText);
            document.getElementById("animation_delay").value = response["led_animation_delay"];
            document.getElementById("led_animation").value = response["led_animation"];
            document.getElementById("brightness_percent").value = response["led_animation_brightness_percent"];
            document.getElementById("brightness").value = response["led_animation_brightness_percent"];
            if (document.getElementById("idle_timeout_minutes")) {
                document.getElementById("idle_timeout_minutes").value = response["idle_timeout_minutes"];
            }
            if (document.getElementById("screensaver_delay")) {
                document.getElementById("screensaver_delay").value = response["screensaver_delay"];
            }
            if (document.getElementById("screen_off_delay")) {
                document.getElementById("screen_off_delay").value = response["screen_off_delay"];
            }
        }
    }
    xhttp.open("GET", "/api/get_idle_animation_settings", true);
    xhttp.send();
}

function get_current_sequence_setting(home = true, is_loading_step = false) {
    let is_editing_sequence = "false"
    const xhttp = new XMLHttpRequest();
    xhttp.timeout = 5000;
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            let response = JSON.parse(this.responseText);
            live_settings = response;

            if (document.getElementById('sequence_edit')) {
                is_editing_sequence = document.getElementById('sequence_edit').getAttribute("active");
            } else {
                is_editing_sequence = "false";
            }

            if (document.getElementById("current_color_mode")) {
                document.getElementById("current_color_mode").innerHTML = response["color_mode"]
                document.getElementById("current_light_mode").innerHTML = response["light_mode"]
            }

            if (is_editing_sequence === "true") {
                document.getElementById('fading').hidden = true;
                document.getElementById('velocity').hidden = true;
                document.getElementById("light_mode").value = response["light_mode"];
                if (response["light_mode"] === "Fading") {
                    document.getElementById('fading').hidden = false;
                    document.getElementById('fading_speed').value = response["fading_speed"];
                }
                if (response["light_mode"] === "Velocity" || response["light_mode"] === "Pedal") {
                    document.getElementById('velocity').hidden = false;
                    document.getElementById('fading_speed').value = response["fading_speed"];
                }
                document.getElementById("color_mode").value = response["color_mode"];
                change_setting("color_mode", response["color_mode"], "no_reload", true);
                change_setting("light_mode", response["light_mode"], false, true);
            }

            if (response["color_mode"] === "Single") {
                document.getElementById("current_led_color").innerHTML = '<svg width="100%" height="45px">' +
                    '<defs>\n' +
                    '   <linearGradient id="gradient_single" x1=".5" y1="1" x2=".5">\n' +
                    '       <stop stop-color="' + response["led_color"] + '" stop-opacity="0"/>\n' +
                    '       <stop offset=".61" stop-color="' + response["led_color"] + '" stop-opacity=".65"/>\n' +
                    '       <stop offset="1" stop-color="' + response["led_color"] + '"/>\n' +
                    '   </linearGradient>\n' +
                    '</defs>' +
                    '<rect width="100%" height="45px" fill="url(#gradient_single)" /></svg>'
                document.getElementById("current_led_color").innerHTML += '<img class="w-full opacity-50" ' +
                    'style="height: 40px;width:100%;margin-top:-40px" src="../static/piano.svg">';

                if (is_editing_sequence === "true") {
                    remove_color_modes();
                    document.getElementById("led_color").value = response["led_color"];
                    document.getElementById('Single').hidden = false;
                    document.getElementById("led_color").dispatchEvent(new Event('input'));

                    change_setting("led_color", response["led_color"], "no_reload", true);
                }

            }
            if (response["color_mode"] === "Multicolor") {

                document.getElementById("current_led_color").innerHTML = '';
                const new_multicolor = {};
                response["multicolor"].forEach(function (item, index) {
                    const multicolor_hex = rgbToHex(item[0], item[1], item[2]);

                    let length = (response.multicolor_range[index][1] - 20) - (response.multicolor_range[index][0] - 20);
                    length = (length / 88) * 100
                    let left_spacing = ((response.multicolor_range[index][0] - 20) / 88) * 100;

                    left_spacing = Math.min(Math.max(parseInt(left_spacing), 0), 88);

                    document.getElementById("current_led_color").innerHTML += '<svg class="mb-2" ' +
                        'style="filter: drop-shadow(0px 5px 15px ' + multicolor_hex + ');margin-left:' + left_spacing + '%" width="100%" height="10px">' +
                        '<rect width="' + length + '%" height="20" fill="' + multicolor_hex + '" /></svg>';

                    if (is_editing_sequence === "true" && is_loading_step === true) {
                        new_multicolor[index] = {};
                        new_multicolor[index]["color"] = multicolor_hex;
                        new_multicolor[index]["range"] = response.multicolor_range[index];
                    }

                });
                document.getElementById("current_led_color").innerHTML += '<img class="w-full opacity-100" ' +
                    'style="height: 40px;width:100%;" src="../static/piano.svg">';

                if (is_editing_sequence === "true" && is_loading_step === true) {
                    remove_color_modes();
                    document.getElementById('Multicolor').hidden = false;
                    show_multicolors(response["multicolor"], response["multicolor_range"], response["multicolor_iteration"]);
                    change_setting("add_multicolor_and_set_value", JSON.stringify(new_multicolor), "", "");
                }


            }
            if (response["color_mode"] === "Gradient") {
                const is_reversed = config_settings["led_reverse"] === "1";
                const start_color = is_reversed ? response["gradient_end_color"] : response["gradient_start_color"];
                const end_color = is_reversed ? response["gradient_start_color"] : response["gradient_end_color"];

                document.getElementById("current_led_color").innerHTML = '<svg ' +
                    'width="100%" height="45px">\n' +
                    '      <defs>\n' +
                    '        <linearGradient id="g1">\n' +
                    '          <stop offset="5%" stop-color="' + start_color + '" />\n' +
                    '          <stop offset="95%" stop-color="' + end_color + '" />\n' +
                    '        </linearGradient>\n' +
                    '       <linearGradient id="g2" x1=".5" x2=".5" y2="1">\n' +
                    '           <stop stop-color="#000" stop-opacity="0"/>\n' +
                    '           <stop offset=".59" stop-color="#000" stop-opacity=".34217436974789917"/>\n' +
                    '           <stop offset="1" stop-color="#000"/>\n' +
                    '       </linearGradient>' +
                    '      </defs>\n' +
                    '      <rect width="100%" height="45px" fill=\'url(#g1)\'/>' +
                    '      <rect width="100%" height="45px" fill=\'url(#g2)\'/>\n' +
                    '    </svg>'
                document.getElementById("current_led_color").innerHTML += '<img class="w-full opacity-50" ' +
                    'style="height: 40px;width:100%;margin-top:-40px" src="../static/piano.svg">';

                if (is_editing_sequence === "true") {
                    remove_color_modes();
                    document.getElementById('Gradient').hidden = false;
                    document.getElementById("gradient_start_color").value = response["gradient_start_color"];
                    document.getElementById("gradient_end_color").value = response["gradient_end_color"];

                    document.getElementById("gradient_start_color").dispatchEvent(new Event('input'));
                    document.getElementById("gradient_end_color").dispatchEvent(new Event('input'));

                    change_setting("gradient_start_color", response["gradient_start_color"], "no_reload", true);
                    change_setting("gradient_end_color", response["gradient_end_color"], "no_reload", true);
                }
            }

            if (response["color_mode"] === "Speed") {
                document.getElementById("current_led_color").innerHTML = '<svg ' +
                    'width="100%" height="45px">\n' +
                    '      <defs>\n' +
                    '        <linearGradient id="g1">\n' +
                    '          <stop offset="5%" stop-color="' + response["speed_slowest_color"] + '" />\n' +
                    '          <stop offset="95%" stop-color="' + response["speed_fastest_color"] + '" />\n' +
                    '        </linearGradient>\n' +
                    '       <linearGradient id="g2" x1=".5" x2=".5" y2="1">\n' +
                    '           <stop stop-color="#000" stop-opacity="0"/>\n' +
                    '           <stop offset=".59" stop-color="#000" stop-opacity=".34217436974789917"/>\n' +
                    '           <stop offset="1" stop-color="#000"/>\n' +
                    '       </linearGradient>' +
                    '      </defs>\n' +
                    '      <rect width="100%" height="45px" fill=\'url(#g1)\'/>' +
                    '      <rect width="100%" height="45px" fill=\'url(#g2)\'/>\n' +
                    '    </svg>'
                document.getElementById("current_led_color").innerHTML += '<img class="w-full opacity-50" ' +
                    'style="height: 40px;width:100%;margin-top:-40px" src="../static/piano.svg">' +
                    '<div class="flex"><p class="w-full text-xs italic text-gray-600 dark:text-gray-400">slowest</p>' +
                    '<p class="w-full text-xs italic text-right text-gray-600 dark:text-gray-400">fastest</p></div>';

                if (is_editing_sequence === "true") {
                    remove_color_modes();
                    document.getElementById('Speed').hidden = false;
                    document.getElementById("speed_slow_color").value = response["speed_slowest_color"];
                    document.getElementById("speed_fast_color").value = response["speed_fastest_color"];

                    document.getElementById("speed_slow_color").dispatchEvent(new Event('input'));
                    document.getElementById("speed_fast_color").dispatchEvent(new Event('input'));


                    change_setting("speed_slow_color", response["speed_slowest_color"], "no_reload", true);
                    change_setting("speed_fast_color", response["speed_fastest_color"], "no_reload", true);
                }
            }

            if (response["color_mode"] === "Rainbow") {
                const now = Date.now();
                let rainbow_example = '';
                rainbow_example += '<div class="flex overflow-hidden mt-2">';
                rainbow_example += '<canvas id="RainbowPreview" style="width: 100%; height: 50px;"></canvas></div>';
                rainbow_example += '<img class="w-full opacity-50" style="height: 40px;width:100%;margin-top:-40px" src="../static/piano.svg">';
                rainbow_example += '<p class="text-xs italic text-right text-gray-600 dark:text-gray-400">*approximate look</p>';
                document.getElementById("current_led_color").innerHTML = rainbow_example;

                window.cancelAnimationFrame(rainbow_animation);
                let count = -1;
                function update_rainbowctx() {
                    const canvas = document.getElementById('RainbowPreview');
                    if (!canvas)
                        return;

                    count++;
                    if (count % 2 === 0) { // 60fps from window.requestAnimationFrame may be excessive...
                        const width = canvas.clientWidth;
                        const height = canvas.clientHeight;
                        canvas.width = width;
                        canvas.height = height;
                        const ctx = canvas.getContext("2d");
                        //ctx.clearRect(0, 0, canvas.width, canvas.height);
                        const grd = ctx.createLinearGradient(0, 0, width, 0);
                        const cmap = gradients[response.rainbow_colormap] ?? [];

                        const led_count = +(config_settings["led_count"] ?? 176);
                        const reverse = (+config_settings["led_reverse"] === 1 ? -1 : 1);
                        const reverse_offset = (reverse === -1 ? led_count : 0);
                        const density = +(config_settings["leds_per_meter"] ?? 144) / 72;

                        const curtime = Date.now();
                        for (let i=0; i<=88; i+=2) {   // i+=2: it's a preview gradient, 44 gradient stops should be fine
                            const shift = ((curtime - now) * response.rainbow_timeshift) / 1000;

                            // Approximate get_note_position
                            const note_position = ~~(reverse * i * density + reverse_offset)
                            const rainbow_value = ~~((note_position + response["rainbow_offset"] + shift) *
                                    (response["rainbow_scale"] / 100)) & 255;
                            x = (rainbow_value/255) * (cmap.length - 1);
                            grd.addColorStop(i/88, rgbToHexA(cmap[~~x]));
                        }
                        ctx.fillStyle = grd;
                        ctx.fillRect(0, 0, width, height);
                    }

                    if (Number(document.getElementById("rainbow_timeshift").value) !== 0
                            && document.getElementById("color_mode").value === "Rainbow"
                            && current_page === "ledsettings") {
                        rainbow_animation = window.requestAnimationFrame(update_rainbowctx);
                    }
                }
                update_rainbowctx();

                if (is_editing_sequence === "true") {
                    document.getElementById("rainbow_offset").value = response["rainbow_offset"];
                    document.getElementById("rainbow_scale").value = response["rainbow_scale"];
                    document.getElementById("rainbow_timeshift").value = response.rainbow_timeshift;
                    document.getElementById("rainbow_colormap").value = response.rainbow_colormap;

                    remove_color_modes();
                    document.getElementById('Rainbow').hidden = false;

                    change_setting("rainbow_offset", response["rainbow_offset"], "no_reload", true);
                    change_setting("rainbow_scale", response["rainbow_scale"], "no_reload", true);
                    change_setting("rainbow_timeshift", response.rainbow_timeshift, "no_reload", true);
                    change_setting("rainbow_colormap", response.rainbow_colormap, "no_reload", true);
                }
            }

            if (response.color_mode === "VelocityRainbow") {
                const offset = ((~~document.getElementById("velocityrainbow_offset").value % 256) + 256) % 256;
                const scale = ~~document.getElementById("velocityrainbow_scale").value;
                const curve = ~~document.getElementById("velocityrainbow_curve").value;
                const colormap = document.getElementById("velocityrainbow_colormap").value;

                document.getElementById("current_led_color").innerHTML = '<canvas id="VelocityRainbowPreview" style="width: 100%; height: 40px;"></canvas>';
                const canvas = document.getElementById('VelocityRainbowPreview');
                const width = canvas.clientWidth;
                const height = canvas.clientHeight;
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext("2d");
                const grd = ctx.createLinearGradient(0, 0, width, 0);
                const cmap = gradients[colormap] ?? [];
                const stops = cmap.length - 1;
                for (let i = 0; i <= stops; i++) {
                    const vel = ~~(i * 255 / stops);
                    const vel2 = 255 * powercurve(i / stops, curve / 100);
                    const vel3 = (~~(vel2 * scale / 100) % 256 + 256) % 256;
                    const vel4 = (~~(vel3 + offset) % 256 + 256) % 256;

                    grd.addColorStop(i / stops, rgbToHexA(cmap[~~(vel4 * stops / 255)]));
                }
                ctx.fillStyle = grd;
                ctx.fillRect(0, 0, width, height);


                if (is_editing_sequence === "true") {
                    document.getElementById("velocityrainbow_offset").value = response["velocityrainbow_offset"];
                    document.getElementById("velocityrainbow_scale").value = response["velocityrainbow_scale"];
                    document.getElementById("velocityrainbow_curve").value = response["velocityrainbow_curve"];
                    document.getElementById("velocityrainbow_colormap").value = response["velocityrainbow_colormap"];

                    remove_color_modes();
                    document.getElementById('VelocityRainbow').hidden = false;

                    change_setting("velocityrainbow_offset", response["velocityrainbow_offset"], "no_reload", true);
                    change_setting("velocityrainbow_scale", response["velocityrainbow_scale"], "no_reload", true);
                    change_setting("velocityrainbow_curve", response["velocityrainbow_curve"], "no_reload", true);
                    change_setting("velocityrainbow_colormap", response["velocityrainbow_colormap"], "no_reload", true);
                }
            }

            if (response["color_mode"] === "Scale") {
                //document.getElementById("led_color").innerHTML = response.scale_key
                let scale_key_array = [response["key_in_scale_color"], response["key_not_in_scale_color"]];
                document.getElementById("current_led_color").innerHTML = '<div id="led_color_scale" class="flex"></div>';

                scale_key_array.forEach(function (item, index) {
                    document.getElementById("led_color_scale").innerHTML += '<svg width="100%" height="45px">' +
                        '<defs>\n' +
                        '   <linearGradient id="gradient_single_' + item + '" x1=".5" y1="1" x2=".5">\n' +
                        '       <stop stop-color="' + item + '" stop-opacity="0"/>\n' +
                        '       <stop offset=".61" stop-color="' + item + '" stop-opacity=".65"/>\n' +
                        '       <stop offset="1" stop-color="' + item + '"/>\n' +
                        '   </linearGradient>\n' +
                        '</defs>' +
                        '<rect width="100%" height="45px" fill="url(#gradient_single_' + item + ')" /></svg>';
                });
                document.getElementById("current_led_color").innerHTML += '<img class="w-full opacity-50" ' +
                    'style="height: 40px;width:100%;margin-top:-40px" src="../static/piano.svg">' +
                    '<div class="flex"><p class="w-full text-xs italic text-gray-600 dark:text-gray-400">in a scale</p>' +
                    '<p class="w-full text-xs italic text-right text-gray-600 dark:text-gray-400">not in a scale</p></div>';
                if (is_editing_sequence === "true") {
                    remove_color_modes();
                    document.getElementById('Scale').hidden = false;
                    document.getElementById("key_in_scale_color").value = response["key_in_scale_color"];
                    document.getElementById("key_not_in_scale_color").value = response["key_not_in_scale_color"];
                    document.getElementById("scale_key").value = response["scale_key"];

                    document.getElementById("key_in_scale_color").dispatchEvent(new Event('input'));
                    document.getElementById("key_not_in_scale_color").dispatchEvent(new Event('input'));

                    change_setting("key_in_scale_color", response["key_in_scale_color"], "no_reload", true);
                    change_setting("key_not_in_scale_color", response["key_not_in_scale_color"], "no_reload", true);
                    change_setting("scale_key", response["scale_key"], "no_reload", true);
                }
            }
        }
    };
    xhttp.open("GET", "/api/get_sequence_setting", true);
    xhttp.send();
}

function get_sequences() {
    if (!document.getElementById('sequences_list_1')) {
        return false;
    }

    const xhttp = new XMLHttpRequest();
    xhttp.timeout = 5000;
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            let sequence_editing_number = document.getElementById('sequences_list_2').value;

            let loop_length = 1;
            if (document.getElementById('sequence_edit').getAttribute("active") === 'true') {
                loop_length = 2;
            }
            for (let s = 1; s <= loop_length; s++) {
                const sequences_list = document.getElementById('sequences_list_' + s);
                let response = JSON.parse(this.responseText);
                removeOptions(document.getElementById('sequences_list_' + s));
                let i = 0;
                response["sequences_list"].unshift("None");
                response["sequences_list"].forEach(function (item, index) {
                    const opt = document.createElement('option');
                    opt.appendChild(document.createTextNode(item));
                    opt.value = i;
                    sequences_list.appendChild(opt);
                    i += 1
                })
                if (s === 1) {
                    sequences_list.value = response["sequence_number"];
                } else {
                    sequences_list.value = sequence_editing_number;
                }

            }
            //get_steps_list();
        }
    };
    xhttp.open("GET", "/api/get_sequences", true);
    xhttp.send();
}

function toggle_edit_sequence() {
    if (document.getElementById('sequence_edit').getAttribute("active") === 'true') {
        document.getElementById('sequence_edit').setAttribute("active", false);
        document.getElementById('sequence_edit_block').classList.add("opacity-50");
        document.getElementById('sequence_edit_block').classList.add("pointer-events-none");
        document.getElementById('sequence_edit').classList.add("animate-pulse");
        document.getElementById('sequence_block').classList.remove("pointer-events-none", "opacity-50");
        document.getElementById('sequences_list_2').value = 0;
    } else {
        document.getElementById('sequence_edit').setAttribute("active", true);
        document.getElementById('sequence_edit_block').classList.remove("opacity-50");
        document.getElementById('sequence_edit_block').classList.remove("pointer-events-none");
        document.getElementById('sequence_edit').classList.remove("animate-pulse");
        document.getElementById('sequence_block').classList.add("pointer-events-none", "opacity-50");
        get_sequences();
    }
}

function get_steps_list() {
    const xhttp = new XMLHttpRequest();
    const sequence_element = document.getElementById('sequences_list_2');
    const sequence = sequence_element.value;

    let current_step = document.getElementById('sequence_step').value;

    document.getElementById('sequence_name').value = sequence_element.options[sequence_element.selectedIndex].text;
    if (sequence === 0) {
        return false;
    }

    xhttp.timeout = 5000;
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            removeOptions(document.getElementById('sequence_step'));
            const sequences_list = document.getElementById('sequence_step');
            let response = JSON.parse(this.responseText);
            let i = 0;
            response["steps_list"].forEach(function (item, index) {
                const opt = document.createElement('option');
                opt.appendChild(document.createTextNode(item.replace('step_', 'Step ')));
                opt.value = i;
                sequences_list.appendChild(opt);
                i += 1
            });
            document.getElementById("control_number").value = response["control_number"];
            document.getElementById("next_step").value = response["next_step"];
            document.getElementById('sequence_step').value = current_step;
            set_step_properties(sequence_element.value,
                document.getElementById('sequence_step').value);

            if (i > 0 && document.getElementById('sequence_step').value === '') {
                document.getElementById('sequence_step').value = 0;
            }
        }
    };
    xhttp.open("GET", "/api/get_steps_list?sequence=" + sequence, true);
    xhttp.send();
}

function set_step_properties(sequence, step) {
    sequence -= 1
    const xhttp = new XMLHttpRequest();
    xhttp.timeout = 5000;
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            get_current_sequence_setting(true, true);
        }
    };
    step = step || 0;
    xhttp.open("GET", "/api/set_step_properties?sequence=" + sequence + "&step=" + step, true);
    xhttp.send();
}

function get_ports() {
    const xhttp = new XMLHttpRequest();
    xhttp.timeout = 5000;
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            let response = JSON.parse(this.responseText);
            
            // Update old dropdowns if they exist
            if (document.getElementById('active_input') != null) {
                const active_input_select = document.getElementById('active_input');
                const secondary_input_select = document.getElementById('secondary_input');
                const playback_select = document.getElementById('playback_input');
                const length = active_input_select.options.length;
                for (let i = length - 1; i >= 0; i--) {
                    active_input_select.options[i] = null;
                    secondary_input_select.options[i] = null;
                    playback_select.options[i] = null;
                }
                response["ports_list"].forEach(function (item, index) {
                    const opt = document.createElement('option');
                    const opt2 = document.createElement('option');
                    const opt3 = document.createElement('option');
                    opt.appendChild(document.createTextNode(item));
                    opt2.appendChild(document.createTextNode(item));
                    opt3.appendChild(document.createTextNode(item));
                    opt.value = item;
                    opt2.value = item;
                    opt3.value = item;
                    active_input_select.appendChild(opt);
                    secondary_input_select.appendChild(opt2);
                    playback_select.appendChild(opt3);
                });
                active_input_select.value = response["input_port"];
                secondary_input_select.value = response["secondary_input_port"];
                playback_select.value = response["play_port"];
            }
            
            // Update raw textarea
            if (document.getElementById('connect_all_textarea') != null) {
                let connected_ports = response["connected_ports"];
                connected_ports = connected_ports.replaceAll("\\n", "&#10;")
                connected_ports = connected_ports.replaceAll("\\t", "        ")
                connected_ports = connected_ports.replaceAll("b\"", "")
                document.getElementById('connect_all_textarea').innerHTML = connected_ports;
            }
            
            if (response["midi_logging"] === "1") {
                const checkbox = document.getElementById("midi_events_checkbox");
                if (checkbox) checkbox.checked = true;
            }
        }
    };
    xhttp.open("GET", "/api/get_ports", true);
    xhttp.send();
}

function get_logs() {
    const refresh_logs_button = document.getElementById("refresh-logs");
    refresh_logs_button.classList.add("animate-spin", "pointer-events-none");

    const xhttp = new XMLHttpRequest();
    xhttp.timeout = 5000;
    xhttp.onreadystatechange = function () {
        if (this["readyState"] === 4 && this["status"] === 200) {
            let response = this["response"];
            let textarea = document.getElementById('logs')
            textarea.innerHTML = response;
            textarea.scrollTop = textarea.scrollHeight;
            refresh_logs_button.classList.remove("animate-spin", "pointer-events-none");
        }
    };
    xhttp.onerror = function () {
        refresh_logs_button.classList.remove("animate-spin", "pointer-events-none");
    }
    xhttp.ontimeout = function () {
        refresh_logs_button.classList.remove("animate-spin", "pointer-events-none");
    }
    let last_logs = document.getElementById("last_logs").value;
    xhttp.open("GET", "/api/get_logs?last_logs=" + last_logs, true);
    xhttp.send();
}

function get_recording_status() {
    const xhttp = new XMLHttpRequest();
    xhttp.timeout = 5000;
    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            let response = JSON.parse(this.responseText);
            document.getElementById("input_port").innerHTML = response["input_port"];
            document.getElementById("play_port").innerHTML = response["play_port"];

            if (response["isrecording"]) {
                document.getElementById("recording_status").innerHTML = '<p class="animate-pulse text-red-400">recording</p>';
                document.getElementById("start_recording_button").classList.add('pointer-events-none', 'animate-pulse');
                document.getElementById("save_recording_button").classList.remove('pointer-events-none', 'opacity-50');
                document.getElementById("cancel_recording_button").classList.remove('pointer-events-none', 'opacity-50');
            } else {
                document.getElementById("recording_status").innerHTML = '<p>idle</p>';
                document.getElementById("start_recording_button").classList.remove('pointer-events-none', 'animate-pulse');
                document.getElementById("save_recording_button").classList.add('pointer-events-none', 'opacity-50');
                document.getElementById("cancel_recording_button").classList.add('pointer-events-none', 'opacity-50');
            }
            if (Object.keys(response["isplaying"]).length > 0) {
                document.getElementById("midi_player_wrapper").classList.remove("hidden");
                document.getElementById("start_midi_play").classList.add("hidden");
                document.getElementById("stop_midi_play").classList.remove("hidden");
            }
        }
    };
    xhttp.open("GET", "/api/get_recording_status", true);
    xhttp.send();
}

function get_learning_status(loop_call = false) {
    const xhttp = new XMLHttpRequest();
    const delay_between_requests = 500;
    xhttp.timeout = 5000;
    xhttp.onreadystatechange = function () {
        let response;
        if (this.readyState === 4 && this.status === 200) {
            response = JSON.parse(this.responseText);

            clearTimeout(learning_status_timeout);
            document.getElementById("start_learning").classList.add("pointer-events-none", "opacity-50");
            switch (response.loading) {
                case 0:
                    learning_status_timeout = setTimeout(get_learning_status, delay_between_requests, true);
                    break;
                case 1:
                    learning_status_timeout = setTimeout(get_learning_status, delay_between_requests, true);
                    document.getElementById("start_learning").innerHTML = '<span class="flex uppercase text-xs m-auto ">' +
                        '<div id="learning_status" class="align-middle text-center">Loading...</div></span>';
                    break;
                case 2:
                    learning_status_timeout = setTimeout(get_learning_status, delay_between_requests, true);
                    document.getElementById("start_learning").innerHTML = '<span class="flex uppercase text-xs m-auto ">' +
                        '<div id="learning_status" class="align-middle text-center">Processing...</div></span>';
                    break;
                case 3:
                    learning_status_timeout = setTimeout(get_learning_status, delay_between_requests, true);
                    document.getElementById("start_learning").innerHTML = '<span class="flex uppercase text-xs m-auto ">' +
                        '<div id="learning_status" class="align-middle text-center">Merging...</div></span>';
                    break;
                case 4:
                    document.getElementById("start_learning").classList.remove("pointer-events-none", "opacity-50");
                    document.getElementById("start_learning").innerHTML = '<span class="flex uppercase text-xs m-auto ">' +
                        '<div id="learning_status" class="align-middle text-center" data-translate="learning_status">Start learning</div></span>';
                    translateStaticContent();
                    break;
                case 5:
                    document.getElementById("start_learning").innerHTML = '<span class="flex uppercase text-xs m-auto ">' +
                        '<div id="learning_status" class="align-middle text-center">Error!</div></span>';
                    break;
                default:
                    break;
            }


            if (response.loading === 4 || loop_call === false) {

                document.getElementById("practice").value = response["practice"];
                document.getElementById("tempo_slider").value = response["set_tempo"];
                document.getElementById("hands").value = response["hands"];
                document.getElementById("mute_hand").value = response["mute_hand"];

                document.getElementById("wrong_notes").value = response["show_wrong_notes"];
                document.getElementById("future_notes").value = response["show_future_notes"];

                document.getElementById("start_point").innerHTML = response["start_point"];
                document.getElementById("end_point").innerHTML = response["end_point"];

                hand_colorList = response["hand_colorList"];
                let hand_colorR = response["hand_colorR"];
                let hand_colorL = response["hand_colorL"];

                let hand_colorR_RGB = response.hand_colorList[hand_colorR][0] + ", " + response.hand_colorList[hand_colorR][1] + ", " + response.hand_colorList[hand_colorR][2];
                let hand_colorL_RGB = response.hand_colorList[hand_colorL][0] + ", " + response.hand_colorList[hand_colorL][1] + ", " + response.hand_colorList[hand_colorL][2];

                document.getElementById("hand_colorR").style.fill = 'rgb(' + hand_colorR_RGB + ')';
                document.getElementById("hand_colorL").style.fill = 'rgb(' + hand_colorL_RGB + ')';

                document.getElementById("number_of_mistakes").value = response["number_of_mistakes"];

                if (response["is_loop_active"] === 1) {
                    document.getElementById("is_loop_active").checked = true;
                }

                const min = 0;
                const max = 100;

                const value_left = response["start_point"];
                const value_right = response["end_point"];

                const value_left_percent = (100 / (max - min)) * value_left - (100 / (max - min)) * min;
                const value_right_percent = (100 / (max - min)) * value_right - (100 / (max - min)) * min;

                const value_right_percent_reverse = 100 - value_right_percent;

                document.getElementById("learning_slider_wrapper").innerHTML = '<div slider="" id="slider-distance">\n' +
                    '<div>\n' +
                    '   <div inverse-left="" style="width:' + value_left_percent + '%;"></div>\n' +
                    '   <div inverse-right="" style="width:' + value_right_percent_reverse + '%;"></div>\n' +
                    '   <div range="" style="left:' + value_left_percent + '%;right:' + value_right_percent_reverse + '%;"></div>\n' +
                    '   <span thumb="" style="left:' + value_left_percent + '%;"></span>\n' +
                    '   <span thumb="" style="left:' + value_right_percent + '%;"></span>\n' +
                    '   <div sign="" style="left:' + value_left_percent + '%;">\n' +
                    '       <span id="value1">' + value_left + '</span>\n' +
                    '   </div>\n' +
                    '   <div sign="" style="left:' + value_right_percent + '%;">\n' +
                    '       <span id="value2">' + value_right + '</span>\n' +
                    '   </div>\n' +
                    '</div>\n' +
                    '<input id="learning_start_point" type="range" tabindex="0" value="' + value_left + '" max="100" min="0" step="1"\n' +
                    '   oninput="show_left_slider(this)" onchange="change_setting(\'learning_start_point\', this.value);\n' +
                    '   document.getElementById(\'start_point\').innerHTML = this.value">\n' +
                    '<input id="learning_end_point" type="range" tabindex="0" value="' + value_right + '" max="100" min="0" step="1"\n' +
                    '   oninput="show_right_slider(this)" onchange="change_setting(\'learning_end_point\', this.value);\n' +
                    '   document.getElementById(\'end_point\').innerHTML = this.value">\n' +
                    '</div>';
                
                if (response["is_led_activeL"] === 1) {
                    document.getElementById("is_led_activeL").checked = true;
                } else {
                    document.getElementById("is_led_activeL").checked = false;
                    document.getElementById("hand_colorL").style.fill = 'rgb(0,0,0)';
                }

                if (response["is_led_activeR"] === 1) {
                    document.getElementById("is_led_activeR").checked = true;
                } else {
                    document.getElementById("is_led_activeR").checked = false;
                    document.getElementById("hand_colorR").style.fill = 'rgb(0,0,0)';
                }
            }

        }

    };
    xhttp.open("GET", "/api/get_learning_status", true);
    xhttp.send();
}

function get_songs() {
    let page;
    let max_page;
    const xhttp_spp = new XMLHttpRequest();
    xhttp_spp.timeout = 5000;
    xhttp_spp.onreadystatechange = function () {          
        let response;
        if (this.readyState === 4 && this.status === 200) {
            response = JSON.parse(this.responseText);  
            length = response["songs_per_page"]; 
            let sortby = response["sort_by"]; 
            document.getElementById("sort_by").value = sortby;
            if (document.getElementById("songs_page")) {
                page = parseInt(document.getElementById("songs_page").value);
                let max_page = parseInt(document.getElementById("songs_page").max);
            } else {
                page = 1;
                max_page = 1;
            }
            if (max_page === 0) {
                max_page = 1;
            }
            if (page > max_page) {
                document.getElementById("songs_page").value = max_page;
                return false;
            }
            if (page < 1) {
                document.getElementById("songs_page").value = 1;
                return false;
            }
            document.getElementById("songs_list_table").classList.add("animate-pulse", "pointer-events-none");
       
            if (document.getElementById("songs_per_page")) {
                length = document.getElementById("songs_per_page").value;
                change_setting("songs_per_page", length)
            }
            let search = document.getElementById("song_search").value;

            const xhttp = new XMLHttpRequest();
            xhttp.timeout = 5000;
            xhttp.onreadystatechange = function () {
                if (this.readyState === 4 && this.status === 200) {
                    document.getElementById("songs_list_table").innerHTML = this.responseText;
                    const dates = document.getElementsByClassName("song_date");
                    for (let i = 0; i < dates.length; i++) {
                        dates.item(i).innerHTML = new Date(dates.item(i).innerHTML * 1000).toISOString().slice(0, 19).replace('T', ' ');
                    }
                    const names = document.getElementsByClassName("song_name");
                    for (let i = 0; i < names.length; i++) {
                        names.item(i).value = names.item(i).value.replace('.mid', '');
                    }
                    document.getElementById("songs_list_table").classList.remove("animate-pulse", "pointer-events-none");

                    document.getElementById("songs_per_page").value = length;

                    if (sortby === "nameAsc") {
                        document.getElementById("sort_icon_nameAsc").classList.remove("hidden");
                        document.getElementById("sort_icon_nameDesc").classList.add("hidden");
                        document.getElementById("sort_by_name").classList.add("text-gray-800", "dark:text-gray-200");
                        document.getElementById("sort_by_date").classList.remove("text-gray-800", "dark:text-gray-200");
                    }
                    if (sortby === "nameDesc") {
                        document.getElementById("sort_icon_nameDesc").classList.remove("hidden");
                        document.getElementById("sort_icon_nameAsc").classList.add("hidden");
                        document.getElementById("sort_by_name").classList.add("text-gray-800", "dark:text-gray-200");
                        document.getElementById("sort_by_date").classList.remove("text-gray-800", "dark:text-gray-200");
                    }

                    if (sortby === "dateAsc") {
                        document.getElementById("sort_icon_dateAsc").classList.remove("hidden");
                        document.getElementById("sort_icon_dateDesc").classList.add("hidden");
                        document.getElementById("sort_by_date").classList.add("text-gray-800", "dark:text-gray-200");
                        document.getElementById("sort_by_name").classList.remove("text-gray-800", "dark:text-gray-200");
                    }
                    if (sortby === "dateDesc") {
                        document.getElementById("sort_icon_dateDesc").classList.remove("hidden");
                        document.getElementById("sort_icon_dateAsc").classList.add("hidden");
                        document.getElementById("sort_by_date").classList.add("text-gray-800", "dark:text-gray-200");
                        document.getElementById("sort_by_name").classList.remove("text-gray-800", "dark:text-gray-200");
                    }

                    // Highscore population after table rendered
                    const applyHighscores = (pid) => {
                        if(!pid) return;
                        fetch('/api/get_highscores?profile_id=' + pid)
                            .then(r=>r.json())
                            .then(data=>{
                                if(!data.success) return;
                                const hs = data.highscores || {};
                                document.querySelectorAll('.song_highscore_cell').forEach(cell=>{
                                    const song = cell.getAttribute('data-song');
                                    const val = Object.prototype.hasOwnProperty.call(hs, song) ? hs[song] : 0;
                                    const span = cell.querySelector('.song_highscore_value');
                                    if(span) span.textContent = val;
                                });
                            })
                            .catch(()=>{});
                    };
                    const pid = window.currentProfileId;
                    if(pid){
                        applyHighscores(pid);
                    } else {
                        let restored = null;
                        try { if(typeof getCookie === 'function') restored = getCookie('currentProfileId'); } catch(e) {}
                        if(restored){
                            window.currentProfileId = parseInt(restored);
                            applyHighscores(window.currentProfileId);
                        } else {
                            fetch('/api/get_current_profile')
                                .then(r=>r.json())
                                .then(d=>{
                                    if(d && d.profile_id){ window.currentProfileId = d.profile_id; applyHighscores(window.currentProfileId); }
                                })
                                .catch(()=>{});
                        }
                    }
                }
                translateStaticContent();
            };
            xhttp.open("GET", "/api/get_songs?page=" + page + "&length=" + length + "&sortby=" + sortby + "&search=" + search, true);
            xhttp.send();
        }
    };
    xhttp_spp.open("GET", "/api/get_song_list_setting", true);
    xhttp_spp.send();
}


function show_multicolors(colors, ranges, iteration) {
    try {
        colors = JSON.parse(colors);
        ranges = JSON.parse(ranges);
        iteration = JSON.parse(iteration);
    } catch (e) {
    }

    let multicolor_element = document.getElementById("Multicolor");
    let i = 0;
    multicolor_element.innerHTML = "<div class=\"flex items-center mb-4\">\n" +
        "            <input onclick=\"change_setting('multicolor_iteration', this.checked)\" id=\"multicolor_iteration_checkbox\" " +
        "           type=\"checkbox\" value=\"\" class=\"w-4 h-4 text-blue-600 glass-light rounded border-gray-300 " +
        "focus:ring-blue-500 dark:focus:ring-blue-600 focus:ring-2\">\n" +
        "            <label for=\"default-checkbox\" class=\"pl-2 block uppercase tracking-wide text-xs font-bold mt-2 " +
        "text-gray-600 dark:text-gray-400\">Cycle through colors</label>\n" +
        "        </div>";

    const add_button = "<button onclick=\"this.classList.add('hidden');this.nextElementSibling.classList.remove('hidden')\" " +
        "id=\"multicolor_add\" class=\"w-full outline-none mb-2 glass-light hover:glass font-bold h-6 py-2 px-2 " +
        "rounded-glass inline-flex items-center transition-smooth-fast\">\n" +
        "   <svg xmlns=\"http://www.w3.org/2000/svg\" class=\"h-6 w-full justify-items-center text-green-400\" " +
        "fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\">\n" +
        "      <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M12 9v3m0 " +
        "0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z\"></path>\n" +
        "   </svg>\n" +
        "</button>\n" +
        "<button onclick=\"change_setting('add_multicolor', '0')\" id=\"multicolor_add\" " +
        "class=\"hidden w-full outline-none mb-2 glass-light hover:glass font-bold h-6 py-2 px-2 " +
        "rounded-glass inline-flex items-center transition-smooth-fast\">\n" +
        "<span class=\"w-full text-green-400\">Click to confirm</span></button>";
    multicolor_element.classList.remove("pointer-events-none", "opacity-50");
    multicolor_element.innerHTML += add_button;
    for (const element of colors) {

        const hex_color = rgbToHex(element[0], element[1], element[2]);

        const min = 20;
        const max = 108;

        const value_left = ranges[i][0];
        const value_right = ranges[i][1];

        const value_left_percent = (100 / (max - min)) * value_left - (100 / (max - min)) * min;
        const value_right_percent = (100 / (max - min)) * value_right - (100 / (max - min)) * min;

        const value_right_percent_reverse = 100 - value_right_percent;

        //append multicolor slider
        multicolor_element.innerHTML += '<div class="mb-2 glass-light rounded-glass p-2 transition-smooth-fast" id="multicolor_' + i + '">' +
            '<label class="ml-2 inline block uppercase tracking-wide text-xs font-bold mt-2 text-gray-600 dark:text-gray-400">\n' +
            '                    Color ' + parseInt(i + 1) + '\n' +
            '                </label><div onclick=\'this.classList.add("hidden");' +
            'this.nextElementSibling.classList.remove("hidden")\' class="inline float-right text-red-400">' +
            '<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">\n' +
            '  <path stroke-linecap="round" stroke-linejoin="round" ' +
            'stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 ' +
            '4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />\n' +
            '</svg>' +
            '</div><div onclick=\'change_setting("remove_multicolor", "' + i + '");' +
            'document.getElementById("Multicolor").classList.add("pointer-events-none","opacity-50")\' ' +
            'class="hidden inline float-right text-red-400">Click to confirm</div>' +
            '<input id="multicolor_input_' + i + '" type="color" value="' + hex_color + '"\n' +
            '                        class="cursor-pointer px-2 pt-2 h-8 w-full glass-light rounded-glass" ' +
            'oninput=\'editLedColor(event, "multicolor_' + i + '_")\'' +
            'onchange=\'change_setting("multicolor", this.value, ' + i + ')\'>\n' +
            '                <div id="multicolors_' + i + '" class="justify-center flex" ' +
            'onchange=\'change_color_input_multicolor(event, "multicolor_' + i + '_", "multicolor_input_' + i + '", "multicolor", ' + i + ')\'>\n' +
            '                    <span class="w-1/12 h-6 px-2 glass-light text-red-400">R:</span>\n' +
            '                    <input id="multicolor_' + i + '_red" type="number" value="' + element[0] + '" min="0" max="255"\n' +
            '                           class="w-2/12 h-6 glass-light" onkeyup=enforceMinMax(this)>\n' +
            '                    <span class="w-1/12 h-6 px-2 glass-light text-green-400">G:</span>\n' +
            '                    <input id="multicolor_' + i + '_green" type="number" value="' + element[1] + '" min="0" max="255"\n' +
            '                           class="w-2/12 h-6 glass-light" onkeyup=enforceMinMax(this)>\n' +
            '                    <span class="w-1/12 h-6 px-2 glass-light text-blue-400">B:</span>\n' +
            '                    <input id="multicolor_' + i + '_blue" type="number" value="' + element[2] + '" min="0" max="255"\n' +
            '                           class="w-2/12 h-6 glass-light" onkeyup=enforceMinMax(this)>\n' +
            '                </div>' +
            '<div slider id="slider-distance">\n' +
            '  <div>\n' +
            '    <div inverse-left style="width:' + value_left_percent + '%;"></div>\n' +
            '    <div inverse-right style="width:' + value_right_percent_reverse + '%;"></div>\n' +
            '    <div range style="left:' + value_left_percent + '%;right:' + value_right_percent_reverse + '%;"></div>\n' +
            '    <span thumb style="left:' + value_left_percent + '%;"></span>\n' +
            '    <span thumb style="left:' + value_right_percent + '%;"></span>\n' +
            '    <div sign style="left:' + value_left_percent + '%;">\n' +
            '      <span id="value">' + value_left + '</span>\n' +
            '    </div>\n' +
            '    <div sign style="left:' + value_right_percent + '%;">\n' +
            '      <span id="value">' + value_right + '</span>\n' +
            '    </div>\n' +
            '  </div>\n' +
            '  <input type="range" tabindex="0" value="' + value_left + '" max="' + max + '" min="' + min + '" ' +
            'step="1" oninput="show_left_slider(this)" ' +
            'onchange=\'change_setting("multicolor_range_left", this.value, ' + i + ')\' />\n' +
            '  <input type="range" tabindex="0" value="' + value_right + '" max="' + max + '" min="' + min + '" ' +
            'step="1" oninput="show_right_slider(this)" ' +
            'onchange=\'change_setting("multicolor_range_right", this.value, ' + i + ')\' />\n' +
            '</div>' +
            '               </div>';
        i++;
    }
    if (i >= 3) {
        multicolor_element.innerHTML += add_button;
    }

    if (iteration === 1) {
        document.getElementById("multicolor_iteration_checkbox").checked = true;
    }
}

function show_note_offsets(note_offsets) {
    try {
        note_offsets = JSON.parse(note_offsets);
    } catch (e) {
    }

    let offset_element = document.getElementById("NoteOffsetEntry");
    if (!offset_element) {
        return;
    }
    var i = 0
    offset_element.innerHTML = "";
    const add_button = `<button onclick="this.classList.add('hidden');this.nextElementSibling.classList.remove('hidden')" id="note_offsets_add" class="w-full outline-none mb-2 glass-light hover:glass font-bold h-6 py-1 px-1 rounded-glass inline-flex items-centers transition-smooth-fast">
   <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-full justify-items-center text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"></path>
   </svg>
</button>
<button onclick="change_setting('add_note_offset', '0');temporary_show_chords_animation();" id="note_offsets_add" class="hidden w-full outline-none mb-2 glass-light hover:glass font-bold h-6 py-1 px-1 rounded-glass inline-flex items-centers transition-smooth-fast">
<span class="w-full text-green-400">Click to confirm</span></button>`;
    offset_element.classList.remove("pointer-events-none", "opacity-50");
    offset_element.innerHTML += add_button;
    for (const element of note_offsets) {
        offset_element.innerHTML += `<div class="mb-2 glass-light rounded-glass p-2 transition-smooth-fast" id="noteoffset_${i}">
            <label class="ml-2 inline block uppercase tracking-wide text-xs font-bold mt-2 text-gray-600 dark:text-gray-400">
                ${translate("note_offset")} ${parseInt(i + 1)}
            </label>
            <div onclick='this.classList.add("hidden");this.nextElementSibling.classList.remove("hidden");temporary_show_chords_animation();' class="inline float-right text-red-400">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </div>
            <div onclick='change_setting("remove_note_offset", "${i}"); document.getElementById("NoteOffsetEntry").classList.add("pointer-events-none","opacity-50"); temporary_show_chords_animation();' class="hidden inline float-right text-red-400">Click to confirm</div>
            <div id="note_offset_${i}" class="justify-center flex" 
                onchange='change_setting("update_note_offset", "${i}", (parseInt(document.getElementById("note_offset_${i}_num").value) + 20) + "," + document.getElementById("note_offset_${i}_off").value); temporary_show_chords_animation();'>
                <span class="w-1/20 px-2 glass-light text-red-400">${translate("light_number")}:</span>
                <input id="note_offset_${i}_num" type="number" value="${element[0] - 20}" min="0" max="255"
                       class="w-2/12 h-6 glass-light" onkeyup=enforceMinMax(this)>
                <span class="w-1/20 h-6 px-2 glass-light text-green-400">${translate("offset")}:</span>
                <input id="note_offset_${i}_off" type="number" value="${element[1]}" min="-255" max="255"
                       class="w-2/12 h-6 glass-light" onkeyup=enforceMinMax(this)>
            </div>
        </div>`;
        i++;
    }

    if (i >= 1) {
        let end_button = add_button.replace("add_note_offset", "append_note_offset")
        end_button = end_button.replace("note_offsets_add", "note_offsets_add2")
        offset_element.innerHTML += end_button;
    }
}

function show_left_slider(element) {
    element.value = Math.min(element.value, element.parentNode.childNodes[5].value);
    const value = (100 / (parseInt(element.max) - parseInt(element.min))) * parseInt(element.value) - (100 / (parseInt(element.max) - parseInt(element.min))) * parseInt(element.min);
    const children = element.parentNode.childNodes[1].childNodes;
    children[1].style.width = value + '%';
    children[5].style.left = value + '%';
    children[7].style.left = value + '%';
    children[11].style.left = value + '%';
    children[11].childNodes[1].innerHTML = element.value;
}

function show_right_slider(element) {
    element.value = Math.max(element.value, element.parentNode.childNodes[3].value);
    const value = (100 / (parseInt(element.max) - parseInt(element.min))) * parseInt(element.value) - (100 / (parseInt(element.max) - parseInt(element.min))) * parseInt(element.min);
    const children = element.parentNode.childNodes[1].childNodes;
    children[3].style.width = (100 - value) + '%';
    children[5].style.right = (100 - value) + '%';
    children[9].style.left = value + '%';
    children[13].style.left = value + '%';
    children[13].childNodes[1].innerHTML = element.value;
}

function change_color_input(prefix, color_input_id, setting_name) {
    const new_color = rgbToHex(
        parseInt(document.getElementById(prefix + "red").value, 10),
        parseInt(document.getElementById(prefix + "green").value, 10),
        parseInt(document.getElementById(prefix + "blue").value, 10));
    document.getElementById(color_input_id).value = new_color;
    change_setting(setting_name, new_color)
}

function change_color_input_multicolor(event, prefix, id_to_change, setting_name, i) {
    const new_color = rgbToHex(
        parseInt(document.getElementById(prefix + "red").value, 10),
        parseInt(document.getElementById(prefix + "green").value, 10),
        parseInt(document.getElementById(prefix + "blue").value, 10));
    document.getElementById(id_to_change).value = new_color;
    change_setting(setting_name, new_color, i)
}

const editLedColor = function (event, prefix) {
    document.getElementById(prefix + "red").value = hexToRgb(event.srcElement.value).r;
    document.getElementById(prefix + "green").value = hexToRgb(event.srcElement.value).g;
    document.getElementById(prefix + "blue").value = hexToRgb(event.srcElement.value).b;
};

function temporary_disable_button(element, timeout) {
    element.classList.add('pointer-events-none', 'animate-pulse');
    setTimeout(function () {
        element.classList.add('hidden');
        element.previousElementSibling.classList.remove('hidden');
        element.classList.remove('pointer-events-none', 'animate-pulse');
    }, timeout);
}

function handle_confirmation_button(element, delay = 1000) {
    element.classList.remove("hidden");
    element.classList.add("pointer-events-none", "animate-pulse")

    setTimeout(() => {
        element.classList.remove('pointer-events-none', "animate-pulse");
    }, delay);
}
// --- Added scoring & session summary features (merged) ---

function handleScoreUpdate(data) {
    if (data.type === "score_update") {
        const scoreElement = document.getElementById('score_value');
        const comboElement = document.getElementById('combo_value');
        const multiplierElement = document.getElementById('multiplier_value');
        const feedbackElement = document.getElementById('score_update_feedback');

        if (scoreElement) scoreElement.textContent = data.score;
        if (comboElement) comboElement.textContent = data.combo;
        if (multiplierElement) multiplierElement.textContent = data.multiplier;

        if (feedbackElement && data.last_update !== 0) {
            let updateValue = data.last_update;
            let updateColor = updateValue > 0 ? 'text-green-500' : 'text-red-500';
            let sign = updateValue > 0 ? '+' : '';

            feedbackElement.textContent = `(${sign}${updateValue})`;
            feedbackElement.className = `ml-2 text-lg font-bold ${updateColor} opacity-100 transition-opacity duration-1000`;

            // Fade out the feedback
            setTimeout(() => {
                feedbackElement.classList.add('opacity-0');
            }, 100); // Start fading shortly after appearing
            
            // Clear the text after fade out
             setTimeout(() => {
                feedbackElement.textContent = '';
            }, 1100); // Corresponds to duration-1000 + timeout delay
        }
         else if (feedbackElement) {
             // Clear feedback instantly if last_update is 0 (e.g., on reset)
             feedbackElement.textContent = '';
             feedbackElement.className = `ml-2 text-lg font-bold opacity-0`;
         }
    }
}

function handleHighscoreUpdate(data){
    if(data.type !== 'highscore_update') return;
    // Only update if current profile matches
    if(window.currentProfileId && parseInt(window.currentProfileId) !== parseInt(data.profile_id)){
        return;
    }
    // Find the highscore cell for this song and update its value
    const selector = `.song_highscore_cell[data-song="${CSS.escape(data.song_name)}"] .song_highscore_value`;
    const span = document.querySelector(selector);
    if(span){ span.textContent = data.score; }
}

let summaryTimeout = null; // To store the timeout ID
let summaryChart = null; // To store the Chart instance

function handleSessionSummary(data, retries = 5) {

    console.log(`Attempting to handle session summary (Retries left: ${retries})`, data);

        // Respect user preference for showing summary popup
    try {
        const prefCookie = (typeof getCookie === 'function') ? getCookie('show_summary_popup') : null;
        // Also check the checkbox state on the page if present
        const prefCheckbox = document.getElementById('show_summary_popup');
        const isAllowed = (prefCookie === null ? (prefCheckbox ? prefCheckbox.checked : true) : prefCookie === '1');
        if (!isAllowed) {
            console.log('Session summary popup disabled by user preference.');
            return; // Do not open the popup
        }
    } catch (e) {
        // If anything goes wrong, default to showing the popup
    }
    const summaryWindow = document.getElementById('session_summary_window');
    const summaryContent = document.getElementById('session_summary_content');
    const delayR_el = document.getElementById('summary_delay_r');
    const delayL_el = document.getElementById('summary_delay_l');
    const mistakesR_el = document.getElementById('summary_mistakes_r_count');
    const mistakesL_el = document.getElementById('summary_mistakes_l_count');
    const canvas = document.getElementById('summary_graph_canvas');

    // Check if elements are loaded
    if (!summaryWindow || !summaryContent || !delayR_el || !delayL_el || !mistakesR_el || !mistakesL_el || !canvas) {
        if (retries > 0) {
            console.log("Summary elements not found, retrying...");
            setTimeout(() => handleSessionSummary(data, retries - 1), 200); // Wait 200ms and retry
            return;
        } else {
            console.error("Summary elements or canvas not found after multiple retries!");
            return; // Give up after several retries
        }
    }

    console.log("Summary elements found, proceeding.");

    // Populate text data
    delayR_el.textContent = data.delay_r;
    delayL_el.textContent = data.delay_l;
    mistakesR_el.textContent = data.mistakes_r_count;
    mistakesL_el.textContent = data.mistakes_l_count;
    
    // Add translations if needed
    translateStaticContent();

    // Clear any existing timeout to prevent premature hiding
    if (summaryTimeout) {
        clearTimeout(summaryTimeout);
        summaryTimeout = null;
    }
    
    // --- Chart.js Setup --- 
    const ctx = canvas.getContext('2d');
    
    // Destroy previous chart instance if it exists
    if (summaryChart) {
        summaryChart.destroy();
        summaryChart = null;
    }

    // Prepare chart data (filter out negative delays; graph shows only positive values)
    const rawTimingDataR = data.timing_r.map(item => ({ x: item[0], y: item[1] }));
    const rawTimingDataL = data.timing_l.map(item => ({ x: item[0], y: item[1] }));
    const timingDataR = rawTimingDataR.filter(p => p.y >= 0);
    const timingDataL = rawTimingDataL.filter(p => p.y >= 0);

    // Determine y-axis max from positive delays (fallback to data.max_delay)
    const allPositiveDelays = timingDataR.map(p => p.y).concat(timingDataL.map(p => p.y));
    const maxPositiveDelay = allPositiveDelays.length > 0 ? Math.max(...allPositiveDelays, data.max_delay) : data.max_delay;
    const minYAxis = 0; // Enforce non-negative axis
    let maxYAxis = maxPositiveDelay * 1.1; // 10% headroom
    if (maxYAxis <= 0) {
        maxYAxis = 0.5; // fallback so chart has visible range
    }

    // Mistake markers: place at baseline (small epsilon so they are visible on the axis line)
    // Place mistake markers slightly above zero so X symbols are not clipped by the axis line.
    const mistakeBaseline = Math.max(0.002, maxYAxis * 0.01); // 1% of range or small epsilon
    const mistakeDataR = data.mistakes_r_times.map(time => ({ x: time, y: mistakeBaseline }));
    const mistakeDataL = data.mistakes_l_times.map(time => ({ x: time, y: mistakeBaseline }));

    summaryChart = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: translate('right_hand_notes'),
                    data: timingDataR,
                    backgroundColor: data.color_r,
                    borderColor: data.color_r,
                    pointRadius: 5,
                },
                {
                    label: translate('left_hand_notes'),
                    data: timingDataL,
                    backgroundColor: data.color_l,
                    borderColor: data.color_l,
                    pointRadius: 5,
                },
                {
                    label: translate('right_hand_mistakes'),
                    data: mistakeDataR,
                    backgroundColor: data.color_r,
                    borderColor: data.color_r,
                    pointStyle: (ctx) => {
                        // Custom draw: larger X centered; Chart.js built-in may clip at baseline
                        const {chart} = ctx;
                        const size = 8;
                        const canvas = document.createElement('canvas');
                        canvas.width = canvas.height = size;
                        const c = canvas.getContext('2d');
                        c.strokeStyle = data.color_r;
                        c.lineWidth = 2;
                        c.beginPath();
                        c.moveTo(1,1); c.lineTo(size-1,size-1);
                        c.moveTo(size-1,1); c.lineTo(1,size-1);
                        c.stroke();
                        return canvas;
                    },
                    radius: 8,
                    showLine: false
                },
                {
                    label: translate('left_hand_mistakes'),
                    data: mistakeDataL,
                    backgroundColor: data.color_l,
                    borderColor: data.color_l,
                    pointStyle: (ctx) => {
                        const size = 8;
                        const canvas = document.createElement('canvas');
                        canvas.width = canvas.height = size;
                        const c = canvas.getContext('2d');
                        c.strokeStyle = data.color_l;
                        c.lineWidth = 2;
                        c.beginPath();
                        c.moveTo(1,1); c.lineTo(size-1,size-1);
                        c.moveTo(size-1,1); c.lineTo(1,size-1);
                        c.stroke();
                        return canvas;
                    },
                    radius: 8,
                    showLine: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: translate('note_timing_vs_delay')
                },
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label.includes(translate('mistakes')) || label.includes(translate('right_hand_mistakes')) || label.includes(translate('left_hand_mistakes'))) {
                                return `${label}: ${translate('time')} ${context.parsed.x.toFixed(2)}s`;
                            }
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += `${translate('delay')} ${context.parsed.y.toFixed(3)}s`;
                            }
                            if (context.parsed.x !== null) {
                                label += ` ${translate('at')} ${context.parsed.x.toFixed(2)}s`;
                            }
                            return label;
                        }
                    }
                },
                annotation: {
                    annotations: {
                        maxDelayLine: {
                            type: 'line',
                            yMin: data.max_delay,
                            yMax: data.max_delay,
                            borderColor: 'rgb(15, 249, 78)', // Green line
                            borderWidth: 2,
                            borderDash: [6, 6],
                            label: {
                                content: translate('max_acceptable_delay'),
                                enabled: true,
                                position: 'start'
                            }
                        }
                    }
                },
                zoom: {
                    // Pan (mouse drag or single-finger touch drag)
                    pan: {
                        enabled: true,
                        mode: 'xy',
                        modifierKey: null,
                        threshold: 5,
                        onPan: ({chart}) => {
                            // Prevent panning into negative Y territory
                            const y = chart.scales.y;
                            if (y.min < 0) {
                                y.options.min = 0;
                                if (y.max <= 0) y.options.max = 0.5;
                                chart.update('none');
                            }
                        }
                    },
                    // Zoom (wheel, pinch, drag selection)
                    zoom: {
                        wheel: { enabled: true },
                        pinch: { enabled: true },
                        drag: { enabled: false }, // keep disabled to favor pan on drag
                        mode: 'xy',
                        onZoom: ({chart}) => {
                            const y = chart.scales.y;
                            if (y.min < 0) {
                                y.options.min = 0;
                                if (y.max <= 0) y.options.max = 0.5;
                                chart.update('none');
                            }
                        }
                    },
                    // Enforce hard limits
                    limits: {
                        y: { min: 0 },
                        x: { min: 0 }
                    }
                }
            },
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    title: {
                        display: true,
                        text: translate('time')
                    },
                    beginAtZero: true,
                    ticks: {
                        callback: (val) => val.toFixed(2)
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: translate('delay')
                    },
                    min: minYAxis,
                    max: maxYAxis,
                    beginAtZero: true,
                    ticks: {
                        callback: (val) => val.toFixed(3)
                    }
                }
            }
        }
    });

    // Fallback manual panning if plugin pan is somehow blocked (e.g. overlay issues)
    (function attachManualPan(chart){
        const canvasEl = chart.canvas;
        if (!canvasEl) return;
        let isDragging = false;
        let startX = 0, startY = 0;
        let startXMin, startXMax, startYMin, startYMax;
        const getPos = evt => {
            if (evt.touches && evt.touches.length) {
                return {x: evt.touches[0].clientX, y: evt.touches[0].clientY};
            }
            return {x: evt.clientX, y: evt.clientY};
        };
        const down = (evt) => {
            if (evt.button !== undefined && evt.button !== 0) return; // left only
            isDragging = true;
            const pos = getPos(evt);
            startX = pos.x; startY = pos.y;
            const x = chart.scales.x; const y = chart.scales.y;
            startXMin = x.min; startXMax = x.max; startYMin = y.min; startYMax = y.max;
        };
        const move = (evt) => {
            if (!isDragging) return;
            const pos = getPos(evt);
            const dx = pos.x - startX;
            const dy = pos.y - startY;
            const x = chart.scales.x; const y = chart.scales.y;
            const xRange = startXMax - startXMin;
            const yRange = startYMax - startYMin;
            const pixelsPerX = chart.chartArea.width / xRange;
            const pixelsPerY = chart.chartArea.height / yRange;
            const shiftX = dx / pixelsPerX;
            const shiftY = dy / pixelsPerY;
            // Apply (invert Y due to screen coords)
            x.options.min = Math.max(0, startXMin - shiftX);
            x.options.max = x.options.min + xRange;
            const newYMin = Math.max(0, startYMin + shiftY); // dragging down increases y
            y.options.min = newYMin;
            y.options.max = newYMin + yRange;
            chart.update('none');
        };
        const up = () => { isDragging = false; };
        canvasEl.addEventListener('mousedown', down);
        window.addEventListener('mousemove', move);
        window.addEventListener('mouseup', up);
        canvasEl.addEventListener('touchstart', down, {passive:true});
        canvasEl.addEventListener('touchmove', move, {passive:true});
        canvasEl.addEventListener('touchend', up);
    })(summaryChart);

    // Add event listener for the reset zoom button
    const resetZoomButton = document.getElementById('reset_zoom_button');
    if (resetZoomButton && summaryChart) {
        // Remove previous listeners by cloning
        resetZoomButton.replaceWith(resetZoomButton.cloneNode(true));
        const newResetButton = document.getElementById('reset_zoom_button');
        newResetButton.addEventListener('click', () => {
            summaryChart.resetZoom();
        });
    } else {
        if (!resetZoomButton) console.warn("Reset zoom button (reset_zoom_button) not found in the DOM.");
        // summaryChart might not be initialized if canvas wasn't found, which is handled earlier
    }

    // Add resize event listener to redraw chart on window resize
    // Remove previous resize listener if it exists
    if (window.__sessionSummaryResizeHandler) {
        window.removeEventListener('resize', window.__sessionSummaryResizeHandler);
    }
    window.__sessionSummaryResizeHandler = () => {
        if (summaryChart) {
            summaryChart.resize();
        }
    };
    window.addEventListener('resize', window.__sessionSummaryResizeHandler);

    // Show the inline section
    summaryWindow.classList.remove('hidden');
    
    // Initialize toggle button
    initSessionSummaryToggle();
    
    // Load and apply saved collapse state from cookie
    const collapsedState = (typeof getCookie === 'function') ? getCookie('session_summary_collapsed') : null;
    const shouldBeCollapsed = collapsedState === '1';
    
    // Initialize collapse state (default to expanded if no cookie)
    if (shouldBeCollapsed) {
        collapseSessionSummary();
    } else {
        expandSessionSummary();
    }
}
window.handleSessionSummary = handleSessionSummary;

// --- Session Summary Collapse/Expand Functions ---
function collapseSessionSummary() {
    const summaryContent = document.getElementById('session_summary_content');
    const arrow = document.getElementById('session_summary_arrow');
    
    if (summaryContent && arrow) {
        // Get the actual content height before collapsing
        const contentHeight = summaryContent.scrollHeight;
        // Set current height explicitly for smooth transition
        summaryContent.style.maxHeight = contentHeight + 'px';
        // Force reflow
        summaryContent.offsetHeight;
        // Now animate to 0
        requestAnimationFrame(() => {
            summaryContent.style.maxHeight = '0';
        });
        arrow.classList.remove('rotate-180');
        arrow.classList.add('rotate-0');
    }
}

function expandSessionSummary() {
    const summaryContent = document.getElementById('session_summary_content');
    const arrow = document.getElementById('session_summary_arrow');
    
    if (summaryContent && arrow) {
        // Check if already expanded (has rotate-180 class)
        const isAlreadyExpanded = arrow.classList.contains('rotate-180');
        
        if (!isAlreadyExpanded) {
            // Get the actual content height (temporarily remove max-height restriction)
            const currentMaxHeight = summaryContent.style.maxHeight;
            summaryContent.style.maxHeight = 'none';
            const contentHeight = summaryContent.scrollHeight;
            summaryContent.style.maxHeight = currentMaxHeight;
            
            // Force reflow
            summaryContent.offsetHeight;
            // Now animate to full height
            requestAnimationFrame(() => {
                summaryContent.style.maxHeight = Math.max(contentHeight, 500) + 'px';
                // Resize chart after expansion animation completes
                setTimeout(() => {
                    if (summaryChart) {
                        summaryChart.resize();
                    }
                }, 350); // Slightly longer than transition duration (300ms)
            });
        } else {
            // Already expanded, just ensure max-height is set properly
            const contentHeight = summaryContent.scrollHeight;
            summaryContent.style.maxHeight = Math.max(contentHeight, 500) + 'px';
            // Resize chart if needed
            if (summaryChart) {
                summaryChart.resize();
            }
        }
        arrow.classList.remove('rotate-0');
        arrow.classList.add('rotate-180');
    }
}

function toggleSessionSummary() {
    const summaryContent = document.getElementById('session_summary_content');
    const arrow = document.getElementById('session_summary_arrow');
    
    if (!summaryContent || !arrow) return;
    
    const isCollapsed = arrow.classList.contains('rotate-0');
    
    if (isCollapsed) {
        expandSessionSummary();
        // Save state: expanded (0)
        if (typeof setCookie === 'function') {
            setCookie('session_summary_collapsed', '0', 365);
        }
    } else {
        collapseSessionSummary();
        // Save state: collapsed (1)
        if (typeof setCookie === 'function') {
            setCookie('session_summary_collapsed', '1', 365);
        }
    }
}

// Initialize collapse toggle button event listener
function initSessionSummaryToggle() {
    const toggleButton = document.getElementById('session_summary_toggle');
    if (toggleButton) {
        // Remove previous listeners by cloning
        toggleButton.replaceWith(toggleButton.cloneNode(true));
        const newToggleButton = document.getElementById('session_summary_toggle');
        newToggleButton.addEventListener('click', toggleSessionSummary);
    }
}

// --- Initialize persisted preferences for Songs page toggles ---
function initSongPagePreferences() {
    try {
        // Read cookie preferences (default to enabled if not set)
        const summaryPref = (typeof getCookie === 'function') ? getCookie('show_summary_popup') : null;
        const scorePref = (typeof getCookie === 'function') ? getCookie('show_score') : null;

        // Apply to summary checkbox if present
        const summaryEl = document.getElementById('show_summary_popup');
        if (summaryEl && summaryPref !== null) {
            summaryEl.checked = (summaryPref === '1');
        }

        // Apply to score checkbox if present and sync the score display visibility
        const scoreEl = document.getElementById('show_score_checkbox');
        const scoreDisplay = document.getElementById('score_display');
        if (scoreEl) {
            if (scorePref !== null) {
                scoreEl.checked = (scorePref === '1');
            }
            if (scoreDisplay) {
                scoreDisplay.classList.toggle('hidden', !scoreEl.checked);
            }
        }
    } catch (e) {
        // Fail silently; preferences will remain default
    }
}

// Run once after DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSongPagePreferences);
} else {
    initSongPagePreferences();
}

// Observe dynamic injections (e.g., when songs.html content is loaded via AJAX)
const __songsPrefsObserver = new MutationObserver(() => {
    const hasTargets = document.getElementById('show_score_checkbox') || document.getElementById('show_summary_popup');
    if (hasTargets) {
        initSongPagePreferences();
    }
});
try {
    __songsPrefsObserver.observe(document.body || document.documentElement, { childList: true, subtree: true });
} catch (e) {
    // ignore
}

// --- Practice mode dependent UI (score & summary visibility) ---
// Hide score display and session summary popup when practice mode is not Melody (value '0').
function updatePracticeModeUI() {
    try {
        const practiceSelect = document.getElementById('practice');
        const scoreDisplay = document.getElementById('score_display');
        const summaryWindow = document.getElementById('session_summary_window');
        const toggleWrapper = document.getElementById('score_summary_toggle_wrapper');
        if (!practiceSelect || !scoreDisplay) return; // Not on page yet
        if (practiceSelect.value === '0') { // Melody
            // Only show if user preference isn't hiding it
            const scoreCheckbox = document.getElementById('show_score_checkbox');
            const showScore = !scoreCheckbox || scoreCheckbox.checked;
            if (showScore) scoreDisplay.classList.remove('hidden');
            if (toggleWrapper) toggleWrapper.classList.remove('hidden');
        } else {
            scoreDisplay.classList.add('hidden');
            if (summaryWindow) summaryWindow.classList.add('hidden');
            if (toggleWrapper) toggleWrapper.classList.add('hidden');
        }
    } catch (e) { /* no-op */ }
}
window.updatePracticeModeUI = updatePracticeModeUI;

// Listen for practice mode changes
document.addEventListener('change', function (e) {
    if (e.target && e.target.id === 'practice') {
        updatePracticeModeUI();
    }
});

// Initial invocation when DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updatePracticeModeUI);
} else {
    updatePracticeModeUI();
}

// Wrap session summary handler to respect practice mode
(function(){
    try {
        if (window.handleSessionSummary && !window.__wrappedHandleSessionSummary) {
            const original = window.handleSessionSummary;
            window.handleSessionSummary = function(data, retries) {
                const practiceSelect = document.getElementById('practice');
                if (practiceSelect && practiceSelect.value !== '0') {
                    const summaryWindow = document.getElementById('session_summary_window');
                    if (summaryWindow) summaryWindow.classList.add('hidden');
                    return; // Skip showing summary
                }
                return original.call(this, data, retries);
            };
            window.__wrappedHandleSessionSummary = true;
        }
        if (window.handleScoreUpdate && !window.__wrappedHandleScoreUpdate) {
            const originalScore = window.handleScoreUpdate;
            window.handleScoreUpdate = function(data) {
                const practiceSelect = document.getElementById('practice');
                if (practiceSelect && practiceSelect.value !== '0') {
                    const scoreDisplay = document.getElementById('score_display');
                    if (scoreDisplay) scoreDisplay.classList.add('hidden');
                    return; // Suppress score updates visually
                }
                return originalScore.call(this, data);
            };
            window.__wrappedHandleScoreUpdate = true;
        }
    } catch (e) { /* no-op */ }
})();

