import unittest
from unittest.mock import patch, MagicMock
from bot import create_wallet, convert_rub_to_ton, start, subscribe, balance, withdraw, donate, handle_referral

class TestBot(unittest.TestCase):

    @patch('bot.client.processing.processing_create_wallet')
    def test_create_wallet(self, mock_create_wallet):
        mock_create_wallet.return_value = MagicMock(address='test_wallet_address')
        result = create_wallet()
        self.assertEqual(result, 'test_wallet_address')

    @patch('requests.get')
    def test_convert_rub_to_ton(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'result': 1.0}
        mock_get.return_value = mock_response
        result = convert_rub_to_ton(100)
        self.assertEqual(result, 1.0)

    @patch('bot.bot.reply_to')
    @patch('bot.cursor.fetchone')
    def test_start(self, mock_fetchone, mock_reply_to):
        mock_fetchone.return_value = None
        message = MagicMock()
        message.from_user.id = 1
        message.from_user.first_name = 'Test User'
        start(message)
        mock_reply_to.assert_called_once_with(message, 'Привет, Test User! Вы зарегистрированы. Ваша реферальная ссылка: https://t.me/bot_name?start=1')

    @patch('bot.bot.reply_to')
    @patch('bot.cursor.fetchone')
    def test_subscribe(self, mock_fetchone, mock_reply_to):
        mock_fetchone.return_value = (1, 'Test User', 'test_wallet_address', 'referral_link', 0, 'ordinary', 0.0)
        message = MagicMock()
        message.from_user.id = 1
        subscribe(message)
        mock_reply_to.assert_called_once_with(message, 'Для оплаты подписки переведите 1 TON на адрес: test_wallet_address')

    @patch('bot.bot.reply_to')
    @patch('bot.cursor.fetchone')
    def test_balance(self, mock_fetchone, mock_reply_to):
        mock_fetchone.return_value = (0.5,)
        message = MagicMock()
        message.from_user.id = 1
        balance(message)
        mock_reply_to.assert_called_once_with(message, 'Ваш текущий баланс: 0.5 TON')

    @patch('bot.bot.reply_to')
    @patch('bot.cursor.fetchone')
    def test_withdraw(self, mock_fetchone, mock_reply_to):
        mock_fetchone.return_value = (0.5, 'test_wallet_address')
        message = MagicMock()
        message.from_user.id = 1
        withdraw(message)
        mock_reply_to.assert_called_once_with(message, 'Средства успешно выведены на ваш кошелек: test_wallet_address')

    @patch('bot.bot.reply_to')
    @patch('bot.cursor.fetchone')
    def test_donate(self, mock_fetchone, mock_reply_to):
        mock_fetchone.return_value = (1, 'Test User', 'test_wallet_address', 'referral_link', 0, 'ordinary', 0.0)
        message = MagicMock()
        message.from_user.id = 1
        donate(message)
        mock_reply_to.assert_called_once_with(message, f'Для доната переведите любую сумму TON на адрес: YOUR_CHARITY_WALLET_ADDRESS')

    @patch('bot.bot.reply_to')
    @patch('bot.cursor.fetchone')
    @patch('bot.cursor.execute')
    def test_handle_referral(self, mock_execute, mock_fetchone, mock_reply_to):
        mock_fetchone.side_effect = [None, (1, 'Inviter User', 'inviter_wallet_address', 'referral_link', 4, 'ordinary', 0.0)]
        message = MagicMock()
        message.from_user.id = 2
        message.from_user.first_name = 'New User'
        message.text = 'https://t.me/bot_name?start=1'
        handle_referral(message)
        mock_reply_to.assert_any_call(message, 'Привет, New User! Вы зарегистрированы. Ваша реферальная ссылка: https://t.me/bot_name?start=2')
        mock_reply_to.assert_any_call(1, 'Поздравляем! Вы открыли доступ к эксклюзивной комнате!')

if __name__ == '__main__':
    unittest.main()