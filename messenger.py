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
      --bg: #1e1f22; --surface: #2b2d31; --surface2: #313338; --surface3: #383a40;
      --border: #3f4248; --text: #dbdee1; --muted: #949ba4; --muted2: #6d6f78;
      --accent: #5865f2; --accent-hover: #4752c4; --accent-dim: rgba(88,101,242,0.18);
      --green: #23a55a; --red: #f23f43; --yellow: #faa61a;
      --server-w: 72px; --sidebar-w: 240px; --members-w: 240px;
    }
    html, body { height: 100%; overflow: hidden; font-family: 'gg sans','Noto Sans','Helvetica Neue',Helvetica,Arial,sans-serif; background: var(--bg); color: var(--text); font-size: 15px; }
    #app { display: flex; height: 100vh; }

    /* Server Rail */
    #server-rail { width: var(--server-w); flex-shrink: 0; background: var(--bg); display: flex; flex-direction: column; align-items: center; padding: 12px 0; gap: 8px; overflow-y: auto; border-right: 1px solid var(--border); }
    .server-icon { width: 48px; height: 48px; border-radius: 50%; background: var(--surface); display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 1.3rem; font-weight: 700; color: white; transition: border-radius 0.15s, background 0.15s; position: relative; flex-shrink: 0; overflow: hidden; user-select: none; }
    .server-icon.active { border-radius: 30%; background: var(--accent); }
    .server-icon:hover:not(.active) { border-radius: 30%; background: var(--surface3); }
    .server-icon img { width: 100%; height: 100%; object-fit: cover; }
    .server-pill { position: absolute; left: 0; top: 50%; transform: translateY(-50%); width: 4px; background: var(--text); border-radius: 0 4px 4px 0; transition: height 0.15s; height: 0; }
    .server-icon.active .server-pill { height: 36px; }
    .server-icon:hover .server-pill { height: 20px; }
    .rail-divider { width: 32px; height: 2px; background: var(--border); border-radius: 2px; margin: 4px 0; }

    /* Sidebar */
    #sidebar { width: var(--sidebar-w); flex-shrink: 0; background: var(--surface); display: flex; flex-direction: column; overflow: hidden; border-right: 1px solid var(--border); }
    #sidebar-header { padding: 0 16px; height: 48px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; font-weight: 700; font-size: 0.95rem; flex-shrink: 0; cursor: pointer; }
    #sidebar-header:hover { background: var(--surface2); }
    #channel-scroll { flex: 1; overflow-y: auto; padding: 8px 8px 80px; }

    /* Category */
    .cat-header { display: flex; align-items: center; gap: 4px; padding: 16px 8px 4px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); cursor: pointer; user-select: none; }
    .cat-header:hover { color: var(--text); }
    .cat-arrow { font-size: 0.6rem; transition: transform 0.15s; display: inline-block; }
    .cat-header.collapsed .cat-arrow { transform: rotate(-90deg); }

    /* Channel row */
    .ch-row { display: flex; align-items: center; gap: 6px; padding: 3px 8px; border-radius: 4px; cursor: pointer; font-size: 0.95rem; color: var(--muted); transition: background 0.1s, color 0.1s; white-space: nowrap; overflow: hidden; min-height: 32px; position: relative; }
    .ch-row:hover { background: var(--surface2); color: var(--text); }
    .ch-row.active { background: var(--surface3); color: white; }
    .ch-icon { font-size: 1rem; flex-shrink: 0; opacity: 0.7; width: 18px; text-align: center; font-style: normal; }
    .ch-name { flex: 1; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }
    .ch-row.voice { opacity: 0.7; }
    .ch-row.disabled { cursor: default; }
    .ch-row.disabled:hover { background: transparent; color: var(--muted); }

    /* DM section */
    .dm-section-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 8px 4px; }
    .dm-section-title { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
    .dm-add-btn { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 1.1rem; padding: 2px 4px; border-radius: 3px; line-height: 1; }
    .dm-add-btn:hover { color: var(--text); }

    /* User bar */
    #user-bar { position: absolute; bottom: 0; left: var(--server-w); width: var(--sidebar-w); background: #232428; border-top: 1px solid var(--border); padding: 8px; display: flex; align-items: center; gap: 8px; z-index: 10; }
    .ubar-avatar { width: 32px; height: 32px; border-radius: 50%; background: var(--accent); display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; flex-shrink: 0; }
    .ubar-name { font-size: 0.85rem; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .ubar-tag { font-size: 0.72rem; color: var(--muted); }

    /* Chat */
    #chat { flex: 1; display: flex; flex-direction: column; min-width: 0; background: var(--surface2); }
    #chat-header { height: 48px; border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 16px; gap: 8px; flex-shrink: 0; background: var(--surface2); }
    #chat-icon { font-size: 1.2rem; color: var(--muted); flex-shrink: 0; }
    #chat-channel-name { font-weight: 700; font-size: 1rem; }
    #chat-channel-topic { font-size: 0.8rem; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px; padding-left: 8px; border-left: 1px solid var(--border); margin-left: 4px; }
    #header-actions { display: flex; gap: 4px; margin-left: auto; }
    .hdr-btn { background: none; border: none; color: var(--muted); cursor: pointer; padding: 6px; border-radius: 4px; font-size: 1rem; line-height: 1; }
    .hdr-btn:hover { color: var(--text); background: var(--surface3); }

    /* Messages */
    #messages { flex: 1; overflow-y: auto; padding: 16px 0 8px; display: flex; flex-direction: column; }
    .msg-divider { display: flex; align-items: center; gap: 8px; padding: 16px 16px 8px; }
    .msg-divider-line { flex: 1; height: 1px; background: var(--border); }
    .msg-divider-date { font-size: 0.72rem; color: var(--muted); font-weight: 600; white-space: nowrap; }
    .msg-wrapper { position: relative; padding: 2px 16px; }
    .msg-wrapper:hover { background: rgba(4,4,5,0.07); }
    .msg-wrapper:hover .msg-actions { display: flex; }
    .msg-group { display: flex; gap: 16px; }
    .msg-group.first { padding-top: 12px; }
    .avatar { width: 40px; height: 40px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 0.82rem; font-weight: 700; color: white; cursor: pointer; }
    .avatar-spacer { width: 40px; flex-shrink: 0; }
    .msg-col { flex: 1; min-width: 0; }
    .msg-meta { display: flex; align-items: baseline; gap: 8px; margin-bottom: 2px; }
    .msg-author { font-size: 1rem; font-weight: 700; cursor: pointer; }
    .msg-time { font-size: 0.72rem; color: var(--muted); }
    .bot-tag { background: var(--accent); color: white; font-size: 0.65rem; font-weight: 700; border-radius: 3px; padding: 1px 5px; letter-spacing: 0.02em; }
    .msg-text { font-size: 1rem; line-height: 1.375; word-break: break-word; white-space: pre-wrap; color: var(--text); }
    .msg-text a { color: #00b0f4; text-decoration: none; }
    .msg-text a:hover { text-decoration: underline; }
    .hover-time { display: none; position: absolute; left: 16px; top: 50%; transform: translateY(-50%); font-size: 0.65rem; color: var(--muted); width: 40px; text-align: center; pointer-events: none; }
    .msg-wrapper.cont:hover .hover-time { display: block; }
    .reply-bar { display: flex; align-items: center; gap: 6px; font-size: 0.82rem; color: var(--muted); margin-bottom: 4px; padding-left: 12px; border-left: 2px solid var(--muted2); cursor: pointer; max-width: 600px; }
    .reply-bar:hover { color: var(--text); }
    .reply-author { font-weight: 700; flex-shrink: 0; }
    .reply-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .attachment-img { margin-top: 8px; max-width: 520px; max-height: 350px; border-radius: 3px; display: block; cursor: zoom-in; }
    .attachment-file { margin-top: 8px; display: inline-flex; align-items: center; gap: 8px; background: var(--surface); border: 1px solid var(--border); border-radius: 3px; padding: 10px 16px; font-size: 0.88rem; color: var(--text); text-decoration: none; }
    .attachment-file:hover { background: var(--surface3); }
    .reactions { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
    .reaction { display: flex; align-items: center; gap: 5px; background: var(--surface3); border: 1px solid var(--border); border-radius: 8px; padding: 2px 8px; font-size: 0.85rem; cursor: pointer; color: var(--text); }
    .reaction:hover { background: var(--accent-dim); border-color: var(--accent); }
    .reaction-count { font-size: 0.78rem; color: var(--muted); font-weight: 600; }
    .add-reaction { background: none; border: 1px solid transparent; border-radius: 8px; padding: 2px 8px; font-size: 0.85rem; cursor: pointer; color: var(--muted); }
    .add-reaction:hover { background: var(--surface3); border-color: var(--border); color: var(--text); }
    .msg-actions { display: none; position: absolute; right: 16px; top: -16px; background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 2px; gap: 1px; z-index: 10; box-shadow: 0 4px 16px rgba(0,0,0,0.3); }
    .mac-btn { background: none; border: none; color: var(--muted); cursor: pointer; padding: 6px 8px; border-radius: 3px; font-size: 0.9rem; line-height: 1; display: flex; align-items: center; gap: 4px; }
    .mac-btn:hover { background: var(--surface2); color: var(--text); }
    .mac-btn.danger:hover { background: var(--red); color: white; }

    /* Emoji picker */
    #emoji-picker { position: fixed; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 10px; display: none; z-index: 200; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }
    #emoji-picker.open { display: block; }
    #emoji-search { width: 100%; padding: 6px 10px; background: var(--bg); border: 1px solid var(--border); border-radius: 4px; color: var(--text); font-family: inherit; font-size: 0.82rem; margin-bottom: 8px; }
    #emoji-search:focus { outline: none; border-color: var(--accent); }
    #emoji-grid { display: grid; grid-template-columns: repeat(9,1fr); gap: 1px; max-height: 180px; overflow-y: auto; width: 260px; }
    .emoji-btn { background: none; border: none; cursor: pointer; font-size: 1.2rem; padding: 4px; border-radius: 3px; text-align: center; }
    .emoji-btn:hover { background: var(--surface2); }

    /* Input area */
    #input-area { padding: 0 16px 24px; flex-shrink: 0; }
    #reply-preview { display: none; align-items: center; gap: 8px; background: var(--surface3); border-radius: 8px 8px 0 0; padding: 8px 12px; font-size: 0.82rem; color: var(--muted); border: 1px solid var(--border); border-bottom: none; }
    #reply-preview.visible { display: flex; }
    #reply-preview .rp-name { font-weight: 700; color: var(--text); }
    #reply-preview .rp-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    #reply-cancel { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 1rem; margin-left: auto; }
    #reply-cancel:hover { color: var(--text); }
    #attach-preview { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
    #attach-preview:empty { display: none; }
    .attach-chip { display: flex; align-items: center; gap: 6px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 4px 10px; font-size: 0.8rem; color: var(--text); }
    .attach-remove { background: none; border: none; color: var(--muted); cursor: pointer; }
    .attach-remove:hover { color: var(--red); }
    #input-box { display: flex; align-items: flex-end; gap: 4px; background: var(--surface3); border-radius: 8px; padding: 11px 16px; }
    #msg-input { flex: 1; background: none; border: none; color: var(--text); font-size: 1rem; font-family: inherit; resize: none; max-height: 150px; line-height: 1.375; outline: none; min-height: 22px; }
    #msg-input::placeholder { color: var(--muted2); }
    .input-action { background: none; border: none; color: var(--muted2); cursor: pointer; padding: 2px 6px; font-size: 1.2rem; line-height: 1; border-radius: 4px; flex-shrink: 0; transition: color 0.1s; }
    .input-action:hover { color: var(--muted); }
    #send-btn { background: none; border: none; color: var(--muted2); cursor: pointer; padding: 2px 6px; font-size: 1.2rem; border-radius: 4px; flex-shrink: 0; transition: color 0.1s; }
    #send-btn.ready { color: var(--accent); }
    #send-btn:hover { background: var(--border); }
    #send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

    /* Members panel */
    #members-panel { width: var(--members-w); flex-shrink: 0; background: var(--surface); border-left: 1px solid var(--border); overflow-y: auto; padding: 16px 8px; }
    #members-panel.hidden { display: none; }
    .members-cat { font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); padding: 16px 8px 4px; }
    .member-row { display: flex; align-items: center; gap: 10px; padding: 4px 8px; border-radius: 4px; cursor: pointer; }
    .member-row:hover { background: var(--surface2); }
    .member-avatar { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 700; color: white; flex-shrink: 0; }
    .member-name { font-size: 0.9rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); }

    /* Lightbox */
    #lightbox { position: fixed; inset: 0; background: rgba(0,0,0,0.87); display: none; align-items: center; justify-content: center; z-index: 300; cursor: zoom-out; }
    #lightbox.open { display: flex; }
    #lightbox img { max-width: 90vw; max-height: 90vh; border-radius: 4px; }

    /* Toast */
    #toast { position: fixed; bottom: 24px; right: 24px; background: var(--surface); color: var(--text); border: 1px solid var(--border); padding: 12px 16px; border-radius: 8px; font-size: 0.88rem; font-weight: 600; display: none; z-index: 999; box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
    #toast.error { border-color: var(--red); color: var(--red); }

    /* DM Modal */
    #new-dm-modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75); z-index: 400; align-items: center; justify-content: center; }
    #new-dm-modal.open { display: flex; }
    .modal-box { background: var(--surface); border-radius: 8px; padding: 24px; width: 420px; max-width: 92vw; }
    .modal-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 4px; }
    .modal-sub { font-size: 0.85rem; color: var(--muted); margin-bottom: 16px; }
    .modal-input { width: 100%; padding: 10px 12px; background: var(--bg); border: 1px solid var(--border); border-radius: 4px; color: var(--text); font-family: inherit; font-size: 0.92rem; margin-bottom: 12px; }
    .modal-input:focus { outline: none; border-color: var(--accent); }
    .modal-results { max-height: 220px; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
    .modal-member { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 4px; cursor: pointer; }
    .modal-member:hover { background: var(--surface2); }
    .modal-footer { display: flex; justify-content: flex-end; margin-top: 16px; }
    .modal-btn { padding: 8px 20px; border-radius: 4px; border: none; font-size: 0.9rem; font-weight: 600; cursor: pointer; background: none; color: var(--muted); }
    .modal-btn:hover { text-decoration: underline; }

    /* Empty state */
    .empty-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--muted); gap: 8px; padding: 32px; text-align: center; }
    .empty-state .e-icon { font-size: 3rem; opacity: 0.4; }
    .empty-state h3 { color: var(--text); font-size: 1.1rem; }
    .empty-state p { font-size: 0.9rem; max-width: 280px; }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--surface3); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--border); }
  </style>
