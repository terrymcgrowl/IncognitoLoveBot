import os
from supabase import create_client, Client
from datetime import datetime
import random
import string
import time
import logging
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        # Подключаемся к Supabase
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        self.supabase: Client = create_client(url, key)
        logger.info("✅ Подключение к Supabase установлено")
    
    def _generate_unique_referral_code(self, length=10):
        """Генерирует уникальный реферальный код"""
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                code = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
                
                existing = self.supabase.table("users")\
                    .select("user_id")\
                    .eq("referral_code", code)\
                    .execute()
                
                if not existing.data:
                    return code
                    
                logger.info(f"🔄 Коллизия, пробуем снова (попытка {attempt + 1})")
                
            except Exception as e:
                logger.error(f"❌ Ошибка при генерации кода: {e}")
                if attempt == max_attempts - 1:
                    # Если все попытки неудачны, генерируем код с timestamp
                    return f"TEMP{int(time.time())}"[:length]
        
        return f"CODE{random.randint(1000, 9999)}"
    
    def add_user(self, user_id, username, first_name, referred_by=None):
        """Добавляем нового пользователя"""
        
        # Генерируем уникальный реферальный код
        referral_code = self._generate_unique_referral_code()
        
        # Данные для вставки - обрабатываем None значения
        user_data = {
            "user_id": user_id,
            "username": username if username else None,
            "first_name": first_name,
            "referral_code": referral_code,
            "referred_by": referred_by,
            "joined_date": datetime.now().isoformat()
        }
        
        try:
            # Вставляем или обновляем пользователя
            response = self.supabase.table("users").upsert(user_data).execute()
            logger.info(f"✅ Пользователь {user_id} добавлен с кодом {referral_code}")
            
            # Если есть реферал, записываем это отдельно
            if referred_by:
                referral_data = {
                    "referrer_id": referred_by,
                    "referred_id": user_id,
                    "date": datetime.now().isoformat()
                }
                self.supabase.table("referrals").insert(referral_data).execute()
                logger.info(f"✅ Реферал записан: {referred_by} -> {user_id}")
            
            return response
        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении пользователя {user_id}: {e}")
            return None
    
    def get_referral_code(self, user_id):
        """Получаем реферальный код пользователя"""
        try:
            response = self.supabase.table("users")\
                .select("referral_code")\
                .eq("user_id", user_id)\
                .execute()
            
            if response.data:
                code = response.data[0]["referral_code"]
                logger.info(f"✅ Реферальный код для {user_id}: {code}")
                return code
            logger.warning(f"⚠️ Реферальный код для {user_id} не найден")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка при получении реферального кода для {user_id}: {e}")
            return None
    
    def get_user_by_referral(self, referral_code):
        """Ищем пользователя по реферальному коду"""
        try:
            logger.info(f"🔍 Поиск пользователя по коду: {referral_code}")
            response = self.supabase.table("users")\
                .select("user_id")\
                .eq("referral_code", referral_code)\
                .execute()
            
            if response.data and len(response.data) > 0:
                user_id = response.data[0]["user_id"]
                logger.info(f"✅ Найден пользователь: {user_id}")
                return user_id
            
            logger.warning(f"❌ Пользователь с кодом {referral_code} не найден")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка при поиске по реферальному коду {referral_code}: {e}")
            return None
    
    def save_valentine(self, from_user_id, to_user_id, to_username, message):
        """Сохраняем валентинку"""
        
        # Обрабатываем случай, когда у получателя нет username
        if to_username:
            to_username = str(to_username).replace('@', '')
        else:
            to_username = None
        
        valentine_data = {
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "to_username": to_username,
            "message": message,
            "created_date": datetime.now().isoformat(),
            "is_delivered": False
        }
        
        try:
            response = self.supabase.table("valentines").insert(valentine_data).execute()
            if response.data and len(response.data) > 0:
                valentine_id = response.data[0]["id"]
                logger.info(f"✅ Валентинка сохранена: {valentine_id}")
                return valentine_id
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении валентинки: {e}")
            return None
    
    def get_referral_stats(self, user_id):
        """Сколько человек пригласил пользователь"""
        try:
            response = self.supabase.table("referrals")\
                .select("*", count="exact")\
                .eq("referrer_id", user_id)\
                .execute()
            
            count = response.count if hasattr(response, 'count') else 0
            logger.info(f"📊 Рефералов у {user_id}: {count}")
            return count
        except Exception as e:
            logger.error(f"❌ Ошибка при получении статистики рефералов для {user_id}: {e}")
            return 0
    
    def get_user_stats(self, user_id):
        """Полная статистика пользователя"""
        try:
            # Отправленные валентинки
            sent = self.supabase.table("valentines")\
                .select("*", count="exact")\
                .eq("from_user_id", user_id)\
                .execute()
            
            # Полученные валентинки
            received = self.supabase.table("valentines")\
                .select("*", count="exact")\
                .eq("to_user_id", user_id)\
                .execute()
            
            # Рефералы
            referrals = self.get_referral_stats(user_id)
            
            stats = {
                "sent": sent.count if hasattr(sent, 'count') else 0,
                "received": received.count if hasattr(received, 'count') else 0,
                "referrals": referrals
            }
            
            logger.info(f"📊 Статистика для {user_id}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка при получении статистики для {user_id}: {e}")
            return {"sent": 0, "received": 0, "referrals": 0}