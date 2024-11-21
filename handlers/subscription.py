import sqlite3
from telebot import types
from telebot import TeleBot


def get_cursor():
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    return cursor, conn

def subscribe(message):
    user_id = message.from_user.id
    cursor, conn = get_cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        wallet_address = user[3]
        bot.send_message(message.chat.id, f"Для оплаты подписки переведите 1 TON на адрес: {wallet_address}")
    else:
        bot.send_message(message.chat.id, "Вы не зарегистрированы. Используйте команду /start для регистрации.")
    conn.close()
