from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.routes.admin import admin_routes_bp
from app.utils import create_db_connection

@admin_routes_bp.route('/admin_dashboard')
@login_required
def admin_dashboard():
    """Страница панели администратора"""
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('auth.login'))

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Получаем статистику
        cursor.execute("""
            SELECT 
                COUNT(*) as total_employees,
                SUM(CASE WHEN status = 'Онлайн' THEN 1 ELSE 0 END) as active_employees,
                SUM(CASE WHEN status = 'fired' THEN 1 ELSE 0 END) as fired_employees,
                COUNT(DISTINCT department_id) as departments_count
            FROM User
        """)
        stats = cursor.fetchone()
        
        # Получаем последние действия
        cursor.execute("""
            SELECT 
                u.full_name,
                a.action,
                a.timestamp
            FROM UserActions a
            JOIN User u ON a.user_id = u.id
            ORDER BY a.timestamp DESC
            LIMIT 10
        """)
        recent_actions = cursor.fetchall()
        
        return render_template('admin/dashboard.html',
                             stats=stats,
                             recent_actions=recent_actions)
                             
    except Exception as e:
        flash(f'Ошибка при загрузке данных: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))
        
    finally:
        cursor.close()
        connection.close() 