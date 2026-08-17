// Grandma Chen's Care Coordinator - Frontend Logic (Modern Instagram Edition)

let currentRetrievalMode = 'sql';
let currentActiveTab = 'chat';
let warmUpTimer = null;

// DOM Elements
const CID_DISPLAY = document.getElementById('cid-display');
const DEV_DRAWER = document.getElementById('dev-drawer');
const DEV_TOGGLE_BTN = document.getElementById('dev-toggle-btn');
const THEME_TOGGLE_BTN = document.getElementById('theme-toggle-btn');
const VIEW_TITLE = document.getElementById('view-title');

const TAB_CHAT = document.getElementById('tab-chat');
const TAB_CARELOG = document.getElementById('tab-carelog');
const VIEW_CHAT = document.getElementById('view-chat');
const VIEW_CARELOG = document.getElementById('view-carelog');
const NAV_NOTE_COUNT = document.getElementById('nav-note-count');

const CHAT_HISTORY = document.getElementById('chat-history');
const CHAT_MESSAGES_CONTAINER = document.getElementById('chat-messages-container');
const CHAT_FORM = document.getElementById('chat-form');
const CHAT_INPUT = document.getElementById('chat-input');
const CHAT_SEND_BTN = document.getElementById('chat-send-btn');
const SIMULATE_BTN = document.getElementById('simulate-btn');
const CHAT_WARMUP_BANNER = document.getElementById('chat-warmup-banner');
const CHAT_LOADING_INDICATOR = document.getElementById('chat-loading-indicator');
const CHAT_LOADING_TEXT = document.getElementById('chat-loading-text');

const NOTE_FORM = document.getElementById('note-form');
const CAREGIVER_INPUT = document.getElementById('caregiver-input');
const CAREGIVER_ERROR = document.getElementById('caregiver-error');
const TYPE_SELECT = document.getElementById('type-select');
const CONTENT_INPUT = document.getElementById('content-input');
const CONTENT_ERROR = document.getElementById('content-error');
const NOTE_BTN = document.getElementById('note-btn');
const NOTE_STATUS = document.getElementById('note-status');
const FEED_COUNT = document.getElementById('feed-count');
const NOTES_LIST = document.getElementById('notes-list');

// ============================================================================
// THEME CONTROLLER (Dark / Light Mode)
// ============================================================================

