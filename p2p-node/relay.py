#!/usr/bin/env python3
"""
Zeta Network Relay - Version production
Repo: https://github.com/cTHE0/zeta5
"""

import asyncio
import json
import logging
import os
import signal
import sys
import yaml
from datetime import datetime
from typing import Set, Dict, Any, Optional
import websockets

# ============================================
# CONFIGURATION
# ============================================

class Config:
    """Gestionnaire de configuration"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.data = self.load()
    
    def load(self) -> Dict[str, Any]:
        """Charger la configuration depuis le fichier YAML"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return self.create_default()
        except Exception as e:
            logging.error(f"Erreur chargement config: {e}")
            return self.create_default()
    
    def create_default(self) -> Dict[str, Any]:
        """Créer une configuration par défaut"""
        return {
            'network': {
                'listen_address': '0.0.0.0',
                'listen_port': 4001,
                'public_ip': 'unknown',
                'max_connections': 1000,
                'heartbeat_interval': 30
            },
            'gossip': {
                'topics': ['zeta-network-global'],
                'message_cache_size': 5000,
                'heartbeat_interval': 1,
                'max_message_size': 1048576
            },
            'bootstrap': {
                'central_hub': 'https://zetanetwork.org',
                'min_connections': 1,
                'max_connections': 10
            },
            'logging': {
                'level': 'INFO',
                'file': '/home/zetanode/zeta-relay.log'
            },
            'relay': {
                'name': 'Zeta-Relay',
                'version': '2.0.0',
                'install_date': datetime.now().isoformat()
            }
        }
    
    @property
    def network(self) -> Dict[str, Any]:
        return self.data.get('network', {})
    
    @property
    def gossip(self) -> Dict[str, Any]:
        return self.data.get('gossip', {})
    
    @property
    def bootstrap(self) -> Dict[str, Any]:
        return self.data.get('bootstrap', {})
    
    @property
    def logging(self) -> Dict[str, Any]:
        return self.data.get('logging', {})
    
    @property
    def relay_info(self) -> Dict[str, Any]:
        return self.data.get('relay', {})

# ============================================
# LOGGING
# ============================================

def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """Configurer le logging"""
    level = config.get('level', 'INFO').upper()
    log_file = config.get('file')
    
    handlers = [logging.StreamHandler()]
    if log_file:
        try:
            handlers.append(logging.FileHandler(log_file))
        except:
            pass
    
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    return logging.getLogger('zeta-relay')

# ============================================
# RELAIS PRINCIPAL
# ============================================

