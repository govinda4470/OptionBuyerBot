from flask import Flask
from threading import Thread
import os, logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app = Flask(__name__)
@app.route('/')
def home():
    return "<h2>✅ OptionBuyerBot Alive 24/7</h2><p>Bot ONLINE</p><a href='/health'>/health</a>"
@app.route('/ping')
def ping():
    return "pong", 200
@app.route('/health')
def health():
    return {"status":"alive","bot":"OptionBuyerBot"}, 200
def run():
    port = int(os.environ.get("PORT", 8080))
    try:
        print(f"🌐 Keep-alive starting on 0.0.0.0:{port}")
        app.run(host='0.0.0.0', port=port, threaded=True)
    except Exception as e:
        print(f"Keep-alive failed: {e}")
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
    print("🌐 Keep-alive thread started")
