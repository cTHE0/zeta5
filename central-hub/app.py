"""
Zeta Network - Application principale
Version minimaliste 100% fonctionnelle
"""

from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Zeta Network</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 800px;
            width: 100%;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 20px 40px rgba(0,0,0,0.2);
        }
        h1 { font-size: 3em; margin-bottom: 20px; text-align: center; }
        .status {
            background: #4CAF50;
            color: white;
            padding: 10px 20px;
            border-radius: 50px;
            display: inline-block;
            margin-bottom: 30px;
            font-weight: bold;
        }
        .relay-box {
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }
        .relay {
            display: flex;
            justify-content: space-between;
            padding: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .ip {
            font-family: monospace;
            background: rgba(0,0,0,0.3);
            padding: 5px 10px;
            border-radius: 5px;
        }
        .btn {
            background: white;
            color: #764ba2;
            padding: 15px 30px;
            border-radius: 50px;
            text-decoration: none;
            font-weight: bold;
            display: inline-block;
            margin-top: 20px;
            transition: transform 0.3s;
            border: none;
            cursor: pointer;
        }
        .btn:hover { transform: translateY(-2px); }
        .install-code {
            background: #1a1a1a;
            color: #4CAF50;
            padding: 15px;
            border-radius: 10px;
            font-family: monospace;
            margin: 20px 0;
            word-break: break-all;
        }
        .footer { margin-top: 40px; text-align: center; opacity: 0.8; }
    </style>
</head>
<body>
    <div class="card">
        <div style="text-align: center;">
            <span class="status">✅ RÉSEAU ACTIF</span>
        </div>
        
        <h1>🌐 Zeta Network</h1>
        
        <p style="text-align: center; margin-bottom: 30px; font-size: 1.2em;">
            Réseau social décentralisé
        </p>
        
        <div class="relay-box">
            <h3 style="margin-bottom: 20px;">📡 Relais actifs</h3>
            <div class="relay">
                <span>🇫🇷 Paris</span>
                <span class="ip">65.75.201.11:4001</span>
                <span style="color: #4CAF50;">● 45ms</span>
            </div>
            <div class="relay">
                <span>🇩🇪 Francfort</span>
                <span class="ip">65.75.200.180:4001</span>
                <span style="color: #4CAF50;">● 60ms</span>
            </div>
        </div>
        
        <div>
            <h3 style="margin-bottom: 20px;">🚀 Devenir un relais</h3>
            <div class="install-code">
                curl -sSL https://raw.githubusercontent.com/cTHE0/zeta5/main/install-relay.sh | sudo bash
            </div>
            <button class="btn" onclick="copyCommand()">📋 Copier</button>
        </div>
        
        <div class="footer">
            <p>
                <a href="/health" style="color: white;">Health</a> • 
                <a href="/api/relays" style="color: white;">API</a> • 
                <a href="https://github.com/cTHE0/zeta5" style="color: white;">GitHub</a>
            </p>
            <p style="margin-top: 10px;">Zeta Network 2026</p>
        </div>
    </div>
    
    <script>
        function copyCommand() {
            const cmd = 'curl -sSL https://raw.githubusercontent.com/cTHE0/zeta5/main/install-relay.sh | sudo bash';
            navigator.clipboard.writeText(cmd);
            alert('✅ Commande copiée !');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return INDEX_HTML

@app.route('/health')
@app.route('/api/health')
@app.route('/api/v1/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "zeta-network",
        "version": "2.0.0",
        "relays": 2,
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    })

@app.route('/api/relays')
@app.route('/api/v1/network/relays')
def relays():
    return jsonify({
        "relays": [
            {
                "id": "relay-01",
                "name": "Relais Paris",
                "ip": "65.75.201.11",
                "port": 4001,
                "endpoint": "ws://65.75.201.11:4001",
                "region": "eu-west",
                "latency": 45,
                "status": "online"
            },
            {
                "id": "relay-02",
                "name": "Relais Francfort",
                "ip": "65.75.200.180",
                "port": 4001,
                "endpoint": "ws://65.75.200.180:4001",
                "region": "eu-central",
                "latency": 60,
                "status": "online"
            }
        ],
        "total": 2,
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)