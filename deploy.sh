#!/bin/bash
# Script de déploiement pour Zeta Network

set -e

echo "🚀 Déploiement de Zeta Network"

# Variables
ENV=${1:-production}
DOCKER_REGISTRY="registry.zeta.network"
VERSION="1.0.0"

deploy_central_hub() {
    echo "📦 Déploiement du hub central..."
    
    cd central-hub
    
    # Installation des dépendances
    pip install -r requirements.txt
    
    # Configuration de la base de données
    if [ "$ENV" = "production" ]; then
        export DATABASE_URL="postgresql://user:pass@localhost/zeta_central"
        export SECRET_KEY=$(openssl rand -hex 32)
    fi
    
    # Migration de la base de données
    flask db upgrade
    
    # Démarrage avec Gunicorn
    gunicorn -w 4 -b 0.0.0.0:5000 app:app \
        --access-logfile - \
        --error-logfile - \
        --timeout 120
    
    cd ..
}

deploy_p2p_node() {
    echo "📦 Déploiement du nœud P2P..."
    
    cd p2p-node
    
    # Construire l'image Docker
    docker build -t ${DOCKER_REGISTRY}/zeta-node:${VERSION} .
    
    # Démarrer le conteneur
    docker run -d \
        --name zeta-node \
        --restart unless-stopped \
        -p 4001:4001 \
        -p 9090:9090 \
        -v $(pwd)/data:/app/data \
        -e NODE_ID=$(hostname) \
        ${DOCKER_REGISTRY}/zeta-node:${VERSION}
    
    cd ..
}

setup_nginx() {
    echo "🔧 Configuration Nginx..."
    
    cat > /etc/nginx/sites-available/zetanetwork.org << EOF
server {
    listen 80;
    server_name zetanetwork.org www.zetanetwork.org;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name zetanetwork.org www.zetanetwork.org;
    
    ssl_certificate /etc/letsencrypt/live/zetanetwork.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zetanetwork.org/privkey.pem;
    
    # Proxy pour le hub central
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # WebSocket support
    location /ws {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }
    
    # API
    location /api {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
    }
}
EOF
    
    # Activer le site
    ln -sf /etc/nginx/sites-available/zetanetwork.org /etc/nginx/sites-enabled/
    nginx -t && systemctl reload nginx
}

setup_monitoring() {
    echo "📊 Configuration du monitoring..."
    
    # Prometheus
    cat > /etc/prometheus/prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'zeta-central'
    static_configs:
      - targets: ['localhost:5000']
    
  - job_name: 'zeta-nodes'
    static_configs:
      - targets: ['localhost:9090']
    
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
EOF
}

print_next_steps() {
    echo ""
    echo "✅ Déploiement terminé!"
    echo ""
    echo "📋 Prochaines étapes:"
    echo "1. Configurer le DNS pour zetanetwork.org"
    echo "2. Obtenir un certificat SSL: certbot --nginx"
    echo "3. Démarrer les services:"
    echo "   - systemctl start zeta-central"
    echo "   - systemctl start zeta-node"
    echo "4. Vérifier les logs:"
    echo "   - journalctl -u zeta-central -f"
    echo "   - docker logs -f zeta-node"
    echo ""
    echo "🌐 Accès:"
    echo "   - Site: https://zetanetwork.org"
    echo "   - API: https://zetanetwork.org/api/v1/network/relays"
    echo "   - Monitoring: http://localhost:9090"
    echo ""
}

# Déploiement principal
main() {
    echo "Mode de déploiement: $ENV"
    
    deploy_central_hub &
    deploy_p2p_node &
    
    wait
    
    if [ "$ENV" = "production" ]; then
        setup_nginx
        setup_monitoring
    fi
    
    print_next_steps
}

main