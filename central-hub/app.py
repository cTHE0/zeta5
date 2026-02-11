"""
Zeta Network - Hub Central
PythonAnywhere - Version production
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from datetime import datetime
import json
import os

app = Flask(__name__)
CORS(app)

# ============================================
# CONFIGURATION
# ============================================

BOOTSTRAP_RELAYS = [
    {
        "id": "relay-01",
        "name": "Relais Principal",
        "multiaddr": "/ip4/65.75.201.11/tcp/4001/ws",
        "endpoint": "ws://65.75.201.11:4001",
        "type": "websocket",
        "region": "eu-west",
        "latency": 45,
        "status": "online",
        "is_verified": True,
        "is_bootstrap": True
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
        "is_verified": True,
        "is_bootstrap": True
    }
]

# Stockage temporaire (en production: utiliser une DB)
PENDING_RELAYS = []
ACTIVE_RELAYS = {r['id']: r for r in BOOTSTRAP_RELAYS}

# ============================================
# ROUTES PRINCIPALES
# ============================================

@app.route('/')
def index():
    """Page d'accueil"""
    return render_template('index.html')

@app.route('/api/v1/network/relays')
def get_relays():
    """Liste des relais actifs"""
    relays = list(ACTIVE_RELAYS.values())
    return jsonify({
        'relays': relays,
        'total': len(relays),
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/v1/relays/notify', methods=['POST'])
def notify_relay():
    """Notification d'installation d'un nouveau relais"""
    try:
        data = request.get_json()
        ip = data.get('relay_ip')
        
        # Ajouter aux relais en attente
        pending = {
            'id': f"pending-{len(PENDING_RELAYS)+1}",
            'ip': ip,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        PENDING_RELAYS.append(pending)
        
        print(f"📡 Nouveau relais installé: {ip}")
        
        return jsonify({
            'success': True,
            'message': 'Notification reçue',
            'next_steps': [
                'Votre relais sera approuvé sous 24h',
                'Consultez votre email pour confirmation',
                'Merci de contribuer au réseau!'
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/relays/register', methods=['POST'])
def register_relay():
    """Enregistrement officiel d'un relais"""
    try:
        data = request.get_json()
        relay_id = data.get('id', f"relay-{len(ACTIVE_RELAYS)+1}")
        
        ACTIVE_RELAYS[relay_id] = {
            **data,
            'status': 'online',
            'is_verified': True,
            'registered_at': datetime.utcnow().isoformat()
        }
        
        return jsonify({
            'success': True,
            'relay_id': relay_id,
            'message': 'Relais enregistré avec succès'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/relays/health', methods=['POST'])
def relay_health():
    """Heartbeat des relais"""
    try:
        data = request.get_json()
        relay_id = data.get('relay_id')
        
        if relay_id in ACTIVE_RELAYS:
            ACTIVE_RELAYS[relay_id]['last_seen'] = datetime.utcnow().isoformat()
            ACTIVE_RELAYS[relay_id]['connected_users'] = data.get('connected_users', 0)
            ACTIVE_RELAYS[relay_id]['status'] = 'online'
            
        return jsonify({'success': True})
        
    except Exception:
        return jsonify({'success': False}), 500

@app.route('/admin/pending')
def pending_relays():
    """Page admin - relais en attente"""
    return jsonify({
        'pending': PENDING_RELAYS,
        'total': len(PENDING_RELAYS)
    })

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'zeta-central-hub',
        'relays': len(ACTIVE_RELAYS),
        'timestamp': datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)