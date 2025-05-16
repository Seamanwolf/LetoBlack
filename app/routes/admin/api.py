@admin_bp.route('/api/add_number', methods=['POST'])
def add_number():
    """Добавить новый номер телефона."""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number', '').strip()
        department = data.get('department')
        additional_numbers = data.get('additional_numbers', [])
        
        # Проверка на обязательные поля
        if not phone_number:
            return jsonify({'success': False, 'message': 'Номер телефона не может быть пустым'})
        if not department:
            return jsonify({'success': False, 'message': 'Необходимо выбрать отдел'})
        
        # Проверяем, что номер уникален
        existing_number = db.session.query(PhoneNumber).filter_by(phone_number=phone_number).first()
        if existing_number:
            return jsonify({'success': False, 'message': 'Номер телефона уже существует в базе'})
        
        # Проверяем дополнительные номера на уникальность
        for add_number in additional_numbers:
            existing = db.session.query(PhoneNumber).filter_by(phone_number=add_number).first()
            if existing:
                return jsonify({'success': False, 'message': f'Дополнительный номер {add_number} уже существует в базе'})
            
            # Также проверяем в таблице дополнительных номеров
            existing_additional = db.session.query(AdditionalPhoneNumber).filter_by(phone_number=add_number).first()
            if existing_additional:
                return jsonify({'success': False, 'message': f'Дополнительный номер {add_number} уже существует в базе'})
        
        # Создаем запись в базе
        new_number = PhoneNumber(
            phone_number=phone_number,
            department=department,
            whatsapp=False,
            telegram=False,
            blocked=False,
            prohibit_issuance=False
        )
        
        db.session.add(new_number)
        db.session.flush()  # Чтобы получить ID созданного номера
        
        # Добавляем дополнительные номера
        for add_number in additional_numbers:
            new_additional = AdditionalPhoneNumber(
                phone_number=add_number,
                main_number_id=new_number.id
            )
            db.session.add(new_additional)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Номер успешно добавлен'})
    
    except Exception as e:
        db.session.rollback()
        print(f"Error adding number: {str(e)}")
        return jsonify({'success': False, 'message': 'Произошла ошибка при добавлении номера'}) 