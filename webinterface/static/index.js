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
                document.getElementById(subpage).classList.add("glass-light");
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
                        if(typeof get_presets === 'function') {
                            get_presets();
                        }
                        break;
                    case "ledanimations":
                        get_led_idle_animation_settings();
                        clearInterval(homepage_interval);
                        populate_colormaps(["colormap_anim_id"]);
                        // Start time update for schedule card (will be started by get_led_idle_animation_settings callback)
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
                        initialize_port_connection_manager();
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



function start_led_animation(name, param) {
    const xhttp = new XMLHttpRequest();
    let url = "/api/start_animation?name=" + name;
    if (param !== null && param !== undefined) {
        url += "&param=" + encodeURIComponent(param);
    }
    xhttp.open("GET", url, true);
    xhttp.send();
}

function handleDisplayTypeChange(value, selectElement) {
    // Get the previous value (the one that was selected before this change)
    const previousValue = value === '1in44' ? '1in3' : '1in44';
    const storedPrevious = selectElement.getAttribute('data-current-value');
    const actualPrevious = storedPrevious || previousValue;
    
    // Show confirmation dialog with translation
    const displayName = value === '1in44' ? '1.44 inch' : '1.3 inch';
    const confirmMessage = translate('lcd_type_change_confirm').replace('{0}', displayName);
    
    showConfirm(confirmMessage, function() {
        // Store the value we're changing to as current for next time
        selectElement.setAttribute('data-current-value', value);
        
        // Show loading state
        selectElement.disabled = true;
        selectElement.style.opacity = '0.6';
        
        // Call change_setting API
        const xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function () {
            if (this.readyState === 4 && this.status === 200) {
                const response = JSON.parse(this.responseText);
                if (response.success === true) {
                    // Show success message with translation
                    showAlert(translate('lcd_type_change_success'), 'info');
                    // Reload page after delay to allow visualizer to restart (30 seconds)
                    setTimeout(function() {
                        window.location.reload();
                    }, 30000);
                } else {
                    // Revert on error
                    selectElement.value = actualPrevious;
                    selectElement.setAttribute('data-current-value', actualPrevious);
                    selectElement.disabled = false;
                    selectElement.style.opacity = '1';
                    const errorMsg = translate('lcd_type_change_error').replace('{0}', response.error || 'Unknown error');
                    showAlert(errorMsg, 'error');
                }
            } else if (this.readyState === 4) {
                // Revert on error
                selectElement.value = actualPrevious;
                selectElement.setAttribute('data-current-value', actualPrevious);
                selectElement.disabled = false;
                selectElement.style.opacity = '1';
                const errorMsg = translate('lcd_type_change_error').replace('{0}', 'Please try again.');
                showAlert(errorMsg, 'error');
            }
        };
        xhttp.open("GET", "/api/change_setting?setting_name=display_type&value=" + value, true);
        xhttp.send();
    }, function() {
        // Revert to previous value if cancelled
        selectElement.value = actualPrevious;
        selectElement.setAttribute('data-current-value', actualPrevious);
    });
}

