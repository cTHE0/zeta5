#!/usr/bin/env python3
"""
Zeta Network Relay - Version simplifiée et stable
"""

import asyncio
import json
import logging
import yaml
import websockets
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('zeta-relay')

class ZetaRelay:
    def __init__(self, config_path='config.yaml'):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        self.node_id = f"relay-{self.config['network']['public_ip']}"
        self.clients = set()
        
    async def handle_client(self, websocket, path):
        """Gérer les connexions WebSocket"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.clients.add(websocket)
        
        logger.info(f"👤 Client connecté: {client_id} (total: {len(self.clients)})")
        
        try:
            # Message de bienvenue
            await websocket.send(json.dumps({
                'type': 'welcome',
                'relay_id': self.node_id,
                'timestamp': datetime.utcnow().isoformat(),
                'peers': len(self.clients)
            }))
            
            # Gérer les messages
            async for message in websocket:
                data = json.loads(message)
                
                if data.get('type') == 'ping':
                    await websocket.send(json.dumps({'type': 'pong'}))
                elif data.get('type') == 'publish':
                    # Relayer à tous les autres clients
                    for client in self.clients:
                        if client != websocket:
                            try:
                                await client.send(message)
                            except:
                                pass
                    
                    await websocket.send(json.dumps({
                        'type': 'ack',
                        'status': 'relayed'
                    }))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"👤 Client déconnecté: {client_id}")
        finally:
            self.clients.discard(websocket)
    
    async def start(self):
        """Démarrer le serveur"""
        host = self.config['network']['listen_address']
        port = self.config['network']['listen_port']
        ip = self.config['network']['public_ip']
        
        logger.info(f"🚀 Démarrage du relais sur {ip}:{port}")
        
        async with websockets.serve(
            self.handle_client,
            host,
            port,
            ping_interval=20,
            ping_timeout=60
        ):
            logger.info(f"✅ Relais prêt: ws://{ip}:{port}")
            await asyncio.Future()  # Run forever

async def main():
    relay = ZetaRelay()
    await relay.start()

if __name__ == '__main__':
    asyncio.run(main())