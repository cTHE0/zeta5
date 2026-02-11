#!/usr/bin/env python3
"""
Zeta Network Relay – Serveur WebSocket simple
Écoute les connexions, relaie les messages entre pairs.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
import yaml
import websockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('zeta-relay')

class Relay:
    def __init__(self, config_path='config.yaml'):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        self.host = cfg['network']['listen_address']
        self.port = cfg['network']['listen_port']
        self.public_ip = cfg['network'].get('public_ip', 'unknown')
        self.domain = cfg['network'].get('domain', self.public_ip)
        self.clients = set()
        self.node_id = f"relay-{self.public_ip}"

    async def handler(self, websocket, path):
        """Gère une connexion client."""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.clients.add(websocket)
        logger.info(f"👤 Client connecté {client_id} – total {len(self.clients)}")

        try:
            # Message de bienvenue
            await websocket.send(json.dumps({
                'type': 'welcome',
                'relay_id': self.node_id,
                'timestamp': datetime.utcnow().isoformat(),
                'peers': len(self.clients)
            }))

            # Boucle de réception
            async for msg in websocket:
                data = json.loads(msg)
                if data.get('type') == 'ping':
                    await websocket.send(json.dumps({'type': 'pong'}))
                elif data.get('type') == 'publish':
                    # Relayer à tous les autres clients
                    for client in self.clients:
                        if client != websocket:
                            try:
                                await client.send(msg)
                            except:
                                pass
                    # Accusé de réception
                    await websocket.send(json.dumps({
                        'type': 'ack',
                        'status': 'relayed'
                    }))
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"👤 Client déconnecté {client_id}")
        finally:
            self.clients.discard(websocket)

    async def run(self):
        logger.info(f"🚀 Démarrage du relais {self.node_id} sur {self.host}:{self.port}")
        async with websockets.serve(self.handler, self.host, self.port,
                                    ping_interval=20, ping_timeout=60):
            logger.info(f"✅ Relais prêt – ws://{self.public_ip}:{self.port}")
            if self.domain != self.public_ip:
                logger.info(f"   Domaine sécurisé : wss://{self.domain}")
            await asyncio.Future()  # tourne indéfiniment

if __name__ == '__main__':
    asyncio.run(Relay().run())