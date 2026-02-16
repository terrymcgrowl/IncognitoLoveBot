import os
import logging
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import asyncio
from datetime import datetime, timezone
import re

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Импортируем ваши модули
from config import BOT_TOKEN, BOT_USERNAME
from database_supabase import Database
from keyboards import main_keyboard, back_keyboard, cancel_keyboard, confirm_keyboard

# Создаем подключение к базе данных
db = Database()

# Вспомогательная функция для склонения слов
def pluralize(number, one, few, many):
    """Склонение слов в зависимости от числа"""
    if number % 10 == 1 and number % 100 != 11:
        return one
    elif 2 <= number % 10 <= 4 and (number % 100 < 10 or number % 100 >= 20):
        return few
    else:
        return many

# Функция для расчета дней
def days_since(date_str):
    """Считает количество дней с указанной даты"""
    try:
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        return (now - date).days
    except:
        return 0

# Обработчик команды /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    username = user.username
    first_name = user.first_name
    
    # Логируем для отладки
    logger.info(f"🔥 Start command from user {user_id} with args: {context.args}")
    
    # Проверяем реферальный код
    referred_by = None
    if context.args and len(context.args) > 0:
        referral_code = context.args[0]
        logger.info(f"🔗 Referral code received: {referral_code}")
        
        # Ищем владельца кода в БД
        referred_by = db.get_user_by_referral(referral_code)
        logger.info(f"👤 Referred by user: {referred_by}")
    
    # Регистрируем пользователя
    db.add_user(user_id, username, first_name, referred_by)
    
    # ЕСЛИ ПЕРЕШЛИ ПО РЕФЕРАЛЬНОЙ ССЫЛКЕ - СРАЗУ ПРЕДЛОЖИТЬ НАПИСАТЬ
    if referred_by:
        # Получаем информацию о владельце ссылки
        try:
            owner = await context.bot.get_chat(referred_by)
            owner_username = owner.username
            owner_name = owner.first_name or "пользователю"
            
            logger.info(f"✅ Owner found: {owner_username} ({referred_by})")
            
            # Сохраняем получателя в временные данные
            context.user_data['recipient'] = {
                'to_user_id': referred_by,
                'to_username': owner_username,
                'is_referral': True  # Отмечаем, что это реферал
            }
            
            # Сразу запрашиваем текст валентинки
            display_name = f"@{owner_username}" if owner_username else f"ID: {referred_by}"
            await update.message.reply_text(
                f"💝 Вы перешли по ссылке от {display_name}!\n\n"
                f"Напишите текст валентинки для {owner_name} (до 500 символов):",
                reply_markup=cancel_keyboard()
            )
            context.user_data['state'] = 'waiting_message'
            return  # Выходим, не показываем главное меню
            
        except Exception as e:
            logger.error(f"❌ Ошибка при получении информации о владельце: {e}")
            # Если не получилось, показываем обычное меню
            pass
    
    # Обычное приветствие (если не реферал)
    welcome_text = (
        f"❤️ Привет, {first_name}!\n\n"
        "Я бот для анонимных валентинок. Ты можешь:\n"
        "💌 Отправлять анонимные сообщения\n"
        "🔗 Получить реферальную ссылку для приглашения друзей\n"
        "💝 Получать валентинки от других пользователей\n\n"
        "Выбери действие:"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=main_keyboard())

# Обработчик нажатий на кнопки
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "write_valentine":
        await query.edit_message_text(
            "📝 Введите **username** получателя (например: @durov) или его **Telegram ID**:\n\n"
            "✏️ Username можно узнать, нажав на профиль пользователя\n"
            "🔢 ID можно получить через специальные боты",
            reply_markup=cancel_keyboard()
        )
        # Сохраняем состояние - ждем ввод получателя
        context.user_data['state'] = 'waiting_recipient'
    
    elif query.data == "referral_link":
        await show_referral_link(query.message, context)
    
    elif query.data == "my_stats":
        await show_stats(query.message, context)
    
    elif query.data == "help":
        await show_help(query.message)
    
    elif query.data == "cancel":
        context.user_data.clear()
        await query.edit_message_text(
            "❌ Действие отменено. Выберите новое действие:",
            reply_markup=main_keyboard()
        )
    
    elif query.data == "back_to_menu":
        context.user_data.clear()
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=main_keyboard()
        )
    
    elif query.data == "confirm_send":
        await send_valentine(update, context)

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    state = context.user_data.get('state')
    
    if state == 'waiting_recipient':
        await process_recipient(update, context)
    elif state == 'waiting_message':
        await process_valentine_text(update, context)
    else:
        await update.message.reply_text(
            "Используйте кнопки меню для навигации.",
            reply_markup=main_keyboard()
        )

