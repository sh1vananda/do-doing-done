from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
import json
import uuid
import threading
import html
import string
import random
import os
from secrets import token_hex

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', token_hex(32))
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Thread-safe data storage
_lock = threading.RLock()
rooms = {}
tasks = {}
connected_users = {}
user_rooms = {}
room_members = {}

class Room:
    def __init__(self, room_id, name, creator):
        self.id = room_id
        self.name = name
        self.creator = creator
        self.created_at = datetime.now()
        self.task_order = []

class Task:
    def __init__(self, title, description="", priority="medium", assignee="", due_date="", room_id=""):
        self.id = str(uuid.uuid4())
        self.title = html.escape(str(title).strip())[:100]
        self.description = html.escape(str(description).strip())[:500]
        self.priority = priority if priority in ['low', 'medium', 'high'] else 'medium'
        self.assignee = html.escape(str(assignee).strip())[:50]
        self.due_date = due_date
        self.status = "todo"
        self.room_id = room_id
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'assignee': self.assignee,
            'due_date': self.due_date,
            'status': self.status,
            'room_id': self.room_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

def generate_room_id():
    while True:
        room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if room_id not in rooms:
            return room_id

def get_user_sid_by_username(username, room_id):
    for sid, user in connected_users.items():
        if user == username and user_rooms.get(sid) == room_id:
            return sid
    return None

def broadcast_to_others(room_id, event, data, exclude_username=None):
    exclude_sid = None
    if exclude_username:
        exclude_sid = get_user_sid_by_username(exclude_username, room_id)
    
    if exclude_sid:
        socketio.emit(event, data, room=f'room_{room_id}', skip_sid=exclude_sid)
    else:
        socketio.emit(event, data, room=f'room_{room_id}')

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create-room', methods=['POST'])
def create_room():
    try:
        data = request.get_json()
        room_name = data.get('name', '').strip()
        creator_name = data.get('creator', '').strip()
        
        if not room_name or not creator_name:
            return jsonify({'error': 'Room name and creator name required'}), 400
        
        room_id = generate_room_id()
        
        with _lock:
            room = Room(room_id, room_name, creator_name)
            rooms[room_id] = room
            room_members[room_id] = set()
        
        return jsonify({
            'room_id': room_id,
            'room_name': room_name,
            'creator': creator_name
        })
    except Exception as e:
        return jsonify({'error': 'Failed to create room'}), 500

@app.route('/join-room', methods=['POST'])
def join_room_endpoint():
    try:
        data = request.get_json()
        room_id = data.get('room_id', '').strip().upper()
        username = data.get('username', '').strip()
        
        if not room_id or not username:
            return jsonify({'error': 'Room ID and username required'}), 400
        
        with _lock:
            if room_id not in rooms:
                return jsonify({'error': 'Room not found'}), 404
        
        return jsonify({
            'room_id': room_id,
            'room_name': rooms[room_id].name,
            'username': username
        })
    except Exception as e:
        return jsonify({'error': 'Failed to join room'}), 500

@app.route('/room/<room_id>')
def room_page(room_id):
    room_id = room_id.upper()
    username = request.args.get('username', '').strip()
    
    with _lock:
        if room_id not in rooms:
            return redirect(url_for('index'))
        room = rooms[room_id]
    
    return render_template('room.html', 
                         room_id=room_id, 
                         room_name=room.name,
                         username=username,
                         is_creator=room.creator == username)

