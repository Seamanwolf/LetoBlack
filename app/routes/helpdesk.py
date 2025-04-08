from flask import Blueprint, render_template

helpdesk_bp = Blueprint('helpdesk', __name__, url_prefix='/helpdesk')

@helpdesk_bp.route('/')
def index():
    return render_template('helpdesk/index.html')

@helpdesk_bp.route('/dashboard')
def helpdesk_dashboard():
    return render_template('helpdesk/helpdesk_dashboard.html')

@helpdesk_bp.route('/new')
def new_tickets():
    return render_template('helpdesk/new_tickets.html')

@helpdesk_bp.route('/in-progress')
def in_progress_tickets():
    return render_template('helpdesk/in_progress_tickets.html')

@helpdesk_bp.route('/closed')
def closed_tickets():
    return render_template('helpdesk/closed_tickets.html') 