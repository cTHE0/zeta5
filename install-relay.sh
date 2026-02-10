#!/bin/bash
# install-relay.sh - Installation en 1 clic pour Zeta Network
# Usage: curl -sSL https://raw.githubusercontent.com/zetanetwork/relay/main/install-relay.sh | sudo bash

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[ZETA]${NC} $1"; }
success() { echo -e "${GREEN}✅${NC} $1"; }
warn() { echo -e "${YELLOW}⚠️${NC} $1"; }
error() { echo -e "${RED}❌${NC} $1"; }

# ============================================
# ÉCRAN DE BIENVENUE
# ============================================

clear
echo ""
echo "╔═══════════════════════════════════════╗"
echo "║      🌐 ZETA NETWORK RELAY           ║"
echo "║      Installation Automatique        ║"
echo "╚═══════════════════════════════════════╝"
echo ""
echo "Ce script va installer un relais P2P pour"
echo "le réseau social décentralisé Zeta Network."
echo ""
echo "📡 Votre relais permettra aux utilisateurs"
echo "   de se connecter au réseau via votre VPS."
echo ""
echo "⏳ Installation en cours..."

# ============================================
# VÉRIFICATIONS
# ============================================

# Vérifier root
if [ "$EUID" -ne 0 ]; then
    error "Veuillez exécuter avec: sudo bash"
    echo ""
    echo "Commande complète:"
    echo "  curl -sSL https://zeta.network/install | sudo bash"
    exit 1
fi

# ============================================
# 1. DÉTECTION IP
# ============================================

log "🔍 Détection de votre IP publique..."
PUBLIC_IP=$(curl -s --max-time 5 https://ifconfig.me || \
            curl -s --max-time 5 https://icanhazip.com || \
            echo "NON_DÉTECTÉ")

if [ "$PUBLIC_IP" = "NON_DÉTECTÉ" ]; then
    warn "IP non détectée automatiquement"
    read -p "🌐 Entrez votre IP publique: " PUBLIC_IP
else
    success "IP détectée: $PUBLIC_IP"
fi

# ============================================
# 2. INSTALLATION DES DÉPENDANCES
# ============================================

log "📦 Installation des dépendances..."
apt-get update > /dev/null 2>&1
apt-get install -y \
    python3 python3-venv python3-pip \
    git curl ufw > /dev/null 2>&1
success "Dépendances installées"

# ============================================
# 3. CONFIGURATION PARE-FEU
# ============================================

log "🛡️ Configuration du pare-feu..."
ufw --force enable > /dev/null 2>&1
ufw allow 22/tcp > /dev/null 2>&1
ufw allow 4001/tcp > /dev/null 2>&1
ufw allow 4001/udp > /dev/null 2>&1
success "Pare-feu configuré"

# ============================================
# 4. CRÉATION UTILISATEUR
# ============================================

log "👤 Création de l'utilisateur zetanode..."
if ! id "zetanode" &>/dev/null; then
    useradd -m -s /bin/bash -r zetanode
    success "Utilisateur créé"
else
    warn "Utilisateur existe déjà"
fi

# ============================================
# 5. TÉLÉCHARGEMENT DU CODE
# ============================================

log "📥 Téléchargement du code Zeta Relay..."
cd /home/zetanode

if [ -d "zeta-relay" ]; then
    warn "Dossier existe déjà, mise à jour..."
    cd zeta-relay
    git pull origin main > /dev/null 2>&1 || true
else
    git clone https://github.com/zetanetwork/relay.git zeta-relay > /dev/null 2>&1
    cd zeta-relay
fi

success "Code téléchargé"

# ============================================
# 6. CONFIGURATION
# ============================================

log "⚙️ Configuration du relais..."
cat > config.yaml << EOF
# Zeta Network Relay - Configuration auto-générée
network:
  listen_address: "0.0.0.0"
  listen_port: 4001
  public_ip: "$PUBLIC_IP"
  max_connections: 1000

bootstrap:
  central_hub: "https://zetanetwork.org"

logging:
  level: "INFO"
  file: "/home/zetanode/zeta-relay.log"

relay:
  name: "Relay-$PUBLIC_IP"
  region: "auto"
  contact: ""
EOF

# ============================================
# 7. ENVIRONNEMENT PYTHON
# ============================================

log "🐍 Configuration de l'environnement Python..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
success "Environnement Python prêt"

# ============================================
# 8. SERVICE SYSTEMD
# ============================================

