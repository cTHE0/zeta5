#!/bin/bash
# install-relay.sh – Version 3.0.0
# Usage : ./install-relay.sh [--ssl mon.domaine.tld]

set -e

VERSION="3.0.0"
REPO_URL="https://github.com/cTHE0/zeta5.git"
INSTALL_DIR="/home/zetanode/zeta-relay"

# Couleurs
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log() { echo -e "${BLUE}[ZETA]${NC} $1"; }
success() { echo -e "${GREEN}✅${NC} $1"; }
warn() { echo -e "${YELLOW}⚠️${NC} $1"; }
error() { echo -e "${RED}❌${NC} $1"; }

# Arguments
SSL_MODE=false
DOMAIN=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --ssl) SSL_MODE=true; DOMAIN="$2"; shift 2;;
        *) error "Argument inconnu : $1"; exit 1;;
    esac
done

# Détection IP
detect_ip() {
    curl -s --max-time 5 https://ifconfig.me || \
    curl -s --max-time 5 https://icanhazip.com || \
    echo ""
}
PUBLIC_IP=$(detect_ip)
if [ -z "$PUBLIC_IP" ]; then
    read -p "🌐 Entrez votre IP publique : " PUBLIC_IP
fi
log "IP publique : $PUBLIC_IP"

# Vérification root
if [ "$EUID" -ne 0 ]; then
    error "Ce script doit être exécuté en root (sudo)."
    exit 1
fi

# Mise à jour et dépendances de base
log "📦 Installation des paquets système..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl ufw

# Pare‑feu
log "🛡️ Configuration du pare‑feu..."
ufw --force enable > /dev/null 2>&1
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 4001/tcp   # optionnel (connexion directe ws)

# Utilisateur zetanode
log "👤 Utilisateur zetanode..."
if ! id "zetanode" &>/dev/null; then
    useradd -m -s /bin/bash -r zetanode
fi

# Téléchargement du code
log "📥 Téléchargement depuis GitHub..."
su - zetanode -c "rm -rf /home/zetanode/zeta-temp"
su - zetanode -c "git clone --depth 1 $REPO_URL /home/zetanode/zeta-temp"
su - zetanode -c "mkdir -p $INSTALL_DIR"
su - zetanode -c "cp -r /home/zetanode/zeta-temp/p2p-node/* $INSTALL_DIR/"
su - zetanode -c "rm -rf /home/zetanode/zeta-temp"

# Configuration du relais
log "⚙️ Écriture de config.yaml..."
cat > $INSTALL_DIR/config.yaml << EOF
network:
  listen_address: "0.0.0.0"
  listen_port: 4001
  public_ip: "$PUBLIC_IP"
  domain: "${DOMAIN:-}"
  max_connections: 1000

bootstrap:
  central_hub: "https://zetanetwork.org"

logging:
  level: "INFO"
EOF
chown zetanode:zetanode $INSTALL_DIR/config.yaml

# Environnement Python
log "🐍 Environnement virtuel..."
su - zetanode -c "cd $INSTALL_DIR && python3 -m venv venv"
su - zetanode -c "cd $INSTALL_DIR && source venv/bin/activate && pip install -q websockets PyYAML"

# ============================================
# MODE SSL – Installation de Nginx + Certbot
# ============================================
if [ "$SSL_MODE" = true ] && [ -n "$DOMAIN" ]; then
    log "🔐 Configuration SSL pour $DOMAIN..."
    apt-get install -y -qq nginx certbot python3-certbot-nginx

    # Arrêt temporaire de Nginx
    systemctl stop nginx

    # Obtention du certificat (standalone)
    certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos --email admin@zetanetwork.org || {
        warn "Certbot a échoué. Vérifiez que le DNS pointe bien vers $PUBLIC_IP"
    }

    # Configuration Nginx
    cat > /etc/nginx/sites-available/zeta-relay << EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:4001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    ln -sf /etc/nginx/sites-available/zeta-relay /etc/nginx/sites-enabled/
    nginx -t && systemctl restart nginx
    success "✅ Nginx avec SSL actif – https://$DOMAIN"
else
    warn "Mode non sécurisé (ws://). Pour SSL, utilisez --ssl votre.domaine"
fi

# ============================================
# SERVICE SYSTEMD
# ============================================
log "⚙️ Installation du service systemd..."
cat > /etc/systemd/system/zeta-relay.service << EOF
[Unit]
Description=Zeta Network P2P Relay
After=network.target

[Service]
Type=simple
User=zetanode
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/relay.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable zeta-relay
systemctl restart zeta-relay
sleep 2

# ============================================
# SCRIPTS UTILITAIRES
# ============================================
log "🧪 Création des scripts de test..."
cat > /home/zetanode/test-relay.sh << 'EOF'
#!/bin/bash
echo "🧪 Test du relais local"
sudo systemctl status zeta-relay --no-pager | head -5
echo ""
echo "📡 Test WebSocket :"
timeout 2 python3 -c "
import asyncio, websockets
async def test():
    try:
        async with websockets.connect('ws://localhost:4001') as ws:
            print('✅ Connexion locale réussie')
    except Exception as e:
        print(f'❌ Échec : {e}')
asyncio.run(test())
"
EOF
chmod +x /home/zetanode/test-relay.sh
chown zetanode:zetanode /home/zetanode/test-relay.sh

# ============================================
# RAPPORT FINAL
# ============================================
success "✅ Installation terminée avec succès !"
echo ""
echo "📋 INFORMATIONS DU RELAIS"
echo "   IP publique : $PUBLIC_IP"
if [ "$SSL_MODE" = true ] && [ -n "$DOMAIN" ]; then
    echo "   Domaine sécurisé : wss://$DOMAIN"
    echo "   (via Nginx reverse proxy)"
else
    echo "   WebSocket direct : ws://$PUBLIC_IP:4001"
fi
echo ""
echo "🔧 Commandes utiles :"
echo "   sudo systemctl status zeta-relay"
echo "   sudo journalctl -u zeta-relay -f"
echo "   cd /home/zetanode && ./test-relay.sh"
echo ""
echo "📧 Envoyez cette IP ou ce domaine à admin@zetanetwork.org"
echo ""
success "🎉 Merci de contribuer à Zeta Network !"