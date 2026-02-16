import telebot
from telebot import types
from config import BOT_TOKEN, BOT_USERNAME
from database_supabase import Database
from keyboards import main_keyboard, back_keyboard, cancel_keyboard, confirm_keyboard
import re
from datetime import datetime, timezone


bot = telebot.TeleBot(BOT_TOKEN)
db = Database()

# Хранилище временных данных (в памяти, не в БД)
# Нужно, чтобы помнить, кому пользователь пишет валентинку
temp_data = {}

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name   
    
    # Проверяем, есть ли реферальный код в ссылке
    referred_by = None
    if len(message.text.split()) > 1:
        referral_code = message.text.split()[1]
        referred_by = db.get_user_by_referral(referral_code)
        if referred_by:
            bot.send_message(referred_by, f"🎉 По вашей реферальной ссылке зарегистрировался новый пользователь {first_name}!")
    
    # Регистрируем пользователя
    db.add_user(user_id, username, first_name, referred_by)
    
    welcome_text = (
        f"❤️ Привет, {first_name}!\n\n"
        "Я бот для анонимных валентинок. Ты можешь:\n"
        "💌 Отправлять анонимные сообщения\n"
        "🔗 Получить реферальную ссылку для приглашения друзей\n"
        "💝 Получать валентинки от других пользователей\n\n"
        "Выбери действие:"
    )
    
    bot.send_message(user_id, welcome_text, reply_markup=main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "write_valentine":
        # Начинаем процесс написания валентинки
        msg = bot.send_message(
            call.message.chat.id,
            "📝 Введите **username** получателя (например: @durov) или его **Telegram ID**:\n\n"
            "✏️ Username можно узнать, нажав на профиль пользователя\n"
            "🔢 ID можно получить через специальные боты",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_recipient)
    
    elif call.data == "referral_link":
        show_referral_link(call.message)
    
    elif call.data == "my_stats":
        show_stats(call.message)
    
    elif call.data == "help":
        show_help(call.message)
    
    elif call.data == "cancel":
        # Очищаем временные данные
        if call.message.chat.id in temp_data:
            del temp_data[call.message.chat.id]
        bot.clear_step_handler(call.message)
        bot.edit_message_text(
            "❌ Действие отменено. Выберите новое действие:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_keyboard()
        )
    
    elif call.data == "back_to_menu":
        bot.edit_message_text(
            "Главное меню:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_keyboard()
        )
    
    elif call.data == "confirm_send":
        # Подтверждение отправки валентинки
        send_valentine(call.message)

def process_recipient(message):
    """Обрабатываем ввод получателя"""
    user_id = message.chat.id
    recipient_input = message.text.strip()
    
    # Проверяем формат ввода
    if recipient_input.startswith('@'):
        # Ввели username
        username = recipient_input[1:]  # убираем @
        try:
            # Пробуем получить информацию о пользователе
            user = bot.get_chat(username)
            recipient_id = user.id
            recipient_username = username
            
            # Сохраняем в временные данные
            temp_data[user_id] = {
                'to_user_id': recipient_id,
                'to_username': recipient_username
            }
            
            # Запрашиваем текст валентинки
            msg = bot.send_message(
                user_id,
                f"✅ Получатель: @{recipient_username}\n\n"
                f"💝 Напишите текст валентинки (до 500 символов):",
                reply_markup=cancel_keyboard()
            )
            bot.register_next_step_handler(msg, process_valentine_text)
            
        except Exception as e:
            bot.send_message(
                user_id,
                "❌ Пользователь не найден. Проверьте username и попробуйте снова.\n"
                "Убедитесь, что пользователь существует и начал диалог с ботом.",
                reply_markup=back_keyboard()
            )
    
    elif recipient_input.isdigit():
        # Ввели ID
        recipient_id = int(recipient_input)
        try:
            # Проверяем, существует ли такой ID
            user = bot.get_chat(recipient_id)
            recipient_username = user.username
            
            # Сохраняем в временные данные
            temp_data[user_id] = {
                'to_user_id': recipient_id,
                'to_username': recipient_username
            }
            
            # Запрашиваем текст валентинки
            username_display = f"@{recipient_username}" if recipient_username else f"ID: {recipient_id}"
            msg = bot.send_message(
                user_id,
                f"✅ Получатель: {username_display}\n\n"
                f"💝 Напишите текст валентинки (до 500 символов):",
                reply_markup=cancel_keyboard()
            )
            bot.register_next_step_handler(msg, process_valentine_text)
            
        except Exception as e:
            bot.send_message(
                user_id,
                "❌ Пользователь с таким ID не найден или не начал диалог с ботом.",
                reply_markup=back_keyboard()
            )
    else:
        bot.send_message(
            user_id,
            "❌ Неверный формат. Введите @username или числовой ID.",
            reply_markup=back_keyboard()
        )

def process_valentine_text(message):
    """Обрабатываем текст валентинки"""
    user_id = message.chat.id
    text = message.text.strip()
    
    # Проверяем длину
    if len(text) > 500:
        bot.send_message(
            user_id,
            "❌ Текст слишком длинный. Максимум 500 символов. Попробуйте снова:",
            reply_markup=cancel_keyboard()
        )
        bot.register_next_step_handler(message, process_valentine_text)
        return
    
    if len(text) < 2:
        bot.send_message(
            user_id,
            "❌ Слишком короткое сообщение. Напишите что-нибудь (минимум 2 символа):",
            reply_markup=cancel_keyboard()
        )
        bot.register_next_step_handler(message, process_valentine_text)
        return
    
    # Сохраняем текст во временные данные
    if user_id in temp_data:
        temp_data[user_id]['message'] = text
        
        # Показываем предпросмотр и просим подтверждение
        recipient = temp_data[user_id]
        recipient_display = f"@{recipient['to_username']}" if recipient['to_username'] else f"ID: {recipient['to_user_id']}"
        
        preview = (
            f"📋 **Предпросмотр валентинки:**\n\n"
            f"**Кому:** {recipient_display}\n"
            f"**Текст:**\n{text}\n\n"
            f"Отправляем? Сообщение будет полностью анонимным!"
        )
        
        bot.send_message(
            user_id,
            preview,
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown"
        )
    else:
        # Что-то пошло не так, начинаем заново
        bot.send_message(
            user_id,
            "❌ Произошла ошибка. Начните заново.",
            reply_markup=main_keyboard()
        )

def send_valentine(message):
    """Отправляем валентинку"""
    user_id = message.chat.id
    
    if user_id not in temp_data:
        bot.send_message(user_id, "❌ Данные не найдены. Начните заново.", reply_markup=main_keyboard())
        return
    
    valentine = temp_data[user_id]
    
    # Сохраняем в базу данных
    valentine_id = db.save_valentine(
        from_user_id=user_id,
        to_user_id=valentine['to_user_id'],
        to_username=valentine['to_username'],
        message=valentine['message']
    )
    
    if valentine_id:
        # Пытаемся отправить получателю
        try:
            delivery_text = (
                "💌 **Вам пришла анонимная валентинка!**\n\n"
                f"{valentine['message']}\n\n"
                "_Это сообщение анонимное, ответить на него нельзя._"
            )
            bot.send_message(
                valentine['to_user_id'],
                delivery_text,
                parse_mode="Markdown"
            )
            
            # Отправляем подтверждение отправителю
            bot.send_message(
                user_id,
                "✅ **Валентинка успешно доставлена!**\n\n"
                "Получатель уже прочитал ваше анонимное сообщение.",
                reply_markup=main_keyboard(),
                parse_mode="Markdown"
            )
            
        except Exception as e:
            # Не удалось доставить
            bot.send_message(
                user_id,
                "⚠️ **Валентинка сохранена, но не доставлена**\n\n"
                "Возможные причины:\n"
                "• Пользователь заблокировал бота\n"
                "• Пользователь не начал диалог с ботом\n"
                "• Пользователь удалил аккаунт\n\n"
                "Когда пользователь запустит бота, он сможет прочитать валентинку!",
                reply_markup=main_keyboard(),
                parse_mode="Markdown"
            )
    else:
        bot.send_message(
            user_id,
            "❌ Ошибка при сохранении валентинки. Попробуйте позже.",
            reply_markup=main_keyboard()
        )
    
    # Очищаем временные данные
    del temp_data[user_id]

def show_referral_link(message):
    """Показываем реферальную ссылку"""
    user_id = message.chat.id
    referral_code = db.get_referral_code(user_id)
    
    if referral_code:
        referral_link = f"https://t.me/{BOT_USERNAME}?start={referral_code}"
        referrals_count = db.get_referral_stats(user_id)
        
        text = (
            f"🔗 **Твоя реферальная ссылка:**\n\n"
            f"`{referral_link}`\n\n"
            f"📊 **Приглашено друзей: {referrals_count}**\n\n"
            "✨ Размести эту ссылку на своей странице или отправь друзьям!\n"
            "За каждого приглашенного друга ты получишь уведомление."
        )
        
        bot.send_message(
            user_id,
            text,
            reply_markup=back_keyboard(),
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            user_id,
            "❌ Ошибка получения реферальной ссылки.",
            reply_markup=back_keyboard()
        )

def days_since(date_str):
    """Считает количество дней с указанной даты"""
    # Парсим дату из строки
    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    
    # Текущее время в UTC
    now = datetime.now(timezone.utc)
    
    # Разница в днях
    return (now - date).days

def show_stats(message):
    """Показываем статистику пользователя"""
    user_id = message.chat.id
    
    try:
        stats = db.get_user_stats(user_id)
        
        # Получаем дату регистрации
        user_info = db.supabase.table("users")\
            .select("joined_date")\
            .eq("user_id", user_id)\
            .execute()
        
        if user_info.data:
            days = days_since(user_info.data[0]['joined_date'])
            
            stats_text = (
                f"📊 **Твоя статистика:**\n\n"
                f"📅 С нами уже **{days}** {pluralize(days, 'день', 'дня', 'дней')}\n"
                f"💝 Отправлено валентинок: **{stats['sent']}**\n"
                f"💌 Получено валентинок: **{stats['received']}**\n"
                f"👥 Приглашено друзей: **{stats['referrals']}**"
            )
        else:
            stats_text = (
                f"📊 **Твоя статистика:**\n\n"
                f"💝 Отправлено валентинок: **{stats['sent']}**\n"
                f"💌 Получено валентинок: **{stats['received']}**\n"
                f"👥 Приглашено друзей: **{stats['referrals']}**"
            )
        
        bot.send_message(user_id, stats_text, reply_markup=back_keyboard(), parse_mode="Markdown")
        
    except Exception as e:
        print(f"❌ ОШИБКА в show_stats: {e}")
        import traceback
        traceback.print_exc()
        bot.send_message(
            user_id, 
            "❌ Произошла ошибка при получении статистики.",
            reply_markup=back_keyboard()
        )


def show_help(message):
    """Показываем справку"""
    help_text = (
        "❓ **Помощь по использованию бота:**\n\n"
        "💝 **Как отправить валентинку?**\n"
        "1. Нажми 'Написать валентинку'\n"
        "2. Введи @username или ID получателя\n"
        "3. Напиши текст сообщения\n"
        "4. Подтверди отправку\n\n"
        "🔗 **Реферальная система**\n"
        "• Получи свою уникальную ссылку в разделе 'Реферальная ссылка'\n"
        "• Размести её в соцсетях или отправь друзьям\n"
        "• Когда друг перейдет по ссылке, ты получишь уведомление\n\n"
        "📊 **Статистика**\n"
        "• Отслеживай количество отправленных и полученных валентинок\n"
        "• Смотри, сколько друзей пригласил\n\n"
        "🔒 **Анонимность**\n"
        "• Все сообщения полностью анонимны\n"
        "• Получатель не узнает, кто отправитель\n"
        "• Ответить на анонимное сообщение нельзя"
    )
    
    bot.send_message(message.chat.id, help_text, reply_markup=back_keyboard(), parse_mode="Markdown")

def pluralize(number, one, few, many):
    """Вспомогательная функция для склонения слов"""
    if number % 10 == 1 and number % 100 != 11:
        return one
    elif 2 <= number % 10 <= 4 and (number % 100 < 10 or number % 100 >= 20):
        return few
    else:
        return many

if __name__ == '__main__':
    print("✅ Бот запущен...")
    print("📦 База данных: Supabase")
    print("💝 Функционал валентинок активирован")
    print("🔄 Ожидание команд...")
    bot.infinity_polling()