#!/bin/bash
# install-relay.sh - Installation Zeta Relay depuis cTHE0/zeta5
# Usage: curl -sSL https://raw.githubusercontent.com/cTHE0/zeta5/main/install-relay.sh | sudo bash

set -e

# ============================================
# CONFIGURATION
# ============================================

VERSION="2.0.0"
REPO_URL="https://github.com/cTHE0/zeta5.git"
INSTALL_DIR="/home/zetanode/zeta-relay"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================
# FONCTIONS
# ============================================

log() { echo -e "${BLUE}[ZETA]${NC} $1"; }
success() { echo -e "${GREEN}✅${NC} $1"; }
warn() { echo -e "${YELLOW}⚠️${NC} $1"; }
error() { echo -e "${RED}❌${NC} $1"; }

detect_ip() {
    log "🔍 Détection IP publique..."
    IP=$(curl -s --max-time 5 https://ifconfig.me 2>/dev/null || echo "NON_DÉTECTÉ")
    if [[ $IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "$IP"
    else
        echo "NON_DÉTECTÉ"
    fi
}

# ============================================
# INSTALLATION
# ============================================

main() {
    echo ""
    echo "🌐 ZETA NETWORK RELAY - Installation"
    echo "===================================="
    echo ""
    
    # Vérifier root
    if [ "$EUID" -ne 0 ]; then
        error "Exécutez avec: sudo bash"
        echo "Commande: curl -sSL https://raw.githubusercontent.com/cTHE0/zeta5/main/install-relay.sh | sudo bash"
        exit 1
    fi
    
    # Détection IP
    PUBLIC_IP=$(detect_ip)
    if [ "$PUBLIC_IP" = "NON_DÉTECTÉ" ]; then
        read -p "🌐 Entrez votre IP publique: " PUBLIC_IP
    else
        success "IP: $PUBLIC_IP"
    fi
    
    # 1. Mise à jour système
    log "📦 Mise à jour..."
    apt-get update > /dev/null 2>&1
    apt-get install -y python3 python3-venv python3-pip git curl ufw > /dev/null 2>&1
    
    # 2. Pare-feu
    log "🛡️ Pare-feu..."
    ufw --force enable > /dev/null 2>&1
    ufw allow 22/tcp > /dev/null 2>&1
    ufw allow 4001/tcp > /dev/null 2>&1
    ufw allow 4001/udp > /dev/null 2>&1
    
    # 3. Utilisateur
    log "👤 Création utilisateur..."
    if ! id "zetanode" &>/dev/null; then
        useradd -m -s /bin/bash -r zetanode
    fi
    
    # 4. Télécharger code
    log "📥 Téléchargement code..."
    su - zetanode -c "rm -rf ~/zeta-relay && mkdir -p ~/zeta-relay"
    su - zetanode -c "git clone $REPO_URL ~/zeta-temp"
    su - zetanode -c "cp -r ~/zeta-temp/p2p-node/* ~/zeta-relay/"
    su - zetanode -c "rm -rf ~/zeta-temp"
    
    # 5. Configuration
    log "⚙️ Configuration..."
    su - zetanode -c "cat > ~/zeta-relay/config.yaml << 'EOF'
network:
  listen_address: \"0.0.0.0\"
  listen_port: 4001
  public_ip: \"$PUBLIC_IP\"
  max_connections: 1000

bootstrap:
  central_hub: \"https://zetanetwork.org\"

logging:
  level: \"INFO\"
EOF"
    
    # 6. Environnement Python
    log "🐍 Environnement Python..."
    su - zetanode -c "cd ~/zeta-relay && python3 -m venv venv"
    su - zetanode -c "cd ~/zeta-relay && source venv/bin/activate && pip install -r requirements.txt"
    
    # 7. Service systemd
    log "⚙️ Service systemd..."
    cat > /etc/systemd/system/zeta-relay.service << EOF
[Unit]
Description=Zeta Network Relay
After=network.target

[Service]
Type=simple
User=zetanode
WorkingDirectory=/home/zetanode/zeta-relay
ExecStart=/home/zetanode/zeta-relay/venv/bin/python /home/zetanode/zeta-relay/relay.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable zeta-relay
    systemctl start zeta-relay
    
    sleep 2
    
    # 8. Vérification
    if systemctl is-active --quiet zeta-relay; then
        success "✅ RELAIS OPÉRATIONNEL !"
        
        echo ""
        echo "📋 RÉSUMÉ :"
        echo "   IP: $PUBLIC_IP"
        echo "   Port: 4001"
        echo "   WebSocket: ws://$PUBLIC_IP:4001"
        echo ""
        echo "🔧 Commandes :"
        echo "   sudo systemctl status zeta-relay"
        echo "   sudo journalctl -u zeta-relay -f"
        echo ""
        echo "📝 Envoyez votre IP à :"
        echo "   admin@zetanetwork.org"
        echo ""
        echo "🌐 Documentation :"
        echo "   https://github.com/cTHE0/zeta5"
        echo ""
        
    else
        error "❌ Échec démarrage"
        journalctl -u zeta-relay -n 20
    fi
}

main "$@"