from flask import Flask, render_template, jsonify, request, make_response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
import hashlib
import json
import redis
import logging
from config import Config

# Configuration
app = Flask(__name__)
app.config.from_object(Config)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Base de données
db = SQLAlchemy(app)
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modèles
class Relay(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128))
    multiaddr = db.Column(db.String(512), unique=True, nullable=False)
    endpoint = db.Column(db.String(256))
    relay_type = db.Column(db.String(32))
    region = db.Column(db.String(64))
    latency = db.Column(db.Integer, default=999)
    capacity = db.Column(db.Integer, default=100)
    connected_users = db.Column(db.Integer, default=0)
    status = db.Column(db.String(32), default='unknown')
    is_verified = db.Column(db.Boolean, default=False)
    is_bootstrap = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "multiaddr": self.multiaddr,
            "endpoint": self.endpoint,
            "type": self.relay_type,
            "region": self.region,
            "latency": self.latency,
            "capacity": self.capacity,
            "connected_users": self.connected_users,
            "status": self.status,
            "is_verified": self.is_verified,
            "is_bootstrap": self.is_bootstrap,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None
        }

class UserSession(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    peer_id = db.Column(db.String(128), unique=True)
    user_agent = db.Column(db.String(512))
    ip_address = db.Column(db.String(64))
    connected_relays = db.Column(db.Text)  # JSON list
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Routes principales
@app.route('/')
def index():
    """Page principale - Interface utilisateur"""
    return render_template('index.html')

@app.route('/api/v1/network/relays')
@limiter.limit("30 per minute")
def get_relays():
    """Obtenir la liste des relais disponibles"""
    try:
        # Essayer le cache Redis d'abord
        cached = redis_client.get('relays:latest')
        if cached:
            return jsonify(json.loads(cached))
        
        # Récupérer depuis la base de données
        relays = Relay.query.filter_by(status='online').order_by(
            Relay.latency, Relay.connected_users
        ).limit(50).all()
        
        # Ajouter les relais bootstrap s'ils ne sont pas déjà là
        bootstrap_ids = {r['id'] for r in Config.BOOTSTRAP_RELAYS}
        existing_ids = {r.id for r in relays}
        
        for bootstrap in Config.BOOTSTRAP_RELAYS:
            if bootstrap['id'] not in existing_ids:
                # Créer un objet relay factice pour les bootstrap manquants
                relay_data = bootstrap
                relays.append(type('obj', (object,), {'to_dict': lambda: relay_data})())
        
        # Ordonner: bootstrap d'abord, puis par latence
        sorted_relays = sorted(
            [r.to_dict() for r in relays],
            key=lambda x: (not x.get('is_bootstrap', False), x['latency'])
        )
        
        response = {
            "relays": sorted_relays[:Config.MAX_RELAYS_PER_USER],
            "network_status": "active",
            "total_relays": len(relays),
            "online_relays": len([r for r in relays if r.to_dict().get('status') == 'online']),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Mettre en cache pour 30 secondes
        redis_client.setex('relays:latest', 30, json.dumps(response))
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting relays: {e}")
        # Fallback aux relais bootstrap
        return jsonify({
            "relays": Config.BOOTSTRAP_RELAYS,
            "network_status": "degraded",
            "timestamp": datetime.utcnow().isoformat()
        })

@app.route('/api/v1/relays/register', methods=['POST'])
@limiter.limit("10 per hour")
def register_relay():
    """API pour qu'un nouveau relais s'enregistre"""
    try:
        data = request.get_json()
        
        # Validation
        required = ['name', 'multiaddr', 'endpoint', 'type', 'region']
        if not all(k in data for k in required):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Vérifier l'API key pour les relais vérifiés
        api_key = request.headers.get('X-API-Key')
        is_verified = api_key in Config.RELAY_API_KEYS if api_key else False
        
        # Générer un ID unique
        relay_id = hashlib.sha256(data['multiaddr'].encode()).hexdigest()[:16]
        
        # Vérifier si le relais existe déjà
        existing = Relay.query.filter_by(multiaddr=data['multiaddr']).first()
        
        if existing:
            # Mettre à jour
            existing.name = data['name']
            existing.endpoint = data['endpoint']
            existing.relay_type = data['type']
            existing.region = data['region']
            existing.status = 'online'
            existing.last_seen = datetime.utcnow()
            if is_verified and not existing.is_verified:
                existing.is_verified = is_verified
        else:
            # Créer nouveau
            relay = Relay(
                id=relay_id,
                name=data['name'],
                multiaddr=data['multiaddr'],
                endpoint=data['endpoint'],
                relay_type=data['type'],
                region=data['region'],
                status='online',
                is_verified=is_verified,
                is_bootstrap=False
            )
            db.session.add(relay)
        
        db.session.commit()
        
        # Invalider le cache
        redis_client.delete('relays:latest')
        
        return jsonify({
            "success": True,
            "relay_id": relay_id,
            "message": "Relay registered successfully"
        })
        
    except Exception as e:
        logger.error(f"Error registering relay: {e}")
        return jsonify({"error": "Registration failed"}), 500

@app.route('/api/v1/relays/health', methods=['POST'])
@limiter.limit("60 per minute")
def relay_health():
    """Endpoint de santé pour les relais"""
    try:
        data = request.get_json()
        relay_id = data.get('relay_id')
        
        if not relay_id:
            return jsonify({"error": "Missing relay_id"}), 400
        
        relay = Relay.query.get(relay_id)
        if relay:
            relay.status = 'online'
            relay.connected_users = data.get('connected_users', relay.connected_users)
            relay.latency = data.get('latency', relay.latency)
            relay.last_seen = datetime.utcnow()
            db.session.commit()
        
        return jsonify({"success": True})
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({"success": False}), 500

@app.route('/api/v1/network/stats')
def network_stats():
    """Statistiques du réseau"""
    try:
        total_relays = Relay.query.count()
        online_relays = Relay.query.filter_by(status='online').count()
        verified_relays = Relay.query.filter_by(is_verified=True, status='online').count()
        
        # Sessions actives (dans les dernières 5 minutes)
        active_since = datetime.utcnow() - timedelta(minutes=5)
        active_sessions = UserSession.query.filter(
            UserSession.last_active >= active_since
        ).count()
        
        return jsonify({
            "total_relays": total_relays,
            "online_relays": online_relays,
            "verified_relays": verified_relays,
            "active_users": active_sessions,
            "bootstrap_relays": len([r for r in Config.BOOTSTRAP_RELAYS]),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": "Could not retrieve stats"}), 500

@app.route('/api/v1/users/register', methods=['POST'])
def register_user():
    """Enregistrer une session utilisateur"""
    try:
        data = request.get_json()
        peer_id = data.get('peer_id')
        
        if not peer_id:
            return jsonify({"error": "Missing peer_id"}), 400
        
        # Générer un ID de session
        session_id = hashlib.sha256(f"{peer_id}{datetime.utcnow().timestamp()}".encode()).hexdigest()[:16]
        
        session = UserSession(
            id=session_id,
            peer_id=peer_id,
            user_agent=request.user_agent.string[:512],
            ip_address=request.remote_addr,
            connected_relays=json.dumps(data.get('connected_relays', [])),
            last_active=datetime.utcnow()
        )
        
        db.session.add(session)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "message": "Session registered"
        })
        
    except Exception as e:
        logger.error(f"User registration error: {e}")
        return jsonify({"success": False}), 500

@app.route('/docs')
def documentation():
    """Documentation de l'API"""
    return render_template('docs.html')

# Initialisation
with app.app_context():
    db.create_all()
    
    # S'assurer que les relais bootstrap existent dans la base
    for relay_data in Config.BOOTSTRAP_RELAYS:
        if not Relay.query.filter_by(id=relay_data['id']).first():
            relay = Relay(
                id=relay_data['id'],
                name=relay_data['name'],
                multiaddr=relay_data['multiaddr'],
                endpoint=relay_data['endpoint'],
                relay_type=relay_data['type'],
                region=relay_data['region'],
                latency=relay_data.get('latency', 999),
                capacity=relay_data.get('capacity', 100),
                status=relay_data.get('status', 'online'),
                is_verified=True,
                is_bootstrap=True
            )
            db.session.add(relay)
    
    db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)