let active_mission = "default";
function verifyPin() {
    const pin = document.getElementById('pin-input').value;
    const SECRET_PIN = "2255"; // Set your 4-digit PIN here

    if (pin === SECRET_PIN) {
        document.getElementById('lock-screen').style.display = 'none';
        alert("Welcome back, Sir. Systems Online.");
    } else {
        alert("Unauthorized Access. Connection Terminated.");
    }
}
async function fetchDirectories() {
    try {
        const response = await fetch('/list-directories');
        const data = await response.json();
        const listContainer = document.getElementById('directory-list');
        listContainer.innerHTML = ''; // Clear current list

        data.directories.forEach(dir => {
            const btn = document.createElement('button');
            btn.className = 'dir-btn';
            btn.innerText = dir.replace(/_/g, ' ').toUpperCase();
            btn.onclick = () => switchWorkspace(dir);
            listContainer.appendChild(btn);
        });
    } catch (err) {
        console.error("Failed to load directories:", err);
    }
}

// 2. Switch the active mission and launch VS Code
async function switchWorkspace(dirName) {
    // Update the local variable when you switch
    active_mission = dirName;

    await fetch('/switch-workspace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directory: dirName })
    });
    loadMissionLogs();
}


// STEP 1: Only load the list of filenames
// STEP 1: Show the List, Hide the Content
async function loadMissionLogs() {
    const response = await fetch('/get-mission-logs');
    const data = await response.json();
    const chatContainer = document.getElementById('chat-history-display');

    if (chatContainer) {
        chatContainer.innerHTML = `
                    <div id="file-explorer-view">
                        <h3 style="color: #00d2ff;">Sector: ${active_mission}</h3>
                        <div id="file-list"></div>
                    </div>
                    <div id="file-content-view" style="display: none;"></div>
                `;

        const fileList = document.getElementById('file-list');
        data.logs.forEach(log => {
            const btn = document.createElement('button');
            btn.className = "file-explorer-btn";
            btn.innerHTML = `📄 ${log.name}`;
            btn.onclick = () => viewFileContent(log.name);
            fileList.appendChild(btn);
        });
    }
}

// STEP 2: Show the Content, Hide the List + Add Back Button
async function viewFileContent(fileName) {
    const listView = document.getElementById('file-explorer-view');
    const contentView = document.getElementById('file-content-view');

    const response = await fetch(`/read-file?name=${fileName}`);
    const data = await response.json();

    listView.style.display = "none"; // Hide the list
    contentView.style.display = "block"; // Show the content

    contentView.innerHTML = `
                <button class="back-btn" onclick="closeFileView()">⬅ Back to Sector</button>
                <h4 style="color: #00d2ff;">File: ${fileName}</h4>
                <pre class="code-preview-block">${data.content}</pre>
            `;
}

// STEP 3: The "Clean UI" Trigger
function closeFileView() {
    document.getElementById('file-explorer-view').style.display = "block";
    document.getElementById('file-content-view').style.display = "none";
}

// Auto-load directories when the page opens
window.onload = fetchDirectories;
// --- Navigation Logic ---
function showSection(sectionId) {
    // 1. Hide all sections first
    document.querySelectorAll('.page-section').forEach(s => {
        s.style.display = 'none';
    });

    // 2. Reveal the target section
    const target = document.getElementById(sectionId + '-section');
    if (target) {
        // Use 'flex' instead of 'block' to keep the Orb centered
        target.style.display = 'flex';
    }

    // 3. Trigger specific data loads
    if (sectionId === 'history') loadHistory();
    if (sectionId === 'notes') loadNotes();
}

// --- Existing Core Functions ---
function sendShortcut(command) {
    fetch('/run-shortcut', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ "command": command })
    })
        .then(res => res.json())
        .then(data => {
            document.getElementById('status').innerText = "Eva: " + data.response;

            // --- HIGHLIGHTED FIX: TRIGGER BROWSER VOICE ---
            if (data.audio === "frontend") {
                speakOnBrowser(data.response);
            }
            loadHistory();
        });
}

function sendTextPrompt() {
    const inputField = document.getElementById('userPrompt');
    const userMessage = inputField.value;
    if (userMessage.trim() !== "") {
        sendShortcut(userMessage);
        inputField.value = "";
    }
}

async function toggleListening() {
    const orb = document.getElementById('eva-orb');
    const status = document.getElementById('status');
    const micMode = document.getElementById('mic-select').value;

    orb.classList.add('listening');

    if (micMode === "Frontend") {
        // --- THIS STARTS THE BROWSER RECOGNITION ---
        status.innerText = "Listening through Browser...";
        recognition.start();

        recognition.onresult = async (event) => {
            const transcript = event.results[0][0].transcript;
            document.getElementById('transcript').innerText = "You: " + transcript;

            // Send the actual words to your Python server
            const res = await fetch('/run-eva', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ "transcript": transcript })
            });
            const data = await res.json();
            handleEVAResponse(data);
            orb.classList.remove('listening');
        };
    } else {
        // Standard Laptop Mic Logic
        status.innerText = "Eva is listening (Laptop Mic)...";
        const res = await fetch('/run-eva', { method: 'POST' });
        const data = await res.json();
        handleEVAResponse(data);
        orb.classList.remove('listening');
    }
}

