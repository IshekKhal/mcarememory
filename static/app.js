// Grandma Chen's Care Coordinator - Frontend Logic v2 (Design System v2)

let currentRetrievalMode = 'sql';
let currentActiveTab = 'chat';
let warmUpTimer = null;

// DOM Elements
const CID_DISPLAY = document.getElementById('cid-display');
const DEV_DRAWER = document.getElementById('dev-drawer');
const DEV_TOGGLE_BTN = document.getElementById('dev-toggle-btn');
const NOTES_LIST = document.getElementById('notes-list');
const FEED_COUNT = document.getElementById('feed-count');
const NAV_NOTE_COUNT = document.getElementById('nav-note-count');

const TAB_CHAT = document.getElementById('tab-chat');
const TAB_CARELOG = document.getElementById('tab-carelog');
const VIEW_CHAT = document.getElementById('view-chat');
const VIEW_CARELOG = document.getElementById('view-carelog');

const CHAT_HISTORY = document.getElementById('chat-history');
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

// ============================================================================
// TAB NAVIGATION CONTROLLER (Keyboard-accessible & Instagram-pill style)
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
        if (CHAT_INPUT && !CHAT_INPUT.disabled) {
            CHAT_INPUT.focus();
        }
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
        if (CAREGIVER_INPUT && !CAREGIVER_INPUT.disabled) {
            CAREGIVER_INPUT.focus();
        }
    }
}

