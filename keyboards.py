from telebot import types

def main_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("💝 Написать валентинку", callback_data="write_valentine"),
        types.InlineKeyboardButton("🔗 Реферальная ссылка", callback_data="referral_link"),
        types.InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats"),
        types.InlineKeyboardButton("❓ Помощь", callback_data="help")
    )
    return keyboard

def cancel_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return keyboard

def back_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return keyboard

def confirm_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("✅ Отправить", callback_data="confirm_send"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    )
    return keyboard