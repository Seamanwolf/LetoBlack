#!/usr/bin/env python3

fixed_add_category = '''@callcenter_bp.route('/add_category', methods=['POST'])
@login_required
def add_category():
    try:
        category_name = request.form['category_name']
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Получаем максимальный порядок
        cursor.execute("SELECT MAX(`order`) as max_order FROM CallCategories")
        result = cursor.fetchone()
        next_order = 0 if not result or not result[0] else result[0] + 1
        
        # Добавляем новую категорию
        cursor.execute("""
            INSERT INTO CallCategories (category_name, `order`, archived) 
            VALUES (%s, %s, 0)
        """, (category_name, next_order))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        flash('Категория успешно добавлена!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при добавлении категории: {str(e)}")
        flash(f"Ошибка при добавлении категории: {str(e)}", 'error')
    
    return redirect(url_for('callcenter.manage_objects_sources'))'''

fixed_add_object = '''@callcenter_bp.route('/add_object', methods=['POST'])
@login_required
def add_object():
    try:
        object_name = request.form['object_name']
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Получаем максимальный порядок
        cursor.execute("SELECT MAX(`order`) as max_order FROM ObjectKC")
        result = cursor.fetchone()
        next_order = 0 if not result or not result[0] else result[0] + 1
        
        # Добавляем новый объект
        cursor.execute("""
            INSERT INTO ObjectKC (object_name, `order`, archived) 
            VALUES (%s, %s, 0)
        """, (object_name, next_order))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        flash('Объект успешно добавлен!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при добавлении объекта: {str(e)}")
        flash(f"Ошибка при добавлении объекта: {str(e)}", 'error')
    
    return redirect(url_for('callcenter.manage_objects_sources'))'''

fixed_add_source = '''@callcenter_bp.route('/add_source', methods=['POST'])
@login_required
def add_source():
    try:
        source_name = request.form['source_name']
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Получаем максимальный порядок
        cursor.execute("SELECT MAX(`order`) as max_order FROM SourceKC")
        result = cursor.fetchone()
        next_order = 0 if not result or not result[0] else result[0] + 1
        
        # Добавляем новый источник
        cursor.execute("""
            INSERT INTO SourceKC (source_name, `order`, archived) 
            VALUES (%s, %s, 0)
        """, (source_name, next_order))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        flash('Источник успешно добавлен!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при добавлении источника: {str(e)}")
        flash(f"Ошибка при добавлении источника: {str(e)}", 'error')
    
    return redirect(url_for('callcenter.manage_objects_sources'))'''

fixed_archive_object = '''@callcenter_bp.route('/archive_object/<int:object_id>', methods=['POST'])
@login_required
def archive_object(object_id):
    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Проверяем, существует ли объект
        cursor.execute("SELECT id FROM ObjectKC WHERE id = %s", (object_id,))
        if not cursor.fetchone():
            flash('Объект не найден', 'error')
            return redirect(url_for('callcenter.manage_objects_sources'))
        
        # Архивируем объект
        cursor.execute("""
            UPDATE ObjectKC
            SET archived = 1
            WHERE id = %s
        """, (object_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        flash('Объект успешно архивирован!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при архивировании объекта: {str(e)}")
        flash(f"Ошибка: {str(e)}", 'error')
    
    return redirect(url_for('callcenter.manage_objects_sources'))'''

fixed_archive_source = '''@callcenter_bp.route('/archive_source/<int:source_id>', methods=['POST'])
@login_required
def archive_source(source_id):
    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Проверяем, существует ли источник
        cursor.execute("SELECT id FROM SourceKC WHERE id = %s", (source_id,))
        if not cursor.fetchone():
            flash('Источник не найден', 'error')
            return redirect(url_for('callcenter.manage_objects_sources'))
        
        # Архивируем источник
        cursor.execute("""
            UPDATE SourceKC
            SET archived = 1
            WHERE id = %s
        """, (source_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        flash('Источник успешно архивирован!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при архивировании источника: {str(e)}")
        flash(f"Ошибка: {str(e)}", 'error')
    
    return redirect(url_for('callcenter.manage_objects_sources'))'''

# Читаем файл
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'r') as f:
    content = f.read()

# Исправляем функцию add_category
start_pos = content.find('@callcenter_bp.route(\'/add_category\'')
next_function_pos = content.find('@callcenter_bp.route(\'/add_object\'', start_pos)
content = content[:start_pos] + fixed_add_category + content[next_function_pos:]

# Исправляем функцию add_object
start_pos = content.find('@callcenter_bp.route(\'/add_object\'')
next_function_pos = content.find('@callcenter_bp.route(\'/archive_object\'', start_pos)
content = content[:start_pos] + fixed_add_object + content[next_function_pos:]

# Исправляем функцию archive_object
start_pos = content.find('@callcenter_bp.route(\'/archive_object\'')
next_function_pos = content.find('@callcenter_bp.route(\'/archive_category\'', start_pos)
content = content[:start_pos] + fixed_archive_object + content[next_function_pos:]

# Исправляем функцию archive_source
start_pos = content.find('@callcenter_bp.route(\'/archive_source\'')
next_function_pos = content.find('@callcenter_bp.route(\'/add_source\'', start_pos)
content = content[:start_pos] + fixed_archive_source + content[next_function_pos:]

# Исправляем функцию add_source
start_pos = content.find('@callcenter_bp.route(\'/add_source\'')
next_function_pos = content.find('@callcenter_bp.route(\'/edit_object\'', start_pos)
content = content[:start_pos] + fixed_add_source + content[next_function_pos:]

# Сохраняем изменения
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'w') as f:
    f.write(content)

print("Функции успешно исправлены") 