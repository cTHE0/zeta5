// Configuration
const CONFIG = {
    MAX_CONNECTIONS: 10,
    RECONNECT_DELAY: 5000,
    HEALTH_CHECK_INTERVAL: 30000,
    MESSAGE_LIMIT: 1000,
    API_BASE: '/api/v1'
};

// État de l'application
class AppState {
    constructor() {
        this.peerId = `user-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        this.connections = new Map();
        this.activeRelays = new Set();
        this.messages = [];
        this.stats = {
            messagesReceived: 0,
            bytesTransferred: 0,
            connectedSince: Date.now()
        };
        this.libp2pNode = null;
        this.gossipsub = null;
    }
}

// Gestionnaire P2P avec libp2p réel
class P2PManager {
    constructor() {
        this.state = new AppState();
        this.init();
    }

    async init() {
        try {
            // Initialiser libp2p
            await this.initLibp2p();
            
            // Obtenir la liste des relais
            await this.fetchRelays();
            
            // Se connecter aux meilleurs relais
            await this.connectToNetwork();
            
            // Démarrer les services
            this.startServices();
            
            this.updateUI('ready');
            console.log('✅ Réseau P2P initialisé');
            
        } catch (error) {
            console.error('❌ Erreur d\'initialisation:', error);
            this.handleConnectionError();
        }
    }

    async initLibp2p() {
        // Import dynamique pour éviter les erreurs de chargement
        const { createLibp2p } = await import('https://unpkg.com/libp2p@0.46.0/dist/index.min.js');
        const { webSockets } = await import('https://unpkg.com/@libp2p/websockets@0.9.0/dist/index.min.js');
        const { noise } = await import('https://unpkg.com/@chainsafe/libp2p-noise@0.12.0/dist/index.min.js');
        const { yamux } = await import('https://unpkg.com/@chainsafe/libp2p-yamux@0.13.0/dist/index.min.js');
        const { gossipsub } = await import('https://unpkg.com/@chainsafe/libp2p-gossipsub@0.15.0/dist/index.min.js');
        const { circuitRelayTransport } = await import('https://unpkg.com/@libp2p/circuit-relay-v2@0.4.0/dist/index.min.js');

        // Créer le nœud libp2p
        this.state.libp2pNode = await createLibp2p({
            addresses: {
                listen: ['/webrtc']
            },
            transports: [
                webSockets(),
                circuitRelayTransport({
                    discoverRelays: 1
                })
            ],
            connectionEncryption: [noise()],
            streamMuxers: [yamux()],
            connectionManager: {
                minConnections: 1,
                maxConnections: CONFIG.MAX_CONNECTIONS
            },
            services: {
                pubsub: gossipsub({
                    emitSelf: false,
                    canRelayMessage: true,
                    messageProcessingTimeout: 1000
                })
            }
        });

        // Récupérer gossipsub pour plus tard
        this.state.gossipsub = this.state.libp2pNode.services.pubsub;

        // Événements
        this.state.libp2pNode.addEventListener('peer:connect', (event) => {
            const peerId = event.detail.toString();
            console.log(`🔗 Connecté à: ${peerId}`);
            this.state.activeRelays.add(peerId);
            this.updateRelayDisplay();
        });

        this.state.libp2pNode.addEventListener('peer:disconnect', (event) => {
            const peerId = event.detail.toString();
            console.log(`🔌 Déconnecté de: ${peerId}`);
            this.state.activeRelays.delete(peerId);
            this.updateRelayDisplay();
        });

        await this.state.libp2pNode.start();
        console.log(`🆔 Peer ID: ${this.state.libp2pNode.peerId.toString()}`);
    }

    async fetchRelays() {
        try {
            const response = await fetch(`${CONFIG.API_BASE}/network/relays`);
            const data = await response.json();
            
            // Trier par latence et statut
            this.state.availableRelays = data.relays
                .filter(relay => relay.status === 'online')
                .sort((a, b) => a.latency - b.latency)
                .slice(0, CONFIG.MAX_CONNECTIONS);
            
            console.log(`📡 ${this.state.availableRelays.length} relais disponibles`);
            return this.state.availableRelays;
            
        } catch (error) {
            console.error('Erreur récupération relais:', error);
            throw error;
        }
    }

    async connectToNetwork() {
        if (!this.state.availableRelays || this.state.availableRelays.length === 0) {
            throw new Error('Aucun relais disponible');
        }

        const connections = [];
        
        // Essayer de se connecter aux relais disponibles
        for (const relay of this.state.availableRelays) {
            if (this.state.activeRelays.size >= CONFIG.MAX_CONNECTIONS) break;
            
            try {
                console.log(`Tentative de connexion à: ${relay.endpoint || relay.multiaddr}`);
                
                // Se connecter via libp2p
                await this.state.libp2pNode.dial(relay.multiaddr);
                
                connections.push(relay.id);
                console.log(`✅ Connecté à ${relay.name || relay.id}`);
                
                // Petite pause entre les connexions
                await new Promise(resolve => setTimeout(resolve, 500));
                
            } catch (error) {
                console.warn(`❌ Échec connexion ${relay.id}:`, error.message);
                continue;
            }
        }

        if (connections.length === 0) {
            throw new Error('Impossible de se connecter à aucun relais');
        }

        // S'abonner au topic global
        await this.subscribeToTopics();
        
        // Enregistrer la session
        await this.registerSession(connections);
    }

    async subscribeToTopics() {
        if (!this.state.gossipsub) return;
        
        // S'abonner aux topics principaux
        const topics = ['zeta-network-global', 'zeta-system-announcements'];
        
        for (const topic of topics) {
            try {
                await this.state.gossipsub.subscribe(topic);
                console.log(`📰 Abonné au topic: ${topic}`);
                
                // Écouter les messages
                this.state.gossipsub.addEventListener(topic, (event) => {
                    this.handleIncomingMessage(event.detail, topic);
                });
                
            } catch (error) {
                console.error(`Erreur abonnement ${topic}:`, error);
            }
        }
    }

    async registerSession(connectedRelays) {
        try {
            await fetch(`${CONFIG.API_BASE}/users/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    peer_id: this.state.libp2pNode.peerId.toString(),
                    connected_relays: connectedRelays,
                    user_agent: navigator.userAgent
                })
            });
        } catch (error) {
            // Silencieux - pas critique
            console.warn('Enregistrement session échoué:', error);
        }
    }

    handleIncomingMessage(message, topic) {
        try {
            // Décoder le message
            const data = JSON.parse(new TextDecoder().decode(message.data));
            
            // Ajouter des métadonnées
            const enrichedMessage = {
                ...data,
                id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                topic: topic,
                receivedAt: new Date().toISOString(),
                source: message.from ? message.from.toString() : 'unknown',
                hops: message.topic
            };
            
            // Stocker localement
            this.state.messages.unshift(enrichedMessage);
            this.state.stats.messagesReceived++;
            
            // Limiter le nombre de messages
            if (this.state.messages.length > CONFIG.MESSAGE_LIMIT) {
                this.state.messages = this.state.messages.slice(0, CONFIG.MESSAGE_LIMIT);
            }
            
            // Sauvegarder dans IndexedDB
            this.saveToIndexedDB(enrichedMessage);
            
            // Afficher
            this.displayMessage(enrichedMessage);
            this.updateStats();
            
        } catch (error) {
            console.error('Erreur traitement message:', error, message);
        }
    }

    async sendMessage(content, topic = 'zeta-network-global') {
        if (!this.state.gossipsub) {
            throw new Error('Gossipsub non initialisé');
        }
        
        const message = {
            type: 'user_message',
            content: content,
            author: this.state.peerId,
            timestamp: new Date().toISOString(),
            version: '1.0'
        };
        
        try {
            await this.state.gossipsub.publish(topic, new TextEncoder().encode(JSON.stringify(message)));
            
            // Afficher localement aussi
            const localMessage = {
                ...message,
                id: `local-${Date.now()}`,
                topic: topic,
                receivedAt: new Date().toISOString(),
                source: 'local'
            };
            
            this.state.messages.unshift(localMessage);
            this.displayMessage(localMessage);
            
            console.log('📤 Message publié sur le réseau');
            return true;
            
        } catch (error) {
            console.error('Erreur publication:', error);
            return false;
        }
    }

    // Gestion IndexedDB
    async initIndexedDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open('ZetaNetworkDB', 1);
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // Store pour les messages
                if (!db.objectStoreNames.contains('messages')) {
                    const store = db.createObjectStore('messages', { keyPath: 'id' });
                    store.createIndex('timestamp', 'timestamp', { unique: false });
                    store.createIndex('topic', 'topic', { unique: false });
                }
                
                // Store pour les paramètres
                if (!db.objectStoreNames.contains('settings')) {
                    db.createObjectStore('settings', { keyPath: 'key' });
                }
            };
            
            request.onsuccess = (event) => {
                this.db = event.target.result;
                resolve(this.db);
            };
            
            request.onerror = (event) => {
                reject(event.target.error);
            };
        });
    }

    async saveToIndexedDB(message) {
        if (!this.db) return;
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['messages'], 'readwrite');
            const store = transaction.objectStore('messages');
            
            const request = store.put(message);
            
            request.onsuccess = () => resolve();
            request.onerror = (event) => reject(event.target.error);
        });
    }

    async loadFromIndexedDB(limit = 100) {
        if (!this.db) return [];
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['messages'], 'readonly');
            const store = transaction.objectStore('messages');
            const index = store.index('timestamp');
            
            const request = index.openCursor(null, 'prev');
            const messages = [];
            
            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor && messages.length < limit) {
                    messages.push(cursor.value);
                    cursor.continue();
                } else {
                    resolve(messages);
                }
            };
            
            request.onerror = (event) => reject(event.target.error);
        });
    }

    // Services en arrière-plan
    startServices() {
        // Vérification santé réseau
        setInterval(() => {
            this.healthCheck();
        }, CONFIG.HEALTH_CHECK_INTERVAL);
        
        // Recharger les relais périodiquement
        setInterval(async () => {
            if (this.state.activeRelays.size < 3) {
                console.log('Peu de connexions, recherche de nouveaux relais...');
                await this.fetchRelays();
                await this.connectToNetwork();
            }
        }, 60000);
        
        // Charger les anciens messages
        setTimeout(async () => {
            try {
                await this.initIndexedDB();
                const savedMessages = await this.loadFromIndexedDB(50);
                savedMessages.reverse().forEach(msg => this.displayMessage(msg));
            } catch (error) {
                console.warn('IndexedDB non disponible:', error);
            }
        }, 1000);
    }

    async healthCheck() {
        const activeConnections = this.state.activeRelays.size;
        
        if (activeConnections === 0) {
            console.warn('⚠️ Aucune connexion active, tentative de reconnexion...');
            await this.connectToNetwork();
        }
    }

    // UI Helpers
    updateUI(status) {
        document.getElementById('networkStatus').textContent = status;
        document.getElementById('networkStatus').className = `status-${status}`;
    }

    updateRelayDisplay() {
        const container = document.getElementById('relayList');
        if (!container) return;
        
        container.innerHTML = '';
        
        this.state.activeRelays.forEach(peerId => {
            const div = document.createElement('div');
            div.className = 'relay-item';
            div.innerHTML = `
                <span class="relay-status active"></span>
                <span class="relay-id">${peerId.substring(0, 16)}...</span>
                <span class="relay-type">P2P</span>
            `;
            container.appendChild(div);
        });
        
        document.getElementById('connectedCount').textContent = this.state.activeRelays.size;
    }

    displayMessage(message) {
        const container = document.getElementById('messageContainer');
        if (!container) return;
        
        const div = document.createElement('div');
        div.className = `message ${message.source === 'local' ? 'message-local' : ''}`;
        div.innerHTML = `
            <div class="message-header">
                <span class="message-author">${message.author || 'Anonymous'}</span>
                <span class="message-time">${new Date(message.timestamp).toLocaleTimeString()}</span>
            </div>
            <div class="message-content">${this.escapeHtml(message.content)}</div>
            <div class="message-footer">
                <span class="message-topic">#${message.topic}</span>
                ${message.source !== 'local' ? `<span class="message-source">via ${message.source.substring(0, 8)}...</span>` : ''}
            </div>
        `;
        
        container.insertBefore(div, container.firstChild);
        
        // Limiter l'affichage
        if (container.children.length > 50) {
            container.removeChild(container.lastChild);
        }
    }

    updateStats() {
        document.getElementById('messageCount').textContent = this.state.stats.messagesReceived;
        document.getElementById('connectionCount').textContent = this.state.activeRelays.size;
        
        const uptime = Math.floor((Date.now() - this.state.stats.connectedSince) / 1000);
        document.getElementById('uptime').textContent = this.formatUptime(uptime);
    }

    handleConnectionError() {
        this.updateUI('error');
        
        // Réessayer après délai
        setTimeout(() => {
            this.init();
        }, CONFIG.RECONNECT_DELAY);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatUptime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }
}

// Initialisation
let p2pManager;

document.addEventListener('DOMContentLoaded', async () => {
    console.log('🚀 Démarrage Zeta Network...');
    
    try {
        p2pManager = new P2PManager();
        
        // Gestionnaire d'envoi de message
        window.sendMessage = function() {
            const input = document.getElementById('messageInput');
            const content = input.value.trim();
            
            if (content && p2pManager) {
                p2pManager.sendMessage(content);
                input.value = '';
            } else {
                alert('Veuillez entrer un message');
            }
        };
        
        // Touche Entrée
        document.getElementById('messageInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                window.sendMessage();
            }
        });
        
    } catch (error) {
        console.error('Erreur initialisation:', error);
        document.getElementById('networkStatus').textContent = 'error';
        document.getElementById('networkStatus').className = 'status-error';
    }
});