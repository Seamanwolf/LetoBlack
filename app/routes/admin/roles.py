from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.utils import create_db_connection
from app.decorators import admin_required

roles_bp = Blueprint('roles', __name__, url_prefix='/admin/settings/roles')

@roles_bp.route('/', methods=['GET'])
@roles_bp.route('/list', methods=['GET'])
@login_required
@admin_required
def index():
    """Отображает страницу управления ролями"""
    # Проверяем, инициализированы ли таблицы ролей
    tables_initialized = True
    try:
        conn = create_db_connection()
        cursor = conn.cursor()
        
        # Проверяем существование таблицы Role
        cursor.execute("SHOW TABLES LIKE 'Role'")
        role_table_exists = cursor.fetchone() is not None
        
        # Проверяем существование таблицы Module
        cursor.execute("SHOW TABLES LIKE 'Module'")
        module_table_exists = cursor.fetchone() is not None
        
        # Проверяем существование таблицы RolePermission
        cursor.execute("SHOW TABLES LIKE 'RolePermission'")
        role_permission_table_exists = cursor.fetchone() is not None
        
        # Если какая-то из таблиц не существует, считаем, что инициализация не выполнена
        tables_initialized = role_table_exists and module_table_exists and role_permission_table_exists
        
        if tables_initialized:
            # Получаем список ролей
            # Проверяем наличие колонки display_name
            cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'display_name'
            """)
            has_display_name = cursor.fetchone() is not None
            
            # Проверяем наличие колонки role_type
            cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'role_type'
            """)
            has_role_type = cursor.fetchone() is not None
            
            # Проверяем наличие колонки is_system
            cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'is_system'
            """)
            has_is_system = cursor.fetchone() is not None
            
            if has_display_name and has_role_type and has_is_system:
                # Полная структура с display_name, role_type и is_system
                cursor.execute("""
                SELECT id, name, display_name, description, role_type, is_system, created_at, updated_at
                FROM Role ORDER BY id
                """)
            elif has_display_name and has_role_type:
                # Есть display_name и role_type, но нет is_system
                cursor.execute("""
                SELECT id, name, display_name, description, role_type, 0 as is_system, created_at, updated_at
                FROM Role ORDER BY id
                """)
            elif has_display_name and has_is_system:
                # Есть display_name и is_system, но нет role_type
                cursor.execute("""
                SELECT id, name, display_name, description, 'custom' as role_type, is_system, created_at, updated_at
                FROM Role ORDER BY id
                """)
            elif has_display_name:
                # Есть только display_name, но нет role_type и is_system
                cursor.execute("""
                SELECT id, name, display_name, description, 
                       'custom' as role_type, 
                       0 as is_system, 
                       created_at, 
                       IFNULL(updated_at, created_at) as updated_at
                FROM Role ORDER BY id
                """)
            else:
                # Запрос без display_name (используем name вместо него)
                cursor.execute("""
                SELECT id, name, name as display_name, 
                       description, 
                       'custom' as role_type, 
                       0 as is_system, 
                       created_at, 
                       IFNULL(updated_at, created_at) as updated_at
                FROM Role ORDER BY id
                """)
            
            roles_data = cursor.fetchall()
            
            # Преобразуем данные в список объектов Role
            roles = []
            for role_data in roles_data:
                roles.append({
                    'id': role_data[0],
                    'name': role_data[1],
                    'display_name': role_data[2],
                    'description': role_data[3],
                    'type': role_data[4],
                    'is_system': bool(role_data[5]),
                    'created_at': role_data[6],
                    'updated_at': role_data[7]
                })
        else:
            roles = []
    except Exception as e:
        flash(f'Ошибка при проверке таблиц ролей: {str(e)}', 'danger')
        tables_initialized = False
        roles = []
    finally:
        if 'conn' in locals() and 'cursor' in locals():
            cursor.close()
            conn.close()
    
    return render_template('admin/settings/roles.html', 
                          roles=roles, 
                          tables_initialized=tables_initialized,
                          active_tab='roles')

@roles_bp.route('/add', methods=['POST'])
@login_required
@admin_required
def add_role():
    """Добавляет новую роль"""
    name = request.form.get('name')
    display_name = request.form.get('display_name')
    description = request.form.get('description')
    role_type = request.form.get('role_type', 'custom')
    
    if not name or not display_name:
        flash('Имя роли и отображаемое имя обязательны', 'danger')
        return redirect(url_for('roles.index'))
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor()
    
        # Проверка существования роли с таким именем
        cursor.execute("SELECT COUNT(*) FROM Role WHERE name = %s", (name,))
        if cursor.fetchone()[0] > 0:
            flash('Роль с таким именем уже существует', 'danger')
            return redirect(url_for('roles.index'))
        
        # Проверяем наличие колонки display_name
        cursor.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'display_name'
        """)
        has_display_name = cursor.fetchone() is not None
        
        # Проверяем наличие колонки role_type
        cursor.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'role_type'
        """)
        has_role_type = cursor.fetchone() is not None
        
        # Проверяем наличие колонки is_system
        cursor.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'is_system'
        """)
        has_is_system = cursor.fetchone() is not None
        
        # Формируем SQL запрос в зависимости от доступных колонок
        if has_display_name and has_role_type and has_is_system:
            # Полная новая структура
            cursor.execute("""
            INSERT INTO Role (name, display_name, description, role_type, is_system) 
            VALUES (%s, %s, %s, %s, 0)
            """, (name, display_name, description, role_type))
        elif has_display_name:
            # Есть display_name, но нет role_type или is_system
            cursor.execute("""
            INSERT INTO Role (name, display_name, description) 
            VALUES (%s, %s, %s)
            """, (name, display_name, description))
        else:
            # Старая структура, только name и description
            cursor.execute("""
            INSERT INTO Role (name, description) 
            VALUES (%s, %s)
            """, (name, description))
        
        conn.commit()
        flash(f'Роль "{display_name}" успешно создана', 'success')
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        flash(f'Ошибка при создании роли: {str(e)}', 'danger')
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()
    
    return redirect(url_for('roles.index'))

