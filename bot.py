import telebot
from telebot import types
import sqlite3
from datetime import datetime
import random
import string
import time
import os
from flask import Flask
from threading import Thread

# --- ১. কনফিগারেশন ---
BOT_TOKEN = '8743917242:AAHaZfpFi13ZIYyglcNU0n1pvS2Z-WY3zes'
ADMIN_ID = 7585875519 
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# --- ২. ওয়েব সার্ভার লজিক (যাতে বোট অফ না হয়) ---
app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run():
    # Render-এর জন্য পোর্ট সেটআপ
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True # যাতে মেইন প্রোগ্রাম বন্ধ হলে এটিও বন্ধ হয়
    t.start()

# --- ৩. ডাটাবেস সেটআপ ---
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect('premium_investment_final.db')
    cursor = conn.cursor()
    cursor.execute(query, params)
    data = cursor.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return data

def init_db():
    db_query(""" CREATE TABLE IF NOT EXISTS users (
        uid INTEGER PRIMARY KEY, balance REAL DEFAULT 0, 
        last_bonus TEXT DEFAULT '', ref_code TEXT UNIQUE, referred_by INTEGER,
        total_ref INTEGER DEFAULT 0, is_blocked INTEGER DEFAULT 0) """)
    
    db_query(""" CREATE TABLE IF NOT EXISTS investments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, plan_id INTEGER, 
        start_date TEXT, daily_profit REAL, last_claim TEXT DEFAULT '') """)
    
    # লেনদেন হিস্টরির জন্য নতুন টেবিল
    db_query(""" CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, type TEXT, 
        amount REAL, info TEXT, date TEXT) """)

init_db()

