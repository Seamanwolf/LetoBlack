#!/usr/bin/env python3

fixed_code = '''def get_common_data():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Получаем категории
        cursor.execute("SELECT id, category_name FROM CallCategories WHERE archived = 0 ORDER BY `order`")
        categories = cursor.fetchall()
        
        # Получаем объекты
        cursor.execute("SELECT id, object_name FROM ObjectKC WHERE archived = 0 ORDER BY `order`")
        objects = cursor.fetchall()
        
        # Получаем источники
        cursor.execute("SELECT id, source_name FROM SourceKC WHERE archived = 0 ORDER BY `order`")
        sources = cursor.fetchall()
        
        # Получаем операторов
        cursor.execute("""
            SELECT u.id, u.full_name, c.status 
            FROM User u
            LEFT JOIN CallCenterOperators c ON u.id = c.user_id
            WHERE u.role = 'operator' AND u.active = 1
            ORDER BY u.full_name
        """)
        operators = cursor.fetchall()
        
        # Получаем брокеров
        cursor.execute("""
            SELECT id, full_name 
            FROM User 
            WHERE role = 'broker' AND active = 1
            ORDER BY full_name
        """)
        brokers = cursor.fetchall()
        
        # Получаем отделы
        cursor.execute("SELECT id, name FROM Department ORDER BY name")
        departments = cursor.fetchall()
        
        return {
            'categories': categories,
            'objects': objects,
            'sources': sources,
            'operators': operators,
            'brokers': brokers,
            'departments': departments
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении общих данных: {str(e)}")
        return {
            'categories': [],
            'objects': [],
            'sources': [],
            'operators': [],
            'brokers': [],
            'departments': []
        }
        
    finally:
        cursor.close()
        connection.close()'''

# Читаем файл
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'r') as f:
    content = f.read()

# Находим начало и конец функции get_common_data
start_pos = content.find('def get_common_data():')
if start_pos == -1:
    print("Не удалось найти функцию get_common_data")
    exit(1)

# Находим следующую функцию после get_common_data
next_function_pos = content.find('@callcenter_bp.route(\'/report_by_day\')', start_pos)
if next_function_pos == -1:
    print("Не удалось найти конец функции get_common_data")
    exit(1)

# Заменяем функцию
new_content = content[:start_pos] + fixed_code + content[next_function_pos:]

# Сохраняем изменения
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'w') as f:
    f.write(new_content)

print("Функция get_common_data успешно заменена") 