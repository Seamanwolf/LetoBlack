from flask import Blueprint, Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, send_from_directory, abort
from werkzeug.security import check_password_hash
from app.utils import authenticate_user, update_operator_status
from datetime import datetime
from app.utils import login_required
from . import itinvent_bp
from flask_login import login_required as flask_login_required, current_user

def format_date(date):
    if date:
        try:
            return date.strftime('%d-%m-%Y')
        except AttributeError:
            return date
    return None

def format_active_time(seconds):
    if seconds is None:
        return "0 сек"
    
    hours = seconds // 3600
    remaining = seconds % 3600
    minutes = remaining // 60
    secs = remaining % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours} ч")
    if minutes > 0:
        parts.append(f"{minutes} мин")
    if secs > 0:
        parts.append(f"{secs} сек")
    
    if not parts:
        return "0 сек"
    
    return ' '.join(parts)

@itinvent_bp.route('/it_tech')
@login_required
def it_tech_dashboard():
    status = request.args.get('status', 'active')
    return render_template('it_tech_dashboard.html', status=status)

@itinvent_bp.route('/api/get_all_data', methods=['GET'])
def get_all_data():
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT
            t.id,
            c.name AS city,
            f.floor AS floor,
            d.name AS department,
            r.room AS room,
            et.type AS equipment_type,
            b.brand AS brand,
            m.model AS model,
            t.serial_number,
            t.inventory_number,
            DATE_FORMAT(t.purchase_date, '%%d-%%m-%%Y') AS purchase_date,
            u.full_name AS responsible_person,
            t.status,
            t.quantity,
            DATE_FORMAT(t.repair_date, '%%d-%%m-%%Y') AS repair_date,
            DATE_FORMAT(t.storage_date, '%%d-%%m-%%Y') AS storage_date,
            DATE_FORMAT(t.decommission_date, '%%d-%%m-%%Y') AS decommission_date
        FROM
            Technic t
            LEFT JOIN City c ON t.city_id = c.id
            LEFT JOIN Floor f ON t.floor_id = f.id
            LEFT JOIN Department d ON t.department_id = d.id
            LEFT JOIN Room r ON t.room_id = r.id
            LEFT JOIN EquipmentType et ON t.equipment_type_id = et.id
            LEFT JOIN Brand b ON t.brand_id = b.id
            LEFT JOIN Model m ON t.model_id = m.id
            LEFT JOIN User u ON t.responsible_person_id = u.id
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        return jsonify(rows)
    except mysql.connector.Error as err:
        print(f"Error fetching data: {err}")
        return jsonify({"success": False, "error": str(err)}), 500

@itinvent_bp.route('/api/<table>', methods=['GET'])
@login_required
def get_table_data(table):
    table_map = {
        'city': 'City',
        'floor': 'Floor',
        'department': 'Department',
        'room': 'Room',
        'equipment_type': 'EquipmentType',
        'brand': 'Brand',
        'model': 'Model'
    }

    if table not in table_map:
        return jsonify({"success": False, "message": "Invalid table name"}), 400

    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM {table_map[table]}")
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        return jsonify(rows)
    except mysql.connector.Error as err:
        print(f"Error fetching data from {table_map[table]}: {err}")
        return jsonify({"success": False, "error": str(err)}), 500

@itinvent_bp.route('/api/edit_<table>/<int:id>', methods=['PUT'])
@login_required
def edit_table_data(table, id):
    table_map = {
        'city': 'City',
        'floor': 'Floor',
        'department': 'Department',
        'room': 'Room',
        'equipment_type': 'EquipmentType',
        'brand': 'Brand',
        'model': 'Model'
    }

    if table not in table_map:
        return jsonify({"success": False, "message": "Invalid table name"}), 400

    data = request.json
    value = data.get('value')

    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        if table in ['equipment_type', 'brand', 'model']:
            cursor.execute(f"UPDATE {table_map[table]} SET name = %s WHERE id = %s", (value, id))
        else:
            cursor.execute(f"UPDATE {table_map[table]} SET name = %s WHERE id = %s", (value, id))
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({"success": True})
    except mysql.connector.Error as err:
        print(f"Error updating data in {table_map[table]}: {err}")
        return jsonify({"success": False, "error": str(err)}), 500

