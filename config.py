import os
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# TON Client Configuration
TON_CLIENT_CONFIG = {
    'network': {
        'server_address': 'https://testnet.toncenter.com/api/v2/jsonRPC',
        'endpoints': ['https://testnet.toncenter.com/api/v2/jsonRPC']
    },
    'crypto': {
        'mnemonic_dict': 1,
        'hdpath': "m/44'/396'/0'/0/0",
        'keypair_type': 1,
        'api_key': os.getenv('TON_API_KEY')
    },
    'abi': {},
    'boc': {}
}

# Exchange API Configuration
EXCHANGE_API_URL = 'https://api.exchange.com/convert'
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY')

# Wallet Addresses
CHARITY_WALLET_ADDRESS = os.getenv('CHARITY_WALLET_ADDRESS')
MAIN_ACCOUNT_WALLET_ADDRESS = os.getenv('MAIN_ACCOUNT_WALLET_ADDRESS')

# Admin User IDs
ADMIN_USER_IDS = [int(id) for id in os.getenv('ADMIN_USER_IDS', '').split(',')]