#!/usr/bin/env python3
"""
Zeta Network P2P Node
Nœud relais pour le réseau social décentralisé
"""

import asyncio
import json
import logging
import signal
import sys
from datetime import datetime
from typing import Dict, List, Set, Optional
import aiohttp
import yaml
from dataclasses import dataclass, asdict
from enum import Enum

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('zeta-node.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("zeta-p2p-node")

# Types
class NodeStatus(Enum):
    STARTING = "starting"
    CONNECTING = "connecting"
    READY = "ready"
    SYNCING = "syncing"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"

@dataclass
class NetworkConfig:
    """Configuration réseau"""
    listen_address: str = "0.0.0.0"
    listen_port: int = 4001
    public_ip: Optional[str] = None
    max_connections: int = 1000
    connection_timeout: int = 30
    heartbeat_interval: int = 30
    reconnect_attempts: int = 5
    reconnect_delay: int = 5
    
    @classmethod
    def from_yaml(cls, path: str):
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data.get('network', {}))

@dataclass
class GossipConfig:
    """Configuration Gossipsub"""
    topics: List[str] = None
    message_cache_size: int = 1000
    heartbeat_interval: int = 1
    fanout_ttl: int = 60
    max_message_size: int = 1024 * 1024  # 1MB
    validate_messages: bool = True
    
    def __post_init__(self):
        if self.topics is None:
            self.topics = ["zeta-network-global", "zeta-system-announcements"]

@dataclass
class BootstrapConfig:
    """Configuration bootstrap"""
    central_hub: str = "https://zetanetwork.org"
    bootstrap_relays: List[str] = None
    min_connections: int = 3
    max_connections: int = 10
    
    def __post_init__(self):
        if self.bootstrap_relays is None:
            self.bootstrap_relays = [
                "/ip4/65.75.201.11/tcp/4001/ws/p2p/12D3KooWPrimaryRelayKey",
                "/ip4/65.75.200.180/tcp/4001/ws/p2p/12D3KooWSecondaryRelayKey"
            ]