class ZetaRelay:
    """Serveur relais P2P pour Zeta Network"""
    
    def __init__(self):
        self.config = Config()
        self.logger = setup_logging(self.config.logging)
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.running = True
        self.start_time = datetime.utcnow()
        self.node_id = self.generate_node_id()
        
        # Statistiques
        self.stats = {
            'messages_received': 0,
            'messages_relayed': 0,
            'clients_total': 0,
            'bytes_transferred': 0,
            'uptime': 0
        }
        
        # Topics
        self.topics = self.config.gossip.get('topics', ['zeta-network-global'])
        self.subscriptions: Dict[str, Set] = {}
        
        # Cache messages
        self.message_cache: Dict[str, Dict] = {}
        self.cache_size = self.config.gossip.get('message_cache_size', 5000)
        
        self.logger.info("=" * 60)
        self.logger.info(f"🚀 Zeta Relay v{self.config.relay_info.get('version', '2.0.0')}")
        self.logger.info(f"📦 GitHub: github.com/cTHE0/zeta5")
        self.logger.info("=" * 60)
    
    def generate_node_id(self) -> str:
        """Générer un ID unique pour ce relais"""
        import hashlib
        import uuid
        seed = f"{self.config.network.get('public_ip', 'unknown')}-{uuid.uuid4()}"
        hash_obj = hashlib.sha256(seed.encode()).hexdigest()
        return f"zeta-relay-{hash_obj[:12]}"
    
    async def start(self):
        """Démarrer le serveur WebSocket"""
        host = self.config.network.get('listen_address', '0.0.0.0')
        port = self.config.network.get('listen_port', 4001)
        
        self.logger.info(f"📡 Démarrage du serveur sur {host}:{port}")
        
        try:
            async def handler(websocket, path):
                """Gestionnaire de connexion client"""
                client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
                self.clients.add(websocket)
                self.stats['clients_total'] = len(self.clients)
                
                self.logger.info(f"👤 Client connecté: {client_id} (total: {len(self.clients)})")
                
                try:
                    # Message de bienvenue
                    welcome = {
                        'type': 'welcome',
                        'relay_id': self.node_id,
                        'relay_ip': self.config.network.get('public_ip', 'unknown'),
                        'timestamp': datetime.utcnow().isoformat(),
                        'topics': self.topics,
                        'message': 'Bienvenue sur Zeta Network!',
                        'version': self.config.relay_info.get('version', '2.0.0')
                    }
                    await websocket.send(json.dumps(welcome))
                    
                    # Boucle de réception des messages
                    async for message in websocket:
                        self.stats['bytes_transferred'] += len(message)
                        await self.handle_message(message, websocket, client_id)
                        
                except websockets.exceptions.ConnectionClosed:
                    self.logger.info(f"👤 Client déconnecté: {client_id}")
                except Exception as e:
                    self.logger.error(f"❌ Erreur client {client_id}: {e}")
                finally:
                    self.clients.discard(websocket)
                    self.stats['clients_total'] = len(self.clients)
            
            # Démarrer le serveur
            server = await websockets.serve(
                handler,
                host,
                port,
                ping_interval=20,
                ping_timeout=40,
                max_size=self.config.gossip.get('max_message_size', 1048576)
            )
            
            self.logger.info(f"✅ Relais opérationnel sur ws://{self.config.network.get('public_ip', host)}:{port}")
            self.logger.info(f"🆔 Node ID: {self.node_id}")
            
            # Boucle principale
            await self.main_loop(server)
            
        except Exception as e:
            self.logger.error(f"❌ Erreur fatale: {e}", exc_info=True)
            raise
    
    async def main_loop(self, server):
        """Boucle principale avec statistiques périodiques"""
        try:
            while self.running:
                await asyncio.sleep(1)
                self.stats['uptime'] = (datetime.utcnow() - self.start_time).total_seconds()
                
                # Log toutes les 5 minutes
                if int(self.stats['uptime']) % 300 == 0:
                    self.logger.info(
                        f"📊 Stats | Clients: {len(self.clients)} | "
                        f"Messages: {self.stats['messages_received']} | "
                        f"Uptime: {self.stats['uptime']:.0f}s"
                    )
        except asyncio.CancelledError:
            self.logger.info("🛑 Arrêt demandé...")
        finally:
            server.close()
            await server.wait_closed()
            self.logger.info("👋 Relais arrêté")
    
    async def handle_message(self, message: str, websocket, client_id: str):
        """Traiter un message reçu d'un client"""
        try:
            data = json.loads(message)
            msg_type = data.get('type', 'unknown')
            
            self.stats['messages_received'] += 1
            
            if msg_type == 'ping':
                await self.handle_ping(websocket)
            elif msg_type == 'publish':
                await self.handle_publish(data, websocket, client_id)
            elif msg_type == 'subscribe':
                await self.handle_subscribe(data, websocket)
            elif msg_type == 'health':
                await self.handle_health(websocket)
            elif msg_type == 'stats':
                await self.handle_stats(websocket)
            else:
                self.logger.debug(f"Message inconnu: {msg_type}")
                
        except json.JSONDecodeError:
            self.logger.warning(f"❌ Message JSON invalide de {client_id}")
        except Exception as e:
            self.logger.error(f"❌ Erreur traitement message: {e}")
    
    async def handle_ping(self, websocket):
        """Répondre au ping"""
        await websocket.send(json.dumps({
            'type': 'pong',
            'timestamp': datetime.utcnow().isoformat()
        }))
    
    async def handle_publish(self, data: Dict, websocket, client_id: str):
        """Publier un message"""
        message_id = data.get('id', f"msg-{datetime.utcnow().timestamp()}")
        
        self.stats['messages_relayed'] += 1
        
        # Accusé de réception
        await websocket.send(json.dumps({
            'type': 'ack',
            'message_id': message_id,
            'status': 'received',
            'timestamp': datetime.utcnow().isoformat(),
            'relay_id': self.node_id
        }))
        
        self.logger.debug(f"📤 Message publié: {message_id[:16]}...")
    
    async def handle_subscribe(self, data: Dict, websocket):
        """S'abonner à des topics"""
        topics = data.get('topics', [])
        if topics:
            self.logger.info(f"📝 Abonnement à: {topics}")
            await websocket.send(json.dumps({
                'type': 'subscribed',
                'topics': topics,
                'timestamp': datetime.utcnow().isoformat()
            }))
    
    async def handle_health(self, websocket):
        """Retourner l'état de santé"""
        await websocket.send(json.dumps({
            'type': 'health_response',
            'status': 'healthy',
            'clients': len(self.clients),
            'uptime': self.stats['uptime'],
            'version': self.config.relay_info.get('version', '2.0.0'),
            'timestamp': datetime.utcnow().isoformat()
        }))
    
    async def handle_stats(self, websocket):
        """Retourner les statistiques"""
        await websocket.send(json.dumps({
            'type': 'stats_response',
            'stats': {
                **self.stats,
                'clients_connected': len(self.clients)
            },
            'relay': {
                'id': self.node_id,
                'ip': self.config.network.get('public_ip', 'unknown'),
                'port': self.config.network.get('listen_port', 4001),
                'version': self.config.relay_info.get('version', '2.0.0')
            },
            'timestamp': datetime.utcnow().isoformat()
        }))

# ============================================
# POINT D'ENTRÉE
# ============================================

async def main():
    """Fonction principale"""
    relay = ZetaRelay()
    
    # Gestion des signaux
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(relay)))
    
    try:
        await relay.start()
    except KeyboardInterrupt:
        relay.logger.info("Interruption clavier")
    except Exception as e:
        relay.logger.error(f"Erreur fatale: {e}")
        return 1
    return 0

async def shutdown(relay: ZetaRelay):
    """Arrêt propre"""
    relay.running = False
    relay.logger.info("🛑 Arrêt en cours...")

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))