</head>
<body>
<div id="app">

  <!-- SERVER RAIL -->
  <div id="server-rail">
    <div class="server-icon active" id="rail-server-icon" title="Server" onclick="showServerView()">
      <div class="server-pill"></div>
      <span id="rail-icon-inner">🐟</span>
    </div>
    <div class="rail-divider"></div>
    <div class="server-icon" id="rail-dm-icon" title="Direct Messages" onclick="showDMView()">
      <div class="server-pill"></div>
      💬
    </div>
  </div>

  <!-- CHANNEL SIDEBAR -->
  <div id="sidebar">
    <div id="sidebar-header">
      <span id="sidebar-guild-name">Loading…</span>
      <span style="color:var(--muted);font-size:0.85rem">▾</span>
    </div>
    <div id="channel-scroll">
      <div id="channel-list-inner">
        <div style="padding:16px;color:var(--muted);font-size:0.85rem">Loading channels…</div>
      </div>
    </div>
    <div id="user-bar">
      <div class="ubar-avatar" id="ubar-avatar">🐟</div>
      <div style="flex:1;min-width:0">
        <div class="ubar-name" id="ubar-name">Floppy</div>
        <div class="ubar-tag">Bot</div>
      </div>
    </div>
  </div>

  <!-- CHAT -->
  <div id="chat">
    <div id="chat-header">
      <span id="chat-icon" style="font-size:1.2rem;color:var(--muted);flex-shrink:0">#</span>
      <span id="chat-channel-name" style="font-weight:700;font-size:1rem;color:var(--muted)">Select a channel</span>
      <span id="chat-channel-topic" style="font-size:0.8rem;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:300px;padding-left:8px;border-left:1px solid var(--border);margin-left:4px"></span>
      <div id="header-actions">
        <button class="hdr-btn" title="Toggle members" onclick="toggleMembers()">👥</button>
        <button class="hdr-btn" title="Refresh" onclick="hardRefresh()">↻</button>
      </div>
    </div>

    <div id="messages">
      <div class="empty-state">
        <div class="e-icon">🐟</div>
        <h3>Floppy Messenger</h3>
        <p>Pick a channel or DM on the left to start messaging as Floppy.</p>
      </div>
    </div>

    <div id="input-area">
      <div id="reply-preview">
        <span>↩ Replying to <span class="rp-name" id="rp-name"></span></span>
        <span class="rp-text" id="rp-text"></span>
        <button id="reply-cancel" onclick="cancelReply()">✕</button>
      </div>
      <div id="attach-preview"></div>
      <div id="input-box">
        <button class="input-action" title="Attach" onclick="document.getElementById('file-input').click()">＋</button>
        <input type="file" id="file-input" multiple style="display:none" onchange="handleFiles(this.files)">
        <textarea id="msg-input" rows="1" placeholder="Select a channel first…" disabled
          onkeydown="handleKey(event)" oninput="autoGrow(this);updateSendBtn()"></textarea>
        <button class="input-action" title="Emoji" onclick="openEmojiPicker(null,event)">😊</button>
        <button id="send-btn" title="Send" onclick="sendMessage()" disabled>➤</button>
      </div>
    </div>
  </div>

  <!-- MEMBERS PANEL -->
  <div id="members-panel" class="hidden">
    <div class="members-cat">Members</div>
    <div id="members-list"><div style="padding:8px;color:var(--muted);font-size:0.85rem">Loading…</div></div>
  </div>

