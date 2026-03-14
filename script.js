
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
    // Hide ALL sections first
    const sections = ['dashboard', 'history', 'notes'];
    sections.forEach(id => {
        const el = document.getElementById(id + '-section');
        if (el) el.style.display = 'none';
    });

    // Show ONLY the requested section
    const target = document.getElementById(sectionId + '-section');
    if (target) {
        target.style.display = (sectionId === 'dashboard') ? 'flex' : 'block';
    }

    // Load data for specific sections
    if (sectionId === 'history') loadHistory();
    if (sectionId === 'notes') loadNotes();

    // Scroll to top so the new view is clear
    window.scrollTo(0, 0);
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
            document.getElementById('status').innerText = "AKRA: " + data.response;

            // --- HIGHLIGHTED FIX: TRIGGER BROWSER VOICE ---
            if (data.audio === "frontend") {
                speakOnBrowser(data.response);
            }
            loadHistory();
        });
}

// This only ATTACHES the image
function uploadImage() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';

    fileInput.onchange = (e) => {
        const file = e.target.files[0];
        const reader = new FileReader();

        reader.onload = () => {
            attachedImageData = reader.result;

            // Show the thumbnail preview
            const previewContainer = document.getElementById('image-preview-container');
            const previewImg = document.getElementById('image-preview');
            previewImg.src = attachedImageData;
            previewContainer.style.display = "block";

            document.getElementById('status').innerText = `AKRA: Image ready. Ask your question, Sir.`;
        };
        reader.readAsDataURL(file);
    };
    fileInput.click();
}

function clearAttachment() {
    attachedImageData = null;
    document.getElementById('image-preview-container').style.display = "none";
    document.getElementById('status').innerText = "AKRA: Attachment cleared.";
}

// Update sendTextPrompt to clear the preview on success
async function sendTextPrompt() {
    const inputField = document.getElementById('userPrompt');
    const userMessage = inputField.value;
    const status = document.getElementById('status');

    if (userMessage.trim() !== "" || attachedImageData) {
        status.innerText = "AKRA: Synchronizing visual and text data...";

        try {
            const res = await fetch('/run-eva', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    "transcript": userMessage,
                    "image_data": attachedImageData
                })
            });

            const data = await res.json();
            handleEVAResponse(data);

            // Reset everything
            clearAttachment();
            inputField.value = "";
        } catch (err) {
            status.innerText = "System Error: Failed to reach the visual core.";
        }
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
                    <strong>you:</strong> ${item.you}<br>
                    <strong>AKRA:</strong> ${item.AKRA}
                </div>
                <hr class="log-divider">
            `).join('');
        })
        .catch(err => console.log("History Load Error:", err));
}

function loadNotes() {
    fetch('/akra_notes.json').then(res => res.json()).then(data => {
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
            document.getElementById('status').innerText = "AKRA: System Silenced.";
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
        status.innerText = "AKRA is listening (Laptop)...";
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
    let responseText = data.response;
    const chatResults = document.getElementById('chat-results-area');

    // Turn the raw code into a button
    if (responseText.includes("MISSION_PDF_READY:")) {
        const fileName = responseText.split(":")[1];
        responseText = `Sir, your Mission Report is ready.<br><br>
                        <a href="/download/${fileName}" target="_blank" class="send-btn" style="text-decoration:none;">📄 Download PDF</a>`;
    }

    // Inject the result into the specific results area
    if (chatResults) {
        chatResults.innerHTML = `<div class="log-item"><strong>AKRA:</strong> ${responseText}</div>`;
    }

    document.getElementById('status').innerText = "AKRA: Task Complete.";
    // Check if we should speak through the Browser/Phone
    if (data.audio === "frontend" || document.getElementById('speaker-select').value === "Frontend") {
        // We strip HTML tags like <br> so the AI doesn't literally say "B R"
        const cleanText = data.response.replace(/<[^>]*>?/gm, '');
        speakOnBrowser(cleanText);
    }
}
function speakOnBrowser(text) {
    const synth = window.speechSynthesis;
    // If a voice is already playing, cancel it first
    synth.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.lang = 'en-IN'; // Uses the Indian accent you prefer

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

// Keep-Alive Heartbeat
setInterval(async () => {
    try {
        const response = await fetch('/ping'); // We will create this route in Flask
        const data = await response.json();
        console.log("Heartbeat sent: Service is Live", data.time);
    } catch (error) {
        console.error("Heartbeat failed: Service might be sleeping", error);
    }
}, 600000); // 10 minutes

