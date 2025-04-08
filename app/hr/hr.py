from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from flask_login import current_user, login_required
import mysql.connector
from datetime import datetime, timedelta, date
from app.utils import create_db_connection
import json

hr_bp = Blueprint('hr', __name__, template_folder='templates/hr')

@hr_bp.route('/candidates', methods=['GET'])
@login_required
def candidates_list():
    current_app.logger.debug("Вызов маршрута /candidates")
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        current_app.logger.debug("Недостаточно прав: role=%s, department=%s", current_user.role, current_user.department)
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем список кандидатов
        query = """
            SELECT *, IF(is_new = 1 AND edit_opened = 0, 1, 0) AS is_new 
            FROM Candidates WHERE archived = 0
        """
        current_app.logger.debug("Выполняется запрос: %s", query)
        cursor.execute(query)
        candidates = cursor.fetchall()
        current_app.logger.debug("Найдено кандидатов: %s", len(candidates))
        
        # Получаем список всех отделов из колонки Department таблицы User
        query_departments = "SELECT DISTINCT Department FROM User WHERE Department IS NOT NULL AND Department != '' ORDER BY Department"
        current_app.logger.debug("Выполняется запрос для получения отделов: %s", query_departments)
        cursor.execute(query_departments)
        departments_records = cursor.fetchall()
        departments = [department['Department'] for department in departments_records]
        current_app.logger.debug("Найдено отделов: %s", len(departments))
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка выборки кандидатов или отделов: %s", err)
        flash("Ошибка базы данных.", "danger")
        candidates = []
        departments = []
    finally:
        cursor.close()
        connection.close()
    return render_template("hr/candidates_list.html", candidates=candidates, departments=departments)

