from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.utils import create_db_connection
from datetime import datetime, timedelta
import json

vats_bp = Blueprint('vats', __name__)

@vats_bp.route('/vats')
@login_required
def index():
    if not current_user.is_authenticated or (current_user.role != 'admin' and current_user.role != 'backoffice'):
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('main.index'))
    return render_template('vats/index.html')

@vats_bp.route('/api/get_free_numbers')
@login_required
def get_free_numbers():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT p.id, p.phone_number, p.purpose
            FROM phone_numbers p
            LEFT JOIN operator_numbers o ON p.id = o.phone_id
            WHERE o.phone_id IS NULL AND p.is_active = 1
        """)
        numbers = cursor.fetchall()
        return jsonify({'success': True, 'numbers': numbers})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@vats_bp.route('/api/get_operators')
@login_required
def get_operators():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT o.id, o.name, o.status,
                   GROUP_CONCAT(p.phone_number) as phone_numbers,
                   GROUP_CONCAT(p.id) as phone_ids
            FROM vats_operators o
            LEFT JOIN operator_numbers op ON o.id = op.operator_id
            LEFT JOIN phone_numbers p ON op.phone_id = p.id
            WHERE o.is_active = 1
            GROUP BY o.id
        """)
        operators = cursor.fetchall()
        return jsonify({'success': True, 'operators': operators})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@vats_bp.route('/api/assign_numbers', methods=['POST'])
@login_required
def assign_numbers():
    data = request.json
    operator_id = data.get('operator_id')
    number_ids = data.get('number_ids', [])
    
    if not operator_id or not number_ids:
        return jsonify({'success': False, 'message': 'Не указан оператор или номера'})
    
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        # Удаляем старые назначения
        cursor.execute("DELETE FROM operator_numbers WHERE operator_id = %s", (operator_id,))
        
        # Добавляем новые назначения
        for number_id in number_ids:
            cursor.execute("""
                INSERT INTO operator_numbers (operator_id, phone_id)
                VALUES (%s, %s)
            """, (operator_id, number_id))
            
            # Добавляем запись в историю
            cursor.execute("""
                INSERT INTO phone_history (phone_id, operator_id, action_type, action_date)
                VALUES (%s, %s, 'assign', NOW())
            """, (number_id, operator_id))
        
        connection.commit()
        flash('Номера успешно назначены оператору', 'success')
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@vats_bp.route('/api/delete_operator/<int:operator_id>', methods=['DELETE'])
@login_required
def delete_operator(operator_id):
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        # Освобождаем номера оператора
        cursor.execute("DELETE FROM operator_numbers WHERE operator_id = %s", (operator_id,))
        # Помечаем оператора как неактивного
        cursor.execute("UPDATE vats_operators SET is_active = 0 WHERE id = %s", (operator_id,))
        connection.commit()
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@vats_bp.route('/api/get_phone_history')
@login_required
def get_phone_history():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT ph.*, p.phone_number, o.name as operator_name
            FROM phone_history ph
            JOIN phone_numbers p ON ph.phone_id = p.id
            JOIN vats_operators o ON ph.operator_id = o.id
            ORDER BY ph.action_date DESC
        """)
        history = cursor.fetchall()
        
        # Преобразуем datetime в строку для JSON
        for record in history:
            record['action_date'] = record['action_date'].strftime('%Y-%m-%d %H:%M:%S')
            
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@vats_bp.route('/api/get_stats')
@login_required
def get_stats():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем количество изменений за сегодня
        today = datetime.now().date()
        cursor.execute("""
            SELECT COUNT(*) as changes_today
            FROM phone_history
            WHERE DATE(action_date) = %s
        """, (today,))
        changes_today = cursor.fetchone()['changes_today']
        
        # Получаем количество активных номеров
        cursor.execute("""
            SELECT COUNT(*) as active_numbers
            FROM phone_numbers
            WHERE is_active = 1
        """)
        active_numbers = cursor.fetchone()['active_numbers']
        
        # Получаем количество операторов
        cursor.execute("""
            SELECT COUNT(*) as operators_count
            FROM vats_operators
            WHERE is_active = 1
        """)
        operators_count = cursor.fetchone()['operators_count']
        
        # Получаем количество свободных номеров
        cursor.execute("""
            SELECT COUNT(*) as free_numbers
            FROM phone_numbers p
            LEFT JOIN operator_numbers o ON p.id = o.phone_id
            WHERE o.phone_id IS NULL AND p.is_active = 1
        """)
        free_numbers = cursor.fetchone()['free_numbers']
        
        return jsonify({
            'success': True,
            'stats': {
                'changes_today': changes_today,
                'active_numbers': active_numbers,
                'operators_count': operators_count,
                'free_numbers': free_numbers
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@vats_bp.route('/api/bulk_delete_phones', methods=['POST'])
@login_required
def bulk_delete_phones():
    data = request.json
    phone_ids = data.get('phone_ids', [])
    
    if not phone_ids:
        return jsonify({'success': False, 'message': 'Не указаны номера для удаления'})
    
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        # Проверяем, не назначены ли номера операторам
        cursor.execute("""
            SELECT p.phone_number
            FROM phone_numbers p
            JOIN operator_numbers o ON p.id = o.phone_id
            WHERE p.id IN %s
        """, (tuple(phone_ids),))
        assigned_numbers = cursor.fetchall()
        
        if assigned_numbers:
            numbers_list = ', '.join([n[0] for n in assigned_numbers])
            return jsonify({
                'success': False,
                'message': f'Следующие номера назначены операторам: {numbers_list}'
            })
        
        # Удаляем номера
        cursor.execute("""
            UPDATE phone_numbers
            SET is_active = 0
            WHERE id IN %s
        """, (tuple(phone_ids),))
        
        connection.commit()
        return jsonify({
            'success': True,
            'message': f'Успешно удалено номеров: {cursor.rowcount}'
        })
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@vats_bp.route('/api/upload_phones', methods=['POST'])
@login_required
def upload_phones():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Файл не найден'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Файл не выбран'})
    
    if not file.filename.endswith('.xlsx'):
        return jsonify({'success': False, 'message': 'Поддерживаются только файлы Excel (.xlsx)'})
    
    try:
        import pandas as pd
        df = pd.read_excel(file)
        
        if 'phone_number' not in df.columns or 'purpose' not in df.columns:
            return jsonify({
                'success': False,
                'message': 'Файл должен содержать столбцы "phone_number" и "purpose"'
            })
        
        connection = create_db_connection()
        cursor = connection.cursor()
        
        added_count = 0
        duplicate_count = 0
        invalid_count = 0
        
        for _, row in df.iterrows():
            phone = str(row['phone_number'])
            purpose = str(row['purpose'])
            
            # Проверяем формат номера
            if not phone.isdigit() or len(phone) != 11:
                invalid_count += 1
                continue
            
            # Проверяем на дубликаты
            cursor.execute("SELECT id FROM phone_numbers WHERE phone_number = %s", (phone,))
            if cursor.fetchone():
                duplicate_count += 1
                continue
            
            # Добавляем номер
            cursor.execute("""
                INSERT INTO phone_numbers (phone_number, purpose, is_active)
                VALUES (%s, %s, 1)
            """, (phone, purpose))
            added_count += 1
        
        connection.commit()
        
        return jsonify({
            'success': True,
            'message': f'Добавлено: {added_count}, Дубликатов: {duplicate_count}, Некорректных: {invalid_count}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close() 