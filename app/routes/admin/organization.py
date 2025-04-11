from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required
from app.models.position import Position
from app.models.location import Location
from app.models.department import Department
from app.models.employee import Employee
from app import db
from app.decorators import admin_required
from app.models.city import City
from app.models.floor import Floor
from app.models.room import Room

bp = Blueprint('admin_organization', __name__)

# Маршрут для отображения страницы настроек организации
@bp.route('/settings/organization', methods=['GET'])
@login_required
@admin_required
def index():
    positions = Position.get_all()
    locations = Location.get_all()
    departments = Department.get_all()
    employees = Employee.get_all()
    
    return render_template('admin/settings/organization.html', 
                          positions=positions, 
                          locations=locations, 
                          departments=departments, 
                          employees=employees,
                          active_tab='organization')

# Маршруты для должностей
@bp.route('/settings/positions', methods=['GET'])
@login_required
@admin_required
def get_positions():
    positions = Position.get_all()
    return jsonify([p.to_dict() for p in positions])

@bp.route('/settings/positions/<int:id>', methods=['GET'])
@login_required
@admin_required
def get_position(id):
    position = Position.get_by_id(id)
    if position:
        return jsonify(position.to_dict())
    return jsonify({'error': 'Должность не найдена'}), 404

@bp.route('/settings/positions', methods=['POST'])
@login_required
@admin_required
def create_position():
    data = request.form
    position = Position(
        name=data['name'],
        description=data.get('description', '')
    )
    position.save()
    return jsonify({'success': True})

@bp.route('/settings/positions/<int:id>', methods=['PUT'])
@login_required
@admin_required
def update_position(id):
    position = Position.get_by_id(id)
    if position:
        data = request.form
        position.name = data['name']
        position.description = data.get('description', '')
        position.save()
        return jsonify({'success': True})
    return jsonify({'error': 'Должность не найдена'}), 404

@bp.route('/settings/positions/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_position(id):
    position = Position.get_by_id(id)
    if position:
        position.delete()
        return jsonify({'success': True})
    return jsonify({'error': 'Должность не найдена'}), 404

# Маршруты для локаций
@bp.route('/settings/locations', methods=['GET'])
@login_required
@admin_required
def get_locations():
    locations = Location.get_all()
    return jsonify([l.to_dict() for l in locations])

@bp.route('/settings/locations/<int:id>', methods=['GET'])
@login_required
@admin_required
def get_location(id):
    location = Location.get_by_id(id)
    if location:
        return jsonify(location.to_dict())
    return jsonify({'error': 'Локация не найдена'}), 404

@bp.route('/settings/locations', methods=['POST'])
@login_required
@admin_required
def create_location():
    data = request.get_json()
    location = Location(
        name=data.get('name'),
        address=data.get('address')
    )
    location.save()
    return jsonify({'success': True, 'message': 'Локация успешно создана'})

@bp.route('/settings/locations/<int:id>', methods=['PUT'])
@login_required
@admin_required
def update_location(id):
    location = Location.get_by_id(id)
    if location:
        data = request.get_json()
        location.name = data.get('name')
        location.address = data.get('address')
        location.save()
        return jsonify({'success': True, 'message': 'Локация успешно обновлена'})
    return jsonify({'error': 'Локация не найдена'}), 404

@bp.route('/settings/locations/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_location(id):
    location = Location.get_by_id(id)
    if location:
        location.delete()
        return jsonify({'success': True, 'message': 'Локация успешно удалена'})
    return jsonify({'error': 'Локация не найдена'}), 404

# Маршруты для отделов
@bp.route('/settings/departments', methods=['GET'])
@login_required
@admin_required
def get_departments():
    departments = Department.get_all()
    return jsonify([d.to_dict() for d in departments])

@bp.route('/settings/departments/<int:id>', methods=['GET'])
@login_required
@admin_required
def get_department(id):
    department = Department.get_by_id(id)
    if department:
        return jsonify(department.to_dict())
    return jsonify({'error': 'Отдел не найден'}), 404

@bp.route('/settings/departments', methods=['POST'])
@login_required
@admin_required
def create_department():
    data = request.get_json()
    department = Department(
        name=data['name'],
        location_id=data['location_id'],
        leader_id=data.get('leader_id')
    )
    department.save()
    return jsonify({'success': True})

@bp.route('/settings/departments/<int:id>', methods=['PUT'])
@login_required
@admin_required
def update_department(id):
    department = Department.get_by_id(id)
    if department:
        data = request.get_json()
        department.name = data['name']
        department.location_id = data['location_id']
        leader_id = data.get('leader_id')
        if leader_id and leader_id != 'None':
            department.leader_id = int(leader_id)
        else:
            department.leader_id = None
        department.save()
        return jsonify({'success': True})
    return jsonify({'error': 'Отдел не найден'}), 404

@bp.route('/settings/departments/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_department(id):
    department = Department.get_by_id(id)
    if department:
        department.delete()
        return jsonify({'success': True})
    return jsonify({'error': 'Отдел не найден'}), 404

@bp.route('/settings/employees', methods=['GET'])
@login_required
@admin_required
def get_employees():
    employees = Employee.get_all()
    return jsonify([employee.to_dict() for employee in employees]) 