@itinvent_bp.route('/api/delete_<table>/<int:id>', methods=['DELETE'])
@login_required
def delete_table_data(table, id):
    table_map = {
        'city': 'City',
        'floor': 'Floor',
        'department': 'Department',
        'room': 'Room',
        'equipment_type': 'EquipmentType',
        'brand': 'Brand',
        'model': 'Model'
    }

    if table not in table_map:
        return jsonify({"success": False, "message": "Invalid table name"}), 400

    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        cursor.execute(f"DELETE FROM {table_map[table]} WHERE id = %s", (id,))
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({"success": True})
    except mysql.connector.Error as err:
        print(f"Error deleting data from {table_map[table]}: {err}")
        return jsonify({"success": False, "error": str(err)}), 500

@itinvent_bp.route('/api/add_city', methods=['POST'])
def add_city():
    try:
        data = request.get_json()
        city = data['value']
        connection = create_db_connection()
        cursor = connection.cursor()
        query = "INSERT INTO City (name) VALUES (%s)"
        cursor.execute(query, (city,))
        connection.commit()
        cursor.close()
        connection.close()
        print(f"Adding city: {city}")
        return jsonify({"success": True})
    except mysql.connector.Error as err:
        print(f"Error adding city: {err}")
        return jsonify({"success": False}), 500

@itinvent_bp.route('/api/cities', methods=['GET'])
@login_required
def get_cities():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM City")
    cities = cursor.fetchall()
    cursor.close()
    connection.close()
    return jsonify(cities)


@itinvent_bp.route('/api/add_floor', methods=['POST'])
def add_floor():
    data = request.json
    city_id = data.get('city_id')
    floor = data.get('value')
    print("Adding floor:", floor)
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO Floor (city_id, floor) VALUES (%s, %s)", (city_id, floor))
        connection.commit()
        cursor.close()
        connection.close()
        print("Floor added successfully")
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        print("Error adding floor:", err)
        return jsonify({'success': False, 'message': str(err)})

@itinvent_bp.route('/api/floors', methods=['GET'])
@login_required
def get_floors():
    city_id = request.args.get('city_id')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    if city_id:
        cursor.execute("SELECT * FROM Floor WHERE city_id = %s", (city_id,))
    else:
        cursor.execute("SELECT * FROM Floor")
    floors = cursor.fetchall()
    cursor.close()
    connection.close()
    return jsonify(floors)


@itinvent_bp.route('/api/add_department', methods=['POST'])
def add_department():
    data = request.json
    floor_id = data.get('floor_id')
    department = data.get('value')
    print("Adding department:", department)
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO Department (floor_id, name) VALUES (%s, %s)", (floor_id, department))
        connection.commit()
        cursor.close()
        connection.close()
        print("Department added successfully")
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        print("Error adding department:", err)
        return jsonify({'success': False, 'message': str(err)})

@itinvent_bp.route('/api/add_room', methods=['POST'])
def add_room():
    data = request.json
    department_id = data.get('department_id')
    room = data.get('value')
    print("Adding room:", room)
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO Room (department_id, room) VALUES (%s, %s)", (department_id, room))
        connection.commit()
        cursor.close()
        connection.close()
        print("Room added successfully")
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        print("Error adding room:", err)
        return jsonify({'success': False, 'message': str(err)})

@itinvent_bp.route('/api/rooms', methods=['GET'])
@login_required
def get_rooms():
    department_id = request.args.get('department_id')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    if department_id:
        cursor.execute("SELECT * FROM Room WHERE department_id = %s", (department_id,))
    else:
        cursor.execute("SELECT * FROM Room")
    rooms = cursor.fetchall()
    cursor.close()
    connection.close()
    return jsonify(rooms)

@itinvent_bp.route('/api/delete_brand/<int:id>', methods=['DELETE'])
def delete_brand(id):
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Проверка на наличие связанных моделей
        cursor.execute("SELECT id, model FROM Model WHERE brand_id = %s", (id,))
        models = cursor.fetchall()
        
        if models:
            # Если есть связанные модели, вернуть список
            return jsonify({"success": False, "message": "Сначала удалите связанные модели", "models": models}), 400
        
        # Если моделей нет, выполнить удаление
        cursor.execute("DELETE FROM Brand WHERE id = %s", (id,))
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({"success": True})
    except mysql.connector.Error as err:
        print(f"Error deleting brand: {err}")
        return jsonify({"success": False, "error": str(err)}), 500

