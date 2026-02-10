"""
APP.PY MINIMAL POUR TEST - Zeta Network
"""

from flask import Flask, render_template, jsonify
import os

# Créer l'application Flask
app = Flask(__name__)

# Configuration de base
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-tt665')
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Route de test principale
@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>✅ Zeta Network - ONLINE</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
                padding: 50px;
            }
            .container {
                background: rgba(0,0,0,0.7);
                padding: 30px;
                border-radius: 15px;
                display: inline-block;
            }
            h1 { color: #4CAF50; }
            .status { 
                font-size: 24px; 
                margin: 20px 0;
                padding: 10px;
                background: #4CAF50;
                border-radius: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌐 Zeta Network</h1>
            <div class="status">✅ SERVEUR CENTRAL ACTIF</div>
            <p>Hub central du réseau social P2P décentralisé</p>
            <p><strong>URL:</strong> https://zetanetwork.org</p>
            <p><strong>Statut:</strong> En ligne et opérationnel</p>
            <hr>
            <h3>📡 Endpoints API:</h3>
            <ul style="text-align: left; display: inline-block;">
                <li><a href="/api/relays" style="color: #ffcc00;">/api/relays</a> - Liste des relais</li>
                <li><a href="/api/health" style="color: #ffcc00;">/api/health</a> - Santé du serveur</li>
                <li><a href="/api/network/stats" style="color: #ffcc00;">/api/network/stats</a> - Statistiques</li>
            </ul>
        </div>
    </body>
    </html>
    """

# API: Liste des relais
@app.route('/api/relays')
def get_relays():
    return jsonify({
        "relays": [
            {
                "id": "relay-01",
                "name": "Relais Principal",
                "multiaddr": "/ip4/65.75.201.11/tcp/4001/ws",
                "endpoint": "ws://65.75.201.11:4001",
                "type": "websocket",
                "region": "eu-west",
                "latency": 45,
                "status": "online",
                "is_verified": True
            },
            {
                "id": "relay-02", 
                "name": "Relais Secondaire",
                "multiaddr": "/ip4/65.75.200.180/tcp/4001/ws",
                "endpoint": "ws://65.75.200.180:4001",
                "type": "websocket",
                "region": "eu-central",
                "latency": 60,
                "status": "online",
                "is_verified": True
            }
        ],
        "network_status": "active",
        "total_relays": 2,
        "timestamp": "2026-02-09T12:00:00Z"
    })

# API: Santé du serveur
@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "zeta-central-hub",
        "version": "1.0.0",
        "uptime": "0",
        "timestamp": "2026-02-09T12:00:00Z"
    })

# API: Statistiques réseau
@app.route('/api/network/stats')
def network_stats():
    return jsonify({
        "total_relays": 2,
        "online_relays": 2,
        "active_users": 0,
        "messages_today": 0,
        "network_load": "low",
        "timestamp": "2026-02-09T12:00:00Z"
    })

# Page de test
@app.route('/test')
def test():
    return "✅ Test réussi - Flask fonctionne correctement"

# Gestion d'erreur 404
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

# Point d'entrée pour le développement
if __name__ == '__main__':
    print("🚀 Démarrage de Zeta Network...")
    print(f"📁 Répertoire: {os.getcwd()}")
    print(f"📄 Fichiers: {os.listdir('.')}")
    app.run(host='0.0.0.0', port=5000, debug=True)