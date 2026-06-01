import io
from quart import Blueprint, jsonify, request, render_template_string
import state

messenger_app = Blueprint('messenger', __name__)

# ---------------------------------------------------------------------------
# HTML PAGE
# ---------------------------------------------------------------------------

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Floppy — Messenger</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #1e1f22; --surface: #2b2d31; --surface2: #313338; --surface3: #3a3d44;
      --border: #3f4248; --text: #dbdee1; --muted: #949ba4; --muted2: #6d6f78;
      --accent: #5865f2; --accent-hover: #4752c4; --accent-dim: rgba(88,101,242,0.15);
      --green: #43b581; --red: #f04747; --yellow: #faa61a;
      --sidebar-w: 230px;
    }
    html, body { height: 100%; overflow: hidden; font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); }

    /* ── Layout ── */
    #app { display: flex; height: 100vh; }

    /* ── Server/Channel sidebar ── */
    #sidebar {
      width: var(--sidebar-w); flex-shrink: 0;
      background: var(--surface); border-right: 1px solid var(--border);
      display: flex; flex-direction: column; overflow: hidden;
    }
    #sidebar-header {
      padding: 1rem; border-bottom: 1px solid var(--border);
      font-size: 0.95rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;
    }
    #channel-search {
      margin: 0.6rem; padding: 0.45rem 0.7rem;
      background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
      color: var(--text); font-size: 0.82rem; font-family: inherit; width: calc(100% - 1.2rem);
    }
    #channel-search:focus { outline: none; border-color: var(--accent); }
    #channel-list { flex: 1; overflow-y: auto; padding: 0.4rem; }
    .ch-category {
      padding: 0.5rem 0.5rem 0.2rem; font-size: 0.68rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted2);
    }
    .ch-item {
      display: flex; align-items: center; gap: 0.45rem;
      padding: 0.42rem 0.6rem; border-radius: 6px; cursor: pointer;
      font-size: 0.88rem; color: var(--muted); transition: background 0.1s, color 0.1s;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .ch-item:hover { background: var(--surface2); color: var(--text); }
    .ch-item.active { background: var(--surface3); color: var(--text); }
    .ch-hash { font-size: 1rem; opacity: 0.5; flex-shrink: 0; }
    .ch-unread::after { content: ''; width: 8px; height: 8px; border-radius: 50%; background: var(--text); margin-left: auto; flex-shrink: 0; }

    /* ── Main chat area ── */
    #chat { flex: 1; display: flex; flex-direction: column; min-width: 0; }

    /* ── Chat header ── */
    #chat-header {
      padding: 0 1rem; height: 48px; border-bottom: 1px solid var(--border);
      display: flex; align-items: center; gap: 0.6rem; flex-shrink: 0;
    }
    #chat-channel-name { font-weight: 700; font-size: 1rem; }
    #chat-channel-name .hash { color: var(--muted); margin-right: 0.1rem; }
    #header-actions { margin-left: auto; display: flex; gap: 0.5rem; }
    .icon-btn {
      background: none; border: none; color: var(--muted); cursor: pointer;
      padding: 0.3rem; border-radius: 5px; font-size: 1.1rem; line-height: 1;
      transition: color 0.1s, background 0.1s;
    }
    .icon-btn:hover { background: var(--surface2); color: var(--text); }

    /* ── Messages ── */
    #messages {
      flex: 1; overflow-y: auto; padding: 1rem 1rem 0.5rem;
      display: flex; flex-direction: column; gap: 0;
    }
    .msg-group { display: flex; gap: 0.8rem; padding: 0.2rem 0; }
    .msg-group:hover { background: rgba(0,0,0,0.06); border-radius: 4px; }
    .msg-group + .msg-group { margin-top: 0.85rem; }
    .msg-group.continuation { margin-top: 0; }
    .msg-group.continuation .msg-group:hover { background: none; }
    .avatar {
      width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.8rem; font-weight: 700; color: white;
    }
    .avatar-gap { width: 38px; flex-shrink: 0; }
    .msg-col { flex: 1; min-width: 0; }
    .msg-meta { display: flex; align-items: baseline; gap: 0.5rem; margin-bottom: 0.15rem; }
    .msg-author { font-size: 0.9rem; font-weight: 700; }
    .msg-time { font-size: 0.72rem; color: var(--muted2); }
    .bot-badge {
      font-size: 0.62rem; background: var(--accent); color: white;
      border-radius: 3px; padding: 0.06rem 0.32rem; font-weight: 700;
      vertical-align: middle;
    }
    .msg-text { font-size: 0.9rem; line-height: 1.5; word-break: break-word; white-space: pre-wrap; color: var(--text); }
    .msg-text.has-reply { color: var(--muted); }

    /* Reply quote */
    .reply-bar {
      display: flex; align-items: center; gap: 0.5rem;
      font-size: 0.78rem; color: var(--muted); margin-bottom: 0.2rem;
      padding-left: 0.5rem; border-left: 2px solid var(--muted2);
      cursor: pointer;
    }
    .reply-bar:hover { color: var(--text); }
    .reply-author { font-weight: 700; }

    /* Attachments */
    .attachment-img {
      margin-top: 0.4rem; max-width: 400px; max-height: 300px;
      border-radius: 6px; display: block; cursor: zoom-in;
    }
    .attachment-file {
      margin-top: 0.4rem; display: inline-flex; align-items: center; gap: 0.5rem;
      background: var(--surface2); border: 1px solid var(--border);
      border-radius: 6px; padding: 0.45rem 0.7rem; font-size: 0.82rem;
      color: var(--text); text-decoration: none;
    }

    /* Reactions */
    .reactions { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.35rem; }
    .reaction {
      display: flex; align-items: center; gap: 0.3rem;
      background: var(--surface2); border: 1px solid var(--border);
      border-radius: 20px; padding: 0.15rem 0.55rem;
      font-size: 0.82rem; cursor: pointer; transition: background 0.1s;
      color: var(--text);
    }
    .reaction:hover { background: var(--accent-dim); border-color: var(--accent); }
    .reaction-count { font-size: 0.78rem; color: var(--muted); }
    .add-reaction {
      background: none; border: 1px solid transparent;
      border-radius: 20px; padding: 0.15rem 0.55rem;
      font-size: 0.82rem; cursor: pointer; color: var(--muted); transition: all 0.1s;
    }
    .add-reaction:hover { background: var(--surface2); border-color: var(--border); color: var(--text); }

    /* Hover actions on a message */
    .msg-actions {
      display: none; position: absolute; right: 0.5rem; top: -14px;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 6px; padding: 0.2rem 0.3rem;
      display: none; gap: 0.1rem; z-index: 10;
    }
    .msg-wrapper { position: relative; }
    .msg-wrapper:hover .msg-actions { display: flex; }
    .msg-action-btn {
      background: none; border: none; color: var(--muted); cursor: pointer;
      padding: 0.25rem 0.35rem; border-radius: 4px; font-size: 0.88rem; line-height: 1;
    }
    .msg-action-btn:hover { background: var(--surface2); color: var(--text); }

    /* Emoji picker */
    #emoji-picker {
      position: fixed; background: var(--surface); border: 1px solid var(--border);
      border-radius: 10px; padding: 0.75rem; display: none; z-index: 100;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    }
    #emoji-picker.open { display: block; }
    #emoji-search {
      width: 100%; padding: 0.4rem 0.6rem; background: var(--bg);
      border: 1px solid var(--border); border-radius: 6px;
      color: var(--text); font-family: inherit; font-size: 0.82rem; margin-bottom: 0.5rem;
    }
    #emoji-search:focus { outline: none; border-color: var(--accent); }
    #emoji-grid {
      display: grid; grid-template-columns: repeat(8, 1fr);
      gap: 2px; max-height: 200px; overflow-y: auto; width: 240px;
    }
    .emoji-btn {
      background: none; border: none; cursor: pointer;
      font-size: 1.15rem; padding: 0.25rem; border-radius: 4px; text-align: center;
    }
    .emoji-btn:hover { background: var(--surface2); }

    /* Image lightbox */
    #lightbox {
      position: fixed; inset: 0; background: rgba(0,0,0,0.85);
      display: none; align-items: center; justify-content: center; z-index: 200;
      cursor: zoom-out;
    }
    #lightbox.open { display: flex; }
    #lightbox img { max-width: 90vw; max-height: 90vh; border-radius: 8px; }

    /* ── Input area ── */
    #input-area {
      padding: 0.75rem 1rem; flex-shrink: 0;
    }
    /* Reply preview */
    #reply-preview {
      display: none; align-items: center; gap: 0.5rem;
      background: var(--surface2); border-radius: 8px 8px 0 0;
      border: 1px solid var(--border); border-bottom: none;
      padding: 0.5rem 0.75rem; font-size: 0.82rem; color: var(--muted);
    }
    #reply-preview.visible { display: flex; }
    #reply-preview .rp-name { font-weight: 700; color: var(--text); }
    #reply-preview .rp-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    #reply-cancel { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 1rem; margin-left: auto; padding: 0.1rem; }
    #reply-cancel:hover { color: var(--text); }

    /* Input box */
    #input-box {
      display: flex; align-items: flex-end; gap: 0.5rem;
      background: var(--surface2); border: 1px solid var(--border); border-radius: 8px;
      padding: 0.5rem 0.75rem;
    }
    #reply-preview.visible + #input-box {
      border-radius: 0 0 8px 8px;
    }
    #msg-input {
      flex: 1; background: none; border: none; color: var(--text);
      font-size: 0.92rem; font-family: inherit; resize: none;
      max-height: 150px; line-height: 1.5; outline: none; min-height: 24px;
    }
    #msg-input::placeholder { color: var(--muted2); }
    .input-btn {
      background: none; border: none; color: var(--muted); cursor: pointer;
      padding: 0.25rem; font-size: 1.15rem; line-height: 1; border-radius: 4px;
      flex-shrink: 0; transition: color 0.1s;
    }
    .input-btn:hover { color: var(--text); }
    #send-btn {
      background: var(--accent); border: none; color: white; cursor: pointer;
      padding: 0.3rem 0.85rem; border-radius: 6px; font-size: 0.88rem;
      font-weight: 600; flex-shrink: 0; transition: background 0.15s;
    }
    #send-btn:hover { background: var(--accent-hover); }
    #send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

    /* File attach preview */
    #attach-preview {
      display: flex; flex-wrap: wrap; gap: 0.4rem;
      margin-bottom: 0.4rem; display: none;
    }
    #attach-preview.visible { display: flex; }
    .attach-chip {
      display: flex; align-items: center; gap: 0.4rem;
      background: var(--surface3); border: 1px solid var(--border);
      border-radius: 6px; padding: 0.3rem 0.6rem; font-size: 0.8rem; color: var(--text);
    }
    .attach-remove { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 0.85rem; }
    .attach-remove:hover { color: var(--red); }

    /* Empty/loading states */
    .state-msg { margin: auto; text-align: center; color: var(--muted); font-size: 0.9rem; padding: 2rem; }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--surface3); border-radius: 3px; }

    /* Toast */
    #toast {
      position: fixed; bottom: 1.5rem; right: 1.5rem;
      background: var(--green); color: white; padding: 0.6rem 1.1rem;
      border-radius: 8px; font-size: 0.88rem; font-weight: 600;
      display: none; z-index: 999; box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    #toast.error { background: var(--red); }
  </style>