const SUN_SVG = `<svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`;
const MOON_SVG = `<svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;

function updateThemeIcon(theme) {
    if (!THEME_TOGGLE_BTN) return;
    if (theme === 'dark') {
        THEME_TOGGLE_BTN.innerHTML = SUN_SVG;
        THEME_TOGGLE_BTN.title = 'Switch to Light Mode';
    } else {
        THEME_TOGGLE_BTN.innerHTML = MOON_SVG;
        THEME_TOGGLE_BTN.title = 'Switch to Dark Mode';
    }
}

function initTheme() {
    const savedTheme = localStorage.getItem('care_coordinator_theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialTheme = savedTheme || (prefersDark ? 'dark' : 'light');

    document.documentElement.setAttribute('data-theme', initialTheme);
    updateThemeIcon(initialTheme);
}

function toggleThemeMode() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';

    document.documentElement.setAttribute('data-theme', nextTheme);
    localStorage.setItem('care_coordinator_theme', nextTheme);
    updateThemeIcon(nextTheme);
}

initTheme();

// ============================================================================
// TAB NAVIGATION CONTROLLER (Sidebar Switcher)
// ============================================================================

function switchTab(tabName) {
    currentActiveTab = tabName === 'carelog' ? 'carelog' : 'chat';

    if (currentActiveTab === 'chat') {
        if (TAB_CHAT) {
            TAB_CHAT.classList.add('active');
            TAB_CHAT.setAttribute('aria-selected', 'true');
            TAB_CHAT.setAttribute('tabindex', '0');
        }
        if (TAB_CARELOG) {
            TAB_CARELOG.classList.remove('active');
            TAB_CARELOG.setAttribute('aria-selected', 'false');
            TAB_CARELOG.setAttribute('tabindex', '-1');
        }
        if (VIEW_CHAT) {
            VIEW_CHAT.classList.add('active');
            VIEW_CHAT.removeAttribute('hidden');
        }
        if (VIEW_CARELOG) {
            VIEW_CARELOG.classList.remove('active');
            VIEW_CARELOG.setAttribute('hidden', '');
        }
        if (VIEW_TITLE) {
            VIEW_TITLE.innerText = 'Coordinator Assistant';
        }
        if (CHAT_INPUT && !CHAT_INPUT.disabled) {
            CHAT_INPUT.focus();
        }
        scrollToBottom();
    } else {
        if (TAB_CARELOG) {
            TAB_CARELOG.classList.add('active');
            TAB_CARELOG.setAttribute('aria-selected', 'true');
            TAB_CARELOG.setAttribute('tabindex', '0');
        }
        if (TAB_CHAT) {
            TAB_CHAT.classList.remove('active');
            TAB_CHAT.setAttribute('aria-selected', 'false');
            TAB_CHAT.setAttribute('tabindex', '-1');
        }
        if (VIEW_CARELOG) {
            VIEW_CARELOG.classList.add('active');
            VIEW_CARELOG.removeAttribute('hidden');
        }
        if (VIEW_CHAT) {
            VIEW_CHAT.classList.remove('active');
            VIEW_CHAT.setAttribute('hidden', '');
        }
        if (VIEW_TITLE) {
            VIEW_TITLE.innerText = 'Care Log & Memory Stream';
        }
        if (CAREGIVER_INPUT && !CAREGIVER_INPUT.disabled) {
            CAREGIVER_INPUT.focus();
        }
    }
}

// Accessible arrow-key navigation between sidebar tabs
const sidebarNavList = document.querySelector('.sidebar-nav-list');
if (sidebarNavList) {
    sidebarNavList.addEventListener('keydown', (e) => {
        const tabs = [TAB_CHAT, TAB_CARELOG].filter(Boolean);
        const currentIndex = tabs.findIndex(tab => tab === document.activeElement);
        if (currentIndex === -1) return;

        let targetIndex = currentIndex;
        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
            e.preventDefault();
            targetIndex = (currentIndex + 1) % tabs.length;
            tabs[targetIndex].focus();
            switchTab(tabs[targetIndex] === TAB_CARELOG ? 'carelog' : 'chat');
        } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
            e.preventDefault();
            targetIndex = (currentIndex - 1 + tabs.length) % tabs.length;
            tabs[targetIndex].focus();
            switchTab(tabs[targetIndex] === TAB_CARELOG ? 'carelog' : 'chat');
        } else if (e.key === 'Home') {
            e.preventDefault();
            tabs[0].focus();
            switchTab('chat');
        } else if (e.key === 'End') {
            e.preventDefault();
            tabs[tabs.length - 1].focus();
            switchTab('carelog');
        }
    });
}

// ============================================================================
// DEVELOPER INFO DRAWER
// ============================================================================

function toggleDevDrawer() {
    if (!DEV_DRAWER) return;
    const isOpen = DEV_DRAWER.classList.toggle('open');
    if (DEV_TOGGLE_BTN) {
        DEV_TOGGLE_BTN.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    }
}

// ============================================================================
// RETRIEVAL ENGINE MODE SWITCH
// ============================================================================

function setRetrievalMode(mode) {
    currentRetrievalMode = mode === 'mcp' ? 'mcp' : 'sql';
    const btnSql = document.getElementById('mode-btn-sql');
    const btnMcp = document.getElementById('mode-btn-mcp');

    if (btnSql && btnMcp) {
        if (currentRetrievalMode === 'mcp') {
            btnSql.classList.remove('active');
            btnSql.setAttribute('aria-pressed', 'false');
            btnMcp.classList.add('active');
            btnMcp.setAttribute('aria-pressed', 'true');
        } else {
            btnMcp.classList.remove('active');
            btnMcp.setAttribute('aria-pressed', 'false');
            btnSql.classList.add('active');
            btnSql.setAttribute('aria-pressed', 'true');
        }
    }
}

// ============================================================================
// CHAT & MESSAGE BUBBLES
// ============================================================================

function scrollToBottom() {
    if (CHAT_HISTORY) {
        CHAT_HISTORY.scrollTop = CHAT_HISTORY.scrollHeight;
    }
}

function showLoadingIndicator(mode) {
    if (!CHAT_LOADING_INDICATOR || !CHAT_LOADING_TEXT) return;
    if (mode === 'mcp') {
        CHAT_LOADING_TEXT.innerText = 'Querying via CockroachDB Cloud MCP Server...';
    } else {
        CHAT_LOADING_TEXT.innerText = 'Querying via Direct SQL...';
    }
    CHAT_LOADING_INDICATOR.classList.add('visible');
}

function hideLoadingIndicator() {
    if (CHAT_LOADING_INDICATOR) {
        CHAT_LOADING_INDICATOR.classList.remove('visible');
    }
}

function appendMessage(role, content, hasConflict = false, receipt = null) {
    const targetContainer = CHAT_MESSAGES_CONTAINER || CHAT_HISTORY;
    if (!targetContainer) return;

    const msgRow = document.createElement('div');
    msgRow.className = `chat-message-row ${role}`;
    if (hasConflict) msgRow.classList.add('has-conflict');

    const metaSpan = document.createElement('span');
    metaSpan.className = 'msg-author-header';
    metaSpan.innerText = role === 'user' ? 'You' : 'Grandma Chen Coordinator Assistant';

    const bubbleContainer = document.createElement('div');
    bubbleContainer.className = 'msg-bubble-container';

    if (role === 'assistant') {
        let innerHtml = '';
        if (hasConflict) {
            innerHtml += '<div class="conflict-flag-badge"><svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> <span>Discrepancy / Mismatch Flagged</span></div>';
        }
        if (window.marked && typeof marked.parse === 'function') {
            innerHtml += marked.parse(content);
        } else {
            innerHtml += escapeHtml(content);
        }
        bubbleContainer.innerHTML = innerHtml;
    } else {
        bubbleContainer.innerText = content;
    }

    msgRow.appendChild(metaSpan);
    msgRow.appendChild(bubbleContainer);

    // Collapsed-by-default retrieval receipt panel
    if (role === 'assistant' && receipt) {
        const isMcp = (receipt.method_label && receipt.method_label.includes('MCP')) || receipt.cte_restructured !== undefined;
        const receiptPanel = document.createElement('details');
        receiptPanel.className = `retrieval-receipt-box ${isMcp ? 'receipt-mcp' : 'receipt-sql'}`;

        let receiptHtml = `
            <summary class="receipt-summary-bar">
                <span class="receipt-tag ${isMcp ? 'badge-mcp' : 'badge-sql'}">
                    ${isMcp ? 'MCP Server' : 'Direct SQL'}
                </span>
                <span class="receipt-title">Retrieval Receipt & Verification</span>
                <span class="receipt-ms-badge">${receipt.latency_ms} ms</span>
                <span class="receipt-arrow-icon" aria-hidden="true">▼</span>
            </summary>
            <div class="receipt-details-body">
                <div class="receipt-info-row">
                    <span class="receipt-k-label">Method:</span>
                    <span class="receipt-v-value">${escapeHtml(receipt.method_label)}</span>
                </div>
                <div class="receipt-info-row">
                    <span class="receipt-k-label">Mechanism:</span>
                    <span class="receipt-v-value">${escapeHtml(receipt.description)}</span>
                </div>
                <div class="receipt-info-row">
                    <span class="receipt-k-label">Measured Latency:</span>
                    <span class="receipt-v-value">${receipt.latency_ms} ms</span>
                </div>
        `;

        if (receipt.cte_restructured !== undefined) {
            receiptHtml += `
                <div class="receipt-info-row">
                    <span class="receipt-k-label">16KB Limit CTE Query:</span>
                    <span class="receipt-v-value cte-highlight">${receipt.cte_restructured ? 'Applied (WITH qv AS vector CTE)' : 'Not Required'}</span>
                </div>
            `;
        }

        receiptHtml += `</div>`;
        receiptPanel.innerHTML = receiptHtml;
        msgRow.appendChild(receiptPanel);
    }

    targetContainer.appendChild(msgRow);
    scrollToBottom();

    return msgRow;
}

async function sendChatMessage(question) {
    if (!question) return;

    if (currentActiveTab !== 'chat') {
        switchTab('chat');
    }

    appendMessage('user', question);

    if (CHAT_INPUT) {
        CHAT_INPUT.value = '';
        CHAT_INPUT.disabled = true;
    }
    if (CHAT_SEND_BTN) {
        CHAT_SEND_BTN.disabled = true;
    }

    const chips = document.querySelectorAll('.preset-q-chip');
    chips.forEach(c => c.disabled = true);

    showLoadingIndicator(currentRetrievalMode);

    if (warmUpTimer) clearTimeout(warmUpTimer);
    if (CHAT_WARMUP_BANNER) {
        CHAT_WARMUP_BANNER.classList.remove('visible');
    }

    warmUpTimer = setTimeout(() => {
        if (CHAT_WARMUP_BANNER && CHAT_LOADING_INDICATOR && CHAT_LOADING_INDICATOR.classList.contains('visible')) {
            CHAT_WARMUP_BANNER.classList.add('visible');
        }
    }, 3000);

    const typingMsg = document.createElement('div');
    typingMsg.className = 'chat-message-row assistant';
    typingMsg.innerHTML = `
        <span class="msg-author-header">Grandma Chen Coordinator Assistant</span>
        <div class="msg-bubble-container" style="color: var(--color-text-secondary); font-style: italic;">
            Synthesizing answer via ${currentRetrievalMode === 'mcp' ? 'Cloud MCP Server' : 'Direct SQL'}...
        </div>
    `;
    const targetContainer = CHAT_MESSAGES_CONTAINER || CHAT_HISTORY;
    if (targetContainer) {
        targetContainer.appendChild(typingMsg);
        scrollToBottom();
    }

    try {
        const res = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, mode: currentRetrievalMode })
        });

        const contentType = res.headers.get('content-type') || '';
        let data = null;
        if (contentType.includes('application/json')) {
            try {
                data = await res.json();
            } catch (parseErr) {
                data = null;
            }
        }

        if (typingMsg.parentNode && targetContainer) {
            targetContainer.removeChild(typingMsg);
        }

        if (!res.ok || !data) {
            const errMsg = (data && data.message) ? data.message : 'Something went wrong — please try again.';
            throw new Error(errMsg);
        }

        const lowerAnswer = (data.answer || '').toLowerCase();
        const hasConflict = lowerAnswer.includes('mismatch') || lowerAnswer.includes('heads-up') || lowerAnswer.includes('discrepancy') || lowerAnswer.includes('conflicting') || lowerAnswer.includes('conflict');

        appendMessage('assistant', data.answer, hasConflict, data.retrieval_receipt);

    } catch (err) {
        if (typingMsg.parentNode && targetContainer) {
            targetContainer.removeChild(typingMsg);
        }
        let errorDisplay = (err && err.message) ? err.message : 'Something went wrong — please try again.';
        if (errorDisplay.includes('Unexpected token') || errorDisplay.includes('JSON')) {
            errorDisplay = 'Something went wrong — please try again.';
        }
        appendMessage('assistant', errorDisplay);
    } finally {
        if (warmUpTimer) {
            clearTimeout(warmUpTimer);
            warmUpTimer = null;
        }
        if (CHAT_WARMUP_BANNER) {
            CHAT_WARMUP_BANNER.classList.remove('visible');
        }
        hideLoadingIndicator();

        chips.forEach(c => c.disabled = false);

        if (CHAT_INPUT) {
            CHAT_INPUT.disabled = false;
            CHAT_INPUT.focus();
        }
        if (CHAT_SEND_BTN) {
            CHAT_SEND_BTN.disabled = false;
        }
    }
}

function sendChipQuestion(questionText) {
    if (CHAT_INPUT && CHAT_INPUT.disabled) return;
    sendChatMessage(questionText);
}

if (CHAT_FORM) {
    CHAT_FORM.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = CHAT_INPUT ? CHAT_INPUT.value.trim() : '';
        if (text && (!CHAT_INPUT || !CHAT_INPUT.disabled)) {
            sendChatMessage(text);
        }
    });
}

// ============================================================================
// SIMULATION ENGINE
// ============================================================================

async function runLiveSimulation() {
    if (!SIMULATE_BTN) return;
    SIMULATE_BTN.disabled = true;
    SIMULATE_BTN.innerHTML = `
        <svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
        <span>Simulating...</span>
    `;

    try {
        const res = await fetch('/api/simulate', { method: 'POST' });
        const contentType = res.headers.get('content-type') || '';
        let data = null;
        if (contentType.includes('application/json')) {
            try {
                data = await res.json();
            } catch (parseErr) {
                data = null;
            }
        }

        if (!res.ok || !data) {
            throw new Error((data && data.message) || 'Simulation failed — please try again.');
        }

        // Refresh notes feed immediately
        await fetchNotes(true);

        if (currentActiveTab !== 'chat') {
            switchTab('chat');
        }

        appendMessage('assistant', `**Live activity batch simulated successfully!**\n\nInserted 4 new caregiver notes into Grandma Chen's memory record, including an updated care plan order from Dr. Evelyn Vance and an administration log from Caregiver Mark.\n\n*Try asking me:* **"Was there any blood pressure medication discrepancy today?"**`);

    } catch (err) {
        let errorDisplay = (err && err.message) ? err.message : 'Simulation failed — please try again.';
        if (errorDisplay.includes('Unexpected token') || errorDisplay.includes('JSON')) {
            errorDisplay = 'Simulation failed — please try again.';
        }
        alert(`Simulation Error: ${errorDisplay}`);
    } finally {
        SIMULATE_BTN.disabled = false;
        SIMULATE_BTN.innerHTML = `
            <svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
            <span>Simulate Activity</span>
        `;
    }
}

