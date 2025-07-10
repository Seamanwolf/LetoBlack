from app.models_updated import User
import pymysql
from datetime import datetime
from app.utils import create_db_connection

class UserDAO:
    """
    Класс для работы с данными пользователей в базе данных
    """

    def __init__(self, db_config):
        """
        Инициализирует объект DAO с конфигурацией базы данных
        """
        self.db_config = db_config

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

    def _get_user_permissions(self, conn, role_id):
        """
        Получает разрешения пользователя на основе его роли
        """
        try:
            with conn.cursor() as cursor:
                # Получаем разрешения для роли
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
            print(f"Error getting user permissions: {e}")
            return {}

    def get_user_by_login(self, login):
        """
        Получает пользователя по логину из базы данных
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # Обновленный SQL запрос для работы с новой структурой базы данных
                sql = """
                SELECT 
                    u.id, 
                    u.login, 
                    u.full_name, 
                    r.name as role, 
                    r.id as role_id,
                    r.display_name as role_display_name,
                    r.is_system,
                    r.role_type,
                    d.name as department,
                    u.department_id,
                    ccs.ukc_kc,
                    ua.status,
                    ua.last_activity,
                    u.position,
                    u.hire_date,
                    u.fire_date,
                    u.fired
                FROM 
                    User u
                LEFT JOIN 
                    Roles r ON u.role_id = r.id
                LEFT JOIN 
                    Departments d ON u.department_id = d.id
                LEFT JOIN 
                    CallCenterSettings ccs ON u.id = ccs.user_id
                LEFT JOIN 
                    UserActivity ua ON u.id = ua.user_id
                WHERE 
                    u.login = %s
                """
                cursor.execute(sql, (login,))
                user_data = cursor.fetchone()
                
                if user_data:
                    # Получаем разрешения пользователя
                    user_data['permissions'] = self._get_user_permissions(conn, user_data['role_id'])
                    return User(**user_data)
                return None
        except Exception as e:
            print(f"Error fetching user by login: {e}")
            return None
        finally:
            conn.close()

    def get_user_by_id(self, user_id):
        """
        Получает пользователя по ID из базы данных
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # Обновленный SQL запрос для работы с новой структурой базы данных
                sql = """
                SELECT 
                    u.id, 
                    u.login, 
                    u.full_name, 
                    r.name as role, 
                    r.id as role_id,
                    r.display_name as role_display_name,
                    r.is_system,
                    r.role_type,
                    d.name as department,
                    u.department_id,
                    ccs.ukc_kc,
                    ua.status,
                    ua.last_activity,
                    u.position,
                    u.hire_date,
                    u.fire_date,
                    u.fired
                FROM 
                    User u
                LEFT JOIN 
                    Roles r ON u.role_id = r.id
                LEFT JOIN 
                    Departments d ON u.department_id = d.id
                LEFT JOIN 
                    CallCenterSettings ccs ON u.id = ccs.user_id
                LEFT JOIN 
                    UserActivity ua ON u.id = ua.user_id
                WHERE 
                    u.id = %s
                """
                cursor.execute(sql, (user_id,))
                user_data = cursor.fetchone()
                
                if user_data:
                    # Получаем разрешения пользователя
                    user_data['permissions'] = self._get_user_permissions(conn, user_data['role_id'])
                    return User(**user_data)
                return None
        except Exception as e:
            print(f"Error fetching user by ID: {e}")
            return None
        finally:
            conn.close()

    def update_user_status(self, user_id, status):
        """
        Обновляет статус пользователя в базе данных
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # Проверяем, существует ли уже запись для пользователя
                check_sql = "SELECT COUNT(*) as count FROM UserActivity WHERE user_id = %s"
                cursor.execute(check_sql, (user_id,))
                result = cursor.fetchone()
                
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if result and result['count'] > 0:
                    # Обновляем существующую запись
                    sql = """
                    UPDATE UserActivity 
                    SET status = %s, last_activity = %s
                    WHERE user_id = %s
                    """
                    cursor.execute(sql, (status, now, user_id))
                else:
                    # Создаем новую запись
                    sql = """
                    INSERT INTO UserActivity (user_id, status, last_activity)
                    VALUES (%s, %s, %s)
                    """
                    cursor.execute(sql, (user_id, status, now))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error updating user status: {e}")
            return False
        finally:
            conn.close()

    def get_all_users(self, include_fired=False):
        """
        Получает список всех пользователей из базы данных
        """
        connection = create_db_connection(self.db_config)
        if connection is None:
            return []
        
        cursor = None
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Базовый запрос для получения всех пользователей
            sql = """
                SELECT u.id, u.login, u.full_name, u.department_id, d.name as department_name,
                       u.role_id, r.name as role_name, r.display_name as role_display_name,
                       u.position, u.Phone as phone, u.personal_email, u.pc_login, 
                       u.office, u.corp_phone, u.fired, u.fire_date, u.hire_date,
                       ua.status as active, ua.last_activity,
                       cc.ukc_kc
                FROM User u
                LEFT JOIN Departments d ON u.department_id = d.id
                LEFT JOIN Roles r ON u.role_id = r.id
                LEFT JOIN UserActivity ua ON u.id = ua.user_id
                LEFT JOIN CallCenterSettings cc ON u.id = cc.user_id
            """
            
            # Добавляем условие фильтрации уволенных, если нужно
            if not include_fired:
                sql += " WHERE u.fired = 0"
            
            sql += " ORDER BY u.full_name"
            
            cursor.execute(sql)
            
            users = []
            for row in cursor.fetchall():
                user = User(
                    id=row['id'],
                    login=row['login'],
                    full_name=row['full_name'],
                    department_id=row['department_id'],
                    department_name=row['department_name'],
                    role_id=row['role_id'],
                    role_name=row['role_name'],
                    role_display_name=row['role_display_name'],
                    position=row['position'],
                    phone=row['phone'],
                    personal_email=row['personal_email'],
                    pc_login=row['pc_login'],
                    office=row['office'],
                    corp_phone=row['corp_phone'],
                    ukc_kc=row['ukc_kc'],
                    fired=bool(row['fired']),
                    fire_date=row['fire_date'],
                    hire_date=row['hire_date'],
                    active=row['active'],
                    last_activity=row['last_activity']
                )
                users.append(user)
            
            return users
        
        except Exception as e:
            print(f"Ошибка при получении списка пользователей: {e}")
            return []
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def get_users_by_department(self, department_id, include_fired=False):
        """
        Получает список пользователей определенного отдела из базы данных
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # Базовый SQL запрос
                sql = """
                SELECT 
                    u.id, 
                    u.login, 
                    u.full_name, 
                    r.name as role, 
                    r.id as role_id,
                    r.display_name as role_display_name,
                    r.is_system,
                    r.role_type,
                    d.name as department,
                    u.department_id,
                    ccs.ukc_kc,
                    ua.status,
                    ua.last_activity,
                    u.position,
                    u.hire_date,
                    u.fire_date,
                    u.fired
                FROM 
                    User u
                LEFT JOIN 
                    Roles r ON u.role_id = r.id
                LEFT JOIN 
                    Departments d ON u.department_id = d.id
                LEFT JOIN 
                    CallCenterSettings ccs ON u.id = ccs.user_id
                LEFT JOIN 
                    UserActivity ua ON u.id = ua.user_id
                WHERE 
                    u.department_id = %s
                """
                
                # Добавляем условие фильтрации уволенных, если требуется
                if not include_fired:
                    sql += " AND (u.fired = 0 OR u.fired IS NULL)"
                
                # Добавляем сортировку
                sql += " ORDER BY u.full_name"
                
                cursor.execute(sql, (department_id,))
                users_data = cursor.fetchall()
                
                users = []
                for user_data in users_data:
                    # Получаем разрешения пользователя
                    user_data['permissions'] = self._get_user_permissions(conn, user_data['role_id'])
                    users.append(User(**user_data))
                
                return users
        except Exception as e:
            print(f"Error fetching users by department: {e}")
            return []
        finally:
            conn.close()

    def get_users_by_role(self, role_name, include_fired=False):
        """
        Получает список пользователей определенной роли из базы данных
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # Базовый SQL запрос
                sql = """
                SELECT 
                    u.id, 
                    u.login, 
                    u.full_name, 
                    r.name as role, 
                    r.id as role_id,
                    r.display_name as role_display_name,
                    r.is_system,
                    r.role_type,
                    d.name as department,
                    u.department_id,
                    ccs.ukc_kc,
                    ua.status,
                    ua.last_activity,
                    u.position,
                    u.hire_date,
                    u.fire_date,
                    u.fired
                FROM 
                    User u
                JOIN 
                    Roles r ON u.role_id = r.id
                LEFT JOIN 
                    Departments d ON u.department_id = d.id
                LEFT JOIN 
                    CallCenterSettings ccs ON u.id = ccs.user_id
                LEFT JOIN 
                    UserActivity ua ON u.id = ua.user_id
                WHERE 
                    r.name = %s
                """
                
                # Добавляем условие фильтрации уволенных, если требуется
                if not include_fired:
                    sql += " AND (u.fired = 0 OR u.fired IS NULL)"
                
                # Добавляем сортировку
                sql += " ORDER BY u.full_name"
                
                cursor.execute(sql, (role_name,))
                users_data = cursor.fetchall()
                
                users = []
                for user_data in users_data:
                    # Получаем разрешения пользователя
                    user_data['permissions'] = self._get_user_permissions(conn, user_data['role_id'])
                    users.append(User(**user_data))
                
                return users
        except Exception as e:
            print(f"Error fetching users by role: {e}")
            return []
        finally:
            conn.close() 