from telebot import types

def show_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    balance_btn = types.KeyboardButton('/balance')
    withdraw_btn = types.KeyboardButton('/withdraw')
    donate_btn = types.KeyboardButton('/donate')
    subscribe_btn = types.KeyboardButton('/subscribe')
    markup.add(balance_btn, withdraw_btn, donate_btn, subscribe_btn)
    message.reply_to(message, "Выберите действие:", reply_markup=markup)
