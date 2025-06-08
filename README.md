# Collaborative Task Manager

A real-time collaborative task management application built with Flask and SocketIO. Create rooms, invite team members, and manage tasks together with a Kanban-style interface.

## Features

- **Room-based collaboration** with 6-character room codes
- **Real-time synchronization** across all connected users
- **Kanban board** with three columns: To Do, In Progress, Done
- **Drag & drop** tasks between columns
- **Inline editing** of task titles and descriptions
- **Task assignment** to team members
- **Priority levels** and due dates
- **Pure black theme** with responsive design

## Quick Start

### Prerequisites
- Python 3.8+
- pip

### Installation

```bash
git clone https://github.com/sh1vananda/do-doing-done.git
cd collaborative-task-manager
pip install -r requirements.txt
python app.py
```

Access at `http://127.0.0.1:5000`

## Project Structure

```
collaborative-task-manager/
├── app.py                          # Main Flask + SocketIO application
├── requirements.txt                # Dependencies
└── templates/
    ├── index.html                  # Landing page
    ├── room.html                   # Main dashboard
    └── components/
        └── task_item.html          # Task component
```

## Usage

1. **Create Room**: Enter room name and your name, get 6-character code
2. **Join Room**: Use room code and your name to join existing workspace
3. **Manage Tasks**: Create, edit, move, assign, and delete tasks in real-time
4. **Collaborate**: All changes sync instantly across team members

## Dependencies

```
Flask==2.3.3
Flask-SocketIO==5.3.6
python-socketio==5.8.0
python-engineio==4.7.1
```

## Architecture

- **Backend**: Flask with SocketIO for real-time communication
- **Frontend**: Vanilla JavaScript with Tailwind CSS
- **Storage**: Thread-safe in-memory data structures
- **Real-time**: WebSocket events for instant synchronization

## Production Deployment

```bash
pip install gunicorn eventlet
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
```
