"""
Zeta Network - Hub Central
Version avec libp2p fonctionnel sans WebRTC
"""

from flask import Flask, render_template_string, jsonify
import json
import datetime

app = Flask(__name__)

# ============================================
# CONFIGURATION - VOS RELAIS
# ============================================

BOOTSTRAP_RELAYS = [
    {
        "id": "relay-01",
        "name": "Relais Principal",
        "multiaddr": "/ip4/65.75.201.11/tcp/4001/ws",
        "endpoint": "ws://65.75.201.11:4001",
        "region": "Paris",
        "latency": 45,
        "status": "online"
    },
    {
        "id": "relay-02", 
        "name": "Relais Secondaire",
        "multiaddr": "/ip4/65.75.200.180/tcp/4001/ws",
        "endpoint": "ws://65.75.200.180:4001",
        "region": "Francfort",
        "latency": 60,
        "status": "online"
    }
]

# ============================================
# PAGE PRINCIPALE - CLIENT LIBP2P SIMPLIFIÉ
# ============================================

INDEX_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zeta Network - Réseau Social P2P</title>
    
    <!-- Version spécifique et compatible de libp2p -->
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
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #fff;
            line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem 0;
            margin-bottom: 2rem;
            border-radius: 0 0 20px 20px;
        }
        .header-content { text-align: center; }
        h1 { font-size: 3rem; margin-bottom: 0.5rem; }
        
        .status-bar {
            background: #1a1a1a;
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #666;
        }
        .status-indicator.connected { background: #10b981; box-shadow: 0 0 10px #10b981; }
        .status-indicator.connecting { background: #f59e0b; }
        .status-indicator.error { background: #ef4444; }
        
        .dashboard {
            display: grid;
            grid-template-columns: 300px 1fr;
            gap: 2rem;
        }
        
        .sidebar {
            background: #1a1a1a;
            border-radius: 15px;
            padding: 1.5rem;
        }
        
        .relay-list {
            list-style: none;
            margin-top: 1rem;
        }
        .relay-item {
            background: #252525;
            padding: 1rem;
            margin-bottom: 0.5rem;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .relay-status {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .connected .relay-status { background: #10b981; }
        
        .feed {
            background: #1a1a1a;
            border-radius: 15px;
            padding: 1.5rem;
        }
        
        .post-form {
            background: #252525;
            padding: 1.5rem;
            border-radius: 10px;
            margin-bottom: 1.5rem;
        }
        textarea {
            width: 100%;
            background: #333;
            border: none;
            border-radius: 8px;
            padding: 1rem;
            color: white;
            font-size: 1rem;
            resize: vertical;
            min-height: 100px;
            margin-bottom: 1rem;
        }
        textarea:focus {
            outline: 2px solid #667eea;
            background: #3a3a3a;
        }
        
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 0.8rem 1.5rem;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s;
        }
        button:hover { transform: translateY(-2px); }
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .messages {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            max-height: 600px;
            overflow-y: auto;
            padding-right: 5px;
        }
        
        .message {
            background: #252525;
            padding: 1.5rem;
            border-radius: 10px;
            border-left: 4px solid #764ba2;
        }
        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.5rem;
            color: #a78bfa;
        }
        .message-time {
            font-size: 0.8rem;
            color: #888;
        }
        .message-content {
            font-size: 1.1rem;
            margin-bottom: 0.5rem;
            word-break: break-word;
        }
        
        .stats {
            display: flex;
            justify-content: space-around;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #333;
        }
        .stat {
            text-align: center;
        }
        .stat-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #667eea;
        }
        .stat-label {
            font-size: 0.8rem;
            color: #888;
        }
        
        .peer-id {
            background: #252525;
            padding: 0.5rem;
            border-radius: 5px;
            font-family: monospace;
            font-size: 0.8rem;
            word-break: break-all;
            margin-top: 1rem;
        }
        
        @media (max-width: 768px) {
            .dashboard { grid-template-columns: 1fr; }
            h1 { font-size: 2rem; }
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <div class="header-content">
                <h1>ζ Zeta Network</h1>
                <p style="font-size: 1.2rem; opacity: 0.9;">Réseau social P2P décentralisé</p>
            </div>
        </div>
    </header>
    
    <div class="container">
        <!-- Status Bar -->
        <div class="status-bar">
            <div id="statusIndicator" class="status-indicator"></div>
            <div id="statusText">Initialisation du réseau P2P...</div>
            <div id="peerId" class="peer-id" style="margin-left: auto; margin-top: 0;"></div>
        </div>
        
        <div class="dashboard">
            <!-- Sidebar -->
            <aside class="sidebar">
                <h3 style="color: #667eea; margin-bottom: 1rem;">📡 Relais P2P</h3>
                <div id="relayList" class="relay-list"></div>
                
                <div style="margin-top: 2rem;">
                    <h3 style="color: #667eea; margin-bottom: 1rem;">📊 Statistiques</h3>
                    <div class="stats">
                        <div class="stat">
                            <div class="stat-value" id="msgCount">0</div>
                            <div class="stat-label">Messages</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" id="peerCount">0</div>
                            <div class="stat-label">Pairs</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" id="relayCount">0</div>
                            <div class="stat-label">Relais</div>
                        </div>
                    </div>
                </div>
                
                <div style="margin-top: 2rem;">
                    <h3 style="color: #667eea; margin-bottom: 1rem;">📝 Topic</h3>
                    <div style="background: #252525; padding: 0.8rem; border-radius: 5px;">
                        <code style="color: #a78bfa;">zeta-network-global</code>
                    </div>
                </div>
            </aside>
            
            <!-- Main Content -->
            <main class="feed">
                <h3 style="color: #667eea; margin-bottom: 1.5rem;">🌍 Fil d'actualité global</h3>
                
                <div class="post-form">
                    <textarea id="messageInput" 
                              placeholder="Publier un message sur le réseau P2P..."></textarea>
                    <button id="sendButton" onclick="sendMessage()" disabled>
                        📤 Publier
                    </button>
                    <span id="publishStatus" style="margin-left: 1rem; color: #888;"></span>
                </div>
                
                <div id="messageContainer" class="messages">
                    <div style="text-align: center; color: #888; padding: 2rem;">
                        Connexion au réseau P2P en cours...
                    </div>
                </div>
            </main>
        </div>
    </div>
    
    <script type="module">
        // ============================================
        // IMPORTS LIBP2P - VERSION COMPATIBLE
        // ============================================
        
        import { createLibp2p } from 'libp2p';
        import { webSockets } from '@libp2p/websockets';
        import { noise } from '@chainsafe/libp2p-noise';
        import { yamux } from '@chainsafe/libp2p-yamux';
        import { gossipsub } from '@chainsafe/libp2p-gossipsub';
        import { bootstrap } from '@libp2p/bootstrap';
        
        // ============================================
        // CONFIGURATION
        // ============================================
        
        const RELAYS = {{ relays | safe }};
        const TOPIC = 'zeta-network-global';
        
        // ============================================
        // ÉTAT
        // ============================================
        
        let libp2p = null;
        let messages = [];
        let connectedPeers = new Set();
        
        // ============================================
        // INITIALISATION LIBP2P
        // ============================================
        
        async function initLibp2p() {
            try {
                updateStatus('connecting', '🚀 Démarrage de libp2p...');
                
                // Configuration bootstrap avec vos relais
                const bootstrapMultiaddrs = RELAYS.map(r => r.multiaddr);
                
                // Créer le noeud libp2p
                libp2p = await createLibp2p({
                    addresses: {
                        listen: []
                    },
                    transports: [
                        webSockets()
                    ],
                    connectionEncryptors: [noise()],
                    streamMuxers: [yamux()],
                    peerDiscovery: [
                        bootstrap({
                            list: bootstrapMultiaddrs,
                            timeout: 1000,
                            tagName: 'bootstrap',
                            limit: 10
                        })
                    ],
                    services: {
                        pubsub: gossipsub({
                            emitSelf: true,
                            allowPublishToZeroPeers: true,
                            floodPublish: true,
                            doPX: false,
                            messageProcessingConcurrency: 16
                        })
                    },
                    connectionManager: {
                        minConnections: 0,
                        maxConnections: 100,
                        autoDial: true,
                        autoDialInterval: 10000
                    }
                });
                
                // Écouter les événements
                libp2p.addEventListener('peer:discovery', (evt) => {
                    console.log('🔍 Pair découvert:', evt.detail.id.toString());
                });
                
                libp2p.addEventListener('peer:connect', (evt) => {
                    const peerId = evt.detail.toString();
                    connectedPeers.add(peerId);
                    updatePeerCount();
                    updateStatus('connected', `✅ Connecté à ${connectedPeers.size} pair(s)`);
                    updateRelayStatus(peerId, true);
                });
                
                libp2p.addEventListener('peer:disconnect', (evt) => {
                    const peerId = evt.detail.toString();
                    connectedPeers.delete(peerId);
                    updatePeerCount();
                    updateRelayStatus(peerId, false);
                });
                
                // Démarrer
                await libp2p.start();
                
                // Afficher PeerId
                const peerId = libp2p.peerId.toString();
                document.getElementById('peerId').textContent = `🆔 ${peerId.slice(0, 16)}...`;
                
                // S'abonner au topic
                const pubsub = libp2p.services.pubsub;
                await pubsub.subscribe(TOPIC);
                console.log(`📡 Abonné à ${TOPIC}`);
                
                // Écouter les messages
                pubsub.addEventListener('message', handleMessage);
                
                // Activer le bouton
                document.getElementById('sendButton').disabled = false;
                
                // Afficher la liste des relais
                displayRelays();
                
                // Message de bienvenue
                addSystemMessage('✅ Connecté au réseau Zeta Network');
                addSystemMessage(`📡 Relais configurés: ${RELAYS.length}`);
                
            } catch (error) {
                console.error('Erreur:', error);
                updateStatus('error', `❌ ${error.message}`);
                addSystemMessage(`❌ Erreur: ${error.message}`);
            }
        }
        
        // ============================================
        // GESTION DES MESSAGES
        // ============================================
        
        function handleMessage(event) {
            try {
                const msg = event.detail;
                const data = JSON.parse(new TextDecoder().decode(msg.data));
                
                const message = {
                    id: msg.msgId || `msg-${Date.now()}-${Math.random()}`,
                    content: data.content,
                    author: data.author || msg.from?.toString().slice(0, 8) || 'anonyme',
                    timestamp: data.timestamp || new Date().toISOString(),
                    from: msg.from?.toString()
                };
                
                messages.unshift(message);
                if (messages.length > 100) messages.pop();
                
                displayMessage(message);
                updateMsgCount();
                
            } catch (error) {
                console.error('Erreur message:', error);
            }
        }
        
        // ============================================
        // ENVOI DE MESSAGE
        // ============================================
        
        window.sendMessage = async function() {
            const input = document.getElementById('messageInput');
            const content = input.value.trim();
            
            if (!content) {
                alert('Veuillez écrire un message');
                return;
            }
            
            try {
                const pubsub = libp2p?.services?.pubsub;
                if (!pubsub) throw new Error('Réseau non connecté');
                
                const status = document.getElementById('publishStatus');
                status.textContent = '⏳ Publication...';
                
                const message = {
                    content: content,
                    author: libp2p.peerId.toString().slice(0, 8),
                    timestamp: new Date().toISOString()
                };
                
                await pubsub.publish(TOPIC, new TextEncoder().encode(JSON.stringify(message)));
                
                input.value = '';
                status.textContent = '✅ Publié !';
                setTimeout(() => { status.textContent = ''; }, 2000);
                
            } catch (error) {
                console.error('Erreur publication:', error);
                document.getElementById('publishStatus').textContent = '❌ Échec';
            }
        };
        
        // ============================================
        // FONCTIONS D'AFFICHAGE
        // ============================================
        
        function displayRelays() {
            const list = document.getElementById('relayList');
            list.innerHTML = '';
            
            RELAYS.forEach(relay => {
                const div = document.createElement('div');
                div.className = 'relay-item';
                div.id = `relay-${relay.id}`;
                div.innerHTML = `
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <span>
                            <span class="relay-status"></span>
                            <strong>${relay.name}</strong>
                        </span>
                        <span style="color: #888; font-size: 0.9rem;" class="relay-connection-status">
                            Connexion...
                        </span>
                    </div>
                    <div style="font-size: 0.8rem; color: #888; margin-top: 5px; margin-left: 16px;">
                        ${relay.region} • ${relay.latency}ms • ${relay.multiaddr}
                    </div>
                `;
                list.appendChild(div);
            });
        }
        
        function updateRelayStatus(peerId, connected) {
            // Cette fonction serait appelée quand un relais se connecte
            // Pour l'instant, on marque tous les relais comme connectés
            RELAYS.forEach(relay => {
                const el = document.getElementById(`relay-${relay.id}`);
                if (el) {
                    const statusEl = el.querySelector('.relay-connection-status');
                    if (statusEl) {
                        statusEl.innerHTML = '✓ Connecté';
                        statusEl.style.color = '#10b981';
                    }
                    el.classList.add('connected');
                }
            });
            
            document.getElementById('relayCount').textContent = RELAYS.length;
        }
        
        function displayMessage(message) {
            const container = document.getElementById('messageContainer');
            
            if (container.children.length === 1 && container.children[0].textContent.includes('Connexion')) {
                container.innerHTML = '';
            }
            
            const div = document.createElement('div');
            div.className = 'message';
            
            const time = new Date(message.timestamp).toLocaleTimeString('fr-FR', {
                hour: '2-digit',
                minute: '2-digit'
            });
            
            const author = message.author || message.from?.slice(0, 8) || 'anonyme';
            
            div.innerHTML = `
                <div class="message-header">
                    <strong style="color: #a78bfa;">${escapeHtml(author)}</strong>
                    <span class="message-time">${time}</span>
                </div>
                <div class="message-content">${escapeHtml(message.content)}</div>
            `;
            
            container.insertBefore(div, container.firstChild);
        }
        
        function addSystemMessage(text) {
            const container = document.getElementById('messageContainer');
            
            if (container.children.length === 1 && container.children[0].textContent.includes('Connexion')) {
                container.innerHTML = '';
            }
            
            const div = document.createElement('div');
            div.className = 'message';
            div.style.borderLeftColor = '#888';
            div.innerHTML = `
                <div class="message-header">
                    <strong style="color: #888;">🤖 Système</strong>
                    <span class="message-time">${new Date().toLocaleTimeString('fr-FR', {hour: '2-digit', minute: '2-digit'})}</span>
                </div>
                <div class="message-content">${escapeHtml(text)}</div>
            `;
            
            container.insertBefore(div, container.firstChild);
        }
        
        function updateStatus(state, text) {
            const indicator = document.getElementById('statusIndicator');
            const statusText = document.getElementById('statusText');
            
            indicator.className = 'status-indicator ' + state;
            statusText.textContent = text;
        }
        
        function updatePeerCount() {
            document.getElementById('peerCount').textContent = connectedPeers.size;
        }
        
        function updateMsgCount() {
            document.getElementById('msgCount').textContent = messages.length;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // ============================================
        // INITIALISATION
        // ============================================
        
        window.addEventListener('load', () => {
            initLibp2p().catch(console.error);
        });
        
        // Entrée pour envoyer
        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                window.sendMessage();
            }
        });
        
        window.sendMessage = window.sendMessage;
        
    </script>
</body>
</html>
"""

# ============================================
# ROUTES FLASK
# ============================================

@app.route('/')
def home():
    """Page principale"""
    return render_template_string(
        INDEX_HTML, 
        relays=json.dumps(BOOTSTRAP_RELAYS)
    )

@app.route('/api/relays')
def get_relays():
    """API des relais"""
    return jsonify({
        "relays": BOOTSTRAP_RELAYS,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "service": "zeta-network",
        "relays": len(BOOTSTRAP_RELAYS),
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)