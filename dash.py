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
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #1e1f22; color: #dbdee1; min-height: 100vh; padding: 2rem; }
    h1 { font-size: 1.8rem; margin-bottom: 0.25rem; }
    .status { display: inline-flex; align-items: center; gap: 0.5rem; font-size: 0.95rem; margin-bottom: 2rem; }
    .dot { width: 10px; height: 10px; border-radius: 50%; background: #f04747; }
    .dot.online { background: #43b581; }
    .card { background: #2b2d31; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { font-size: 1rem; text-transform: uppercase; letter-spacing: 0.05em; color: #949ba4; margin-bottom: 1rem; }
    .field { margin-bottom: 1rem; }
    label { display: block; font-size: 0.85rem; color: #949ba4; margin-bottom: 0.4rem; }
    input, select { width: 100%; padding: 0.6rem 0.8rem; background: #1e1f22; border: 1px solid #3f4248; border-radius: 8px; color: #dbdee1; font-size: 0.95rem; }
    input:focus, select:focus { outline: none; border-color: #5865f2; }
    .hint { font-size: 0.78rem; color: #6d757d; margin-top: 0.3rem; }
    button { background: #5865f2; color: white; border: none; padding: 0.65rem 1.5rem; border-radius: 8px; font-size: 0.95rem; cursor: pointer; margin-top: 0.5rem; }
    button:hover { background: #4752c4; }
    .toast { position: fixed; bottom: 2rem; right: 2rem; background: #43b581; color: white; padding: 0.75rem 1.25rem; border-radius: 8px; display: none; font-size: 0.9rem; }
  </style>
</head>
<body>
  <h1>🐟 Floppy</h1>
  <div class="status">
    <div class="dot" id="dot"></div>
    <span id="status-text">Checking...</span>
  </div>

  <div class="card">
    <h2>Welcome & Goodbye</h2>
    <div class="field">
      <label>Welcome Channel ID</label>
      <input id="welcome_channel" placeholder="e.g. 123456789012345678">
    </div>
    <div class="field">
      <label>Welcome Message</label>
      <input id="welcome_message" placeholder="Welcome {mention} to {server}!">
      <div class="hint">Use {mention}, {name}, {server}</div>
    </div>
    <div class="field">
      <label>Goodbye Channel ID</label>
      <input id="goodbye_channel" placeholder="e.g. 123456789012345678">
    </div>
    <div class="field">
      <label>Goodbye Message</label>
      <input id="goodbye_message" placeholder="Goodbye {name}, we'll miss you!">
      <div class="hint">Use {mention}, {name}, {server}</div>
    </div>
  </div>

  <div class="card">
    <h2>Join Role</h2>
    <div class="field">
      <label>Role ID to assign on join</label>
      <input id="join_role" placeholder="e.g. 123456789012345678">
    </div>
  </div>

  <div class="card">
    <h2>Audit Log</h2>
    <div class="field">
      <label>Audit Log Channel ID</label>
      <input id="audit_log_channel" placeholder="e.g. 123456789012345678">
    </div>
  </div>

  <button onclick="save()">Save Changes</button>
  <div class="toast" id="toast">✅ Saved!</div>

  <script>
    async function load() {
      const res = await fetch('/api/config');
      const cfg = await res.json();
      for (const key of Object.keys(cfg)) {
        const el = document.getElementById(key);
        if (el) el.value = cfg[key] ?? '';
      }
    }

    async function checkStatus() {
      const res = await fetch('/api/status');
      const data = await res.json();
      document.getElementById('dot').className = 'dot' + (data.online ? ' online' : '');
      document.getElementById('status-text').textContent = data.online ? 'Floppy is online' : 'Floppy is offline';
    }

    async function save() {
      const keys = ['welcome_channel','welcome_message','goodbye_channel','goodbye_message','join_role','audit_log_channel'];
      const body = {};
      for (const k of keys) {
        const el = document.getElementById(k);
        body[k] = el.value || null;
      }
      await fetch('/api/config', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
      const toast = document.getElementById('toast');
      toast.style.display = 'block';
      setTimeout(() => toast.style.display = 'none', 2500);
    }

    load();
    checkStatus();
    setInterval(checkStatus, 10000);
  </script>
</body>
</html>
"""

@app.route("/")
async def index():
    return render_template_string(PAGE)

@app.route("/api/status")
async def status():
    return jsonify({"online": state.bot_ready})

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
