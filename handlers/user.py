import sqlite3
import logging
import config
from telebot import types
from tonclient.client import TonClient, ClientConfig
from tonclient.types import NetworkConfig, CryptoConfig
from telebot import TeleBot
from jinja2 import Environment, FileSystemLoader
from handlers.main_menu import show_main_menu

# Инициализация бота и логгера
bot = TeleBot(config.TELEGRAM_BOT_TOKEN)
logger = logging.getLogger(__name__)

# Функция для получения курсора базы данных
def get_cursor():
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    return cursor, conn

# Конфигурация TON client
client_config = ClientConfig(
    network=NetworkConfig(**config.TON_CLIENT_CONFIG['network']),
    crypto=CryptoConfig(),
    abi=config.TON_CLIENT_CONFIG['abi'],
    boc=config.TON_CLIENT_CONFIG['boc']
)
client = TonClient(config=client_config)

# Функция для рендеринга шаблонов
def render_template(template_name, context):
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template(template_name)
    return template.render(context)

# Команда для регистрации
def start(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    cursor, conn = get_cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        try:
            bot_username = bot.get_me().username # Получаем имя пользователя бота
            referral_link = f"https://t.me/{bot_username}?start={user_id}"
            cursor.execute("INSERT INTO users (telegram_id, name, referral_link) VALUES (?, ?, ?)",
                         (user_id, name, referral_link))
            conn.commit()
            welcome_message = render_template('welcome.html', {'name': name, 'referral_link': referral_link})
            bot.send_message(message.chat.id, welcome_message, parse_mode='HTML')
            show_main_menu(bot, message) # Показываем главное меню после приветственного сообщения
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            bot.send_message(message.chat.id, "Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.")
    else:
        bot.send_message(message.chat.id, f"Привет, {name}! Вы уже зарегистрированы.")
        show_main_menu(bot, message) # Показываем главное меню, если пользователь уже зарегистрирован
    conn.close()

# Регистрация команды /start
bot.register_message_handler(start, commands=['start'])

# Запуск бота
if __name__ == '__main__':
    bot.polling()