@roles_bp.route('/update', methods=['POST'])
@login_required
@admin_required
def update_role():
    """Обновляет существующую роль"""
    role_id = request.form.get('role_id')
    display_name = request.form.get('display_name')
    description = request.form.get('description')
    role_type = request.form.get('role_type')
    
    if not role_id or not display_name:
        flash('ID роли и отображаемое имя обязательны', 'danger')
        return redirect(url_for('roles.index'))
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor()
        
        # Проверяем наличие колонки is_system
        cursor.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'is_system'
        """)
        has_is_system = cursor.fetchone() is not None
        
        # Проверяем наличие колонки display_name
        cursor.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'display_name'
        """)
        has_display_name = cursor.fetchone() is not None
        
        # Проверяем наличие колонки role_type
        cursor.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'role_type'
        """)
        has_role_type = cursor.fetchone() is not None
        
        # Сначала проверим существование роли
        cursor.execute("SELECT * FROM Role WHERE id = %s", (role_id,))
        role_data = cursor.fetchone()
        
        if not role_data:
            flash('Роль не найдена', 'danger')
            return redirect(url_for('roles.index'))
        
        # Проверяем, системная ли роль
        if has_is_system:
            is_system = bool(role_data[5]) if len(role_data) > 5 else False
        else:
            # Если колонки is_system нет, считаем все роли не системными
            is_system = False
        
        # Формируем SQL запрос в зависимости от доступных колонок и статуса роли
        if is_system:
            # Для системных ролей можно менять только описание
            cursor.execute("""
            UPDATE Role SET description = %s WHERE id = %s
            """, (description, role_id))
        else:
            # Для обычных ролей можно менять все доступные поля
            if has_display_name and has_role_type:
                cursor.execute("""
                UPDATE Role SET display_name = %s, description = %s, role_type = %s 
                WHERE id = %s
                """, (display_name, description, role_type, role_id))
            elif has_display_name:
                cursor.execute("""
                UPDATE Role SET display_name = %s, description = %s 
                WHERE id = %s
                """, (display_name, description, role_id))
            else:
                cursor.execute("""
                UPDATE Role SET description = %s 
                WHERE id = %s
                """, (description, role_id))
        
        conn.commit()
        flash('Роль успешно обновлена', 'success')
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        flash(f'Ошибка при обновлении роли: {str(e)}', 'danger')
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()
    
    return redirect(url_for('roles.index'))

@roles_bp.route('/delete', methods=['POST'])
@login_required
@admin_required
def delete_role():
    """Удаляет роль"""
    role_id = request.form.get('role_id')
    
    if not role_id:
        return jsonify({'success': False, 'message': 'ID роли обязателен'})
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor()
        
        # Проверяем наличие колонки is_system
        cursor.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'is_system'
        """)
        has_is_system = cursor.fetchone() is not None
        
        # Проверяем наличие колонки display_name
        cursor.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'display_name'
        """)
        has_display_name = cursor.fetchone() is not None
        
        # Выбираем данные о роли с учетом структуры таблицы
        if has_is_system and has_display_name:
            cursor.execute("SELECT is_system, display_name FROM Role WHERE id = %s", (role_id,))
            role_data = cursor.fetchone()
            if not role_data:
                return jsonify({'success': False, 'message': 'Роль не найдена'})
            
            is_system, display_name = bool(role_data[0]), role_data[1]
        elif has_is_system:
            cursor.execute("SELECT is_system, name FROM Role WHERE id = %s", (role_id,))
            role_data = cursor.fetchone()
            if not role_data:
                return jsonify({'success': False, 'message': 'Роль не найдена'})
            
            is_system, display_name = bool(role_data[0]), role_data[1]  # Используем name как display_name
        elif has_display_name:
            cursor.execute("SELECT display_name FROM Role WHERE id = %s", (role_id,))
            role_data = cursor.fetchone()
            if not role_data:
                return jsonify({'success': False, 'message': 'Роль не найдена'})
            
            is_system, display_name = False, role_data[0]  # Считаем все роли не системными
        else:
            cursor.execute("SELECT name FROM Role WHERE id = %s", (role_id,))
            role_data = cursor.fetchone()
            if not role_data:
                return jsonify({'success': False, 'message': 'Роль не найдена'})
            
            is_system, display_name = False, role_data[0]  # Считаем все роли не системными и используем name как display_name
        
        if is_system:
            return jsonify({'success': False, 'message': 'Системные роли нельзя удалить'})
        
        # Проверяем, есть ли таблица UserRole
        cursor.execute("SHOW TABLES LIKE 'UserRole'")
        has_user_role_table = cursor.fetchone() is not None
        
        if has_user_role_table:
            # Проверяем, есть ли пользователи с этой ролью
            cursor.execute("SELECT COUNT(*) FROM UserRole WHERE role_id = %s", (role_id,))
            if cursor.fetchone()[0] > 0:
                return jsonify({
                    'success': False, 
                    'error': 'role_has_users',
                    'message': 'Невозможно удалить роль, назначенную пользователям'
                })
            
            # Проверяем, есть ли таблица RolePermission
            cursor.execute("SHOW TABLES LIKE 'RolePermission'")
            has_role_permission_table = cursor.fetchone() is not None
            
            if has_role_permission_table:
                # Удаляем разрешения роли
                cursor.execute("DELETE FROM RolePermission WHERE role_id = %s", (role_id,))
        
        # Удаляем роль
        cursor.execute("DELETE FROM Role WHERE id = %s", (role_id,))
        
        conn.commit()
        return jsonify({'success': True, 'message': f'Роль "{display_name}" успешно удалена'})
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return jsonify({'success': False, 'message': f'Ошибка при удалении роли: {str(e)}'})
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@roles_bp.route('/get_role_permissions/<int:role_id>', methods=['GET'])
@login_required
@admin_required
def get_role_permissions(role_id):
    """Получает права доступа для роли"""
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, есть ли таблица RolePermission
        cursor.execute("SHOW TABLES LIKE 'RolePermission'")
        has_role_permission_table = cursor.fetchone() is not None
        
        if not has_role_permission_table:
            return jsonify({
                'role_id': role_id,
                'permissions': []
            })
            
        # Проверяем, есть ли таблица Module
        cursor.execute("SHOW TABLES LIKE 'Module'")
        has_module_table = cursor.fetchone() is not None
        
        if not has_module_table:
            return jsonify({
                'role_id': role_id,
                'permissions': []
            })
        
        # Получаем разрешения для роли
        cursor.execute("""
        SELECT rp.*, m.name as module_name 
        FROM RolePermission rp 
        JOIN Module m ON rp.module_id = m.id 
        WHERE rp.role_id = %s
        """, (role_id,))
        
        permissions = cursor.fetchall()
        
        return jsonify({
            'role_id': role_id,
            'permissions': permissions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@roles_bp.route('/get_modules', methods=['GET'])
@login_required
@admin_required
def get_modules():
    """Получает список модулей системы"""
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, есть ли таблица Module
        cursor.execute("SHOW TABLES LIKE 'Module'")
        has_module_table = cursor.fetchone() is not None
        
        if not has_module_table:
            return jsonify({
                'modules': []
            })
        
        # Проверяем наличие колонки display_name
        cursor.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Module' AND COLUMN_NAME = 'display_name'
        """)
        has_display_name = cursor.fetchone() is not None
        
        # Получаем все модули
        if has_display_name:
            cursor.execute("""
            SELECT id, name, name as display_name, description, url_path, icon, `order`, is_active, parent_id, created_at, updated_at
            FROM Module ORDER BY `order`
            """)
        else:
            cursor.execute("""
            SELECT id, name, name as display_name, description, url_path, icon, `order`, is_active, parent_id, created_at, updated_at
            FROM Module ORDER BY `order`
            """)
        
        modules = cursor.fetchall()
        
        return jsonify({
            'modules': modules
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@roles_bp.route('/update_role_permissions', methods=['POST'])
@login_required
@admin_required
def update_role_permissions():
    """Обновляет права доступа для роли"""
    role_id = request.form.get('role_id')
    
    if not role_id:
        flash('ID роли обязателен', 'danger')
        return redirect(url_for('roles.index'))
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor()
        
        # Проверяем, есть ли таблица RolePermission
        cursor.execute("SHOW TABLES LIKE 'RolePermission'")
        has_role_permission_table = cursor.fetchone() is not None
        
        if not has_role_permission_table:
            flash('Таблица RolePermission не существует. Пожалуйста, инициализируйте таблицы ролей.', 'danger')
            return redirect(url_for('roles.index'))
        
        # Удаляем все текущие разрешения роли
        cursor.execute("DELETE FROM RolePermission WHERE role_id = %s", (role_id,))
        
        # Получаем разрешения из формы
        module_permissions = {}
        for key, value in request.form.items():
            if key.startswith('permissions['):
                # Парсим ключ вида permissions[module_id][permission_type]
                parts = key.replace('permissions[', '').replace(']', '').split('[')
                if len(parts) == 2:
                    module_id, permission_type = parts
                    if module_id not in module_permissions:
                        module_permissions[module_id] = {
                            'view': False,
                            'create': False,
                            'edit': False,
                            'delete': False
                        }
                    module_permissions[module_id][permission_type] = True
        
        # Вставляем новые разрешения
        for module_id, permissions in module_permissions.items():
            cursor.execute("""
            INSERT INTO RolePermission (role_id, module_id, can_view, can_create, can_edit, can_delete)
            VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                role_id,
                module_id,
                permissions['view'],
                permissions['create'],
                permissions['edit'],
                permissions['delete']
            ))
        
        conn.commit()
        flash('Разрешения успешно обновлены', 'success')
        return redirect(url_for('roles.index'))
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        flash(f'Ошибка при обновлении разрешений: {str(e)}', 'danger')
        return redirect(url_for('roles.index'))
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@roles_bp.route('/get_role_users/<int:role_id>', methods=['GET'])
@login_required
@admin_required
def get_role_users(role_id):
    """Получает список пользователей с указанной ролью"""
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем существование таблицы UserRole
        cursor.execute("SHOW TABLES LIKE 'UserRole'")
        if not cursor.fetchone():
            return jsonify({'users': []})
        
        # Получаем пользователей с указанной ролью
        cursor.execute("""
        SELECT u.id, u.full_name as name, u.login as email
        FROM User u
        JOIN UserRole ur ON u.id = ur.user_id
        WHERE ur.role_id = %s
        ORDER BY u.full_name
        """, (role_id,))
        
        users = cursor.fetchall()
        
        return jsonify({'users': users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@roles_bp.route('/get_available_roles', methods=['GET'])
@login_required
@admin_required
def get_available_roles():
    """Возвращает список доступных ролей для выбора"""
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем наличие колонки display_name
        cursor.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Role' AND COLUMN_NAME = 'display_name'
        """)
        has_display_name = cursor.fetchone() is not None
        
        if has_display_name:
            cursor.execute("""
            SELECT id, name, display_name FROM Role ORDER BY display_name
            """)
        else:
            cursor.execute("""
            SELECT id, name, name as display_name FROM Role ORDER BY name
            """)
        
        roles = cursor.fetchall()
        
        return jsonify({'roles': roles})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@roles_bp.route('/remove_role_from_user', methods=['POST'])
@login_required
@admin_required
def remove_role_from_user():
    """Удаляет роль у конкретного пользователя"""
    user_id = request.form.get('user_id')
    role_id = request.form.get('role_id')
    
    if not user_id or not role_id:
        return jsonify({'success': False, 'message': 'Не указан ID пользователя или роли'})
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor()
        
        # Проверяем существование таблицы UserRole
        cursor.execute("SHOW TABLES LIKE 'UserRole'")
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Таблица ролей не найдена'})
        
        # Удаляем роль у пользователя
        cursor.execute("""
        DELETE FROM UserRole 
        WHERE user_id = %s AND role_id = %s
        """, (user_id, role_id))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Роль успешно удалена у пользователя'})
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@roles_bp.route('/remove_role_from_all_users', methods=['POST'])
@login_required
@admin_required
def remove_role_from_all_users():
    """Удаляет роль у всех пользователей"""
    role_id = request.form.get('role_id')
    
    if not role_id:
        return jsonify({'success': False, 'message': 'Не указан ID роли'})
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor()
        
        # Проверяем существование таблицы UserRole
        cursor.execute("SHOW TABLES LIKE 'UserRole'")
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Таблица ролей не найдена'})
        
        # Удаляем роль у всех пользователей
        cursor.execute("""
        DELETE FROM UserRole 
        WHERE role_id = %s
        """, (role_id,))
        
        conn.commit()
        
        affected_rows = cursor.rowcount
        
        return jsonify({
            'success': True, 
            'message': f'Роль успешно удалена у {affected_rows} пользователей',
            'affected_rows': affected_rows
        })
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@roles_bp.route('/change_role_for_all_users', methods=['POST'])
@login_required
@admin_required
def change_role_for_all_users():
    """Меняет роль для всех пользователей с одной роли на другую"""
    role_id = request.form.get('role_id')
    new_role_id = request.form.get('new_role_id')
    
    if not role_id or not new_role_id:
        return jsonify({'success': False, 'message': 'Не указан ID текущей или новой роли'})
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor()
        
        # Проверяем существование таблицы UserRole
        cursor.execute("SHOW TABLES LIKE 'UserRole'")
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Таблица ролей не найдена'})
        
        # Получаем пользователей с указанной ролью
        cursor.execute("""
        SELECT user_id FROM UserRole 
        WHERE role_id = %s
        """, (role_id,))
        
        user_ids = [row[0] for row in cursor.fetchall()]
        
        if not user_ids:
            return jsonify({'success': True, 'message': 'Нет пользователей с этой ролью', 'affected_rows': 0})
        
        # Удаляем старую роль
        cursor.execute("""
        DELETE FROM UserRole 
        WHERE role_id = %s
        """, (role_id,))
        
        # Добавляем новую роль для всех пользователей
        for user_id in user_ids:
            cursor.execute("""
            INSERT INTO UserRole (user_id, role_id)
            VALUES (%s, %s)
            """, (user_id, new_role_id))
        
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Роль успешно изменена для {len(user_ids)} пользователей',
            'affected_rows': len(user_ids)
        })
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@roles_bp.route('/verify_admin_password', methods=['POST'])
@login_required
@admin_required
def verify_admin_password():
    """Проверяет пароль администратора для разблокировки системных ролей"""
    data = request.get_json()
    password = data.get('password')
    role_id = data.get('role_id')
    
    if not password or not role_id:
        return jsonify({'success': False, 'message': 'Не указан пароль или ID роли'})
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor()
        
        # Проверяем, является ли роль системной
        cursor.execute("SELECT is_system FROM Role WHERE id = %s", (role_id,))
        role = cursor.fetchone()
        
        if not role or not role[0]:
            return jsonify({'success': False, 'message': 'Роль не найдена или не является системной'})
        
        # Проверяем пароль администратора
        cursor.execute("SELECT password FROM User WHERE role = 'admin' LIMIT 1")
        admin = cursor.fetchone()
        
        if not admin:
            return jsonify({'success': False, 'message': 'Администратор не найден'})
        
        # В реальном приложении здесь должна быть проверка хеша пароля
        if password == admin[0]:  # Замените на правильную проверку хеша
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Неверный пароль'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if 'conn' in locals() and 'cursor' in locals():
            cursor.close()
            conn.close()