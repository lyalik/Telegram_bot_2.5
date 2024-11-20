import telebot
from tonclient.client import TonClient, ClientConfig
from tonclient.types import ParamsOfCreateWallet, ParamsOfTransfer
import requests
import sqlite3
import config

# Инициализация бота
bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN)

# Конфигурация TON client
client_config = ClientConfig(
    network=config.TON_CLIENT_CONFIG['network'],
    crypto={
        'mnemonic_dict': config.TON_CLIENT_CONFIG['crypto']['mnemonic_dict'],
        'hdpath': config.TON_CLIENT_CONFIG['crypto']['hdpath'],
        'keypair_type': config.TON_CLIENT_CONFIG['crypto']['keypair_type'],
        'api_key': config.TON_API_KEY  # Добавьте API ключ здесь
    },
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


# Функция для создания кошелька TON
def create_wallet():
    params = ParamsOfCreateWallet(workchain=0)
    result = client.processing.processing_create_wallet(params=params)
    return result.address


# Функция для конвертации рублей в TON
def convert_rub_to_ton(amount_rub):
    headers = {'Authorization': f'Bearer {config.EXCHANGE_API_KEY}'}
    response = requests.get(f'{config.EXCHANGE_API_URL}?from=RUB&to=TON&amount={amount_rub}', headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data['result']
    else:
        raise Exception('Failed to convert RUB to TON')


# Команда для регистрации
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        wallet_address = create_wallet()
        referral_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        cursor.execute("INSERT INTO users (telegram_id, name, wallet_address, referral_link) VALUES (?, ?, ?, ?)",
                       (user_id, name, wallet_address, referral_link))
        conn.commit()
        bot.reply_to(message, f"Привет, {name}! Вы зарегистрированы. Ваша реферальная ссылка: {referral_link}")
    else:
        bot.reply_to(message, f"Привет, {name}! Вы уже зарегистрированы.")


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
    balance = cursor.fetchone()[0]
    bot.reply_to(message, f"Ваш текущий баланс: {balance} TON")


# Команда для вывода средств
@bot.message_handler(commands=['withdraw'])
def withdraw(message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance, wallet_address FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        balance, wallet_address = user
        if balance > 0:
            params = ParamsOfTransfer(address=wallet_address, amount=int(balance * 1e9))
            client.processing.processing_transfer(params=params)
            cursor.execute("UPDATE users SET balance=0 WHERE telegram_id=?", (user_id,))
            conn.commit()
            bot.reply_to(message, f"Средства успешно выведены на ваш кошелек: {wallet_address}")
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


# Запуск бота
if __name__ == '__main__':
    bot.polling()