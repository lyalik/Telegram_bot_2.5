# config.py1
TELEGRAM_BOT_TOKEN = '7554899021:AAFLbYwilRZtAc0NrtRmJPHWhHXk06bG2r8'
TON_CLIENT_CONFIG = {
    'network': {
        'server_address': 'https://testnet.toncenter.com/api/v2/jsonRPC',
        'send_retries': 3,
        'message_retries': 3,
        'message_processing_timeout': 30
    },
    'crypto': {
        'mnemonic_dict': 1,
        'hdpath': "m/44'/396'/0'/0/0",
        'keypair_type': 1,
        'api_key': 'YOUR_TON_API_KEY'
    },
    'abi': {},
    'boc': {}
}
EXCHANGE_API_URL = 'https://api.exchange.com/convert'
TON_API_KEY = '7e871f1f84625ca426bc2f4da176035b6fb502b7280604d420aa2a1789c6571c'
CHARITY_WALLET_ADDRESS = 'YOUR_CHARITY_WALLET_ADDRESS'
MAIN_ACCOUNT_WALLET_ADDRESS = 'YOUR_MAIN_ACCOUNT_WALLET_ADDRESS'