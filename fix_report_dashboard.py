#!/usr/bin/env python3

fixed_code = '''@callcenter_bp.route('/report_dashboard')
@login_required
def report_dashboard():
    try:
        report_type = request.args.get('type', 'daily')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
    
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Получаем данные согласно типу отчета
        if report_type == 'daily':
            report_title = 'Отчет за сегодня'
            query = """
                SELECT 
                    s.id, 
                    s.date, 
                    s.time, 
                    u.full_name AS broker_name,
                    s.department_id, 
                    c.category_name AS floor_name,
                    o.object_name, 
                    src.source_name, 
                    s.client_id, 
                    s.operator
                FROM ScoringKC s
                JOIN User u ON s.broker_id = u.id
                JOIN CallCategories c ON s.floor_id = c.id
                JOIN ObjectKC o ON s.object_id = o.id
                JOIN SourceKC src ON s.source_id = src.id
                WHERE s.date = CURDATE()
                ORDER BY s.time DESC
            """
            params = ()
        
        elif report_type == 'monthly':
            report_title = 'Отчет за текущий месяц'
            query = """
                SELECT 
                    s.id, 
                    s.date, 
                    s.time, 
                    u.full_name AS broker_name,
                    s.department_id, 
                    c.category_name AS floor_name,
                    o.object_name, 
                    src.source_name, 
                    s.client_id, 
                    s.operator
                FROM ScoringKC s
                JOIN User u ON s.broker_id = u.id
                JOIN CallCategories c ON s.floor_id = c.id
                JOIN ObjectKC o ON s.object_id = o.id
                JOIN SourceKC src ON s.source_id = src.id
                WHERE MONTH(s.date) = MONTH(CURDATE()) 
                  AND YEAR(s.date) = YEAR(CURDATE())
                ORDER BY s.date DESC, s.time DESC
            """
            params = ()
        
        elif report_type == 'yearly':
            report_title = 'Отчет за текущий год'
            query = """
                SELECT 
                    s.id, 
                    s.date, 
                    s.time, 
                    u.full_name AS broker_name,
                    s.department_id, 
                    c.category_name AS floor_name,
                    o.object_name, 
                    src.source_name, 
                    s.client_id, 
                    s.operator
                FROM ScoringKC s
                JOIN User u ON s.broker_id = u.id
                JOIN CallCategories c ON s.floor_id = c.id
                JOIN ObjectKC o ON s.object_id = o.id
                JOIN SourceKC src ON s.source_id = src.id
                WHERE YEAR(s.date) = YEAR(CURDATE())
                ORDER BY s.date DESC, s.time DESC
            """
            params = ()
        
        elif report_type == 'custom' and start_date and end_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            report_title = f'Отчет с {start_date} по {end_date}'
            query = """
                SELECT 
                    s.id, 
                    s.date, 
                    s.time, 
                    u.full_name AS broker_name,
                    s.department_id, 
                    c.category_name AS floor_name,
                    o.object_name, 
                    src.source_name, 
                    s.client_id, 
                    s.operator
                FROM ScoringKC s
                JOIN User u ON s.broker_id = u.id
                JOIN CallCategories c ON s.floor_id = c.id
                JOIN ObjectKC o ON s.object_id = o.id
                JOIN SourceKC src ON s.source_id = src.id
                WHERE s.date BETWEEN %s AND %s
                ORDER BY s.date DESC, s.time DESC
            """
            params = (start_date_obj, end_date_obj)
        
        else:
            report_title = 'Отчет за сегодня'
            query = """
                SELECT 
                    s.id, 
                    s.date, 
                    s.time, 
                    u.full_name AS broker_name,
                    s.department_id, 
                    c.category_name AS floor_name,
                    o.object_name, 
                    src.source_name, 
                    s.client_id, 
                    s.operator
                FROM ScoringKC s
                JOIN User u ON s.broker_id = u.id
                JOIN CallCategories c ON s.floor_id = c.id
                JOIN ObjectKC o ON s.object_id = o.id
                JOIN SourceKC src ON s.source_id = src.id
                WHERE s.date = CURDATE()
                ORDER BY s.time DESC
            """
            params = ()
        
        cursor.execute(query, params)
        entries = cursor.fetchall()
        
        # Получаем общие данные (категории, объекты, источники)
        common_data = get_common_data()
    
        if report_type == "custom":
            return render_template(
                'report_dashboard.html',
                entries=entries,
                report_title=report_title,
                report_type=report_type,
                start_date=start_date,
                end_date=end_date,
                **common_data
            )
        else:
            return render_template(
                'report_dashboard.html',
                entries=entries,
                report_title=report_title,
                report_type=report_type,
                **common_data
            )
        
    except Exception as e:
        logger.error(f"Ошибка при формировании отчета: {str(e)}")
        logger.error(traceback.format_exc())
        flash('Произошла ошибка при формировании отчета', 'error')
        return render_template(
            'report_dashboard.html',
            entries=[],
            report_title='Ошибка',
            report_type='daily'
        )
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()'''

# Читаем файл
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'r') as f:
    content = f.read()

# Находим начало и конец функции report_dashboard
start_pos = content.find('@callcenter_bp.route(\'/report_dashboard\')')
if start_pos == -1:
    print("Не удалось найти функцию report_dashboard")
    exit(1)

# Находим следующую функцию после report_dashboard
next_function_pos = content.find('@callcenter_bp.route(\'/api/leads/yearly\'', start_pos)
if next_function_pos == -1:
    print("Не удалось найти конец функции report_dashboard")
    exit(1)

# Заменяем функцию
new_content = content[:start_pos] + fixed_code + content[next_function_pos:]

# Сохраняем изменения
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'w') as f:
    f.write(new_content)

print("Функция report_dashboard успешно заменена") 