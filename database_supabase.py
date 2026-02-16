import os
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from datetime import datetime
import random
import string
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_KEY')
        options = ClientOptions(
            postgrest_client_timeout=30,
            storage_client_timeout=30,
            schema="public"
        )
        self.supabase: Client = create_client(url, key, options=options)

    def _generate_unique_referral_code(self, length=10):
        while True:
            code = ''.join(random.choices(string.ascii_letters + string.digits, k=length))

            existing = self.supabase.table('users')\
                .select('user_id')\
                .eq('referral_code', code)\
                .execute()
            
            if not existing.data:
                return code

    def add_user(self, user_id, username, first_name, referred_by=None):
        referral_code = self._generate_unique_referral_code()

        user_data = {
            'user_id': user_id,
            'username': username if username else None,
            'first_name': first_name,
            'referral_code': referral_code,
            'referred_by': referred_by,
            'joined_date': datetime.now().isoformat()
        }

        try:
            # Вставляем или обновляем пользователя
            response = self.supabase.table('users').upsert(user_data).execute()
            
            # Если есть реферал, записываем это отдельно
            if referred_by:
                referral_data = {
                    'referrer_id': referred_by,
                    'referred_id': user_id,
                    'date': datetime.now().isoformat()
                }
                self.supabase.table('referrals').insert(referral_data).execute()
            
            return response
        except Exception as e:
            print(f'Ошибка при добавлении пользователя {user_id}: {e}')
            return None
        
    def get_referral_code(self, user_id):
        try:
            response = self.supabase.table('users')\
            .select('referral_code')\
            .eq('user_id', user_id)\
            .execute()

            if response.data:
                return response.data[0]['referral_code']
            return None
        except Exception as e:
            print(f'Ошибка при получении реферального кода для {user_id}: {e}')
            return None
        
    def get_user_by_referral(self, referral_code):
        """Ищем пользователя по реферальному коду"""
        try:
            response = self.supabase.table("users")\
                .select("user_id")\
                .eq("referral_code", referral_code)\
                .execute()
            
            if response.data:
                return response.data[0]["user_id"]
            return None
        except Exception as e:
            print(f"Ошибка при поиске по реферальному коду {referral_code}: {e}")
            return None
        

    def save_valentine(self, from_user_id, to_user_id, to_username, message):
        """Сохраняем валентинку"""
        to_username = str(to_username).replace('@', '') if to_username else None
        
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
            if response.data:
                return response.data[0]["id"]
            return None
        except Exception as e:
            print(f"Ошибка при сохранении валентинки: {e}")
            return None
        
    def get_referral_stats(self, user_id):
        """Сколько человек пригласил пользователь"""
        try:
            response = self.supabase.table("referrals")\
                .select("*", count="exact")\
                .eq("referrer_id", user_id)\
                .execute()
            
            return response.count if hasattr(response, 'count') else 0
        except Exception as e:
            print(f"Ошибка при получении статистики рефералов для {user_id}: {e}")
            return 0
        
    def get_user_stats(self, user_id):
        try:
            print(f"🔍 DB: Запрос статистики для {user_id}")  # Отладка
        
            # Отправленные валентинки
            sent = self.supabase.table("valentines")\
                .select("*", count="exact")\
                .eq("from_user_id", user_id)\
                .execute()
            print(f"📤 DB: Отправлено: {sent.count if hasattr(sent, 'count') else 0}")  # Отладка
            
            # Полученные валентинки
            received = self.supabase.table("valentines")\
                .select("*", count="exact")\
                .eq("to_user_id", user_id)\
                .execute()
            print(f"📥 DB: Получено: {received.count if hasattr(received, 'count') else 0}")  # Отладка
            
            # Рефералы
            referrals = self.get_referral_stats(user_id)
            print(f"👥 DB: Рефералы: {referrals}")  # Отладка
            
            result = {
                "sent": sent.count if hasattr(sent, 'count') else 0,
                "received": received.count if hasattr(received, 'count') else 0,
                "referrals": referrals
            }
            print(f"✅ DB: Результат: {result}")  # Отладка
            return result
            
        except Exception as e:
            print(f"❌ DB: Ошибка в get_user_stats: {e}")
            return {"sent": 0, "received": 0, "referrals": 0}