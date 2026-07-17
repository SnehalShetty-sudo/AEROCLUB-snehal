// --- CLOCK ---
function updateClock() {
    const now = new Date();
    // Start of mission arbitrary time
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
    const diff = new Date(now - start);
    const h = String(diff.getUTCHours()).padStart(2, '0');
    const m = String(diff.getUTCMinutes()).padStart(2, '0');
    const s = String(diff.getUTCSeconds()).padStart(2, '0');
    document.getElementById('clock-display').textContent = `${h}:${m}:${s}`;
}
setInterval(updateClock, 1000);
updateClock();

// --- CONSOLE LOGGING ---
const consoleFeed = document.getElementById('console-feed');
function tacLog(msg, type = 'normal') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const timestamp = new Date().toISOString().substring(11, 19);
    entry.textContent = `[${timestamp}] ${msg}`;
    consoleFeed.appendChild(entry);
    consoleFeed.scrollTop = consoleFeed.scrollHeight;
}

// --- BUTTON INTERACTIONS (GENERIC) ---
document.querySelectorAll('.cmd-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        // e.currentTarget to handle child <i> tags
        const cmd = e.currentTarget.getAttribute('data-cmd') || e.currentTarget.innerText;
        
        if (cmd === 'KILL_SWITCH') {
            tacLog(`[CRITICAL] EMERGENCY MOTOR STOP TRIGGERED!`, 'error');
            document.getElementById('val-spd').textContent = '0.0';
            isArmed = false;
            updateArmButtonState();
            return;
        }

        if (cmd === 'FORCE_LOITER') {
            tacLog(`[SYS] EMERGENCY LOITER. DRONE HOLDING POSITION.`, 'warn');
            return;
        }

        if (cmd.startsWith('CLAW')) {
            tacLog(`[PAYLOAD] Executing: ${cmd}...`, 'normal');
            setTimeout(() => tacLog(`[ACK] Claw mechanism actuated.`, 'success'), 400);
            return;
        }

        if (cmd === 'AUTO_DROP_SEQ') {
            tacLog(`[MISSION] Initializing Auto-Drop Sequence...`, 'warn');
            setTimeout(() => tacLog(`[MISSION] Target acquired. Claw opened.`, 'success'), 1500);
            return;
        }

        tacLog(`[CMD] Sending command: ${cmd}...`, 'normal');
        setTimeout(() => tacLog(`[ACK] Command ${cmd} acknowledged.`, 'success'), 500);
    });
});

// --- FLIGHT MODES ---
const modeBtns = document.querySelectorAll('.mode-btn');
const currentModeDisplay = document.getElementById('current-mode');
if(modeBtns.length > 0) {
    modeBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            modeBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            const mode = e.target.getAttribute('data-mode');
            currentModeDisplay.textContent = mode;
            tacLog(`[SYS] Flight mode changed to ${mode}.`, 'normal');
        });
    });
}

// --- ARM / DISARM LOGIC ---
const armBtn = document.getElementById('btn-arm');
let isArmed = false;
let checklistPassed = false;

function updateArmButtonState() {
    if (!checklistPassed) {
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

armBtn.addEventListener('click', () => {
    if(!checklistPassed) return;
    
    isArmed = !isArmed;
    if (isArmed) {
        tacLog(`[WARN] SYSTEM ARMED. PROPELLERS ACTIVE.`, 'error');
    } else {
        tacLog(`[SYS] System disarmed. Safe to approach.`, 'success');
    }
    updateArmButtonState();
});

// --- PRE-FLIGHT CHECKLIST ---
document.getElementById('btn-preflight').addEventListener('click', () => {
    modalTitle.textContent = '// PRE-FLIGHT SAFETY CHECKLIST';
    modalBody.innerHTML = `
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
                <span>3. Radio and Telemetry link > 90%</span>
            </label>
            <label class="checklist-item">
                <input type="checkbox" class="chk-item">
                <span>4. Claw Payload Mechanism securely locked</span>
            </label>
            <label class="checklist-item">
                <input type="checkbox" class="chk-item">
                <span>5. GPS 3D Fix established (Sats > 10)</span>
            </label>
        </div>
        <button id="btn-submit-checklist" class="tactical-btn btn-large" style="margin-top:20px; background:rgba(0,255,102,0.1); border-color:var(--color-green); color:var(--color-green);" disabled>
            VERIFY AND UNLOCK
        </button>
    `;
    modalOverlay.classList.remove('hidden');

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
        modalOverlay.classList.add('hidden');
        tacLog(`[SYS] Pre-flight checklist completed. System UNLOCKED.`, 'success');
    });
});