function handleLedPinChange(value, selectElement) {
    // Get the previous value (the one that was selected before this change)
    const validPins = ['12', '13', '18', '19'];
    const storedPrevious = selectElement.getAttribute('data-current-value');
    const actualPrevious = storedPrevious || '18';
    
    // Show confirmation dialog with translation
    const confirmMessage = translate('led_pin_change_confirm').replace('{0}', value);
    
    showConfirm(confirmMessage, function() {
        // Store the value we're changing to as current for next time
        selectElement.setAttribute('data-current-value', value);
        
        // Show loading state
        selectElement.disabled = true;
        selectElement.style.opacity = '0.6';
        
        // Call change_setting API
        const xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function () {
            if (this.readyState === 4 && this.status === 200) {
                const response = JSON.parse(this.responseText);
                if (response.success === true) {
                    // Show success message with translation
                    showAlert(translate('led_pin_change_success'), 'info');
                    // Reload page after delay to allow visualizer to restart (30 seconds)
                    setTimeout(function() {
                        window.location.reload();
                    }, 30000);
                } else {
                    // Revert on error
                    selectElement.value = actualPrevious;
                    selectElement.setAttribute('data-current-value', actualPrevious);
                    selectElement.disabled = false;
                    selectElement.style.opacity = '1';
                    const errorMsg = translate('led_pin_change_error').replace('{0}', response.error || 'Unknown error');
                    showAlert(errorMsg, 'error');
                }
            } else if (this.readyState === 4) {
                // Revert on error
                selectElement.value = actualPrevious;
                selectElement.setAttribute('data-current-value', actualPrevious);
                selectElement.disabled = false;
                selectElement.style.opacity = '1';
                const errorMsg = translate('led_pin_change_error').replace('{0}', 'Please try again.');
                showAlert(errorMsg, 'error');
            }
        };
        xhttp.open("GET", "/api/change_setting?setting_name=led_pin&value=" + value, true);
        xhttp.send();
    }, function() {
        // Revert to previous value if cancelled
        selectElement.value = actualPrevious;
        selectElement.setAttribute('data-current-value', actualPrevious);
    });
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
        start_led_animation('stop', null);
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

    // Update secondary stats grid columns based on advanced mode
    const secondaryStatsGrid = document.getElementById('secondary_stats_grid');
    if (secondaryStatsGrid) {
        if (advancedMode) {
            secondaryStatsGrid.className = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-6';
        } else {
            secondaryStatsGrid.className = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-6';
        }
    }

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
        } else {
            setAdvancedMode(false);
        }
    } else {
        // Default to normal mode if no cookie exists
        setAdvancedMode(false);
    }
}

// ========== Port Connection Manager ==========

let portConnectionState = {
    selectedSource: null,
    availablePorts: { inputs: [], outputs: [], all: [] },
    connections: [],
    portElements: new Map(),
    connectionColors: [
        '#3b82f6', // blue
        '#10b981', // green
        '#f59e0b', // amber
        '#ef4444', // red
        '#8b5cf6', // violet
        '#ec4899', // pink
        '#14b8a6', // teal
        '#f97316', // orange
        '#06b6d4', // cyan
        '#84cc16', // lime
    ]
};

function initialize_port_connection_manager() {
    refresh_port_connections();
}

function refresh_all_ports() {
    // Refresh both visual manager and raw output
    refresh_port_connections();
    get_ports();
}

function toggle_raw_output() {
    const container = document.getElementById('raw-output-container');
    const arrow = document.getElementById('raw-output-arrow');
    const button = event.currentTarget.querySelector('span');
    
    if (container.classList.contains('hidden')) {
        container.classList.remove('hidden');
        arrow.classList.add('rotate-180');
        button.textContent = 'Hide Raw Port List (aconnect -l)';
    } else {
        container.classList.add('hidden');
        arrow.classList.remove('rotate-180');
        button.textContent = 'Show Raw Port List (aconnect -l)';
    }
}

function connect_all_ports_action() {
    change_setting('connect_ports', '0');
    temporary_disable_button(event.currentTarget, 5000);
    // Refresh after connection
    setTimeout(() => {
        refresh_all_ports();
    }, 1000);
}

function disconnect_all_ports_action() {
    change_setting('disconnect_ports', '0');
    temporary_disable_button(event.currentTarget, 1500);
    // Refresh after disconnection
    setTimeout(() => {
        refresh_all_ports();
    }, 500);
}

function refresh_port_connections() {
    fetch('/api/get_available_ports')
        .then(response => response.json())
        .then(ports => {
            portConnectionState.availablePorts = ports;
            return fetch('/api/get_port_connections');
        })
        .then(response => response.json())
        .then(data => {
            portConnectionState.connections = data.connections || [];
            render_port_connection_interface();
        })
        .catch(error => {
            console.error('Error loading port connections:', error);
        });
}