log "⚙️ Configuration du service..."
cat > /etc/systemd/system/zeta-relay.service << EOF
[Unit]
Description=Zeta Network P2P Relay
After=network.target

[Service]
Type=simple
User=zetanode
WorkingDirectory=/home/zetanode/zeta-relay
Environment="PATH=/home/zetanode/zeta-relay/venv/bin"
ExecStart=/home/zetanode/zeta-relay/venv/bin/python relay.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable zeta-relay
systemctl start zeta-relay
sleep 2  # Attendre le démarrage

# ============================================
# 9. AUTO-ENREGISTREMENT
# ============================================

log "📡 Enregistrement auprès du réseau..."
AUTO_REGISTER_URL="https://zetanetwork.org/api/v1/relays/auto-register"

# Créer les données d'enregistrement
cat > /tmp/zeta-register.json << EOF
{
    "relay_ip": "$PUBLIC_IP",
    "status": "ready",
    "version": "1.0.0",
    "timestamp": "$(date -Iseconds)"
}
EOF

# Essayer d'envoyer (silencieusement)
curl -s -X POST \
    -H "Content-Type: application/json" \
    -d @/tmp/zeta-register.json \
    "$AUTO_REGISTER_URL" > /tmp/response.json 2>/dev/null || true

# ============================================
# 10. VÉRIFICATION FINALE
# ============================================

log "🧪 Vérification finale..."

if systemctl is-active --quiet zeta-relay; then
    success "✅ RELAIS OPÉRATIONNEL !"
    
    # ============================================
    # ÉCRAN DE RÉSUMÉ
    # ============================================
    
    echo ""
    echo "╔═══════════════════════════════════════╗"
    echo "║        INSTALLATION TERMINÉE         ║"
    echo "╚═══════════════════════════════════════╝"
    echo ""
    echo "🌐 VOTRE RELAIS EST PRÊT :"
    echo "   IP: $PUBLIC_IP"
    echo "   Port: 4001"
    echo "   WebSocket: ws://$PUBLIC_IP:4001"
    echo ""
    echo "📊 VÉRIFICATION :"
    echo "   Service: $(systemctl is-active zeta-relay)"
    echo "   Port ouvert: $(netstat -tuln | grep :4001 | wc -l)"
    echo ""
    echo "📝 PROCHAINES ÉTAPES :"
    echo "   1. Envoyez votre IP à l'admin :"
    echo "      admin@zetanetwork.org"
    echo "   2. Votre relais sera ajouté au réseau"
    echo "   3. Il apparaîtra sur zetanetwork.org"
    echo ""
    echo "🔧 COMMANDES UTILES :"
    echo "   sudo systemctl status zeta-relay"
    echo "   sudo journalctl -u zeta-relay -f"
    echo "   curl http://localhost:4001/health"
    echo ""
    echo "💡 Le relais redémarre automatiquement"
    echo "   après un reboot du serveur."
    echo ""
    
else
    error "Le service n'est pas actif"
    echo "Vérifiez avec: sudo journalctl -u zeta-relay"
fi

# ============================================
# SCRIPT DE TEST AUTOMATIQUE
# ============================================

# Créer un script de test pour l'utilisateur
cat > /home/zetanode/test-relay.sh << 'EOF'
#!/bin/bash
echo "🧪 Test du relais Zeta Network"
echo "================================"
echo ""
echo "1. Statut du service:"
sudo systemctl status zeta-relay --no-pager | head -5
echo ""
echo "2. Test de connexion locale:"
timeout 2 curl -s http://localhost:4001/health 2>/dev/null && echo "✅ Relais répond" || echo "⚠️  Relais ne répond pas"
echo ""
echo "3. Pour voir les logs:"
echo "   sudo journalctl -u zeta-relay -n 20"
echo ""
echo "4. Pour tester avec un client:"
echo "   python3 -c \"import websockets, asyncio, json; async def test(): async with websockets.connect('ws://localhost:4001') as ws: print(await ws.recv()); asyncio.run(test())\""
EOF

chmod +x /home/zetanode/test-relay.sh
chown zetanode:zetanode /home/zetanode/test-relay.sh

# ============================================
# FIN
# ============================================

echo ""
echo "📞 Support: https://zeta.network/docs"
echo "🐛 Issues: https://github.com/zetanetwork/relay/issues"
echo ""
success "Merci de contribuer au réseau Zeta ! 🌐"