@itinvent_bp.route('/api/delete_models_by_brand/<int:brand_id>', methods=['DELETE'])
def delete_models_by_brand(brand_id):
    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM Model WHERE brand_id = %s", (brand_id,))
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({"success": True})
    except mysql.connector.Error as err:
        print(f"Error deleting models: {err}")
        return jsonify({"success": False, "error": str(err)}), 500

@itinvent_bp.route('/api/add_equipment_type', methods=['POST'])
def add_equipment_type():
    data = request.json
    equipment_type = data.get('value')
    print("Adding equipment type:", equipment_type)
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO EquipmentType (type) VALUES (%s)", (equipment_type,))
        connection.commit()
        cursor.close()
        connection.close()
        print("Equipment type added successfully")
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        print("Error adding equipment type:", err)
        return jsonify({'success': False, 'message': str(err)})

@itinvent_bp.route('/api/departments', methods=['GET'])
@login_required
def get_departments():
    floor_id = request.args.get('floor_id')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    if floor_id:
        cursor.execute("SELECT * FROM Department WHERE floor_id = %s", (floor_id,))
    else:
        cursor.execute("SELECT * FROM Department")
    departments = cursor.fetchall()
    cursor.close()
    connection.close()
    return jsonify(departments)


@itinvent_bp.route('/api/add_brand', methods=['POST'])
def add_brand():
    data = request.json
    equipment_type_id = data.get('type_id')
    brand = data.get('value')
    print("Adding brand:", brand)
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO Brand (equipment_type_id, brand) VALUES (%s, %s)", (equipment_type_id, brand))
        connection.commit()
        cursor.close()
        connection.close()
        print("Brand added successfully")
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        print("Error adding brand:", err)
        return jsonify({'success': False, 'message': str(err)})

@itinvent_bp.route('/api/add_model', methods=['POST'])
def add_model():
    data = request.json
    brand_id = data.get('brand_id')
    model = data.get('value')
    print("Adding model:", model)
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO Model (brand_id, model) VALUES (%s, %s)", (brand_id, model))
        connection.commit()
        cursor.close()
        connection.close()
        print("Model added successfully")
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        print("Error adding model:", err)
        return jsonify({'success': False, 'message': str(err)})

@itinvent_bp.route('/api/technic_types', methods=['GET'])
@login_required
def get_technic_types():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM EquipmentType")
    types = cursor.fetchall()
    cursor.close()
    connection.close()
    return jsonify(types)

@itinvent_bp.route('/api/brands', methods=['GET'])
@login_required
def get_brands():
    type_id = request.args.get('type_id')  # Получаем type_id из параметров запроса
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    if type_id:
        cursor.execute("SELECT * FROM Brand WHERE equipment_type_id = %s", (type_id,))
    else:
        cursor.execute("SELECT * FROM Brand")
    
    brands = cursor.fetchall()
    print(brands)  # Добавь этот принт для отладки
    cursor.close()
    connection.close()
    return jsonify(brands)

@itinvent_bp.route('/api/models', methods=['GET'])
@login_required
def get_models():
    brand_id = request.args.get('brand_id')  # Получаем brand_id из параметров запроса
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    if brand_id:
        cursor.execute("SELECT * FROM Model WHERE brand_id = %s", (brand_id,))
    else:
        cursor.execute("SELECT * FROM Model")
    
    models = cursor.fetchall()
    cursor.close()
    connection.close()
    return jsonify(models)

@itinvent_bp.route('/api/users', methods=['GET'])
@login_required
def get_users():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, full_name FROM User")
    users = cursor.fetchall()
    cursor.close()
    connection.close()
    return jsonify(users)