// ============================================================================
// CARE LOG FORM & FEED
// ============================================================================

function selectNoteCategory(type) {
    if (TYPE_SELECT) {
        TYPE_SELECT.value = type;
    }
    const buttons = document.querySelectorAll('.cat-chip-btn');
    buttons.forEach(btn => {
        const isMatch = btn.getAttribute('data-type') === type;
        btn.classList.toggle('active', isMatch);
        btn.setAttribute('aria-checked', isMatch ? 'true' : 'false');
    });
}

function validateNoteForm() {
    const nameVal = CAREGIVER_INPUT ? CAREGIVER_INPUT.value.trim() : '';
    const contentVal = CONTENT_INPUT ? CONTENT_INPUT.value.trim() : '';

    const isValid = Boolean(nameVal && contentVal);
    if (NOTE_BTN) {
        NOTE_BTN.disabled = !isValid;
    }
    return isValid;
}

if (CAREGIVER_INPUT) {
    CAREGIVER_INPUT.addEventListener('input', () => {
        validateNoteForm();
        if (CAREGIVER_INPUT.value.trim()) {
            CAREGIVER_INPUT.removeAttribute('aria-invalid');
            if (CAREGIVER_ERROR) CAREGIVER_ERROR.classList.remove('visible');
        }
    });
    CAREGIVER_INPUT.addEventListener('blur', () => {
        if (!CAREGIVER_INPUT.value.trim()) {
            CAREGIVER_INPUT.setAttribute('aria-invalid', 'true');
            if (CAREGIVER_ERROR) CAREGIVER_ERROR.classList.add('visible');
        } else {
            CAREGIVER_INPUT.removeAttribute('aria-invalid');
            if (CAREGIVER_ERROR) CAREGIVER_ERROR.classList.remove('visible');
        }
    });
}

