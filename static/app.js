// Grandma Chen's Care Coordinator - Frontend Logic

let currentRetrievalMode = 'sql';

const CID_DISPLAY = document.getElementById('cid-display');
const DEV_DRAWER = document.getElementById('dev-drawer');
const NOTES_LIST = document.getElementById('notes-list');
const FEED_COUNT = document.getElementById('feed-count');

const CHAT_HISTORY = document.getElementById('chat-history');
const CHAT_FORM = document.getElementById('chat-form');
const CHAT_INPUT = document.getElementById('chat-input');
const CHAT_SEND_BTN = document.getElementById('chat-send-btn');
const SIMULATE_BTN = document.getElementById('simulate-btn');
const CHAT_LOADING_INDICATOR = document.getElementById('chat-loading-indicator');
const CHAT_LOADING_TEXT = document.getElementById('chat-loading-text');

function showLoadingIndicator(mode) {
    if (!CHAT_LOADING_INDICATOR || !CHAT_LOADING_TEXT) return;
    if (mode === 'mcp') {
        CHAT_LOADING_TEXT.innerText = 'Querying via MCP Server...';
    } else {
        CHAT_LOADING_TEXT.innerText = 'Querying...';
    }
    CHAT_LOADING_INDICATOR.style.display = 'flex';
}

function hideLoadingIndicator() {
    if (CHAT_LOADING_INDICATOR) {
        CHAT_LOADING_INDICATOR.style.display = 'none';
    }
}

const NOTE_FORM = document.getElementById('note-form');
const CAREGIVER_INPUT = document.getElementById('caregiver-input');
const TYPE_SELECT = document.getElementById('type-select');
const CONTENT_INPUT = document.getElementById('content-input');
const NOTE_BTN = document.getElementById('note-btn');
const NOTE_STATUS = document.getElementById('note-status');

function toggleDevDrawer() {
    if (DEV_DRAWER) DEV_DRAWER.classList.toggle('open');
}

function scrollToBottom() {
    if (CHAT_HISTORY) CHAT_HISTORY.scrollTop = CHAT_HISTORY.scrollHeight;
}

function setRetrievalMode(mode) {
    currentRetrievalMode = mode === 'mcp' ? 'mcp' : 'sql';
    const btnSql = document.getElementById('mode-btn-sql');
    const btnMcp = document.getElementById('mode-btn-mcp');

    if (btnSql && btnMcp) {
        if (currentRetrievalMode === 'mcp') {
            btnSql.classList.remove('active');
            btnMcp.classList.add('active');
        } else {
            btnMcp.classList.remove('active');
            btnSql.classList.add('active');
        }
    }
}

