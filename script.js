// AKRA AI Assistant - Clean & Intuitive Frontend Controller
let currentUser = null;
let currentRole = "operator";
let isAdmin = false;
let active_mission = "general";
let attachedImageData = null;
let allHistoryLogs = [];
let allAdminUsers = [];

// --- INITIALIZATION & AUTHENTICATION ---

async function checkAuth() {
    try {
        const response = await fetch('/api/auth/me');
        const data = await response.json();
        
        if (!data.authenticated) {
            if (data.banned) {
                alert("ACCESS DENIED: Your Operator account has been suspended by an Administrator.");
            }
            window.location.href = "login.html";
            return false;
        }

        currentUser = data.user;
        currentRole = data.role || "operator";
        isAdmin = !!data.is_admin;

        // Update Operator Profile Display in Sidebar
        const userDisplay = document.getElementById('nav-username');
        const roleDisplay = document.getElementById('nav-user-role');
        const avatarDisplay = document.getElementById('sidebar-avatar');
        const adminLink = document.getElementById('admin-nav-link');

        if (userDisplay) userDisplay.innerText = currentUser;
        if (avatarDisplay) avatarDisplay.innerText = currentUser.substring(0, 2).toUpperCase();
        if (roleDisplay) {
            roleDisplay.innerText = currentRole.toUpperCase();
            roleDisplay.className = isAdmin ? "role-pill admin-badge" : "role-pill";
        }

        if (adminLink) {
            adminLink.style.display = isAdmin ? "flex" : "none";
        }

        return true;
    } catch (err) {
        console.error("Auth check failed:", err);
        window.location.href = "login.html";
        return false;
    }
}

window.onload = async () => {
    const authenticated = await checkAuth();
    if (authenticated) {
        fetchDirectories();
        loadRecentChatFeed();
        setupInputHandlers();
    }
};

// --- SIDEBAR & VIEW NAVIGATION ---

function toggleSidebar(open) {
    const sidebar = document.getElementById('app-sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (!sidebar || !backdrop) return;

    if (open) {
        sidebar.classList.add('open');
        backdrop.classList.add('open');
    } else {
        sidebar.classList.remove('open');
        backdrop.classList.remove('open');
    }
}

function navigateTo(sectionId) {
    toggleSidebar(false); // Close mobile drawer on navigation

    const sections = ['dashboard', 'history', 'notes', 'admin'];
    const titles = {
        'dashboard': 'Chat Console',
        'history': 'Mission Logs',
        'notes': 'Knowledge Bank',
        'admin': 'Admin Command Matrix'
    };

    sections.forEach(id => {
        const el = document.getElementById(id + '-section');
        const navEl = document.getElementById('nav-' + id);
        if (el) el.style.display = 'none';
        if (navEl) navEl.classList.remove('active');
    });

    const target = document.getElementById(sectionId + '-section');
    const targetNav = document.getElementById('nav-' + sectionId) || document.getElementById('admin-nav-link');
    const pageTitle = document.getElementById('page-title');

    if (target) target.style.display = (sectionId === 'dashboard') ? 'flex' : 'block';
    if (targetNav) targetNav.classList.add('active');
    if (pageTitle) pageTitle.innerText = titles[sectionId] || 'AKRA Assistant';

    if (sectionId === 'history') loadHistory();
    if (sectionId === 'notes') loadNotes();
    if (sectionId === 'admin') {
        if (!isAdmin) {
            alert("ACCESS DENIED: Restricted to Administrators.");
            navigateTo('dashboard');
            return;
        }
        loadAdminPanel();
    }
}

function setSystemStatus(text, isBusy = false) {
    const statusText = document.getElementById('status-text');
    const indicator = document.getElementById('system-status-indicator');
    if (statusText) statusText.innerText = text;
    if (indicator) {
        indicator.style.borderColor = isBusy ? "var(--warning)" : "var(--border-subtle)";
    }
}

// --- WORKSPACE DIRECTORIES ---

async function fetchDirectories() {
    try {
        const response = await fetch('/list-directories');
        const data = await response.json();
        const select = document.getElementById('workspace-select');
        if (!select) return;

        select.innerHTML = '';
        const dirs = data.directories || ["general"];
        
        dirs.forEach(dir => {
            const opt = document.createElement('option');
            opt.value = dir;
            opt.innerText = dir.replace(/_/g, ' ').toUpperCase();
            if (dir === active_mission) opt.selected = true;
            select.appendChild(opt);
        });

        updateSectorBadge(active_mission);
    } catch (err) {
        console.error("Failed to load directories:", err);
    }
}

async function changeWorkspaceSelect(dirName) {
    active_mission = dirName;
    updateSectorBadge(dirName);
    try {
        await fetch('/switch-workspace', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ directory: dirName })
        });
        showToast(`Sector switched to: ${dirName.toUpperCase()}`);
    } catch (e) {
        console.error("Error switching workspace:", e);
    }
}

