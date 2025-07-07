from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app.utils import create_db_connection
from app.routes.auth import redirect_based_on_role
from app.routes.admin import admin_routes_bp
from datetime import datetime

# Дублирующий маршрут personnel_dashboard удален - используется версия из personnel.py