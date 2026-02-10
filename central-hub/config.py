import os
from datetime import datetime

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///network.db')
    
    # Relais de base pour le bootstrap
    BOOTSTRAP_RELAYS = [
        {
            "id": "zeta-relay-01",
            "name": "Primary Relay EU",
            "multiaddr": "/ip4/65.75.201.11/tcp/4001/ws/p2p/12D3KooWPrimaryRelayKey",
            "endpoint": "wss://65.75.201.11:4001",
            "type": "websocket",
            "region": "eu-west",
            "latency": 45,
            "capacity": 1000,
            "status": "online",
            "last_seen": datetime.utcnow().isoformat()
        },
        {
            "id": "zeta-relay-02", 
            "name": "Secondary Relay US",
            "multiaddr": "/ip4/65.75.200.180/tcp/4001/ws/p2p/12D3KooWSecondaryRelayKey",
            "endpoint": "wss://65.75.200.180:4001",
            "type": "webrtc",
            "region": "us-east",
            "latency": 120,
            "capacity": 500,
            "status": "online",
            "last_seen": datetime.utcnow().isoformat()
        }
    ]
    
    # Paramètres réseau
    MAX_RELAYS_PER_USER = 10
    RELAY_HEALTH_CHECK_INTERVAL = 300  # secondes
    USER_SESSION_TIMEOUT = 3600  # secondes
    
    # API Keys pour les relais vérifiés
    RELAY_API_KEYS = os.environ.get('RELAY_API_KEYS', '').split(',')