function updateSectorBadge(sectorName) {
    const badge = document.getElementById('topbar-sector-badge');
    if (badge) {
        badge.innerText = `Sector: ${sectorName.toUpperCase()}`;
    }
}

// --- INPUT & TEXTAREA AUTO-RESIZE ---

function setupInputHandlers() {
    const textarea = document.getElementById('userPrompt');
    if (!textarea) return;

    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendTextPrompt();
        }
    });

    textarea.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
}

// --- MARKDOWN & CODE FORMATTING ---

function formatMarkdown(text) {
    if (!text) return "";

    let safe = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Code Blocks: ```lang code ```
    safe = safe.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function(match, lang, code) {
        const safeCode = code.trim();
        const codeId = "code-" + Math.random().toString(36).substr(2, 9);
        return `
            <div class="code-block">
                <div class="code-header">
                    <span>${lang || 'CODE'}</span>
                    <button class="copy-btn" onclick="copyCode('${codeId}')">📋 Copy</button>
                </div>
                <pre><code id="${codeId}">${safeCode}</code></pre>
            </div>
        `;
    });

    // Inline code: `code`
    safe = safe.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    // Bold: **text**
    safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic: *text*
    safe = safe.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Images: ![alt](url)
    safe = safe.replace(/!\[([^\]]*)\]\((https?:\/\/[^\s\)]+)\)/g, '<img src="$2" alt="$1" class="chat-attachment-img" onclick="window.open(\'$2\')">');

    // Links: [text](url)
    safe = safe.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="chat-link">$1 ↗</a>');

    // Bullet list items
    safe = safe.replace(/^\s*[\*\-]\s+(.+)$/gm, '<li>$1</li>');
    safe = safe.replace(/(<li>.*<\/li>)/s, '<ul class="chat-list">$1</ul>');

    // Line breaks
    safe = safe.replace(/\n/g, '<br>');
    safe = safe.replace(/<\/div><br>/g, '</div>');
    safe = safe.replace(/<\/pre><br>/g, '</pre>');

    return safe;
}

function copyCode(elementId) {
    const codeEl = document.getElementById(elementId);
    if (codeEl) {
        navigator.clipboard.writeText(codeEl.innerText).then(() => {
            showToast("Code copied to clipboard!");
        });
    }
}

// --- CHAT STREAM FEED CONTROLLER ---

function appendMessage(sender, text, timestamp = null, imageData = null) {
    const chatFeed = document.getElementById('chat-feed');
    const hero = document.getElementById('welcome-hero');
    if (hero) hero.style.display = "none";

    const isUser = (sender.toLowerCase() === "user" || sender.toLowerCase() === "operator");
    const timeFormatted = timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const msgId = "msg-" + Math.random().toString(36).substr(2, 9);

    const msgDiv = document.createElement('div');
    msgDiv.className = isUser ? "chat-message user-message" : "chat-message akra-message";
    msgDiv.id = msgId;

    let imageHtml = "";
    if (imageData) {
        imageHtml = `<div><img src="${imageData}" alt="Attached Visual" class="chat-attachment-img"></div>`;
    }

    let actionButtons = "";
    if (!isUser) {
        actionButtons = `
            <div class="msg-actions">
                <button class="msg-btn" onclick="speakMessage('${msgId}')">🔊 Speak</button>
                <button class="msg-btn" onclick="copyMessageText('${msgId}')">📄 Copy</button>
            </div>
        `;
    }

    const formattedContent = formatMarkdown(text);

    msgDiv.innerHTML = `
        <div class="msg-avatar">${isUser ? 'OP' : 'AKRA'}</div>
        <div class="msg-content-wrap">
            <div class="msg-header">
                <span>${isUser ? (currentUser || 'Operator') : 'AKRA Core'}</span>
                <span>${timeFormatted}</span>
            </div>
            ${imageHtml}
            <div class="msg-body" id="${msgId}-body">${formattedContent}</div>
            ${actionButtons}
        </div>
    `;

    chatFeed.appendChild(msgDiv);
    scrollChatBottom();
}

