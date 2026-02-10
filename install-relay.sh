#!/bin/bash
set -e

echo -e "\n🌐 ZETA NETWORK RELAY - Installation"
echo "====================================\n"

# Détection IP
IP=$(curl -s https://api.ipify.org)
echo "✅ IP publique: $IP"

# Créer utilisateur dédié (si absent)
id -u zetanode &>/dev/null || useradd -m -s /bin/bash zetanode

# Préparer le dossier
rm -rf /home/zetanode/zeta-relay
sudo -u zetanode mkdir -p /home/zetanode/zeta-relay

# Cloner le dépôt (en tant que zetanode)
sudo -u zetanode git clone https://github.com/CTHE0/zeta4.git /home/zetanode/zeta-relay

# Compiler le relais Rust
cd /home/zetanode/zeta-relay/zetanetwork-node
sudo -u zetanode cargo build --release

# Générer l'identité au premier démarrage
echo -e "\n🔑 Génération de l'identité du relais..."
sudo -u zetanode ./target/release/zetanetwork-node 2>&1 | tee /tmp/zeta-first-run.log &
PID=$!
sleep 5
kill $PID 2>/dev/null || true
wait $PID 2>/dev/null || true

# Récupérer le PeerID
PEER_ID=$(grep -oP 'PeerID: \K\S+' /tmp/zeta-first-run.log | head -1)
echo -e "\n🆔 Votre PeerID: $PEER_ID"

# systemd
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

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl start zetanetwork
systemctl enable zetanetwork

# Ouvrir les ports
ufw allow 9090/tcp >/dev/null 2>&1 || true
ufw allow 9091/tcp >/dev/null 2>&1 || true

echo -e "\n✅ Relais démarré !"
echo "📊 Statut: systemctl status zetanetwork"
echo "📄 Logs: journalctl -u zetanetwork -f"
echo "🆔 PeerID à partager: $PEER_ID"