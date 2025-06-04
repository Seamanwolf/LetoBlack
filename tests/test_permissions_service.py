import pytest
from unittest.mock import MagicMock, patch
from app.services.permissions_service import PermissionService

@patch('app.services.permissions_service.RoleDAO')
def test_get_all_modules(mock_role_dao):
    mock_instance = mock_role_dao.return_value
    mock_instance.get_all_modules.return_value = [{'id': 1, 'name': 'mod1'}]
    service = PermissionService()
    result = service.get_all_modules()
    assert result == [{'id': 1, 'name': 'mod1'}]
    mock_instance.get_all_modules.assert_called_once()

@patch('app.services.permissions_service.RoleDAO')
def test_get_role_permissions(mock_role_dao):
    mock_instance = mock_role_dao.return_value
    mock_instance.get_role_permissions.return_value = ['perm1', 'perm2']
    service = PermissionService()
    result = service.get_role_permissions(5)
    assert result == ['perm1', 'perm2']
    mock_instance.get_role_permissions.assert_called_once_with(5)

@patch('app.services.permissions_service.RoleDAO')
def test_clear_role_permissions(mock_role_dao):
    mock_instance = mock_role_dao.return_value
    mock_instance.clear_role_permissions.return_value = True
    service = PermissionService()
    result = service.clear_role_permissions(7)
    assert result is True
    mock_instance.clear_role_permissions.assert_called_once_with(7)

@patch('app.services.permissions_service.RoleDAO')
def test_set_role_permissions(mock_role_dao):
    mock_instance = mock_role_dao.return_value
    mock_instance.set_role_permissions.return_value = True
    service = PermissionService()
    result = service.set_role_permissions(1, 2, True, False, True, False)
    assert result is True
    mock_instance.set_role_permissions.assert_called_once_with(1, 2, True, False, True, False) 