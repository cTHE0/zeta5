"""
Zeta Network – Hub Central (PythonAnywhere)
Version finale avec client libp2p fonctionnel en HTTPS → WSS
"""

from flask import Flask, render_template_string, jsonify
import json
import datetime

app = Flask(__name__)

# ============================================
# RELAIS BOOTSTRAP – utilisez VOS domaines SSL
# ============================================
BOOTSTRAP_RELAYS = [
    {
        "id": "relay-01",
        "name": "Relais Paris",
        "multiaddr": "/dns4/relay1.zetanetwork.org/tcp/443/wss",
        "endpoint": "wss://relay1.zetanetwork.org",
        "region": "Paris",
        "latency": 45,
        "status": "online"
    },
    {
        "id": "relay-02",
        "name": "Relais Francfort",
        "multiaddr": "/dns4/relay2.zetanetwork.org/tcp/443/wss",
        "endpoint": "wss://relay2.zetanetwork.org",
        "region": "Francfort",
        "latency": 60,
        "status": "online"
    }
]

INDEX_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeta Network – Réseau social P2P</title>
    <!-- libp2p stable, sans WebRTC -->
    <script type="importmap">
        {
            "imports": {
                "libp2p": "https://esm.sh/libp2p@0.46.22",
                "@libp2p/websockets": "https://esm.sh/@libp2p/websockets@5.0.5",
                "@chainsafe/libp2p-noise": "https://esm.sh/@chainsafe/libp2p-noise@11.0.0",
                "@chainsafe/libp2p-yamux": "https://esm.sh/@chainsafe/libp2p-yamux@4.0.0",
                "@chainsafe/libp2p-gossipsub": "https://esm.sh/@chainsafe/libp2p-gossipsub@7.0.0",
                "@libp2p/bootstrap": "https://esm.sh/@libp2p/bootstrap@6.0.3"
            }
        }
    </script>
    <style>
        /* (styles identiques à ceux fournis précédemment) */
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family: system-ui, sans-serif; background:#0a0a0a; color:#fff; line-height:1.6; }
        .container { max-width:1200px; margin:0 auto; padding:20px; }
        header { background:linear-gradient(135deg,#667eea,#764ba2); padding:2rem 0; margin-bottom:2rem; border-radius:0 0 20px 20px; }
        .header-content { text-align:center; }
        h1 { font-size:3rem; margin-bottom:0.5rem; }
        .status-bar { background:#1a1a1a; padding:1rem; border-radius:10px; margin-bottom:2rem; display:flex; align-items:center; gap:1rem; }
        .status-indicator { width:12px; height:12px; border-radius:50%; background:#666; }
        .connected { background:#10b981; box-shadow:0 0 10px #10b981; }
        .connecting { background:#f59e0b; }
        .error { background:#ef4444; }
        .dashboard { display:grid; grid-template-columns:300px 1fr; gap:2rem; }
        .sidebar { background:#1a1a1a; border-radius:15px; padding:1.5rem; }
        .relay-item { background:#252525; padding:1rem; margin-bottom:0.5rem; border-radius:8px; border-left:4px solid #667eea; }
        .feed { background:#1a1a1a; border-radius:15px; padding:1.5rem; }
        .post-form { background:#252525; padding:1.5rem; border-radius:10px; margin-bottom:1.5rem; }
        textarea { width:100%; background:#333; border:none; border-radius:8px; padding:1rem; color:white; font-size:1rem; resize:vertical; min-height:100px; margin-bottom:1rem; }
        button { background:linear-gradient(135deg,#667eea,#764ba2); color:white; border:none; padding:0.8rem 1.5rem; border-radius:8px; cursor:pointer; font-weight:600; transition:transform 0.2s; }
        button:hover { transform:translateY(-2px); }
        .messages { display:flex; flex-direction:column; gap:1rem; max-height:600px; overflow-y:auto; padding-right:5px; }
        .message { background:#252525; padding:1.5rem; border-radius:10px; border-left:4px solid #764ba2; }
        .stats { display:flex; justify-content:space-around; margin-top:2rem; padding-top:1rem; border-top:1px solid #333; }
        .stat-value { font-size:1.5rem; font-weight:bold; color:#667eea; }
        .peer-id { background:#252525; padding:0.5rem; border-radius:5px; font-family:monospace; font-size:0.8rem; word-break:break-all; }
    </style>
</head>
<body>
    <header>
        <div class="container"><div class="header-content"><h1>ζ Zeta Network</h1><p style="font-size:1.2rem; opacity:0.9;">Réseau social P2P décentralisé</p></div></div>
    </header>
    <div class="container">
        <div class="status-bar">
            <div id="statusIndicator" class="status-indicator"></div>
            <div id="statusText">Initialisation...</div>
            <div id="peerId" class="peer-id" style="margin-left:auto;"></div>
        </div>
        <div class="dashboard">
            <aside class="sidebar">
                <h3 style="color:#667eea; margin-bottom:1rem;">📡 Relais P2P</h3>
                <div id="relayList"></div>
                <div style="margin-top:2rem;"><h3 style="color:#667eea; margin-bottom:1rem;">📊 Statistiques</h3>
                    <div class="stats">
                        <div class="stat"><div class="stat-value" id="msgCount">0</div><div class="stat-label">Messages</div></div>
                        <div class="stat"><div class="stat-value" id="peerCount">0</div><div class="stat-label">Pairs</div></div>
                        <div class="stat"><div class="stat-value" id="relayCount">0</div><div class="stat-label">Relais</div></div>
                    </div>
                </div>
                <div style="margin-top:2rem;"><h3 style="color:#667eea; margin-bottom:1rem;">📝 Topic</h3>
                    <div style="background:#252525; padding:0.8rem; border-radius:5px;"><code style="color:#a78bfa;">zeta-network-global</code></div>
                </div>
            </aside>
            <main class="feed">
                <h3 style="color:#667eea; margin-bottom:1.5rem;">🌍 Fil d'actualité global</h3>
                <div class="post-form">
                    <textarea id="messageInput" placeholder="Publier un message sur le réseau P2P..."></textarea>
                    <button id="sendButton" onclick="sendMessage()" disabled>📤 Publier</button>
                    <span id="publishStatus" style="margin-left:1rem; color:#888;"></span>
                </div>
                <div id="messageContainer" class="messages">
                    <div style="text-align:center; color:#888; padding:2rem;">Connexion au réseau P2P en cours...</div>
                </div>
            </main>
        </div>
    </div>
    <script type="module">
        import { createLibp2p } from 'libp2p';
        import { webSockets } from '@libp2p/websockets';
        import { noise } from '@chainsafe/libp2p-noise';
        import { yamux } from '@chainsafe/libp2p-yamux';
        import { gossipsub } from '@chainsafe/libp2p-gossipsub';
        import { bootstrap } from '@libp2p/bootstrap';

        const RELAYS = {{ relays | safe }};
        const TOPIC = 'zeta-network-global';
        let libp2p;
        let messages = [];
        let connectedPeers = new Set();

        async function init() {
            updateStatus('connecting', '🚀 Démarrage de libp2p...');
            try {
                libp2p = await createLibp2p({
                    transports: [webSockets()],
                    connectionEncryptors: [noise()],
                    streamMuxers: [yamux()],
                    peerDiscovery: [
                        bootstrap({
                            list: RELAYS.map(r => r.multiaddr),
                            timeout: 1000,
                            limit: 10
                        })
                    ],
                    services: {
                        pubsub: gossipsub({
                            emitSelf: true,
                            allowPublishToZeroPeers: true,
                            floodPublish: true
                        })
                    },
                    connectionManager: {
                        minConnections: 0,
                        maxConnections: 100,
                        autoDial: true
                    }
                });

                libp2p.addEventListener('peer:connect', (evt) => {
                    connectedPeers.add(evt.detail.toString());
                    updatePeerCount();
                    updateStatus('connected', `✅ Connecté à ${connectedPeers.size} pair(s)`);
                });
                libp2p.addEventListener('peer:disconnect', (evt) => {
                    connectedPeers.delete(evt.detail.toString());
                    updatePeerCount();
                });

                await libp2p.start();
                document.getElementById('peerId').innerText = `🆔 ${libp2p.peerId.toString().slice(0,16)}...`;
                
                const ps = libp2p.services.pubsub;
                await ps.subscribe(TOPIC);
                ps.addEventListener('message', (e) => {
                    try {
                        const msg = e.detail;
                        const data = JSON.parse(new TextDecoder().decode(msg.data));
                        const message = {
                            id: msg.msgId,
                            content: data.content,
                            author: data.author || msg.from.toString().slice(0,8),
                            timestamp: data.timestamp || new Date().toISOString()
                        };
                        messages.unshift(message);
                        if (messages.length > 100) messages.pop();
                        displayMessage(message);
                        document.getElementById('msgCount').innerText = messages.length;
                    } catch (err) { console.error(err); }
                });

                document.getElementById('sendButton').disabled = false;
                updateRelayList();
                addSystemMessage('✅ Connecté au réseau Zeta Network');
            } catch (err) {
                console.error(err);
                updateStatus('error', `❌ ${err.message}`);
                addSystemMessage(`❌ Erreur: ${err.message}`);
            }
        }

        window.sendMessage = async function() {
            const input = document.getElementById('messageInput');
            const content = input.value.trim();
            if (!content) return alert('Message vide');
            try {
                const status = document.getElementById('publishStatus');
                status.innerText = '⏳ Publication...';
                await libp2p.services.pubsub.publish(TOPIC, new TextEncoder().encode(JSON.stringify({
                    content,
                    author: libp2p.peerId.toString().slice(0,8),
                    timestamp: new Date().toISOString()
                })));
                input.value = '';
                status.innerText = '✅ Publié !';
                setTimeout(() => status.innerText = '', 2000);
            } catch (err) {
                document.getElementById('publishStatus').innerText = '❌ Échec';
            }
        };

        function updateStatus(state, text) {
            const el = document.getElementById('statusIndicator');
            el.className = 'status-indicator ' + state;
            document.getElementById('statusText').innerText = text;
        }
        function updatePeerCount() {
            document.getElementById('peerCount').innerText = connectedPeers.size;
        }
        function updateRelayList() {
            const list = document.getElementById('relayList');
            list.innerHTML = RELAYS.map(r => `<div class="relay-item">
                <div><span class="relay-status" style="background:#10b981;"></span><strong>${r.name}</strong></div>
                <div style="font-size:0.8rem; color:#888;">${r.region} • ${r.latency}ms<br>${r.endpoint}</div>
            </div>`).join('');
            document.getElementById('relayCount').innerText = RELAYS.length;
        }
        function displayMessage(m) {
            const container = document.getElementById('messageContainer');
            if (container.children.length === 1 && container.children[0].innerText.includes('Connexion')) container.innerHTML = '';
            const div = document.createElement('div');
            div.className = 'message';
            div.innerHTML = `<div class="message-header"><strong style="color:#a78bfa;">${escapeHtml(m.author)}</strong>
                <span class="message-time">${new Date(m.timestamp).toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'})}</span></div>
                <div class="message-content">${escapeHtml(m.content)}</div>`;
            container.insertBefore(div, container.firstChild);
        }
        function addSystemMessage(text) {
            const container = document.getElementById('messageContainer');
            if (container.children.length === 1 && container.children[0].innerText.includes('Connexion')) container.innerHTML = '';
            const div = document.createElement('div');
            div.className = 'message';
            div.style.borderLeftColor = '#888';
            div.innerHTML = `<div class="message-header"><strong style="color:#888;">🤖 Système</strong>
                <span class="message-time">${new Date().toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'})}</span></div>
                <div class="message-content">${escapeHtml(text)}</div>`;
            container.insertBefore(div, container.firstChild);
        }
        function escapeHtml(t) { return t.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]); }

        window.addEventListener('load', init);
        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); window.sendMessage(); }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(INDEX_HTML, relays=json.dumps(BOOTSTRAP_RELAYS))

@app.route('/api/relays')
def api_relays():
    return jsonify({"relays": BOOTSTRAP_RELAYS, "timestamp": datetime.datetime.utcnow().isoformat()})

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "zeta-network-central", "relays": len(BOOTSTRAP_RELAYS)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)