</div>

<!-- DM MODAL -->
<div id="new-dm-modal">
  <div class="modal-box">
    <div class="modal-title">Open Direct Message</div>
    <div class="modal-sub">Message a server member as Floppy.</div>
    <input class="modal-input" id="dm-search" type="text" placeholder="Search by name…" oninput="filterDMSearch(this.value)" autocomplete="off">
    <div class="modal-results" id="dm-results"></div>
    <div class="modal-footer"><button class="modal-btn" onclick="closeDMModal()">Cancel</button></div>
  </div>
</div>

<!-- EMOJI PICKER -->
<div id="emoji-picker">
  <input id="emoji-search" type="text" placeholder="Search emoji…" oninput="filterEmoji(this.value)">
  <div id="emoji-grid"></div>
</div>

<!-- LIGHTBOX -->
<div id="lightbox" onclick="closeLightbox()"><img id="lightbox-img" src="" alt=""></div>

<!-- TOAST -->
<div id="toast"></div>

<script>
// STATE
let guildData = { channels:[], categories:[], members:[], dms:[] };
let activeChannel = null;
let replyTarget = null;
let pendingFiles = [];
let lastMsgIds = new Set();
let pollTimer = null;
let emojiTarget = null;
let allMembers = [];
let allChannels = [];
let viewMode = 'server';
let membersOpen = false;

