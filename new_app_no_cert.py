import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import LoginManager, login_required, current_user
from flask_socketio import SocketIO
from flask_cors import CORS
from app import create_app

app = create_app()
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False) 