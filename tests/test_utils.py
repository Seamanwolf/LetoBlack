import pytest
from app.utils import validate_role_form, validate_update_role_form

def test_validate_role_form_valid():
    form = {'name': 'admin_role', 'display_name': 'Админ'}
    is_valid, error = validate_role_form(form)
    assert is_valid
    assert error is None

def test_validate_role_form_missing_name():
    form = {'display_name': 'Админ'}
    is_valid, error = validate_role_form(form)
    assert not is_valid
    assert 'Имя и отображаемое имя обязательны' in error

def test_validate_role_form_invalid_name():
    form = {'name': 'Admin!', 'display_name': 'Админ'}
    is_valid, error = validate_role_form(form)
    assert not is_valid
    assert 'Системное имя может содержать только' in error

def test_validate_update_role_form_valid():
    form = {'role_id': '1', 'display_name': 'Менеджер'}
    is_valid, error = validate_update_role_form(form)
    assert is_valid
    assert error is None

def test_validate_update_role_form_missing_id():
    form = {'display_name': 'Менеджер'}
    is_valid, error = validate_update_role_form(form)
    assert not is_valid
    assert 'ID роли и отображаемое имя обязательны' in error

def test_validate_update_role_form_missing_display_name():
    form = {'role_id': '1'}
    is_valid, error = validate_update_role_form(form)
    assert not is_valid
    assert 'ID роли и отображаемое имя обязательны' in error 