// AKRA Core Interactive System Controller
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

        // Update UI Operator Profile Badge
        const userDisplay = document.getElementById('nav-username');
        const roleDisplay = document.getElementById('nav-user-role');
        const adminLink = document.getElementById('admin-nav-link');

        if (userDisplay) userDisplay.innerText = currentUser;
        if (roleDisplay) {
            roleDisplay.innerText = currentRole.toUpperCase();
            roleDisplay.className = isAdmin ? "user-role-badge admin-badge" : "user-role-badge";
        }

        // Show Admin link only if admin
        if (adminLink) {
            adminLink.style.display = isAdmin ? "inline-block" : "none";
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
        setupInputListeners();
        updateTimeDisplays();
    }
};

function updateTimeDisplays() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const welcomeTime = document.getElementById('welcome-time');
    if (welcomeTime) welcomeTime.innerText = timeStr;
}

function setupInputListeners() {
    const input = document.getElementById('userPrompt');
    if (input) {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                sendTextPrompt();
            }
        });
    }
}

// --- WORKSPACE & DIRECTORY MANAGEMENT ---

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
    } catch (err) {
        console.error("Failed to load directories:", err);
    }
}

async function changeWorkspaceSelect(dirName) {
    active_mission = dirName;
    try {
        const res = await fetch('/switch-workspace', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ directory: dirName })
        });
        const data = await res.json();
        showNotification(`Workspace sector switched to: ${dirName.toUpperCase()}`);
    } catch (e) {
        console.error("Error switching workspace:", e);
    }
}

// --- NAVIGATION MATRIX ---

function showSection(sectionId) {
    const sections = ['dashboard', 'history', 'notes', 'admin'];
    sections.forEach(id => {
        const el = document.getElementById(id + '-section');
        const navEl = document.getElementById('nav-' + id);
        if (el) el.style.display = 'none';
        if (navEl) navEl.classList.remove('active');
    });

    const target = document.getElementById(sectionId + '-section');
    const targetNav = document.getElementById('nav-' + sectionId) || document.getElementById('admin-nav-link');
    
    if (target) {
        target.style.display = (sectionId === 'dashboard') ? 'flex' : 'block';
    }
    if (targetNav && sectionId !== 'admin') {
        targetNav.classList.add('active');
    }

    if (sectionId === 'history') loadHistory();
    if (sectionId === 'notes') loadNotes();
    if (sectionId === 'admin') {
        if (!isAdmin) {
            alert("ACCESS DENIED: Restricted to System Administrators.");
            showSection('dashboard');
            return;
        }
        loadAdminPanel();
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- MARKDOWN & TEXT FORMATTING HELPER ---

function formatMarkdown(text) {
    if (!text) return "";

    // 1. Sanitize HTML entities
    let safe = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // 2. Format Code Blocks: ```lang \n code \n ```
    safe = safe.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function(match, lang, code) {
        const safeCode = code.trim();
        const codeId = "code-" + Math.random().toString(36).substr(2, 9);
        return `
            <div class="code-block-container">
                <div class="code-block-header">
                    <span class="code-lang-tag">${lang || 'CODE'}</span>
                    <button class="copy-code-btn" onclick="copyCodeBlock('${codeId}')">📋 Copy</button>
                </div>
                <pre class="code-snippet"><code id="${codeId}">${safeCode}</code></pre>
            </div>
        `;
    });

    // 3. Inline code: `code`
    safe = safe.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    // 4. Bold: **text** or __text__
    safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/__([^_]+)__/g, '<strong>$1</strong>');

    // 5. Italic: *text* or _text_
    safe = safe.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    safe = safe.replace(/_([^_]+)_/g, '<em>$1</em>');

    // 6. Markdown Images: ![alt](url)
    safe = safe.replace(/!\[([^\]]*)\]\((https?:\/\/[^\s\)]+)\)/g, '<div class="chat-img-wrapper"><img src="$2" alt="$1" class="chat-generated-img" onclick="window.open(\'$2\')"></div>');

    // 7. Markdown Links: [text](url)
    safe = safe.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="chat-link">$1 ↗</a>');

    // 8. Bullet points
    safe = safe.replace(/^\s*[\*\-]\s+(.+)$/gm, '<li>$1</li>');
    safe = safe.replace(/(<li>.*<\/li>)/s, '<ul class="chat-bullet-list">$1</ul>');

    // 9. Line breaks
    safe = safe.replace(/\n/g, '<br>');

    // Clean up empty br tags in lists and code
    safe = safe.replace(/<\/div><br>/g, '</div>');
    safe = safe.replace(/<\/pre><br>/g, '</pre>');

    return safe;
}