# Обработка ввода получателя
async def process_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем ввод получателя"""
    user_id = update.message.chat.id
    recipient_input = update.message.text.strip()
    
    # Проверяем формат ввода
    if recipient_input.startswith('@'):
        # Ввели username
        username = recipient_input[1:]  # убираем @
        try:
            # Пробуем получить информацию о пользователе
            user = await context.bot.get_chat(username)
            recipient_id = user.id
            recipient_username = username
            
            # Сохраняем во временные данные
            context.user_data['recipient'] = {
                'to_user_id': recipient_id,
                'to_username': recipient_username
            }
            
            # Запрашиваем текст валентинки
            await update.message.reply_text(
                f"✅ Получатель: @{recipient_username}\n\n"
                f"💝 Напишите текст валентинки (до 500 символов):",
                reply_markup=cancel_keyboard()
            )
            context.user_data['state'] = 'waiting_message'
            
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователя: {e}")
            await update.message.reply_text(
                "❌ Пользователь не найден. Проверьте username и попробуйте снова.\n"
                "Убедитесь, что пользователь существует и начал диалог с ботом.",
                reply_markup=back_keyboard()
            )
            context.user_data['state'] = None
    
    elif recipient_input.isdigit():
        # Ввели ID
        recipient_id = int(recipient_input)
        try:
            # Проверяем, существует ли такой ID
            user = await context.bot.get_chat(recipient_id)
            recipient_username = user.username
            
            # Сохраняем во временные данные
            context.user_data['recipient'] = {
                'to_user_id': recipient_id,
                'to_username': recipient_username
            }
            
            # Запрашиваем текст валентинки
            username_display = f"@{recipient_username}" if recipient_username else f"ID: {recipient_id}"
            await update.message.reply_text(
                f"✅ Получатель: {username_display}\n\n"
                f"💝 Напишите текст валентинки (до 500 символов):",
                reply_markup=cancel_keyboard()
            )
            context.user_data['state'] = 'waiting_message'
            
        except Exception as e:
            logger.error(f"Ошибка при поиске по ID: {e}")
            await update.message.reply_text(
                "❌ Пользователь с таким ID не найден или не начал диалог с ботом.",
                reply_markup=back_keyboard()
            )
            context.user_data['state'] = None
    else:
        await update.message.reply_text(
            "❌ Неверный формат. Введите @username или числовой ID.",
            reply_markup=back_keyboard()
        )
        context.user_data['state'] = None

# Обработка текста валентинки
async def process_valentine_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем текст валентинки"""
    user_id = update.message.chat.id
    text = update.message.text.strip()
    
    # Проверяем длину
    if len(text) > 500:
        await update.message.reply_text(
            "❌ Текст слишком длинный. Максимум 500 символов. Попробуйте снова:",
            reply_markup=cancel_keyboard()
        )
        return
    
    if len(text) < 2:
        await update.message.reply_text(
            "❌ Слишком короткое сообщение. Напишите что-нибудь (минимум 2 символа):",
            reply_markup=cancel_keyboard()
        )
        return
    
    # Сохраняем текст
    if 'recipient' in context.user_data:
        context.user_data['recipient']['message'] = text
        
        # Показываем предпросмотр
        recipient = context.user_data['recipient']
        recipient_display = f"@{recipient['to_username']}" if recipient['to_username'] else f"ID: {recipient['to_user_id']}"
        
        # Если это реферал, показываем специальное сообщение
        if recipient.get('is_referral'):
            preview = (
                f"📋 **Валентинка для пригласившего вас друга:**\n\n"
                f"**Кому:** {recipient_display}\n"
                f"**Текст:**\n{text}\n\n"
                f"Отправляем? Сообщение будет полностью анонимным!"
            )
        else:
            preview = (
                f"📋 **Предпросмотр валентинки:**\n\n"
                f"**Кому:** {recipient_display}\n"
                f"**Текст:**\n{text}\n\n"
                f"Отправляем? Сообщение будет полностью анонимным!"
            )
        
        await update.message.reply_text(
            preview,
            reply_markup=confirm_keyboard(),
            parse_mode="Markdown"
        )
        context.user_data['state'] = 'confirming'
    else:
        await update.message.reply_text(
            "❌ Произошла ошибка. Начните заново.",
            reply_markup=main_keyboard()
        )
        context.user_data.clear()

