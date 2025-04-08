from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, abort, current_app, session
from app.utils import create_db_connection, login_required, get_user_department, get_notifications_count
from werkzeug.utils import secure_filename
from functools import wraps
import os
from app.extensions import socketio
import mysql.connector
from datetime import datetime
from flask_login import login_required as flask_login_required, current_user

helpdesk_bp = Blueprint('helpdesk', __name__)

@helpdesk_bp.app_template_filter('status_translate')
def status_translate_filter(status):
    translations = {
        'new': 'Новая',
        'open': 'В работе',
        'close': 'Закрытая'
    }
    return translations.get(status, status)

@helpdesk_bp.route('/helpdesk')
@login_required
def helpdesk_dashboard():
    if current_user.role not in ['admin', 'leader']:
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('helpdesk/helpdesk_dashboard.html')

@helpdesk_bp.route('/helpdesk/new_tickets')
@login_required
def new_tickets():
    if current_user.role not in ['admin', 'leader']:
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('auth.login'))

    department_id = get_user_department()

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT t.ticket_id, t.user_id, u.full_name, t.service, t.subservice, t.status, t.creation_date
        FROM ticket t
        JOIN User u ON t.user_id = u.id
        WHERE t.status = 'new'
    """)
    unassigned_tickets = cursor.fetchall()

    cursor.close()
    connection.close()

    current_time = datetime.utcnow()
    return render_template('helpdesk/new_tickets.html', unassigned_tickets=unassigned_tickets, current_time=current_time)

@helpdesk_bp.route('/helpdesk/in_progress_tickets')
@login_required
def in_progress_tickets():
    if current_user.role not in ['admin', 'leader']:
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('auth.login'))

    user_id = session.get('id')
    department_id = get_user_department()

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT t.ticket_id, t.user_id, u.full_name, t.service, t.subservice, t.status, t.creation_date
        FROM ticket t
        JOIN User u ON t.user_id = u.id
        WHERE t.status = 'open' AND t.assigned_admin_id = %s
    """, (user_id,))
    my_tickets = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('helpdesk/in_progress_tickets.html', my_tickets=my_tickets)

@helpdesk_bp.route('/helpdesk/closed_tickets')
@login_required
def closed_tickets():
    if current_user.role not in ['admin', 'leader']:
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('auth.login'))

    user_id = session.get('id')
    department_id = get_user_department()

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT t.ticket_id, t.user_id, u.full_name, t.service, t.subservice, t.status, t.creation_date, t.close_date
        FROM ticket t
        JOIN User u ON t.user_id = u.id
        WHERE t.status = 'close' AND t.assigned_admin_id = %s
    """, (user_id,))
    closed_tickets = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('helpdesk/closed_tickets.html', closed_tickets=closed_tickets)

@helpdesk_bp.route('/helpdesk/index')
@login_required
def index():
    if current_user.role not in ['admin', 'leader']:
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('auth.login'))
    
    # Получаем статистику тикетов
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Получаем количество новых тикетов
    cursor.execute("SELECT COUNT(*) as count FROM ticket WHERE status = 'new'")
    new_tickets_count = cursor.fetchone()['count']
    
    # Получаем количество тикетов в работе
    cursor.execute("SELECT COUNT(*) as count FROM ticket WHERE status = 'open'")
    in_progress_tickets_count = cursor.fetchone()['count']
    
    # Получаем количество решенных тикетов
    cursor.execute("SELECT COUNT(*) as count FROM ticket WHERE status = 'close'")
    resolved_tickets_count = cursor.fetchone()['count']
    
    # Общее количество тикетов
    total_tickets = new_tickets_count + in_progress_tickets_count + resolved_tickets_count
    
    # Получаем последние тикеты
    cursor.execute("""
        SELECT t.ticket_id as id, t.service as subject, t.status, t.creation_date as created_at, 
               COALESCE(u.department_name, 'Не указан') as department
        FROM ticket t
        LEFT JOIN User u ON t.user_id = u.id
        ORDER BY t.creation_date DESC
        LIMIT 5
    """)
    recent_tickets = cursor.fetchall()
    
    # Получаем статистику по отделам
    cursor.execute("""
        SELECT 
            COALESCE(d.name, u.department_name, 'Не указан') as name,
            SUM(CASE WHEN t.status = 'new' THEN 1 ELSE 0 END) as new,
            SUM(CASE WHEN t.status = 'open' THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN t.status = 'close' THEN 1 ELSE 0 END) as resolved,
            COUNT(*) as total
        FROM ticket t
        LEFT JOIN User u ON t.user_id = u.id
        LEFT JOIN Department d ON u.department_id = d.id
        GROUP BY COALESCE(d.name, u.department_name, 'Не указан')
    """)
    department_stats = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    return render_template(
        'helpdesk/index.html',
        new_tickets_count=new_tickets_count,
        in_progress_tickets_count=in_progress_tickets_count,
        resolved_tickets_count=resolved_tickets_count,
        total_tickets=total_tickets,
        recent_tickets=recent_tickets or [],
        department_stats=department_stats or []
    )