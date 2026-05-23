from quart import Quart, jsonify, request, render_template_string
import state
import config

app = Quart(__name__)

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Floppy Dashboard</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #1e1f22; --surface: #2b2d31; --surface2: #313338;
      --border: #3f4248; --text: #dbdee1; --muted: #949ba4;
      --accent: #5865f2; --accent-hover: #4752c4;
      --green: #43b581; --red: #f04747; --yellow: #faa61a;
    }
    body { font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
    .sidebar { position: fixed; top: 0; left: 0; width: 220px; height: 100vh; background: var(--surface); border-right: 1px solid var(--border); padding: 1.5rem 1rem; display: flex; flex-direction: column; gap: 0.4rem; }
    .sidebar h1 { font-size: 1.2rem; font-weight: 700; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
    .nav-item { padding: 0.6rem 0.75rem; border-radius: 8px; cursor: pointer; font-size: 0.9rem; color: var(--muted); transition: all 0.15s; display: flex; align-items: center; gap: 0.6rem; }
    .nav-item:hover { background: var(--surface2); color: var(--text); }
    .nav-item.active { background: var(--accent); color: white; }
    .status-pill { margin-top: auto; display: flex; align-items: center; gap: 0.5rem; font-size: 0.82rem; color: var(--muted); padding: 0.5rem 0.75rem; background: var(--surface2); border-radius: 8px; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--red); flex-shrink: 0; }
    .dot.online { background: var(--green); }
    .main { margin-left: 220px; padding: 2rem; max-width: 820px; }
    .page { display: none; }
    .page.active { display: block; }
    .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem; }
    .page-header-left h2 { font-size: 1.4rem; font-weight: 700; margin-bottom: 0.25rem; }
    .page-header-left .subtitle { color: var(--muted); font-size: 0.9rem; }
    .card { background: var(--surface); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.25rem; border: 1px solid var(--border); }
    .card-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 1rem; }
    .field { margin-bottom: 1rem; }
    .field:last-child { margin-bottom: 0; }
    label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 0.4rem; font-weight: 500; }
    input, select, textarea { width: 100%; padding: 0.6rem 0.85rem; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 0.92rem; font-family: inherit; transition: border-color 0.15s; }
    input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); }
    select option { background: var(--surface2); }
    .hint { font-size: 0.78rem; color: var(--muted); margin-top: 0.35rem; }
    .preview { font-size: 0.85rem; background: var(--surface2); border-radius: 8px; padding: 0.75rem 1rem; margin-top: 0.5rem; border-left: 3px solid var(--accent); color: var(--text); min-height: 2rem; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    .btn { background: var(--accent); color: white; border: none; padding: 0.65rem 1.5rem; border-radius: 8px; font-size: 0.92rem; cursor: pointer; font-weight: 600; transition: background 0.15s; white-space: nowrap; }
    .btn:hover { background: var(--accent-hover); }
    .btn.secondary { background: var(--surface2); color: var(--text); border: 1px solid var(--border); }
    .btn.secondary:hover { background: var(--border); }
    .btn.danger { background: var(--red); }
    .btn.danger:hover { background: #c0392b; }
    .btn-row { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1rem; align-items: center; flex-wrap: wrap; }
    .unsaved-badge { font-size: 0.8rem; color: var(--yellow); font-weight: 600; display: none; align-items: center; gap: 0.4rem; margin-right: auto; }
    .unsaved-badge.visible { display: flex; }
    .toast { position: fixed; bottom: 2rem; right: 2rem; color: white; padding: 0.75rem 1.25rem; border-radius: 8px; display: none; font-size: 0.9rem; font-weight: 600; box-shadow: 0 4px 20px rgba(0,0,0,0.3); z-index: 999; background: var(--green); }
    .toast.error { background: var(--red); }
    .tag { display: inline-block; background: var(--accent); color: white; border-radius: 4px; padding: 0.1rem 0.4rem; font-size: 0.78rem; cursor: pointer; margin: 0.15rem; font-family: monospace; }
    .tag:hover { background: var(--accent-hover); }
    .multi-select { display: flex; flex-direction: column; gap: 0.4rem; max-height: 180px; overflow-y: auto; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 0.5rem; }
    .multi-select label { display: flex; align-items: center; gap: 0.5rem; font-size: 0.88rem; color: var(--text); cursor: pointer; padding: 0.3rem 0.4rem; border-radius: 6px; font-weight: normal; }
    .multi-select label:hover { background: var(--surface2); }
    .multi-select input[type=checkbox] { width: auto; accent-color: var(--accent); }
    .refresh-btn { font-size: 0.78rem; background: none; border: 1px solid var(--border); color: var(--muted); padding: 0.3rem 0.7rem; border-radius: 6px; cursor: pointer; display: flex; align-items: center; gap: 0.35rem; }
    .refresh-btn:hover { color: var(--text); border-color: var(--muted); }
    .refresh-btn.spinning svg { animation: spin 1s linear infinite; }
    .log-line { padding: 0.2rem 0.5rem; border-radius: 4px; color: var(--muted); }
    .log-line:hover { background: var(--surface2); color: var(--text); }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>

<div class="sidebar">
  <h1>🐟 Floppy</h1>
  <div class="nav-item active" onclick="showPage('welcome', this)">👋 Welcome & Goodbye</div>
  <div class="nav-item" onclick="showPage('roles', this)">🔖 Join Role</div>
  <div class="nav-item" onclick="showPage('tickets', this)">🎫 Tickets</div>
  <div class="nav-item" onclick="showPage('audit', this)">📋 Audit Log</div>
  <div class="nav-item" onclick="showPage('logs', this)">🖥️ Logs</div>
  <div class="status-pill">
    <div class="dot" id="dot"></div>
    <span id="status-text">Checking...</span>
  </div>
</div>

<div class="main">

  <!-- WELCOME PAGE -->
  <div class="page active" id="page-welcome">
    <div class="page-header">
      <div class="page-header-left">
        <h2>👋 Welcome & Goodbye</h2>
        <p class="subtitle">Configure join and leave messages for your server.</p>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Welcome Message</div>
      <div class="field">
        <label>Channel</label>
        <select id="welcome_channel" onchange="markDirty()"><option value="">— none —</option></select>
      </div>
      <div class="field">
        <label>Message</label>
        <input id="welcome_message" placeholder="Welcome {mention} to {server}! 🎉" oninput="updatePreview('welcome'); markDirty()">
        <div class="hint">
          Click to insert:
          <span class="tag" onclick="insert('welcome_message','{mention}')"><code>{mention}</code></span>
          <span class="tag" onclick="insert('welcome_message','{name}')"><code>{name}</code></span>
          <span class="tag" onclick="insert('welcome_message','{server}')"><code>{server}</code></span>
        </div>
        <div class="preview" id="preview-welcome"></div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Goodbye Message</div>
      <div class="field">
        <label>Channel</label>
        <select id="goodbye_channel" onchange="markDirty()"><option value="">— none —</option></select>
      </div>
      <div class="field">
        <label>Message</label>
        <input id="goodbye_message" placeholder="Goodbye {mention}, we'll miss you! 👋" oninput="updatePreview('goodbye'); markDirty()">
        <div class="hint">
          Click to insert:
          <span class="tag" onclick="insert('goodbye_message','{mention}')"><code>{mention}</code></span>
          <span class="tag" onclick="insert('goodbye_message','{name}')"><code>{name}</code></span>
          <span class="tag" onclick="insert('goodbye_message','{server}')"><code>{server}</code></span>
        </div>
        <div class="preview" id="preview-goodbye"></div>
      </div>
    </div>
    <div class="btn-row">
      <span class="unsaved-badge" id="unsaved-welcome">⚠️ Unsaved changes</span>
      <button class="btn" onclick="save('welcome')">Save Changes</button>
    </div>
  </div>

  <!-- ROLES PAGE -->
  <div class="page" id="page-roles">
    <div class="page-header">
      <div class="page-header-left">
        <h2>🔖 Join Role</h2>
        <p class="subtitle">Automatically assign a role when someone joins.</p>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Auto Role</div>
      <div class="field">
        <label>Role to assign on join</label>
        <select id="join_role" onchange="markDirty()"><option value="">— none —</option></select>
      </div>
    </div>
    <div class="btn-row">
      <span class="unsaved-badge" id="unsaved-roles">⚠️ Unsaved changes</span>
      <button class="btn" onclick="save('roles')">Save Changes</button>
    </div>
  </div>

  <!-- TICKETS PAGE -->
  <div class="page" id="page-tickets">
    <div class="page-header">
      <div class="page-header-left">
        <h2>🎫 Tickets</h2>
        <p class="subtitle">Configure the ticket system.</p>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Panel</div>
      <div class="row">
        <div class="field">
          <label>Panel Channel</label>
          <select id="ticket_channel" onchange="markDirty()"><option value="">— none —</option></select>
          <div class="hint">Where the "Open a Ticket" button is posted.</div>
        </div>
        <div class="field">
          <label>Ticket Category</label>
          <select id="ticket_category" onchange="markDirty()"><option value="">— none —</option></select>
          <div class="hint">New ticket channels go under this category.</div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Staff Roles</div>
      <div class="field">
        <label>Roles that can manage tickets</label>
        <div class="multi-select" id="ticket_staff_roles"></div>
        <div class="hint">Selected roles can see, claim, and close tickets.</div>
      </div>
    </div>
    <div class="btn-row">
      <span class="unsaved-badge" id="unsaved-tickets">⚠️ Unsaved changes</span>
      <button class="btn secondary" onclick="repostPanel()">🔄 Update Panel</button>
      <button class="btn" onclick="save('tickets')">Save Changes</button>
    </div>
  </div>

  <!-- AUDIT PAGE -->
  <div class="page" id="page-audit">
    <div class="page-header">
      <div class="page-header-left">
        <h2>📋 Audit Log</h2>
        <p class="subtitle">Log all server activity to a channel.</p>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Log Channel</div>
      <div class="field">
        <label>Send logs to</label>
        <select id="audit_log_channel" onchange="markDirty()"><option value="">— none —</option></select>
      </div>
      <div class="hint" style="margin-top:0.5rem;">Logs: message edits/deletes, joins/leaves, role changes, nickname changes, bans, channel changes, voice activity, invites.</div>
    </div>
    <div class="btn-row">
      <span class="unsaved-badge" id="unsaved-audit">⚠️ Unsaved changes</span>
      <button class="btn" onclick="save('audit')">Save Changes</button>
    </div>
  </div>

  <!-- LOGS PAGE -->
  <div class="page" id="page-logs">
    <div class="page-header">
      <div class="page-header-left">
        <h2>🖥️ Bot Logs</h2>
        <p class="subtitle">Last 25 bot events. Auto-refreshes every 5 seconds.</p>
      </div>
    </div>
    <div class="card" style="padding:0;overflow:hidden;">
      <div id="log-list" style="font-family:monospace;font-size:0.82rem;line-height:1.7;padding:1rem;display:flex;flex-direction:column;gap:0.15rem;min-height:200px;"></div>
    </div>
  </div>

</div>

<div class="toast" id="toast"></div>

<script>
  let guildData = { channels: [], roles: [], categories: [] };
  let cfg = {};
  let currentPage = 'welcome';
  let dirty = false;

  function showPage(name, el) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
    el.classList.add('active');
    currentPage = name;
    dirty = false;
  }

  function markDirty() {
    dirty = true;
    const badge = document.getElementById('unsaved-' + currentPage);
    if (badge) badge.classList.add('visible');
  }

  function clearDirty() {
    dirty = false;
    document.querySelectorAll('.unsaved-badge').forEach(b => b.classList.remove('visible'));
  }

  function toast(msg, error = false) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast' + (error ? ' error' : '');
    el.style.display = 'block';
    setTimeout(() => el.style.display = 'none', 2500);
  }

  function populateSelect(id, options, savedValue) {
    const el = document.getElementById(id);
    el.innerHTML = '<option value="">— none —</option>';
    for (const o of options) {
      const opt = document.createElement('option');
      opt.value = o.id;
      opt.textContent = o.name;
      if (String(savedValue) === String(o.id)) opt.selected = true;
      el.appendChild(opt);
    }
  }

  function populateStaffRoles(roles, savedValues) {
    const container = document.getElementById('ticket_staff_roles');
    container.innerHTML = '';
    const saved = (savedValues || []).map(String);
    for (const role of roles) {
      const label = document.createElement('label');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = role.id;
      cb.checked = saved.includes(String(role.id));
      cb.onchange = markDirty;
      label.appendChild(cb);
      label.appendChild(document.createTextNode(role.name));
      container.appendChild(label);
    }
  }

  function insert(fieldId, text) {
    const el = document.getElementById(fieldId);
    const start = el.selectionStart, end = el.selectionEnd;
    el.value = el.value.substring(0, start) + text + el.value.substring(end);
    el.selectionStart = el.selectionEnd = start + text.length;
    el.focus();
    updatePreview(fieldId.includes('welcome') ? 'welcome' : 'goodbye');
    markDirty();
  }

  function updatePreview(type) {
    const msg = document.getElementById(type + '_message').value;
    document.getElementById('preview-' + type).textContent = msg
      .replace(/{mention}/g, '@YourName')
      .replace(/{name}/g, 'YourName')
      .replace(/{server}/g, 'Social Space');
  }

  async function fetchGuild() {
    const res = await fetch('/api/guild');
    guildData = await res.json();
    populateSelect('welcome_channel', guildData.channels, cfg.welcome_channel);
    populateSelect('goodbye_channel', guildData.channels, cfg.goodbye_channel);
    populateSelect('audit_log_channel', guildData.channels, cfg.audit_log_channel);
    populateSelect('ticket_channel', guildData.channels, cfg.ticket_channel);
    populateSelect('ticket_category', guildData.categories, cfg.ticket_category);
    populateSelect('join_role', guildData.roles, cfg.join_role);
    populateStaffRoles(guildData.roles, cfg.ticket_staff_roles);
  }

  async function load() {
    const cfgRes = await fetch('/api/config');
    cfg = await cfgRes.json();
    document.getElementById('welcome_message').value = cfg.welcome_message ?? '';
    document.getElementById('goodbye_message').value = cfg.goodbye_message ?? '';
    updatePreview('welcome');
    updatePreview('goodbye');
    await fetchGuild();
  }

  async function checkStatus() {
    const res = await fetch('/api/status');
    const data = await res.json();
    const wasOnline = document.getElementById('dot').classList.contains('online');
    document.getElementById('dot').className = 'dot' + (data.online ? ' online' : '');
    document.getElementById('status-text').textContent = data.online ? 'Online' : 'Offline';
    // Refetch guild data whenever bot is online and dropdowns are empty
    const hasData = document.querySelector('#welcome_channel option:nth-child(2)');
    if (data.online && (!wasOnline || !hasData)) {
      await fetchGuild();
    }
  }

  async function save(page) {
    const staffRoles = [...document.querySelectorAll('#ticket_staff_roles input:checked')].map(cb => cb.value);
    const body = {
      welcome_channel: document.getElementById('welcome_channel').value || null,
      welcome_message: document.getElementById('welcome_message').value || null,
      goodbye_channel: document.getElementById('goodbye_channel').value || null,
      goodbye_message: document.getElementById('goodbye_message').value || null,
      join_role: document.getElementById('join_role').value || null,
      audit_log_channel: document.getElementById('audit_log_channel').value || null,
      ticket_channel: document.getElementById('ticket_channel').value || null,
      ticket_category: document.getElementById('ticket_category').value || null,
      ticket_staff_roles: staffRoles,
    };
    const res = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (res.ok) {
      cfg = { ...cfg, ...body };
      clearDirty();
      toast('✅ Saved!');
    } else {
      toast('❌ Save failed', true);
    }
  }

  async function repostPanel() {
    const res = await fetch('/api/repost-panel', { method: 'POST' });
    if (res.ok) {
      toast('✅ Panel updated!');
    } else {
      toast('❌ Failed — is the bot online?', true);
    }
  }

  async function fetchLogs() {
    const res = await fetch('/api/logs');
    const data = await res.json();
    const list = document.getElementById('log-list');
    if (!list) return;
    list.innerHTML = data.logs.length
      ? data.logs.map(l => `<div class="log-line">${l}</div>`).join('')
      : '<div class="log-line" style="color:var(--muted)">No logs yet...</div>';
  }

  load();
  checkStatus();
  setInterval(fetchLogs, 5000);
  setInterval(checkStatus, 10000);
  // Auto-refresh guild data every 60s
  setInterval(fetchGuild, 60000);
