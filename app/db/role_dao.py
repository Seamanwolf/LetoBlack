import pymysql
from typing import List, Dict, Any, Optional
from app.utils import create_db_connection

class Role:
    """Класс для представления роли пользователя"""
    
    def __init__(self, id, name, display_name, type, description=None, permissions=None):
        self.id = id
        self.name = name
        self.display_name = display_name
        self.type = type
        self.description = description
        self.permissions = permissions or {}
        
    @property
    def is_system(self):
        """Проверяет, является ли роль системной"""
        return self.type == 'system'
    
    @property 
    def is_backoffice(self):
        """Проверяет, является ли роль бэкофисной"""
        return self.type == 'backoffice'
    
    @property
    def is_regular(self):
        """Проверяет, является ли роль обычной"""
        return self.type == 'regular'


class RoleDAO:
    """Data Access Object для работы с ролями пользователей"""
    
    def __init__(self, db_config=None):
        """
        Инициализация DAO для работы с ролями
        
        Args:
            db_config (dict, optional): Конфигурация подключения к БД
        """
        self.db_config = db_config
    
    def get_all_roles(self):
        """
        Получает список всех ролей из базы данных
        
        Returns:
            list: Список объектов Role
        """
        connection = create_db_connection(self.db_config)
        if connection is None:
            return []
        
        cursor = None
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Запрос для получения всех ролей
            cursor.execute("""
                SELECT id, name, display_name, type, description
                FROM Roles
                ORDER BY type DESC, display_name
            """)
            
            roles = []
            for row in cursor.fetchall():
                role = Role(
                    id=row['id'],
                    name=row['name'],
                    display_name=row['display_name'],
                    type=row['type'],
                    description=row['description']
                )
                roles.append(role)
            
            return roles
        
        except Exception as e:
            print(f"Ошибка при получении списка ролей: {e}")
            return []
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def get_role_by_id(self, role_id):
        """
        Получает роль по ID
        
        Args:
            role_id (int): ID роли
            
        Returns:
            Role: Объект роли или None, если роль не найдена
        """
        connection = create_db_connection(self.db_config)
        if connection is None:
            return None
        
        cursor = None
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Получаем информацию о роли
            cursor.execute("""
                SELECT id, name, display_name, type, description
                FROM Roles
                WHERE id = %s
            """, (role_id,))
            
            role_data = cursor.fetchone()
            if not role_data:
                return None
            
            # Создаем объект роли
            role = Role(
                id=role_data['id'],
                name=role_data['name'],
                display_name=role_data['display_name'],
                type=role_data['type'],
                description=role_data['description']
            )
            
            return role
        
        except Exception as e:
            print(f"Ошибка при получении роли по ID: {e}")
            return None
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def get_users_by_role_id(self, role_id):
        """
        Получает список пользователей с указанной ролью
        
        Args:
            role_id (int): ID роли
            
        Returns:
            list: Список пользователей с указанной ролью
        """
        connection = create_db_connection(self.db_config)
        if connection is None:
            return []
        
        cursor = None
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Запрос для получения пользователей с указанной ролью
            cursor.execute("""
                SELECT u.id, u.login, u.full_name, d.name as department_name
                FROM User u
                LEFT JOIN Departments d ON u.department_id = d.id
                WHERE u.role_id = %s AND u.fired = 0
                ORDER BY u.full_name
            """, (role_id,))
            
            return cursor.fetchall()
        
        except Exception as e:
            print(f"Ошибка при получении пользователей с ролью: {e}")
            return []
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def create_role(self, name, display_name, role_type, description=None):
        """
        Создает новую роль в базе данных
        
        Args:
            name (str): Системное имя роли
            display_name (str): Отображаемое имя роли
            role_type (str): Тип роли (system, backoffice, regular)
            description (str, optional): Описание роли
            
        Returns:
            int: ID созданной роли или None в случае ошибки
        """
        connection = create_db_connection(self.db_config)
        if connection is None:
            return None
        
        cursor = None
        try:
            cursor = connection.cursor()
            
            # Проверяем, не существует ли уже роль с таким именем
            cursor.execute("SELECT id FROM Roles WHERE name = %s", (name,))
            if cursor.fetchone():
                print(f"Роль с именем {name} уже существует")
                return None
            
            # Вставляем новую роль
            cursor.execute("""
                INSERT INTO Roles (name, display_name, type, description, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (name, display_name, role_type, description))
            
            connection.commit()
            return cursor.lastrowid
        
        except Exception as e:
            connection.rollback()
            print(f"Ошибка при создании роли: {e}")
            return None
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def update_role(self, role_id, display_name=None, role_type=None, description=None):
        """
        Обновляет существующую роль
        
        Args:
            role_id (int): ID роли для обновления
            display_name (str, optional): Новое отображаемое имя роли
            role_type (str, optional): Новый тип роли
            description (str, optional): Новое описание роли
            
        Returns:
            bool: True если обновление успешно, иначе False
        """
        # Получаем существующую роль для проверки типа
        existing_role = self.get_role_by_id(role_id)
        if not existing_role:
            return False
        
        # Системные роли можно менять только описание
        if existing_role.is_system and (display_name or role_type):
            return False
        
        connection = create_db_connection(self.db_config)
        if connection is None:
            return False
        
        cursor = None
        try:
            cursor = connection.cursor()
            
            # Формируем SQL запрос для обновления
            update_fields = []
            params = []
            
            if display_name:
                update_fields.append("display_name = %s")
                params.append(display_name)
            
            if role_type and not existing_role.is_system:
                update_fields.append("type = %s")
                params.append(role_type)
            
            update_fields.append("description = %s")
            params.append(description)
            
            update_fields.append("updated_at = NOW()")
            
            # Добавляем ID роли в конец параметров
            params.append(role_id)
            
            # Выполняем обновление
            sql = f"UPDATE Roles SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(sql, params)
            
            connection.commit()
            return cursor.rowcount > 0
        
        except Exception as e:
            connection.rollback()
            print(f"Ошибка при обновлении роли: {e}")
            return False
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def delete_role(self, role_id):
        """
        Удаляет роль из базы данных
        
        Args:
            role_id (int): ID роли для удаления
            
        Returns:
            bool: True если удаление успешно, иначе False
        """
        # Получаем роль для проверки типа
        role = self.get_role_by_id(role_id)
        if not role:
            return False
        
        # Системные роли удалять нельзя
        if role.is_system:
            return False
        
        # Проверяем, есть ли пользователи с этой ролью
        users = self.get_users_by_role_id(role_id)
        if users:
            return False
        
        connection = create_db_connection(self.db_config)
        if connection is None:
            return False
        
        cursor = None
        try:
            cursor = connection.cursor()
            
            # Удаляем роль
            cursor.execute("DELETE FROM Roles WHERE id = %s", (role_id,))
            
            connection.commit()
            return cursor.rowcount > 0
        
        except Exception as e:
            connection.rollback()
            print(f"Ошибка при удалении роли: {e}")
            return False
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def get_role_by_name(self, role_name: str) -> Optional[Dict[str, Any]]:
        """
        Получает роль по имени
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                sql = """
                SELECT id, name, display_name, description, is_system, role_type
                FROM Roles
                WHERE name = %s
                """
                cursor.execute(sql, (role_name,))
                return cursor.fetchone()
        except Exception as e:
            print(f"Ошибка при получении роли по имени: {e}")
            return None
        finally:
            conn.close()

    def get_all_modules(self) -> List[Dict[str, Any]]:
        """
        Получает список всех модулей системы
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                sql = """
                SELECT id, name, display_name, description, route, icon
                FROM Modules
                ORDER BY display_name
                """
                cursor.execute(sql)
                return cursor.fetchall()
        except Exception as e:
            print(f"Ошибка при получении списка модулей: {e}")
            return []
        finally:
            conn.close()

    def get_role_permissions(self, role_id: int) -> Dict[str, Dict[str, bool]]:
        """
        Получает разрешения для роли в формате:
        {
            'module_name': {
                'can_view': True,
                'can_create': False,
                'can_edit': False,
                'can_delete': False
            },
            ...
        }
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                sql = """
                SELECT 
                    m.name AS module_name,
                    rp.can_view,
                    rp.can_create,
                    rp.can_edit,
                    rp.can_delete
                FROM RolePermissions rp
                JOIN Modules m ON rp.module_id = m.id
                WHERE rp.role_id = %s
                """
                cursor.execute(sql, (role_id,))
                permissions = {}
                
                for row in cursor.fetchall():
                    module_name = row.pop('module_name')
                    permissions[module_name] = row
                
                return permissions
        except Exception as e:
            print(f"Ошибка при получении разрешений роли: {e}")
            return {}
        finally:
            conn.close()

    def set_role_permissions(self, role_id: int, module_id: int, can_view: bool, can_create: bool, can_edit: bool, can_delete: bool) -> bool:
        """
        Устанавливает разрешения роли для модуля
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # Сначала проверяем, что роль не системная (для системных ролей не меняем разрешения)
                check_sql = "SELECT is_system FROM Roles WHERE id = %s"
                cursor.execute(check_sql, (role_id,))
                role = cursor.fetchone()
                
                if not role:
                    return False
                
                # Для системных ролей разрешаем только добавлять разрешения, но не удалять
                if role['is_system'] and not (can_view or can_create or can_edit or can_delete):
                    return False
                
                # Проверяем, существует ли уже запись
                check_perm_sql = """
                SELECT id FROM RolePermissions
                WHERE role_id = %s AND module_id = %s
                """
                cursor.execute(check_perm_sql, (role_id, module_id))
                perm = cursor.fetchone()
                
                if perm:
                    # Обновляем существующую запись
                    update_sql = """
                    UPDATE RolePermissions
                    SET can_view = %s, can_create = %s, can_edit = %s, can_delete = %s
                    WHERE role_id = %s AND module_id = %s
                    """
                    cursor.execute(update_sql, (can_view, can_create, can_edit, can_delete, role_id, module_id))
                else:
                    # Создаем новую запись
                    insert_sql = """
                    INSERT INTO RolePermissions (role_id, module_id, can_view, can_create, can_edit, can_delete)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, (role_id, module_id, can_view, can_create, can_edit, can_delete))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Ошибка при установке разрешений роли: {e}")
            return False
        finally:
            conn.close()

    def delete_role_permissions(self, role_id: int, module_id: int) -> bool:
        """
        Удаляет разрешения роли для модуля
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # Сначала проверяем, что роль не системная
                check_sql = "SELECT is_system FROM Roles WHERE id = %s"
                cursor.execute(check_sql, (role_id,))
                role = cursor.fetchone()
                
                if not role or role['is_system']:
                    return False
                
                sql = """
                DELETE FROM RolePermissions
                WHERE role_id = %s AND module_id = %s
                """
                cursor.execute(sql, (role_id, module_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка при удалении разрешений роли: {e}")
            return False
        finally:
            conn.close()

    def get_users_by_role(self, role_id: int) -> List[Dict[str, Any]]:
        """
        Получает список пользователей с указанной ролью
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                sql = """
                SELECT 
                    u.id, 
                    u.login, 
                    u.full_name,
                    u.department_id,
                    d.name AS department
                FROM User u
                LEFT JOIN Departments d ON u.department_id = d.id
                WHERE u.role_id = %s AND (u.fired = 0 OR u.fired IS NULL)
                ORDER BY u.full_name
                """
                cursor.execute(sql, (role_id,))
                return cursor.fetchall()
        except Exception as e:
            print(f"Ошибка при получении пользователей по роли: {e}")
            return []
        finally:
            conn.close()

    def _get_connection(self):
        """
        Создает подключение к базе данных
        """
        return pymysql.connect(
            host=self.db_config['host'],
            user=self.db_config['user'],
            password=self.db_config['password'],
            database=self.db_config['database'],
            cursorclass=pymysql.cursors.DictCursor
        ) 

    def clear_role_permissions(self, role_id):
        """
        Очищает все разрешения для указанной роли
        
        Args:
            role_id (int): ID роли
            
        Returns:
            bool: True если операция успешна, иначе False
        """
        # Получаем роль для проверки типа
        role = self.get_role_by_id(role_id)
        if not role:
            return False
        
        # Системные роли не изменяем
        if role.is_system:
            return False
        
        connection = create_db_connection(self.db_config)
        if connection is None:
            return False
        
        cursor = None
        try:
            cursor = connection.cursor()
            
            # Удаляем все разрешения роли
            cursor.execute("DELETE FROM RolePermissions WHERE role_id = %s", (role_id,))
            
            connection.commit()
            return True
        
        except Exception as e:
            connection.rollback()
            print(f"Ошибка при очистке разрешений роли: {e}")
            return False
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close() 