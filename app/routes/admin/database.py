from flask import Blueprint, render_template, jsonify, send_file, current_app
from flask_login import login_required
from app.decorators import admin_required
from app.utils import create_db_connection, execute_sql_file
import os
import subprocess
import tempfile
import datetime
import pymysql
import decimal

bp = Blueprint('admin_database', __name__)

@bp.route('/settings/database', methods=['GET'])
@login_required
@admin_required
def index():
    """Страница «База данных»"""
    return render_template('admin/settings/database.html', active_tab='database')

@bp.route('/settings/database/tables', methods=['GET'])
@login_required
@admin_required
def get_tables():
    """Возвращает статистику всех таблиц"""
    conn = create_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Нет подключения к базе данных'}), 500
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute('SHOW TABLE STATUS')
    tables = cur.fetchall()
    cur.close()
    conn.close()
    # Приводим числовые значения к int для JSON
    for tbl in tables:
        for key, val in tbl.items():
            if isinstance(val, (int, float, decimal.Decimal)):
                tbl[key] = int(val)
            if isinstance(val, datetime.datetime):
                tbl[key] = val.strftime('%Y-%m-%d %H:%M:%S')
    return jsonify({'success': True, 'tables': tables})

@bp.route('/settings/database/optimize', methods=['POST'])
@login_required
@admin_required
def optimize_db():
    """Оптимизирует все таблицы"""
    conn = create_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Нет подключения к базе данных'}), 500
    cur = conn.cursor()
    cur.execute('SHOW TABLES')
    tables = [row[0] for row in cur.fetchall()]
    success = True
    for tbl in tables:
        try:
            cur.execute(f'OPTIMIZE TABLE `{tbl}`')
        except Exception as e:
            current_app.logger.error(f'OPTIMIZE TABLE {tbl} error: {e}')
            success = False
    conn.close()
    if success:
        return jsonify({'success': True, 'message': 'Оптимизация завершена'})
    else:
        return jsonify({'success': False, 'message': 'Оптимизация завершена с ошибками'})

@bp.route('/settings/database/backup', methods=['GET'])
@login_required
@admin_required
def backup_db():
    """Скачивает SQL-дамп базы через mysqldump (если доступно)"""
    cfg = current_app.config
    db_host = cfg.get('DB_HOST', 'localhost')
    db_user = cfg.get('DB_USER', 'root')
    db_pass = cfg.get('DB_PASSWORD', '')
    db_name = cfg.get('DB_NAME', 'crm')

    dump_file = tempfile.NamedTemporaryFile(delete=False, suffix='.sql')
    dump_file.close()
    cmd = [
        'mysqldump',
        f'-h{db_host}',
        f'-u{db_user}',
        f'-p{db_pass}',
        '--single-transaction',
        '--quick',
        '--skip-lock-tables',
        db_name,
    ]
    try:
        with open(dump_file.name, 'wb') as f:
            subprocess.check_call(cmd, stdout=f)
    except Exception as e:
        current_app.logger.error(f'mysqldump error: {e}')
        return jsonify({'success': False, 'message': 'Ошибка при создании дампа. Проверьте наличие mysqldump и доступы'}), 500

    filename = f'{db_name}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.sql'
    return send_file(dump_file.name, as_attachment=True, download_name=filename, mimetype='application/sql')

@bp.route('/settings/database/restore', methods=['POST'])
@login_required
@admin_required
def restore_db():
    """Восстанавливает базу данных из загруженного SQL-файла"""
    from flask import request
    if 'sql_file' not in request.files:
        return jsonify({'success': False, 'message': 'Файл не передан'}), 400
    file = request.files['sql_file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Файл не выбран'}), 400
    tmp_path = tempfile.mktemp(suffix='.sql')
    file.save(tmp_path)
    ok = execute_sql_file(tmp_path)
    os.remove(tmp_path)
    if ok:
        return jsonify({'success': True, 'message': 'База успешно восстановлена'}), 200
    else:
        return jsonify({'success': False, 'message': 'Ошибка при восстановлении базы'}), 500 