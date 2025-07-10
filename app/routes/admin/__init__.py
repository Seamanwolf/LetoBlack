from flask import Blueprint, render_template
from flask_login import login_required
from app.models import User
from app.models.role import Role
from app.models.department import Department
from app.models.location import Location
from app.utils import create_db_connection

# Убрал url_prefix, так как он добавляется при регистрации
admin_routes_bp = Blueprint('admin_routes_unique', __name__)

@admin_routes_bp.route('/admin')
def index():
    # Получаем количество записей для каждой сущности через соединение с БД
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Подсчет пользователей
        cursor.execute("SELECT COUNT(*) as count FROM User")
        user_count = cursor.fetchone()['count']
        
        # Подсчет ролей
        cursor.execute("SELECT COUNT(*) as count FROM Role")
        role_count = cursor.fetchone()['count']
        
        # Подсчет отделов
        cursor.execute("SELECT COUNT(*) as count FROM Department")
        department_count = cursor.fetchone()['count']
        
        # Подсчет локаций
        cursor.execute("SELECT COUNT(*) as count FROM Location")
        location_count = cursor.fetchone()['count']
        
        # Здесь можно добавить логику получения последних действий
        cursor.execute("""
            SELECT a.*, u.full_name 
            FROM UserActivity a
            JOIN User u ON a.user_id = u.id
            ORDER BY a.created_at DESC
            LIMIT 10
        """)
        recent_actions = cursor.fetchall()
        
        return render_template('admin/index.html',
                             user_count=user_count,
                             role_count=role_count,
                             department_count=department_count,
                             location_count=location_count,
                             recent_actions=recent_actions)
    except Exception as e:
        return render_template('admin/index.html',
                              user_count=0,
                              role_count=0,
                              department_count=0,
                              location_count=0,
                              recent_actions=[],
                              error_message=str(e))
    finally:
        cursor.close()
        connection.close()

# Импортируем модули после создания Blueprint
from app.routes.admin import roles, personnel, dashboard, admin_routes

# Добавляем маршруты восстановления уволенных сотрудников
@admin_routes_bp.route('/rehire_employee', methods=['POST'])
@admin_routes_bp.route('/api/restore_employee', methods=['POST'])
@admin_routes_bp.route('/admin/api/restore_employee', methods=['POST'])
@login_required
def rehire_employee():
    """Восстановление уволенного сотрудника"""
    from flask import request, jsonify
    from flask_login import current_user, login_required
    from app.utils import create_db_connection
    import logging
    
    logger = logging.getLogger(__name__)
    
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Необходима авторизация'}), 401
        
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'У вас нет доступа к этой операции'})
    
    try:
        data = request.json
        employee_id = data.get('employee_id') or data.get('id')
        
        if not employee_id:
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'})
        
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Проверяем, что сотрудник существует и уволен
        cursor.execute("SELECT id, full_name, status, fire_date FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            return jsonify({'success': False, 'message': 'Сотрудник не найден'})
        
        if not employee.get('fire_date'):
            return jsonify({'success': False, 'message': 'Сотрудник не уволен'})
        
        # Обновляем запись сотрудника
        cursor.execute("""
            UPDATE User 
            SET status = 'offline', 
                fire_date = NULL 
            WHERE id = %s
        """, (employee_id,))
        
        connection.commit()
        
        logger.info(f"Сотрудник {employee['full_name']} (ID: {employee_id}) успешно восстановлен")
        
        return jsonify({
            'success': True, 
            'message': f"Сотрудник {employee['full_name']} успешно восстановлен"
        })
    
    except Exception as e:
        logger.error(f"Ошибка при восстановлении сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при восстановлении сотрудника: {str(e)}'})
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

# Добавляем маршрут для удаления уволенных сотрудников
@admin_routes_bp.route('/api/delete_fired_employee_permanently', methods=['POST'])
@admin_routes_bp.route('/admin/api/delete_fired_employee_permanently', methods=['POST'])
@login_required
def delete_fired_employee_permanently():
    """Удаление уволенного сотрудника насовсем"""
    from flask import request, jsonify
    from flask_login import current_user, login_required
    from app.utils import create_db_connection
    import logging
    
    logger = logging.getLogger(__name__)
    
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Необходима авторизация'}), 401
    
    if current_user.role != 'admin':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
            
        employee_id = data.get('employee_id')
        if not employee_id:
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400

        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, что сотрудник существует и уволен
        cursor.execute("SELECT id, full_name, status, fire_date FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404
        
        if not employee.get('fire_date'):
            return jsonify({'success': False, 'message': 'Можно удалять только уволенных сотрудников'}), 400
        
        # Удаляем сотрудника насовсем
        cursor.execute("DELETE FROM User WHERE id = %s", (employee_id,))
        conn.commit()
        
        logger.info(f"Уволенный сотрудник {employee['full_name']} (ID: {employee_id}) удален насовсем")
        
        return jsonify({
            'success': True, 
            'message': f"Сотрудник {employee['full_name']} успешно удален насовсем"
        })
        
    except Exception as e:
        logger.error(f"Ошибка при удалении уволенного сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при удалении сотрудника: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close() 