function scrollChatBottom() {
    const chatFeed = document.getElementById('chat-feed');
    if (chatFeed) {
        chatFeed.scrollTop = chatFeed.scrollHeight;
    }
}

async function loadRecentChatFeed() {
    try {
        const response = await fetch('/api/chat/history');
        if (!response.ok) return;
        const history = await response.json();
        
        if (Array.isArray(history) && history.length > 0) {
            const recentLogs = history.slice(-20);
            recentLogs.forEach(item => {
                if (item.you) appendMessage("user", item.you, item.timestamp);
                if (item.AKRA) appendMessage("akra", item.AKRA, item.timestamp);
            });
        }
    } catch (err) {
        console.error("Error loading chat feed:", err);
    }
}

function speakMessage(msgId) {
    const bodyEl = document.getElementById(msgId + '-body');
    if (bodyEl) {
        const plainText = bodyEl.innerText || bodyEl.textContent;
        speakOnBrowser(plainText);
    }
}

function copyMessageText(msgId) {
    const bodyEl = document.getElementById(msgId + '-body');
    if (bodyEl) {
        navigator.clipboard.writeText(bodyEl.innerText || bodyEl.textContent).then(() => {
            showToast("Message copied to clipboard.");
        });
    }
}

// --- SENDING PROMPTS & ATTACHMENTS ---

function uploadImage() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';

    fileInput.onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = () => {
            attachedImageData = reader.result;
            const previewContainer = document.getElementById('image-preview-container');
            const previewImg = document.getElementById('image-preview');
            if (previewImg && previewContainer) {
                previewImg.src = attachedImageData;
                previewContainer.style.display = "flex";
            }
            showToast("Visual scan attached.");
        };
        reader.readAsDataURL(file);
    };
    fileInput.click();
}

function clearAttachment() {
    attachedImageData = null;
    const previewContainer = document.getElementById('image-preview-container');
    if (previewContainer) previewContainer.style.display = "none";
}

function quickPrompt(text) {
    const input = document.getElementById('userPrompt');
    if (input) {
        input.value = text;
        sendTextPrompt();
    }
}

