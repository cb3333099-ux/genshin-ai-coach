/* ================================
   Genshin AI Coach - script.js
   ================================ */

const API_BASE = 'https://genshin-ai-coach.onrender.com';

/* ---------- DOM refs ---------- */
const chatMessages = document.getElementById('chatMessages');
const chatInput    = document.getElementById('chatInput');
const sendBtn      = document.getElementById('sendBtn');
const uidInput     = document.getElementById('uidInput');

/* ---------- Particles ---------- */
(function spawnParticles() {
    const container = document.querySelector('.particles');
    if (!container) return;

    const COLORS = [
        'rgba(91,141,238,0.7)',
        'rgba(155,89,182,0.7)',
        'rgba(240,192,64,0.6)',
        'rgba(80,220,180,0.5)',
        'rgba(255,100,60,0.5)',
    ];

    const COUNT = window.innerWidth < 600 ? 18 : 32;

    for (let i = 0; i < COUNT; i++) {
        const p  = document.createElement('div');
        const sz = Math.random() * 5 + 2;
        p.className = 'particle';
        p.style.cssText = `
            left: ${Math.random() * 100}%;
            width: ${sz}px;
            height: ${sz}px;
            background: ${COLORS[Math.floor(Math.random() * COLORS.length)]};
            --dur:   ${Math.random() * 10 + 7}s;
            --delay: ${Math.random() * 8}s;
        `;
        container.appendChild(p);
    }
})();

/* ---------- Toast ---------- */
function showToast(msg, type = 'info', ms = 3200) {
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.className   = `toast ${type}`;
    requestAnimationFrame(() => {
        requestAnimationFrame(() => { toast.classList.add('show'); });
    });
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
        toast.classList.remove('show');
    }, ms);
}

/* ---------- Welcome message ---------- */
function addWelcome() {
    addMessage(
        '✨ Welcome to Genshin AI Coach! I\'m your personal Teyvat guide.\n\n' +
        'Ask me about team compositions, character builds, farming routes, ' +
        'spiral abyss strategies, and more. Optionally enter your UID above for personalised advice!',
        'bot'
    );
}

/* ---------- Add message to chat ---------- */
function addMessage(text, sender) {
    const msg = document.createElement('div');
    msg.className = `message ${sender}`;

    const avatar = document.createElement('div');
    avatar.className = `msg-avatar ${sender}`;
    avatar.textContent = sender === 'bot' ? '🎮' : '🌟';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    bubble.innerHTML = formatText(text);

    msg.appendChild(avatar);
    msg.appendChild(bubble);
    chatMessages.appendChild(msg);
    scrollBottom();
}

/* ---------- Typing indicator ---------- */
function showTyping() {
    const msg = document.createElement('div');
    msg.className = 'message bot';
    msg.id = 'typingMsg';

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar bot';
    avatar.textContent = '🎮';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble typing-indicator';
    bubble.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';

    msg.appendChild(avatar);
    msg.appendChild(bubble);
    chatMessages.appendChild(msg);
    scrollBottom();
}

function hideTyping() {
    const el = document.getElementById('typingMsg');
    if (el) el.remove();
}

/* ---------- Scroll to bottom ---------- */
function scrollBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/* ---------- Basic text formatting ---------- */
function formatText(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code style="background:rgba(255,255,255,0.1);padding:1px 5px;border-radius:4px;font-size:0.85em">$1</code>')
        .replace(/\n/g, '<br>');
}

/* ---------- Send message ---------- */
async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    addMessage(text, 'user');
    chatInput.value = '';
    setInputDisabled(true);
    showTyping();

    try {
        const uid = uidInput ? uidInput.value.trim() : '';
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: text, uid: uid || '' }),
        });

        hideTyping();

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();

        if (data.success) {
            addMessage(data.response, 'bot');
        } else {
            addMessage('⚠️ Sorry, the coach ran into an issue. Please try again!', 'bot');
            showToast('Coach returned an error response', 'error');
        }
    } catch (err) {
        hideTyping();
        console.error('Chat error:', err);
        addMessage('🔌 Could not reach the server. Please check your connection and try again.', 'bot');
        showToast('Connection error — server may be waking up', 'error');
    } finally {
        setInputDisabled(false);
        chatInput.focus();
    }
}

/* ---------- Toggle input state ---------- */
function setInputDisabled(disabled) {
    chatInput.disabled = disabled;
    sendBtn.disabled   = disabled;
}

/* ---------- Quick question buttons ---------- */
document.querySelectorAll('.quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const q = btn.dataset.q;
        if (!q) {
            console.warn('quick-btn is missing data-q attribute', btn);
            return;
        }
        chatInput.value = q;
        sendMessage();
    });
});

/* ---------- Enter key ---------- */
chatInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

/* ---------- Send button ---------- */
sendBtn.addEventListener('click', sendMessage);

/* ---------- Init ---------- */
window.addEventListener('DOMContentLoaded', () => {
    addWelcome();
    chatInput.focus();
    showToast('✨ Genshin AI Coach is ready!', 'success');
});