class ZetaP2PNode:
    """Nœud P2P principal"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.status = NodeStatus.STARTING
        self.node_id: Optional[str] = None
        self.peer_id: Optional[str] = None
        self.start_time = datetime.utcnow()
        
        # Configuration
        self.network_config: Optional[NetworkConfig] = None
        self.gossip_config: Optional[GossipConfig] = None
        self.bootstrap_config: Optional[BootstrapConfig] = None
        
        # État du réseau
        self.connected_peers: Set[str] = set()
        self.pending_messages: List[Dict] = []
        self.message_cache: Dict[str, Dict] = {}
        self.topics_subscribed: Set[str] = set()
        
        # Services
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.tasks: Set[asyncio.Task] = set()
        
        # Statistiques
        self.stats = {
            "messages_received": 0,
            "messages_relayed": 0,
            "peers_connected": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "uptime": 0
        }
        
        # Gestion des signaux
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    async def initialize(self):
        """Initialiser le nœud"""
        logger.info("🚀 Initialisation du nœud P2P Zeta Network")
        
        try:
            # Charger la configuration
            await self.load_configuration()
            
            # Générer les identifiants
            await self.generate_identities()
            
            # Initialiser les services HTTP
            self.http_session = aiohttp.ClientSession()
            
            # S'enregistrer auprès du hub central
            await self.register_with_hub()
            
            # Démarrer les services
            await self.start_services()
            
            # Se connecter au réseau
            await self.connect_to_network()
            
            self.status = NodeStatus.READY
            logger.info(f"✅ Nœud prêt. ID: {self.node_id}")
            
        except Exception as e:
            logger.error(f"❌ Erreur d'initialisation: {e}")
            self.status = NodeStatus.ERROR
            raise
    
    async def load_configuration(self):
        """Charger la configuration depuis YAML"""
        try:
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            self.network_config = NetworkConfig(**config_data.get('network', {}))
            self.gossip_config = GossipConfig(**config_data.get('gossip', {}))
            self.bootstrap_config = BootstrapConfig(**config_data.get('bootstrap', {}))
            
            logger.info("📋 Configuration chargée")
            
        except FileNotFoundError:
            logger.warning("Fichier config non trouvé, utilisation des valeurs par défaut")
            self.network_config = NetworkConfig()
            self.gossip_config = GossipConfig()
            self.bootstrap_config = BootstrapConfig()
    
    async def generate_identities(self):
        """Générer les identifiants du nœud"""
        # En production, utiliser libp2p pour générer les clés
        import hashlib
        import uuid
        
        node_uuid = str(uuid.uuid4())
        self.node_id = hashlib.sha256(node_uuid.encode()).hexdigest()[:16]
        self.peer_id = f"12D3KooW{self.node_id}"
        
        logger.info(f"🆔 Node ID généré: {self.node_id}")
        logger.info(f"🆔 Peer ID: {self.peer_id}")
    
    async def register_with_hub(self):
        """S'enregistrer auprès du hub central"""
        if not self.bootstrap_config:
            return
        
        try:
            registration_data = {
                "name": f"Zeta-Relay-{self.node_id}",
                "multiaddr": f"/ip4/{self.network_config.public_ip or '0.0.0.0'}/tcp/{self.network_config.listen_port}/ws/p2p/{self.peer_id}",
                "endpoint": f"wss://{self.network_config.public_ip or '0.0.0.0'}:{self.network_config.listen_port}",
                "type": "websocket",
                "region": "auto",
                "node_id": self.node_id,
                "version": "1.0.0"
            }
            
            async with self.http_session.post(
                f"{self.bootstrap_config.central_hub}/api/v1/relays/register",
                json=registration_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Enregistré auprès du hub central: {data.get('relay_id')}")
                else:
                    logger.warning(f"⚠️ Échec enregistrement hub: {response.status}")
        
        except Exception as e:
            logger.warning(f"⚠️ Impossible de s'enregistrer: {e}")
    
    async def start_services(self):
        """Démarrer les services en arrière-plan"""
        # Service de santé
        health_task = asyncio.create_task(self.health_service())
        self.tasks.add(health_task)
        health_task.add_done_callback(self.tasks.discard)
        
        # Service de statistiques
        stats_task = asyncio.create_task(self.stats_service())
        self.tasks.add(stats_task)
        stats_task.add_done_callback(self.tasks.discard)
        
        # Service de gossiping simulé
        gossip_task = asyncio.create_task(self.gossip_service())
        self.tasks.add(gossip_task)
        gossip_task.add_done_callback(self.tasks.discard)
        
        logger.info("🔄 Services démarrés")
    
    async def connect_to_network(self):
        """Se connecter au réseau P2P"""
        self.status = NodeStatus.CONNECTING
        
        if not self.bootstrap_config or not self.bootstrap_config.bootstrap_relays:
            logger.warning("⚠️ Aucun relais bootstrap configuré")
            return
        
        logger.info(f"🌐 Connexion au réseau via {len(self.bootstrap_config.bootstrap_relays)} relais")
        
        successful_connections = 0
        
        for relay_addr in self.bootstrap_config.bootstrap_relays:
            if successful_connections >= self.bootstrap_config.max_connections:
                break
            
            try:
                # Simulation de connexion
                # En production: utiliser libp2p pour se connecter
                await asyncio.sleep(0.5)
                
                logger.info(f"  → Connecté à: {relay_addr[:50]}...")
                self.connected_peers.add(relay_addr)
                successful_connections += 1
                
            except Exception as e:
                logger.warning(f"  ❌ Échec connexion {relay_addr[:30]}: {e}")
                continue
        
        if successful_connections >= self.bootstrap_config.min_connections:
            self.status = NodeStatus.READY
            logger.info(f"✅ Connecté à {successful_connections} relais")
        else:
            self.status = NodeStatus.ERROR
            logger.error(f"❌ Connexions insuffisantes: {successful_connections}/{self.bootstrap_config.min_connections}")
    
    async def health_service(self):
        """Service de santé périodique"""
        while self.status != NodeStatus.SHUTTING_DOWN:
            try:
                # Envoyer un heartbeat au hub central
                await self.send_heartbeat()
                
                # Vérifier les connexions
                await self.check_connections()
                
            except Exception as e:
                logger.error(f"Erreur service santé: {e}")
            
            await asyncio.sleep(self.network_config.heartbeat_interval)
    
    async def send_heartbeat(self):
        """Envoyer un heartbeat au hub central"""
        if not self.http_session or not self.bootstrap_config:
            return
        
        try:
            health_data = {
                "relay_id": self.node_id,
                "status": self.status.value,
                "connected_users": len(self.connected_peers),
                "latency": 50,  # À mesurer réellement
                "topics": list(self.topics_subscribed),
                "messages_cached": len(self.message_cache),
                "peers_connected": len(self.connected_peers)
            }
            
            async with self.http_session.post(
                f"{self.bootstrap_config.central_hub}/api/v1/relays/health",
                json=health_data,
                timeout=aiohttp.ClientTimeout(total=5)
            ):
                pass  # Ignorer la réponse
            
        except Exception as e:
            logger.debug(f"Heartbeat échoué: {e}")
    
    async def check_connections(self):
        """Vérifier l'état des connexions"""
        current_connections = len(self.connected_peers)
        
        if current_connections < self.bootstrap_config.min_connections:
            logger.warning(f"⚠️ Connexions faibles: {current_connections}")
            
            # Tentative de reconnexion
            if self.status == NodeStatus.READY:
                await self.connect_to_network()
    
    async def stats_service(self):
        """Service de collecte de statistiques"""
        while self.status != NodeStatus.SHUTTING_DOWN:
            self.stats["uptime"] = (datetime.utcnow() - self.start_time).total_seconds()
            self.stats["peers_connected"] = len(self.connected_peers)
            
            # Log périodique
            if int(self.stats["uptime"]) % 300 == 0:  # Toutes les 5 minutes
                logger.info(
                    f"📊 Stats: {self.stats['peers_connected']} peers, "
                    f"{self.stats['messages_received']} msgs, "
                    f"{self.stats['uptime']:.0f}s uptime"
                )
            
            await asyncio.sleep(10)
    
    async def gossip_service(self):
        """Service de gossiping simulé"""
        while self.status != NodeStatus.SHUTTING_DOWN:
            try:
                # Simuler la réception de messages
                if self.connected_peers and len(self.pending_messages) < 100:
                    # Générer un message simulé
                    message = {
                        "id": f"msg-{datetime.utcnow().timestamp()}-{len(self.message_cache)}",
                        "type": "simulated",
                        "content": f"Message test du relay {self.node_id}",
                        "timestamp": datetime.utcnow().isoformat(),
                        "topic": "zeta-network-global",
                        "author": f"relay-{self.node_id}",
                        "hops": 0
                    }
                    
                    # Ajouter au cache
                    self.message_cache[message["id"]] = message
                    self.stats["messages_received"] += 1
                    
                    # Limiter la taille du cache
                    if len(self.message_cache) > self.gossip_config.message_cache_size:
                        # Supprimer les plus anciens
                        oldest_keys = sorted(self.message_cache.keys())[:100]
                        for key in oldest_keys:
                            del self.message_cache[key]
                
                # Traiter les messages en attente
                await self.process_pending_messages()
                
            except Exception as e:
                logger.error(f"Erreur gossip service: {e}")
            
            await asyncio.sleep(self.gossip_config.heartbeat_interval)
    
    async def process_pending_messages(self):
        """Traiter les messages en attente"""
        if not self.pending_messages:
            return
        
        # Traiter par lots de 10
        batch = self.pending_messages[:10]
        self.pending_messages = self.pending_messages[10:]
        
        for message in batch:
            try:
                # Simuler la propagation
                self.stats["messages_relayed"] += 1
                
                # Stocker dans le cache
                if message.get("id"):
                    self.message_cache[message["id"]] = message
                
            except Exception as e:
                logger.error(f"Erreur traitement message: {e}")
    
    async def handle_incoming_message(self, message: Dict):
        """Traiter un message entrant"""
        try:
            message_id = message.get("id")
            
            if not message_id:
                logger.warning("Message sans ID reçu")
                return
            
            # Vérifier les doublons
            if message_id in self.message_cache:
                return
            
            # Valider le message
            if self.gossip_config.validate_messages:
                if not self.validate_message(message):
                    logger.warning(f"Message invalide: {message_id}")
                    return
            
            # Ajouter au cache
            self.message_cache[message_id] = message
            self.stats["messages_received"] += 1
            
            # Ajouter à la file de traitement
            self.pending_messages.append(message)
            
            logger.debug(f"📨 Message reçu: {message_id}")
            
        except Exception as e:
            logger.error(f"Erreur traitement message entrant: {e}")
    
    def validate_message(self, message: Dict) -> bool:
        """Valider un message"""
        required_fields = ["id", "type", "content", "timestamp", "topic"]
        
        # Vérifier les champs requis
        for field in required_fields:
            if field not in message:
                return False
        
        # Vérifier la taille
        message_size = len(json.dumps(message).encode('utf-8'))
        if message_size > self.gossip_config.max_message_size:
            return False
        
        # Vérifier le timestamp
        try:
            message_time = datetime.fromisoformat(message["timestamp"].replace('Z', '+00:00'))
            now = datetime.utcnow()
            
            # Rejeter les messages trop anciens (> 24h) ou futurs
            time_diff = (now - message_time).total_seconds()
            if abs(time_diff) > 86400:  # 24 heures
                return False
                
        except (ValueError, KeyError):
            return False
        
        return True
    
    async def get_status_report(self) -> Dict:
        """Générer un rapport d'état"""
        return {
            "node_id": self.node_id,
            "peer_id": self.peer_id,
            "status": self.status.value,
            "uptime": self.stats["uptime"],
            "network": {
                "connected_peers": len(self.connected_peers),
                "listen_address": f"{self.network_config.listen_address}:{self.network_config.listen_port}",
                "public_ip": self.network_config.public_ip
            },
            "gossip": {
                "topics_subscribed": list(self.topics_subscribed),
                "messages_cached": len(self.message_cache),
                "pending_messages": len(self.pending_messages)
            },
            "stats": self.stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def signal_handler(self, signum, frame):
        """Gérer les signaux d'arrêt"""
        logger.info(f"Signal {signum} reçu, arrêt en cours...")
        asyncio.create_task(self.shutdown())
    
    async def shutdown(self):
        """Arrêter le nœud proprement"""
        self.status = NodeStatus.SHUTTING_DOWN
        logger.info("🛑 Arrêt du nœud P2P")
        
        # Annuler les tâches
        for task in self.tasks:
            task.cancel()
        
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Fermer la session HTTP
        if self.http_session:
            await self.http_session.close()
        
        logger.info("👋 Nœud arrêté")
        sys.exit(0)

async def main():
    """Point d'entrée principal"""
    node = ZetaP2PNode()
    
    try:
        await node.initialize()
        
        # Garder le programme actif
        while node.status not in [NodeStatus.ERROR, NodeStatus.SHUTTING_DOWN]:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Interruption clavier")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
    finally:
        await node.shutdown()

if __name__ == "__main__":
    asyncio.run(main())