async function sendTextPrompt() {
    const input = document.getElementById('userPrompt');
    const userMessage = input.value.trim();
    const imagePayload = attachedImageData;

    if (!userMessage && !imagePayload) return;

    // Display user message in chat
    appendMessage("user", userMessage || "[Visual Inspection]", null, imagePayload);

    // Reset input
    input.value = "";
    input.style.height = 'auto';
    clearAttachment();

    setSystemStatus("Processing...", true);

    // Show Typing indicator
    const typingId = "typing-" + Date.now();
    const chatFeed = document.getElementById('chat-feed');
    const typingDiv = document.createElement('div');
    typingDiv.className = "chat-message akra-message";
    typingDiv.id = typingId;
    typingDiv.innerHTML = `
        <div class="msg-avatar">AKRA</div>
        <div class="msg-content-wrap">
            <div class="typing-dots">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    chatFeed.appendChild(typingDiv);
    scrollChatBottom();

    try {
        const res = await fetch('/run-eva', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                "transcript": userMessage,
                "image_data": imagePayload
            })
        });

        const tEl = document.getElementById(typingId);
        if (tEl) tEl.remove();

        if (res.status === 401) {
            window.location.href = "login.html";
            return;
        }

        if (res.status === 403) {
            const errData = await res.json();
            alert(errData.error || "ACCESS DENIED: Account suspended.");
            window.location.href = "login.html";
            return;
        }

        const data = await res.json();
        let responseText = data.response || "No response.";

        if (responseText.includes("MISSION_PDF_READY:")) {
            const fileName = responseText.split(":")[1].trim();
            responseText = `Sir, your Mission Report PDF is ready.\n\n[📄 Download Mission PDF](/download/${fileName})`;
        }

        appendMessage("akra", responseText);
        setSystemStatus("Ready", false);

        // Voice output
        const speakerMode = document.getElementById('speaker-select').value;
        if (data.audio === "frontend" || speakerMode === "Frontend") {
            const cleanText = responseText
                .replace(/```[\s\S]*?```/g, 'Code snippet provided.')
                .replace(/!\[.*?\]\(.*?\)/g, '')
                .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1')
                .replace(/<[^>]*>?/gm, '');
            speakOnBrowser(cleanText);
        }
    } catch (err) {
        const tEl = document.getElementById(typingId);
        if (tEl) tEl.remove();
        setSystemStatus("Error", false);
        appendMessage("akra", "⚠️ Neural connection timeout. Check network status.");
    }
}

// --- VOICE RECOGNITION ---

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = SpeechRecognition ? new SpeechRecognition() : null;

if (recognition) {
    recognition.lang = 'en-IN';
    recognition.continuous = false;
    recognition.interimResults = true;
}

let isListening = false;

function toggleListening() {
    const micMode = document.getElementById('mic-select').value;
    const overlay = document.getElementById('voice-overlay');
    const transcriptEl = document.getElementById('voice-transcript');
    const micBtn = document.getElementById('mic-btn');

    if (micMode === "Frontend") {
        if (!recognition) {
            alert("Voice input is not supported in this browser. Please use Chrome/Edge or text input.");
            return;
        }

        if (isListening) {
            recognition.stop();
            stopVoiceState();
            return;
        }

        try {
            isListening = true;
            if (overlay) overlay.style.display = "flex";
            if (micBtn) micBtn.classList.add('active');
            if (transcriptEl) transcriptEl.innerText = "Listening... Speak now";
            setSystemStatus("Listening...", true);

            recognition.start();

            recognition.onresult = (event) => {
                let finalTranscript = '';
                let interim = '';

                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;
                    } else {
                        interim += event.results[i][0].transcript;
                    }
                }

                if (transcriptEl) transcriptEl.innerText = finalTranscript || interim || "Listening...";

                if (finalTranscript) {
                    const input = document.getElementById('userPrompt');
                    if (input) input.value = finalTranscript;
                    stopVoiceState();
                    sendTextPrompt();
                }
            };

            recognition.onerror = (e) => {
                console.error("Mic error:", e);
                stopVoiceState();
                showToast("Mic Error: " + (e.error || "Permission Denied"));
            };

            recognition.onend = () => {
                stopVoiceState();
            };

        } catch (e) {
            stopVoiceState();
        }
    } else {
        // Laptop Hardware Mode
        setSystemStatus("Hardware Mic Listening...", true);
        fetch('/run-eva', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                appendMessage("akra", data.response);
                setSystemStatus("Ready", false);
            })
            .catch(() => setSystemStatus("Error", false));
    }
}

function stopVoiceState() {
    isListening = false;
    const overlay = document.getElementById('voice-overlay');
    const micBtn = document.getElementById('mic-btn');
    if (overlay) overlay.style.display = "none";
    if (micBtn) micBtn.classList.remove('active');
    setSystemStatus("Ready", false);
}

function speakOnBrowser(text) {
    if (!('speechSynthesis' in window)) return;
    const synth = window.speechSynthesis;
    synth.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.lang = 'en-IN';

    const voices = synth.getVoices();
    const indVoice = voices.find(v => v.lang === 'en-IN' || v.name.includes('India'));
    if (indVoice) utterance.voice = indVoice;

    synth.speak(utterance);
}

function stopSpeaking() {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }
    fetch('/stop-eva', { method: 'POST' }).catch(console.error);
    showToast("Voice silenced.");
}

function changeEVAMood() {
    const mood = document.getElementById('mood-select').value;
    fetch('/set-mood', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ "mood": mood })
    }).then(() => {
        showToast(`Persona set to ${mood}`);
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
    }).then(() => {
        showToast("Hardware routing updated.");
    });
}

// --- MISSION LOGS & ARCHIVE ---

async function loadHistory() {
    const container = document.getElementById('history-list');
    if (container) container.innerHTML = `<div class="empty-state">Loading mission logs...</div>`;

    try {
        const res = await fetch('/api/chat/history');
        if (res.status === 401) {
            window.location.href = "login.html";
            return;
        }

        const data = await res.json();
        allHistoryLogs = Array.isArray(data) ? data : [];
        renderHistoryLogs(allHistoryLogs);
    } catch (err) {
        if (container) container.innerHTML = `<div class="empty-state">Failed to load logs.</div>`;
    }
}

function renderHistoryLogs(logs) {
    const container = document.getElementById('history-list');
    if (!container) return;

    if (!logs || logs.length === 0) {
        container.innerHTML = `<div class="empty-state">No mission records in this sector.</div>`;
        return;
    }

    const reversed = [...logs].reverse();
    container.innerHTML = reversed.map(item => `
        <div class="history-card">
            <div class="card-meta">
                <span>⏱️ ${item.timestamp || 'N/A'}</span>
                <span class="card-sector">Sector: ${(item.mission || 'General').toUpperCase()}</span>
            </div>
            <div class="card-turn user-turn">
                <strong>You:</strong> ${formatMarkdown(item.you || '')}
            </div>
            <div class="card-turn bot-turn">
                <strong>AKRA:</strong> ${formatMarkdown(item.AKRA || '')}
            </div>
        </div>
    `).join('');
}

function filterHistoryLogs() {
    const query = (document.getElementById('history-search-input').value || '').toLowerCase().trim();
    if (!query) {
        renderHistoryLogs(allHistoryLogs);
        return;
    }
    const filtered = allHistoryLogs.filter(item => 
        (item.you && item.you.toLowerCase().includes(query)) ||
        (item.AKRA && item.AKRA.toLowerCase().includes(query)) ||
        (item.mission && item.mission.toLowerCase().includes(query))
    );
    renderHistoryLogs(filtered);
}

async function clearAllHistory() {
    if (!confirm("Are you sure you want to purge all mission logs?")) return;

    try {
        const res = await fetch('/api/chat/clear', { method: 'DELETE' });
        if (res.ok) {
            allHistoryLogs = [];
            renderHistoryLogs([]);
            showToast("Mission logs cleared.");
        }
    } catch (e) {
        showToast("Error wiping logs.");
    }
}

async function exportCurrentChat() {
    try {
        const res = await fetch('/api/chat/export');
        const data = await res.json();
        if (data.status === 'success') {
            const blob = new Blob([data.transcript], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `AKRA_Logs_${currentUser || 'Operator'}_${Date.now()}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showToast("Mission log downloaded.");
        }
    } catch (e) {
        showToast("Export failed.");
    }
}