// --- VIDEO PIP TOGGLE ---
const videoPip = document.querySelector('.video-pip');
document.getElementById('toggle-video').addEventListener('click', () => {
    videoPip.classList.toggle('expanded');
    const isExpanded = videoPip.classList.contains('expanded');
    document.getElementById('toggle-video').innerHTML = isExpanded 
        ? '<i class="fa-solid fa-compress"></i>' 
        : '<i class="fa-solid fa-expand"></i>';
});

// --- MAP INITIALIZATION ---
const map = L.map('tactical-map', {
    zoomControl: false,
    attributionControl: false
}).setView([15.4326, 75.0118], 16); // Centered near Dharwad / SDMCET roughly

// Using ESRI Satellite map (base)
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19
}).addTo(map);

// Adding ESRI Reference layer (transparent)
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19
}).addTo(map);

// Add drone marker
const droneIcon = L.divIcon({
    html: '<i class="fa-solid fa-location-crosshairs" style="color:#ffaa00; font-size: 24px; filter: drop-shadow(0 0 5px #ffaa00);"></i>',
    className: '',
    iconSize: [24, 24],
    iconAnchor: [12, 12]
});
L.marker([15.4326, 75.0118], {icon: droneIcon}).addTo(map);

// --- LEAFLET DRAW (GEOFENCE) ---
const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

const drawControl = new L.Control.Draw({
    edit: { featureGroup: drawnItems },
    draw: {
        polygon: {
            allowIntersection: false,
            shapeOptions: { color: '#ff3333', weight: 3, fillOpacity: 0.2 }
        },
        polyline: false,
        circle: false,
        rectangle: false,
        marker: false,
        circlemarker: false
    }
});

// We hide the default toolbar and trigger it via our custom buttons
map.on(L.Draw.Event.CREATED, function (event) {
    const layer = event.layer;
    drawnItems.addLayer(layer);
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


// --- TELEMETRY MOCK ---
let simAlt = 14.2;
let simSpd = 0.0;
let simHdg = 342;
let simPitch = -2.1;
let simRoll = 0.4;

setInterval(() => {
    simAlt += (Math.random() - 0.5) * 0.2;
    simSpd = isArmed ? 5.2 + (Math.random() - 0.5) : 0.0;
    simPitch += (Math.random() - 0.5) * 0.5;
    simRoll += (Math.random() - 0.5) * 1.0;

    document.getElementById('val-alt').textContent = simAlt.toFixed(1);
    document.getElementById('val-spd').textContent = simSpd.toFixed(1);
    document.getElementById('val-pitch').textContent = simPitch.toFixed(1);
    document.getElementById('val-roll').textContent = simRoll.toFixed(1);

    const horizon = document.querySelector('.artificial-horizon');
    horizon.style.transform = `rotate(${simRoll}deg) translateY(${simPitch}px)`;

}, 200);


// --- MODALS (Provisioning/Apps) ---
const modalOverlay = document.getElementById('modal-overlay');
const modalTitle = document.getElementById('modal-title');
const modalBody = document.getElementById('modal-body');

document.getElementById('close-modal').addEventListener('click', () => {
    modalOverlay.classList.add('hidden');
});

const setupContents = {
    'APPS': `
        <div class="app-grid">
            <div class="app-card" onclick="tacLog('[APP] Swarm Control initiated.', 'normal')">
                <i class="fa-solid fa-cubes"></i>
                <div>SWARM CONTROL</div>
            </div>
            <div class="app-card" onclick="tacLog('[APP] Target Tracking initiated.', 'normal')">
                <i class="fa-solid fa-crosshairs"></i>
                <div>TARGET TRACKING</div>
            </div>
        </div>
    `,
    'CALIBRATE': `
        <div style="display:flex; flex-direction:column; gap:10px;">
            <button class="tactical-btn" onclick="tacLog('[CAL] Compass Calib sequence started.', 'normal')">CALIBRATE COMPASS (MAG)</button>
            <button class="tactical-btn" onclick="tacLog('[CAL] Accel Calib sequence started.', 'normal')">CALIBRATE ACCELEROMETER</button>
        </div>
    `
};

document.querySelectorAll('.setup-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        const type = e.currentTarget.getAttribute('data-app');
        modalTitle.textContent = `// SETUP: ${type}`;
        modalBody.innerHTML = setupContents[type];
        modalOverlay.classList.remove('hidden');
        tacLog(`[UI] Opened setup menu: ${type}`);
    });
});
