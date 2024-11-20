import unittest
from bot import bot, create_wallet, convert_rub_to_ton, start, subscribe, balance, withdraw, donate, handle_referral
import sqlite3

class TestIntegration(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                                id INTEGER PRIMARY KEY,
                                telegram_id INTEGER UNIQUE,
                                name TEXT,
                                wallet_address TEXT,
                                referral_link TEXT,
                                invited_count INTEGER DEFAULT 0,
                                status TEXT DEFAULT 'ordinary',
                                balance REAL DEFAULT 0.0)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
                                id INTEGER PRIMARY KEY,
                                user_id INTEGER,
                                amount REAL,
                                type TEXT,
                                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    def tearDown(self):
        self.conn.close()

    def test_full_flow(self):
        # Регистрация пользователя
        message = MagicMock()
        message.from_user.id = 1
        message.from_user.first_name = 'Test User'
        start(message)
        self.cursor.execute("SELECT * FROM users WHERE telegram_id=1")
        user = self.cursor.fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user[2], 'Test User')

        # Оплата подписки
        subscribe(message)
        self.cursor.execute("SELECT * FROM users WHERE telegram_id=1")
        user = self.cursor.fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user[3], 'test_wallet_address')

        # Донат
        donate(message)
        self.cursor.execute("SELECT * FROM users WHERE telegram_id=1")
        user = self.cursor.fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user[3], 'test_wallet_address')

        # Реферальная система
        referral_message = MagicMock()
        referral_message.from_user.id = 2
        referral_message.from_user.first_name = 'New User'
        referral_message.text = f'https://t.me/bot_name?start=1'
        handle_referral(referral_message)
        self.cursor.execute("SELECT * FROM users WHERE telegram_id=1")
        inviter = self.cursor.fetchone()
        self.assertEqual(inviter[5], 1)

        # Проверка баланса
        balance(message)
        self.cursor.execute("SELECT * FROM users WHERE telegram_id=1")
        user = self.cursor.fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user[7], 0.0)

        # Вывод средств
        withdraw(message)
        self.cursor.execute("SELECT * FROM users WHERE telegram_id=1")
        user = self.cursor.fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user[7], 0.0)

if __name__ == '__main__':
    unittest.main()