function copyCodeBlock(elementId) {
    const codeEl = document.getElementById(elementId);
    if (codeEl) {
        navigator.clipboard.writeText(codeEl.innerText).then(() => {
            showNotification("Code copied to clipboard!");
        }).catch(() => {
            showNotification("Failed to copy code.");
        });
    }
}

// --- LIVE CHAT STREAM FEED CONTROLLER ---

function appendMessageToFeed(sender, text, timestamp = null, imageData = null) {
    const chatFeed = document.getElementById('chat-feed');
    if (!chatFeed) return;

    const isUser = (sender.toLowerCase() === "user" || sender.toLowerCase() === "operator");
    const timeFormatted = timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const msgId = "msg-" + Math.random().toString(36).substr(2, 9);

    const msgDiv = document.createElement('div');
    msgDiv.className = isUser ? "chat-message user-message" : "chat-message akra-message";
    msgDiv.id = msgId;

    let imageHtml = "";
    if (imageData) {
        imageHtml = `<div class="chat-attachment-bubble"><img src="${imageData}" alt="Attached Visual Scan"></div>`;
    }

    let actionButtons = "";
    if (!isUser) {
        actionButtons = `
            <div class="msg-footer-actions">
                <button class="msg-tool-btn" onclick="speakMessage('${msgId}')" title="Read aloud">🔊 Speak</button>
                <button class="msg-tool-btn" onclick="copyMessageText('${msgId}')" title="Copy response">📄 Copy</button>
            </div>
        `;
    }

    const formattedContent = formatMarkdown(text);

    msgDiv.innerHTML = `
        <div class="msg-avatar">${isUser ? 'OP' : 'AKRA'}</div>
        <div class="msg-content-wrapper">
            <div class="msg-meta">
                <span class="msg-sender">${isUser ? (currentUser || 'Operator') : 'AKRA Core'}</span>
                <span class="msg-time">${timeFormatted}</span>
            </div>
            ${imageHtml}
            <div class="msg-body" id="${msgId}-content">${formattedContent}</div>
            ${actionButtons}
        </div>
    `;

    chatFeed.appendChild(msgDiv);
    scrollChatFeedToBottom();
}

function scrollChatFeedToBottom() {
    const chatFeed = document.getElementById('chat-feed');
    if (chatFeed) {
        chatFeed.scrollTop = chatFeed.scrollHeight;
    }
}

function clearLiveChatFeed() {
    const chatFeed = document.getElementById('chat-feed');
    if (chatFeed) {
        chatFeed.innerHTML = `
            <div class="chat-message akra-message">
                <div class="msg-avatar">AKRA</div>
                <div class="msg-content-wrapper">
                    <div class="msg-meta">
                        <span class="msg-sender">AKRA Core</span>
                        <span class="msg-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div class="msg-body">
                        Stream purged. Standing by for new commands, Operator.
                    </div>
                </div>
            </div>
        `;
    }
    showNotification("Live chat feed cleared.");
}

async function loadRecentChatFeed() {
    try {
        const response = await fetch('/api/chat/history');
        if (!response.ok) return;
        const history = await response.json();
        
        if (Array.isArray(history) && history.length > 0) {
            const recentLogs = history.slice(-15);
            recentLogs.forEach(item => {
                if (item.you) {
                    appendMessageToFeed("user", item.you, item.timestamp);
                }
                if (item.AKRA) {
                    appendMessageToFeed("akra", item.AKRA, item.timestamp);
                }
            });
        }
    } catch (err) {
        console.error("Error loading chat feed:", err);
    }
}

function speakMessage(msgId) {
    const contentEl = document.getElementById(msgId + '-content');
    if (contentEl) {
        const plainText = contentEl.innerText || contentEl.textContent;
        speakOnBrowser(plainText);
    }
}

function copyMessageText(msgId) {
    const contentEl = document.getElementById(msgId + '-content');
    if (contentEl) {
        const plainText = contentEl.innerText || contentEl.textContent;
        navigator.clipboard.writeText(plainText).then(() => {
            showNotification("Response text copied to clipboard.");
        });
    }
}

// --- SENDING COMMANDS & IMAGE ATTACHMENTS ---

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
            document.getElementById('status').innerText = "AKRA: Visual data attached. Transmit your query.";
        };
        reader.readAsDataURL(file);
    };
    fileInput.click();
}

function clearAttachment() {
    attachedImageData = null;
    const previewContainer = document.getElementById('image-preview-container');
    if (previewContainer) previewContainer.style.display = "none";
    document.getElementById('status').innerText = "AKRA: Attachment removed.";
}