const AVATAR_COLORS = ['#5865f2','#3ba55d','#faa61a','#ed4245','#9b59b6','#1abc9c','#e67e22','#e91e8c','#2980b9','#16a085'];
const EMOJI_LIST = ['👍','👎','❤️','😂','😮','😢','🔥','🎉','✅','❌','🙏','💯','😎','🤔','👀','💀','🫡','😭','🥹','🤣','😅','🤦','🤷','💪','👏','🫶','😍','🥰','😜','🤩','😤','😡','🥺','😳','🤯','😱','🤫','🫠','🥲','😈','👾','🤖','💬','📌','📎','🔗','✨','⭐','💫','🌟','🎵','🎮','🍕','☕','🌙','☀️','⚡','💥','🎯','🏆'];

// HELPERS
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function avatarColor(seed){let h=0;for(let i=0;i<(seed||'').length;i++)h=(h*31+seed.charCodeAt(i))&0x7fffffff;return AVATAR_COLORS[h%AVATAR_COLORS.length];}
function initials(name){return (name||'?').split(' ').map(w=>w[0]||'').join('').toUpperCase().slice(0,2)||'?';}
function autoGrow(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,150)+'px';}
function updateSendBtn(){const v=document.getElementById('msg-input').value.trim();const btn=document.getElementById('send-btn');btn.classList.toggle('ready',!!(v||pendingFiles.length));}
function toast(msg,type='ok'){const el=document.getElementById('toast');el.textContent=msg;el.className=type;el.style.display='block';clearTimeout(el._t);el._t=setTimeout(()=>el.style.display='none',3000);}
function chanIcon(type){return {text:'#',voice:'🔊',announcement:'📣',news:'📣',forum:'💬',stage:'🎙️',dm:'💬'}[type]||'#';}

// INIT
async function init(){
  await loadGuild();
  loadMembers();
}

async function loadGuild(){
  try{
    const res=await fetch('/messenger/api/guild');
    const data=await res.json();
    guildData=data;
    allChannels=data.channels||[];
    document.getElementById('sidebar-guild-name').textContent=data.guild_name||'Server';
    const iconEl=document.getElementById('rail-icon-inner');
    if(data.guild_icon){
      iconEl.innerHTML='<img src="'+data.guild_icon+'" style="width:100%;height:100%;object-fit:cover;border-radius:inherit">';
    } else {
      iconEl.textContent=(data.guild_name||'?')[0].toUpperCase();
    }
    if(data.bot_name){document.getElementById('ubar-name').textContent=data.bot_name;}
    if(viewMode==='server') renderServerChannels();
    loadDMs();
  }catch(e){console.error(e);}
}

async function loadDMs(){
  try{
    const res=await fetch('/messenger/api/dms');
    const data=await res.json();
    guildData.dms=data.dms||[];
    if(viewMode==='dm') renderDMView();
  }catch(e){}
}

async function loadMembers(){
  try{
    const res=await fetch('/messenger/api/members');
    const data=await res.json();
    allMembers=data.members||[];
    renderMembersPanel();
  }catch(e){}
}

// VIEW SWITCHING
function showServerView(){
  viewMode='server';
  document.getElementById('rail-server-icon').classList.add('active');
  document.getElementById('rail-dm-icon').classList.remove('active');
  renderServerChannels();
}
function showDMView(){
  viewMode='dm';
  document.getElementById('rail-dm-icon').classList.add('active');
  document.getElementById('rail-server-icon').classList.remove('active');
  renderDMView();
}

// RENDER SERVER CHANNELS
function renderServerChannels(){
  const wrap=document.getElementById('channel-list-inner');
  const channels=guildData.channels||[];
  const categories=guildData.categories||[];
  if(!channels.length){wrap.innerHTML='<div style="padding:16px;color:var(--muted);font-size:0.85rem">No channels</div>';return;}

  const byCat={};const noCat=[];
  for(const ch of channels){
    if(ch.category_id){(byCat[ch.category_id]=byCat[ch.category_id]||[]).push(ch);}
    else noCat.push(ch);
  }

  let html='';
  for(const ch of noCat) html+=channelRow(ch);
  for(const cat of categories){
    const chs=byCat[cat.id]||[];
    if(!chs.length) continue;
    html+=`<div class="cat-header" onclick="toggleCat('${cat.id}',this)"><span class="cat-arrow">▾</span> ${esc(cat.name.toUpperCase())}</div>`;
    html+=`<div id="cat-${cat.id}">${chs.map(ch=>channelRow(ch)).join('')}</div>`;
  }
  wrap.innerHTML=html;
}