</head>
<body>

<div id="app">

  <!-- ── SIDEBAR ── -->
  <div id="sidebar">
    <div id="sidebar-header">🐟 Floppy Messenger</div>
    <input id="channel-search" type="text" placeholder="Search channels…" oninput="filterChannels(this.value)">
    <div id="channel-list"><div class="state-msg">Loading…</div></div>
  </div>

  <!-- ── CHAT ── -->
  <div id="chat">
    <div id="chat-header">
      <div id="chat-channel-name" style="color:var(--muted);">Select a channel</div>
      <div id="header-actions">
        <button class="icon-btn" title="Refresh" onclick="hardRefresh()">↻</button>
      </div>
    </div>

    <div id="messages">
      <div class="state-msg">Pick a channel on the left to start chatting.</div>
    </div>

    <div id="input-area">
      <div id="attach-preview"></div>
      <div id="reply-preview">
        <span>Replying to <span class="rp-name" id="rp-name"></span>:</span>
        <span class="rp-text" id="rp-text"></span>
        <button id="reply-cancel" onclick="cancelReply()" title="Cancel reply">✕</button>
      </div>
      <div id="input-box">
        <button class="input-btn" title="Attach file" onclick="document.getElementById('file-input').click()">📎</button>
        <input type="file" id="file-input" multiple accept="image/*,video/*,*/*" style="display:none" onchange="handleFiles(this.files)">
        <textarea id="msg-input" rows="1" placeholder="Select a channel first…"
          onkeydown="handleKey(event)" oninput="autoGrow(this)" disabled></textarea>
        <button class="input-btn" title="Add emoji" onclick="openEmojiPicker(null, event)">😊</button>
        <button id="send-btn" onclick="sendMessage()" disabled>Send</button>
      </div>
    </div>
  </div>
