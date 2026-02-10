#!/bin/bash
# deploy-relay.sh - Installation Auto-enregistrante pour Relais Zeta Network
# Usage: sudo ./deploy-relay.sh [HUB_URL]

set -e

# ============================================
# CONFIGURATION
# ============================================

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# URL par défaut du hub
DEFAULT_HUB="https://zetanetwork.org"
HUB_URL="${1:-$DEFAULT_HUB}"

# Fonctions
log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================
# DÉTECTION AUTOMATIQUE DE L'IP PUBLIQUE
# ============================================

detect_public_ip() {
    log "🔍 Détection de l'IP publique..."
    
    # Essayer plusieurs services
    local services=(
        "ifconfig.me"
        "icanhazip.com"
        "api.ipify.org"
        "checkip.amazonaws.com"
    )
    
    for service in "${services[@]}"; do
        IP=$(curl -s --connect-timeout 5 "https://$service")
        if [[ $IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            PUBLIC_IP=$IP
            success "IP publique détectée: $PUBLIC_IP (via $service)"
            return 0
        fi
    done
    
    # Fallback: demander à l'utilisateur
    warn "Impossible de détecter l'IP automatiquement"
    read -p "🌐 Entrez votre IP publique: " PUBLIC_IP
    
    if [[ ! $PUBLIC_IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        error "IP invalide: $PUBLIC_IP"
        exit 1
    fi
    
    return 0
}

# ============================================
# AUTO-ENREGISTREMENT AU HUB CENTRAL
# ============================================

auto_register() {
    local ip="$1"
    local hub_url="$2"
    
    log "📡 Envoi de l'IP au hub central..."
    
    # Créer un fichier temporaire avec les infos
    cat > /tmp/zeta-relay-info.json << EOF
{
    "relay_ip": "$ip",
    "install_date": "$(date -Iseconds)",
    "ubuntu_version": "$(lsb_release -ds)",
    "status": "pending_approval",
    "contact_email": "",
    "notes": "Installed via deploy-relay.sh"
}
EOF
    
    # Envoyer au hub central
    if curl -s -X POST \
        -H "Content-Type: application/json" \
        -d @/tmp/zeta-relay-info.json \
        "$hub_url/api/v1/relays/auto-register" > /tmp/response.json 2>&1; then
        
        if [ -s /tmp/response.json ]; then
            local relay_id=$(jq -r '.relay_id' /tmp/response.json 2>/dev/null || echo "")
            if [ -n "$relay_id" ]; then
                success "✅ Relais envoyé pour approbation !"
                success "📋 ID: $relay_id"
                echo ""
                echo "========================================"
                echo "🌐 VOTRE RELAIS EST PRÊT !"
                echo "========================================"
                echo "IP: $ip"
                echo "Port: 4001"
                echo "Endpoint: ws://$ip:4001"
                echo "ID: $relay_id"
                echo ""
                echo "📧 Envoyez ces informations à:"
                echo "   admin@zetanetwork.org"
                echo "   ou via Telegram: @zetanetwork_admin"
                echo ""
                echo "Une fois approuvé, votre relais apparaîtra"
                echo "automatiquement sur https://zetanetwork.org"
                echo "========================================"
                return 0
            fi
        fi
    fi
    
    # Fallback si l'API n'existe pas encore
    warn "L'API d'auto-enregistrement n'est pas disponible"
    warn "Veuillez envoyer manuellement votre IP à l'admin"
    
    echo ""
    echo "========================================"
    echo "📋 MANUEL - À ENVOYER À L'ADMIN"
    echo "========================================"
    echo "Nouveau relais prêt !"
    echo ""
    echo "IP: $ip"
    echo "Port: 4001"
    echo "WebSocket: ws://$ip:4001"
    echo "Installé le: $(date)"
    echo ""
    echo "📧 Envoyez à: admin@zetanetwork.org"
    echo "   ou Telegram: @zetanetwork_admin"
    echo "========================================"
    
    return 1
}

# ============================================
# INSTALLATION DU RELAIS
# ============================================

install_relay() {
    local ip="$1"
    local hub_url="$2"
    
    log "🚀 Installation du relais Zeta Network..."
    
    # Mise à jour
    apt-get update > /dev/null 2>&1
    apt-get upgrade -y > /dev/null 2>&1
    
    # Dépendances
    log "📦 Installation des dépendances..."
    apt-get install -y \
        python3 python3-venv python3-pip \
        git curl wget net-tools ufw \
        nginx supervisor jq > /dev/null 2>&1
    
    # Pare-feu
    ufw --force enable > /dev/null 2>&1
    ufw allow 22/tcp > /dev/null 2>&1
    ufw allow 4001/tcp > /dev/null 2>&1
    ufw allow 4001/udp > /dev/null 2>&1
    
    # Utilisateur
    if ! id "zetanode" &>/dev/null; then
        useradd -m -s /bin/bash -r zetanode
        usermod -a -G www-data zetanode
    fi
    
    # Code du relais
    su - zetanode -c "mkdir -p ~/zeta-relay"
    cd /home/zetanode/zeta-relay
    
    # Télécharger le code depuis GitHub
    log "📥 Téléchargement du code..."
    if [ -d ".git" ]; then
        su - zetanode -c "cd ~/zeta-relay && git pull"
    else
        su - zetanode -c "cd ~ && git clone https://github.com/zetanetwork/relay.git zeta-relay"
    fi
    
    # Configuration
    cat > config.yaml << EOF
network:
  listen_address: "0.0.0.0"
  listen_port: 4001
  public_ip: "$ip"
  max_connections: 1000

bootstrap:
  central_hub: "$hub_url"
  
logging:
  level: "INFO"
EOF
    
    # Environnement Python
    su - zetanode -c "cd ~/zeta-relay && python3 -m venv venv"
    su - zetanode -c "cd ~/zeta-relay && source venv/bin/activate && pip install -r requirements.txt"
    
    # Service systemd
    cat > /etc/systemd/system/zeta-relay.service << EOF
[Unit]
Description=Zeta Network Relay
After=network.target

[Service]
Type=simple
User=zetanode
WorkingDirectory=/home/zetanode/zeta-relay
ExecStart=/home/zetanode/zeta-relay/venv/bin/python relay.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable zeta-relay
    systemctl start zeta-relay
    
    # Script de test
    cat > /home/zetanode/test.sh << 'EOF'
#!/bin/bash
echo "🧪 Test du relais..."
systemctl status zeta-relay --no-pager | head -10
echo ""
echo "🌐 Test de connexion:"
timeout 2 curl -s http://localhost:4001/health || echo "Relais en cours de démarrage..."
EOF
    chmod +x /home/zetanode/test.sh
    chown zetanode:zetanode /home/zetanode/test.sh
    
    success "✅ Relais installé avec succès !"
}

# ============================================
# MAIN
# ============================================

main() {
    echo ""
    echo "========================================"
    echo "🌐 ZETA NETWORK RELAY - INSTALLATION"
    echo "========================================"
    echo ""
    
    # Vérifier root
    if [ "$EUID" -ne 0 ]; then
        error "Ce script nécessite les droits root"
        echo "Utilisez: sudo $0"
        exit 1
    fi
    
    # Détecter IP
    detect_public_ip
    
    # Installation
    install_relay "$PUBLIC_IP" "$HUB_URL"
    
    # Auto-enregistrement
    auto_register "$PUBLIC_IP" "$HUB_URL"
    
    # Attendre le démarrage
    sleep 3
    
    # Test final
    log "🧪 Test final..."
    if systemctl is-active --quiet zeta-relay; then
        success "🎉 RELAIS OPÉRATIONNEL !"
        echo ""
        echo "Commandes utiles:"
        echo "  sudo systemctl status zeta-relay"
        echo "  sudo journalctl -u zeta-relay -f"
        echo "  cd /home/zetanode && ./test.sh"
    else
        warn "⚠️  Le service n'est pas actif"
        echo "Vérifiez avec: sudo journalctl -u zeta-relay"
    fi
    
    echo ""
    success "Installation terminée à $(date)"
}

main "$@"