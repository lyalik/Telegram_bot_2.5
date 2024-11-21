import telebot
from tonclient.client import TonClient, ClientConfig
from tonclient.types import ParamsOfEncodeMessage, ParamsOfSendMessage, ParamsOfSign
from tonclient.types import NetworkConfig, CryptoConfig
import requests
import sqlite3
import config
import threading
import logging

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
conn.commit()

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

# Функция для конвертации рублей в TON
def convert_rub_to_ton(amount_rub):
    try:
        headers = {'Authorization': f'Bearer {config.EXCHANGE_API_KEY}'}
        response = requests.get(f'{config.EXCHANGE_API_URL}?from=RUB&to=TON&amount={amount_rub}', headers=headers)
        response.raise_for_status()
        data = response.json()
        return data['result']
    except Exception as e:
        logger.error(f"Error converting RUB to TON: {e}")
        raise

# Команда для регистрации
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    cursor, conn = get_cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        try:
            wallet_address = create_wallet()
            referral_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
            cursor.execute("INSERT INTO users (telegram_id, name, wallet_address, referral_link) VALUES (?, ?, ?, ?)",
                           (user_id, name, wallet_address, referral_link))
            conn.commit()
            bot.reply_to(message, f"Привет, {name}! Вы успешно зарегистрированы.")
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            bot.reply_to(message, "Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.")
    else:
        bot.reply_to(message, f"Привет, {name}! Вы уже зарегистрированы.")
    conn.close()

# Команда для оплаты подписки
@bot.message_handler(commands=['subscribe'])
def subscribe(message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        wallet_address = user[3]
        bot.reply_to(message, f"Для оплаты подписки переведите 1 TON на адрес: {wallet_address}")
    else:
        bot.reply_to(message, "Вы не зарегистрированы. Используйте команду /start для регистрации.")

# Команда для проверки баланса
@bot.message_handler(commands=['balance'])
def balance(message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE telegram_id=?", (user_id,))
    balance = cursor.fetchone()
    if balance:
        bot.reply_to(message, f"Ваш текущий баланс: {balance[0]} TON")
    else:
        bot.reply_to(message, "Вы не зарегистрированы. Используйте команду /start для регистрации.")

# Команда для вывода средств
@bot.message_handler(commands=['withdraw'])
def withdraw(message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance, wallet_address FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        balance, wallet_address = user
        if balance > 0:
            try:
                with open('wallet.abi.json', 'r') as f:
                    wallet_abi = f.read()

                call_set = {
                    "function_name": "sendTransaction",
                    "input": {
                        "dest": wallet_address,
                        "value": int(balance * 1e9),
                        "bounce": False,
                        "flags": 1,
                        "payload": ""
                    }
                }

                params = ParamsOfEncodeMessage(
                    abi=wallet_abi,
                    address=wallet_address,
                    deploy_set=None,
                    call_set=call_set,
                    signer=None
                )
                encoded_message = client.abi.encode_message(params=params)

                keypair = client.crypto.generate_random_sign_keys()
                sign_params = ParamsOfSign(
                    unsigned=encoded_message.message,
                    keys=keypair
                )
                signed_message = client.crypto.sign(params=sign_params)

                send_params = ParamsOfSendMessage(
                    message=signed_message.signed,
                    send_events=False
                )
                result = client.net.send_message(params=send_params)

                cursor.execute("UPDATE users SET balance=0 WHERE telegram_id=?", (user_id,))
                conn.commit()
                bot.reply_to(message, f"Средства успешно выведены на ваш кошелек: {wallet_address}")
            except Exception as e:
                logger.error(f"Error withdrawing funds: {e}")
                bot.reply_to(message, "Произошла ошибка при выводе средств. Пожалуйста, попробуйте позже.")
        else:
            bot.reply_to(message, "У вас недостаточно средств для вывода.")
    else:
        bot.reply_to(message, "Вы не зарегистрированы. Используйте команду /start для регистрации.")

# Команда для доната
@bot.message_handler(commands=['donate'])
def donate(message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        bot.reply_to(message, f"Для доната переведите любую сумму TON на адрес: {config.CHARITY_WALLET_ADDRESS}")
    else:
        bot.reply_to(message, "Вы не зарегистрированы. Используйте команду /start для регистрации.")

# Обработка реферальных ссылок
@bot.message_handler(func=lambda message: message.text.startswith('https://t.me/'))
def handle_referral(message):
    referral_link = message.text
    referral_code = referral_link.split('=')[-1]
    inviter_id = int(referral_code)

    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        bot.reply_to(message, "Вы уже зарегистрированы.")
    else:
        try:
            wallet_address = create_wallet()
            referral_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
            cursor.execute("INSERT INTO users (telegram_id, name, wallet_address, referral_link) VALUES (?, ?, ?, ?)",
                           (user_id, message.from_user.first_name, wallet_address, referral_link))

            cursor.execute("UPDATE users SET invited_count=invited_count+1 WHERE telegram_id=?", (inviter_id,))
            cursor.execute("SELECT invited_count FROM users WHERE telegram_id=?", (inviter_id,))
            invited_count = cursor.fetchone()[0]

            if invited_count >= 5:
                cursor.execute("UPDATE users SET status='privileged' WHERE telegram_id=?", (inviter_id,))
                bot.send_message(inviter_id, "Поздравляем! Вы открыли доступ к эксклюзивной комнате!")

            conn.commit()
            bot.reply_to(message,
                         f"Привет, {message.from_user.first_name}! Вы зарегистрированы. Ваша реферальная ссылка: {referral_link}")
        except Exception as e:
            logger.error(f"Error handling referral: {e}")
            bot.reply_to(message, "Произошла ошибка при обработке реферальной ссылки. Пожалуйста, попробуйте позже.")

# Запуск бота
if __name__ == '__main__':
    bot.polling()
