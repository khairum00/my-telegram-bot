import os
import threading
from flask import Flask
import bot

app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot Running"

def start_bot():
    bot.bot.infinity_polling()

# bot thread start
threading.Thread(target=start_bot).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
