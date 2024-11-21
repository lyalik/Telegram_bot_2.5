import telebot
from telebot import types
from tonclient.client import TonClient, ClientConfig
from tonclient.types import ParamsOfEncodeMessage, ParamsOfSendMessage, ParamsOfSign
from tonclient.types import NetworkConfig, CryptoConfig
import requests
import sqlite3
import config
import threading
import logging
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, timedelta
from handlers import admin, main_menu, referral, subscription, transaction, user

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

lock = threading.Lock()

def get_cursor():
    with lock:
        conn = sqlite3.connect('bot.db', check_same_thread=False)
        cursor = conn.cursor()
        return cursor, conn

# Инициализация бота
bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN)

# Конфигурация TON client
client_config = ClientConfig(
    network=NetworkConfig(**config.TON_CLIENT_CONFIG['network']),
    crypto=CryptoConfig(),
    abi=config.TON_CLIENT_CONFIG['abi'],
    boc=config.TON_CLIENT_CONFIG['boc']
)
client = TonClient(config=client_config)

# Подключение к базе данных
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    telegram_id INTEGER UNIQUE,
                    name TEXT,
                    wallet_address TEXT,
                    referral_link TEXT,
                    invited_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'ordinary',
                    balance REAL DEFAULT 0.0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    amount REAL,
                    type TEXT,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY,
                    text TEXT,
                    type TEXT,
                    publication_date TIMESTAMP)''')
conn.commit()

# Регистрация команд
bot.register_message_handler(user.start, commands=['start'])
bot.register_message_handler(main_menu.show_main_menu, commands=['menu'])
bot.register_message_handler(subscription.subscribe, commands=['subscribe'])
bot.register_message_handler(transaction.balance, commands=['balance'])
bot.register_message_handler(transaction.withdraw, commands=['withdraw'])
bot.register_message_handler(transaction.donate, commands=['donate'])
bot.register_message_handler(referral.handle_referral, func=lambda message: message.text.startswith('https://t.me/'))
bot.register_message_handler(admin.admin_stats, commands=['admin_stats'])
bot.register_message_handler(admin.admin_manage_access, commands=['admin_manage_access'])
bot.register_message_handler(admin.admin_view_transactions, commands=['admin_view_transactions'])
bot.register_message_handler(admin.admin_schedule_post, commands=['admin_schedule_post'])

# Запуск бота
if __name__ == '__main__':
    bot.polling()

    # Запуск еженедельного отчёта
    import schedule
    import time

    schedule.every().monday.at("09:00").do(admin.send_weekly_report)

    while True:
        schedule.run_pending()
        time.sleep(1)
