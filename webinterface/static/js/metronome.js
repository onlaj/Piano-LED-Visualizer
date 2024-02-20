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