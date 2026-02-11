#!/bin/bash
# install-relay.sh - Installation 1-clic pour Zeta Network Relay
# Repo: https://github.com/cTHE0/zeta5
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
    log "🔍 Détection de l'IP publique..."
    local services=(
        "ifconfig.me"
        "icanhazip.com"
        "api.ipify.org"
        "checkip.amazonaws.com"
    )
    for service in "${services[@]}"; do
        IP=$(curl -s --max-time 5 "https://$service" 2>/dev/null || echo "")
        if [[ $IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo "$IP"
            return 0
        fi
    done
    echo ""
    return 1
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "Ce script nécessite les droits root."
        echo ""
        echo "Utilisez:"
        echo "  curl -sSL https://raw.githubusercontent.com/cTHE0/zeta5/main/install-relay.sh | sudo bash"
        echo ""
        exit 1
    fi
}

check_system() {
    if ! command -v apt-get &> /dev/null; then
        error "Ce script nécessite Ubuntu/Debian."
        exit 1
    fi
}

install_dependencies() {
    log "📦 Installation des dépendances système..."
    apt-get update -qq > /dev/null 2>&1
    apt-get install -y -qq \
        python3 \
        python3-venv \
        python3-pip \
        git \
        curl \
        ufw \
        net-tools \
        jq > /dev/null 2>&1
    success "Dépendances installées"
}

setup_firewall() {
    log "🛡️ Configuration du pare-feu..."
    ufw --force enable > /dev/null 2>&1
    ufw allow 22/tcp > /dev/null 2>&1
    ufw allow 4001/tcp > /dev/null 2>&1
    ufw allow 4001/udp > /dev/null 2>&1
    success "Pare-feu configuré (port 4001 ouvert)"
}

create_user() {
    log "👤 Création de l'utilisateur dédié..."
    if ! id "zetanode" &>/dev/null; then
        useradd -m -s /bin/bash -r zetanode
        success "Utilisateur 'zetanode' créé"
    else
        warn "Utilisateur 'zetanode' existe déjà"
    fi
}

install_code() {
    log "📥 Téléchargement du code depuis GitHub..."
    rm -rf /home/zetanode/zeta-temp
    su - zetanode -c "git clone --depth 1 $REPO_URL /home/zetanode/zeta-temp" > /dev/null 2>&1
    su - zetanode -c "rm -rf $INSTALL_DIR"
    su - zetanode -c "mkdir -p $INSTALL_DIR"
    su - zetanode -c "cp -r /home/zetanode/zeta-temp/p2p-node/* $INSTALL_DIR/"
    su - zetanode -c "rm -rf /home/zetanode/zeta-temp"
    chown -R zetanode:zetanode $INSTALL_DIR
    success "Code installé dans $INSTALL_DIR"
}

create_config() {
    local ip="$1"
    log "⚙️ Génération de la configuration..."
    cat > $INSTALL_DIR/config.yaml << EOF
# Zeta Network Relay - Configuration automatique
# Généré le $(date)

network:
  listen_address: "0.0.0.0"
  listen_port: 4001
  public_ip: "$ip"
  max_connections: 1000
  heartbeat_interval: 30

gossip:
  topics:
    - "zeta-network-global"
    - "zeta-system-announcements"
  message_cache_size: 5000
  heartbeat_interval: 1
  max_message_size: 1048576

bootstrap:
  central_hub: "https://zetanetwork.org"
  min_connections: 1
  max_connections: 10

logging:
  level: "INFO"
  file: "/home/zetanode/zeta-relay.log"

relay:
  name: "Relay-$ip"
  version: "$VERSION"
  install_date: "$(date -Iseconds)"
EOF
    chown zetanode:zetanode $INSTALL_DIR/config.yaml
    success "Configuration créée"
}

setup_python_env() {
    log "🐍 Configuration de l'environnement Python..."
    su - zetanode -c "cd $INSTALL_DIR && python3 -m venv venv" > /dev/null 2>&1
    su - zetanode -c "cd $INSTALL_DIR && source venv/bin/activate && pip install --upgrade pip setuptools wheel -q" > /dev/null 2>&1
    su - zetanode -c "cd $INSTALL_DIR && source venv/bin/activate && pip install -r requirements.txt -q" > /dev/null 2>&1
    success "Environnement Python prêt"
}

setup_systemd() {
    log "⚙️ Configuration du service systemd..."
    cat > /etc/systemd/system/zeta-relay.service << EOF
[Unit]
Description=Zeta Network P2P Relay
Documentation=https://github.com/cTHE0/zeta5
After=network.target

[Service]
Type=simple
User=zetanode
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/relay.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=zeta-relay

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable zeta-relay > /dev/null 2>&1
    success "Service systemd créé"
}

start_service() {
    log "🚀 Démarrage du service..."
    systemctl start zeta-relay
    sleep 3
    if systemctl is-active --quiet zeta-relay; then
        success "Service démarré avec succès"
        return 0
    else
        error "Échec du démarrage"
        journalctl -u zeta-relay -n 20 --no-pager
        return 1
    fi
}

create_scripts() {
    log "🧪 Création des scripts utilitaires..."
    
    # Script de test
    cat > /home/zetanode/test-relay.sh << 'EOF'
#!/bin/bash
echo "🧪 Test du relais Zeta Network"
echo "================================"
echo ""
echo "1. Statut du service:"
sudo systemctl status zeta-relay --no-pager | head -5
echo ""
echo "2. Vérification du port:"
sudo netstat -tulpn | grep :4001 || echo "❌ Port 4001 non écouté"
echo ""
echo "3. Test de connexion WebSocket locale:"
timeout 3 python3 -c "
import asyncio, websockets, json
async def test():
    try:
        async with websockets.connect('ws://localhost:4001', timeout=2) as ws:
            welcome = await ws.recv()
            data = json.loads(welcome)
            print(f'✅ Connecté au relais: {data.get(\"relay_id\", \"N/A\")}')
    except Exception as e:
        print(f'❌ Erreur: {e}')
asyncio.run(test())
" 2>/dev/null || echo "❌ Échec de connexion"
echo ""
echo "4. Logs récents:"
sudo journalctl -u zeta-relay -n 10 --no-pager --no-hostname
EOF
    
    # Script de mise à jour
    cat > /home/zetanode/update-relay.sh << 'EOF'
#!/bin/bash
echo "🔄 Mise à jour du relais Zeta Network..."
cd /home/zetanode/zeta-relay
sudo systemctl stop zeta-relay
git pull origin main
cp -r p2p-node/* . 2>/dev/null || true
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start zeta-relay
sleep 2
sudo systemctl status zeta-relay --no-pager | head -5
echo "✅ Mise à jour terminée"
EOF
    
    # Script de désinstallation
    cat > /home/zetanode/uninstall-relay.sh << 'EOF'
#!/bin/bash
echo "🗑️ Désinstallation du relais Zeta Network..."
read -p "Confirmer la désinstallation ? (oui/non) " confirm
if [ "$confirm" = "oui" ]; then
    sudo systemctl stop zeta-relay
    sudo systemctl disable zeta-relay
    sudo rm /etc/systemd/system/zeta-relay.service
    sudo systemctl daemon-reload
    sudo userdel -r zetanode 2>/dev/null || true
    echo "✅ Désinstallation terminée"
else
    echo "❌ Annulé"
fi
EOF
    
    chmod +x /home/zetanode/*.sh
    chown zetanode:zetanode /home/zetanode/*.sh
    success "Scripts créés dans /home/zetanode/"
}

register_relay() {
    local ip="$1"
    log "📡 Enregistrement automatique..."
    cat > /tmp/zeta-register.json << EOF
{
    "relay_ip": "$ip",
    "version": "$VERSION",
    "timestamp": "$(date -Iseconds)",
    "source": "github.com/cTHE0/zeta5"
}
EOF
    curl -s -X POST -H "Content-Type: application/json" -d @/tmp/zeta-register.json https://zetanetwork.org/api/v1/relays/notify > /dev/null 2>&1 || true
    success "Notification envoyée à zetanetwork.org"
}

show_summary() {
    local ip="$1"
    clear
    echo ""
    echo "╔════════════════════════════════════════════════════╗"
    echo "║     🌐  ZETA NETWORK - RELAY INSTALLÉ AVEC SUCCÈS  ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo ""
    echo "   📋 INFORMATIONS DU RELAIS"
    echo "   ─────────────────────────"
    echo "   🔗 IP Publique:    $ip"
    echo "   🚪 Port:           4001"
    echo "   🌐 WebSocket:      ws://$ip:4001"
    echo "   📁 Installation:   $INSTALL_DIR"
    echo "   📦 Version:        $VERSION"
    echo ""
    echo "   ✅ SERVICES ACTIFS"
    echo "   ─────────────────"
    echo "   • Service systemd: zeta-relay (actif)"
    echo "   • Pare-feu:        port 4001 ouvert"
    echo "   • Utilisateur:     zetanode"
    echo "   • Environnement:   Python venv"
    echo ""
    echo "   🔧 COMMANDES UTILES"
    echo "   ─────────────────"
    echo "   • Voir le statut : sudo systemctl status zeta-relay"
    echo "   • Voir les logs  : sudo journalctl -u zeta-relay -f"
    echo "   • Tester         : cd /home/zetanode && ./test-relay.sh"
    echo "   • Mettre à jour  : cd /home/zetanode && ./update-relay.sh"
    echo "   • Désinstaller   : cd /home/zetanode && ./uninstall-relay.sh"
    echo ""
    echo "   📝 ÉTAPES SUIVANTES"
    echo "   ─────────────────"
    echo "   1. Vérifiez le bon fonctionnement :"
    echo "        /home/zetanode/test-relay.sh"
    echo ""
    echo "   2. Envoyez votre IP à l'administrateur :"
    echo "        📧 admin@zetanetwork.org"
    echo "        📱 Telegram: @zetanetwork_admin"
    echo ""
    echo "   3. Votre relais sera approuvé sous 24h"
    echo "      et apparaîtra sur https://zetanetwork.org"
    echo ""
    echo "   💡 Le relais redémarre automatiquement"
    echo "      après un reboot du serveur."
    echo ""
    echo "   📚 Documentation : https://github.com/cTHE0/zeta5"
    echo ""
    echo "╔════════════════════════════════════════════════════╗"
    echo "║     🎉  MERCI DE CONTRIBUER AU RÉSEAU !           ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo ""
}

# ============================================
# MAIN
# ============================================

main() {
    check_root
    check_system
    
    PUBLIC_IP=$(detect_ip)
    if [ -z "$PUBLIC_IP" ]; then
        warn "Détection automatique échouée"
        read -p "🌐 Entrez votre IP publique: " PUBLIC_IP
        if [[ ! $PUBLIC_IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            error "Format d'IP invalide"
            exit 1
        fi
    fi
    
    install_dependencies
    setup_firewall
    create_user
    install_code
    create_config "$PUBLIC_IP"
    setup_python_env
    setup_systemd
    start_service || exit 1
    create_scripts
    register_relay "$PUBLIC_IP"
    show_summary "$PUBLIC_IP"
}

main "$@"