# Отправка валентинки
async def send_valentine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляем валентинку"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if 'recipient' not in context.user_data:
        await query.edit_message_text(
            "❌ Данные не найдены. Начните заново.",
            reply_markup=main_keyboard()
        )
        context.user_data.clear()
        return
    
    valentine = context.user_data['recipient']
    
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
            await context.bot.send_message(
                chat_id=valentine['to_user_id'],
                text=delivery_text,
                parse_mode="Markdown"
            )
            
            # Отправляем подтверждение отправителю
            await query.edit_message_text(
                "✅ **Валентинка успешно доставлена!**\n\n"
                "Получатель уже прочитал ваше анонимное сообщение.",
                reply_markup=main_keyboard(),
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Ошибка доставки: {e}")
            await query.edit_message_text(
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
        await query.edit_message_text(
            "❌ Ошибка при сохранении валентинки. Попробуйте позже.",
            reply_markup=main_keyboard()
        )
    
    context.user_data.clear()

# Показать реферальную ссылку
async def show_referral_link(message, context: ContextTypes.DEFAULT_TYPE):
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
            "По этой ссылке друзья смогут сразу отправить тебе анонимную валентинку!"
        )
        
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=back_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Ошибка получения реферальной ссылки.",
            reply_markup=back_keyboard()
        )

# Показать статистику
async def show_stats(message, context: ContextTypes.DEFAULT_TYPE):
    """Показываем статистику пользователя"""
    user_id = message.chat.id
    
    try:
        stats = db.get_user_stats(user_id)
        logger.info(f"Статистика для {user_id}: {stats}")
        
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
        
        await context.bot.send_message(
            chat_id=user_id,
            text=stats_text,
            reply_markup=back_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в show_stats: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Произошла ошибка при получении статистики.",
            reply_markup=back_keyboard()
        )

# Показать помощь
async def show_help(message):
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
        "• Когда друг перейдет по ссылке, он сможет сразу отправить тебе валентинку\n\n"
        "📊 **Статистика**\n"
        "• Отслеживай количество отправленных и полученных валентинок\n"
        "• Смотри, сколько друзей пригласил\n\n"
        "🔒 **Анонимность**\n"
        "• Все сообщения полностью анонимны\n"
        "• Получатель не узнает, кто отправитель\n"
        "• Ответить на анонимное сообщение нельзя"
    )
    
    await message.reply_text(help_text, reply_markup=back_keyboard(), parse_mode="Markdown")

# Главная функция
async def main():
    """Главная функция для запуска бота на Render"""
    logger.info("🔧 Начало инициализации бота")
    
    # Создаем приложение Telegram бота
    application = Application.builder().token(BOT_TOKEN).build()
    logger.info("✅ Application создан")
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Получаем URL от Render
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        logger.error("❌ RENDER_EXTERNAL_URL не найден!")
        return
    
    # Сбрасываем и устанавливаем вебхук
    webhook_url = f"{render_url}/telegram"
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("🔄 Старый вебхук удален")
    
    await application.bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Вебхук установлен на {webhook_url}")
    
    # Проверка вебхука
    webhook_info = await application.bot.get_webhook_info()
    logger.info(f"📊 Информация о вебхуке: {webhook_info}")
    
    # Создаем Starlette приложение для веб-сервера
    async def telegram_webhook(request: Request) -> Response:
        """Обработчик вебхука от Telegram"""
        try:
            data = await request.json()
            update = Update.de_json(data, application.bot)
            await application.process_update(update)
            return Response()
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return Response(status_code=500)
    
    async def health_check(request: Request) -> PlainTextResponse:
        """Проверка здоровья"""
        return PlainTextResponse("OK")
    
    async def root(request: Request) -> PlainTextResponse:
        """Корневой маршрут"""
        return PlainTextResponse("🤖 Бот для анонимных валентинок работает!")
    
    # Создаем Starlette приложение
    app = Starlette(routes=[
        Route("/telegram", telegram_webhook, methods=["POST"]),
        Route("/health", health_check, methods=["GET"]),
        Route("/", root, methods=["GET"]),
    ])
    
    # Запускаем сервер
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    # Запускаем бота и сервер
    async with application:
        await application.start()
        logger.info("🚀 Бот запущен и готов к работе!")
        await server.serve()
        await application.stop()

if __name__ == "__main__":
    asyncio.run(main())