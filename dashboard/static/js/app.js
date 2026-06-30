/* dashboard/static/js/app.js */
document.addEventListener("DOMContentLoaded", () => {
    const socket = io();

    // DOM Elements
    const connStatus = document.getElementById('conn-status');
    const armStatus = document.getElementById('arm-status');
    const modeStatus = document.getElementById('mode-status');
    
    const countPerson = document.getElementById('count-person');
    const countTriangle = document.getElementById('count-triangle');
    const countSquare = document.getElementById('count-square');
    const countRectangle = document.getElementById('count-rectangle');
    const countTotal = document.getElementById('count-total');

    const telAlt = document.getElementById('tel-alt');
    const telSpeed = document.getElementById('tel-speed');
    const telGps = document.getElementById('tel-gps');
    const telHdg = document.getElementById('tel-hdg');
    const telBat = document.getElementById('tel-bat');

    const wpText = document.getElementById('wp-text');
    const progressFill = document.getElementById('progress-fill');
    
    const eventLog = document.getElementById('event-log');

    // Helper to add log entries
    function addLog(msg, type='info') {
        const div = document.createElement('div');
        div.className = `log-item ${type}`;
        const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: "numeric", minute: "numeric", second: "numeric" });
        div.textContent = `[${time}] ${msg}`;
        eventLog.appendChild(div);
        eventLog.scrollTop = eventLog.scrollHeight;
        
        // Keep only last 50 logs
        while (eventLog.children.length > 50) {
            eventLog.removeChild(eventLog.firstChild);
        }
    }

    // Connection events
    socket.on('connect', () => {
        connStatus.textContent = 'CONNECTED';
        connStatus.className = 'status badge-success';
        addLog('WebSocket connected to backend');
    });

    socket.on('disconnect', () => {
        connStatus.textContent = 'DISCONNECTED';
        connStatus.className = 'status badge-danger';
        addLog('WebSocket disconnected', 'error');
    });

    // Telemetry updates
    socket.on('telemetry_update', (data) => {
        if(data.alt !== undefined) telAlt.textContent = data.alt.toFixed(1) + ' m';
        if(data.speed !== undefined) telSpeed.textContent = data.speed.toFixed(1) + ' m/s';
        if(data.lat !== undefined && data.lon !== undefined) {
            telGps.textContent = `${data.lat.toFixed(6)}, ${data.lon.toFixed(6)}`;
        }
        if(data.heading !== undefined) telHdg.textContent = data.heading + ' °';
        if(data.battery_v !== undefined && data.battery_pct !== undefined) {
            telBat.textContent = `${data.battery_v.toFixed(1)}V (${data.battery_pct}%)`;
        }

        if(data.armed !== undefined) {
            if(data.armed) {
                armStatus.textContent = 'ARMED';
                armStatus.className = 'status badge-danger';
            } else {
                armStatus.textContent = 'DISARMED';
                armStatus.className = 'status badge-success';
            }
        }

        if(data.mode !== undefined) {
            modeStatus.textContent = data.mode;
        }

        if(data.wp_current !== undefined && data.wp_total !== undefined) {
            wpText.textContent = `WP: ${data.wp_current}/${data.wp_total}`;
            const pct = data.wp_total > 0 ? (data.wp_current / data.wp_total) * 100 : 0;
            progressFill.style.width = `${pct}%`;
        }
    });

    // Detection updates
    let lastCounts = {};
    socket.on('detection_update', (data) => {
        // data.counts is a dict e.g. {"person": 5, "triangle": 1}
        const counts = data.counts || {};
        
        countPerson.textContent = counts['person'] || 0;
        countTriangle.textContent = counts['triangle'] || 0;
        countSquare.textContent = counts['square'] || 0;
        countRectangle.textContent = counts['rectangle'] || 0;
        
        let total = 0;
        for (const val of Object.values(counts)) {
            total += val;
        }
        countTotal.textContent = total;

        // Log newly found items
        for (const [cls, count] of Object.entries(counts)) {
            const last = lastCounts[cls] || 0;
            if (count > last) {
                // simple diff logging
                addLog(`Detected new ${cls} (Total: ${count})`, 'detect');
            }
        }
        lastCounts = {...counts};
    });

    // Buttons
    document.getElementById('btn-start').addEventListener('click', () => {
        socket.emit('mission_command', { command: 'start' });
        addLog('Sent START mission command');
    });
    
    document.getElementById('btn-pause').addEventListener('click', () => {
        socket.emit('mission_command', { command: 'pause' });
        addLog('Sent PAUSE mission command', 'warn');
    });
    
    document.getElementById('btn-rtl').addEventListener('click', () => {
        if(confirm("Are you sure you want to Abort and Return To Launch?")) {
            socket.emit('mission_command', { command: 'rtl' });
            addLog('Sent RTL (Abort) command', 'error');
        }
    });
});
