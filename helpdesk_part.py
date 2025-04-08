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