# ==================== ১৫ মিনিট রোটেশন + টাইমার ====================
def get_current_number(method):
    """প্রতি ১৫ মিনিট পর নম্বর অটো চেঞ্জ করার সঠিক লজিক"""
    now = datetime.now()
    # ২৪ ঘণ্টার প্রতিটি ১৫ মিনিটের ব্লককে আলাদা ইনডেক্স দেওয়া হলো
    current_slot = (now.hour * 4) + (now.minute // 15)
    
    number_list = NUMBERS[method]
    # লিস্টের দৈর্ঘ্য অনুযায়ী নম্বরটি খুঁজে বের করা
    index = current_slot % len(number_list)
    
    return number_list[index]


def get_remaining_minutes():
    """এই নম্বর আর কত মিনিট পর চেঞ্জ হবে তার নির্ভুল হিসাব"""
    now = datetime.now()
    current_min = now.minute
    # পরবর্তী ১৫ মিনিটের বাউন্ডারি (যেমন: ১৫, ৩০, ৪৫, ৬০)
    next_boundary = ((current_min // 15) + 1) * 15
    remaining = next_boundary - current_min
    
    return remaining



# তোমার NUMBERS (যত খুশি নম্বর রাখতে পারো)
NUMBERS = {
    'Bkash': ['01864707606', '01906245591', '01735047020'],
    'Nagad': ['01906245591', '01864707606', '01302550839'],
    'Rocket': ['01906245591', '01906245591', '01906475591']
}

# ১৫টি প্রিমিয়াম ইনভেস্টমেন্ট প্ল্যান
PLANS = { i: {'price': p, 'daily': d, 'days': t, 'bonus': b} for i, p, d, t, b in [ 
    (1, 800, 80, 30, 5), (2, 1500, 120, 45, 10), (3, 3000, 200, 60, 20), (4, 5000, 320, 75, 30),
    (5, 8000, 480, 90, 50), (6, 12000, 650, 120, 70), (7, 18000, 900, 150, 100), (8, 25000, 1300, 180, 150),
    (9, 35000, 1800, 210, 200), (10, 50000, 2500, 240, 300), (11, 65000, 3200, 270, 400), (12, 80000, 3900, 300, 500),
    (13, 95000, 4500, 320, 600), (14, 110000, 5200, 340, 750), (15, 120000, 6000, 365, 1000) ] }

# --- ৩. কিবোর্ড ডিজাইন ---
def main_menu(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("📊 ব্যালেন্স 💰", "📈 ইনভেস্ট প্ল্যান 🚀")
    markup.add("📥 জমা করুন 💳", "📤 উত্তোলন করুন 🏦")
    markup.add("💼 আমার কাজ/দৈনিক টাক্স 📂", "🔗 রেফারেল 👥")
    markup.add("🎁 ডেইলি বোনাস ✨", "📜 লেনদেন হিস্টরি 📑")
    markup.add("💬 সাপোর্ট ও সাহায্য 🎧")
    if uid == ADMIN_ID: markup.add("⚙️ কন্ট্রোলার প্যানেল 🛠")
    return markup

def is_user_valid(uid):
    res = db_query("SELECT is_blocked FROM users WHERE uid=?", (uid,), fetch=True)
    if res and res[0][0] == 1: return False
    return True

def get_user_bonus_amount(uid):
    res = db_query("SELECT plan_id FROM investments WHERE uid=? ORDER BY plan_id DESC LIMIT 1", (uid,), fetch=True)
    if not res: return 0
    return PLANS[res[0][0]]['bonus']

# --- ৪. মেসেজ হ্যান্ডলার ---

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.chat.id
    if not is_user_valid(uid):
        bot.send_message(uid, "🚫 <b>দুঃখিত! আপনাকে ব্লক করা হয়েছে।</b>")
        return
    
    res = db_query("SELECT uid FROM users WHERE uid=?", (uid,), fetch=True)
    if not res:
        ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        ref_by = message.text.split()[1] if len(message.text.split()) > 1 else None
        db_query("INSERT INTO users (uid, ref_code, referred_by) VALUES (?, ?, ?)", (uid, ref_code, ref_by))
    
    welcome_txt = """🔥 <b>স্বাগতম PREMIUM INCOME BD-তে!</b> 🔥
━━━━━━━━━━━━━━━━━━━━
আপনার স্বপ্নকে সত্যি করতে এবং ঘরে বসে নিরাপদ আয়ের নিশ্চয়তা নিয়ে আমরা এসেছি আপনার পাশে।

✨ <b>আমাদের বিশেষত্ব:</b> ✨
✅ <b>সহজ বিনিয়োগ:</b> মাত্র ৮০০ টাকা থেকে শুরু।
✅ <b>নিশ্চিত আয়:</b> প্রতিদিন আপনার একাউন্টে লাভ যোগ হবে।
✅ <b>দ্রুত পেমেন্ট:</b> মাত্র ৮ ঘণ্টার মধ্যে উইথড্র সফল।
✅ <b>রেফার বোনাস:</b> বন্ধুদের ইনভাইট করলেই পাচ্ছেন আকর্ষণীয় বোনাস।

আমাদের সাথে আপনার যাত্রা হোক লাভজনক ও আনন্দময়!"""
    bot.send_message(uid, welcome_txt, reply_markup=main_menu(uid))

@bot.message_handler(func=lambda m: True)
def handle_msg(message):
    uid, txt = message.chat.id, message.text
    if not is_user_valid(uid): return

    elif "📊 ব্যালেন্স" in txt:
        res = db_query("SELECT balance FROM users WHERE uid=?", (uid,), fetch=True)
        bal = res[0][0] if res else 0.0

        balance_msg = f"""💰 <b>আপনার বর্তমান ব্যালেন্স</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━

         ➡️➡️➡️ ৳ {bal:,.2f} 💳

━━━━━━━━━━━━━━━━━━━━━━━━━━━

• মোট ব্যালেন্স 💰: <b>৳{bal:,.2f}</b>
• উপলব্ধ উত্তোলন 💰: <b>৳{max(0, bal):,.2f}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 <b>টিপস:</b>
• সর্বনিম্ন উত্তোলন: ৳৫০০
• উত্তোলন করতে "উত্তোলন করুন" বাটনে চাপুন
• আরও ব্যালেন্স যোগ করতে "জমা করুন" ব্যবহার করুন

সফলতার জন্য শুভকামনা! 🚀"""

        bot.send_message(uid, balance_msg)

    elif "📈 ইনভেস্ট প্ল্যান" in txt:
        msg = "💎 <b>আমাদের প্রিমিয়াম ইনভেস্টমেন্ট প্ল্যানসমূহ:</b>\n"
        msg += "⚠️ <i>মনে রাখবেন: বড় প্যাকেজে ডেইলি বোনাসও বেশি!</i>\n"
        for pid, p in PLANS.items():
            total = p['daily'] * p['days']
            msg += f"\n┌─────────────────────────┐\n💼 <b>ইনভেস্ট প্ল্যান – {pid:02}</b>\n💰 ইনভেস্ট: ৳{p['price']:,}\n⏳ মেয়াদ: {p['days']} দিন\n💵 দৈনিক আয়: ৳{p['daily']:,}\n🎁 ডেইলি বোনাস: ৳{p['bonus']}\n📊 মোট পাবেন: ৳{total:,}\n└─────────────────────────┘\n"
        bot.send_message(uid, msg + "\n📝 <b>আপনি কত নম্বর প্যাকেজটি নিতে চান? শুধু নম্বরটি লিখে পাঠান (যেমন: 1, 2, 5)</b>")
        bot.register_next_step_handler(message, process_buy_plan)

    elif "📥 জমা করুন" in txt:
        remaining = get_remaining_minutes()
        timer_line = f"🔄 এই নম্বরগুলো আর <b>{remaining}</b> মিনিট পর চেঞ্জ হবে ⏳"

        depo_msg = f"""<b>💳 জমা করার পেমেন্ট নম্বরসমূহ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{timer_line}

┌───────────────────────────────┐
│ 📱 <b>বিকাশ (Personal)</b>           │
│ <code>{get_current_number('Bkash')}</code>   │
│ 🔸 মিনিমাম: ৳৮০০                   │
└───────────────────────────────┘

┌───────────────────────────────┐
│ 🟠 <b>নগদ (Personal)</b>             │
│ <code>{get_current_number('Nagad')}</code>   │
│ 🔸 মিনিমাম: ৳৮০০                   │
└───────────────────────────────┘

┌───────────────────────────────┐
│ 🚀 <b>রকেট (Personal)</b>            │
│ <code>{get_current_number('Rocket')}</code>  │
│ 🔸 মিনিমাম: ৳৮০০                   │
└───────────────────────────────┘

┌───────────────────────────────┐
│ 🪙 <b>USDT (TRC20)</b>                │
│ <code>TMbcaNfCmm3LsbtMsw5sFXSfdAJ4ibA3WN</code> │
│ 🔸 মিনিমাম: $১০                     │
└───────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌍 <b>আন্তর্জাতিক পেমেন্ট (শীঘ্রই আসছে)</b>  <b>International Payments (Coming Soon)</b>
• 🇮🇳 UPI / PhonePe / Paytm
• 🇵🇰 Easypaisa / JazzCash
• 🇸🇦 STC Pay / Mada Pay
• 🇦🇪 PayBy / e& money
• 🇲🇾 Touch 'n Go / Boost
• 🇳🇵 eSewa / Khalti

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 <b>কম রেটে USDT/ডলার লাগলে যোগাযোগ:</b> @PremiumSupport_26

⚠️ <b>গুরুত্বপূর্ণ নির্দেশনা:</b>
• শুধু <b>Send Money</b> করবেন 
• পেমেন্টের স্ক্রিনশট এখানে পাঠান
• *অ্যাডমিন যাচাই করে দ্রুত ব্যালেন্স যোগ করে দিবে*

সব নম্বর <b>প্রতি ১৫ মিনিটে</b> অটো পরিবর্তন হয়।"""
        
        bot.send_message(uid, depo_msg)
        bot.register_next_step_handler(message, process_deposit_screenshot)

    elif "📤 উত্তোলন করুন" in txt:
        res = db_query("SELECT balance FROM users WHERE uid=?", (uid,), fetch=True)
        bal = res[0][0] if res else 0.0
        
        if bal < 500:
            bot.send_message(uid, f"""❌ <b>উত্তোলন করা যাবে না</b>

💰 বর্তমান ব্যালেন্স: ৳{bal:,.2f}
⚠️ সর্বনিম্ন উত্তোলন: ৳৫০০

আরও ব্যালেন্স যোগ করে পরে চেষ্টা করুন।""")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        methods = [
            ("🇧🇩 বিকাশ", "w_Bkash"),
            ("🇧🇩 নগদ", "w_Nagad"),
            ("🇧🇩 রকেট", "w_Rocket"),
            ("🪙 USDT", "w_USDT"),
            ("🇮🇳 UPI", "w_UPI"),
            ("🇵🇰 Easypaisa", "w_Easypaisa"),
            ("🇸🇦 STC Pay", "w_STCPay")
        ]
        
        for name, callback in methods:
            markup.add(types.InlineKeyboardButton(name, callback_data=callback))

        withdraw_msg = f"""🏦 <b>উত্তোলনের জন্য পেমেন্ট মেথড নির্বাচন করুন</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 বর্তমান ব্যালেন্স: <b>৳{bal:,.2f}</b>
⚠️ সর্বনিম্ন উত্তোলন: ৳৫০০

নিচের যেকোনো একটি মেথড বেছে নিন:
━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

        bot.send_message(uid, withdraw_msg, reply_markup=markup)

    elif "💼 আমার কাজ" in txt:
        invs = db_query("SELECT id, plan_id, daily_profit, last_claim FROM investments WHERE uid=?", (uid,), fetch=True)
        if not invs:
            bot.send_message(uid, "❌ আপনার কোনো সক্রিয় প্যাকেজ নেই। আয়ের জন্য আগে একটি প্ল্যান কিনুন।")
        else:
            for i in invs:
                today = datetime.now().strftime('%Y-%m-%d')
                btn_text = "✅ আজকের কাজ শেষ" if i[3] == today else "💰 প্রফিট সংগ্রহ করুন"
                markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(btn_text, callback_data=f"claim_{i[0]}"))
                bot.send_message(uid, f"💼 <b>প্যাকেজ নং: {i[1]}</b>\n💸 দৈনিক আয়: ৳{i[2]}", reply_markup=markup)

    elif "🔗 রেফারেল" in txt:
        res_check = db_query("SELECT id FROM investments WHERE uid=?", (uid,), fetch=True)
        if not res_check:
            bot.send_message(uid, "❌ <b>দুঃখিত! রেফারেল সুবিধা পেতে আপনাকে অবশ্যই একটি ইনভেস্ট প্ল্যান কিনতে হবে।</b>")
            return
        res = db_query("SELECT ref_code, total_ref FROM users WHERE uid=?", (uid,), fetch=True)
        ref_link = f"https://t.me/{(bot.get_me()).username}?start={res[0][0]}"
        bot.send_message(uid, f"👥 <b>আপনার রেফারেল তথ্য:</b>\n━━━━━━━━━━━━━━━━━━━━\n🔗 রেফার লিঙ্ক: <code>{ref_link}</code>\n👥 মোট রেফার: {res[0][1]} জন\n🎁 প্রতি রেফারে বোনাস: ৳১০")

    elif "🎁 ডেইলি বোনাস" in txt:
        bonus_amt = get_user_bonus_amount(uid)
        if bonus_amt == 0:
            bot.send_message(uid, "❌ <b>বোনাস পেতে আপনাকে অবশ্যই একটি ইনভেস্ট প্ল্যান কিনতে হবে। প্যাকেজের দাম যত বেশি বোনাসও তত বেশি!</b>")
            return
        
        res = db_query("SELECT last_bonus FROM users WHERE uid=?", (uid,), fetch=True)
        today = datetime.now().strftime('%Y-%m-%d')
        if res[0][0] == today:
            bot.send_message(uid, "❌ আপনি আজ অলরেডি বোনাস নিয়েছেন। আগামীকাল আবার চেষ্টা করুন।")
        else:
            db_query("UPDATE users SET balance = balance + ?, last_bonus = ? WHERE uid = ?", (bonus_amt, today, uid))
            bot.send_message(uid, f"✅ অভিনন্দন! আপনি আপনার প্যাকেজ অনুযায়ী আজ <b>৳{bonus_amt}</b> ডেইলি বোনাস পেয়েছেন।")

    elif "📜 লেনদেন হিস্টরি" in txt:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📥 ডিপোজিট হিস্টরি", callback_data="hist_depo"),
            types.InlineKeyboardButton("📤 উত্তোলন হিস্টরি", callback_data="hist_with"),
            types.InlineKeyboardButton("💼 প্যাকেজ হিস্টরি", callback_data="hist_pack")
        )
        
        history_msg = f"""📜 <b>লেনদেন হিস্টরি</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━

আপনার লেনদেনের ধরন নির্বাচন করুন:

• ডিপোজিট হিস্টরি → জমা করা লেনদেন দেখুন
• উত্তোলন হিস্টরি → উত্তোলনের রেকর্ড দেখুন
• প্যাকেজ হিস্টরি → কেনা প্যাকেজের তথ্য দেখুন

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 <b>টিপস:</b>
• সর্বোচ্চ ১০টি সাম্প্রতিক লেনদেন দেখানো হবে
• বিস্তারিত দেখতে উপরের বাটনে চাপুন

সবকিছু সঠিকভাবে যাচাই করে লেনদেন করুন।"""

        bot.send_message(uid, history_msg, reply_markup=markup)

    elif "💬 সাপোর্ট ও সাহায্য" in txt:
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("👨‍💻 Admin Support", url="https://t.me/PremiumSupport_26"))
        bot.send_message(uid, "🎧 কোনো সমস্যা বা পেমেন্ট সংক্রান্ত সাহায্যের জন্য নিচের বাটনে ক্লিক করে এডমিনের সাথে যোগাযোগ করুন।", reply_markup=markup)

    elif "⚙️ কন্ট্রোলার প্যানেল" in txt and uid == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📢 সকল ইউজারকে নোটিশ", callback_data="adm_broadcast"),
            types.InlineKeyboardButton("🚫 ইউজার ব্লক/আনব্লক", callback_data="adm_block"),
            types.InlineKeyboardButton("💰 ব্যালেন্স অ্যাড/কাটা", callback_data="adm_edit_bal")
        )
        bot.send_message(uid, "🛠 <b>এডমিন কন্ট্রোল সেন্টার</b>", reply_markup=markup)

# --- ৫. ব্যাকএন্ড লজিক ---

def process_buy_plan(message):
    try:
        pid = int(message.text)
        uid = message.chat.id
        if pid in PLANS:
            res = db_query("SELECT balance FROM users WHERE uid=?", (uid,), fetch=True)
            if res[0][0] >= PLANS[pid]['price']:
                db_query("UPDATE users SET balance = balance - ? WHERE uid = ?", (PLANS[pid]['price'], uid))
                db_query("INSERT INTO investments (uid, plan_id, daily_profit) VALUES (?, ?, ?)", (uid, pid, PLANS[pid]['daily']))
                # হিস্টরি সেভ
                db_query("INSERT INTO history (uid, type, amount, info, date) VALUES (?, ?, ?, ?, ?)", 
                         (uid, 'PACK', PLANS[pid]['price'], f"প্যাকেজ {pid}", datetime.now().strftime('%Y-%m-%d %H:%M')))
                
                ref_res = db_query("SELECT referred_by FROM users WHERE uid=?", (uid,), fetch=True)
                if ref_res and ref_res[0][0]:
                    db_query("UPDATE users SET balance = balance + 10, total_ref = total_ref + 1 WHERE ref_code = ?", (ref_res[0][0],))
                
                bot.send_message(uid, f"✅ অভিনন্দন! আপনি সফলভাবে {pid} নম্বর প্যাকেজটি সক্রিয় করেছেন।")
                
                notice = f"""🌟 <b>প্রিমিয়াম আপডেট নোটিশ</b> 🌟
━━━━━━━━━━━━━━━━━━━━
অভিনন্দন! আপনি {pid} নং প্যাকেজটি কিনেছেন। 

🚀 <b>আপনার নতুন সুবিধা:</b>
✅ এখন থেকে আপনি প্রতি রেফারে পাবেন <b>৳১০</b>।
✅ আপনার ডেইলি বোনাস এখন থেকে <b>৳{PLANS[pid]['bonus']}</b>।
💡 <i>টিপস: যত বড় প্যাকেজ কিনবেন, আপনার ডেইলি বোনাস তত বৃদ্ধি পাবে!</i>
━━━━━━━━━━━━━━━━━━━━"""
                bot.send_message(uid, notice)
            else: bot.send_message(uid, "❌ আপনার পর্যাপ্ত ব্যালেন্স নেই। আগে ডিপোজিট করুন।")
    except: bot.send_message(message.chat.id, "❌ ভুল নম্বর! শুধু প্যাকেজ আইডি দিন।")

def process_deposit_screenshot(message):
    if message.content_type == 'photo':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Accept", callback_data=f"depo_acc_{message.chat.id}"),
                   types.InlineKeyboardButton("❌ Cancel", callback_data=f"depo_can_{message.chat.id}"))
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=f"🔔 <b>নতুন ডিপোজিট রিকোয়েস্ট</b>\nUID: <code>{message.chat.id}</code>", reply_markup=markup)
        bot.send_message(message.chat.id, "⏳ আপনার পেমেন্ট স্ক্রিনশটটি পাঠানো হয়েছে। এডমিন চেক করে ব্যালেন্স যোগ করে দিবে।")

# --- ৬. এডমিন ও ইউজার অ্যাকশন (Callbacks) ---

@bot.callback_query_handler(func=lambda call: True)
def callback_logic(call):
    uid, data = call.message.chat.id, call.data
    
    if data.startswith("claim_"):
        inv_id = data.split("_")[1]
        res = db_query("SELECT daily_profit, last_claim FROM investments WHERE id=?", (inv_id,), fetch=True)
        today = datetime.now().strftime('%Y-%m-%d')
        if res[0][1] == today:
            bot.answer_callback_query(call.id, "❌ আজকে লাভ সংগ্রহ করেছেন!", show_alert=True)
        else:
            db_query("UPDATE users SET balance = balance + ? WHERE uid = ?", (res[0][0], uid))
            db_query("UPDATE investments SET last_claim = ? WHERE id = ?", (today, inv_id))
            bot.edit_message_text(f"✅ আজকের লাভ ৳{res[0][0]} ব্যালেন্সে যুক্ত হয়েছে।", uid, call.message.message_id)

    elif data.startswith("w_"):
        method = data.split("_")[1]
        msg = bot.send_message(uid, f"📝 আপনার {method} তথ্য (নম্বর/এড্রেস) দিন:")
        bot.register_next_step_handler(msg, process_withdraw_amount, method)

    elif data.startswith("depo_"):
        action, target_uid = data.split("_")[1], int(data.split("_")[2])
        if action == "acc":
            msg = bot.send_message(ADMIN_ID, f"ইউজার {target_uid} কে কত টাকা দিতে চান?")
            bot.register_next_step_handler(msg, admin_final_depo, target_uid, call.message.message_id)
        else:
            bot.send_message(target_uid, "❌ আপনার ডিপোজিট রিকোয়েস্টটি বাতিল করা হয়েছে।")
            bot.edit_message_caption("❌ ডিপোজিট বাতিল করা হয়েছে।", ADMIN_ID, call.message.message_id)

    elif data.startswith("wd_"):
        action, target_uid, amt = data.split("_")[1], int(data.split("_")[2]), float(data.split("_")[3])
        if action == "acc":
            # উইথড্র হিস্টরি সেভ
            db_query("INSERT INTO history (uid, type, amount, info, date) VALUES (?, ?, ?, ?, ?)", 
                     (target_uid, 'WITH', amt, "সফল উত্তোলন", datetime.now().strftime('%Y-%m-%d %H:%M')))
            bot.send_message(target_uid, f"✅ আপনার ৳{amt} উইথড্র সফল হয়েছে।")
            bot.edit_message_text(f"✅ উইথড্র এপ্রুভড (৳{amt})", ADMIN_ID, call.message.message_id)
        else:
            db_query("UPDATE users SET balance = balance + ? WHERE uid = ?", (amt, target_uid))
            bot.send_message(target_uid, f"❌ আপনার ৳{amt} উইথড্র বাতিল হয়েছে এবং টাকা ব্যালেন্সে ফেরত দেওয়া হয়েছে।")
            bot.edit_message_text(f"❌ উইথড্র বাতিল করা হয়েছে।", ADMIN_ID, call.message.message_id)

    # লেনদেন হিস্টরি লজিক
    elif data.startswith("hist_"):
        h_type = data.split("_")[1]
        t_map = {'depo': 'DEPO', 'with': 'WITH', 'pack': 'PACK'}
        db_type = t_map[h_type]
        results = db_query("SELECT amount, info, date FROM history WHERE uid=? AND type=? ORDER BY id DESC LIMIT 10", (uid, db_type), fetch=True)
        
        if not results:
            bot.send_message(uid, f"""📭 <b>{db_type} হিস্টরি</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
কোনো লেনদেন পাওয়া যায়নি।

প্রথম লেনদেন করুন এবং আবার চেক করুন।""")
            return

        h_msg = f"""📜 <b>{db_type} হিস্টরি (সাম্প্রতিক ১০টি)</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"""

        for i, r in enumerate(results, 1):
            h_msg += f"""┌──── লেনদেন #{i} ─────┐
│ 📅 তারিখ: {r[2]} │
│ 💰 পরিমাণ: ৳{r[0]:,.2f} │
│ ℹ️ বিবরণ: {r[1]} │
└─────────────────────┘\n"""

        h_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 সর্বোচ্চ সাম্প্রতিক ১০টি লেনদেন দেখানো হচ্ছে।"

        bot.send_message(uid, h_msg)
        
        if not results:
            bot.send_message(uid, "📭 এই ক্যাটাগরিতে আপনার কোনো হিস্টরি পাওয়া যায়নি।")
        else:
            h_msg = f"📜 <b>আপনার {db_type} হিস্টরি:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            for r in results:
                h_msg += f"📅 {r[2]}\n💰 পরিমাণ: ৳{r[0]}\nℹ️ তথ্য: {r[1]}\n\n"
            bot.send_message(uid, h_msg)

    elif data == "adm_broadcast":
        msg = bot.send_message(ADMIN_ID, "📢 সকল ইউজারকে পাঠানোর জন্য নোটিশটি লিখুন:")
        bot.register_next_step_handler(msg, admin_broadcast_msg)

    elif data == "adm_block":
        msg = bot.send_message(ADMIN_ID, "ব্লক করতে: `ID block` | আনব্লক করতে: `ID unblock` লিখুন।")
        bot.register_next_step_handler(msg, admin_block_user)

# --- ৭. এডমিন প্রসেসিং ফাংশনস ---

def admin_final_depo(message, target_uid, old_id):
    try:
        amt = float(message.text)
        db_query("UPDATE users SET balance = balance + ? WHERE uid = ?", (amt, target_uid))
        # ডিপোজিট হিস্টরি সেভ
        db_query("INSERT INTO history (uid, type, amount, info, date) VALUES (?, ?, ?, ?, ?)", 
                 (target_uid, 'DEPO', amt, "এডমিন এপ্রুভড", datetime.now().strftime('%Y-%m-%d %H:%M')))
        
        bot.send_message(target_uid, f"✅ এডমিন আপনার ৳{amt} ডিপোজিট সফলভাবে যুক্ত করেছে।")
        bot.edit_message_caption(f"✅ অনুমোদিত: ৳{amt}", ADMIN_ID, old_id)
    except: bot.send_message(ADMIN_ID, "❌ ভুল অ্যামাউন্ট!")

def process_withdraw_amount(message, method):
    num = message.text
    msg = bot.send_message(message.chat.id, "💰 উত্তোলনের পরিমাণ (৳) লিখুন:")
    bot.register_next_step_handler(msg, finish_withdrawal, method, num)

def finish_withdrawal(message, method, num):
    try:
        amt, uid = float(message.text), message.chat.id
        res = db_query("SELECT balance FROM users WHERE uid=?", (uid,), fetch=True)
        if res[0][0] >= amt:
            db_query("UPDATE users SET balance = balance - ? WHERE uid = ?", (amt, uid))
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ Accept", callback_data=f"wd_acc_{uid}_{amt}"),
                       types.InlineKeyboardButton("❌ Cancel", callback_data=f"wd_can_{uid}_{amt}"))
            bot.send_message(ADMIN_ID, f"📤 <b>নতুন উইথড্র রিকোয়েস্ট</b>\nUID: {uid}\nমেথড: {method}\nতথ্য: {num}\nপরিমাণ: ৳{amt}", reply_markup=markup)
            bot.send_message(uid, "✅ আপনার উইথড্র রিকোয়েস্টটি এডমিনের কাছে পাঠানো হয়েছে।")
        else: bot.send_message(uid, "❌ পর্যাপ্ত ব্যালেন্স নেই।")
    except: pass

def admin_broadcast_msg(message):
    users = db_query("SELECT uid FROM users", fetch=True)
    count = 0
    for u in users:
        try:
            bot.send_message(u[0], f"📢 <b>অফিশিয়াল নোটিশ</b>\n\n{message.text}")
            count += 1
        except: continue
    bot.send_message(ADMIN_ID, f"✅ {count} জন ইউজারকে নোটিশ পাঠানো হয়েছে।")

def admin_block_user(message):
    try:
        parts = message.text.split()
        target_id, action = int(parts[0]), parts[1].lower()
        val = 1 if action == "block" else 0
        db_query("UPDATE users SET is_blocked = ? WHERE uid = ?", (val, target_id))
        bot.send_message(ADMIN_ID, f"✅ ইউজার {target_id} সফলভাবে {action} করা হয়েছে।")
    except: bot.send_message(ADMIN_ID, "❌ ফরম্যাট ভুল!")

# --- ১০. বোট রান (সবার শেষে - এটি স্ক্রিনশট ৫ অনুযায়ী ঠিক করা) ---
if __name__ == "__main__":
    keep_alive() # এটি সবার আগে কল হবে
    
    print("--- Siyam, Your Full Bot is Online! ---")
    
    # বোটের পুরোনো ওয়েব হুক রিমুভ করা
    try:
        bot.remove_webhook()
    except:
        pass
        
    while True:
        try:
            # interval=0 এবং timeout=60 দিয়ে পোলিং শুরু
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5) # এরর আসলে ৫ সেকেন্ড অপেক্ষা করে আবার চেষ্টা করবে
            continue