</div>

<!-- ── EMOJI PICKER ── -->
<div id="emoji-picker">
  <input id="emoji-search" type="text" placeholder="Search emoji…" oninput="filterEmoji(this.value)">
  <div id="emoji-grid"></div>
</div>

<!-- ── LIGHTBOX ── -->
<div id="lightbox" onclick="closeLightbox()">
  <img id="lightbox-img" src="" alt="">
</div>

<!-- ── TOAST ── -->
<div id="toast"></div>

<script>
// ── State ──
let guildData = { channels: [], categories: [] };
let activeChannel = null; // { id, name }
let replyTarget = null;   // { id, author, content }
let pendingFiles = [];
let lastMessageIds = new Set();
let pollInterval = null;
let emojiTarget = null;   // message id if reacting, null if inserting into text
let allChannels = [];

const AVATAR_COLORS = [
  '#5865f2','#3ba55d','#faa61a','#ed4245',
  '#9b59b6','#1abc9c','#e67e22','#e91e8c',
  '#2980b9','#16a085'
];

const COMMON_EMOJI = [
  '👍','👎','❤️','😂','😮','😢','🔥','🎉','✅','❌',
  '🙏','💯','😎','🤔','👀','💀','🫡','😭','🥹','🤣',
  '😅','🤦','🤷','💪','👏','🫶','😍','🥰','😜','🤩',
  '😤','😡','🥺','😳','🤯','😱','🤫','🫠','🥲','😈',
  '👾','🤖','💬','📌','📎','🔗','✨','⭐','💫','🌟'
];

