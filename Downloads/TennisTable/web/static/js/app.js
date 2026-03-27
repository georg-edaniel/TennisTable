/**
 * Alpine.js global store + WebSocket client with auto-reconnect
 * Loaded in base.html before Alpine.start()
 */

// ── WebSocket client ─────────────────────────────────────────────────────────
class TennisWS {
  constructor(token) {
    this.token = token || '';
    this.ws = null;
    this.reconnectDelay = 1500;
    this.maxDelay = 30000;
    this.handlers = [];
    this.connected = false;
    this._connect();
  }

  _connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${location.host}/ws/live?token=${encodeURIComponent(this.token)}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.connected = true;
      this.reconnectDelay = 1500;
      console.log('[WS] connected');
      Alpine.store('tennis').bleConnected = true;
    };

    this.ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        this.handlers.forEach(fn => fn(msg));
      } catch(e) {}
    };

    this.ws.onclose = () => {
      this.connected = false;
      Alpine.store('tennis').bleConnected = false;
      console.log(`[WS] disconnected — retry in ${this.reconnectDelay}ms`);
      setTimeout(() => this._connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay);
    };

    this.ws.onerror = () => {
      this.ws.close();
    };
  }

  on(fn) { this.handlers.push(fn); }

  joinSession(sessionId) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'join_session', session_id: sessionId }));
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}

// ── Alpine store ─────────────────────────────────────────────────────────────
document.addEventListener('alpine:init', () => {
  Alpine.store('tennis', {
    // Connection state
    bleConnected: false,

    // Live MQTT data per device
    devices: {},   // device_name → latest payload

    // Active session state
    session: null,  // { id, mode, ... }
    score: { p1: 0, p2: 0, p1_sets: 0, p2_sets: 0, sets: [] },

    // Accumulated live strokes for current view
    liveStrokes: {
      bh_drive: 0, bh_smash: 0,
      fh_drive: 0, fh_loop: 0, fh_smash: 0,
      total: 0,
    },

    // Strokes per minute (rolling 60s window)
    _strokeTimes: [],
    strokesPerMin: 0,

    // Timer
    _timerStart: null,
    _timerInterval: null,
    elapsedSeconds: 0,

    // Notifications
    notifications: [],

    // ── Methods ──────────────────────────────────────────────────────────────

    initWS(token) {
      window._ws = new TennisWS(token);
      window._ws.on((msg) => this._handleMessage(msg));
    },

    _handleMessage(msg) {
      if (msg.type === 'stroke') {
        const d = msg.data;
        const dev = d.device || 'unknown';

        // Update device map
        this.devices[dev] = d;

        // Update live strokes (use payload cumulative counts)
        const ls = this.liveStrokes;
        ls.bh_drive = (ls.bh_drive || 0) + 1;  // just count events
        ls.total++;

        // If payload has cumulative data, use it
        if (d.total !== undefined) {
          Object.assign(this.liveStrokes, {
            bh_drive: d.bh_drive,
            bh_smash: d.bh_smash,
            fh_drive: d.fh_drive,
            fh_loop:  d.fh_loop,
            fh_smash: d.fh_smash,
            total:    d.total,
          });
        }

        // SPM rolling window
        const now = Date.now();
        this._strokeTimes.push(now);
        this._strokeTimes = this._strokeTimes.filter(t => now - t < 60000);
        this.strokesPerMin = this._strokeTimes.length;

        // Toast notification for last stroke
        if (d.last_stroke?.name) {
          this._notify(`🏓 ${d.last_stroke.name}`, 'stroke');
        }
      }

      if (msg.type === 'status') {
        const d = msg.data;
        this.bleConnected = d.status === 'online';
      }
    },

    startTimer() {
      this._timerStart = Date.now();
      this._timerInterval = setInterval(() => {
        this.elapsedSeconds = Math.floor((Date.now() - this._timerStart) / 1000);
      }, 1000);
    },

    stopTimer() {
      if (this._timerInterval) {
        clearInterval(this._timerInterval);
        this._timerInterval = null;
      }
    },

    formatTime(seconds) {
      const m = Math.floor(seconds / 60).toString().padStart(2, '0');
      const s = (seconds % 60).toString().padStart(2, '0');
      return `${m}:${s}`;
    },

    resetLive() {
      this.liveStrokes = { bh_drive:0, bh_smash:0, fh_drive:0, fh_loop:0, fh_smash:0, total:0 };
      this._strokeTimes = [];
      this.strokesPerMin = 0;
      this.elapsedSeconds = 0;
    },

    _notify(text, type = 'info') {
      const id = Date.now();
      this.notifications.push({ id, text, type });
      setTimeout(() => {
        this.notifications = this.notifications.filter(n => n.id !== id);
      }, 3000);
    },

    notify(text, type = 'info') { this._notify(text, type); },

    // ── API helpers ───────────────────────────────────────────────────────────

    async apiPost(url, body) {
      const r = await fetch('/api' + url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(err.detail || 'Erreur serveur');
      }
      return r.json();
    },

    async apiGet(url) {
      const r = await fetch('/api' + url);
      if (!r.ok) throw new Error(r.statusText);
      return r.json();
    },
  });
});