@itinvent_bp.route('/api/it_tech', methods=['GET'])
@login_required
def api_it_tech():
    status = request.args.get('status', 'active')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    base_query = """
        SELECT t.id, et.type AS equipment_type, b.brand, m.model, t.serial_number, 
               t.inventory_number, t.purchase_date, t.repair_date, t.storage_date,
               t.decommission_date, u.full_name AS responsible_person, t.status, 
               t.quantity, c.name AS city, f.floor, d.name AS department, r.room
        FROM Technic t
        JOIN EquipmentType et ON t.equipment_type_id = et.id
        JOIN Brand b ON t.brand_id = b.id
        LEFT JOIN Model m ON t.model_id = m.id
        LEFT JOIN User u ON t.responsible_person_id = u.id
        LEFT JOIN Location l ON t.location_id = l.id
        LEFT JOIN City c ON l.city_id = c.id
        LEFT JOIN Floor f ON l.floor_id = f.id
        LEFT JOIN Department d ON l.department_id = d.id
        LEFT JOIN Room r ON l.room_id = r.id
    """

    try:
        if status == 'active':
            cursor.execute(base_query + " WHERE t.status = 'Активный' AND t.quantity > 0")
        elif status == 'in_repair':
            cursor.execute(base_query + " WHERE t.status = 'В ремонте' AND t.quantity > 0")
        elif status == 'storage':
            cursor.execute(base_query + " WHERE t.status = 'Склад' AND t.quantity > 0")
        elif status == 'decommissioned':
            cursor.execute(base_query + " WHERE t.status = 'Списано' AND t.quantity > 0")
        elif status == 'cartridges':
            cursor.execute(base_query + " WHERE et.type = 'Картридж' AND t.quantity > 0")
        elif status == 'archive':
            cursor.execute(base_query + " WHERE t.status = 'Архив' AND t.quantity > 0")
        else:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400

        technic_data = cursor.fetchall()

        # Форматирование дат
        for item in technic_data:
            item['purchase_date'] = format_date(item['purchase_date'])
            item['repair_date'] = format_date(item['repair_date'])
            item['storage_date'] = format_date(item['storage_date'])
            item['decommission_date'] = format_date(item['decommission_date'])
            
            # Отладочные выводы
            print("Formatted dates:", item['purchase_date'], item['repair_date'], item['storage_date'], item['decommission_date'])

        return jsonify(technic_data)
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        connection.close()

@itinvent_bp.route('/it_tech_add', methods=['GET'])
@login_required
def it_tech_add():
    return render_template('it_tech_add.html')

@itinvent_bp.route('/it_tech_edit')
def it_tech_edit():
    return render_template('it_tech_edit.html')

@itinvent_bp.route('/api/update_technic', methods=['POST'])
@login_required
def update_technic():
    data = request.json
    connection = create_db_connection()
    cursor = connection.cursor()

    try:
        # Получаем текущее количество техники с указанным ID
        cursor.execute("SELECT quantity FROM Technic WHERE id = %s", (data['id'],))
        current_quantity = cursor.fetchone()[0]

        move_quantity = data['quantity']

        if move_quantity > current_quantity:
            return jsonify({'success': False, 'message': 'Невозможно переместить больше, чем имеется'})

        if data['status'] in ['В ремонте', 'Склад', 'Списано']:
            # Обновляем количество в текущем статусе
            cursor.execute("""
                UPDATE Technic
                SET quantity = quantity - %s
                WHERE id = %s
            """, (move_quantity, data['id']))

            # Проверяем, существует ли уже запись с указанным статусом и такими же характеристиками
            cursor.execute("""
                SELECT id, quantity FROM Technic
                WHERE equipment_type_id = %s AND brand_id = %s AND model_id = %s AND status = %s
            """, (data['type_id'], data['brand_id'], data['model_id'], data['status']))

            existing_record = cursor.fetchone()

            if existing_record:
                # Обновляем количество в существующей записи
                cursor.execute("""
                    UPDATE Technic
                    SET quantity = quantity + %s
                    WHERE id = %s
                """, (move_quantity, existing_record[0]))
            else:
                # Добавляем новую запись с перемещением
                cursor.execute("""
                    INSERT INTO Technic (location_id, equipment_type_id, brand_id, model_id, serial_number, inventory_number, purchase_date, responsible_person_id, status, quantity, repair_date, storage_date, decommission_date)
                    SELECT location_id, equipment_type_id, brand_id, model_id, serial_number, inventory_number, purchase_date, responsible_person_id, %s, %s, %s, %s, %s
                    FROM Technic
                    WHERE id = %s
                """, (data['status'], move_quantity, data.get('repair_date'), data.get('storage_date'), data.get('decommission_date'), data['id']))

        else:
            # Обновляем информацию для других статусов
            cursor.execute("""
                UPDATE Technic
                SET responsible_person_id = %s, status = %s, quantity = %s,
                    repair_date = %s, storage_date = %s, decommission_date = %s
                WHERE id = %s
            """, (
                data['responsible_person_id'], data['status'], data['quantity'],
                data.get('repair_date'), data.get('storage_date'), data.get('decommission_date'), data['id']
            ))

        connection.commit()
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()

