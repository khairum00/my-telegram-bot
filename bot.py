import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import random
import string

# --- ১. কনফিগারেশন ---
BOT_TOKEN = '8743917242:AAEVNA3mEgTTK045gLWAuzN002ACTLw26Yo'
ADMIN_ID = 7585875519 
bot = telebot.TeleBot(BOT_TOKEN)

# --- ২. ডাটাবেস ফাংশন ---
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect('premium_final_v11.db')
    cursor = conn.cursor()
    cursor.execute(query, params)
    data = cursor.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return data

def init_db():
    db_query(""" CREATE TABLE IF NOT EXISTS users (
        uid INTEGER PRIMARY KEY, balance REAL DEFAULT 0, 
        last_bonus TEXT DEFAULT '', ref_code TEXT UNIQUE, referred_by INTEGER ) """)
    db_query(""" CREATE TABLE IF NOT EXISTS investments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, plan_id INTEGER, 
        start_date TEXT, end_date TEXT, daily_profit REAL, last_claim TEXT DEFAULT '') """)
    db_query(""" CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT) """)
    
    # তোমার দেওয়া ওয়েলকাম মেসেজটি এখানে সেট করা হয়েছে
    welcome_txt = """🔥 *স্বাগতম PREMIUM INCOME BD-তে!* 🔥
━━━━━━━━━━━━━━━━━━━━
আপনার স্বপ্নকে সত্যি করতে এবং ঘরে বসে নিরাপদ আয়ের নিশ্চয়তা নিয়ে আমরা এসেছি আপনার পাশে। এটি একটি নির্ভরযোগ্য এবং দীর্ঘমেয়াদী বিনিয়োগ প্ল্যাটফর্ম। 💸
✨ *আমাদের বিশেষত্ব:* ✨
✅ *সহজ বিনিয়োগ:* মাত্র ৮০০ টাকা থেকে শুরু।
✅ *নিশ্চিত আয়:* প্রতিদিন আপনার একাউন্টে লাভ যোগ হবে।
✅ *দ্রুত পেমেন্ট:* মাত্র ৮ ঘণ্টা থেকে ২৪ ঘণ্টার মধ্যে উইথড্র সফল।
✅ *রেফার বোনাস:* বন্ধুদের ইনভাইট করলেই পাচ্ছেন আকর্ষণীয় বোনাস।"""

    defaults = [
        ('welcome_msg', welcome_txt),
        ('depo_msg', '💳 আমাদের বিকাশ/নগদ (Personal): `01906245591`\n⚠️ অবশ্যই *Send Money* করবেন।')
    ]
    for k, v in defaults:
        db_query("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

init_db()

# --- ৩. ইনভেস্টমেন্ট প্ল্যান ---
PLANS = { i: {'price': p, 'daily': d, 'days': t} for i, p, d, t in [ 
    (1, 800, 80, 30), (2, 1500, 120, 45), (3, 3000, 200, 60), (4, 5000, 320, 75),
    (5, 8000, 480, 90), (6, 12000, 650, 120), (7, 18000, 900, 150), (8, 25000, 1300, 180),
    (9, 35000, 1800, 210), (10, 50000, 2500, 240), (11, 65000, 3200, 270), (12, 80000, 3900, 300),
    (13, 95000, 4500, 320), (14, 110000, 5200, 340), (15, 120000, 6000, 365) ] }

# --- ৪. মেইন কিবোর্ড ---
def main_menu(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("📊 ব্যালেন্স 💰", "📈 ইনভেস্ট প্ল্যান 🚀")
    markup.add("📥 টাকা জমা দিন 💳", "📤 টাকা উত্তোলন 🏦")
    markup.add("💼 আমার কাজ 📂", "🔗 রেফারেল 👥", "🎁 ডেইলি বোনাস ✨")
    if uid == ADMIN_ID: markup.add("⚙️ কন্ট্রোলার প্যানেল 🛠")
    return markup

def register_user(uid):
    user = db_query("SELECT uid FROM users WHERE uid=?", (uid,), fetch=True)
    if not user:
        ref = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        db_query("INSERT INTO users (uid, ref_code) VALUES (?, ?)", (uid, ref))

# --- ৫. মেসেজ হ্যান্ডলার ---
@bot.message_handler(commands=['start'])
def start(message):
    register_user(message.chat.id)
    welcome = db_query("SELECT value FROM settings WHERE key='welcome_msg'", fetch=True)[0][0]
    bot.send_message(message.chat.id, welcome, reply_markup=main_menu(message.chat.id), parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_msg(message):
    uid = message.chat.id
    register_user(uid)
    txt = message.text

    if "📊 ব্যালেন্স" in txt:
        bal = db_query("SELECT balance FROM users WHERE uid=?", (uid,), fetch=True)[0][0]
        bot.send_message(uid, f"💰 আপনার বর্তমান ব্যালেন্স: *৳{bal}*", parse_mode="Markdown")

    elif "📥 টাকা জমা দিন" in txt:
        msg_text = db_query("SELECT value FROM settings WHERE key='depo_msg'", fetch=True)[0][0]
        msg = bot.send_message(uid, f"{msg_text}\n\nটাকা পাঠানোর পর *এমাউন্ট* এবং *TrxID* দিন।", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_deposit)

    elif "💼 আমার কাজ" in txt:
        invs = db_query("SELECT plan_id, start_date, end_date, daily_profit, id FROM investments WHERE uid=?", (uid,), fetch=True)
        if not invs:
            bot.send_message(uid, "❌ আপনার কোনো সক্রিয় প্যাকেজ নেই।")
        else:
            for i in invs:
                msg = f"📂 *প্যাকেজ ডিটেইলস:*\n📦 প্ল্যান: {i[0]}\n📅 শুরু: {i[1]}\n⏳ শেষ: {i[2]}\n💸 দৈনিক আয়: ৳{i[3]}"
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("💰 আজকের পেমেন্ট গ্রহণ করুন", callback_data=f"claim_{i[4]}"))
                bot.send_message(uid, msg, reply_markup=markup, parse_mode="Markdown")

    elif "📤 টাকা উত্তোলন" in txt:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("বিকাশ 📱", callback_data="w_Bkash"), 
                   types.InlineKeyboardButton("নগদ 🟠", callback_data="w_Nagad"))
        bot.send_message(uid, "🏦 পেমেন্ট মেথড সিলেক্ট করুন:", reply_markup=markup)

    elif "📈 ইনভেস্ট প্ল্যান" in txt:
        markup = types.InlineKeyboardMarkup(row_width=3)
        btns = [types.InlineKeyboardButton(f"📦 {i}", callback_data=f"view_{i}") for i in PLANS]
        markup.add(*btns)
        bot.send_message(uid, "💎 *আমাদের ইনভেস্টমেন্ট প্ল্যানসমূহ:*", reply_markup=markup, parse_mode="Markdown")

    elif "🎁 ডেইলি বোনাস" in txt:
        now = datetime.now()
        row = db_query("SELECT last_bonus FROM users WHERE uid=?", (uid,), fetch=True)[0]
        if row[0]:
            last_t = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
            if now - last_t < timedelta(hours=24):
                rem = timedelta(hours=24) - (now - last_t)
                return bot.send_message(uid, f"⏳ ইতিমধ্যে বোনাস নিয়েছেন!\nআবার পাবেন: `{str(rem).split('.')[0]}` পর।")
        
        db_query("UPDATE users SET balance = balance + 5, last_bonus = ? WHERE uid = ?", (now.strftime('%Y-%m-%d %H:%M:%S'), uid))
        bot.send_message(uid, "🎁 অভিনন্দন! আপনি ৫ টাকা ডেইলি বোনাস পেয়েছেন। ✨")

    elif "⚙️ কন্ট্রোলার প্যানেল" in txt and uid == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("👋 ওয়েলকাম মেসেজ পরিবর্তন", callback_data="set_welcome_msg"),
            types.InlineKeyboardButton("📢 নোটিশ পাঠান", callback_data="send_broadcast"),
            types.InlineKeyboardButton("🛠 Fix Button (Settings)", callback_data="fix_menu")
        )
        bot.send_message(ADMIN_ID, "🛠 এডমিন কন্ট্রোল সেন্টার:", reply_markup=markup)