if (CONTENT_INPUT) {
    CONTENT_INPUT.addEventListener('input', () => {
        validateNoteForm();
        if (CONTENT_INPUT.value.trim()) {
            CONTENT_INPUT.removeAttribute('aria-invalid');
            if (CONTENT_ERROR) CONTENT_ERROR.classList.remove('visible');
        }
    });
    CONTENT_INPUT.addEventListener('blur', () => {
        if (!CONTENT_INPUT.value.trim()) {
            CONTENT_INPUT.setAttribute('aria-invalid', 'true');
            if (CONTENT_ERROR) CONTENT_ERROR.classList.add('visible');
        } else {
            CONTENT_INPUT.removeAttribute('aria-invalid');
            if (CONTENT_ERROR) CONTENT_ERROR.classList.remove('visible');
        }
    });
}

if (NOTE_FORM) {
    NOTE_FORM.addEventListener('submit', async (e) => {
        e.preventDefault();
        const caregiver_name = CAREGIVER_INPUT ? CAREGIVER_INPUT.value.trim() : '';
        const note_type = TYPE_SELECT ? TYPE_SELECT.value : 'general';
        const content = CONTENT_INPUT ? CONTENT_INPUT.value.trim() : '';

        if (!caregiver_name || !content) {
            if (!caregiver_name && CAREGIVER_INPUT && CAREGIVER_ERROR) {
                CAREGIVER_INPUT.setAttribute('aria-invalid', 'true');
                CAREGIVER_ERROR.classList.add('visible');
            }
            if (!content && CONTENT_INPUT && CONTENT_ERROR) {
                CONTENT_INPUT.setAttribute('aria-invalid', 'true');
                CONTENT_ERROR.classList.add('visible');
            }
            return;
        }

        if (NOTE_BTN) {
            NOTE_BTN.disabled = true;
            NOTE_BTN.innerHTML = '<span>Saving Caregiver Note...</span>';
        }
        if (NOTE_STATUS) {
            NOTE_STATUS.className = 'toast-status-box';
            NOTE_STATUS.innerText = '';
        }

        try {
            const res = await fetch('/api/notes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ caregiver_name, note_type, content })
            });
            const contentType = res.headers.get('content-type') || '';
            let data = null;
            if (contentType.includes('application/json')) {
                try {
                    data = await res.json();
                } catch (parseErr) {
                    data = null;
                }
            }

            if (!res.ok || !data) {
                throw new Error((data && data.message) || 'Failed to add note — please try again.');
            }

            if (NOTE_STATUS) {
                NOTE_STATUS.innerHTML = `
                    <svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                    <span>Caregiver note successfully saved to distributed memory record.</span>
                `;
                NOTE_STATUS.className = 'toast-status-box success';
            }

            if (CONTENT_INPUT) {
                CONTENT_INPUT.value = '';
            }

            // Refresh feed immediately and highlight top note
            await fetchNotes(true);

            // Auto-scroll feed to top
            if (NOTES_LIST) {
                NOTES_LIST.scrollTop = 0;
            }

        } catch (err) {
            let errorDisplay = (err && err.message) ? err.message : 'Failed to add note — please try again.';
            if (errorDisplay.includes('Unexpected token') || errorDisplay.includes('JSON')) {
                errorDisplay = 'Failed to add note — please try again.';
            }
            if (NOTE_STATUS) {
                NOTE_STATUS.innerHTML = `
                    <svg class="icon-svg icon-svg-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    <span>Error: ${errorDisplay}</span>
                `;
                NOTE_STATUS.className = 'toast-status-box error';
            }
        } finally {
            if (NOTE_BTN) {
                NOTE_BTN.disabled = false;
                NOTE_BTN.innerHTML = '<span>Save Caregiver Note</span>';
            }
            validateNoteForm();
        }
    });
}

