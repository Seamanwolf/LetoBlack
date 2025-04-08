from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.utils import create_db_connection, login_required
from werkzeug.security import generate_password_hash
import os
from flask_login import login_required as flask_login_required, current_user
import traceback
from . import backoffice_bp


@backoffice_bp.route('/backoffice')
@login_required
def show_backoffice():
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('auth.login'))

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, login, full_name, department, Phone, hire_date FROM User WHERE role = 'backoffice'")
    backoffice_staff = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('backoffice.html', backoffice_staff=backoffice_staff)


@backoffice_bp.route('/api/get_backoffice_staff', methods=['GET'])
@login_required
def get_backoffice_staff():
    staff_id = request.args.get('id')

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, login, full_name, Phone, department, hire_date FROM User WHERE id = %s AND role = 'backoffice'", (staff_id,))
    staff = cursor.fetchone()
    cursor.close()
    connection.close()

    if not staff:
        return jsonify({'success': False, 'message': 'Сотрудник не найден'})

    return jsonify({'success': True, **staff})


@backoffice_bp.route('/api/add_backoffice_staff', methods=['POST'])
@login_required
def add_backoffice_staff():
    data = request.json

    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO User (login, full_name, Phone, department, hire_date, password, role)
            VALUES (%s, %s, %s, %s, %s, %s, 'backoffice')
        """, (
            data.get('login'),
            data.get('full_name'),
            data.get('Phone'),
            data.get('department'),
            data.get('hire_date'),
            generate_password_hash(data.get('password'))
        ))
        connection.commit()
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()


@backoffice_bp.route('/api/update_backoffice_staff', methods=['POST'])
@login_required
def update_backoffice_staff():
    data = request.json

    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE User
            SET login = %s, full_name = %s, Phone = %s, department = %s, hire_date = %s
            WHERE id = %s AND role = 'backoffice'
        """, (
            data.get('login'),
            data.get('full_name'),
            data.get('Phone'),
            data.get('department'),
            data.get('hire_date'),
            data.get('id')
        ))
        connection.commit()
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()


@backoffice_bp.route('/api/delete_backoffice_staff', methods=['POST'])
@login_required
def delete_backoffice_staff():
    staff_id = request.args.get('id')

    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM User WHERE id = %s AND role = 'backoffice'", (staff_id,))
        connection.commit()
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()


@backoffice_bp.route('/admin/users/change_password/<int:id>', methods=['POST'])
@login_required
def change_user_password(id):
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    if new_password != confirm_password:
        flash('Пароли не совпадают.', 'danger')
        return redirect(url_for('edit_user', id=id))

    hashed_password = generate_password_hash(new_password)
    connection = create_db_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE User SET password = %s WHERE id = %s", (hashed_password, id))
    connection.commit()
    cursor.close()
    connection.close()

    flash('Пароль успешно изменён.', 'success')
    return redirect(url_for('edit_user', id=id))

def fill_missing_days(scores):
    if not scores:
        return []

    # Создаем список всех дней за последние 7 дней
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)
    all_dates = [start_date + timedelta(days=i) for i in range(7)]

    # Преобразуем даты в формат YYYY-MM-DD
    all_dates_str = [date.strftime('%Y-%m-%d') for date in all_dates]

    # Создаем словарь, где ключи - даты, значения - отчеты за соответствующий день
    scores_dict = {score['date']: score for score in scores}

    filled_scores = []
    for date in all_dates_str:
        # Если есть отчет за текущий день, добавляем его в новый список
        if date in scores_dict:
            filled_scores.append(scores_dict[date])
        # Если отчета за текущий день нет, используем предыдущий отчет
        else:
            if filled_scores:
                # Копируем данные предыдущего дня
                previous_day_score = filled_scores[-1].copy()
                # Заменяем дату на текущий день
                previous_day_score['date'] = date
                filled_scores.append(previous_day_score)

    return filled_scores