# --- ৬. উইথড্র ও ডিপোজিট প্রসেস ---
def process_withdraw_num(message, method):
    num = message.text
    msg = bot.send_message(message.chat.id, f"💰 {method} নাম্বার: `{num}`।\nউত্তোলনের পরিমাণ লিখুন:")
    bot.register_next_step_handler(msg, process_withdraw_final, method, num)

def process_withdraw_final(message, method, num):
    try:
        amt = float(message.text)
        bal = db_query("SELECT balance FROM users WHERE uid=?", (message.chat.id,), fetch=True)[0][0]
        if amt < 500: return bot.send_message(message.chat.id, "❌ সর্বনিম্ন উত্তোলন ৫০০ টাকা।")
        if amt > bal: return bot.send_message(message.chat.id, "❌ পর্যাপ্ত ব্যালেন্স নেই।")
        
        db_query("UPDATE users SET balance = balance - ? WHERE uid = ?", (amt, message.chat.id))
        bot.send_message(message.chat.id, f"✅ রিকোয়েস্ট সফল! আগামী ৮ ঘণ্টার মধ্যে পেমেন্ট পাবেন। ✨")
        bot.send_message(ADMIN_ID, f"📤 *Withdraw Request*\nUID: `{message.chat.id}`\nMethod: {method}\nNum: `{num}`\nAmt: ৳{amt}")
    except: bot.send_message(message.chat.id, "❌ ভুল হয়েছে।")

