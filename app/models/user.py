from datetime import datetime
from app.utils import create_db_connection
from flask_login import UserMixin

def normalize_role(role):
    """Преобразует числовую или строковую роль в стандартизированную строковую роль в нижнем регистре."""
    if isinstance(role, int):
        role_mapping = {
            1: 'admin',
            2: 'leader',
            3: 'operator',
            4: 'user',
            5: 'backoffice'
        }
        return role_mapping.get(role, 'user')
        
    if isinstance(role, str):
        role_lower = role.lower()
        # Если роль — это числовая строка, преобразуем в int и мапим
        if role_lower.isdigit():
            return normalize_role(int(role_lower))
        # Обработка русских названий ролей
        role_translations = {
            'администратор': 'admin',
            'руководитель': 'leader',
            'оператор': 'operator',
            'пользователь': 'user',
            'бэк-офис': 'backoffice',
        }
        return role_translations.get(role_lower, role_lower)
        
    return 'user' # Значение по умолчанию для None или других типов

class User(UserMixin):
    def __init__(self, id=None, login=None, full_name=None, role=None, role_id=None, department=None, ukc_kc=None, **kwargs):
        self.id = id
        self.login = login
        self.full_name = full_name
        self.role = normalize_role(role)
        self._role_id = role_id  # Сохраняем role_id во внутреннем атрибуте
        self.department = department
        self.ukc_kc = ukc_kc
        self.status = kwargs.get('status', 'Офлайн')
        
        for key, value in kwargs.items():
            setattr(self, key, value)
            
        self._roles = None
    
    def get_id(self):
        return str(self.id)
        
    @property
    def roles(self):
        """
        Возвращает список ролей пользователя.
        Для обратной совместимости, если у пользователя есть только атрибут `role`,
        то будет возвращен список с одним объектом роли.
        """
        # Если роли уже были установлены вручную (например, при impersonate), возвращаем их
        if getattr(self, '_roles', None) is not None:
            return self._roles

        # Если роли уже были загружены, возвращаем их
        if getattr(self, '_cached_roles', None) is not None:
            return self._cached_roles
        
        # Если у пользователя нет ID, возвращаем пустой список
        if not self.id:
            return []
            
        connection = None
        cursor = None
        try:
            connection = create_db_connection()
            if not connection:
                return []
                
            cursor = connection.cursor(dictionary=True)
            
            # Для обратной совместимости, если используется старая система ролей
            if hasattr(self, 'role') and self.role:
                # Создаем простой объект с атрибутом name для совместимости
                class SimpleRole:
                    def __init__(self, name):
                        self.name = name
                    
                if self.role == 'admin':
                    return [SimpleRole('admin')]
                return [SimpleRole(self.role)]
            
            # Для новой системы ролей
            # Получаем роли пользователя из таблицы UserRole
            query = """
            SELECT r.id, r.name, r.display_name, r.description, r.role_type, r.is_system
            FROM Roles r
            JOIN UserRole ur ON r.id = ur.role_id
            WHERE ur.user_id = %s
            """
            cursor.execute(query, (self.id,))
            roles_data = cursor.fetchall()

            # Для старых пользователей, у которых есть только `role`
            if not roles_data and hasattr(self, 'role') and self.role:
                class SimpleRole:
                    def __init__(self, name):
                        self.name = name
                self._cached_roles = [SimpleRole(self.role)]
                return self._cached_roles

            # Создаем простые объекты ролей с необходимыми атрибутами
            class Role:
                def __init__(self, id, name, display_name, description, role_type, is_system):
                    self.id = id
                    self.name = name
                    self.display_name = display_name
                    self.description = description
                    self.type = role_type
                    self.is_system = is_system
                    
                def has_permission(self, module_name, action):
                    """
                    Проверяет, имеет ли роль разрешение на действие в модуле
                    
                    Args:
                        module_name (str): Название модуля
                        action (str): Название действия (view, create, edit, delete)
                        
                    Returns:
                        bool: True, если есть разрешение, иначе False
                    """
                    if self.name == 'admin':
                        return True
                        
                    conn = create_db_connection()
                    if not conn:
                        return False
                        
                    curs = conn.cursor(dictionary=True)
                    
                    try:
                        # Получаем ID модуля
                        curs.execute("SELECT id FROM Module WHERE name = %s", (module_name,))
                        module = curs.fetchone()
                        if not module:
                            return False
                            
                        # Проверяем разрешение
                        field_name = f"can_{action}"
                        curs.execute(f"""
                        SELECT {field_name} FROM RolePermission 
                        WHERE role_id = %s AND module_id = %s
                        """, (self.id, module['id']))
                        
                        permission = curs.fetchone()
                        return permission and permission[field_name]
                    finally:
                        curs.close()
                        conn.close()
            
            self._cached_roles = [Role(**role) for role in roles_data]
            return self._cached_roles
        except Exception as e:
            print(f"Ошибка при получении ролей пользователя: {e}")
            # В случае ошибки возвращаем роль из атрибута пользователя, если она есть
            if hasattr(self, 'role') and self.role:
                class SimpleRole:
                    def __init__(self, name):
                        self.name = name
                return [SimpleRole(self.role)]
            return []
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
            
    def has_role(self, role_name):
        """
        Проверяет, имеет ли пользователь указанную роль
        
        Args:
            role_name (str): Название роли
            
        Returns:
            bool: True, если у пользователя есть указанная роль, иначе False
        """
        return any(role.name == role_name for role in self.roles)

    @property
    def is_admin(self):
        """
        Проверяет, является ли пользователь администратором
        """
        return self.role == 'admin'

    # --- Методы проверки ролей (используются в utils.get_user_accessible_modules) ---
    def is_hr(self):
        return self.role == 'hr' or (hasattr(self, 'department') and self.department == 'HR')

    def is_leader(self):
        return self.role == 'leader'

    def is_callcenter(self):
        return self.role == 'operator'

    def is_helpdesk(self):
        return self.role == 'helpdesk'

    def is_itinvent(self):
        return self.role == 'itinvent'

    def is_avito(self):
        return self.role == 'avito'

    def is_reception(self):
        return self.role == 'reception' or (hasattr(self, 'department') and self.department == 'Ресепшн')

    def is_backoffice(self):
        return self.role == 'backoffice'

    def is_vats(self):
        return self.role == 'vats'

    def create_role_object(self, role_name):
        """Создает простой объект роли для совместимости"""
        class SimpleRole:
            def __init__(self, name):
                self.name = name
        return SimpleRole(role_name)

    @property
    def role_id(self):
        """Возвращает ID роли. Сначала проверяет прямой атрибут, потом вычисляет."""
        if hasattr(self, '_role_id') and self._role_id is not None:
            return self._role_id
        
        # Логика для обратной совместимости, если _role_id не был загружен
        if self.roles:
            r = self.roles[0]
            return getattr(r, 'id', None)
        return None

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
            SELECT u.id, u.login, u.full_name, u.role, u.role_id, u.department, u.fired, ua.status
            FROM User u
            LEFT JOIN UserActivity ua ON u.id = ua.user_id
            WHERE u.id = %s
            """, (user_id,))
            
            user_data = cursor.fetchone()
            if user_data:
                # Если в user_data нет строки роли, но есть role_id, пытаемся загрузить имя роли
                if (not user_data.get('role')) and user_data.get('role_id'):
                    try:
                        cursor.execute("SELECT name FROM Roles WHERE id = %s", (user_data['role_id'],))
                        role_row = cursor.fetchone()
                        if role_row:
                            user_data['role'] = role_row['name']
                    except Exception:
                        pass
                # Получаем ukc_kc для пользователя, если он есть
                ukc_kc_data = User.get_ukc_kc(user_id)
                user_data['ukc_kc'] = ukc_kc_data
                return User(**user_data)
        except Exception as e:
            print(f"Ошибка при загрузке пользователя по ID: {e}")
        finally:
            cursor.close()
            connection.close()
            
        return None

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

    @staticmethod
    def count():
        """Возвращает общее количество пользователей"""
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT COUNT(*) as count FROM User")
            result = cursor.fetchone()
            return result['count']
        finally:
            cursor.close()
            conn.close()

    # ... existing code ...