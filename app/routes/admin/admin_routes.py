from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app.utils import create_db_connection
from app.routes.auth import redirect_based_on_role
from app.routes.admin import admin_routes_bp
from datetime import datetime

@admin_routes_bp.route('/personnel_dashboard')
@login_required
def personnel_dashboard():
    """Панель управления персоналом"""
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'error')
        return redirect_based_on_role(current_user)
    
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Получение статистики
        cursor.execute("SELECT COUNT(*) as total FROM User WHERE status != 'fired'")
        total_employees = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as active FROM User WHERE status = 'Онлайн'")
        active_employees = cursor.fetchone()['active']

        cursor.execute("SELECT COUNT(*) as fired FROM User WHERE status = 'fired'")
        fired_employees = cursor.fetchone()['fired']

        cursor.execute("SELECT COUNT(*) as departments FROM Department")
        departments_count = cursor.fetchone()['departments']

        # Получение данных для графиков
        cursor.execute("""
            SELECT DATE(hire_date) as date, COUNT(*) as count 
                FROM User
            WHERE hire_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(hire_date)
            ORDER BY date
        """)
        staff_dynamics = cursor.fetchall()

        dates = []
        staff_counts = []
        for item in staff_dynamics:
            dates.append(item['date'].strftime('%d.%m'))
            staff_counts.append(item['count'])

        cursor.execute("""
            SELECT d.name, COUNT(u.id) as count
            FROM Department d
            LEFT JOIN User u ON d.id = u.department_id AND u.status != 'fired'
            GROUP BY d.id, d.name
        """)
        department_distribution = cursor.fetchall()

        department_names = []
        department_counts = []
        for item in department_distribution:
            department_names.append(item['name'])
            department_counts.append(item['count'])

        cursor.execute("""
            SELECT u.full_name, d.name as department, u.position, u.hire_date
                    FROM User u
            JOIN Department d ON u.department_id = d.id
            WHERE u.status != 'fired'
            ORDER BY u.hire_date DESC
            LIMIT 5
        """)
        recent_hires = cursor.fetchall()

        cursor.execute("""
            SELECT u.full_name, d.name as department, u.position, u.fire_date
                        FROM User u
            JOIN Department d ON u.department_id = d.id
            WHERE u.status = 'fired' AND u.fire_date IS NOT NULL
                        ORDER BY u.fire_date DESC
            LIMIT 5
        """)
        recent_fires = cursor.fetchall()

        cursor.close()
        connection.close()
        
        return render_template('admin/personnel_dashboard.html',
                            total_employees=total_employees,
                            active_employees=active_employees,
                            fired_employees=fired_employees,
                            departments_count=departments_count,
                            dates=dates,
                            staff_counts=staff_counts,
                            department_names=department_names,
                            department_counts=department_counts,
                            recent_hires=recent_hires,
                            recent_fires=recent_fires)
    except Exception as e:
        flash(f'Ошибка при загрузке данных: {str(e)}', 'error')
        return redirect_based_on_role(current_user) 