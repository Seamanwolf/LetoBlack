from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from app.decorators import admin_required
from app.utils import create_db_connection
import pymysql
import datetime

bp = Blueprint('admin_logs', __name__)

@bp.route('/settings/logs')
@login_required
@admin_required
def index():
    """Страница логов"""
    return render_template('admin/settings/logs.html', active_tab='logs')

@bp.route('/settings/logs/data')
@login_required
@admin_required
def logs_data():
    """Возвращает логи в JSON с фильтрами"""
    args = request.args
    username = args.get('username')
    action = args.get('action')
    status = args.get('status')
    date_from = args.get('date_from')
    date_to = args.get('date_to')
    limit = int(args.get('limit', 200))

    conn = create_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'DB connection error'}), 500
    cur = conn.cursor(pymysql.cursors.DictCursor)
    sql = 'SELECT * FROM audit_log WHERE 1=1'
    params = []
    if username:
        sql += ' AND username LIKE %s'
        params.append(f'%{username}%')
    if action:
        sql += ' AND action = %s'
        params.append(action)
    if status:
        sql += ' AND status = %s'
        params.append(status)
    if date_from:
        sql += ' AND timestamp >= %s'
        params.append(date_from)
    if date_to:
        sql += ' AND timestamp <= %s'
        params.append(date_to)
    sql += ' ORDER BY timestamp DESC LIMIT %s'
    params.append(limit)
    cur.execute(sql, params)
    logs = cur.fetchall()
    cur.close()
    conn.close()

    actions = sorted({log['action'] for log in logs})
    statuses = sorted({log['status'] for log in logs})

    # Convert datetime to string
    for log in logs:
        if isinstance(log.get('timestamp'), (datetime.datetime, datetime.date)):
            log['timestamp'] = log['timestamp'].strftime('%Y-%m-%d %H:%M:%S')

    return jsonify({'success': True, 'logs': logs, 'actions': actions, 'statuses': statuses}) 