function render_port_connection_interface() {
    const sourceList = document.getElementById('source-ports-list');
    const destList = document.getElementById('destination-ports-list');
    
    if (!sourceList || !destList) return;
    
    // Clear existing content
    sourceList.innerHTML = '';
    destList.innerHTML = '';
    portConnectionState.portElements.clear();
    
    // Render source ports (all available ports)
    portConnectionState.availablePorts.all.forEach(port => {
        const portEl = create_port_element(port, 'source');
        sourceList.appendChild(portEl);
        portConnectionState.portElements.set(`source-${port.id}`, portEl);
    });
    
    // Render destination ports (all available ports)
    portConnectionState.availablePorts.all.forEach(port => {
        const portEl = create_port_element(port, 'destination');
        destList.appendChild(portEl);
        portConnectionState.portElements.set(`dest-${port.id}`, portEl);
    });
    
    // Draw connection lines
    setTimeout(() => draw_connection_lines(), 100);
}

function create_port_element(port, type) {
    const div = document.createElement('div');
    div.className = 'port-item relative glass-light p-3 rounded-glass cursor-pointer hover:glass transition-smooth-fast';
    div.dataset.portId = port.id;
    div.dataset.portType = type;
    div.title = port.full_name;
    
    // Port name
    const nameSpan = document.createElement('div');
    nameSpan.className = 'text-sm font-semibold truncate';
    nameSpan.textContent = port.client_name;
    
    const portSpan = document.createElement('div');
    portSpan.className = 'text-xs text-gray-600 dark:text-gray-400 truncate';
    portSpan.textContent = port.name;
    
    div.appendChild(nameSpan);
    div.appendChild(portSpan);
    
    // Add connection information for mobile
    const connectionsDiv = document.createElement('div');
    connectionsDiv.className = 'port-connections-mobile hidden mt-2';
    connectionsDiv.dataset.portId = port.id;
    div.appendChild(connectionsDiv);
    
    // Add connection point indicator
    const connectionDot = document.createElement('div');
    connectionDot.className = 'connection-dot';
    if (type === 'source') {
        connectionDot.className += ' right-0';
    } else {
        connectionDot.className += ' left-0';
    }
    div.appendChild(connectionDot);
    
    // Add click handler
    div.addEventListener('click', () => handle_port_click(port, type));
    
    return div;
}

function handle_port_click(port, type) {
    if (type === 'source') {
        // Select sender port
        portConnectionState.selectedSource = port;
        update_port_selection_ui();
        update_connection_status(`<strong>${translate('sender_selected')}</strong> ${port.full_name}<br><small>${translate('click_receiver_to_connect')}</small>`);
    } else {
        // Receiver port clicked
        if (portConnectionState.selectedSource) {
            // Prevent self-connection
            if (portConnectionState.selectedSource.id === port.id) {
                update_connection_status(`❌ <strong>${translate('cannot_connect_to_self')}</strong><br><small>${translate('select_different_receiver')}</small>`);
                return;
            }
            
            // Check if connection already exists
            const existingConn = portConnectionState.connections.find(
                c => c.source === portConnectionState.selectedSource.id && c.destination === port.id
            );
            
            if (existingConn) {
                // Delete existing connection
                delete_port_connection(portConnectionState.selectedSource.id, port.id);
            } else {
                // Create new connection
                create_port_connection(portConnectionState.selectedSource.id, port.id);
            }
            
            portConnectionState.selectedSource = null;
            update_port_selection_ui();
        } else {
            update_connection_status(`<small>⚠️ ${translate('select_sender_first')}</small>`);
        }
    }
}

function create_port_connection(source, destination) {
    fetch('/api/create_port_connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, destination })
    })
    .then(response => response.json())
        .then(data => {
            if (data.success) {
                update_connection_status(`✅ <strong>${translate('connection_created')}</strong> ${translate('connection_data_flow')}`);
                refresh_all_ports();
            } else {
                const errorMsg = data.error || translate('connection_create_failed');
                update_connection_status(`❌ <strong>${errorMsg}</strong>`);
            }
        })
        .catch(error => {
            console.error('Error creating connection:', error);
            update_connection_status(`❌ ${translate('connection_create_failed')}`);
        });
}

