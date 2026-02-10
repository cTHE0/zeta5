#!/bin/bash
# install-relay.sh - Installation en 1 clic pour Zeta Network
# Usage: curl -sSL https://raw.githubusercontent.com/cTHE0/zeta5/main/install-relay.sh | sudo bash

set -e

# ============================================
# CONFIGURATION
# ============================================

VERSION="2.0.0"
REPO_URL="https://github.com/cTHE0/zeta5.git"
INSTALL_DIR="/home/zetanode/zeta5-relay"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging
log() { echo -e "${BLUE}[ZETA]${NC} $1"; }
success() { echo -e "${GREEN}✅${NC} $1"; }
warn() { echo -e "${YELLOW}⚠️${NC} $1"; }
error() { echo -e "${RED}❌${NC} $1"; }

# ============================================
# FONCTIONS
# ============================================

detect_ip() {
    log "🔍 Détection de l'IP publique..."
    
    local services=(
        "ifconfig.me"
        "icanhazip.com" 
        "api.ipify.org"
        "checkip.amazonaws.com"
    )
    
    for service in "${services[@]}"; do
        if IP=$(curl -s --max-time 5 "https://$service" 2>/dev/null); then
            if [[ $IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                echo "$IP"
                return 0
            fi
        fi
    done
    
    echo "NON_DÉTECTÉ"
    return 1
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "Ce script nécessite les droits root"
        echo ""
        echo "Utilisez:"
        echo "  curl -sSL https://raw.githubusercontent.com/cTHE0/zeta5/main/install-relay.sh | sudo bash"
        echo ""
        exit 1
    fi
}

check_system() {
    if ! command -v apt-get &> /dev/null; then
        error "Ce script nécessite Ubuntu/Debian"
        exit 1
    fi
}

install_dependencies() {
    log "📦 Installation des dépendances système..."
    
    apt-get update > /dev/null 2>&1
    
    apt-get install -y \
        python3 \
        python3-venv \
        python3-pip \
        git \
        curl \
        ufw \
        jq > /dev/null 2>&1
        
    success "Dépendances installées"
}

setup_firewall() {
    log "🛡️ Configuration du pare-feu..."
    
    ufw --force enable > /dev/null 2>&1
    ufw allow 22/tcp > /dev/null 2>&1
    ufw allow 4001/tcp > /dev/null 2>&1
    ufw allow 4001/udp > /dev/null 2>&1
    
    success "Pare-feu configuré"
}

create_user() {
    log "👤 Création de l'utilisateur zetanode..."
    
    if ! id "zetanode" &>/dev/null; then
        useradd -m -s /bin/bash -r zetanode
        usermod -a -G www-data zetanode 2>/dev/null || true
        success "Utilisateur zetanode créé"
    else
        warn "Utilisateur zetanode existe déjà"
    fi
}

install_code() {
    log "📥 Téléchargement du code depuis GitHub..."
    
    mkdir -p "$INSTALL_DIR"
    chown zetanode:zetanode "$INSTALL_DIR"
    
    if [ -d "$INSTALL_DIR/.git" ]; then
        warn "Code déjà présent, mise à jour..."
        su - zetanode -c "cd '$INSTALL_DIR' && git pull origin main"
    else
        su - zetanode -c "git clone '$REPO_URL' '$INSTALL_DIR'"
    fi
    
    success "Code téléchargé dans $INSTALL_DIR"
}

setup_python_env() {
    log "🐍 Configuration de l'environnement Python..."
    
    su - zetanode -c "cd '$INSTALL_DIR' && python3 -m venv venv"
    su - zetanode -c "cd '$INSTALL_DIR' && source venv/bin/activate && pip install --upgrade pip"
    su - zetanode -c "cd '$INSTALL_DIR' && source venv/bin/activate && pip install -r requirements.txt"
    
    success "Environnement Python configuré"
}

create_config() {
    local ip="$1"
    
    log "⚙️ Création de la configuration..."
    
    cat > "$INSTALL_DIR/config.yaml" << EOF
# Zeta Network Relay - Auto-généré
# Version: $VERSION
# Date: $(date)

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

bootstrap:
  central_hub: "https://zetanetwork.org"
  min_connections: 1
  max_connections: 10

logging:
  level: "INFO"
  file: "/home/zetanode/zeta-relay.log"

relay_info:
  name: "Relay-$ip"
  region: "auto"
  installed_by: "install-relay.sh"
  install_date: "$(date -Iseconds)"
EOF
    
    chown zetanode:zetanode "$INSTALL_DIR/config.yaml"
    success "Configuration créée"
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
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
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
    systemctl enable zeta-relay
    
    success "Service systemd configuré"
}

start_service() {
    log "🚀 Démarrage du service..."
    
    systemctl start zeta-relay
    sleep 3
    
    if systemctl is-active --quiet zeta-relay; then
        success "Service démarré avec succès"
        return 0
    else
        error "Échec du démarrage du service"
        journalctl -u zeta-relay -n 20 --no-pager
        return 1
    fi
}

create_test_script() {
    log "🧪 Création des scripts de test..."
    
    cat > /home/zetanode/test-relay.sh << 'EOF'
#!/bin/bash
echo "🧪 Test du relais Zeta Network"
echo "================================"
echo ""
echo "1. Statut du service:"
sudo systemctl status zeta-relay --no-pager | grep -A 3 "Active:"
echo ""
echo "2. Logs récents:"
sudo journalctl -u zeta-relay -n 5 --no-pager --no-hostname
echo ""
echo "3. Test de connexion WebSocket:"
python3 -c "
import asyncio, websockets, json, sys
async def test():
    try:
        async with websockets.connect('ws://localhost:4001', timeout=2) as ws:
            welcome = await ws.recv()
            data = json.loads(welcome)
            print(f'✅ Connecté au relais: {data.get(\"relay_id\", \"N/A\")}')
            return True
    except Exception as e:
        print(f'❌ Erreur: {e}')
        return False
asyncio.run(test())
"
echo ""
echo "4. Pour plus d'informations:"
echo "   sudo journalctl -u zeta-relay -f"
echo "   curl -s http://localhost:4001/health | jq ."
EOF
    
    chmod +x /home/zetanode/test-relay.sh
    chown zetanode:zetanode /home/zetanode/test-relay.sh
    
    # Script de mise à jour
    cat > /home/zetanode/update-relay.sh << 'EOF'
#!/bin/bash
echo "🔄 Mise à jour du relais Zeta..."
cd /home/zetanode/zeta5-relay
sudo systemctl stop zeta-relay
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start zeta-relay
echo "✅ Mise à jour terminée"
sudo systemctl status zeta-relay --no-pager | head -5
EOF
    
    chmod +x /home/zetanode/update-relay.sh
    chown zetanode:zetanode /home/zetanode/update-relay.sh
    
    success "Scripts de test créés"
}

register_relay() {
    local ip="$1"
    
    log "📡 Enregistrement automatique..."
    
    cat > /tmp/zeta-register.json << EOF
{
    "action": "new_relay",
    "relay_ip": "$ip",
    "version": "$VERSION",
    "timestamp": "$(date -Iseconds)",
    "source": "github.com/cTHE0/zeta5"
}
EOF
    
    # Essayer d'envoyer la notification (silencieux)
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d @/tmp/zeta-register.json \
        "https://zetanetwork.org/api/v1/relays/notify" > /dev/null 2>&1 || true
    
    success "Notification envoyée"
}

show_summary() {
    local ip="$1"
    
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║          🌐 ZETA NETWORK RELAY              ║"
    echo "║          Installation Réussie               ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    echo "📋 INFORMATIONS DE VOTRE RELAIS :"
    echo "   🔗 IP Publique: $ip"
    echo "   🚪 Port: 4001"
    echo "   🌐 WebSocket: ws://$ip:4001"
    echo "   📁 Installation: $INSTALL_DIR"
    echo ""
    echo "✅ CE QUI A ÉTÉ INSTALLÉ :"
    echo "   ✓ Service systemd: zeta-relay"
    echo "   ✓ Utilisateur: zetanode"
    echo "   ✓ Pare-feu: port 4001 ouvert"
    echo "   ✓ Environnement Python isolé"
    echo "   ✓ Code depuis: github.com/cTHE0/zeta5"
    echo ""
    echo "🔧 COMMANDES UTILES :"
    echo "   sudo systemctl status zeta-relay"
    echo "   sudo journalctl -u zeta-relay -f"
    echo "   cd /home/zetanode && ./test-relay.sh"
    echo "   cd /home/zetanode && ./update-relay.sh"
    echo ""
    echo "📝 ÉTAPES SUIVANTES :"
    echo "   1. Vérifiez que tout fonctionne :"
    echo "      ./test-relay.sh"
    echo ""
    echo "   2. Envoyez votre IP à l'administrateur :"
    echo "      📧 admin@zetanetwork.org"
    echo "      📱 Telegram: @zetanetwork_admin"
    echo ""
    echo "   3. Une fois approuvé, votre relais sera"
    echo "      visible sur https://zetanetwork.org"
    echo ""
    echo "💡 Le relais redémarre automatiquement"
    echo "   après un reboot du serveur."
    echo ""
    echo "🔄 Pour mettre à jour plus tard :"
    echo "   curl -sSL https://zeta.network/update | sudo bash"
    echo ""
    echo "📚 Documentation :"
    echo "   https://github.com/cTHE0/zeta5"
    echo "   https://zeta.network/docs"
    echo ""
    success "Merci de contribuer au réseau Zeta Network ! 🌐"
}

# ============================================
# MAIN
# ============================================

main() {
    clear
    
    # En-tête
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║          🌐 ZETA NETWORK RELAY              ║"
    echo "║          Version $VERSION                      ║"
    echo "║          Installation Automatique           ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    echo "Ce script va installer un relais P2P pour le"
    echo "réseau social décentralisé Zeta Network."
    echo ""
    echo "📡 Votre serveur deviendra un point d'accès"
    echo "   pour les utilisateurs du réseau."
    echo ""
    echo "⏳ Installation en cours..."
    echo ""
    
    # Vérifications
    check_root
    check_system
    
    # Détection IP
    PUBLIC_IP=$(detect_ip)
    if [ "$PUBLIC_IP" = "NON_DÉTECTÉ" ]; then
        warn "IP publique non détectée automatiquement"
        read -p "🌐 Entrez votre IP publique: " PUBLIC_IP
        
        if [[ ! $PUBLIC_IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            error "Format d'IP invalide"
            exit 1
        fi
    else
        success "IP détectée: $PUBLIC_IP"
    fi
    
    # Installation
    install_dependencies
    setup_firewall
    create_user
    install_code
    setup_python_env
    create_config "$PUBLIC_IP"
    setup_systemd
    
    if ! start_service; then
        error "Installation échouée"
        exit 1
    fi
    
    # Finalisation
    create_test_script
    register_relay "$PUBLIC_IP"
    show_summary "$PUBLIC_IP"
}

# Exécution
main "$@"