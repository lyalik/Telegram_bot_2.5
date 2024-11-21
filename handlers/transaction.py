import sqlite3
import config
import logging
from telebot import types
from tonclient.types import ParamsOfEncodeMessage, ParamsOfSendMessage, ParamsOfSign
from tonclient.client import TonClient, ClientConfig
from tonclient.types import NetworkConfig, CryptoConfig

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

def balance(message):
    user_id = message.from_user.id
    cursor, conn = get_cursor()
    cursor.execute("SELECT balance FROM users WHERE telegram_id=?", (user_id,))
    balance = cursor.fetchone()
    if balance:
        message.reply_to(message, f"Ваш текущий баланс: {balance[0]} TON")
    else:
        message.reply_to(message, "Вы не зарегистрированы. Используйте команду /start для регистрации.")
    conn.close()

def withdraw(message):
    user_id = message.from_user.id
    cursor, conn = get_cursor()
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
                message.reply_to(message, f"Средства успешно выведены на ваш кошелек: {wallet_address}")
            except Exception as e:
                logger.error(f"Error withdrawing funds: {e}")
                message.reply_to(message, "Произошла ошибка при выводе средств. Пожалуйста, попробуйте позже.")
        else:
            message.reply_to(message, "У вас недостаточно средств для вывода.")
    else:
        message.reply_to(message, "Вы не зарегистрированы. Используйте команду /start для регистрации.")
    conn.close()

def donate(message):
    user_id = message.from_user.id
    cursor, conn = get_cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        message.reply_to(message, f"Для доната переведите любую сумму TON на адрес: {config.CHARITY_WALLET_ADDRESS}")
    else:
        message.reply_to(message, "Вы не зарегистрированы. Используйте команду /start для регистрации.")
    conn.close()