function delete_port_connection(source, destination) {
    fetch('/api/delete_port_connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, destination })
    })
    .then(response => response.json())
        .then(data => {
            if (data.success) {
                update_connection_status(`✅ <strong>${translate('connection_deleted')}</strong>`);
                refresh_all_ports();
            } else {
                update_connection_status(`❌ <strong>${translate('connection_delete_failed')}</strong>`);
            }
        })
        .catch(error => {
            console.error('Error deleting connection:', error);
            update_connection_status(`❌ ${translate('connection_delete_failed')}`);
        });
}

function update_port_selection_ui() {
    // Remove previous selection highlights
    document.querySelectorAll('.port-item').forEach(el => {
        el.classList.remove('port-selected');
    });
    
    // Highlight selected source
    if (portConnectionState.selectedSource) {
        const sourceEl = portConnectionState.portElements.get(`source-${portConnectionState.selectedSource.id}`);
        if (sourceEl) {
            sourceEl.classList.add('port-selected');
        }
    }
}

function update_connection_status(message) {
    const statusEl = document.getElementById('connection-status');
    if (statusEl) {
        statusEl.innerHTML = `
            <div class="flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>${message}</span>
            </div>
        `;
    }
}

function draw_connection_lines() {
    const svg = document.getElementById('connection-lines');
    if (!svg) return;
    
    // Clear existing lines
    svg.innerHTML = '';
    
    // Create SVG defs with arrowhead markers for each color
    let defsHTML = '<defs>';
    portConnectionState.connectionColors.forEach((color, index) => {
        defsHTML += `
            <marker id="arrowhead-${index}" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
                <polygon points="0 0, 10 3, 0 6" fill="${color}" />
            </marker>
            <marker id="arrowhead-${index}-hover" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
                <polygon points="0 0, 10 3, 0 6" fill="#ef4444" />
            </marker>
        `;
    });
    defsHTML += '</defs>';
    svg.innerHTML = defsHTML;
    
    const container = document.getElementById('port-connection-container');
    if (!container) return;
    
    // Draw lines for each connection with different colors
    portConnectionState.connections.forEach((conn, index) => {
        const sourceEl = portConnectionState.portElements.get(`source-${conn.source}`);
        const destEl = portConnectionState.portElements.get(`dest-${conn.destination}`);
        
        if (sourceEl && destEl) {
            const colorIndex = index % portConnectionState.connectionColors.length;
            const line = create_connection_line(sourceEl, destEl, container, conn, colorIndex);
            svg.appendChild(line);
        }
    });
    
    // Update mobile connection displays
    update_mobile_connections();
}

