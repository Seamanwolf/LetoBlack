from datetime import datetime
from app.utils import create_db_connection
from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id=None, login=None, full_name=None, role=None, department=None, ukc_kc=None, **kwargs):
        self.id = id
        self.login = login
        self.full_name = full_name
        self.role = role
        self.department = department
        self.ukc_kc = ukc_kc
        self.status = kwargs.get('status', 'Офлайн')  # Добавляем атрибут status со значением по умолчанию
        
        # Добавляем все оставшиеся атрибуты из kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def get_id(self):
        return str(self.id)

    @staticmethod
    def get_by_id(user_id):
        """
        Загружает пользователя по ID из базы данных
        """
        connection = create_db_connection()
        if not connection:
            return None
            
        cursor = connection.cursor(dictionary=True)
        
        try:
            cursor.execute("""
            SELECT u.id, u.login, u.full_name, u.role, u.department, u.fired, ua.status
            FROM User u
            LEFT JOIN UserActivity ua ON u.id = ua.user_id
            WHERE u.id = %s
            """, (user_id,))
            
            user_data = cursor.fetchone()
            if user_data:
                # Получаем ukc_kc для пользователя, если он есть
                ukc_kc = User.get_ukc_kc(user_id)
                if ukc_kc:
                    user_data['ukc_kc'] = ukc_kc
                
                # Преобразуем статус в русский формат
                if user_data.get('status') == 'online':
                    user_data['status'] = 'Онлайн'
                elif user_data.get('status') == 'offline':
                    user_data['status'] = 'Офлайн'
                elif user_data.get('status') == 'away':
                    user_data['status'] = 'Отошел'
                elif user_data.get('status') == 'busy':
                    user_data['status'] = 'Занят'
                else:
                    user_data['status'] = 'Офлайн'
                
                return User(**user_data)
            return None
        except Exception as e:
            print(f"Ошибка при получении пользователя по ID: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def migrate_ukc_kc_to_new_table():
        """
        Метод для миграции данных ukc_kc в отдельную таблицу
        """
        connection = create_db_connection()
        if not connection:
            return False
            
        cursor = connection.cursor()
        
        try:
            # Создаем новую таблицу для хранения ukc_kc
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_ukc (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                ukc_kc ENUM('УКЦ','КЦ') NOT NULL DEFAULT 'УКЦ',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES User(id) ON DELETE CASCADE,
                UNIQUE KEY unique_user_id (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
            """)
            
            # Получаем всех пользователей
            cursor.execute("SELECT id FROM User WHERE role = 'callcenter' OR role = 'admin'")
            users = cursor.fetchall()
            
            now = datetime.utcnow()
            
            # Добавляем записи в новую таблицу с ukc_kc = УКЦ (значение по умолчанию)
            for user in users:
                user_id = user[0]
                cursor.execute("""
                INSERT INTO user_ukc (user_id, ukc_kc, created_at, updated_at)
                VALUES (%s, 'УКЦ', %s, %s)
                ON DUPLICATE KEY UPDATE updated_at = %s
                """, (user_id, now, now, now))
            
            # Фиксируем транзакцию
            connection.commit()
            print(f"Создана таблица user_ukc и добавлены записи для {len(users)} пользователей")
            return True
        except Exception as e:
            connection.rollback()
            print(f"Ошибка при миграции данных ukc_kc: {e}")
            return False
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_ukc_kc(user_id):
        """
        Возвращает значение ukc_kc пользователя из новой таблицы user_ukc
        """
        connection = create_db_connection()
        if not connection:
            return None
            
        cursor = connection.cursor(dictionary=True)
        
        try:
            cursor.execute("""
            SELECT ukc_kc FROM user_ukc
            WHERE user_id = %s
            """, (user_id,))
            
            result = cursor.fetchone()
            return result['ukc_kc'] if result else None
        except Exception as e:
            print(f"Ошибка при получении ukc_kc: {e}")
            return None
        finally:
            cursor.close()
            connection.close()
    
    @staticmethod
    def set_ukc_kc(user_id, ukc_kc):
        """
        Устанавливает значение ukc_kc для пользователя в новой таблице user_ukc
        """
        connection = create_db_connection()
        if not connection:
            return False
            
        cursor = connection.cursor()
        
        try:
            now = datetime.utcnow()
            
            # Проверяем, существует ли уже запись для этого пользователя
            cursor.execute("SELECT 1 FROM user_ukc WHERE user_id = %s", (user_id,))
            exists = cursor.fetchone() is not None
            
            if exists:
                # Обновляем существующую запись
                cursor.execute("""
                UPDATE user_ukc
                SET ukc_kc = %s, updated_at = %s
                WHERE user_id = %s
                """, (ukc_kc, now, user_id))
            else:
                # Создаем новую запись
                cursor.execute("""
                INSERT INTO user_ukc (user_id, ukc_kc, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                """, (user_id, ukc_kc, now, now))
            
            connection.commit()
            return True
        except Exception as e:
            connection.rollback()
            print(f"Ошибка при установке ukc_kc: {e}")
            return False
        finally:
            cursor.close()
            connection.close()
    
    @staticmethod
    def get_users_by_ukc_kc(ukc_kc):
        """
        Получает список пользователей по типу УКЦ/КЦ
        """
        connection = create_db_connection()
        if not connection:
            return []
            
        cursor = connection.cursor(dictionary=True)
        
        try:
            cursor.execute("""
            SELECT u.id, u.login, u.full_name, u.role, u.department, u.fired
            FROM User u
            JOIN user_ukc uu ON u.id = uu.user_id
            WHERE uu.ukc_kc = %s
            """, (ukc_kc,))
            
            users = cursor.fetchall()
            return [User(**user) for user in users]
        except Exception as e:
            print(f"Ошибка при получении пользователей по типу УКЦ/КЦ: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def get_all():
        """
        Получает список всех пользователей
        """
        connection = create_db_connection()
        if not connection:
            return []
            
        cursor = connection.cursor(dictionary=True)
        
        try:
            cursor.execute("""
            SELECT u.id, u.login, u.full_name, u.role, u.department, u.fired, ua.status
            FROM User u
            LEFT JOIN UserActivity ua ON u.id = ua.user_id
            """)
            
            users = cursor.fetchall()
            result = []
            for user_data in users:
                # Преобразуем статус в русский формат
                if user_data.get('status') == 'online':
                    user_data['status'] = 'Онлайн'
                elif user_data.get('status') == 'offline':
                    user_data['status'] = 'Офлайн'
                elif user_data.get('status') == 'away':
                    user_data['status'] = 'Отошел'
                elif user_data.get('status') == 'busy':
                    user_data['status'] = 'Занят'
                else:
                    user_data['status'] = 'Офлайн'
                
                result.append(User(**user_data))
            return result
        except Exception as e:
            print(f"Ошибка при получении всех пользователей: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    # ... existing code ...