// --- NEW: History & Notes Loaders ---
function loadHistory() {
    // Adding ?v= + new Date().getTime() makes the URL unique every time
    fetch('/task_history.json?v=' + new Date().getTime())
        .then(response => response.json())
        .then(data => {
            const list = document.getElementById('history-list');
            list.innerHTML = data.reverse().map(item => `
                <div class="log-item">
                    <small style="color: #00d2ff;">${item.timestamp}</small><br>
                    <strong>User:</strong> ${item.user}<br>
                    <strong>EVA:</strong> ${item.eva}
                </div>
                <hr class="log-divider">
            `).join('');
        })
        .catch(err => console.log("History Load Error:", err));
}

function loadNotes() {
    fetch('/eva_notes.json').then(res => res.json()).then(data => {
        const list = document.getElementById('notes-list');
        list.innerHTML = data.map(n => `
                    <div class="log-item note-item">
                        <small>${n.timestamp}</small><br>
                        ${n.content}
                    </div>
                `).join('');
    }).catch(() => document.getElementById('notes-list').innerText = "No permanent notes found yet.");
}

function stopSpeaking() {
    // 1. STOP THE PHONE (Frontend)
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel(); // This kills the browser voice instantly
    }

    // 2. STOP THE LAPTOP (Backend)
    fetch('/stop-eva', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log("Backend stop signal sent:", data.response);
            document.getElementById('status').innerText = "Eva: System Silenced.";
        })
        .catch(err => console.error("Could not reach Backend stop:", err));
}

function changeEVAMood() {
    const mood = document.getElementById('mood-select').value;
    fetch('/set-mood', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ "mood": mood })
    });
}
function syncIO() {
    const config = {
        mic: document.getElementById('mic-select').value,
        speaker: document.getElementById('speaker-select').value
    };
    fetch('/update-io', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    });
}

// --- HIGHLIGHTED CHANGE: INITIALIZE WEB SPEECH API ---
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = SpeechRecognition ? new SpeechRecognition() : null;

if (recognition) {
    recognition.lang = 'en-IN';
    recognition.continuous = false;
    recognition.interimResults = false;
}

async function toggleListening() {
    const orb = document.getElementById('eva-orb');
    const status = document.getElementById('status');
    const micMode = document.getElementById('mic-select').value;

    orb.classList.add('listening');

    // --- HIGHLIGHTED CHANGE: LOGIC FOR FRONTEND MIC ---
    if (micMode === "Frontend") {
        if (!recognition) {
            alert("Sir, this browser does not support voice input.");
            orb.classList.remove('listening');
            return;
        }

        status.innerText = "Listening through Phone...";
        recognition.start();

        recognition.onresult = async (event) => {
            const transcript = event.results[0][0].transcript;
            document.getElementById('transcript').innerText = "You (Mobile): " + transcript;

            // Send captured voice text to your Python server
            try {
                const res = await fetch('/run-eva', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ "transcript": transcript })
                });
                const data = await res.json();
                handleEVAResponse(data);
            } catch (err) {
                status.innerText = "Error: Could not reach Python server.";
            } finally {
                orb.classList.remove('listening');
            }
        };

        recognition.onerror = () => {
            status.innerText = "Mic Error. Check permissions, Sir.";
            orb.classList.remove('listening');
        };

    } else {
        // --- CASE B: BACKEND (LAPTOP) MIC ---
        status.innerText = "Eva is listening (Laptop)...";
        try {
            const res = await fetch('/run-eva', { method: 'POST' });
            const data = await res.json();
            handleEVAResponse(data);
        } catch (err) {
            status.innerText = "Error: Laptop mic failed.";
        } finally {
            orb.classList.remove('listening');
        }
    }
}

// --- HIGHLIGHTED CHANGE: UNIFIED RESPONSE HANDLER ---
function handleEVAResponse(data) {
    document.getElementById('status').innerText = "Eva: " + data.response;
    if (data.audio === "frontend") {
        speakOnBrowser(data.response);
    }
    loadHistory();
}

function speakOnBrowser(text) {
    const synth = window.speechSynthesis;
    const utterance = new SpeechSynthesisUtterance(text);
    // Akash, you can change pitch/rate here for your phone's voice
    utterance.rate = 1.0;
    synth.speak(utterance);
}
recognition.onstart = () => {
    console.log("Mic is active and recording...");
    document.getElementById('status').innerText = "🔴 Listening... Speak now!";
};

recognition.onspeechend = () => {
    console.log("Speech finished. Processing...");
    recognition.stop(); // Stop the mic once you finish speaking
};

recognition.onerror = (event) => {
    console.error("Speech Error:", event.error);
    document.getElementById('status').innerText = "Mic Error: " + event.error;
};