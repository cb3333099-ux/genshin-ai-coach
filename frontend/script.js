/* ================================
   Genshin AI Coach - script.js
   ================================ */

const API_BASE = 'https://genshin-ai-coach.onrender.com';

/* ---------- DOM refs ---------- */
const chatMessages  = document.getElementById('chatMessages');
const chatInput     = document.getElementById('chatInput');
const sendBtn       = document.getElementById('sendBtn');
const uidInput      = document.getElementById('uidInput');
const accountPanel  = document.getElementById('accountPanel');
const accountContent = document.getElementById('accountContent');
const accountLoading = document.getElementById('accountLoading');

/* ---------- Element emoji map ---------- */
const ELEMENT_EMOJI = {
    Pyro: '🔥', Hydro: '💧', Anemo: '🌀', Electro: '⚡',
    Dendro: '🌿', Cryo: '❄️', Geo: '🪨', Unknown: '✨',
};
const ELEMENT_CLASS = {
    Pyro: 'el-pyro', Hydro: 'el-hydro', Anemo: 'el-anemo', Electro: 'el-electro',
    Dendro: 'el-dendro', Cryo: 'el-cryo', Geo: 'el-geo', Unknown: '',
};

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

/* ---------- Account Info Fetch & Display ---------- */
let accountFetchTimer = null;

async function fetchAndDisplayAccount(uid) {
    if (!uid || uid.length < 6) return;

    accountPanel.style.display = 'block';
    accountLoading.style.display = 'inline';
    accountContent.innerHTML = '<div class="account-loading-msg">Fetching account data…</div>';

    try {
        const res = await fetch(`${API_BASE}/api/account/${encodeURIComponent(uid)}`);
        const json = await res.json();

        if (!res.ok) {
            const detail = json.detail || 'Unknown error';
            accountContent.innerHTML = `<div class="account-error">⚠️ ${escapeHtml(detail)}</div>`;
            showToast('Could not load account data', 'error');
            return;
        }

        if (json.success && json.data) {
            renderAccountPanel(json.data);
            showToast(`✅ Loaded account: ${json.data.nickname || uid}`, 'success');
        }
    } catch (err) {
        console.error('Account fetch error:', err);
        accountContent.innerHTML = '<div class="account-error">🔌 Could not reach server. Try again later.</div>';
        showToast('Server unreachable', 'error');
    } finally {
        accountLoading.style.display = 'none';
    }
}

function renderAccountPanel(data) {
    const nickname = data.nickname || 'Traveler';
    const level    = data.level    || '?';
    const wl       = data.world_level != null ? data.world_level : '?';
    const abyssStr = data.abyss_floor
        ? `Floor ${data.abyss_floor}-${data.abyss_chamber}`
        : '—';
    const sig = data.signature ? `<div class="account-sig">"${escapeHtml(data.signature)}"</div>` : '';

    let html = `
        <div class="account-header">
            <div class="account-name">${escapeHtml(nickname)}</div>
            <div class="account-meta">AR ${level} &nbsp;·&nbsp; WL ${wl} &nbsp;·&nbsp; Abyss ${abyssStr}</div>
            ${sig}
        </div>`;

    const characters = data.characters || [];
    if (characters.length > 0) {
        html += `<div class="char-list">`;
        for (const char of characters) {
            const elem      = char.element || 'Unknown';
            const emoji     = ELEMENT_EMOJI[elem]  || '✨';
            const cls       = ELEMENT_CLASS[elem]  || '';
            const name      = escapeHtml(char.name  || 'Unknown');
            const lvl       = char.level            || 1;
            const cons      = char.constellations   != null ? char.constellations : '?';
            const na        = char.talents?.normal_attack   ?? '?';
            const skill     = char.talents?.elemental_skill ?? '?';
            const burst     = char.talents?.elemental_burst ?? '?';

            const stats  = char.stats  || {};
            const cr     = stats['Crit Rate']  || '—';
            const cd     = stats['Crit DMG']   || '—';
            const er     = stats['Energy Recharge'] || '—';
            const em     = stats['Elemental Mastery'] != null ? stats['Elemental Mastery'] : '—';

            const weapon = char.weapon || {};
            const wLvl   = weapon.level ? `Lv.${weapon.level}` : '';
            const wRef   = weapon.refinement ? `R${weapon.refinement}` : '';
            const wRar   = weapon.rarity ? `${weapon.rarity}★` : '';
            const weaponStr = [wRar, wLvl, wRef].filter(Boolean).join(' ');

            const artifacts = char.artifacts || [];
            const bestArti  = artifacts.length
                ? `${artifacts.length} pieces · +${Math.max(...artifacts.map(a => a.level || 0))}`
                : '';

            html += `
            <div class="char-card">
                <div class="char-card-top">
                    <span class="char-elem-badge ${cls}">${emoji}</span>
                    <div class="char-info">
                        <div class="char-name">${name}</div>
                        <div class="char-sub">Lv.${lvl} &nbsp;·&nbsp; C${cons}</div>
                    </div>
                </div>
                <div class="char-details">
                    <div class="char-detail-row"><span class="cd-label">Talents</span><span class="cd-val">${na} / ${skill} / ${burst}</span></div>
                    ${weaponStr ? `<div class="char-detail-row"><span class="cd-label">Weapon</span><span class="cd-val">${weaponStr}</span></div>` : ''}
                    <div class="char-detail-row"><span class="cd-label">CR / CD</span><span class="cd-val">${cr} / ${cd}</span></div>
                    <div class="char-detail-row"><span class="cd-label">ER</span><span class="cd-val">${er}</span></div>
                    ${em !== '—' ? `<div class="char-detail-row"><span class="cd-label">EM</span><span class="cd-val">${em}</span></div>` : ''}
                    ${bestArti ? `<div class="char-detail-row"><span class="cd-label">Artifacts</span><span class="cd-val">${bestArti}</span></div>` : ''}
                </div>
            </div>`;
        }
        html += `</div>`;
    } else {
        html += `<div class="account-error">No showcase characters found. Set characters in your in-game profile showcase.</div>`;
    }

    accountContent.innerHTML = html;
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

/* ---------- UID input listener ---------- */
if (uidInput) {
    uidInput.addEventListener('input', () => {
        clearTimeout(accountFetchTimer);
        const uid = uidInput.value.trim();
        if (!uid) {
            accountPanel.style.display = 'none';
            return;
        }
        // Debounce: fetch 1.2 s after user stops typing
        accountFetchTimer = setTimeout(() => fetchAndDisplayAccount(uid), 1200);
    });

    uidInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            clearTimeout(accountFetchTimer);
            fetchAndDisplayAccount(uidInput.value.trim());
        }
    });
}

/* ---------- Init ---------- */
window.addEventListener('DOMContentLoaded', () => {
    addWelcome();
    chatInput.focus();
    showToast('✨ Genshin AI Coach is ready!', 'success');
});