@app.route('/api/tasks/<room_id>')
def get_tasks_api(room_id):
    try:
        room_id = room_id.upper()
        with _lock:
            if room_id not in rooms:
                return jsonify({'success': False, 'error': 'Room not found'}), 404
            
            room = rooms[room_id]
            categorized = {'todo': [], 'in_progress': [], 'done': []}
            
            for task_id in room.task_order:
                if task_id in tasks:
                    task = tasks[task_id]
                    categorized[task.status].append(task.to_dict())
        
        return jsonify({
            'success': True,
            'tasks': categorized,
            'members': list(room_members.get(room_id, set()))
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tasks', methods=['POST'])
def create_task():
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        room_id = data.get('room_id', '').upper()
        creator = data.get('creator', '').strip()
        
        if not title or not room_id:
            return jsonify({'success': False, 'error': 'Title and room ID required'}), 400
        
        with _lock:
            if room_id not in rooms:
                return jsonify({'success': False, 'error': 'Room not found'}), 404
            
            task = Task(
                title=title,
                description=data.get('description', ''),
                priority=data.get('priority', 'medium'),
                assignee=data.get('assignee', ''),
                due_date=data.get('due_date', ''),
                room_id=room_id
            )
            
            tasks[task.id] = task
            rooms[room_id].task_order.append(task.id)
        
        # Broadcast to others only
        broadcast_to_others(room_id, 'task_created', {
            'task': task.to_dict()
        }, exclude_username=creator)
        
        return jsonify({'success': True, 'task': task.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    try:
        data = request.get_json()
        updater = data.get('updater', '')
        
        with _lock:
            if task_id not in tasks:
                return jsonify({'success': False, 'error': 'Task not found'}), 404
            
            task = tasks[task_id]
            old_status = task.status
            
            # Update fields
            if 'title' in data and data['title'].strip():
                task.title = html.escape(str(data['title']).strip())[:100]
            if 'description' in data:
                task.description = html.escape(str(data['description']).strip())[:500]
            if 'status' in data and data['status'] in ['todo', 'in_progress', 'done']:
                task.status = data['status']
            if 'priority' in data and data['priority'] in ['low', 'medium', 'high']:
                task.priority = data['priority']
            if 'assignee' in data:
                task.assignee = html.escape(str(data['assignee']).strip())[:50]
            
            task.updated_at = datetime.now()
        
        # Broadcast to others only
        broadcast_to_others(task.room_id, 'task_updated', {
            'task': task.to_dict(),
            'old_status': old_status
        }, exclude_username=updater)
        
        return jsonify({'success': True, 'task': task.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        with _lock:
            if task_id not in tasks:
                return jsonify({'success': False, 'error': 'Task not found'}), 404
            
            task = tasks[task_id]
            room_id = task.room_id
            
            if room_id in rooms and task_id in rooms[room_id].task_order:
                rooms[room_id].task_order.remove(task_id)
            
            del tasks[task_id]
        
        # Broadcast to ALL users
        socketio.emit('task_deleted', {
            'task_id': task_id
        }, room=f'room_{room_id}')
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    with _lock:
        username = connected_users.pop(sid, None)
        room_id = user_rooms.pop(sid, None)
        
        if room_id and username:
            if room_id in room_members:
                room_members[room_id].discard(username)
            leave_room(f'room_{room_id}')
            
            socketio.emit('user_left', {
                'username': username,
                'member_count': len(room_members.get(room_id, set()))
            }, room=f'room_{room_id}')

@socketio.on('join_room')
def handle_join_room(data):
    try:
        username = data.get('username', '').strip()
        room_id = data.get('room_id', '').upper()
        sid = request.sid
        
        if not username or not room_id:
            emit('error', {'message': 'Invalid username or room ID'})
            return
        
        with _lock:
            if room_id not in rooms:
                emit('error', {'message': 'Room not found'})
                return
            
            # Leave old room
            old_room = user_rooms.get(sid)
            if old_room:
                leave_room(f'room_{old_room}')
                if old_room in room_members:
                    room_members[old_room].discard(connected_users.get(sid, ''))
            
            # Join new room
            join_room(f'room_{room_id}')
            connected_users[sid] = username
            user_rooms[sid] = room_id
            
            if room_id not in room_members:
                room_members[room_id] = set()
            room_members[room_id].add(username)
        
        # Notify others
        socketio.emit('user_joined', {
            'username': username,
            'member_count': len(room_members[room_id])
        }, room=f'room_{room_id}')
        
        # Confirm to user
        emit('room_joined', {
            'room_id': room_id,
            'username': username,
            'room_name': rooms[room_id].name
        })
    except Exception as e:
        emit('error', {'message': 'Failed to join room'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
