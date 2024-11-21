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

# Функция для рендеринга шаблонов
def render_template(template_name, context):
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template(template_name)
    return template.render(context)

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
            welcome_message = render_template('welcome.html', {'name': name, 'referral_link': referral_link})
            bot.reply_to(message, welcome_message, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            bot.reply_to(message, "Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.")
    else:
        bot.reply_to(message, f"Привет, {name}! Вы уже зарегистрированы.")
        show_main_menu(message)
    conn.close()

# Функция для отображения главного меню
def show_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    balance_btn = types.KeyboardButton('/balance')
    withdraw_btn = types.KeyboardButton('/withdraw')
    donate_btn = types.KeyboardButton('/donate')
    subscribe_btn = types.KeyboardButton('/subscribe')
    markup.add(balance_btn, withdraw_btn, donate_btn, subscribe_btn)
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)

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
            # Проверяем, есть ли у пользователя кошелек
            cursor.execute("SELECT wallet_address FROM users WHERE telegram_id=?", (user_id,))
            wallet_address = cursor.fetchone()

            if not wallet_address:
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

# Административные команды
@bot.message_handler(commands=['admin_stats'])
def admin_stats(message):
    if message.from_user.id not in config.ADMIN_USER_IDS:
        bot.reply_to(message, "У вас нет доступа к этой команде.")
        return

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
    bot.reply_to(message, stats_message)

# Команда для управления доступами
@bot.message_handler(commands=['admin_manage_access'])
def admin_manage_access(message):
    if message.from_user.id not in config.ADMIN_USER_IDS:
        bot.reply_to(message, "У вас нет доступа к этой команде.")
        return

    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Используйте команду в формате: /admin_manage_access <user_id> <add/remove>")
        return

    user_id = int(args[1])
    action = args[2]

    if action == 'add':
        cursor.execute("UPDATE users SET status='privileged' WHERE telegram_id=?", (user_id,))
        bot.reply_to(message, f"Пользователь {user_id} добавлен в приватную комнату.")
    elif action == 'remove':
        cursor.execute("UPDATE users SET status='ordinary' WHERE telegram_id=?", (user_id,))
        bot.reply_to(message, f"Пользователь {user_id} удален из приватной комнаты.")
    else:
        bot.reply_to(message, "Неверная команда. Используйте 'add' или 'remove'.")

    conn.commit()

# Команда для просмотра истории транзакций
@bot.message_handler(commands=['admin_view_transactions'])
def admin_view_transactions(message):
    if message.from_user.id not in config.ADMIN_USER_IDS:
        bot.reply_to(message, "У вас нет доступа к этой команде.")
        return

    cursor.execute("SELECT * FROM transactions")
    transactions = cursor.fetchall()

    if transactions:
        transactions_message = "История транзакций:\n"
        for transaction in transactions:
            transactions_message += f"ID: {transaction[0]}, User ID: {transaction[1]}, Amount: {transaction[2]} TON, Type: {transaction[3]}, Date: {transaction[4]}\n"
        bot.reply_to(message, transactions_message)
    else:
        bot.reply_to(message, "Нет транзакций для отображения.")

# Команда для запланированных постов
@bot.message_handler(commands=['admin_schedule_post'])
def admin_schedule_post(message):
    if message.from_user.id not in config.ADMIN_USER_IDS:
        bot.reply_to(message, "У вас нет доступа к этой команде.")
        return

    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        bot.reply_to(message, "Используйте команду в формате: /admin_schedule_post <type> <date> <text>")
        return

    post_type = args[1]
    publication_date = args[2]
    text = args[3]

    try:
        publication_date = datetime.strptime(publication_date, '%Y-%m-%d %H:%M:%S')
        schedule_post(text, post_type, publication_date)
        bot.reply_to(message, "Пост успешно запланирован.")
    except Exception as e:
        logger.error(f"Error scheduling post: {e}")
        bot.reply_to(message, "Произошла ошибка при планировании поста. Пожалуйста, проверьте формат даты.")

# Еженедельные отчёты для администратора
def send_weekly_report():
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE status='privileged'")
    privileged_users = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='subscription'")
    total_subscriptions = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='donate'")
    total_donations = cursor.fetchone()[0]

    report_message = (
        f"Еженедельный отчёт:\n"
        f"Общее количество подписчиков: {total_users}\n"
        f"Количество привилегированных пользователей: {privileged_users}\n"
        f"Сумма подписок: {total_subscriptions} TON\n"
        f"Сумма донатов: {total_donations} TON"
    )

    for admin_id in config.ADMIN_USER_IDS:
        bot.send_message(admin_id, report_message)

# Запланированные посты
def schedule_post(text, post_type, publication_date):
    cursor.execute("INSERT INTO posts (text, type, publication_date) VALUES (?, ?, ?)",
                   (text, post_type, publication_date))
    conn.commit()

# Запуск бота
if __name__ == '__main__':
    bot.polling()

    # Запуск еженедельного отчёта
    import schedule
    import time

    schedule.every().monday.at("09:00").do(send_weekly_report)

    while True:
        schedule.run_pending()
        time.sleep(1)
