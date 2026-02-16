from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_keyboard():
    """Главное меню"""
    keyboard = [
        [
            InlineKeyboardButton("💝 Написать валентинку", callback_data="write_valentine"),
            InlineKeyboardButton("🔗 Реферальная ссылка", callback_data="referral_link")
        ],
        [
            InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats"),
            InlineKeyboardButton("❓ Помощь", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def cancel_keyboard():
    """Кнопка отмены"""
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    """Кнопка назад"""
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def confirm_keyboard():
    """Кнопки подтверждения"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Отправить", callback_data="confirm_send"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)