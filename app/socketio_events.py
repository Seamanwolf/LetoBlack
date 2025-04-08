from .extensions import socketio

@socketio.on('connect', namespace='/notifications')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect', namespace='/notifications')
def handle_disconnect():
    print('Client disconnected')