// ── Helpers ──
function esc(s) {
  return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function avatarColor(seed) {
  let h = 0;
  for (let i = 0; i < (seed||'').length; i++) h = (h * 31 + seed.charCodeAt(i)) & 0x7fffffff;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

function initials(name) {
  return (name||'?').split(/\\s+/).map(w => w[0]).join('').toUpperCase().slice(0,2);
}

function toast(msg, error=false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = error ? 'error' : '';
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 2800);
}

function autoGrow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 150) + 'px';
}

// ── Channel sidebar ──
async function loadGuild() {
  try {
    const res = await fetch('/messenger/api/guild');
    const data = await res.json();
    if (!data.channels) return;
    guildData = data;
    allChannels = data.channels;
    renderChannels(data.channels, data.categories);
  } catch(e) {}
}

function renderChannels(channels, categories) {
  const list = document.getElementById('channel-list');
  if (!channels.length) {
    list.innerHTML = '<div class="state-msg">Bot not ready</div>';
    return;
  }

  // Group by category
  const byCategory = {};
  const noCat = [];
  for (const ch of channels) {
    if (ch.category_id) {
      if (!byCategory[ch.category_id]) byCategory[ch.category_id] = [];
      byCategory[ch.category_id].push(ch);
    } else {
      noCat.push(ch);
    }
  }

  let html = '';
  if (noCat.length) {
    html += noCat.map(ch => channelHTML(ch)).join('');
  }
  for (const cat of (categories || [])) {
    const chs = byCategory[cat.id] || [];
    if (!chs.length) continue;
    html += `<div class="ch-category">${esc(cat.name)}</div>`;
    html += chs.map(ch => channelHTML(ch)).join('');
  }
  list.innerHTML = html || '<div class="state-msg">No text channels</div>';
}