function channelRow(ch){
  const isActive=activeChannel&&!activeChannel.isDM&&activeChannel.id===ch.id;
  const clickable=['text','announcement','news','forum'].includes(ch.type);
  const icon=chanIcon(ch.type);
  const cls=['ch-row',ch.type,isActive?'active':'',!clickable?'disabled':''].filter(Boolean).join(' ');
  const click=clickable?`onclick="selectChannel('${ch.id}','${esc(ch.name)}','${ch.type}','${esc((ch.topic||'').replace(/'/g,"\\'")))}'"`:'';
  return `<div class="${cls}" id="chi-${ch.id}" ${click} title="${esc(ch.name)}">
    <span class="ch-icon">${icon}</span>
    <span class="ch-name">${esc(ch.name)}</span>
  </div>`;
}

function toggleCat(id,header){
  header.classList.toggle('collapsed');
  const el=document.getElementById('cat-'+id);
  if(el) el.style.display=header.classList.contains('collapsed')?'none':'';
}

// RENDER DM VIEW
function renderDMView(){
  const wrap=document.getElementById('channel-list-inner');
  const dms=guildData.dms||[];
  let html=`<div class="dm-section-header"><span class="dm-section-title">Direct Messages</span><button class="dm-add-btn" onclick="openDMModal()" title="New DM">✎</button></div>`;
  if(!dms.length){
    html+='<div style="padding:8px 16px;color:var(--muted);font-size:0.85rem">No recent DMs — click ✎ to start one</div>';
  }else{
    for(const dm of dms){
      const isActive=activeChannel&&activeChannel.isDM&&activeChannel.userId===dm.user_id;
      const c=avatarColor(dm.user_id);
      html+=`<div class="ch-row${isActive?' active':''}" id="chi-dm-${dm.user_id}" onclick="selectDM('${dm.user_id}','${esc(dm.display_name||dm.username)}')" title="${esc(dm.display_name||dm.username)}">
        <div style="width:28px;height:28px;border-radius:50%;background:${c};display:flex;align-items:center;justify-content:center;font-size:0.68rem;font-weight:700;color:white;flex-shrink:0">${initials(dm.display_name||dm.username)}</div>
        <span class="ch-name">${esc(dm.display_name||dm.username)}</span>
      </div>`;
    }
  }
  wrap.innerHTML=html;
}

// SELECT CHANNEL / DM
async function selectChannel(id,name,type,topic){
  activeChannel={id,name,isDM:false,type,topic};
  document.querySelectorAll('.ch-row').forEach(el=>el.classList.remove('active'));
  const el=document.getElementById('chi-'+id);if(el)el.classList.add('active');
  document.getElementById('chat-icon').textContent=chanIcon(type);
  document.getElementById('chat-channel-name').textContent=name;
  document.getElementById('chat-channel-name').style.color='var(--text)';
  document.getElementById('chat-channel-topic').textContent=topic||'';
  document.getElementById('msg-input').placeholder='Message #'+name;
  document.getElementById('msg-input').disabled=false;
  document.getElementById('send-btn').disabled=false;
  startPolling();
}

async function selectDM(userId,username){
  activeChannel={id:userId,name:username,isDM:true,userId};
  document.querySelectorAll('.ch-row').forEach(el=>el.classList.remove('active'));
  const el=document.getElementById('chi-dm-'+userId);if(el)el.classList.add('active');
  document.getElementById('chat-icon').textContent='💬';
  document.getElementById('chat-channel-name').textContent=username;
  document.getElementById('chat-channel-name').style.color='var(--text)';
  document.getElementById('chat-channel-topic').textContent='';
  document.getElementById('msg-input').placeholder='Message '+username;
  document.getElementById('msg-input').disabled=false;
  document.getElementById('send-btn').disabled=false;
  startPolling();
}

function startPolling(){
  cancelReply();lastMsgIds=new Set();
  document.getElementById('messages').innerHTML='<div style="padding:32px;color:var(--muted);text-align:center;font-size:0.9rem">Loading messages…</div>';
  if(pollTimer)clearInterval(pollTimer);
  fetchMessages();
  pollTimer=setInterval(fetchMessages,3500);
}
function hardRefresh(){lastMsgIds=new Set();fetchMessages();}

// FETCH & RENDER MESSAGES
async function fetchMessages(){
  if(!activeChannel)return;
  try{
    const url=activeChannel.isDM
      ?`/messenger/api/dm-messages/${activeChannel.userId}`
      :`/messenger/api/messages/${activeChannel.id}`;
    const res=await fetch(url);
    const data=await res.json();
    if(!data.ok){
      document.getElementById('messages').innerHTML=`<div class="empty-state"><div class="e-icon">⚠️</div><h3>Error</h3><p>${esc(data.error||'Failed to load')}</p></div>`;
      return;
    }
    renderMessages(data.messages||[]);
  }catch(e){}
}

function renderMessages(messages){
  const container=document.getElementById('messages');
  const atBottom=container.scrollHeight-container.scrollTop-container.clientHeight<150;
  const newIds=new Set(messages.map(m=>m.id));
  const hasNew=messages.some(m=>!lastMsgIds.has(m.id));
  lastMsgIds=newIds;
  if(!hasNew&&container.querySelector('.msg-wrapper'))return;
  if(!messages.length){container.innerHTML='<div class="empty-state"><div class="e-icon">💬</div><h3>No messages yet</h3><p>Be the first to say something!</p></div>';return;}

  let html='';let prevAuthor=null,prevTime=null,prevDate=null;
  for(const m of messages){
    const d=new Date(m.timestamp*1000);
    const dateStr=d.toLocaleDateString(undefined,{weekday:'long',year:'numeric',month:'long',day:'numeric'});
    if(dateStr!==prevDate){
      html+=`<div class="msg-divider"><div class="msg-divider-line"></div><div class="msg-divider-date">${esc(dateStr)}</div><div class="msg-divider-line"></div></div>`;
      prevDate=dateStr;prevAuthor=null;prevTime=null;
    }
    const cont=prevAuthor===m.author_id&&m.timestamp-prevTime<420;
    prevAuthor=m.author_id;prevTime=m.timestamp;
    html+=buildMessage(m,cont);
  }
  container.innerHTML=html;
  if(atBottom||hasNew)container.scrollTop=container.scrollHeight;
}