@hr_bp.route('/candidate/<int:candidate_id>', methods=['GET'])
@login_required
def candidate_data(candidate_id):
    current_app.logger.debug("Вызов candidate_data для id=%s", candidate_id)
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Candidates WHERE id = %s", (candidate_id,))
        candidate = cursor.fetchone()
        if candidate:
            # Приведение дат к формату YYYY-MM-DD
            for key in ['birth_date', 'exit_date_1', 'exit_date_7']:
                value = candidate.get(key)
                if value is not None:
                    if isinstance(value, datetime):
                        candidate[key] = value.strftime('%Y-%m-%d')
                    else:
                        candidate[key] = value
            # Если поле manager_full_name отсутствует, заполняем его значением из rop
            if not candidate.get("manager_full_name"):
                candidate["manager_full_name"] = candidate.get("rop", "")
            current_app.logger.debug("Данные кандидата: %s", candidate)
            return jsonify(candidate)
        else:
            current_app.logger.debug("Кандидат с id=%s не найден", candidate_id)
            return jsonify({"error": "Кандидат не найден"}), 404
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка candidate_data: %s", err)
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@hr_bp.route('/candidates/add', methods=['GET', 'POST'])
@login_required
def add_candidate():
    current_app.logger.debug("Вызов add_candidate, метод=%s", request.method)
    
    # Проверяем права: только backoffice + HR
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        flash("Доступ запрещён.", "danger")
        current_app.logger.debug("Недостаточно прав для добавления кандидата")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        # Считываем поля из формы
        full_name = request.form.get("full_name")
        department = request.form.get("department")
        position = request.form.get("position")
        manager_full_name = request.form.get("manager_full_name")  # из скрытого поля
        current_app.logger.debug(
            "Данные формы добавления кандидата: full_name=%s, department=%s, position=%s, manager_full_name=%s, form=%s",
            full_name, department, position, manager_full_name, request.form
        )
        
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            # Автоподстановка "РОП" (ищем лидера в данном отделе)
            cursor.execute("SELECT full_name FROM User WHERE role = 'leader' AND department = %s LIMIT 1", (department,))
            leader = cursor.fetchone()
            rop = leader['full_name'] if leader else ''
            current_app.logger.debug("Подставляем РОП: %s", rop)

            # Выполняем INSERT в таблицу Candidates
            # Обратите внимание, что теперь добавили manager_full_name в список колонок
            query = """
                INSERT INTO Candidates (full_name, department, position, rop, manager_full_name, is_new, login_pc)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            current_app.logger.debug("Выполняется запрос добавления кандидата: %s", query)
            cursor.execute(
                query,
                (full_name, department, position, rop, manager_full_name, 1, "")
            )
            connection.commit()
            candidate_id = cursor.lastrowid

            # Логируем факт создания кандидата (CandidateHistory)
            now = datetime.now()
            now_formatted = now.strftime("%d.%m.%Y %H:%M")
            log_query = """
                INSERT INTO CandidateHistory (candidate_id, timestamp, user, field_changed, old_value, new_value)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(log_query, (
                candidate_id,
                now,
                current_user.full_name,
                "creation",  # условная метка "creation"
                "",
                now_formatted
            ))
            connection.commit()

            flash("Новый кандидат добавлен. Не забудьте заполнить остальные данные.", "success")
            current_app.logger.debug("Кандидат успешно добавлен с записью о создании")

        except mysql.connector.Error as err:
            connection.rollback()
            current_app.logger.error("Ошибка при добавлении кандидата: %s", err)
            flash("Ошибка при добавлении кандидата: " + str(err), "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for("hr.candidates_list"))

    return render_template("hr/add_candidate.html")


@hr_bp.route('/candidates/edit/<int:candidate_id>', methods=['GET', 'POST'])
@login_required
def edit_candidate(candidate_id):
    current_app.logger.debug("Вызов edit_candidate для id=%s, метод=%s", candidate_id, request.method)
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        current_app.logger.debug("Недостаточно прав для редактирования кандидата: role=%s, department=%s", current_user.role, current_user.department)
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    if request.method == 'POST':
        current_app.logger.debug("Получены данные формы редактирования: %s", request.form)
        new_data = {
            "full_name": request.form.get("full_name"),
            "department": request.form.get("department"),
            "position": request.form.get("position"),
            "city": request.form.get("city"),
            "personal_email": request.form.get("personal_email"),
            "birth_date": request.form.get("birth_date") or None,
            "exit_date_1": request.form.get("exit_date_1") or None,
            "exit_date_7": request.form.get("exit_date_7") or None,
            "referral": request.form.get("referral"),
            "manager_full_name": request.form.get("manager_full_name"),
            "status": request.form.get("status")
        }
        now = datetime.now()
        try:
            # Получаем старые данные для логирования изменений
            cursor.execute("SELECT * FROM Candidates WHERE id = %s", (candidate_id,))
            old_data = cursor.fetchone()
            current_app.logger.debug("Старые данные кандидата: %s", old_data)
            query = """
            UPDATE Candidates
            SET full_name=%s, department=%s, position=%s, city=%s, personal_email=%s,
                birth_date=%s, exit_date_1=%s, exit_date_7=%s, referral=%s, manager_full_name=%s,
                status=%s, updated_at=%s, is_new=%s, edit_opened=%s
            WHERE id=%s
            """
            current_app.logger.debug("Выполняется запрос UPDATE кандидата: %s", query)
            cursor.execute(query, (
                new_data["full_name"], new_data["department"], new_data["position"], 
                new_data["city"], new_data["personal_email"], new_data["birth_date"], 
                new_data["exit_date_1"], new_data["exit_date_7"], new_data["referral"], 
                new_data["manager_full_name"], new_data["status"], now, 0, 0, candidate_id))
            current_app.logger.debug("Запрос UPDATE выполнен успешно")
            # Логирование изменений по каждому полю
            for field in new_data:
                old_val = old_data.get(field) if old_data.get(field) is not None else ""
                new_val = new_data[field] if new_data[field] is not None else ""
                if str(old_val) != str(new_val):
                    log_query = """
                    INSERT INTO CandidateHistory (candidate_id, timestamp, user, field_changed, old_value, new_value)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    current_app.logger.debug("Логирование изменения поля %s: старое=%s, новое=%s", field, old_val, new_val)
                    cursor.execute(log_query, (candidate_id, now, current_user.full_name, field, old_val, new_val))
            connection.commit()
            current_app.logger.debug("Изменения кандидата сохранены")
            # Если запрос сделан через AJAX, возвращаем JSON и не перезагружаем страницу
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Данные кандидата обновлены.'})
            else:
                flash("Данные кандидата обновлены.", "success")
                return redirect(url_for("hr.candidates_list"))
        except mysql.connector.Error as err:
            connection.rollback()
            current_app.logger.error("Ошибка при обновлении кандидата %s: %s", candidate_id, err)
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': str(err)}), 500
            else:
                flash("Ошибка при обновлении кандидата: " + str(err), "danger")
                return redirect(url_for("hr.candidates_list"))
        finally:
            cursor.close()
            connection.close()
    else:
        try:
            cursor.execute("SELECT * FROM Candidates WHERE id=%s", (candidate_id,))
            candidate = cursor.fetchone()
            current_app.logger.debug("Данные кандидата для редактирования: %s", candidate)
        except mysql.connector.Error as err:
            candidate = None
            current_app.logger.error("Ошибка при получении данных кандидата: %s", err)
            flash("Ошибка при получении данных кандидата: " + str(err), "danger")
        finally:
            cursor.close()
            connection.close()
        return render_template("hr/edit_candidate.html", candidate=candidate)

@hr_bp.route('/candidate/archive/<int:candidate_id>', methods=['POST'])
@login_required
def archive_candidate(candidate_id):
    current_app.logger.debug("Вызов archive_candidate для id=%s", candidate_id)
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        current_app.logger.debug("Недостаточно прав для архивирования кандидата")
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    
    connection = create_db_connection()
    cursor = connection.cursor()
    now = datetime.now()
    try:
        # Сначала получаем текущий статус кандидата для логирования
        cursor.execute("SELECT status FROM Candidates WHERE id = %s", (candidate_id,))
        result = cursor.fetchone()
        current_status = result[0] if result else ""
        
        # Обновляем запись кандидата: перевод в архив и очищаем корпоративный номер
        query = """
            UPDATE Candidates 
            SET status = %s, archived = 1, archive_date = %s, corporate_number = NULL, login_pc = ''
            WHERE id = %s
        """
        cursor.execute(query, ("Не вышел", now, candidate_id))
        connection.commit()
        
        # Открепляем номер в таблице user_phone_numbers, если он был назначен кандидату
        cursor.execute("UPDATE user_phone_numbers SET assigned_operator_id = NULL WHERE assigned_operator_id = %s", (candidate_id,))
        connection.commit()
        
        current_app.logger.debug("Кандидат переведен в архив и номер очищен, id=%s", candidate_id)
        
        # Логирование архивирования
        log_query = """
            INSERT INTO CandidateHistory (candidate_id, timestamp, user, field_changed, old_value, new_value)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(log_query, (candidate_id, now, current_user.full_name, "status", current_status, "Кандидат перемещён в архив"))
        connection.commit()
        return jsonify({"success": True, "reload": True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка архивирования кандидата %s: %s", candidate_id, err)
        flash("Ошибка архивирования кандидата: " + str(err), "danger")
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@hr_bp.route('/candidate/set_edit_opened/<int:candidate_id>', methods=['POST'])
@login_required
def set_edit_opened(candidate_id):
    current_app.logger.debug("Вызов set_edit_opened для id=%s", candidate_id)
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        current_app.logger.debug("Доступ запрещён для установки edit_opened")
        return jsonify({"error": "Доступ запрещён"}), 403
    new_state = request.form.get('edit_opened', 1)
    current_app.logger.debug("Новое значение edit_opened: %s", new_state)
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        query = "UPDATE Candidates SET edit_opened=%s WHERE id=%s"
        cursor.execute(query, (new_state, candidate_id))
        connection.commit()
        current_app.logger.debug("edit_opened обновлён для кандидата %s на %s", candidate_id, new_state)
        return jsonify({"success": True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка обновления edit_opened для кандидата %s: %s", candidate_id, err)
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@hr_bp.route('/candidate/history/<int:candidate_id>', methods=['GET'])
@login_required
def candidate_history(candidate_id):
    current_app.logger.debug("Вызов candidate_history для id=%s", candidate_id)
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        query = "SELECT * FROM CandidateHistory WHERE candidate_id = %s ORDER BY timestamp DESC"
        current_app.logger.debug("Выполняется запрос истории: %s", query)
        cursor.execute(query, (candidate_id,))
        history = cursor.fetchall()
        current_app.logger.debug("Найдено записей истории: %s", len(history))
        return jsonify(history)
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка получения истории изменений для кандидата %s: %s", candidate_id, err)
        return jsonify([]), 500
    finally:
        cursor.close()
        connection.close()

@hr_bp.route('/candidates/archive', methods=['GET'])
@login_required
def archive_candidates():
    current_app.logger.debug("Вызов archive_candidates")
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        current_app.logger.debug("Доступ запрещён для просмотра архивных кандидатов")
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Candidates WHERE archived = 1")
        archived = cursor.fetchall()
        current_app.logger.debug("Найдено архивированных кандидатов: %s", len(archived))
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка получения архивных кандидатов: %s", err)
        flash("Ошибка при получении архивных кандидатов: " + str(err), "danger")
        archived = []
    finally:
        cursor.close()
        connection.close()
    return render_template("hr/archive_candidates.html", candidates=archived)

@hr_bp.route('/candidates/restore/<int:candidate_id>', methods=['POST'])
@login_required
def restore_candidate(candidate_id):
    current_app.logger.debug("Вызов restore_candidate для id=%s", candidate_id)
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        current_app.logger.debug("Доступ запрещён для восстановления кандидата")
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        query = "UPDATE Candidates SET archived=0, archive_date=NULL, status=%s WHERE id=%s"
        cursor.execute(query, ("", candidate_id))
        connection.commit()
        current_app.logger.debug("Кандидат %s восстановлен", candidate_id)
        
        # Добавим запись в историю
        now = datetime.now()
        log_query = """
            INSERT INTO CandidateHistory (candidate_id, timestamp, user, field_changed, old_value, new_value)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(log_query, (
            candidate_id, now, current_user.full_name,
            "архивирован", "1", "0"
        ))
        connection.commit()
        
        # Проверяем, какой тип ответа нужно вернуть
        if request.is_json:
            return jsonify({"success": True})
        else:
            flash("Кандидат восстановлен.", "success")
            return redirect(url_for("hr.archive_candidates"))
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка при восстановлении кандидата %s: %s", candidate_id, err)
        if request.is_json:
            return jsonify({"success": False, "error": str(err)}), 500
        else:
            flash("Ошибка при восстановлении кандидата: " + str(err), "danger")
            return redirect(url_for("hr.archive_candidates"))
    finally:
        cursor.close()
        connection.close()

@hr_bp.route('/candidates/delete/<int:candidate_id>', methods=['POST'])
@login_required
def delete_candidate(candidate_id):
    current_app.logger.debug("Вызов delete_candidate для id=%s", candidate_id)
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        current_app.logger.debug("Доступ запрещён для удаления кандидата")
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        query = "DELETE FROM Candidates WHERE id=%s AND archived=1"
        cursor.execute(query, (candidate_id,))
        if cursor.rowcount == 0:
            current_app.logger.debug("Удаление не выполнено для кандидата %s: кандидат не найден или не архивирован", candidate_id)
            flash("Удаление не выполнено. Кандидат не найден или не архивирован.", "danger")
        else:
            connection.commit()
            current_app.logger.debug("Кандидат %s удалён", candidate_id)
            flash("Кандидат удалён навсегда.", "success")
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка при удалении кандидата %s: %s", candidate_id, err)
        flash("Ошибка при удалении кандидата: " + str(err), "danger")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("hr.archive_candidates"))

@hr_bp.route('/candidate/transfer_it/<int:candidate_id>', methods=['POST'])
@login_required
def transfer_to_it(candidate_id):
    current_app.logger.debug("Вызов transfer_to_it для id=%s", candidate_id)
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        current_app.logger.debug("Недостаточно прав для передачи кандидата в ИТ")
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    connection = create_db_connection()
    cursor = connection.cursor()
    now = datetime.now()
    try:
        query = "UPDATE Candidates SET login_pc=%s WHERE id=%s"
        cursor.execute(query, ("В работе", candidate_id))
        connection.commit()
        current_app.logger.debug("Поле login_pc обновлено для кандидата %s", candidate_id)
        log_query = """
            INSERT INTO CandidateHistory (candidate_id, timestamp, user, field_changed, old_value, new_value)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(log_query, (candidate_id, now, current_user.full_name, "login_pc", "", "В работе"))
        connection.commit()
        current_app.logger.debug("Логирование передачи в ИТ выполнено")
        return jsonify({"success": True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка передачи в ИТ для кандидата %s: %s", candidate_id, err)
        flash("Ошибка передачи в ИТ: " + str(err), "danger")
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@hr_bp.route('/candidate/transfer_it/<int:candidate_id>', methods=['POST'])
def transfer_it(candidate_id):
    current_app.logger.debug("Вызов transfer_it для id=%s", candidate_id)
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        update_sql = "UPDATE Candidates SET transferred_to_it=1 WHERE id=%s"
        current_app.logger.debug("Выполняем запрос: %s, candidate_id=%s", update_sql, candidate_id)
        cursor.execute(update_sql, (candidate_id,))
        connection.commit()
        current_app.logger.debug("Установили transferred_to_it=1 у кандидата %s", candidate_id)
        
        # Дополнительная проверка:
        cursor.execute("SELECT transferred_to_it FROM Candidates WHERE id=%s", (candidate_id,))
        result = cursor.fetchone()
        current_app.logger.debug("После обновления, transferred_to_it=%s", result.get('transferred_to_it'))
        
        # Логирование в истории:
        now = datetime.now()
        log_query = """
            INSERT INTO CandidateHistory (candidate_id, timestamp, user, field_changed, old_value, new_value)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(log_query, (
            candidate_id, now, current_user.full_name,
            "transferred_to_it", "0", "1"
        ))
        connection.commit()
        current_app.logger.debug("Логирование передачи в ИТ выполнено")
        return jsonify({"success": True})
    except Exception as e:
        connection.rollback()
        current_app.logger.error("Ошибка transfer_it: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@hr_bp.route('/candidate/transfer_it_new/<int:candidate_id>', methods=['POST'])
@login_required
def transfer_it_new(candidate_id):
    current_app.logger.debug("Вызов transfer_it_new для id=%s", candidate_id)
    
    # Проверяем права HR
    if not (current_user.role == 'backoffice' and current_user.department == "HR"):
        current_app.logger.debug("Недостаточно прав для передачи кандидата в ИТ: role=%s, department=%s",
                                   current_user.role, current_user.department)
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем отдел кандидата
        cursor.execute("SELECT department FROM Candidates WHERE id = %s", (candidate_id,))
        candidate = cursor.fetchone()
        if not candidate:
            current_app.logger.error("Кандидат не найден")
            return jsonify({"success": False, "error": "Кандидат не найден"}), 404
        candidate_department = candidate['department']
        
        # Ищем свободный номер для данного отдела
        free_number_query = """
            SELECT id, phone_number 
            FROM user_phone_numbers 
            WHERE assigned_operator_id IS NULL 
              AND prohibit_issuance = 0
              AND department = %s
            ORDER BY id ASC
            LIMIT 1
        """
        current_app.logger.debug("Выполняется запрос свободного номера: %s", free_number_query)
        cursor.execute(free_number_query, (candidate_department,))
        free_number = cursor.fetchone()
        
        if not free_number:
            current_app.logger.error("Нет свободных номеров для выдачи для отдела %s", candidate_department)
            return jsonify({"success": False, "error": "Нет свободных номеров для выбранного отдела"}), 400
        
        assigned_phone = free_number['phone_number']
        
        # Обновляем запись кандидата: записываем номер в поле corporate_number
        update_candidate_sql = """
            UPDATE Candidates 
            SET transferred_to_it = 1, corporate_number = %s
            WHERE id = %s
        """
        cursor.execute(update_candidate_sql, (assigned_phone, candidate_id))
        
        # Обновляем таблицу номеров: отмечаем, что номер выдан кандидату
        update_number_sql = """
            UPDATE user_phone_numbers
            SET assigned_operator_id = %s
            WHERE id = %s
        """
        cursor.execute(update_number_sql, (candidate_id, free_number['id']))
        
        connection.commit()
        current_app.logger.debug("Номер %s передан кандидату id=%s", assigned_phone, candidate_id)
        return jsonify({"success": True, "assigned_phone": assigned_phone})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка передачи номера кандидату: %s", err)
        return jsonify({"success": False, "error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@hr_bp.route('/candidates/transferred', methods=['GET'])
@login_required
def transferred_candidates():
    current_app.logger.debug("Вызов transferred_candidates")
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        current_app.logger.debug("Доступ запрещён для просмотра переданных кандидатов")
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Выбираем всех кандидатов со статусом "вышел"
        cursor.execute("SELECT * FROM Candidates WHERE status = 'Вышел' AND archived = 0")
        candidates = cursor.fetchall()
        
        # Для каждого кандидата создаем поле с датой передачи
        for candidate in candidates:
            # Ищем запись в истории о смене статуса на "Вышел"
            history_query = """
                SELECT timestamp FROM CandidateHistory 
                WHERE candidate_id = %s 
                AND field_changed = 'status' 
                AND new_value = 'Вышел'
                ORDER BY timestamp DESC LIMIT 1
            """
            cursor.execute(history_query, (candidate['id'],))
            history_record = cursor.fetchone()
            
            if history_record:
                # Если есть запись, сохраняем дату
                transferred_date = history_record['timestamp']
                candidate['transferred_date'] = transferred_date
                
                # Рассчитываем, сколько дней прошло с момента передачи
                days_diff = (datetime.now() - transferred_date).days
                candidate['transferred_date_days'] = days_diff
            else:
                candidate['transferred_date'] = None
                candidate['transferred_date_days'] = None
                
            # Получаем историю изменений для этого кандидата
            cursor.execute("""
                SELECT * FROM CandidateHistory 
                WHERE candidate_id = %s 
                ORDER BY timestamp DESC
            """, (candidate['id'],))
            history = cursor.fetchall()
            
            # Обрабатываем историю для удобного отображения
            processed_history = []
            for entry in history:
                date_str = entry['timestamp'].strftime('%Y-%m-%d')
                time_str = entry['timestamp'].strftime('%H:%M:%S')
                
                history_item = {
                    'date': date_str,
                    'time': time_str,
                    'timestamp': entry['timestamp'],
                    'user': entry['user'],
                    'action': f"Изменил поле {entry['field_changed']}",
                    'changes': [{
                        'field': entry['field_changed'],
                        'old_value': entry['old_value'] or '—',
                        'new_value': entry['new_value'] or '—'
                    }]
                }
                processed_history.append(history_item)
            
            candidate['history'] = processed_history
            
        current_app.logger.debug("Найдено переданных кандидатов: %s", len(candidates))
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка получения переданных кандидатов: %s", err)
        flash("Ошибка при получении переданных кандидатов: " + str(err), "danger")
        candidates = []
    finally:
        cursor.close()
        connection.close()
    return render_template("hr/transferred_candidates.html", candidates=candidates)

@hr_bp.route('/candidates/clear_archive', methods=['POST'])
@login_required
def clear_archive():
    current_app.logger.debug("Вызов clear_archive")
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        current_app.logger.debug("Доступ запрещён для очистки архива кандидатов")
        return jsonify({"success": False, "error": "Доступ запрещён"}), 403
        
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        # Удаляем всех архивированных кандидатов
        query = "DELETE FROM Candidates WHERE archived = 1"
        cursor.execute(query)
        deleted_count = cursor.rowcount
        connection.commit()
        current_app.logger.debug("Удалено %s архивированных кандидатов", deleted_count)
        
        # Также можно удалить историю изменений для этих кандидатов,
        # но для этого потребуется дополнительная логика, так как
        # записи в CandidateHistory связаны с id кандидатов
        
        return jsonify({"success": True, "deleted_count": deleted_count})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка при очистке архива кандидатов: %s", err)
        return jsonify({"success": False, "error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@hr_bp.route('/candidates/statistics', methods=['GET'])
@login_required
def candidates_statistics():
    current_app.logger.debug("Вызов candidates_statistics")
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        current_app.logger.debug("Доступ запрещён для просмотра статистики кандидатов")
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    statistics = {}
    hr_stats = []  # Инициализируем переменную пустым списком
    
    try:
        # Общая статистика
        cursor.execute("SELECT COUNT(*) as total FROM Candidates WHERE archived = 0")
        statistics['total'] = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as archived FROM Candidates WHERE archived = 1")
        statistics['archived'] = cursor.fetchone()['archived']
        
        cursor.execute("SELECT COUNT(*) as transferred FROM Candidates WHERE status = 'Вышел' AND archived = 0")
        statistics['transferred'] = cursor.fetchone()['transferred']
        
        # Статистика по статусам
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM Candidates 
            WHERE archived = 0 
            GROUP BY status 
            ORDER BY count DESC
        """)
        statistics['by_status'] = cursor.fetchall()
        
        # Статистика по отделам
        cursor.execute("""
            SELECT department, COUNT(*) as count 
            FROM Candidates 
            WHERE archived = 0 
            GROUP BY department 
            ORDER BY count DESC
        """)
        statistics['by_department'] = cursor.fetchall()
        
        # Статистика по городам
        cursor.execute("""
            SELECT city, COUNT(*) as count 
            FROM Candidates 
            WHERE archived = 0 AND city IS NOT NULL AND city != ''
            GROUP BY city 
            ORDER BY count DESC
        """)
        statistics['by_city'] = cursor.fetchall()
        
        # Статистика по месяцам (добавленные кандидаты)
        cursor.execute("""
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') as month,
                COUNT(*) as count
            FROM Candidates
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """)
        statistics['by_month'] = cursor.fetchall()
        
        # Топ-5 рефералов
        cursor.execute("""
            SELECT referral, COUNT(*) as count 
            FROM Candidates 
            WHERE archived = 0 AND referral IS NOT NULL AND referral != ''
            GROUP BY referral 
            ORDER BY count DESC
            LIMIT 5
        """)
        statistics['top_referrals'] = cursor.fetchall()
        
        # Статистика по сотрудникам HR
        cursor.execute("""
            SELECT 
                h.user as name,
                COUNT(DISTINCT c.id) as added,
                SUM(CASE WHEN c.status = 'Вышел' THEN 1 ELSE 0 END) as transferred,
                SUM(CASE WHEN c.archived = 1 THEN 1 ELSE 0 END) as archived
            FROM 
                CandidateHistory h
            JOIN 
                Candidates c ON h.candidate_id = c.id
            WHERE 
                h.field_changed = 'creation'
            GROUP BY 
                h.user
            ORDER BY 
                added DESC
        """)
        hr_stats = cursor.fetchall()
        
        current_app.logger.debug("Статистика собрана успешно")
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка при получении статистики: %s", err)
        flash("Ошибка при получении статистики: " + str(err), "danger")
    finally:
        cursor.close()
        connection.close()
        
    return render_template("hr/candidates_statistics.html", statistics=statistics, hr_stats=hr_stats)

@hr_bp.route('/check_new_login_data', methods=['GET'])
@login_required
def check_new_login_data():
    current_app.logger.debug("Проверка наличия новых данных для входа")
    if not (current_user.role == 'backoffice' and current_user.department == 'HR'):
        return jsonify({"has_new_login_data": False}), 403
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Проверяем наличие новых данных для входа от IT за последние 30 минут
        # Это данные, где login_pc или password не пустые и были обновлены недавно
        query = """
        SELECT COUNT(*) as count FROM candidates 
        WHERE (login_pc IS NOT NULL AND login_pc != '' AND login_pc_updated_at > DATE_SUB(NOW(), INTERVAL 30 MINUTE))
        OR (password IS NOT NULL AND password != '' AND password_updated_at > DATE_SUB(NOW(), INTERVAL 30 MINUTE))
        """
        
        cursor.execute(query)
        result = cursor.fetchone()
        
        has_new_data = result['count'] > 0 if result else False
        
        return jsonify({"has_new_login_data": has_new_data})
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка при проверке новых данных для входа: %s", err)
        return jsonify({"has_new_login_data": False, "error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()
