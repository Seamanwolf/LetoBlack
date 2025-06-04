from app.db.role_dao import RoleDAO
from flask import current_app

class PermissionService:
    def __init__(self):
        db_config = current_app.config.get('DB_CONFIG', {})
        self.role_dao = RoleDAO(db_config)

    def get_all_modules(self):
        return self.role_dao.get_all_modules()

    def get_role_permissions(self, role_id):
        return self.role_dao.get_role_permissions(role_id)

    def clear_role_permissions(self, role_id):
        return self.role_dao.clear_role_permissions(role_id)

    def set_role_permissions(self, role_id, module_id, can_view, can_create, can_edit, can_delete):
        return self.role_dao.set_role_permissions(role_id, module_id, can_view, can_create, can_edit, can_delete) 