import config
import sqlite3
import logging
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader
from telebot import types

logger = logging.getLogger(__name__)

def get_cursor():
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    return cursor, conn

# Административные команды
def admin_stats(message):
    if message.from_user.id not in config.ADMIN_USER_IDS:
        bot.send_message(message.chat.id, "У вас нет доступа к этой команде.")
        return

    cursor, conn = get_cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE status='privileged'")
    privileged_users = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='subscription'")
    total_subscriptions = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='donate'")
    total_donations = cursor.fetchone()[0]

    stats_message = (
        f"Общее количество подписчиков: {total_users}\n"
        f"Количество привилегированных пользователей: {privileged_users}\n"
        f"Сумма подписок: {total_subscriptions} TON\n"
        f"Сумма донатов: {total_donations} TON"
    )
    bot.send_message(message.chat.id, stats_message)
    conn.close()

def admin_manage_access(message):
    if message.from_user.id not in config.ADMIN_USER_IDS:
        bot.send_message(message.chat.id, "У вас нет доступа к этой команде.")
        return

    args = message.text.split()
    if len(args) < 3:
        bot.send_message(message.chat.id, "Используйте команду в формате: /admin_manage_access <user_id> <add/remove>")
        return

    user_id = int(args[1])
    action = args[2]

    cursor, conn = get_cursor()
    if action == 'add':
        cursor.execute("UPDATE users SET status='privileged' WHERE telegram_id=?", (user_id,))
        bot.send_message(message.chat.id, f"Пользователь {user_id} добавлен в приватную комнату.")
    elif action == 'remove':
        cursor.execute("UPDATE users SET status='ordinary' WHERE telegram_id=?", (user_id,))
        bot.send_message(message.chat.id, f"Пользователь {user_id} удален из приватной комнаты.")
    else:
        bot.send_message(message.chat.id, "Неверная команда. Используйте 'add' или 'remove'.")

    conn.commit()
    conn.close()

def admin_view_transactions(message):
    if message.from_user.id not in config.ADMIN_USER_IDS:
        bot.send_message(message.chat.id, "У вас нет доступа к этой команде.")
        return

    cursor, conn = get_cursor()
    cursor.execute("SELECT * FROM transactions")
    transactions = cursor.fetchall()

    if transactions:
        transactions_message = "История транзакций:\n"
        for transaction in transactions:
            transactions_message += f"ID: {transaction[0]}, User ID: {transaction[1]}, Amount: {transaction[2]} TON, Type: {transaction[3]}, Date: {transaction[4]}\n"
        bot.send_message(message.chat.id, transactions_message)
    else:
        bot.send_message(message.chat.id, "Нет транзакций для отображения.")
    conn.close()

def admin_schedule_post(message):
    if message.from_user.id not in config.ADMIN_USER_IDS:
        bot.send_message(message.chat.id, "У вас нет доступа к этой команде.")
        return

    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        bot.send_message(message.chat.id, "Используйте команду в формате: /admin_schedule_post <type> <date> <text>")
        return

    post_type = args[1]
    publication_date = args[2]
    text = args[3]

    try:
        publication_date = datetime.strptime(publication_date, '%Y-%m-%d %H:%M:%S')
        schedule_post(text, post_type, publication_date)
        bot.send_message(message.chat.id, "Пост успешно запланирован.")
    except Exception as e:
        logger.error(f"Error scheduling post: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при планировании поста. Пожалуйста, проверьте формат даты.")

def schedule_post(text, post_type, publication_date):
    cursor, conn = get_cursor()
    cursor.execute("INSERT INTO posts (text, type, publication_date) VALUES (?, ?, ?)",
                   (text, post_type, publication_date))
    conn.commit()
    conn.close()

def send_weekly_report():
    cursor, conn = get_cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE status='privileged'")
    privileged_users = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='subscription'")
    total_subscriptions = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='donate'")
    total_donations = cursor.fetchone()[0]

    report_message = (
        f"Еженедельный отчет:\n"
        f"Общее количество подписчиков: {total_users}\n"
        f"Количество привилегированных пользователей: {privileged_users}\n"
        f"Сумма подписок: {total_subscriptions} TON\n"
        f"Сумма донатов: {total_donations} TON"
    )

    for admin_id in config.ADMIN_USER_IDS:
        bot.send_message(admin_id, report_message)
    conn.close()
