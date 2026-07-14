/* dashboard/static/js/app.js */
document.addEventListener("DOMContentLoaded", () => {
    const socket = io();

    // DOM Elements — GCS-level (always present)
    const connStatus = document.getElementById('conn-status');
    const armStatus = document.getElementById('arm-status');
    const modeStatus = document.getElementById('mode-status');

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
        addLog('WebSocket connected to GCS backend');
        // Load apps and active app info on connect
        loadApps();
        loadActiveApp();
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
        
        // Update Map Marker
        if(window.droneMarker && data.lat !== undefined && data.lon !== undefined) {
            const newLatLng = new L.LatLng(data.lat, data.lon);
            window.droneMarker.setLatLng(newLatLng);
            
            // Auto-center map on first GPS fix
            if (!window.mapHasCentered) {
                if(window.droneMap) {
                    window.droneMap.panTo(newLatLng);
                    window.mapHasCentered = true;
                }
            }
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

    // ═══════════════════════════════════════════════
    //  Dynamic App Stats (replaces hardcoded detection_update)
    // ═══════════════════════════════════════════════
    socket.on('app_stats', (data) => {
        // Dynamically update any stat elements the current app has rendered
        for (const [key, value] of Object.entries(data)) {
            const el = document.getElementById(`app-stat-${key}`);
            if (el) {
                el.textContent = value;
            }
        }
        // Update total if it exists
        if (data.total !== undefined) {
            const totalEl = document.getElementById('app-stat-total');
            if (totalEl) totalEl.textContent = data.total;
        }
    });

    // New detections (app-agnostic event log)
    socket.on('new_detection', (data) => {
        const cls = data.class_name || 'object';
        const lat = data.lat ? data.lat.toFixed(6) : '--';
        const lon = data.lon ? data.lon.toFixed(6) : '--';
        addLog(`New ${cls} detected at (${lat}, ${lon})`, 'detect');
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

    // --- NEW V2 LOGIC ---

    // Tab Switching Logic
    const sidebarItems = document.querySelectorAll('.sidebar-item');
    const tabContents = document.querySelectorAll('.tab-content');

    sidebarItems.forEach(item => {
        item.addEventListener('click', () => {
            // Remove active from all tabs
            sidebarItems.forEach(i => i.classList.remove('active'));
            tabContents.forEach(tc => tc.classList.remove('active-tab'));
            
            // Add active to clicked
            item.classList.add('active');
            const targetTab = item.getAttribute('data-tab');
            document.getElementById('tab-' + targetTab).classList.add('active-tab');
        });
    });

    // Calibration Logic
    document.getElementById('btn-calibrate-compass').addEventListener('click', () => {
        socket.emit('start_calibration', { type: 'compass' });
        document.getElementById('compass-progress-container').style.display = 'block';
        addLog('Started Compass Calibration', 'warn');
    });

    const btnAccel = document.getElementById('btn-calibrate-accel');
    if (btnAccel) {
        btnAccel.addEventListener('click', () => {
            socket.emit('start_calibration', { type: 'accel' });
            addLog('Started Accel Calibration', 'warn');
        });
    }

    const btnEsc = document.getElementById('btn-calibrate-esc');
    if (btnEsc) {
        btnEsc.addEventListener('click', () => {
            socket.emit('start_calibration', { type: 'esc' });
            addLog('Started ESC Calibration', 'warn');
        });
    }

    socket.on('calibration_progress', (data) => {
        if(data.type === 'compass') {
            const pct = data.progress;
            document.getElementById('compass-progress-fill').style.width = pct + '%';
            document.getElementById('compass-progress-text').textContent = `Progress: ${pct}%`;
            if (pct >= 100) {
                addLog('Compass Calibration Complete', 'success');
            }
        } else if (data.type === 'accel') {
            addLog(`Accel Progress: ${data.progress}%`, 'info');
            if (data.progress >= 100) {
                addLog('Accel Calibration Complete', 'success');
            }
        }
    });

    socket.on('calibration_step', async (data) => {
        // Log the step instruction
        addLog(`[${data.type.toUpperCase()}] ${data.text}`, 'warn');
        // If it requires user to click continue
        if (data.wait_for_user) {
            // Very simple confirm dialog for continuing
            if (confirm(`Calibration Step:\n${data.text}\n\nClick OK when done.`)) {
                await fetch('/api/calibration/continue', { method: 'POST' });
                addLog('User confirmed step, continuing...', 'info');
            }
        }
    });

    // Pre-flight check
    document.getElementById('btn-run-checks').addEventListener('click', async () => {
        const resultsDiv = document.getElementById('preflight-results');
        const verdictDiv = document.getElementById('preflight-verdict');
        resultsDiv.innerHTML = '<p>Running checks...</p>';
        try {
            const response = await fetch('/api/preflight');
            const data = await response.json();
            let html = '<ul style="list-style: none; padding: 0;">';
            data.checks.forEach(check => {
                const icon = check.passed ? '<i class="fa-solid fa-check" style="color: var(--accent-green)"></i>' : (check.warning ? '<i class="fa-solid fa-triangle-exclamation" style="color: var(--accent-orange)"></i>' : '<i class="fa-solid fa-xmark" style="color: var(--badge-danger-bg)"></i>');
                html += `<li style="padding: 5px 0;">${icon} <strong style="display:inline-block; width: 150px;">${check.name}</strong> ${check.message}</li>`;
            });
            html += '</ul>';
            resultsDiv.innerHTML = html;
            
            if (verdictDiv) {
                if (data.ready) {
                    verdictDiv.innerHTML = `<h3 style="color: var(--accent-green);"><i class="fa-solid fa-circle-check"></i> READY TO FLY</h3><p style="margin-top: 5px; color: var(--text-muted);">All automated checks passed.</p>`;
                } else {
                    verdictDiv.innerHTML = `<h3 style="color: var(--accent-orange);"><i class="fa-solid fa-circle-exclamation"></i> ${data.issues} ISSUES — NOT READY</h3><p style="margin-top: 5px; color: var(--text-muted);">Resolve issues before flight.</p>`;
                }
            }
        } catch (e) {
            resultsDiv.innerHTML = '<p style="color:red">Failed to run checks</p>';
        }
    });

    // Profile Management
    async function loadProfiles() {
        try {
            // Load active profile
            const activeRes = await fetch('/api/profiles/active');
            const activeData = await activeRes.json();
            if (activeData.profile) {
                const p = activeData.profile;
                document.getElementById('active-profile-name').textContent = p.name + (p.version ? ` — v${p.version}` : '');
                let detailsStr = `Name: ${p.name}\nFrame: ${p.frame || 'N/A'}\nMotors: ${p.motors || 'N/A'}\nFC: ${p.fc || 'N/A'}`;
                document.getElementById('profile-details-content').textContent = detailsStr;
                
                // Also update Overview Tab drone identity
                const ovName = document.getElementById('ov-drone-name');
                if(ovName) ovName.textContent = p.name;
                const ovFrame = document.getElementById('ov-drone-frame');
                if(ovFrame) ovFrame.textContent = p.frame || 'N/A';
            }

            // Load all profiles list
            const res = await fetch('/api/profiles');
            const data = await res.json();
            const listEl = document.getElementById('profile-list');
            if (listEl && data.profiles) {
                listEl.innerHTML = '';
                data.profiles.forEach(prof => {
                    const li = document.createElement('li');
                    li.innerHTML = `<label><input type="radio" name="profile" value="${prof.id}" ${prof.active ? 'checked' : ''}> ${prof.name} — v${prof.version} ${prof.active ? '<span class="badge-success" style="font-size: 0.7rem; padding: 2px 6px;">Active</span>' : ''}</label>`;
                    
                    const radio = li.querySelector('input');
                    radio.addEventListener('change', async (e) => {
                        if (e.target.checked && !prof.active) {
                            if(confirm(`Switch to profile: ${prof.name}?`)) {
                                await fetch('/api/profiles/switch', {
                                    method: 'POST', 
                                    headers: {'Content-Type': 'application/json'},
                                    body: JSON.stringify({name: prof.id})
                                });
                                location.reload(); // Reload dashboard
                            }
                        }
                    });
                    listEl.appendChild(li);
                });
            }
        } catch (e) {
            console.error(e);
        }
    }
    
    async function loadFlightLogs() {
        try {
            const res = await fetch('/api/logs');
            const data = await res.json();
            const tbody = document.getElementById('flight-logs-tbody');
            if (tbody && data.logs) {
                tbody.innerHTML = '';
                data.logs.forEach((log, idx) => {
                    const tr = document.createElement('tr');
                    tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                    
                    const min = Math.floor(log.duration / 60);
                    const sec = Math.floor(log.duration % 60);
                    
                    tr.innerHTML = `
                        <td style="padding: 10px;">${data.logs.length - idx}</td>
                        <td style="padding: 10px;">${log.date}</td>
                        <td style="padding: 10px;">${min}m ${sec}s</td>
                        <td style="padding: 10px;">${log.max_alt.toFixed(1)}m</td>
                        <td style="padding: 10px; color: var(--accent-green);">${log.detections}</td>
                        <td style="padding: 10px;">${log.battery_start}% &rarr; ${log.battery_end}%</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } catch(e) {
            console.error('Failed to load logs:', e);
        }
    }
    
    loadProfiles();
    loadFlightLogs();

    document.getElementById('btn-push-params').addEventListener('click', async () => {
        addLog('Pushing parameters to FC...', 'warn');
        try {
            const response = await fetch('/api/profiles/push', { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                addLog('Parameters pushed successfully', 'success');
            } else {
                addLog('Failed to push params', 'error');
            }
        } catch (e) {
            addLog('Error pushing params', 'error');
        }
    });

    // --- Leaflet Map Integration ---
    if (document.getElementById('map')) {
        // Initialize Map
        const map = L.map('map').setView([-35.363, 149.165], 18); // Default to SITL location
        window.droneMap = map;
        
        // Add Dark Tile Layer
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
            maxZoom: 20
        }).addTo(map);

        // Drone Marker SVG
        const droneSvg = `
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="filter: drop-shadow(0 0 8px rgba(34,211,238,0.8));">
                <path d="M12 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/>
                <path d="M12 14v4"/>
                <path d="M12 18m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0"/>
                <path d="M10.5 12h-4.5"/>
                <path d="M13.5 12h4.5"/>
                <path d="M18 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0"/>
                <path d="M6 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0"/>
                <path d="M18 11v-2"/>
                <path d="M17 7h2"/>
                <path d="M6 11v-2"/>
                <path d="M5 7h2"/>
            </svg>
        `;
        
        const droneIcon = L.divIcon({
            html: droneSvg,
            className: 'drone-marker-icon',
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });
        
        window.droneMarker = L.marker([-35.363, 149.165], {icon: droneIcon}).addTo(map);
        window.mapHasCentered = false;

        // Draw Geofence if available
        if (window.GEOFENCE && window.GEOFENCE.length > 0) {
            const polygon = L.polygon(window.GEOFENCE, {
                color: 'var(--accent-orange)',
                fillColor: 'var(--accent-orange)',
                fillOpacity: 0.1,
                weight: 2,
                dashArray: '5, 5'
            }).addTo(map);
            map.fitBounds(polygon.getBounds());
        }
    }

    // --- Layout Toggles ---
    const layoutBtns = document.querySelectorAll('.btn-layout');
    const layoutContainer = document.getElementById('mission-layout-container');
    
    layoutBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            layoutBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            layoutContainer.classList.remove('layout-video-main', 'layout-split', 'layout-map-main', 'layout-video-only');
            const layoutClass = btn.getAttribute('data-layout');
            layoutContainer.classList.add(layoutClass);
            if (window.droneMap) {
                setTimeout(() => { window.droneMap.invalidateSize(); }, 400);
            }
        });
    });

    // ═══════════════════════════════════════════════
    //  App Management System
    // ═══════════════════════════════════════════════

    async function loadApps() {
        try {
            const res = await fetch('/api/apps');
            const data = await res.json();
            const grid = document.getElementById('apps-grid');
            if (!grid) return;
            grid.innerHTML = '';

            (data.apps || []).forEach(app => {
                const card = document.createElement('div');
                card.className = 'card';
                card.style.cursor = 'pointer';
                card.style.transition = 'all 0.2s ease';
                
                const isActive = app.active;
                if (isActive) {
                    card.style.borderColor = 'var(--accent-blue)';
                    card.style.boxShadow = '0 0 20px rgba(61, 139, 253, 0.15)';
                }

                card.innerHTML = `
                    <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                        <span><i class="${app.icon}"></i> ${app.name}</span>
                        ${isActive ? '<span class="badge-success" style="padding: 2px 8px; font-size: 0.65rem;">ACTIVE</span>' : ''}
                    </div>
                    <div style="padding: 14px;">
                        <p style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.5; margin-bottom: 12px;">${app.description}</p>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 0.7rem; color: var(--text-faint);">v${app.version}</span>
                            <button class="btn ${isActive ? 'btn-info' : 'btn-success'}" style="padding: 6px 16px; font-size: 0.78rem;" data-app-id="${app.id}">
                                ${isActive ? '<i class="fa-solid fa-check"></i> Active' : '<i class="fa-solid fa-play"></i> Load'}
                            </button>
                        </div>
                    </div>
                `;

                // Wire up the load button
                const btn = card.querySelector('button');
                btn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (isActive) return;
                    await loadApp(app.id);
                });

                grid.appendChild(card);
            });
        } catch (e) {
            console.error('Failed to load apps:', e);
        }
    }

    async function loadApp(appId) {
        addLog(`Loading app: ${appId}...`, 'warn');
        try {
            const res = await fetch('/api/apps/load', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: appId})
            });
            const result = await res.json();
            if (result.success) {
                addLog(`App "${result.app.name}" loaded successfully.`, 'detect');
                renderAppWidgets(result.app.widgets);
                loadApps(); // Refresh the app list to update active states
            } else {
                addLog('Failed to load app.', 'error');
            }
        } catch (e) {
            addLog('Error loading app.', 'error');
            console.error(e);
        }
    }

    async function loadActiveApp() {
        try {
            const res = await fetch('/api/apps/active');
            const data = await res.json();
            if (data && data.widgets) {
                renderAppWidgets(data.widgets);
                addLog(`Active app: ${data.name}`);
            }
        } catch (e) {
            console.error('Failed to load active app:', e);
        }
    }

    function renderAppWidgets(widgets) {
        const container = document.getElementById('app-widgets');
        if (!container) return;
        container.innerHTML = '';

        if (!widgets || widgets.length === 0) {
            container.innerHTML = `
                <div class="card">
                    <div class="card-header">App Status</div>
                    <div style="padding: 20px; text-align: center; color: var(--text-faint);">
                        <i class="fa-solid fa-cubes" style="font-size: 2rem; margin-bottom: 10px; display: block; opacity: 0.4;"></i>
                        <p>No widgets available.</p>
                    </div>
                </div>
            `;
            return;
        }

        widgets.forEach(widget => {
            const card = document.createElement('div');
            card.className = 'card';

            if (widget.type === 'stat_grid') {
                // Generate stat grid dynamically
                let statsHtml = '';
                widget.stats.forEach(stat => {
                    const iconStyle = stat.icon_style ? `style="${stat.icon_style}"` : '';
                    statsHtml += `
                        <div class="stat-box">
                            <div class="stat-icon" style="color: ${stat.color};">
                                <i class="${stat.icon}" ${iconStyle}></i>
                            </div>
                            <div class="stat-val" id="app-stat-${stat.id}" style="color: ${stat.color}; text-shadow: 0 0 20px ${stat.color}40;">0</div>
                            <div class="stat-label">${stat.label}</div>
                        </div>
                    `;
                });

                card.innerHTML = `
                    <div class="card-header">${widget.title}</div>
                    <div class="stats-grid">${statsHtml}</div>
                    <div class="total-objects">Total: <span id="app-stat-total" style="font-weight: 700; color: var(--text-main);">0</span></div>
                `;
            } else if (widget.type === 'info_card') {
                card.innerHTML = `
                    <div class="card-header">${widget.title}</div>
                    <div style="padding: 16px; color: var(--text-muted); font-size: 0.88rem; line-height: 1.6;">
                        <i class="fa-solid fa-info-circle" style="color: var(--accent-blue); margin-right: 6px;"></i>
                        ${widget.content}
                    </div>
                `;
            } else if (widget.type === 'log') {
                card.innerHTML = `
                    <div class="card-header">${widget.title}</div>
                    <div class="event-log" id="${widget.id}" style="max-height: 200px;"></div>
                `;
            }

            container.appendChild(card);
        });
    }

});