function channelHTML(ch) {
  const active = activeChannel && activeChannel.id === ch.id ? ' active' : '';
  const name = (ch.name || '').replace(/^# /, '');
  return `<div class="ch-item${active}" id="chi-${ch.id}" onclick="selectChannel('${ch.id}','${esc(name)}')" title="#${esc(name)}">
    <span class="ch-hash">#</span>${esc(name)}
  </div>`;
}

function filterChannels(q) {
  q = q.toLowerCase();
  const filtered = q ? allChannels.filter(ch => ch.name.toLowerCase().includes(q)) : allChannels;
  renderChannels(filtered, q ? [] : guildData.categories);
}

// ── Channel selection ──
async function selectChannel(id, name) {
  activeChannel = { id, name: name.replace(/^# /, '') };
  document.querySelectorAll('.ch-item').forEach(el => el.classList.remove('active'));
  const el = document.getElementById('chi-' + id);
  if (el) el.classList.add('active');
  document.getElementById('chat-channel-name').innerHTML =
    `<span class="hash">#</span>${esc(activeChannel.name)}`;
  document.getElementById('msg-input').placeholder = `Message #${activeChannel.name}…`;
  document.getElementById('msg-input').disabled = false;
  document.getElementById('send-btn').disabled = false;
  document.getElementById('messages').innerHTML = '<div class="state-msg">Loading messages…</div>';
  lastMessageIds = new Set();
  cancelReply();
  if (pollInterval) clearInterval(pollInterval);
  await fetchMessages();
  pollInterval = setInterval(fetchMessages, 4000);
}

// ── Fetch & render messages ──
async function fetchMessages() {
  if (!activeChannel) return;
  try {
    const res = await fetch(`/messenger/api/messages/${activeChannel.id}`);
    const data = await res.json();
    if (!data.ok) {
      document.getElementById('messages').innerHTML =
        `<div class="state-msg" style="color:var(--red)">${esc(data.error || 'Failed to load')}</div>`;
      return;
    }
    renderMessages(data.messages);
  } catch(e) {}
}

function hardRefresh() {
  lastMessageIds = new Set();
  fetchMessages();
}

function renderMessages(messages) {
  const container = document.getElementById('messages');
  const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 120;
  const newIds = new Set(messages.map(m => m.id));
  const hasNew = messages.some(m => !lastMessageIds.has(m.id));
  lastMessageIds = newIds;
  if (!hasNew && container.querySelector('.msg-wrapper')) return; // no changes

  if (!messages.length) {
    container.innerHTML = '<div class="state-msg">No messages yet. Say something!</div>';
    return;
  }

  let html = '';
  let prevAuthor = null;
  let prevTime = null;
  for (const m of messages) {
    const sameAuthor = prevAuthor === m.author_id;
    const timeDiff = prevTime && (m.timestamp - prevTime) < 300;
    const cont = sameAuthor && timeDiff;
    prevAuthor = m.author_id;
    prevTime = m.timestamp;
    html += buildMessage(m, cont);
  }
  container.innerHTML = html;
  if (atBottom || hasNew) container.scrollTop = container.scrollHeight;
}

function buildMessage(m, continuation) {
  const color = avatarColor(m.author_id);
  const botBadge = m.bot ? ' <span class="bot-badge">BOT</span>' : '';

  const avatarOrGap = continuation
    ? `<div class="avatar-gap"></div>`
    : `<div class="avatar" style="background:${color}" title="${esc(m.author)}">${initials(m.author)}</div>`;

  const metaLine = continuation ? '' :
    `<div class="msg-meta">
      <span class="msg-author">${esc(m.author)}${botBadge}</span>
      <span class="msg-time">${m.time}</span>
    </div>`;

  const replyBar = m.reply ? `
    <div class="reply-bar" onclick="scrollToMsg('${esc(m.reply.id)}')">
      <span class="reply-author">${esc(m.reply.author)}</span>
      <span>${esc((m.reply.content||'').slice(0,80))}</span>
    </div>` : '';

  const textLine = m.content
    ? `<div class="msg-text">${esc(m.content)}</div>` : '';

  const attachments = (m.attachments||[]).map(a => {
    if (a.type === 'image') {
      return `<img class="attachment-img" src="${esc(a.url)}" alt="${esc(a.name)}" onclick="openLightbox('${esc(a.url)}')">`;
    }
    return `<a class="attachment-file" href="${esc(a.url)}" target="_blank">📎 ${esc(a.name)}</a>`;
  }).join('');

  const reactions = (m.reactions||[]).length ? `
    <div class="reactions">
      ${m.reactions.map(r =>
        `<button class="reaction" onclick="addReaction('${m.id}','${esc(r.emoji)}')" title="${esc(r.emoji)}">
          ${r.emoji} <span class="reaction-count">${r.count}</span>
        </button>`
      ).join('')}
      <button class="add-reaction" onclick="openEmojiPicker('${m.id}', event)" title="Add reaction">+</button>
    </div>` : `
    <div class="reactions" id="rxn-${m.id}"></div>`;

  const actions = `
    <div class="msg-actions">
      <button class="msg-action-btn" title="React" onclick="openEmojiPicker('${m.id}', event)">😊</button>
      <button class="msg-action-btn" title="Reply" onclick="startReply('${m.id}','${esc(m.author)}','${esc((m.content||'').replace(/'/g,"\\'").slice(0,80))}')">↩</button>
    </div>`;

  return `<div class="msg-wrapper" id="msg-${m.id}">
    <div class="msg-group${continuation ? ' continuation' : ''}">
      ${avatarOrGap}
      <div class="msg-col">
        ${metaLine}
        ${replyBar}
        ${textLine}
        ${attachments}
        ${reactions}
      </div>
    </div>
    ${actions}
  </div>`;
}

function scrollToMsg(id) {
  const el = document.getElementById('msg-' + id);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ── Reply ──
function startReply(msgId, author, content) {
  replyTarget = { id: msgId, author, content };
  document.getElementById('rp-name').textContent = author;
  document.getElementById('rp-text').textContent = content || '[attachment]';
  document.getElementById('reply-preview').classList.add('visible');
  document.getElementById('msg-input').focus();
}

function cancelReply() {
  replyTarget = null;
  document.getElementById('reply-preview').classList.remove('visible');
}

// ── File attachments ──
function handleFiles(files) {
  for (const f of files) {
    if (pendingFiles.find(p => p.name === f.name && p.size === f.size)) continue;
    pendingFiles.push(f);
  }
  document.getElementById('file-input').value = '';
  renderAttachPreview();
}

function renderAttachPreview() {
  const container = document.getElementById('attach-preview');
  if (!pendingFiles.length) {
    container.classList.remove('visible');
    container.innerHTML = '';
    return;
  }
  container.classList.add('visible');
  container.innerHTML = pendingFiles.map((f, i) =>
    `<div class="attach-chip">
      ${f.type.startsWith('image/') ? '🖼️' : '📎'} ${esc(f.name)}
      <button class="attach-remove" onclick="removeFile(${i})" title="Remove">✕</button>
    </div>`
  ).join('');
}

function removeFile(i) {
  pendingFiles.splice(i, 1);
  renderAttachPreview();
}

// ── Send ──
async function sendMessage() {
  if (!activeChannel) return;
  const input = document.getElementById('msg-input');
  const content = input.value.trim();
  if (!content && !pendingFiles.length) return;

  const btn = document.getElementById('send-btn');
  btn.disabled = true; btn.textContent = '…';

  try {
    const fd = new FormData();
    fd.append('channel_id', activeChannel.id);
    if (content) fd.append('content', content);
    if (replyTarget) fd.append('reply_to', replyTarget.id);
    for (const f of pendingFiles) fd.append('files', f);

    const res = await fetch('/messenger/api/send', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
      input.value = '';
      input.style.height = 'auto';
      pendingFiles = [];
      renderAttachPreview();
      cancelReply();
      lastMessageIds = new Set();
      await fetchMessages();
    } else {
      toast(data.error || 'Failed to send', true);
    }
  } catch(e) { toast('Network error', true); }

  btn.disabled = false; btn.textContent = 'Send';
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

// ── Reactions ──
async function addReaction(msgId, emoji) {
  if (!activeChannel) return;
  try {
    const res = await fetch('/messenger/api/react', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ channel_id: activeChannel.id, message_id: msgId, emoji })
    });
    const data = await res.json();
    if (!data.ok) toast(data.error || 'Could not react', true);
    else { lastMessageIds = new Set(); await fetchMessages(); }
  } catch(e) { toast('Network error', true); }
  closeEmojiPicker();
}

// ── Emoji picker ──
let filteredEmoji = [...COMMON_EMOJI];

function openEmojiPicker(msgId, event) {
  event.stopPropagation();
  emojiTarget = msgId;
  const picker = document.getElementById('emoji-picker');
  document.getElementById('emoji-search').value = '';
  filteredEmoji = [...COMMON_EMOJI];
  renderEmojiGrid(COMMON_EMOJI);
  picker.classList.add('open');
  const rect = event.target.getBoundingClientRect();
  picker.style.left = Math.min(rect.left, window.innerWidth - 280) + 'px';
  picker.style.top = (rect.top - picker.offsetHeight - 8) + 'px';
  // Reposition after render
  requestAnimationFrame(() => {
    const h = picker.offsetHeight;
    picker.style.top = Math.max(8, rect.top - h - 8) + 'px';
  });
}

function closeEmojiPicker() {
  document.getElementById('emoji-picker').classList.remove('open');
  emojiTarget = null;
}

function renderEmojiGrid(list) {
  const grid = document.getElementById('emoji-grid');
  grid.innerHTML = list.map(e =>
    `<button class="emoji-btn" onclick="pickEmoji('${e}')">${e}</button>`
  ).join('');
}

function filterEmoji(q) {
  // Simple filter: just show all common emoji (no name search without a library)
  renderEmojiGrid(COMMON_EMOJI);
}

function pickEmoji(emoji) {
  if (emojiTarget) {
    addReaction(emojiTarget, emoji);
  } else {
    const input = document.getElementById('msg-input');
    const pos = input.selectionStart;
    input.value = input.value.slice(0, pos) + emoji + input.value.slice(pos);
    input.selectionStart = input.selectionEnd = pos + emoji.length;
    input.focus();
    autoGrow(input);
    closeEmojiPicker();
  }
}

document.addEventListener('click', e => {
  const picker = document.getElementById('emoji-picker');
  if (picker.classList.contains('open') && !picker.contains(e.target)) {
    closeEmojiPicker();
  }
});

// ── Lightbox ──
function openLightbox(url) {
  document.getElementById('lightbox-img').src = url;
  document.getElementById('lightbox').classList.add('open');
}
function closeLightbox() {
  document.getElementById('lightbox').classList.remove('open');
}
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeLightbox();
    closeEmojiPicker();
  }
});