function update_mobile_connections() {
    // Clear all existing mobile connection info
    document.querySelectorAll('.port-connections-mobile').forEach(el => {
        el.innerHTML = '';
        el.classList.add('hidden');
    });
    
    // Group connections by source and destination
    const sourceConnections = {};
    const destConnections = {};
    
    portConnectionState.connections.forEach(conn => {
        if (!sourceConnections[conn.source]) {
            sourceConnections[conn.source] = [];
        }
        sourceConnections[conn.source].push(conn.destination);
        
        if (!destConnections[conn.destination]) {
            destConnections[conn.destination] = [];
        }
        destConnections[conn.destination].push(conn.source);
    });
    
    // Update sender ports with their connections
    Object.keys(sourceConnections).forEach(sourceId => {
        const connections = sourceConnections[sourceId];
        const sourceEl = portConnectionState.portElements.get(`source-${sourceId}`);
        if (sourceEl) {
            const mobileDiv = sourceEl.querySelector('.port-connections-mobile');
            if (mobileDiv && connections.length > 0) {
                mobileDiv.classList.remove('hidden');
                mobileDiv.innerHTML = `
                    <div class="text-xs border-t border-gray-400 dark:border-gray-500 pt-2 mt-1">
                        <div class="flex items-center gap-1 text-gray-600 dark:text-gray-400 mb-1">
                            <svg xmlns="http://www.w3.org/2000/svg" style="width: 15px; height: 15px; flex-shrink: 0;" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                            </svg>
                            <span class="font-semibold">${translate('sending_to')}</span>
                        </div>
                        ${connections.map(destId => {
                            const destPort = portConnectionState.availablePorts.all.find(p => p.id === destId);
                            return destPort ? `<div class="ml-4 text-blue-600 dark:text-blue-400">→ ${destPort.client_name}</div>` : '';
                        }).join('')}
                    </div>
                `;
            }
        }
    });
    
    // Update receiver ports with their connections
    Object.keys(destConnections).forEach(destId => {
        const connections = destConnections[destId];
        const destEl = portConnectionState.portElements.get(`dest-${destId}`);
        if (destEl) {
            const mobileDiv = destEl.querySelector('.port-connections-mobile');
            if (mobileDiv && connections.length > 0) {
                mobileDiv.classList.remove('hidden');
                mobileDiv.innerHTML = `
                    <div class="text-xs border-t border-gray-400 dark:border-gray-500 pt-2 mt-1">
                        <div class="flex items-center gap-1 text-gray-600 dark:text-gray-400 mb-1">
                            <svg xmlns="http://www.w3.org/2000/svg" style="width: 15px; height: 15px; flex-shrink: 0;" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16l-4-4m0 0l4-4m-4 4h18" />
                            </svg>
                            <span class="font-semibold">${translate('receiving_from')}</span>
                        </div>
                        ${connections.map(sourceId => {
                            const sourcePort = portConnectionState.availablePorts.all.find(p => p.id === sourceId);
                            return sourcePort ? `<div class="ml-4 text-green-600 dark:text-green-400">← ${sourcePort.client_name}</div>` : '';
                        }).join('')}
                    </div>
                `;
            }
        }
    });
}

function create_connection_line(sourceEl, destEl, container, connection, colorIndex) {
    const containerRect = container.getBoundingClientRect();
    const sourceRect = sourceEl.getBoundingClientRect();
    const destRect = destEl.getBoundingClientRect();
    
    // Calculate line coordinates relative to container
    const x1 = sourceRect.right - containerRect.left;
    const y1 = sourceRect.top + sourceRect.height / 2 - containerRect.top;
    const x2 = destRect.left - containerRect.left;
    const y2 = destRect.top + destRect.height / 2 - containerRect.top;
    
    // Get color for this connection
    const color = portConnectionState.connectionColors[colorIndex];
    
    // Create SVG line with curve and arrowhead
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const midX = (x1 + x2) / 2;
    const d = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;
    
    path.setAttribute('d', d);
    path.setAttribute('stroke', color);
    path.setAttribute('stroke-width', '2.5');
    path.setAttribute('fill', 'none');
    path.setAttribute('class', 'connection-line');
    path.setAttribute('marker-end', `url(#arrowhead-${colorIndex})`);
    path.dataset.colorIndex = colorIndex;
    path.style.pointerEvents = 'auto';
    path.style.cursor = 'pointer';
    
    // Add title tooltip
    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = `${connection.source} → ${connection.destination} (click to delete)`;
    path.appendChild(title);
    
    // Add click handler to delete connection
    path.addEventListener('click', () => {
        showConfirm(`Delete connection:\n${connection.source} → ${connection.destination}\n\nThis will stop data flow from sender to receiver.`, function() {
            delete_port_connection(connection.source, connection.destination);
        });
    });
    
    // Add hover effect
    path.addEventListener('mouseenter', () => {
        path.setAttribute('stroke', '#ef4444');
        path.setAttribute('stroke-width', '3.5');
        path.setAttribute('marker-end', `url(#arrowhead-${colorIndex}-hover)`);
    });
    
    path.addEventListener('mouseleave', () => {
        path.setAttribute('stroke', color);
        path.setAttribute('stroke-width', '2.5');
        path.setAttribute('marker-end', `url(#arrowhead-${colorIndex})`);
    });
    
    return path;
}

// Redraw lines on window resize
window.addEventListener('resize', () => {
    if (document.getElementById('port-connection-container')) {
        draw_connection_lines();
    }
});