function buildMessage(m,cont){
  const color=avatarColor(m.author_id);
  const timeStr=new Date(m.timestamp*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  const avatarPart=cont
    ?'<div class="avatar-spacer"></div>'
    :`<div class="avatar" style="background:${color}" title="${esc(m.author)}">${initials(m.author)}</div>`;
  const meta=cont?'':`<div class="msg-meta"><span class="msg-author" style="color:${color}">${esc(m.author)}</span>${m.bot?'<span class="bot-tag">BOT</span>':''}<span class="msg-time">${esc(timeStr)}</span></div>`;
  const hoverTime=cont?`<span class="hover-time">${esc(timeStr)}</span>`:'';
  const reply=m.reply?`<div class="reply-bar" onclick="scrollToMsg('${esc(m.reply.id)}')"><span class="reply-author">↩ ${esc(m.reply.author)}</span><span class="reply-text">${esc((m.reply.content||'[attachment]').slice(0,80))}</span></div>`:'';
  const text=m.content?`<div class="msg-text">${linkify(esc(m.content))}</div>`:'';
  const attachments=(m.attachments||[]).map(a=>{
    if(a.type==='image')return`<img class="attachment-img" src="${esc(a.url)}" alt="${esc(a.name)}" onclick="openLightbox('${esc(a.url)}')">`;
    return`<a class="attachment-file" href="${esc(a.url)}" target="_blank" rel="noreferrer">📎 ${esc(a.name)}</a>`;
  }).join('');
  const reactions=(m.reactions||[]).length?`<div class="reactions">${m.reactions.map(r=>`<button class="reaction" onclick="addReaction('${m.id}','${esc(r.emoji)}')">${r.emoji} <span class="reaction-count">${r.count}</span></button>`).join('')}<button class="add-reaction" onclick="openEmojiPicker('${m.id}',event)">+</button></div>`:'';
  const actions=`<div class="msg-actions">
    <button class="mac-btn" title="React" onclick="openEmojiPicker('${m.id}',event)">😊</button>
    <button class="mac-btn" title="Reply" onclick="startReply('${m.id}','${esc(m.author)}','${esc((m.content||'').replace(/'/g,"\\'").slice(0,80))}')">↩</button>
    <button class="mac-btn danger" title="Delete" onclick="deleteMessage('${m.id}')">🗑️</button>
  </div>`;
  return`<div class="msg-wrapper ${cont?'cont':'first'}" id="msg-${m.id}">${hoverTime}<div class="msg-group ${cont?'cont':'first'}">${avatarPart}<div class="msg-col">${meta}${reply}${text}${attachments}${reactions}</div></div>${actions}</div>`;
}

function linkify(s){return s.replace(/(https?:\/\/[^\s<>"]+)/g,'<a href="$1" target="_blank" rel="noreferrer">$1</a>');}
function scrollToMsg(id){const el=document.getElementById('msg-'+id);if(el)el.scrollIntoView({behavior:'smooth',block:'center'});}

// SEND
async function sendMessage(){
  if(!activeChannel)return;
  const input=document.getElementById('msg-input');
  const content=input.value.trim();
  if(!content&&!pendingFiles.length)return;
  const btn=document.getElementById('send-btn');btn.disabled=true;
  try{
    const fd=new FormData();
    if(activeChannel.isDM){fd.append('user_id',activeChannel.userId);}
    else{fd.append('channel_id',activeChannel.id);}
    if(content)fd.append('content',content);
    if(replyTarget)fd.append('reply_to',replyTarget.id);
    for(const f of pendingFiles)fd.append('files',f);
    const endpoint=activeChannel.isDM?'/messenger/api/dm-send':'/messenger/api/send';
    const res=await fetch(endpoint,{method:'POST',body:fd});
    const data=await res.json();
    if(data.ok){input.value='';input.style.height='auto';pendingFiles=[];renderAttachPreview();cancelReply();lastMsgIds=new Set();await fetchMessages();}
    else toast(data.error||'Send failed','error');
  }catch(e){toast('Network error','error');}
  btn.disabled=false;updateSendBtn();
}
function handleKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();}}

// REPLY
function startReply(id,author,content){replyTarget={id,author,content};document.getElementById('rp-name').textContent=author;document.getElementById('rp-text').textContent=content||'[attachment]';document.getElementById('reply-preview').classList.add('visible');document.getElementById('msg-input').focus();}
function cancelReply(){replyTarget=null;document.getElementById('reply-preview').classList.remove('visible');}

// FILES
function handleFiles(files){for(const f of files){if(!pendingFiles.find(p=>p.name===f.name&&p.size===f.size))pendingFiles.push(f);}document.getElementById('file-input').value='';renderAttachPreview();updateSendBtn();}
function renderAttachPreview(){const c=document.getElementById('attach-preview');if(!pendingFiles.length){c.innerHTML='';return;}c.innerHTML=pendingFiles.map((f,i)=>`<div class="attach-chip">${f.type.startsWith('image/')?'🖼️':'📎'} ${esc(f.name)}<button class="attach-remove" onclick="removeFile(${i})">✕</button></div>`).join('');}
function removeFile(i){pendingFiles.splice(i,1);renderAttachPreview();updateSendBtn();}

// DELETE
async function deleteMessage(msgId){
  if(!activeChannel)return;
  if(!confirm('Delete this message? This cannot be undone.'))return;
  try{
    const body=activeChannel.isDM?{user_id:activeChannel.userId,message_id:msgId}:{channel_id:activeChannel.id,message_id:msgId};
    const res=await fetch('/messenger/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await res.json();
    if(data.ok){const el=document.getElementById('msg-'+msgId);if(el)el.remove();lastMsgIds=new Set();await fetchMessages();}
    else toast(data.error||'Delete failed','error');
  }catch(e){toast('Network error','error');}
}

// REACTIONS
async function addReaction(msgId,emoji){
  if(!activeChannel||activeChannel.isDM)return;
  try{
    const res=await fetch('/messenger/api/react',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel_id:activeChannel.id,message_id:msgId,emoji})});
    const data=await res.json();
    if(!data.ok)toast(data.error||'React failed','error');
    else{lastMsgIds=new Set();await fetchMessages();}
  }catch(e){toast('Network error','error');}
  closeEmojiPicker();
}

// EMOJI PICKER
function openEmojiPicker(msgId,event){event.stopPropagation();emojiTarget=msgId;const picker=document.getElementById('emoji-picker');document.getElementById('emoji-search').value='';renderEmojiGrid(EMOJI_LIST);picker.classList.add('open');const rect=event.target.getBoundingClientRect();picker.style.left=Math.min(rect.left,window.innerWidth-290)+'px';requestAnimationFrame(()=>{const h=picker.offsetHeight;picker.style.top=Math.max(8,rect.top-h-8)+'px';});}
function closeEmojiPicker(){document.getElementById('emoji-picker').classList.remove('open');emojiTarget=null;}
function renderEmojiGrid(list){document.getElementById('emoji-grid').innerHTML=list.map(e=>`<button class="emoji-btn" onclick="pickEmoji('${e}')">${e}</button>`).join('');}
function filterEmoji(q){renderEmojiGrid(q?EMOJI_LIST.filter(e=>e.includes(q)):EMOJI_LIST);}
function pickEmoji(emoji){if(emojiTarget){addReaction(emojiTarget,emoji);}else{const input=document.getElementById('msg-input');const pos=input.selectionStart;input.value=input.value.slice(0,pos)+emoji+input.value.slice(pos);input.selectionStart=input.selectionEnd=pos+emoji.length;input.focus();autoGrow(input);closeEmojiPicker();}}
document.addEventListener('click',e=>{const p=document.getElementById('emoji-picker');if(p.classList.contains('open')&&!p.contains(e.target))closeEmojiPicker();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeLightbox();closeEmojiPicker();}});