// ── Init ──
loadGuild();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

@messenger_app.route("/")
async def index():
    return await render_template_string(PAGE)


@messenger_app.route("/api/guild")
async def guild():
    bot = state.bot
    if not bot or not bot.guilds:
        return jsonify({"channels": [], "roles": [], "categories": []})
    g = bot.guilds[0]
    channels = [
        {
            "id": str(c.id),
            "name": c.name,
            "category_id": str(c.category_id) if c.category_id else None,
            "position": c.position,
        }
        for c in sorted(g.text_channels, key=lambda c: c.position)
    ]
    categories = [
        {"id": str(c.id), "name": c.name, "position": c.position}
        for c in sorted(g.categories, key=lambda c: c.position)
    ]
    return jsonify({"channels": channels, "categories": categories})


@messenger_app.route("/api/messages/<int:channel_id>")
async def get_messages(channel_id):
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503
    channel = bot.get_channel(channel_id)
    if not channel:
        return jsonify({"ok": False, "error": "Channel not found or no access"}), 404
    try:
        messages = []
        async for msg in channel.history(limit=60):
            reply = None
            if msg.reference and msg.reference.resolved:
                ref = msg.reference.resolved
                reply = {
                    "id": str(ref.id),
                    "author": ref.author.display_name if hasattr(ref, "author") and ref.author else "Unknown",
                    "content": ref.content or "",
                }
            attachments = []
            for a in msg.attachments:
                is_image = a.content_type and a.content_type.startswith("image/")
                attachments.append({
                    "name": a.filename,
                    "url": a.url,
                    "type": "image" if is_image else "file",
                })
            reactions = []
            for r in msg.reactions:
                reactions.append({
                    "emoji": str(r.emoji),
                    "count": r.count,
                })
            messages.append({
                "id": str(msg.id),
                "author": msg.author.display_name if msg.author else "Unknown",
                "author_id": str(msg.author.id) if msg.author else "0",
                "bot": msg.author.bot if msg.author else False,
                "content": msg.content or "",
                "time": msg.created_at.strftime("%H:%M"),
                "timestamp": msg.created_at.timestamp(),
                "reply": reply,
                "attachments": attachments,
                "reactions": reactions,
            })
        messages.reverse()
        return jsonify({"ok": True, "messages": messages})
    except Exception as e:
        print(f"[get_messages] Error for channel {channel_id}: {e}", flush=True)
        return jsonify({"ok": False, "error": str(e)}), 500


