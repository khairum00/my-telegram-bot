from flask import Flask
import os
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run():
    port = int(os.environ.get("PORT", 10001))
    app.run(host="0.0.0.0", port=port)

def start():
    thread = threading.Thread(target=run)
    thread.start()

start()

import bot