// MEMBERS PANEL
function toggleMembers(){membersOpen=!membersOpen;document.getElementById('members-panel').classList.toggle('hidden',!membersOpen);}
function renderMembersPanel(){const el=document.getElementById('members-list');if(!allMembers.length){el.innerHTML='<div style="padding:8px;color:var(--muted);font-size:0.85rem">No members</div>';return;}el.innerHTML=allMembers.map(m=>`<div class="member-row"><div class="member-avatar" style="background:${avatarColor(m.id)}">${initials(m.display_name||m.username)}</div><span class="member-name">${esc(m.display_name||m.username)}</span></div>`).join('');}

// DM MODAL
function openDMModal(){document.getElementById('new-dm-modal').classList.add('open');document.getElementById('dm-search').value='';renderDMResults(allMembers.slice(0,25));setTimeout(()=>document.getElementById('dm-search').focus(),50);}
function closeDMModal(){document.getElementById('new-dm-modal').classList.remove('open');}
function filterDMSearch(q){q=q.toLowerCase();const f=q?allMembers.filter(m=>(m.display_name||'').toLowerCase().includes(q)||m.username.toLowerCase().includes(q)):allMembers.slice(0,25);renderDMResults(f);}
function renderDMResults(members){const el=document.getElementById('dm-results');if(!members.length){el.innerHTML='<div style="padding:8px;color:var(--muted);font-size:0.85rem">No results</div>';return;}el.innerHTML=members.map(m=>{const c=avatarColor(m.id);return`<div class="modal-member" onclick="startDM('${m.id}','${esc(m.display_name||m.username)}')"><div style="width:36px;height:36px;border-radius:50%;background:${c};display:flex;align-items:center;justify-content:center;font-size:0.78rem;font-weight:700;color:white;flex-shrink:0">${initials(m.display_name||m.username)}</div><div><div style="font-weight:600;font-size:0.92rem">${esc(m.display_name||m.username)}</div><div style="font-size:0.78rem;color:var(--muted)">@${esc(m.username)}</div></div></div>`;}).join('');}
function startDM(userId,username){closeDMModal();showDMView();selectDM(userId,username);}

// LIGHTBOX
function openLightbox(url){document.getElementById('lightbox-img').src=url;document.getElementById('lightbox').classList.add('open');}
function closeLightbox(){document.getElementById('lightbox').classList.remove('open');}

init();
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

@messenger_app.route("/")
async def index():
    return await render_template_string(PAGE)


@messenger_app.route("/api/guild")
async def guild():
    import discord as _discord
    bot = state.bot
    if not bot or not bot.guilds:
        return jsonify({"channels": [], "categories": [], "members": [],
                        "guild_name": "", "guild_icon": None, "bot_name": "Floppy"})
    g = bot.guilds[0]

    # Channel type mapping
    TYPE_MAP = {
        _discord.ChannelType.text: "text",
        _discord.ChannelType.voice: "voice",
        _discord.ChannelType.news: "announcement",
        _discord.ChannelType.stage_voice: "stage",
        _discord.ChannelType.forum: "forum",
    }

    # All non-category channels sorted by position
    all_chans = sorted(
        [c for c in g.channels if not isinstance(c, _discord.CategoryChannel)],
        key=lambda c: (c.position if hasattr(c, "position") else 0)
    )

    channels = []
    for c in all_chans:
        ch_type = TYPE_MAP.get(c.type, str(c.type).replace("ChannelType.", ""))
        topic = getattr(c, "topic", None) or ""
        channels.append({
            "id": str(c.id),
            "name": c.name,
            "type": ch_type,
            "category_id": str(c.category_id) if getattr(c, "category_id", None) else None,
            "position": getattr(c, "position", 0),
            "topic": topic,
        })

    categories = [
        {"id": str(c.id), "name": c.name, "position": c.position}
        for c in sorted(g.categories, key=lambda c: c.position)
    ]

    guild_icon = str(g.icon.url) if g.icon else None
    bot_name = bot.user.display_name if bot.user else "Floppy"

    return jsonify({
        "channels": channels,
        "categories": categories,
        "members": [],
        "guild_name": g.name,
        "guild_icon": guild_icon,
        "bot_name": bot_name,
    })


