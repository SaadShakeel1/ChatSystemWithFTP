# Secure Chat & FTP System

A modern, real-time chat and file sharing application built with FastAPI and vanilla JavaScript.

## 📋 Table of Contents
- [Features](#features)
- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Codebase Structure](#codebase-structure)
- [Understanding the Code](#understanding-the-code)
- [How It Works](#how-it-works)
- [API Reference](#api-reference)

---

## ✨ Features

- **Real-Time Chat**: Instant messaging using WebSockets
- **Broadcast & Direct Messages**: Send to everyone or privately to specific users
- **File Sharing**: Upload and download files with ownership tracking
- **Secure Deletion**: Only file owners can delete their uploads
- **Modern UI**: Professional dark-themed interface
- **Concurrent Users**: Handles multiple simultaneous connections

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the server:**
   ```bash
   python -m uvicorn server:app --host 127.0.0.1 --port 8010
   ```

3. **Access the application:**
   Open your browser and navigate to:
   ```
   http://127.0.0.1:8010
   ```

### What Happens When You Start the Server?

1. **FastAPI Server** starts on port 8010
2. **FTP Server** starts on port 2121 (or next available port)
3. **WebSocket endpoint** becomes available at `ws://127.0.0.1:8010/ws`
4. **Frontend** is served at `http://127.0.0.1:8010`

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT SIDE                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Web Browser (static/index.html)                       │ │
│  │  - HTML/CSS/JavaScript UI                              │ │
│  │  - WebSocket Client (real-time messages)               │ │
│  │  - HTTP Client (file operations)                       │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↕ ↕ ↕
                    WebSocket | HTTP | FTP
                            ↕ ↕ ↕
┌─────────────────────────────────────────────────────────────┐
│                        SERVER SIDE                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  FastAPI Application (server.py)                       │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  WebSocket Handler                               │  │ │
│  │  │  - Manages active connections                    │  │ │
│  │  │  - Routes broadcast/direct messages              │  │ │
│  │  │  - Handles user join/leave events                │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  HTTP Endpoints                                  │  │ │
│  │  │  - GET /files (list files with owners)           │  │ │
│  │  │  - POST /upload (upload file + record owner)     │  │ │
│  │  │  - DELETE /delete/{filename} (owner-only)        │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Custom FTP Server (ftp_server.py)                    │ │
│  │  - Runs in separate thread                            │ │
│  │  - Serves files from data/files/                      │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Data Storage                                          │ │
│  │  - data/files/ (uploaded files)                        │ │
│  │  - data/files_metadata.json (ownership tracking)       │ │
│  │  - data/logs/server.log (activity logs)                │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Codebase Structure

```
secure-chat/
├── server.py                    # Main FastAPI backend (CORE FILE)
├── ftp_server.py               # Custom FTP server implementation
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── static/
│   └── index.html             # Frontend SPA (HTML + CSS + JS)
└── data/
    ├── files/                 # Uploaded files storage
    ├── files_metadata.json    # File ownership tracking
    └── logs/
        └── server.log         # Server activity logs
```

### Key Files Explained

#### `server.py` - Backend Server (500+ lines)
The heart of the application. Contains:
- **FastAPI setup** (lines 1-115)
- **WebSocket connection management** (lines 178-290)
- **File operation endpoints** (lines 350-480)
- **FTP server integration** (lines 292-348)

#### `static/index.html` - Frontend Application (550+ lines)
Single-page application containing:
- **HTML structure** (lines 1-253)
- **CSS styling** (lines 10-187)
- **JavaScript logic** (lines 255-551)

#### `ftp_server.py` - FTP Server
Custom FTP server implementation for file sharing.

---

## 💡 Understanding the Code

### Backend (`server.py`)

#### 1. **Imports and Setup** (Lines 1-35)
```python
"""
Module docstring explaining the system
"""
import os, json, asyncio, threading, socket
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# Directory paths for data storage
LOG_DIR = os.path.join("data", "logs")
FILES_DIR = os.path.join("data", "files")
METADATA_FILE = os.path.join("data", "files_metadata.json")
```

**What this does:**
- Imports required libraries
- Defines paths for storing logs, files, and metadata
- Sets up the foundation for the application

#### 2. **Helper Functions** (Lines 35-77)

**`ensure_dir(path)`** - Creates directories if they don't exist
```python
def ensure_dir(path):
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)
```

**`log_server(message)`** - Logs activity with timestamps
```python
def log_server(message: str):
    """Log server activity to file and console."""
    # Writes to data/logs/server.log with timestamp
```

**`load_metadata()` / `save_metadata()`** - Manage file ownership
```python
def load_metadata():
    """Load file ownership from JSON."""
    # Returns: {"filename.pdf": "alice", "image.png": "bob"}
```

#### 3. **FastAPI Application** (Lines 95-115)
```python
app = FastAPI(title="Secure Chat & FTP")

# Serve frontend files
app.mount("/static", StaticFiles(directory="static"))
# Serve uploaded files for download
app.mount("/files_proxy", StaticFiles(directory="data/files"))
```

**What this does:**
- Creates FastAPI application instance
- Mounts static directories for serving files
- `/static` → serves `index.html`
- `/files_proxy` → serves uploaded files

#### 4. **Connection Management** (Lines 110-115)
```python
# Dictionary: username → WebSocket connection
active_connections: Dict[str, WebSocket] = {}

# Lock to prevent race conditions
connections_lock = asyncio.Lock()
```

**Why a dictionary?**
- Fast O(1) lookup by username
- Easy to broadcast to all users
- Simple to add/remove connections

**Why a lock?**
- Prevents race conditions when multiple users connect/disconnect simultaneously
- Ensures thread-safe access to `active_connections`

#### 5. **WebSocket Endpoint** (Lines 178-290)

**Connection Flow:**
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # 1. Extract username from query parameter
    username = websocket.query_params.get("username")
    
    # 2. Validate username exists
    if not username:
        await websocket.close(code=1008)
        return
    
    # 3. Accept connection
    await websocket.accept()
    
    # 4. Check for duplicate username
    async with connections_lock:
        if username in active_connections:
            # Reject duplicate
            await websocket.send_text(...)
            await websocket.close()
            return
        # Add to active connections
        active_connections[username] = websocket
    
    # 5. Broadcast join notification
    await broadcast({"type": "info", "message": f"{username} joined", ...})
    
    # 6. Message loop
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            
            # Route based on message type
            if data["type"] == "broadcast":
                await broadcast(...)
            elif data["type"] == "direct":
                await send_to_user(...)
    finally:
        # 7. Cleanup on disconnect
        del active_connections[username]
        await broadcast({"type": "info", "message": f"{username} left", ...})
```

**Message Types:**

| Type | Purpose | Example |
|------|---------|---------|
| `broadcast` | Send to all users | `{"type": "broadcast", "message": "Hello!"}` |
| `direct` | Send to specific user | `{"type": "direct", "to": "alice", "message": "Hi"}` |
| `users` | Request user list | `{"type": "users"}` |

#### 6. **File Operations** (Lines 350-480)

**List Files:**
```python
@app.get("/files")
async def list_files():
    # 1. List files in directory
    files = os.listdir(FILES_DIR)
    
    # 2. Load ownership metadata
    metadata = load_metadata()
    
    # 3. Build response with ownership
    file_list = [
        {"name": f, "owner": metadata.get(f, "Unknown")}
        for f in files
    ]
    return {"files": file_list}
```

**Upload File:**
```python
@app.post("/upload")
async def upload_file(file: UploadFile, username: str):
    # 1. Save file to disk
    file_path = os.path.join(FILES_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # 2. Record ownership
    metadata = load_metadata()
    metadata[file.filename] = username
    save_metadata(metadata)
    
    # 3. Log and return
    log_server(f"[UPLOAD] {username} uploaded {file.filename}")
    return {"filename": file.filename, "message": "Success"}
```

**Delete File (with ownership check):**
```python
@app.delete("/delete/{filename}")
async def delete_file(filename: str, username: str):
    # 1. Check file exists
    if not os.path.exists(file_path):
        raise HTTPException(404, "File not found")
    
    # 2. Load metadata and check ownership
    metadata = load_metadata()
    owner = metadata.get(filename)
    
    # 3. SECURITY CHECK: Validate ownership
    if owner != username:
        raise HTTPException(403, "You can only delete your own files")
    
    # 4. Delete file and update metadata
    os.remove(file_path)
    del metadata[filename]
    save_metadata(metadata)
    
    return {"message": "File deleted successfully"}
```

**Security Features:**
- ✅ Server-side ownership validation
- ✅ HTTP 403 Forbidden for unauthorized attempts
- ✅ File existence check (404 if not found)
- ✅ Metadata persistence across restarts

### Frontend (`static/index.html`)

#### JavaScript State Management

**Global State:**
```javascript
let ws;                    // WebSocket connection
let currentUser = '';      // Logged-in username
let activeChat = 'broadcast'; // Current chat view
let chats = {              // Chat history
    'broadcast': { name: 'Broadcast Channel', messages: [], unread: 0 }
};
let allUsers = [];         // List of online users
```

**Chat Data Structure:**
```javascript
chats = {
    'broadcast': {
        name: 'Broadcast Channel',
        messages: [
            { sender: 'alice', text: 'Hello!', isSent: false, time: Date },
            { sender: 'You', text: 'Hi!', isSent: true, time: Date }
        ],
        unread: 0
    },
    'alice': {
        name: 'alice',
        messages: [...],
        unread: 2  // Unread message count
    }
}
```

#### Key Functions

**`connect()`** - Establish WebSocket connection
```javascript
function connect() {
    const username = document.getElementById('username-input').value;
    currentUser = username;
    
    // Create WebSocket connection
    ws = new WebSocket(`ws://localhost:8010/ws?username=${username}`);
    
    ws.onopen = () => {
        // Hide login, show chat
        loginScreen.style.display = 'none';
        app.classList.add('active');
    };
    
    ws.onmessage = (event) => {
        // Handle incoming messages
        handleMessage(JSON.parse(event.data));
    };
}
```

**`handleMessage(data)`** - Process incoming messages
```javascript
function handleMessage(data) {
    if (data.type === 'message') {
        const isDirect = data.is_direct;
        const sender = data.from;
        
        // Determine which chat this belongs to
        let targetChat = isDirect ? sender : 'broadcast';
        
        // Add message to chat history
        chats[targetChat].messages.push({
            sender: sender,
            text: data.message,
            isSent: false,
            time: new Date()
        });
        
        // Update UI
        if (activeChat === targetChat) {
            renderChat();  // Render immediately if viewing this chat
        } else {
            chats[targetChat].unread++;  // Increment unread counter
        }
    }
}
```

**`sendMessage()`** - Send message
```javascript
function sendMessage() {
    const text = messageInput.value.trim();
    
    if (activeChat === 'broadcast') {
        // Broadcast to all
        ws.send(JSON.stringify({ type: 'broadcast', message: text }));
        // Server echoes back, so don't add manually
    } else {
        // Direct message
        ws.send(JSON.stringify({ type: 'direct', to: activeChat, message: text }));
        // Server doesn't echo DMs to sender, so add manually
        chats[activeChat].messages.push({
            sender: currentUser,
            text: text,
            isSent: true,
            time: new Date()
        });
        renderChat();
    }
}
```

**Why different handling for broadcast vs direct?**
- **Broadcast**: Server sends to ALL users (including sender) → client receives own message → don't add manually
- **Direct**: Server sends ONLY to recipient → sender doesn't receive echo → must add manually

---

## 🔄 How It Works

### User Connection Flow

```
1. User opens http://127.0.0.1:8010
   ↓
2. Server serves static/index.html
   ↓
3. User enters username and clicks "Join Chat"
   ↓
4. JavaScript creates WebSocket connection:
   ws://127.0.0.1:8010/ws?username=alice
   ↓
5. Server validates username (must be unique)
   ↓
6. Server accepts connection and adds to active_connections
   ↓
7. Server broadcasts join notification to all users
   ↓
8. All clients update their user lists
```

### Message Flow (Broadcast)

```
1. Alice types "Hello everyone!" and clicks send
   ↓
2. Client sends: {"type": "broadcast", "message": "Hello everyone!"}
   ↓
3. Server receives message via WebSocket
   ↓
4. Server calls broadcast() function
   ↓
5. Server sends to ALL active connections (including Alice)
   ↓
6. All clients receive: {"type": "message", "from": "alice", "message": "Hello everyone!"}
   ↓
7. Each client adds message to broadcast chat history
   ↓
8. UI updates with new message
```

### Message Flow (Direct)

```
1. Alice clicks "Bob" in user list (switches to DM chat)
   ↓
2. Alice types "Secret message" and clicks send
   ↓
3. Client sends: {"type": "direct", "to": "bob", "message": "Secret message"}
   ↓
4. Server receives message
   ↓
5. Server calls send_to_user("bob", ...)
   ↓
6. Server sends ONLY to Bob's WebSocket connection
   ↓
7. Bob's client receives message and adds to chat with Alice
   ↓
8. Alice's client adds message manually (server doesn't echo)
```

### File Upload Flow

```
1. User clicks upload button (⬆)
   ↓
2. User selects file from file picker
   ↓
3. JavaScript creates FormData with file + username
   ↓
4. POST /upload with multipart/form-data
   ↓
5. Server saves file to data/files/
   ↓
6. Server records ownership in metadata.json:
   {"filename.pdf": "alice"}
   ↓
7. Server returns success response
   ↓
8. Client calls refreshFiles()
   ↓
9. GET /files returns list with owners
   ↓
10. UI updates file list with delete button (if owner)
```

### File Deletion Flow

```
1. User clicks delete button (🗑) on their file
   ↓
2. JavaScript shows confirmation dialog
   ↓
3. User confirms deletion
   ↓
4. DELETE /delete/filename?username=alice
   ↓
5. Server checks file exists (404 if not)
   ↓
6. Server loads metadata and gets owner
   ↓
7. Server compares owner with requester
   ↓
8. If match:
   - Delete file from filesystem
   - Remove from metadata
   - Return 200 OK
   ↓
9. If no match:
   - Return 403 Forbidden
   ↓
10. Client refreshes file list
```

---

## 📚 API Reference

### WebSocket API

**Endpoint:** `ws://localhost:8010/ws?username=<username>`

**Client → Server Messages:**

| Type | Format | Description |
|------|--------|-------------|
| Broadcast | `{"type": "broadcast", "message": "text"}` | Send to all users |
| Direct | `{"type": "direct", "to": "username", "message": "text"}` | Send to specific user |
| Users | `{"type": "users"}` | Request user list |

**Server → Client Messages:**

| Type | Format | Description |
|------|--------|-------------|
| Message | `{"type": "message", "from": "username", "message": "text", "is_direct": bool}` | Incoming message |
| Info | `{"type": "info", "message": "text", "users": [...]}` | System notification + user list |
| Error | `{"type": "error", "message": "text"}` | Error message |

### HTTP API

| Method | Endpoint | Parameters | Response | Description |
|--------|----------|------------|----------|-------------|
| GET | `/` | - | HTML | Serve frontend |
| GET | `/files` | - | `{"files": [{"name": "...", "owner": "..."}]}` | List files with owners |
| POST | `/upload` | `file` (multipart), `username` (form) | `{"filename": "...", "message": "..."}` | Upload file |
| DELETE | `/delete/{filename}` | `username` (query) | `{"message": "..."}` or 403/404 | Delete file (owner only) |
| GET | `/files_proxy/{filename}` | - | File content | Download file |

---

## 🔐 Security Features

1. **Ownership-Based Deletion**
   - Server validates file ownership before deletion
   - HTTP 403 Forbidden for unauthorized attempts
   - Metadata persists across server restarts

2. **Input Validation**
   - Username required for WebSocket connection
   - Duplicate usernames rejected
   - JSON validation for all messages

3. **Concurrent Access Protection**
   - Asyncio locks prevent race conditions
   - Thread-safe connection management
   - Atomic metadata updates

4. **Error Handling**
   - Graceful error messages
   - Server stability maintained
   - User-friendly error alerts

---

## 📝 Code Comments Guide

The codebase includes extensive inline comments:

- **Docstrings**: Every function has a docstring explaining purpose, parameters, and return values
- **Inline Comments**: Complex logic is explained step-by-step
- **Section Headers**: Major sections are clearly marked with comment blocks
- **Examples**: Data structures include example values in comments

**Example from `server.py`:**
```python
async def send_to_user(username: str, message: dict):
    \"\"\"
    Send message to a specific user (direct message).
    
    Args:
        username: Target user's username
        message: Dictionary to send (will be JSON serialized)
    
    If user is not connected, message is silently dropped.
    Errors are logged but don't raise exceptions.
    \"\"\"
    async with connections_lock:  # Acquire lock for thread safety
        ws = active_connections.get(username)
    if ws:
        try:
            await ws.send_text(json.dumps(message))
        except Exception as e:
            log_server(f\"[SEND_ERROR] to {username}: {e}\")
```

---

## 🎓 Learning Resources

To understand this codebase better, study these concepts:

1. **WebSockets**: Real-time bidirectional communication
2. **Async/Await**: Python's asynchronous programming
3. **FastAPI**: Modern Python web framework
4. **REST APIs**: HTTP endpoint design
5. **JavaScript DOM**: Frontend manipulation
6. **Event-Driven Programming**: WebSocket event handlers

---

## 📞 Support

For questions or issues:
1. Read the inline code comments
2. Check the comprehensive documentation
3. Review the walkthrough guide
4. Examine the server logs in `data/logs/server.log`

---

**Built with ❤️ using FastAPI and Vanilla JavaScript**