function quickPrompt(promptText) {
    const inputField = document.getElementById('userPrompt');
    if (inputField) {
        inputField.value = promptText;
        sendTextPrompt();
    }
}

async function sendTextPrompt() {
    const inputField = document.getElementById('userPrompt');
    const userMessage = inputField.value.trim();
    const status = document.getElementById('status');
    const imagePayload = attachedImageData;

    if (!userMessage && !imagePayload) {
        return;
    }

    appendMessageToFeed("user", userMessage || "[Visual Inspection Request]", null, imagePayload);
    
    inputField.value = "";
    clearAttachment();

    status.innerText = "AKRA: Processing neural query...";
    
    const typingId = "typing-" + Date.now();
    const chatFeed = document.getElementById('chat-feed');
    const typingDiv = document.createElement('div');
    typingDiv.className = "chat-message akra-message typing-bubble";
    typingDiv.id = typingId;
    typingDiv.innerHTML = `
        <div class="msg-avatar">AKRA</div>
        <div class="msg-content-wrapper">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    chatFeed.appendChild(typingDiv);
    scrollChatFeedToBottom();

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
        handleAKRAResponse(data);
    } catch (err) {
        const tEl = document.getElementById(typingId);
        if (tEl) tEl.remove();
        status.innerText = "System Error: Neural communication timeout.";
        appendMessageToFeed("akra", "⚠️ Neural connection lost. Check network or server status.");
    }
}

function handleAKRAResponse(data) {
    let responseText = data.response || "No response received.";
    const status = document.getElementById('status');

    if (responseText.includes("MISSION_PDF_READY:")) {
        const fileName = responseText.split(":")[1].trim();
        responseText = `Sir, your Mission PDF Report has been generated successfully.\n\n[📄 Download Mission PDF](/download/${fileName})`;
    }

    appendMessageToFeed("akra", responseText);
    status.innerText = "AKRA: Command executed.";

    const speakerMode = document.getElementById('speaker-select').value;
    if (data.audio === "frontend" || speakerMode === "Frontend") {
        const cleanForSpeech = responseText
            .replace(/```[\s\S]*?```/g, 'Code block generated.')
            .replace(/!\[.*?\]\(.*?\)/g, 'Image visualized.')
            .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1')
            .replace(/<[^>]*>?/gm, '');
        speakOnBrowser(cleanForSpeech);
    }
}

// --- VOICE RECOGNITION (WEB SPEECH API) ---

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = SpeechRecognition ? new SpeechRecognition() : null;

if (recognition) {
    recognition.lang = 'en-IN';
    recognition.continuous = false;
    recognition.interimResults = true;
}

let isListening = false;

async function toggleListening() {
    const orb = document.getElementById('eva-orb');
    const status = document.getElementById('status');
    const transcriptBanner = document.getElementById('voice-transcript');
    const micMode = document.getElementById('mic-select').value;

    if (micMode === "Frontend") {
        if (!recognition) {
            alert("Voice input is not supported in this browser. Please use Chrome, Edge, or text input.");
            return;
        }

        if (isListening) {
            recognition.stop();
            return;
        }

        try {
            isListening = true;
            orb.classList.add('listening');
            status.innerText = "🔴 Listening... Speak clearly into your mic";
            if (transcriptBanner) {
                transcriptBanner.innerText = "Listening...";
                transcriptBanner.style.display = "block";
            }

            recognition.start();

            recognition.onresult = (event) => {
                let interim = '';
                let finalTranscript = '';

                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;
                    } else {
                        interim += event.results[i][0].transcript;
                    }
                }

                if (transcriptBanner) {
                    transcriptBanner.innerText = finalTranscript || interim || "Listening...";
                }

                if (finalTranscript) {
                    const inputField = document.getElementById('userPrompt');
                    if (inputField) inputField.value = finalTranscript;
                    sendTextPrompt();
                }
            };

            recognition.onerror = (e) => {
                console.error("Mic error:", e);
                status.innerText = "Mic Error: " + (e.error || "Permission Denied");
                stopListeningState();
            };

            recognition.onend = () => {
                stopListeningState();
            };

        } catch (e) {
            console.error(e);
            stopListeningState();
        }

    } else {
        status.innerText = "AKRA is listening via Laptop hardware mic...";
        orb.classList.add('listening');
        try {
            const res = await fetch('/run-eva', { method: 'POST' });
            const data = await res.json();
            handleAKRAResponse(data);
        } catch (err) {
            status.innerText = "Error: Hardware mic failed.";
        } finally {
            orb.classList.remove('listening');
        }
    }
}

function stopListeningState() {
    isListening = false;
    const orb = document.getElementById('eva-orb');
    const transcriptBanner = document.getElementById('voice-transcript');
    if (orb) orb.classList.remove('listening');
    if (transcriptBanner) transcriptBanner.style.display = "none";
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
    fetch('/stop-eva', { method: 'POST' })
        .then(() => {
            document.getElementById('status').innerText = "AKRA: System Silenced.";
            showNotification("Voice playback terminated.");
        })
        .catch(console.error);
}

function changeEVAMood() {
    const mood = document.getElementById('mood-select').value;
    fetch('/set-mood', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ "mood": mood })
    }).then(() => {
        showNotification(`Persona shifted to ${mood} mode.`);
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
        showNotification("Hardware routing configuration synced.");
    });
}

// --- ADMIN PANEL CONTROLLER ---

async function loadAdminPanel() {
    const tbody = document.getElementById('admin-users-tbody');
    if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="loading-cell">Scanning operator matrix...</td></tr>`;

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
            tbody.innerHTML = `<tr><td colspan="7" class="error-cell">Admin Clearance Required.</td></tr>`;
            return;
        }

        const data = await usersRes.json();
        allAdminUsers = data.users || [];
        renderAdminUsersTable(allAdminUsers);
    } catch (err) {
        console.error("Admin Load Error:", err);
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="error-cell">System Error loading admin matrix.</td></tr>`;
    }
}

function renderAdminUsersTable(users) {
    const tbody = document.getElementById('admin-users-tbody');
    if (!tbody) return;

    if (!users || users.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-cell">No operators registered in sector.</td></tr>`;
        return;
    }

    tbody.innerHTML = users.map(user => {
        const isBanned = !!user.is_banned;
        const isUserAdmin = (user.role === 'admin');
        const isSelf = (user.username === currentUser);
        const isRoot = !!user.is_immutable;

        const statusBadge = isBanned 
            ? `<span class="badge badge-banned">🚫 BANNED</span>` 
            : `<span class="badge badge-active">🟢 ACTIVE</span>`;

        const roleBadge = isUserAdmin 
            ? `<span class="badge badge-admin">⚡ ADMIN</span>` 
            : `<span class="badge badge-operator">OPERATOR</span>`;

        let actionButtons = "";
        if (isRoot) {
            actionButtons = `<span class="tag-immutable">🔒 SYSTEM ROOT</span>`;
        } else if (isSelf) {
            actionButtons = `<span class="tag-self">CURRENT SESSION</span>`;
        } else {
            const banBtn = isBanned
                ? `<button class="admin-action-btn btn-unban" onclick="adminUnbanUser('${user.username}')">🔓 Unban</button>`
                : `<button class="admin-action-btn btn-ban" onclick="adminBanUser('${user.username}')">🚫 Ban</button>`;

            const roleBtn = isUserAdmin
                ? `<button class="admin-action-btn btn-demote" onclick="adminChangeRole('${user.username}', 'operator')">Demote</button>`
                : `<button class="admin-action-btn btn-promote" onclick="adminChangeRole('${user.username}', 'admin')">Promote</button>`;

            const deleteBtn = `<button class="admin-action-btn btn-delete" onclick="adminDeleteUser('${user.username}')">🗑️ Delete</button>`;

            actionButtons = `<div class="action-btn-group">${banBtn} ${roleBtn} ${deleteBtn}</div>`;
        }

        return `
            <tr class="${isBanned ? 'row-banned' : ''}">
                <td class="operator-id-cell"><strong>${user.username}</strong></td>
                <td>${roleBadge}</td>
                <td>${statusBadge}</td>
                <td class="time-cell">${user.created_at || 'N/A'}</td>
                <td class="time-cell">${user.last_login || 'Never'}</td>
                <td class="numeric-cell">${user.chat_count || 0}</td>
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
    if (!confirm(`Are you sure you want to BAN operator '${username}'? They will be immediately blocked from the system.`)) return;

    try {
        const res = await fetch('/api/admin/ban', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const data = await res.json();
        if (res.ok) {
            showNotification(`Operator '${username}' has been banned.`);
            loadAdminPanel();
        } else {
            alert(data.message || "Action failed.");
        }
    } catch (e) {
        alert("Server error banning operator.");
    }
}

async function adminUnbanUser(username) {
    try {
        const res = await fetch('/api/admin/unban', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const data = await res.json();
        if (res.ok) {
            showNotification(`Operator '${username}' access restored.`);
            loadAdminPanel();
        } else {
            alert(data.message || "Action failed.");
        }
    } catch (e) {
        alert("Server error unbanning operator.");
    }
}

async function adminDeleteUser(username) {
    if (!confirm(`⚠️ DANGER: Permanently delete account for '${username}'? This cannot be undone.`)) return;

    try {
        const res = await fetch('/api/admin/delete-user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const data = await res.json();
        if (res.ok) {
            showNotification(`Operator '${username}' account deleted.`);
            loadAdminPanel();
        } else {
            alert(data.message || "Action failed.");
        }
    } catch (e) {
        alert("Server error deleting operator.");
    }
}

async function adminChangeRole(username, newRole) {
    try {
        const res = await fetch('/api/admin/change-role', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, role: newRole })
        });
        const data = await res.json();
        if (res.ok) {
            showNotification(`Role for '${username}' changed to ${newRole.toUpperCase()}.`);
            loadAdminPanel();
        } else {
            alert(data.message || "Action failed.");
        }
    } catch (e) {
        alert("Server error changing role.");
    }
}

// --- MISSION LOGS & ARCHIVE ---

async function loadHistory() {
    const list = document.getElementById('history-list');
    if (list) list.innerHTML = `<p class="loading">Loading mission logs...</p>`;

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
        console.error("History load error:", err);
        if (list) list.innerHTML = `<p class="error">Failed to load mission logs.</p>`;
    }
}

function renderHistoryLogs(logs) {
    const list = document.getElementById('history-list');
    if (!list) return;

    if (!logs || logs.length === 0) {
        list.innerHTML = `<div class="empty-logs">No mission logs recorded in your sector yet.</div>`;
        return;
    }

    const reversed = [...logs].reverse();
    list.innerHTML = reversed.map((item) => `
        <div class="log-item">
            <div class="log-header">
                <span class="log-timestamp">⏱️ ${item.timestamp || 'N/A'}</span>
                <span class="log-sector">Sector: ${item.mission || 'General'}</span>
            </div>
            <div class="log-body">
                <div class="log-turn user-turn">
                    <strong>OPERATOR:</strong> ${formatMarkdown(item.you || '')}
                </div>
                <div class="log-turn akra-turn">
                    <strong>AKRA:</strong> ${formatMarkdown(item.AKRA || '')}
                </div>
            </div>
        </div>
        <hr class="log-divider">
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
    if (!confirm("Are you sure you want to wipe all mission history logs in your private sector?")) return;

    try {
        const res = await fetch('/api/chat/clear', { method: 'DELETE' });
        if (res.ok) {
            allHistoryLogs = [];
            renderHistoryLogs([]);
            clearLiveChatFeed();
            showNotification("Mission history purged.");
        }
    } catch (e) {
        alert("Failed to clear history.");
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
            a.download = `AKRA_Mission_Log_${currentUser || 'Operator'}_${Date.now()}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showNotification("Mission log exported to file.");
        }
    } catch (e) {
        alert("Failed to export chat logs.");
    }
}

// --- PERMANENT KNOWLEDGE BANK (NOTES) ---

async function loadNotes() {
    const list = document.getElementById('notes-list');
    if (list) list.innerHTML = `<p class="loading">Loading permanent memories...</p>`;

    try {
        const res = await fetch('/akra_notes.json');
        const data = await res.json();
        
        if (Array.isArray(data) && data.length > 0) {
            list.innerHTML = data.map(n => `
                <div class="note-item">
                    <small>📌 ${n.timestamp}</small>
                    <div class="note-content">${formatMarkdown(n.content)}</div>
                </div>
            `).join('');
        } else {
            list.innerHTML = `<div class="empty-logs">No permanent notes stored.</div>`;
        }
    } catch (err) {
        if (list) list.innerHTML = `<div class="empty-logs">No permanent knowledge files found.</div>`;
    }
}

async function submitNewNote() {
    const input = document.getElementById('new-note-input');
    const content = input.value.trim();
    if (!content) return;

    try {
        const res = await fetch('/run-eva', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ "transcript": `note this ${content}` })
        });
        const data = await res.json();
        input.value = "";
        showNotification("Rule committed to Permanent Knowledge Bank.");
        loadNotes();
    } catch (e) {
        alert("Error saving permanent note.");
    }
}

// --- NOTIFICATION TOAST HELPER ---

function showNotification(msg) {
    let toast = document.getElementById('akra-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'akra-toast';
        toast.className = 'akra-toast';
        document.body.appendChild(toast);
    }
    toast.innerText = `⚡ ${msg}`;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// --- TERMINATE SESSION / LOGOUT ---

async function logout() {
    if (confirm("Terminate active neural session and lock operator console?")) {
        try {
            await fetch('/logout');
            window.location.href = "login.html";
        } catch (err) {
            window.location.href = "login.html";
        }
    }
}