def process_deposit(message):
    try:
        amt = message.text.split()[0]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"app_{message.chat.id}_{amt}"),
                   types.InlineKeyboardButton("❌ Cancel", callback_data=f"rej_{message.chat.id}"))
        bot.send_message(ADMIN_ID, f"🔔 নতুন ডিপোজিট: `{message.text}` (UID: `{message.chat.id}`)", reply_markup=markup)
        bot.send_message(message.chat.id, "⏳ তথ্য যাচাই করা হচ্ছে।")
    except: bot.send_message(message.chat.id, "❌ ভুল ফরম্যাট।")

# --- ৭. কলব্যাক হ্যান্ডলার ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.message.chat.id
    if call.data.startswith("app_"):
        _, target, amount = call.data.split("_")
        db_query("UPDATE users SET balance = balance + ? WHERE uid = ?", (float(amount), int(target)))
        bot.send_message(target, f"✅ অভিনন্দন! আপনার একাউন্টে ৳{amount} জমা হয়েছে। 🎉")
        bot.edit_message_text("✅ Approved!", chat_id=ADMIN_ID, message_id=call.message.message_id)

    elif call.data.startswith("claim_"):
        inv_id = call.data.split("_")[1]
        now = datetime.now()
        if not (10 <= now.hour < 17): return bot.answer_callback_query(call.id, "❌ সময়: সকাল ১০টা - বিকেল ৫টা", show_alert=True)
        
        row = db_query("SELECT last_claim, daily_profit FROM investments WHERE id=?", (inv_id,), fetch=True)[0]
        if row[0] == now.strftime('%Y-%m-%d'): return bot.answer_callback_query(call.id, "❌ আজ নেওয়া হয়ে গেছে", show_alert=True)
        
        db_query("UPDATE users SET balance = balance + ?, last_claim = ? WHERE uid = ?", (row[1], now.strftime('%Y-%m-%d'), uid))
        db_query("UPDATE investments SET last_claim = ? WHERE id = ?", (now.strftime('%Y-%m-%d'), inv_id))
        bot.answer_callback_query(call.id, f"✅ ৳{row[1]} যোগ হয়েছে।", show_alert=True)

    elif call.data.startswith("w_"):
        msg = bot.send_message(uid, "📝 আপনার নাম্বারটি লিখুন:")
        bot.register_next_step_handler(msg, process_withdraw_num, call.data.split("_")[1])

    elif call.data.startswith("view_"):
        pid = int(call.data.split("_")[1]); p = PLANS[pid]
        msg = f"💼 *প্যাকেজ {pid}*\n💵 দাম: ৳{p['price']}\n💰 দৈনিক আয়: ৳{p['daily']}\n⏳ মেয়াদ: {p['days']} দিন"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ কিনুন", callback_data=f"buy_{pid}"))
        bot.send_message(uid, msg, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("buy_"):
        pid = int(call.data.split("_")[1]); p = PLANS[pid]
        bal = db_query("SELECT balance FROM users WHERE uid=?", (uid,), fetch=True)[0][0]
        if bal < p['price']: return bot.answer_callback_query(call.id, "❌ ব্যালেন্স নেই", show_alert=True)
        
        db_query("UPDATE users SET balance = balance - ? WHERE uid=?", (p['price'], uid))
        db_query("INSERT INTO investments (uid, plan_id, start_date, end_date, daily_profit) VALUES (?, ?, ?, ?, ?)", 
                 (uid, pid, datetime.now().strftime('%Y-%m-%d'), (datetime.now() + timedelta(days=p['days'])).strftime('%Y-%m-%d'), p['daily']))
        bot.send_message(uid, "✅ প্যাকেজ কেনা সফল!")

bot.polling(none_stop=True)