@itinvent_bp.route('/api/add_technic', methods=['POST'])
@login_required
def add_technic():
    data = request.json
    connection = create_db_connection()
    cursor = connection.cursor()

    try:
        # Добавить новую запись в таблицу Location
        location_query = """
            INSERT INTO Location (city_id, floor_id, department_id, room_id)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(location_query, (
            data.get('city_id'), 
            data.get('floor_id'), 
            data.get('department_id'), 
            data.get('room_id')
        ))
        location_id = cursor.lastrowid

        # Добавить новую запись в таблицу Technic с ссылкой на Location
        technic_query = """
            INSERT INTO Technic (location_id, equipment_type_id, brand_id, model_id, serial_number, inventory_number, purchase_date, responsible_person_id, status, quantity)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(technic_query, (
            location_id,
            data.get('type_id'), 
            data.get('brand_id'), 
            data.get('model_id'), 
            data.get('serial_number'), 
            data.get('inventory_number'), 
            data.get('purchase_date'), 
            data.get('responsible_person_id'), 
            data.get('status'), 
            data.get('quantity')
        ))
        connection.commit()
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()

@itinvent_bp.route('/api/filter_technic', methods=['POST'])
@login_required
def filter_technic():
    filters = request.json
    print("Получены фильтры:", filters)  # Отладочный вывод для фильтров

    query = """
        SELECT t.id, et.type AS equipment_type, b.brand, m.model, t.serial_number, 
               t.inventory_number, t.purchase_date, t.repair_date, t.storage_date,
               t.decommission_date, u.full_name AS responsible_person, t.status, 
               t.quantity, c.name AS city, f.floor, d.name AS department, r.room
        FROM Technic t
        JOIN EquipmentType et ON t.equipment_type_id = et.id
        JOIN Brand b ON t.brand_id = b.id
        LEFT JOIN Model m ON t.model_id = m.id
        LEFT JOIN User u ON t.responsible_person_id = u.id
        LEFT JOIN Location l ON t.location_id = l.id
        LEFT JOIN City c ON l.city_id = c.id
        LEFT JOIN Floor f ON l.floor_id = f.id
        LEFT JOIN Department d ON l.department_id = d.id
        LEFT JOIN Room r ON l.room_id = r.id
        WHERE 1=1
    """

    params = []
    if 'city' in filters:
        query += " AND c.name LIKE %s"
        params.append(f"%{filters['city']}%")
    if 'floor' in filters:
        query += " AND f.floor LIKE %s"
        params.append(f"%{filters['floor']}%")
    if 'department' in filters:
        query += " AND d.name LIKE %s"
        params.append(f"%{filters['department']}%")
    if 'room' in filters:
        query += " AND r.room LIKE %s"
        params.append(f"%{filters['room']}%")
    if 'equipment_type' in filters:
        query += " AND et.type LIKE %s"
        params.append(f"%{filters['equipment_type']}%")
    if 'brand' in filters:
        query += " AND b.brand LIKE %s"
        params.append(f"%{filters['brand']}%")
    if 'model' in filters:
        query += " AND m.model LIKE %s"
        params.append(f"%{filters['model']}%")
    if 'responsible_person' in filters:
        query += " AND u.full_name LIKE %s"
        params.append(f"%{filters['responsible_person']}%")
    if 'status' in filters:
        query += " AND t.status LIKE %s"
        params.append(f"%{filters['status']}%")

    print("SQL-запрос:", query)  # Отладочный вывод для SQL-запроса
    print("Параметры:", params)  # Отладочный вывод для параметров запроса

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute(query, tuple(params))
        filtered_data = cursor.fetchall()
        print("Полученные данные:", filtered_data)  # Отладочный вывод для полученных данных
    finally:
        cursor.close()
        connection.close()

    return jsonify(filtered_data)
