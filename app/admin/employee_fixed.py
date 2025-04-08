@admin_bp.route('/api/get_employee', methods=['GET'])
@admin_bp.route('/admin/api/get_employee', methods=['GET'])
@login_required
def get_employee():
    """Получение данных сотрудника по ID"""
    try:
        if current_user.role != 'admin' and current_user.role != 'leader':
            return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'}), 403
        
        employee_id = request.args.get('id')
        
        if not employee_id:
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400
            
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Получаем данные сотрудника с названием отдела
            cursor.execute("""
                SELECT u.*, d.name as department_name 
                FROM User u
                LEFT JOIN Department d ON u.department_id = d.id 
                WHERE u.id = %s
            """, (employee_id,))
            
            employee = cursor.fetchone()
            if not employee:
                return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404

            # Форматируем даты в строки для JSON
            for date_field in ['hire_date', 'termination_date', 'birth_date', 'fire_date', 'last_active']:
                if employee.get(date_field) and isinstance(employee[date_field], (datetime, date)):
                    employee[date_field] = employee[date_field].strftime('%Y-%m-%d')

            # Для обратной совместимости
            if not employee.get('department'):
                employee['department'] = employee.get('department_name', '')

            # Возвращаем данные в едином формате
            return jsonify({
                'success': True,
                'data': employee
            })
        
        except Exception as e:
            logger.error(f"Ошибка при получении данных сотрудника: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Ошибка при получении данных: {str(e)}'
            }), 500
        
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()

    except Exception as e:
        logger.error(f"Критическая ошибка в методе get_employee: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Критическая ошибка: {str(e)}'
        }), 500 