// ============================================================================
// NOTES POLLING & RENDERER
// ============================================================================

async function fetchNotes(highlightNewest = false) {
    try {
        const res = await fetch('/api/notes');
        const contentType = res.headers.get('content-type') || '';
        if (!res.ok || !contentType.includes('application/json')) {
            return;
        }
        const data = await res.json();

        if (data.conversation_id && CID_DISPLAY) {
            CID_DISPLAY.innerText = data.conversation_id;
        }

        const countText = `${data.count || 0} Notes`;
        if (FEED_COUNT) {
            FEED_COUNT.innerText = countText;
        }
        if (NAV_NOTE_COUNT) {
            NAV_NOTE_COUNT.innerText = `${data.count || 0}`;
        }

        renderNotes(data.notes || [], highlightNewest);
    } catch (err) {
        console.error('Error fetching notes:', err);
    }
}

function renderNotes(notes, highlightNewest = false) {
    if (!NOTES_LIST) return;
    if (notes.length === 0) {
        NOTES_LIST.innerHTML = '<div class="empty-stream-text">No caregiver notes recorded yet.</div>';
        return;
    }

    NOTES_LIST.innerHTML = notes.map((note, index) => {
        const type = (note.note_type || 'general').toLowerCase();
        const badgeClass = `badge-${type}`;
        const ts = note.human_timestamp || note.created_at || 'Just now';
        const initial = (note.caregiver_name || 'C').charAt(0).toUpperCase();
        const shouldHighlight = highlightNewest && index === 0;

        return `
            <article class="stream-note-card ${shouldHighlight ? 'pulse-new-note' : ''}">
                <div class="card-meta-header">
                    <div class="card-caregiver-info">
                        <div class="caregiver-initial-circle" aria-hidden="true">${initial}</div>
                        <span class="caregiver-name-text">${escapeHtml(note.caregiver_name)}</span>
                        <span class="card-timestamp-text">• ${escapeHtml(ts)}</span>
                    </div>
                    <span class="note-category-tag ${badgeClass}">${escapeHtml(type)}</span>
                </div>
                <div class="card-note-body">${escapeHtml(note.content)}</div>
            </article>
        `;
    }).join('');
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, function(m) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
    });
}

// Initial fetch and 4s polling
fetchNotes();
setInterval(fetchNotes, 4000);