// Accessible arrow-key navigation between tabs
const tabList = document.querySelector('.nav-tabs');
if (tabList) {
    tabList.addEventListener('keydown', (e) => {
        const tabs = [TAB_CHAT, TAB_CARELOG].filter(Boolean);
        const currentIndex = tabs.findIndex(tab => tab === document.activeElement);
        if (currentIndex === -1) return;

        let targetIndex = currentIndex;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            e.preventDefault();
            targetIndex = (currentIndex + 1) % tabs.length;
            tabs[targetIndex].focus();
            switchTab(tabs[targetIndex] === TAB_CARELOG ? 'carelog' : 'chat');
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
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
        CHAT_LOADING_TEXT.innerText = 'Querying via CockroachDB MCP Server...';
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
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${role}`;
    if (hasConflict) msgDiv.classList.add('has-conflict');

    const senderSpan = document.createElement('span');
    senderSpan.className = 'msg-sender';
    senderSpan.innerText = role === 'user' ? '👤 You' : '👵 Coordinator Assistant';

    const bubbleContent = document.createElement('div');
    bubbleContent.className = 'msg-bubble-content';

    if (role === 'assistant') {
        let innerHtml = '';
        if (hasConflict) {
            innerHtml += '<div class="conflict-tag">⚠️ Discrepancy / Mismatch Flagged</div>';
        }
        if (window.marked && typeof marked.parse === 'function') {
            innerHtml += marked.parse(content);
        } else {
            innerHtml += escapeHtml(content);
        }
        bubbleContent.innerHTML = innerHtml;
    } else {
        bubbleContent.innerText = content;
    }

    msgDiv.appendChild(senderSpan);
    msgDiv.appendChild(bubbleContent);

    // Render collapsed-by-default retrieval receipt pill if metadata exists
    if (role === 'assistant' && receipt) {
        const isMcp = (receipt.method_label && receipt.method_label.includes('MCP')) || receipt.cte_restructured !== undefined;
        const receiptPanel = document.createElement('details');
        receiptPanel.className = `retrieval-receipt ${isMcp ? 'receipt-mcp' : 'receipt-sql'}`;

        let receiptHtml = `
            <summary class="receipt-summary">
                <span class="receipt-mode-pill ${isMcp ? 'badge-mcp' : 'badge-sql'}">
                    ${isMcp ? '🔌 MCP Server' : '⚡ Direct SQL'}
                </span>
                <span class="receipt-summary-text">How this was retrieved</span>
                <span class="receipt-latency-pill">${receipt.latency_ms} ms</span>
                <span class="receipt-chevron" aria-hidden="true">▼</span>
            </summary>
            <div class="receipt-body">
                <div class="receipt-field">
                    <span class="receipt-label">Method:</span>
                    <span class="receipt-data">${escapeHtml(receipt.method_label)}</span>
                </div>
                <div class="receipt-field">
                    <span class="receipt-label">Mechanism:</span>
                    <span class="receipt-data">${escapeHtml(receipt.description)}</span>
                </div>
                <div class="receipt-field">
                    <span class="receipt-label">Measured RTT:</span>
                    <span class="receipt-data">${receipt.latency_ms} ms</span>
                </div>
        `;

        if (receipt.cte_restructured !== undefined) {
            receiptHtml += `
                <div class="receipt-field">
                    <span class="receipt-label">16KB Limit CTE Restructuring:</span>
                    <span class="receipt-data cte-tag">${receipt.cte_restructured ? 'Applied (WITH qv AS vector CTE)' : 'Not Required'}</span>
                </div>
            `;
        }

        receiptHtml += `</div>`;
        receiptPanel.innerHTML = receiptHtml;
        msgDiv.appendChild(receiptPanel);
    }

    if (CHAT_HISTORY) {
        CHAT_HISTORY.appendChild(msgDiv);
        scrollToBottom();
    }

    return msgDiv;
}

async function sendChatMessage(question) {
    if (!question) return;

    // Ensure chat view is visible
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

    // Disable chips during request
    const chips = document.querySelectorAll('.prompt-chip');
    chips.forEach(c => c.disabled = true);

    showLoadingIndicator(currentRetrievalMode);

    // Trigger prominent full-width warm-up banner after 3.0 seconds
    if (warmUpTimer) clearTimeout(warmUpTimer);
    if (CHAT_WARMUP_BANNER) {
        CHAT_WARMUP_BANNER.classList.remove('visible');
    }

    warmUpTimer = setTimeout(() => {
        if (CHAT_WARMUP_BANNER && CHAT_LOADING_INDICATOR && CHAT_LOADING_INDICATOR.classList.contains('visible')) {
            CHAT_WARMUP_BANNER.classList.add('visible');
        }
    }, 3000);

    // Temporary typing indicator
    const typingMsg = document.createElement('div');
    typingMsg.className = 'chat-message assistant';
    typingMsg.innerHTML = `
        <span class="msg-sender">👵 Coordinator Assistant</span>
        <div class="msg-bubble-content" style="color: var(--color-text-secondary); font-style: italic;">
            Synthesizing answer via ${currentRetrievalMode === 'mcp' ? 'Cloud MCP Server' : 'Direct SQL'}...
        </div>
    `;
    if (CHAT_HISTORY) {
        CHAT_HISTORY.appendChild(typingMsg);
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

        if (typingMsg.parentNode && CHAT_HISTORY) {
            CHAT_HISTORY.removeChild(typingMsg);
        }

        if (!res.ok || !data) {
            const errMsg = (data && data.message) ? data.message : 'Something went wrong — please try again.';
            throw new Error(errMsg);
        }

        const lowerAnswer = (data.answer || '').toLowerCase();
        const hasConflict = lowerAnswer.includes('mismatch') || lowerAnswer.includes('heads-up') || lowerAnswer.includes('discrepancy') || lowerAnswer.includes('conflicting') || lowerAnswer.includes('conflict');

        appendMessage('assistant', data.answer, hasConflict, data.retrieval_receipt);

    } catch (err) {
        if (typingMsg.parentNode && CHAT_HISTORY) {
            CHAT_HISTORY.removeChild(typingMsg);
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
    SIMULATE_BTN.innerHTML = '<span aria-hidden="true">⏳</span> Simulating Activity...';

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

        // Append simulation notification message to chat history
        appendMessage('assistant', `⚡ **Live activity batch simulated successfully!**\n\nInserted 4 new caregiver notes into Grandma Chen's memory record, including an updated care plan order from Dr. Evelyn Vance and an administration log from Caregiver Mark.\n\n*Try asking me:* **"Was there any blood pressure medication discrepancy today?"**`);

    } catch (err) {
        let errorDisplay = (err && err.message) ? err.message : 'Simulation failed — please try again.';
        if (errorDisplay.includes('Unexpected token') || errorDisplay.includes('JSON')) {
            errorDisplay = 'Simulation failed — please try again.';
        }
        alert(`Simulation Error: ${errorDisplay}`);
    } finally {
        SIMULATE_BTN.disabled = false;
        SIMULATE_BTN.innerHTML = '<span aria-hidden="true">⚡</span> Simulate Live Activity';
    }
}

// ============================================================================
// CARE LOG FORM & FEED
// ============================================================================

function selectNoteCategory(type) {
    if (TYPE_SELECT) {
        TYPE_SELECT.value = type;
    }
    const buttons = document.querySelectorAll('.category-chip-btn');
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
            NOTE_STATUS.className = 'toast-notification';
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
                NOTE_STATUS.innerText = 'Caregiver note successfully saved.';
                NOTE_STATUS.className = 'toast-notification success';
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
                NOTE_STATUS.innerText = `Error: ${errorDisplay}`;
                NOTE_STATUS.className = 'toast-notification error';
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
        NOTES_LIST.innerHTML = '<div class="empty-feed-placeholder">No caregiver notes recorded yet.</div>';
        return;
    }

    NOTES_LIST.innerHTML = notes.map((note, index) => {
        const type = (note.note_type || 'general').toLowerCase();
        const badgeClass = `badge-${type}`;
        const ts = note.human_timestamp || note.created_at || 'Just now';
        const initial = (note.caregiver_name || 'C').charAt(0).toUpperCase();
        const shouldHighlight = highlightNewest && index === 0;

        return `
            <article class="memory-feed-card ${shouldHighlight ? 'highlight-pulse' : ''}">
                <div class="feed-card-header">
                    <div class="feed-actor">
                        <div class="avatar-circle" aria-hidden="true">${initial}</div>
                        <span class="actor-name">${escapeHtml(note.caregiver_name)}</span>
                        <span class="feed-timestamp">• ${escapeHtml(ts)}</span>
                    </div>
                    <span class="note-badge ${badgeClass}">${escapeHtml(type)}</span>
                </div>
                <div class="feed-card-content">${escapeHtml(note.content)}</div>
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

// Initial fetch and 4s polling interval
fetchNotes();
setInterval(fetchNotes, 4000);
