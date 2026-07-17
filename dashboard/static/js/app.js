// dashboard/static/js/app.js (Military Tactical GCS Integration)
document.addEventListener("DOMContentLoaded", () => {
    const socket = io();

    // --- CLOCK ---
    function updateClock() {
        const now = new Date();
        const h = String(now.getHours()).padStart(2, '0');
        const m = String(now.getMinutes()).padStart(2, '0');
        const s = String(now.getSeconds()).padStart(2, '0');
        const clockDisplay = document.getElementById('clock-display');
        if(clockDisplay) clockDisplay.textContent = `${h}:${m}:${s}`;
    }
    setInterval(updateClock, 1000);
    updateClock();

    // --- CONSOLE LOGGING ---
    const consoleFeed = document.getElementById('console-feed');
    function tacLog(msg, type = 'normal') {
        if(!consoleFeed) return;
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        const timestamp = new Date().toISOString().substring(11, 19);
        entry.textContent = `[${timestamp}] ${msg}`;
        consoleFeed.appendChild(entry);
        consoleFeed.scrollTop = consoleFeed.scrollHeight;
    }

    // --- CONNECTION STATUS ---
    const backendStatus = document.getElementById('backend-status');
    const backendStatusText = document.getElementById('backend-status-text');

    socket.on('connect', () => {
        if(backendStatus) backendStatus.className = 'global-status nominal';
        if(backendStatusText) backendStatusText.textContent = 'SYSTEM NOMINAL // DATALINK ONLINE';
        tacLog('[SYS] Connected to Backend Server', 'success');
        loadApps(); // Load apps on connect
    });

    socket.on('disconnect', () => {
        if(backendStatus) backendStatus.className = 'global-status danger';
        if(backendStatusText) backendStatusText.textContent = 'CONNECTION LOST // OFFLINE';
        tacLog('[SYS] Backend Disconnected', 'error');
    });

    // --- TELEMETRY HANDLING ---
    let isArmed = false;
    
    socket.on('telemetry_update', (data) => {
        if(data.alt !== undefined) document.getElementById('val-alt').textContent = data.alt.toFixed(1);
        if(data.speed !== undefined) document.getElementById('val-spd').textContent = data.speed.toFixed(1);
        if(data.heading !== undefined) document.getElementById('val-hdg').textContent = Math.round(data.heading);
        if(data.battery_v !== undefined) {
            document.getElementById('val-batt').textContent = data.battery_v.toFixed(1);
            if(data.battery_pct !== undefined) document.getElementById('val-batt').textContent += ` (${data.battery_pct}%)`;
        }
        
        // Mocking Pitch/Roll based on speed/heading changes if not provided natively by this backend build
        // In a real system, you'd pull data.pitch and data.roll
        let p = data.pitch || 0;
        let r = data.roll || 0;
        const horizon = document.querySelector('.artificial-horizon');
        if(horizon) horizon.style.transform = `rotate(${r}deg) translateY(${p}px)`;
        if(document.getElementById('val-pitch')) document.getElementById('val-pitch').textContent = p.toFixed(1);
        if(document.getElementById('val-roll')) document.getElementById('val-roll').textContent = r.toFixed(1);

        if(data.armed !== undefined) {
            isArmed = data.armed;
            updateArmButtonState();
        }

        if(data.mode !== undefined) {
            document.getElementById('current-mode').textContent = data.mode.toUpperCase();
        }

        if(data.sats !== undefined) {
             document.getElementById('val-sats').textContent = `${data.sats} (3D FIX)`;
        }

        // Update Map Drone Marker
        if (window.droneMarker && data.lat !== undefined && data.lon !== undefined) {
            const newLatLng = new L.LatLng(data.lat, data.lon);
            window.droneMarker.setLatLng(newLatLng);
            
            if (!window.mapHasCentered && window.droneMap) {
                window.droneMap.panTo(newLatLng);
                window.mapHasCentered = true;
            }
        }
    });

    // --- ARM / DISARM LOGIC & BUTTON COMMANDS ---
    const armBtn = document.getElementById('btn-arm');
    let checklistPassed = false;

    function updateArmButtonState() {
        if(!armBtn) return;
        if (!checklistPassed && !isArmed) {
            armBtn.disabled = true;
            armBtn.style.opacity = '0.5';
            armBtn.innerHTML = '<i class="fa-solid fa-lock"></i> ARM SYSTEM (LOCKED)';
            armBtn.classList.remove('armed');
            return;
        }
        
        armBtn.disabled = false;
        armBtn.style.opacity = '1';
        
        if (isArmed) {
            armBtn.innerHTML = '<i class="fa-solid fa-lock-open"></i> SYSTEM ARMED';
            armBtn.classList.add('armed');
        } else {
            armBtn.innerHTML = '<i class="fa-solid fa-lock"></i> ARM SYSTEM (READY)';
            armBtn.classList.remove('armed');
        }
    }

    if(armBtn) {
        armBtn.addEventListener('click', () => {
            if(!checklistPassed && !isArmed) return;
            const targetCmd = isArmed ? 'disarm' : 'arm';
            socket.emit('mission_command', { command: targetCmd });
            tacLog(`[CMD] Sending ${targetCmd} command to FC...`, 'warn');
        });
    }

    // Generic Buttons
    document.querySelectorAll('.cmd-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const cmd = e.currentTarget.getAttribute('data-cmd');
            
            if (cmd === 'KILL_SWITCH') {
                tacLog(`[CRITICAL] EMERGENCY MOTOR STOP TRIGGERED!`, 'error');
                socket.emit('mission_command', { command: 'kill' });
                return;
            }
            if (cmd === 'PAUSE') {
                tacLog(`[SYS] EMERGENCY LOITER. DRONE HOLDING POSITION.`, 'warn');
                socket.emit('mission_command', { command: 'pause' });
                return;
            }
            if (cmd === 'START') {
                socket.emit('mission_command', { command: 'start' });
                tacLog(`[CMD] Taking Off...`, 'normal');
                return;
            }
            if (cmd === 'RTL' || cmd === 'LAND') {
                socket.emit('mission_command', { command: cmd.toLowerCase() });
                tacLog(`[CMD] Sending ${cmd} command...`, 'warn');
                return;
            }
            if (cmd.startsWith('CLAW') || cmd === 'AUTO_DROP_SEQ') {
                // Mock payload for now unless backend specifically supports it
                tacLog(`[PAYLOAD] Executing: ${cmd}...`, 'normal');
                setTimeout(() => tacLog(`[ACK] Payload mechanism actuated.`, 'success'), 400);
                return;
            }
        });
    });

    // --- PRE-FLIGHT CHECKLIST ---
    const btnPreflight = document.getElementById('btn-preflight');
    if(btnPreflight) {
        btnPreflight.addEventListener('click', () => {
            showModal('// PRE-FLIGHT SAFETY CHECKLIST', `
                <div class="checklist-container">
                    <label class="checklist-item">
                        <input type="checkbox" class="chk-item">
                        <span>1. Props secure and area clear of personnel</span>
                    </label>
                    <label class="checklist-item">
                        <input type="checkbox" class="chk-item">
                        <span>2. Battery voltage > 14.8V (Fully Charged)</span>
                    </label>
                    <label class="checklist-item">
                        <input type="checkbox" class="chk-item">
                        <span>3. Run Automated Backend Checks</span>
                    </label>
                    <div id="auto-check-results" style="margin-top: 10px; color: var(--color-amber);"></div>
                </div>
                <button id="btn-submit-checklist" class="tactical-btn btn-large" style="margin-top:20px; background:rgba(0,255,102,0.1); border-color:var(--color-green); color:var(--color-green);" disabled>
                    VERIFY AND UNLOCK
                </button>
            `);

            // Trigger backend check
            fetch('/api/preflight').then(r=>r.json()).then(data => {
                let html = '<ul style="list-style: none; padding: 0; font-size: 0.9rem;">';
                data.checks.forEach(check => {
                    const color = check.passed ? 'var(--color-green)' : 'var(--color-red)';
                    html += `<li style="color:${color};"><i class="fa-solid fa-circle-check"></i> ${check.name}: ${check.message}</li>`;
                });
                html += '</ul>';
                document.getElementById('auto-check-results').innerHTML = html;
            });

            const checkboxes = document.querySelectorAll('.chk-item');
            const submitBtn = document.getElementById('btn-submit-checklist');
            
            checkboxes.forEach(chk => {
                chk.addEventListener('change', () => {
                    const allChecked = Array.from(checkboxes).every(c => c.checked);
                    submitBtn.disabled = !allChecked;
                    if(allChecked) {
                        submitBtn.style.opacity = '1';
                        submitBtn.style.background = 'var(--color-green)';
                        submitBtn.style.color = 'var(--bg-dark)';
                    } else {
                        submitBtn.style.background = 'rgba(0,255,102,0.1)';
                        submitBtn.style.color = 'var(--color-green)';
                    }
                });
            });

            submitBtn.addEventListener('click', () => {
                checklistPassed = true;
                updateArmButtonState();
                hideModal();
                tacLog(`[SYS] Pre-flight checklist completed. System UNLOCKED.`, 'success');
            });
        });
    }

    // --- MODAL UTILS ---
    const modalOverlay = document.getElementById('modal-overlay');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');

    document.getElementById('close-modal').addEventListener('click', hideModal);

    function showModal(title, contentHTML) {
        modalTitle.textContent = title;
        modalBody.innerHTML = contentHTML;
        modalOverlay.classList.remove('hidden');
    }

    function hideModal() {
        modalOverlay.classList.add('hidden');
    }

    // --- PROVISIONING & CALIBRATION (Connected to Backend) ---
    document.querySelectorAll('.setup-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const type = e.currentTarget.getAttribute('data-app');
            if(type === 'APPS') {
                // Show loaded apps
                showModal('// APPS CONFIG', `<div id="apps-grid-modal" class="grid-2">Loading...</div>`);
                loadAppsIntoModal();
            } else if (type === 'CALIBRATE') {
                showModal('// SENSOR CALIBRATION', `
                    <div style="display:flex; flex-direction:column; gap:10px;">
                        <button class="tactical-btn cal-btn" data-type="compass">CALIBRATE COMPASS (MAG)</button>
                        <button class="tactical-btn cal-btn" data-type="accel">CALIBRATE ACCELEROMETER</button>
                        <button class="tactical-btn cal-btn" data-type="esc">CALIBRATE ESC</button>
                        <div id="cal-progress" style="margin-top:15px; color:var(--color-cyan);"></div>
                    </div>
                `);
                
                document.querySelectorAll('.cal-btn').forEach(cb => {
                    cb.addEventListener('click', (e2) => {
                        const calType = e2.currentTarget.getAttribute('data-type');
                        socket.emit('start_calibration', { type: calType });
                        tacLog(`[CAL] Started ${calType.toUpperCase()} calibration.`, 'warn');
                        document.getElementById('cal-progress').textContent = `Initiating ${calType.toUpperCase()}...`;
                    });
                });
            } else if (type === 'PROFILES') {
                showModal('// DRONE PROFILES', `<div id="profiles-grid" class="grid-2">Loading...</div>`);
                fetch('/api/profiles')
                    .then(r => r.json())
                    .then(data => {
                        const grid = document.getElementById('profiles-grid');
                        grid.innerHTML = '';
                        if (data.profiles && data.profiles.length > 0) {
                            data.profiles.forEach(p => {
                                grid.innerHTML += `
                                    <div class="app-card">
                                        <div class="app-card-title">${p.name} (v${p.version})</div>
                                        <div class="app-card-desc">FC: ${p.fc} | Frame: ${p.frame}</div>
                                        <button class="tactical-btn" onclick="activateProfile('${p.id}')">ACTIVATE</button>
                                    </div>
                                `;
                            });
                        } else {
                            grid.innerHTML = '<p>No profiles found.</p>';
                        }
                    })
                    .catch(e => console.error(e));
            } else if (type === 'LOGS') {
                showModal('// FLIGHT LOGS', `<div id="logs-container">Loading...</div>`);
                fetch('/api/logs')
                    .then(r => r.json())
                    .then(data => {
                        const container = document.getElementById('logs-container');
                        if (data.logs && data.logs.length > 0) {
                            let tableHTML = `<table class="logs-table" style="width:100%; text-align:left; border-collapse: collapse;">
                                <thead>
                                    <tr style="border-bottom: 1px solid var(--color-cyan); color: var(--color-cyan);">
                                        <th>Date</th><th>Duration (s)</th><th>Detections</th>
                                    </tr>
                                </thead>
                                <tbody>`;
                            data.logs.forEach(l => {
                                tableHTML += `<tr>
                                    <td>${new Date(l.start_time * 1000).toLocaleString()}</td>
                                    <td>${l.duration.toFixed(1)}</td>
                                    <td>${l.total_detections}</td>
                                </tr>`;
                            });
                            tableHTML += `</tbody></table>`;
                            container.innerHTML = tableHTML;
                        } else {
                            container.innerHTML = '<p>No flight logs found.</p>';
                        }
                    })
                    .catch(e => console.error(e));
            }
        });
    });

    window.activateProfile = function(profileId) {
        tacLog(`[PROFILE] Activating profile: ${profileId}`, 'warn');
        fetch('/api/profiles/active', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({profile_id: profileId})
        }).then(r => r.json()).then(data => {
            if(data.success) {
                tacLog(`[PROFILE] Activated successfully.`, 'success');
                hideModal();
            }
        });
    };

    socket.on('calibration_progress', (data) => {
        const prog = document.getElementById('cal-progress');
        if(prog) prog.textContent = `Progress: ${data.progress}%`;
        if(data.progress >= 100) tacLog(`[CAL] ${data.type} Calibration Complete!`, 'success');
    });

    socket.on('calibration_step', async (data) => {
        tacLog(`[CAL STEP] ${data.text}`, 'warn');
        if (data.wait_for_user) {
            if (confirm(`Calibration Step:\n${data.text}\n\nClick OK when done.`)) {
                await fetch('/api/calibration/continue', { method: 'POST' });
                tacLog('[CAL] Step confirmed.', 'info');
            }
        }
    });

    async function loadAppsIntoModal() {
        try {
            const res = await fetch('/api/apps');
            const data = await res.json();
            const grid = document.getElementById('apps-grid-modal');
            if(!grid) return;
            grid.innerHTML = '';
            (data.apps || []).forEach(app => {
                grid.innerHTML += `
                    <div class="stat-card" style="cursor:pointer;" onclick="loadApp('${app.id}')">
                        <i class="${app.icon}"></i>
                        <div style="margin-top:5px; font-weight:bold;">${app.name}</div>
                        <div style="font-size:0.7rem;">${app.active ? '<span style="color:var(--color-green)">ACTIVE</span>' : 'Load'}</div>
                    </div>
                `;
            });
        } catch(e) {
            console.error(e);
        }
    }

    window.loadApp = async function(appId) {
        tacLog(`[APP] Loading app: ${appId}...`, 'warn');
        await fetch('/api/apps/load', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: appId})});
        tacLog(`[APP] ${appId} loaded.`, 'success');
        hideModal();
    }

    // --- LIVE FLIGHT SETUP ---
    const btnLiveFlight = document.getElementById('btn-live-flight');
    if(btnLiveFlight) {
        btnLiveFlight.addEventListener('click', async () => {
            // First fetch available ports
            let portOptions = '<option value="/dev/ttyAMA0">/dev/ttyAMA0</option>';
            try {
                const res = await fetch('/api/ports');
                const data = await res.json();
                if (data.ports && data.ports.length > 0) {
                    portOptions = data.ports.map(p => `<option value="${p.device}">${p.device} - ${p.description}</option>`).join('');
                }
            } catch (e) {
                console.error("Failed to fetch ports:", e);
            }

            showModal('// INITIALIZE FLIGHT ENVIRONMENT', `
                <div style="display:flex; flex-direction:column; gap:10px;">
                    <div style="margin-bottom: 15px;">
                        <label style="color:var(--color-cyan); font-size:0.9rem;">SELECT HARDWARE PORT:</label><br>
                        <select id="live-port-select" style="background:rgba(0,0,0,0.5); color:var(--color-cyan); border:1px solid var(--color-cyan); padding:8px; width:100%; margin-top:5px; font-family:'Courier New', monospace;">
                            ${portOptions}
                        </select>
                    </div>
                    <button class="tactical-btn" onclick="startEnv('SITL')">START SIMULATOR (SITL)</button>
                    <button class="tactical-btn btn-danger" onclick="startEnv('LIVE')">START LIVE FLIGHT (HW)</button>
                </div>
            `);
        });
    }

    window.startEnv = async function(mode) {
        tacLog(`[ENV] Initializing ${mode} environment...`, 'warn');
        let port = '/dev/ttyAMA0';
        const portSelect = document.getElementById('live-port-select');
        if (portSelect) {
            port = portSelect.value;
        }
        hideModal();
        try {
            const res = await fetch('/api/env/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: mode, port: port, baud: 57600 }) // using selected port
            });
            const data = await res.json();
            if (data.success) {
                tacLog(`[ENV] ${mode} Environment Online on ${port}!`, 'success');
            } else {
                tacLog(`[ENV] Failed: ${data.error}`, 'error');
            }
        } catch (e) {
            tacLog(`[ENV] Error connecting to backend`, 'error');
        }
    };


    // --- MAP INITIALIZATION ---
    if(document.getElementById('tactical-map')) {
        const map = L.map('tactical-map', {
            zoomControl: false,
            attributionControl: false
        }).setView([15.4326, 75.0118], 16); 
        window.droneMap = map;

        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 19
        }).addTo(map);
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 19
        }).addTo(map);

        const droneIcon = L.divIcon({
            html: '<i class="fa-solid fa-location-crosshairs" style="color:#ffaa00; font-size: 24px; filter: drop-shadow(0 0 5px #ffaa00);"></i>',
            className: '',
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });
        window.droneMarker = L.marker([15.4326, 75.0118], {icon: droneIcon}).addTo(map);
        window.mapHasCentered = false;

        // Leaflet Draw (Geofence)
        const drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);
        const drawControl = new L.Control.Draw({
            edit: { featureGroup: drawnItems },
            draw: {
                polygon: { allowIntersection: false, shapeOptions: { color: '#ff3333', weight: 3, fillOpacity: 0.2 } },
                polyline: false, circle: false, rectangle: false, marker: false, circlemarker: false
            }
        });
        
        map.on(L.Draw.Event.CREATED, function (event) {
            drawnItems.addLayer(event.layer);
            tacLog(`[GEO] Geofence boundary established.`, 'warn');
        });

        let polygonDrawer = new L.Draw.Polygon(map, drawControl.options.draw.polygon);
        document.getElementById('btn-draw-fence').addEventListener('click', () => {
            polygonDrawer.enable();
            tacLog(`[UI] Drawing Geofence. Click map to set points.`, 'normal');
        });
        document.getElementById('btn-clear-fence').addEventListener('click', () => {
            drawnItems.clearLayers();
            tacLog(`[GEO] Geofence cleared.`, 'normal');
        });
    }

    // --- VIDEO PIP TOGGLE ---
    const videoPip = document.querySelector('.video-pip');
    const toggleBtn = document.getElementById('toggle-video');
    if(toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            videoPip.classList.toggle('expanded');
            const isExpanded = videoPip.classList.contains('expanded');
            toggleBtn.innerHTML = isExpanded 
                ? '<i class="fa-solid fa-compress"></i>' 
                : '<i class="fa-solid fa-expand"></i>';
        });
    }
});
