import sqlite3
import logging
from telebot import types
from tonclient.types import ParamsOfEncodeMessage, ParamsOfSendMessage
from tonclient.client import TonClient, ClientConfig
from tonclient.types import NetworkConfig, CryptoConfig
import config
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

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

# Функция для создания кошелька TON
def create_wallet():
    try:
        with open('wallet.abi.json', 'r') as f:
            wallet_abi = f.read()
        with open('wallet.tvc', 'rb') as f:
            wallet_tvc = f.read()

        params = ParamsOfEncodeMessage(
            abi=wallet_abi,
            deploy_set={"tvc": wallet_tvc, "initial_data": {}},
            call_set=None,
            signer=None
        )
        encoded_message = client.abi.encode_message(params=params)

        send_params = ParamsOfSendMessage(
            message=encoded_message.message,
            send_events=False
        )
        result = client.net.send_message(params=send_params)

        return encoded_message.address
    except Exception as e:
        logger.error(f"Error creating wallet: {e}")
        raise

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
            wallet_address = create_wallet()
            referral_link = f"https://t.me/{message.bot.get_me().username}?start={user_id}"
            cursor.execute("INSERT INTO users (telegram_id, name, wallet_address, referral_link) VALUES (?, ?, ?, ?)",
                           (user_id, name, wallet_address, referral_link))
            conn.commit()
            welcome_message = render_template('welcome.html', {'name': name, 'referral_link': referral_link})
            message.reply_to(message, welcome_message, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            message.reply_to(message, "Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.")
    else:
        message.reply_to(message, f"Привет, {name}! Вы уже зарегистрированы.")
        show_main_menu(message)
    conn.close()
