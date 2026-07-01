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

        if(data.lat !== undefined && data.lon !== undefined && window.GEOFENCE) {
            drawRadar(data.lat, data.lon, data.heading || 0);
        }
    });

    // Radar Widget Logic
    function drawRadar(droneLat, droneLon, heading) {
        const canvas = document.getElementById('radar-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;

        // Clear canvas
        ctx.clearRect(0, 0, w, h);
        
        // Draw grid lines for aesthetics
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        for (let i = 0; i < w; i += 20) {
            ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, h); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(w, i); ctx.stroke();
        }

        // Calculate bounding box of geofence
        let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
        window.GEOFENCE.forEach(pt => {
            if (pt[0] < minLat) minLat = pt[0];
            if (pt[0] > maxLat) maxLat = pt[0];
            if (pt[1] < minLon) minLon = pt[1];
            if (pt[1] > maxLon) maxLon = pt[1];
        });

        // Add 10% padding to bounds
        const latPad = (maxLat - minLat) * 0.1;
        const lonPad = (maxLon - minLon) * 0.1;
        minLat -= latPad; maxLat += latPad;
        minLon -= lonPad; maxLon += lonPad;

        const latRange = maxLat - minLat;
        const lonRange = maxLon - minLon;

        // Helper to convert lat/lon to canvas x/y
        function getXY(lat, lon) {
            const x = ((lon - minLon) / lonRange) * w;
            // latitude increases as you go North (up), so invert Y
            const y = h - (((lat - minLat) / latRange) * h);
            return {x, y};
        }

        // Draw Geofence
        ctx.beginPath();
        window.GEOFENCE.forEach((pt, i) => {
            const pos = getXY(pt[0], pt[1]);
            if (i === 0) ctx.moveTo(pos.x, pos.y);
            else ctx.lineTo(pos.x, pos.y);
        });
        ctx.closePath();
        ctx.strokeStyle = '#e74c3c'; // red boundary
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = 'rgba(231, 76, 60, 0.1)';
        ctx.fill();

        // Draw Drone
        const dronePos = getXY(droneLat, droneLon);
        
        ctx.save();
        ctx.translate(dronePos.x, dronePos.y);
        // Convert heading to radians (0 is North)
        ctx.rotate(heading * Math.PI / 180);
        
        // Draw drone triangle pointing North (up)
        ctx.beginPath();
        ctx.moveTo(0, -8);
        ctx.lineTo(6, 6);
        ctx.lineTo(0, 3);
        ctx.lineTo(-6, 6);
        ctx.closePath();
        ctx.fillStyle = '#00ff00';
        ctx.fill();
        
        ctx.restore();
    }

    // Detection updates
    let lastCounts = {};
    socket.on('detection_update', (data) => {
        // data.counts is a dict e.g. {"person": 5, "triangle": 1}
        const counts = data.counts || {};
        // Use max to ensure counts only go UP (permanent running total for the judges)
        if (counts['person'] !== undefined) {
            countPerson.textContent = Math.max(parseInt(countPerson.textContent) || 0, counts['person']);
        }
        if (counts['triangle'] !== undefined) {
            countTriangle.textContent = Math.max(parseInt(countTriangle.textContent) || 0, counts['triangle']);
        }
        if (counts['square'] !== undefined) {
            countSquare.textContent = Math.max(parseInt(countSquare.textContent) || 0, counts['square']);
        }
        if (counts['rectangle'] !== undefined) {
            countRectangle.textContent = Math.max(parseInt(countRectangle.textContent) || 0, counts['rectangle']);
        }
        
        let total = parseInt(countPerson.textContent) + 
                    parseInt(countTriangle.textContent) + 
                    parseInt(countSquare.textContent) + 
                    parseInt(countRectangle.textContent);
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

    // Detailed Geotagged Detections
    const detectionLogBody = document.getElementById('detection-log-body');
    socket.on('new_detection', (data) => {
        // Create a new row for the detection log table
        const row = document.createElement('tr');
        row.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
        
        const timeCell = document.createElement('td');
        timeCell.style.padding = '6px';
        timeCell.textContent = data.time;
        
        const cellIdCell = document.createElement('td');
        cellIdCell.style.padding = '6px';
        cellIdCell.innerHTML = `<span class="badge-success" style="padding: 2px 6px; border-radius: 4px;">${data.cell_id}</span>`;
        
        const coordsCell = document.createElement('td');
        coordsCell.style.padding = '6px';
        coordsCell.style.fontFamily = 'monospace';
        coordsCell.textContent = `${data.lat}, ${data.lon}`;
        
        row.appendChild(timeCell);
        row.appendChild(cellIdCell);
        row.appendChild(coordsCell);
        
        // Add to the top of the table
        detectionLogBody.insertBefore(row, detectionLogBody.firstChild);
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