@messenger_app.route("/api/send", methods=["POST"])
async def send_message():
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503

    form = await request.form
    files = await request.files

    channel_id = form.get("channel_id")
    content = form.get("content", "").strip()
    reply_to = form.get("reply_to")

    if not channel_id:
        return jsonify({"ok": False, "error": "Missing channel_id"}), 400
    if not content and not files.getlist("files"):
        return jsonify({"ok": False, "error": "Nothing to send"}), 400
    if content and len(content) > 2000:
        return jsonify({"ok": False, "error": "Message exceeds 2000 chars"}), 400

    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({"ok": False, "error": "Channel not found"}), 404

    import discord as _discord

    try:
        reference = None
        if reply_to:
            try:
                ref_msg = await channel.fetch_message(int(reply_to))
                reference = ref_msg.to_reference()
            except Exception:
                pass

        # Build file objects
        discord_files = []
        for f in files.getlist("files"):
            data = f.read()
            discord_files.append(_discord.File(io.BytesIO(data), filename=f.filename))

        await channel.send(
            content or None,
            reference=reference,
            files=discord_files if discord_files else _discord.utils.MISSING,
        )
        state.add_log(f"Messenger sent to #{channel.name}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@messenger_app.route("/api/react", methods=["POST"])
async def react():
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503

    data = await request.get_json()
    channel_id = data.get("channel_id")
    message_id = data.get("message_id")
    emoji = data.get("emoji")

    if not all([channel_id, message_id, emoji]):
        return jsonify({"ok": False, "error": "Missing fields"}), 400

    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({"ok": False, "error": "Channel not found"}), 404

    try:
        msg = await channel.fetch_message(int(message_id))
        await msg.add_reaction(emoji)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