// --- PERMANENT KNOWLEDGE BANK ---

async function loadNotes() {
    const container = document.getElementById('notes-list');
    if (container) container.innerHTML = `<div class="empty-state">Loading knowledge bank...</div>`;

    try {
        const res = await fetch('/akra_notes.json');
        const data = await res.json();
        
        if (Array.isArray(data) && data.length > 0) {
            container.innerHTML = data.map(n => `
                <div class="note-card">
                    <div class="card-meta">
                        <span>📌 Memory Timestamp: ${n.timestamp}</span>
                    </div>
                    <div>${formatMarkdown(n.content)}</div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `<div class="empty-state">No permanent memories stored yet.</div>`;
        }
    } catch (err) {
        if (container) container.innerHTML = `<div class="empty-state">Knowledge bank empty.</div>`;
    }
}

async function submitNewNote() {
    const input = document.getElementById('new-note-input');
    const content = input.value.trim();
    if (!content) return;

    try {
        await fetch('/run-eva', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ "transcript": `note this ${content}` })
        });
        input.value = "";
        showToast("Memory committed to Knowledge Bank.");
        loadNotes();
    } catch (e) {
        showToast("Error saving note.");
    }
}

// --- ADMIN PANEL ---

async function loadAdminPanel() {
    const tbody = document.getElementById('admin-users-tbody');
    if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Scanning operator matrix...</td></tr>`;

    try {
        const statsRes = await fetch('/api/admin/stats');
        if (statsRes.ok) {
            const stats = await statsRes.json();
            document.getElementById('stat-total-users').innerText = stats.total_users || 0;
            document.getElementById('stat-active-users').innerText = stats.active_users || 0;
            document.getElementById('stat-banned-users').innerText = stats.banned_users || 0;
            document.getElementById('stat-total-chats').innerText = stats.total_interactions || 0;
        }

        const usersRes = await fetch('/api/admin/users');
        if (!usersRes.ok) {
            tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Admin Clearance Required.</td></tr>`;
            return;
        }

        const data = await usersRes.json();
        allAdminUsers = data.users || [];
        renderAdminUsersTable(allAdminUsers);
    } catch (err) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Error loading operator matrix.</td></tr>`;
    }
}

function renderAdminUsersTable(users) {
    const tbody = document.getElementById('admin-users-tbody');
    if (!tbody) return;

    if (!users || users.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No operators registered.</td></tr>`;
        return;
    }

    tbody.innerHTML = users.map(user => {
        const isBanned = !!user.is_banned;
        const isUserAdmin = (user.role === 'admin');
        const isSelf = (user.username === currentUser);
        const isRoot = !!user.is_immutable;

        const statusBadge = isBanned 
            ? `<span class="table-badge badge-banned">Banned</span>` 
            : `<span class="table-badge badge-active">Active</span>`;

        const roleBadge = isUserAdmin 
            ? `<span class="table-badge badge-admin">Admin</span>` 
            : `<span class="table-badge badge-operator">Operator</span>`;

        let actionButtons = "";
        if (isRoot) {
            actionButtons = `<span style="color: var(--warning); font-size: 0.75rem; font-weight: 600;">🔒 System Root</span>`;
        } else if (isSelf) {
            actionButtons = `<span style="color: var(--primary); font-size: 0.75rem;">Current Session</span>`;
        } else {
            const banBtn = isBanned
                ? `<button class="tbl-btn tbl-btn-unban" onclick="adminUnbanUser('${user.username}')">Unban</button>`
                : `<button class="tbl-btn tbl-btn-ban" onclick="adminBanUser('${user.username}')">Ban</button>`;

            const roleBtn = isUserAdmin
                ? `<button class="tbl-btn tbl-btn-role" onclick="adminChangeRole('${user.username}', 'operator')">Demote</button>`
                : `<button class="tbl-btn tbl-btn-role" onclick="adminChangeRole('${user.username}', 'admin')">Promote</button>`;

            const delBtn = `<button class="tbl-btn tbl-btn-del" onclick="adminDeleteUser('${user.username}')">Delete</button>`;

            actionButtons = `<div class="table-actions">${banBtn} ${roleBtn} ${delBtn}</div>`;
        }

        return `
            <tr>
                <td><strong>${user.username}</strong></td>
                <td>${roleBadge}</td>
                <td>${statusBadge}</td>
                <td>${user.created_at || 'N/A'}</td>
                <td>${user.last_login || 'Never'}</td>
                <td>${user.chat_count || 0}</td>
                <td>${actionButtons}</td>
            </tr>
        `;
    }).join('');
}

function filterAdminUsers() {
    const query = (document.getElementById('admin-search-user').value || '').toLowerCase().trim();
    if (!query) {
        renderAdminUsersTable(allAdminUsers);
        return;
    }
    const filtered = allAdminUsers.filter(u => 
        u.username.toLowerCase().includes(query) || 
        (u.role && u.role.toLowerCase().includes(query))
    );
    renderAdminUsersTable(filtered);
}

async function adminBanUser(username) {
    if (!confirm(`Ban operator '${username}'?`)) return;
    try {
        const res = await fetch('/api/admin/ban', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        if (res.ok) {
            showToast(`Operator '${username}' banned.`);
            loadAdminPanel();
        }
    } catch (e) {
        showToast("Action failed.");
    }
}

async function adminUnbanUser(username) {
    try {
        const res = await fetch('/api/admin/unban', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        if (res.ok) {
            showToast(`Operator '${username}' unbanned.`);
            loadAdminPanel();
        }
    } catch (e) {
        showToast("Action failed.");
    }
}

async function adminDeleteUser(username) {
    if (!confirm(`Permanently delete account for '${username}'?`)) return;
    try {
        const res = await fetch('/api/admin/delete-user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        if (res.ok) {
            showToast(`Operator '${username}' deleted.`);
            loadAdminPanel();
        }
    } catch (e) {
        showToast("Action failed.");
    }
}

async function adminChangeRole(username, newRole) {
    try {
        const res = await fetch('/api/admin/change-role', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, role: newRole })
        });
        if (res.ok) {
            showToast(`Role for '${username}' updated to ${newRole.toUpperCase()}.`);
            loadAdminPanel();
        }
    } catch (e) {
        showToast("Action failed.");
    }
}

// --- TOAST NOTIFICATIONS ---

function showToast(msg) {
    const toast = document.getElementById('akra-toast');
    if (!toast) return;
    toast.innerText = msg;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2800);
}

// --- LOGOUT ---

async function logout() {
    if (confirm("Terminate active session?")) {
        try {
            await fetch('/logout');
            window.location.href = "login.html";
        } catch (err) {
            window.location.href = "login.html";
        }
    }
}
