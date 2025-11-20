function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : null;
}

function rgbToHex(r, g, b) {
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
}

/*
const rgbToHex = (r, g, b) => '#' + [r, g, b].map(x => {
    const hex = x.toString(16)
    return hex.length === 1 ? '0' + hex : hex
}).join('');
*/

const rgbToHexA = (a) => '#' + [~~a[0], ~~a[1], ~~a[2]].map(x => {
    const hex = x.toString(16)
    return hex.length === 1 ? '0' + hex : hex
}).join('');

function enforceMinMax(el) {
    if (el.value !== "") {
        if (parseInt(el.value) < parseInt(el.min)) {
            el.value = el.min;
        }
        if (parseInt(el.value) > parseInt(el.max)) {
            el.value = el.max;
        }
    }
}

function formatBytes(bytes, decimals = 2, suffix = true) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];

    const i = Math.floor(Math.log(bytes) / Math.log(k));
    if (suffix === true) {
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    } else {
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm));
    }
}

function animateValue(obj, start, end, duration, format = false) {
    if (!obj) return;
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        if (format) {
            obj.innerHTML = formatBytes(Math.floor(progress * (end - start) + start));
        } else {
            obj.innerHTML = Math.floor(progress * (end - start) + start);
        }
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}



function calculate_rainbow(x) {
    let red, green, blue;
    x = x % 255;
    let y = x % 85;
    const t1 = y * 3;
    const t2 = 255 - (y * 3);

    if (x < 85) return rgbToHex(t2, t1, 0);
    else if (x < 170) return rgbToHex(0, t2, t1);
    else return rgbToHex(t1, 0, t2);
}

/**
 * Converts an HSV color value to RGB. Conversion formula
 * adapted from http://en.wikipedia.org/wiki/HSV_color_space.
 * Assumes h, s, and v are contained in the set [0, 1] and
 * returns r, g, and b in the set [0, 255].
 *
 * @param   Number  h       The hue
 * @param   Number  s       The saturation
 * @param   Number  v       The value
 * @return  Array           The RGB representation
 */
function hsvToRgb(h, s, v) {
    let r, g, b;

    const i = Math.floor(h * 6);
    const f = h * 6 - i;
    const p = v * (1 - s);
    const q = v * (1 - f * s);
    const t = v * (1 - (1 - f) * s);

    switch (i % 6) {
        case 0:
            r = v, g = t, b = p;
            break;
        case 1:
            r = q, g = v, b = p;
            break;
        case 2:
            r = p, g = v, b = t;
            break;
        case 3:
            r = p, g = q, b = v;
            break;
        case 4:
            r = t, g = p, b = v;
            break;
        case 5:
            r = v, g = p, b = q;
            break;
    }

    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

function powercurve(x, p) {
    if (p === 0) return x;
    return (Math.exp(-p * x) - 1) / (Math.exp(-p) - 1);
}

let recordingTimer = null;
let recordingStartTime = 0;

function formatTime(timeInSeconds) {
    const hours = Math.floor(timeInSeconds / 3600);
    const minutes = Math.floor((timeInSeconds % 3600) / 60);
    const seconds = Math.floor(timeInSeconds % 60);

    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

function startRecordingTimer() {
    const timerElement = document.getElementById('recording_timer');
    timerElement.classList.remove('hidden');
    recordingStartTime = Date.now();

    recordingTimer = setInterval(() => {
        const currentTime = Math.floor((Date.now() - recordingStartTime) / 1000);
        timerElement.querySelector('span').textContent = formatTime(currentTime);
    }, 1000);
}

function stopRecordingTimer() {
    if (recordingTimer) {
        clearInterval(recordingTimer);
        recordingTimer = null;
    }
}

function hideRecordingTimer() {
    stopRecordingTimer();
    const timerElement = document.getElementById('recording_timer');
    timerElement.classList.add('hidden');
}