@messenger_app.route("/api/members")
async def get_members():
    bot = state.bot
    if not bot or not bot.guilds:
        return jsonify({"members": []})
    g = bot.guilds[0]
    members = [
        {
            "id": str(m.id),
            "username": m.name,
            "display_name": m.display_name,
        }
        async for m in g.fetch_members(limit=1000)
        if not m.bot
    ]
    members.sort(key=lambda m: m["display_name"].lower())
    return jsonify({"members": members})


@messenger_app.route("/api/dms")
async def get_dms():
    bot = state.bot
    if not bot:
        return jsonify({"dms": []})
    dms = []
    for channel in bot.private_channels:
        if hasattr(channel, "recipient") and channel.recipient:
            u = channel.recipient
            dms.append({
                "user_id": str(u.id),
                "username": u.name,
                "display_name": u.display_name,
            })
    return jsonify({"dms": dms})


@messenger_app.route("/api/dm-messages/<int:user_id>")
async def get_dm_messages(user_id):
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503
    try:
        g = bot.guilds[0]
        member = g.get_member(user_id) or await g.fetch_member(user_id)
        dm = await member.create_dm()
        messages = []
        async for msg in dm.history(limit=60):
            if not msg.author:
                continue
            attachments = []
            for a in msg.attachments:
                is_image = a.content_type and a.content_type.startswith("image/")
                attachments.append({"name": a.filename, "url": a.url, "type": "image" if is_image else "file"})
            messages.append({
                "id": str(msg.id),
                "author": msg.author.display_name,
                "author_id": str(msg.author.id),
                "bot": msg.author.bot,
                "content": msg.content or "",
                "time": msg.created_at.strftime("%H:%M"),
                "timestamp": msg.created_at.timestamp(),
                "reply": None,
                "attachments": attachments,
                "reactions": [],
            })
        messages.reverse()
        return jsonify({"ok": True, "messages": messages})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@messenger_app.route("/api/dm-send", methods=["POST"])
async def dm_send():
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503

    form = await request.form
    files = await request.files
    user_id = form.get("user_id")
    content = form.get("content", "").strip()

    if not user_id:
        return jsonify({"ok": False, "error": "Missing user_id"}), 400
    if not content and not files.getlist("files"):
        return jsonify({"ok": False, "error": "Nothing to send"}), 400

    import discord as _discord
    try:
        g = bot.guilds[0]
        try:
            member = g.get_member(int(user_id)) or await g.fetch_member(int(user_id))
            dm = await member.create_dm()
        except (_discord.NotFound, _discord.HTTPException):
            # Fallback: fetch_member failed (e.g. Members Intent off), try fetch_user
            user = await bot.fetch_user(int(user_id))
            dm = await user.create_dm()
        discord_files = []
        for f in files.getlist("files"):
            discord_files.append(_discord.File(io.BytesIO(f.read()), filename=f.filename))
        await dm.send(
            content or None,
            files=discord_files if discord_files else _discord.utils.MISSING,
        )
        state.add_log(f"Messenger DM sent to user {user_id}")
        return jsonify({"ok": True})
    except _discord.Forbidden as e:
        return jsonify({"ok": False, "error": f"Forbidden — user may have DMs disabled ({e.text})"}), 403
    except _discord.NotFound:
        return jsonify({"ok": False, "error": "User not found"}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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
            if not msg.author:
                continue
            reply = None
            if msg.reference and msg.reference.resolved:
                ref = msg.reference.resolved
                if hasattr(ref, "content"):
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
                "author": msg.author.display_name,
                "author_id": str(msg.author.id),
                "bot": msg.author.bot,
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
        import traceback
        traceback.print_exc()
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


@messenger_app.route("/api/delete", methods=["POST"])
async def delete_message():
    bot = state.bot
    if not bot:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503

    import discord as _discord

    payload = await request.get_json()
    message_id = payload.get("message_id")
    channel_id = payload.get("channel_id")   # server channel
    user_id    = payload.get("user_id")       # DM recipient

    if not message_id:
        return jsonify({"ok": False, "error": "Missing message_id"}), 400

    try:
        if user_id:
            # ── DM delete — bot can only delete its own messages ──
            g = bot.guilds[0]
            try:
                member = g.get_member(int(user_id)) or await g.fetch_member(int(user_id))
                dm = await member.create_dm()
            except (_discord.NotFound, _discord.HTTPException):
                user = await bot.fetch_user(int(user_id))
                dm = await user.create_dm()

            msg = await dm.fetch_message(int(message_id))
            if msg.author.id != bot.user.id:
                return jsonify({"ok": False, "error": "Can only delete the bot's own DM messages"}), 403
            await msg.delete()
            state.add_log(f"Messenger deleted DM message {message_id}")
            return jsonify({"ok": True})

        elif channel_id:
            # ── Server channel delete — needs Manage Messages ──
            channel = bot.get_channel(int(channel_id))
            if not channel:
                return jsonify({"ok": False, "error": "Channel not found"}), 404

            me = channel.guild.me
            perms = channel.permissions_for(me)
            if not perms.manage_messages and not perms.administrator:
                return jsonify({"ok": False, "error": "Bot lacks Manage Messages permission in this channel"}), 403

            msg = await channel.fetch_message(int(message_id))
            await msg.delete()
            state.add_log(f"Messenger deleted message {message_id} in #{channel.name}")
            return jsonify({"ok": True})

        else:
            return jsonify({"ok": False, "error": "Missing channel_id or user_id"}), 400

    except _discord.NotFound:
        return jsonify({"ok": False, "error": "Message not found (already deleted?)"}), 404
    except _discord.Forbidden as e:
        return jsonify({"ok": False, "error": f"Forbidden: {e.text}"}), 403
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