</script>
</body>
</html>
"""

@app.route("/")
async def index():
    return await render_template_string(PAGE)

@app.route("/api/status")
async def status():
    return jsonify({"online": state.bot_ready})

@app.route("/api/guild")
async def guild():
    bot = state.bot
    if not bot or not state.bot_ready or not bot.guilds:
        return jsonify({"channels": [], "roles": [], "categories": []})
    g = bot.guilds[0]
    channels = [{"id": str(c.id), "name": f"# {c.name}"} for c in sorted(g.text_channels, key=lambda c: c.position)]
    roles = [{"id": str(r.id), "name": r.name} for r in sorted(g.roles, key=lambda r: -r.position) if r.name != "@everyone"]
    categories = [{"id": str(c.id), "name": c.name} for c in sorted(g.categories, key=lambda c: c.position)]
    return jsonify({"channels": channels, "roles": roles, "categories": categories})

@app.route("/api/config", methods=["GET"])
async def get_config():
    return jsonify(config.load())

@app.route("/api/config", methods=["POST"])
async def set_config():
    data = await request.get_json()
    cfg = config.load()
    cfg.update(data)
    config.save(cfg)
    return jsonify({"ok": True})

@app.route("/api/logs")
async def get_logs():
    return jsonify({"logs": list(state.logs)})

@app.route("/api/repost-panel", methods=["POST"])
async def repost_panel():
    from tickets import post_ticket_panel
    bot = state.bot
    if not bot or not state.bot_ready:
        return jsonify({"ok": False, "error": "Bot not ready"}), 503
    await post_ticket_panel(bot)
    return jsonify({"ok": True})
