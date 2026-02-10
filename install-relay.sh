#!/bin/bash
set -e

echo -e "\n🌐 ZETA NETWORK RELAY - Installation"
echo "====================================\n"

# 1. IP publique
IP=$(curl -s https://api.ipify.org || echo "127.0.0.1")
echo "✅ IP: $IP"

# 2. Installer Rust globalement (évite les problèmes de permissions)
if ! command -v cargo &>/dev/null; then
    echo "[ZETA] 🦀 Installation Rust (globale)..."
    apt update >/dev/null 2>&1
    apt install -y cargo pkg-config libssl-dev build-essential >/dev/null 2>&1
fi

# 3. Créer utilisateur dédié
id -u zetanode &>/dev/null || useradd -m -s /bin/bash zetanode

# 4. Préparer le dossier
rm -rf /home/zetanode/zeta-relay
sudo -u zetanode mkdir -p /home/zetanode/zeta-relay

# 5. Cloner le dépôt
echo "[ZETA] 📥 Clonage dépôt..."
sudo -u zetanode git clone -q https://github.com/CTHE0/zeta4.git /home/zetanode/zeta-relay

# 6. Compiler (en tant que zetanode)
echo "[ZETA] ⚙️ Compilation (patientez ~2 min)..."
cd /home/zetanode/zeta-relay/zetanetwork-node
sudo -u zetanode cargo build --release --quiet

# 7. Générer l'identité
echo -e "\n🔑 Génération identité du relais..."
sudo -u zetanode timeout 10 ./target/release/zetanetwork-node 2>&1 | tee /tmp/zeta-first-run.log || true

# 8. Récupérer le PeerID
PEER_ID=$(grep -oP 'PeerID: \K\S+' /tmp/zeta-first-run.log | head -1)
if [ -z "$PEER_ID" ]; then
    echo "❌ Échec: PeerID non détecté. Vérifiez les logs:"
    cat /tmp/zeta-first-run.log
    exit 1
fi
echo -e "\n🆔 PeerID: $PEER_ID"

# 9. systemd
cat > /etc/systemd/system/zetanetwork.service <<EOF
[Unit]
Description=Zeta Network Relay
After=network.target

[Service]
User=zetanode
WorkingDirectory=/home/zetanode/zeta-relay/zetanetwork-node
ExecStart=/home/zetanode/zeta-relay/zetanetwork-node/target/release/zetanetwork-node
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl start zetanetwork
systemctl enable zetanetwork >/dev/null 2>&1

# 10. Pare-feu
ufw allow 9090/tcp >/dev/null 2>&1 || true
ufw allow 9091/tcp >/dev/null 2>&1 || true

echo -e "\n✅ Relais opérationnel !"
echo "📊 Statut: systemctl status zetanetwork"
echo "📄 Logs: journalctl -u zetanetwork -f"
echo -e "\n🔗 À ajouter dans bootstrap_nodes (sur autres relais):"
echo "/ip4/$IP/tcp/9090/p2p/$PEER_ID"