function appendMessage(role, content, hasConflict = false, receipt = null) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-msg ${role}`;
    if (hasConflict) msgDiv.classList.add('has-conflict');

    const metaDiv = document.createElement('div');
    metaDiv.className = 'msg-meta';
    if (role === 'user') {
        metaDiv.innerHTML = '<span>👤 You</span>';
    } else {
        metaDiv.innerHTML = '<span>👵 Coordinator Assistant</span>';
    }

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'msg-bubble';

    if (role === 'assistant') {
        let innerHtml = '';
        if (hasConflict) {
            innerHtml += '<div class="conflict-banner">⚠️ Discrepancy / Mismatch Flagged</div>';
        }
        if (window.marked) {
            innerHtml += marked.parse(content);
        } else {
            innerHtml += escapeHtml(content);
        }
        bubbleDiv.innerHTML = innerHtml;
    } else {
        bubbleDiv.innerText = content;
    }

    msgDiv.appendChild(metaDiv);
    msgDiv.appendChild(bubbleDiv);

    // Render compact collapsed-by-default retrieval receipt panel if metadata exists
    if (role === 'assistant' && receipt) {
        const isMcp = (receipt.method_label && receipt.method_label.includes('MCP')) || receipt.cte_restructured !== undefined;
        const receiptPanel = document.createElement('details');
        receiptPanel.className = `retrieval-receipt ${isMcp ? 'receipt-mcp' : 'receipt-sql'}`;

        let receiptHtml = `
            <summary class="receipt-summary">
                <span class="receipt-badge ${isMcp ? 'badge-mcp' : 'badge-sql'}">
                    ${isMcp ? '🔌 MCP Server' : '⚡ Direct SQL'}
                </span>
                <span class="receipt-title">How this was retrieved</span>
                <span class="receipt-latency">${receipt.latency_ms} ms</span>
                <span class="receipt-chevron">▼</span>
            </summary>
            <div class="receipt-content">
                <div class="receipt-row">
                    <span class="receipt-key">Method:</span>
                    <span class="receipt-val">${escapeHtml(receipt.method_label)}</span>
                </div>
                <div class="receipt-row">
                    <span class="receipt-key">Mechanism:</span>
                    <span class="receipt-val">${escapeHtml(receipt.description)}</span>
                </div>
                <div class="receipt-row">
                    <span class="receipt-key">Measured RTT:</span>
                    <span class="receipt-val">${receipt.latency_ms} ms</span>
                </div>
        `;

        if (receipt.cte_restructured !== undefined) {
            receiptHtml += `
                <div class="receipt-row">
                    <span class="receipt-key">16KB Limit CTE Restructuring:</span>
                    <span class="receipt-val tag-cte">${receipt.cte_restructured ? 'Applied (WITH qv AS vector CTE)' : 'Not Required'}</span>
                </div>
            `;
        }

        receiptHtml += `</div>`;
        receiptPanel.innerHTML = receiptHtml;
        msgDiv.appendChild(receiptPanel);
    }

    CHAT_HISTORY.appendChild(msgDiv);
    scrollToBottom();

    return msgDiv;
}

let warmUpTimer = null;

async function sendChatMessage(question) {
    if (!question) return;

    appendMessage('user', question);
    if (CHAT_INPUT) {
        CHAT_INPUT.value = '';
        CHAT_INPUT.disabled = true;
    }
    if (CHAT_SEND_BTN) {
        CHAT_SEND_BTN.disabled = true;
    }

    // Show inline loading indicator
    showLoadingIndicator(currentRetrievalMode);

    // Schedule 8-second warmup notice if model inference takes time
    if (warmUpTimer) clearTimeout(warmUpTimer);
    warmUpTimer = setTimeout(() => {
        if (CHAT_LOADING_TEXT && CHAT_LOADING_INDICATOR && CHAT_LOADING_INDICATOR.style.display !== 'none') {
            CHAT_LOADING_TEXT.innerText = 'Still warming up the AI models — first questions after a quiet period can take up to a minute.';
        }
    }, 8000);

    // Add typing indicator
    const typingMsg = document.createElement('div');
    typingMsg.className = 'chat-msg assistant';
    typingMsg.innerHTML = `
        <div class="msg-meta"><span>👵 Coordinator Assistant</span></div>
        <div class="msg-bubble" style="color: #64748b; font-style: italic;">
            Synthesizing answer via ${currentRetrievalMode === 'mcp' ? 'Cloud MCP' : 'Direct SQL'}...
        </div>
    `;
    CHAT_HISTORY.appendChild(typingMsg);
    scrollToBottom();

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

        // Remove typing indicator
        if (typingMsg.parentNode) CHAT_HISTORY.removeChild(typingMsg);

        if (!res.ok || !data) {
            const errMsg = (data && data.message) ? data.message : 'Something went wrong — please try again.';
            throw new Error(errMsg);
        }

        const lowerAnswer = (data.answer || '').toLowerCase();
        const hasConflict = lowerAnswer.includes('mismatch') || lowerAnswer.includes('heads-up') || lowerAnswer.includes('discrepancy') || lowerAnswer.includes('conflicting') || lowerAnswer.includes('conflict');

        appendMessage('assistant', data.answer, hasConflict, data.retrieval_receipt);

    } catch (err) {
        if (typingMsg.parentNode) CHAT_HISTORY.removeChild(typingMsg);
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
        hideLoadingIndicator();
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
        const text = CHAT_INPUT.value.trim();
        if (text && !CHAT_INPUT.disabled) sendChatMessage(text);
    });
}

async function runLiveSimulation() {
    if (!SIMULATE_BTN) return;
    SIMULATE_BTN.disabled = true;
    SIMULATE_BTN.innerHTML = '<span>⏳ Simulating Activity...</span>';

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
        await fetchNotes();

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
        SIMULATE_BTN.innerHTML = '<span>⚡ Simulate Live Activity</span>';
    }
}

async function fetchNotes() {
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

        if (FEED_COUNT) {
            FEED_COUNT.innerText = `${data.count || 0} Notes`;
        }
        renderNotes(data.notes || []);
    } catch (err) {
        console.error('Error fetching notes:', err);
    }
}

function renderNotes(notes) {
    if (!NOTES_LIST) return;
    if (notes.length === 0) {
        NOTES_LIST.innerHTML = '<div class="empty-feed">No caregiver notes recorded yet.</div>';
        return;
    }

    NOTES_LIST.innerHTML = notes.map(note => {
        const type = (note.note_type || 'general').toLowerCase();
        const badgeClass = `badge-${type}`;
        const ts = note.human_timestamp || note.created_at || 'Just now';
        const initial = (note.caregiver_name || 'C').charAt(0).toUpperCase();

        return `
            <div class="note-item">
                <div class="note-item-header">
                    <div class="note-meta">
                        <div class="caregiver-avatar">${initial}</div>
                        <span class="caregiver-name">${escapeHtml(note.caregiver_name)}</span>
                        <span class="note-timestamp">• ${escapeHtml(ts)}</span>
                    </div>
                    <span class="note-type-badge ${badgeClass}">${escapeHtml(type)}</span>
                </div>
                <div class="note-content">${escapeHtml(note.content)}</div>
            </div>
        `;
    }).join('');
}

if (NOTE_FORM) {
    NOTE_FORM.addEventListener('submit', async (e) => {
        e.preventDefault();
        const caregiver_name = CAREGIVER_INPUT.value.trim();
        const note_type = TYPE_SELECT.value;
        const content = CONTENT_INPUT.value.trim();

        if (!caregiver_name || !content) return;

        NOTE_BTN.disabled = true;
        NOTE_BTN.innerText = 'Saving Caregiver Note...';
        NOTE_STATUS.className = 'status-toast';
        NOTE_STATUS.innerText = '';

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

            NOTE_STATUS.innerText = 'Caregiver note successfully saved.';
            NOTE_STATUS.className = 'status-toast success';
            CONTENT_INPUT.value = '';

            // Refresh feed immediately
            fetchNotes();
        } catch (err) {
            let errorDisplay = (err && err.message) ? err.message : 'Failed to add note — please try again.';
            if (errorDisplay.includes('Unexpected token') || errorDisplay.includes('JSON')) {
                errorDisplay = 'Failed to add note — please try again.';
            }
            NOTE_STATUS.innerText = `Error: ${errorDisplay}`;
            NOTE_STATUS.className = 'status-toast error';
        } finally {
            NOTE_BTN.disabled = false;
            NOTE_BTN.innerText = 'Save Caregiver Note';
        }
    });
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, function(m) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
    });
}

// Initial load & 4s polling
fetchNotes();
setInterval(fetchNotes, 4000);
