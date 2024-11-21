import config
import sqlite3
import logging
from telebot import types
from handlers.user import create_wallet

logger = logging.getLogger(__name__)

def get_cursor():
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    return cursor, conn

def handle_referral(message):
    referral_link = message.text
    referral_code = referral_link.split('=')[-1]
    inviter_id = int(referral_code)

    user_id = message.from_user.id
    cursor, conn = get_cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        message.reply_to(message, "Вы уже зарегистрированы.")
    else:
        try:
            # Проверяем, есть ли у пользователя кошелек
            cursor.execute("SELECT wallet_address FROM users WHERE telegram_id=?", (user_id,))
            wallet_address = cursor.fetchone()

            if not wallet_address:
                wallet_address = create_wallet()

            referral_link = f"https://t.me/{message.bot.get_me().username}?start={user_id}"
            cursor.execute("INSERT INTO users (telegram_id, name, wallet_address, referral_link) VALUES (?, ?, ?, ?)",
                           (user_id, message.from_user.first_name, wallet_address, referral_link))

            cursor.execute("UPDATE users SET invited_count=invited_count+1 WHERE telegram_id=?", (inviter_id,))
            cursor.execute("SELECT invited_count FROM users WHERE telegram_id=?", (inviter_id,))
            invited_count = cursor.fetchone()[0]

            if invited_count >= 5:
                cursor.execute("UPDATE users SET status='privileged' WHERE telegram_id=?", (inviter_id,))
                message.bot.send_message(inviter_id, "Поздравляем! Вы открыли доступ к эксклюзивной комнате!")

            conn.commit()
            message.reply_to(message,
                             f"Привет, {message.from_user.first_name}! Вы зарегистрированы. Ваша реферальная ссылка: {referral_link}")
        except Exception as e:
            logger.error(f"Error handling referral: {e}")
            message.reply_to(message, "Произошла ошибка при обработке реферальной ссылки. Пожалуйста, попробуйте позже.")
        finally:
            conn.close()
