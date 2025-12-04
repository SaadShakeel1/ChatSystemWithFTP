"""
Secure Chat & FTP System - Backend Server
==========================================

This module implements a real-time chat and file sharing system using:
- FastAPI for the web framework
- WebSockets for real-time bidirectional communication
- HTTP endpoints for file operations
- Custom FTP server for file sharing

Key Features:
- Broadcast messaging (send to all users)
- Direct messaging (private one-on-one chat)
- File upload/download with ownership tracking
- Secure file deletion (only owner can delete)
- Real-time user presence updates
"""

import os
import json
import asyncio
import threading
import socket
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Directory paths for data storage
LOG_DIR = os.path.join("data", "logs")              # Server activity logs
FILES_DIR = os.path.join("data", "files")           # Uploaded files storage
METADATA_FILE = os.path.join("data", "files_metadata.json")  # File ownership tracking


def ensure_dir(path):
    """
    Create directory if it doesn't exist.
    
    Args:
        path: Directory path to create
    """
    os.makedirs(path, exist_ok=True)


def log_server(message: str):
    """
    Log server activity to file and console.
    
    Args:
        message: Log message to record
    
    Logs are stored in data/logs/server.log with timestamps.
    """
    ensure_dir(LOG_DIR)
    with open(os.path.join(LOG_DIR, "server.log"), "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    print(message)


def load_metadata():
    """
    Load file ownership metadata from JSON file.
    
    Returns:
        dict: Mapping of filename -> owner username
              Example: {"document.pdf": "alice", "image.png": "bob"}
    
    Returns empty dict if file doesn't exist or is corrupted.
    """
    if not os.path.exists(METADATA_FILE):
        return {}
    try:
        with open(METADATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_metadata(metadata):
    """
    Save file ownership metadata to JSON file.
    
    Args:
        metadata: Dictionary mapping filename -> owner username
    
    Creates directory if it doesn't exist.
    """
    ensure_dir(os.path.dirname(METADATA_FILE))
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f)


# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(title="Secure Chat & FTP", description="WebSocket chat with FTP sharing")

# Mount static directories for serving files
app.mount("/static", StaticFiles(directory="static"), name="static")  # Frontend HTML/CSS/JS
app.mount("/files_proxy", StaticFiles(directory="data/files"), name="files")  # Uploaded files for download


# ============================================================================
# WebSocket Connection Management
# ============================================================================

# Dictionary mapping username -> WebSocket connection
# Example: {"alice": <WebSocket>, "bob": <WebSocket>}
active_connections: Dict[str, WebSocket] = {}

# Async lock to prevent race conditions when multiple users connect/disconnect simultaneously
connections_lock = asyncio.Lock()


# ============================================================================
# HTTP Endpoints
# ============================================================================

@app.get("/")
async def index():
    """
    Serve the main frontend application.
    
    Returns:
        HTML page with the chat interface
    """
    return FileResponse("static/index.html")


@app.get("/users")
async def list_users():
    """
    Get list of currently connected users.
    
    Returns:
        JSON: {"users": ["alice", "bob", "charlie"]}
    """
    async with connections_lock:
        return {"users": list(active_connections.keys())}


async def broadcast(message: dict):
    """
    Send message to all connected users.
    
    Args:
        message: Dictionary to send (will be JSON serialized)
    
    Uses asyncio.gather to send to all users concurrently.
    Exceptions are caught to prevent one failed send from affecting others.
    """
    async with connections_lock:
        send_tasks = [ws.send_text(json.dumps(message)) for ws in active_connections.values()]
    if send_tasks:
        await asyncio.gather(*send_tasks, return_exceptions=True)


async def send_to_user(username: str, message: dict):
    """
    Send message to a specific user (direct message).
    
    Args:
        username: Target user's username
        message: Dictionary to send (will be JSON serialized)
    
    If user is not connected, message is silently dropped.
    Errors are logged but don't raise exceptions.
    """
    async with connections_lock:
        ws = active_connections.get(username)
    if ws:
        try:
            await ws.send_text(json.dumps(message))
        except Exception as e:
            log_server(f"[SEND_ERROR] to {username}: {e}")


# ============================================================================
# WebSocket Endpoint - Real-Time Chat
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handle WebSocket connections for real-time chat.
    
    Connection Flow:
    1. Client connects with ?username=<name> query parameter
    2. Server validates username (must exist and be unique)
    3. Accept connection and add to active_connections
    4. Broadcast join notification to all users
    5. Listen for incoming messages
    6. Route messages (broadcast or direct)
    7. On disconnect, remove from active_connections and notify others
    
    Message Types:
    - broadcast: {"type": "broadcast", "message": "text"}
    - direct: {"type": "direct", "to": "username", "message": "text"}
    - users: {"type": "users"} - request user list
    """
    # Extract username from query parameters
    # Example: ws://localhost:8010/ws?username=alice
    username = websocket.query_params.get("username")
    if not username:
        # Reject connection if no username provided
        await websocket.close(code=1008)  # Policy Violation
        return

    # Accept the WebSocket connection
    await websocket.accept()
    
    # Check for duplicate username (prevent identity conflicts)
    async with connections_lock:
        if username in active_connections:
            await websocket.send_text(json.dumps({"type": "error", "message": "Username already connected."}))
            await websocket.close(code=1008)
            return
        # Add user to active connections
        active_connections[username] = websocket
    
    # Log the join event
    log_server(f"[JOIN] {username}")
    
    # Notify all users about the new user (includes updated user list)
    await broadcast({"type": "info", "message": f"{username} joined", "users": list(active_connections.keys())})

    # Main message loop - listen for incoming messages
    try:
        while True:
            # Wait for message from client
            raw = await websocket.receive_text()
            
            # Parse JSON message
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON."}))
                continue

            # Route message based on type
            msg_type = data.get("type")
            
            if msg_type == "broadcast":
                # Broadcast message to ALL users (including sender)
                text = data.get("message", "")
                await broadcast({"type": "message", "from": username, "message": text})
                log_server(f"[BCAST] {username}: {text}")
                
            elif msg_type == "direct":
                # Direct message to specific user (private)
                to = data.get("to")
                text = data.get("message", "")
                if not to:
                    await websocket.send_text(json.dumps({"type": "error", "message": "Missing 'to' for direct message."}))
                    continue
                # Send only to recipient (NOT to sender - client handles that)
                await send_to_user(to, {"type": "message", "from": username, "message": text, "is_direct": True})
                log_server(f"[DM] {username} → {to}: {text}")
                
            elif msg_type == "users":
                # Client requesting current user list
                async with connections_lock:
                    users = list(active_connections.keys())
                await websocket.send_text(json.dumps({"type": "users", "users": users}))
                
            else:
                # Unknown message type
                await websocket.send_text(json.dumps({"type": "error", "message": "Unknown message type."}))
                
    except WebSocketDisconnect:
        # Client disconnected (normal closure)
        pass
    finally:
        # Cleanup: Remove user from active connections
        async with connections_lock:
            if username in active_connections and active_connections[username] is websocket:
                del active_connections[username]
        
        # Log the leave event
        log_server(f"[LEAVE] {username}")
        
        # Notify all remaining users
        await broadcast({"type": "info", "message": f"{username} left", "users": list(active_connections.keys())})


# ============================================================================
# FTP Server Integration
# ============================================================================

# Import custom FTP server implementation
from ftp_server import CustomFTPServer

def start_ftp_server():
    """
    Start the custom FTP server in a separate daemon thread.
    
    Port Selection:
    - Tries ports 2121-2129 in sequence
    - Uses first available port
    - Logs which port was selected
    
    The FTP server:
    - Runs in a separate thread (non-blocking)
    - Serves files from data/files/ directory
    - Allows anonymous read-only access
    - Supports user/password authentication
    """
    try:
        ensure_dir(FILES_DIR)
        ftp_port = 2121
        server = None
        
        # Try multiple ports to avoid conflicts
        while ftp_port < 2130:
            try:
                # Test if port is available before binding
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.bind(('0.0.0.0', ftp_port))
                test_sock.close()
                
                # Port is available, create FTP server
                server = CustomFTPServer(host='0.0.0.0', port=ftp_port, root_dir=FILES_DIR)
                break
            except Exception as e:
                log_server(f"FTP port {ftp_port} in use, trying {ftp_port + 1}...")
                ftp_port += 1
        
        if server:
            # Start FTP server in background daemon thread
            # Daemon thread will automatically terminate when main program exits
            threading.Thread(target=server.start, daemon=True).start()
            log_server(f"Custom FTP server started on port {ftp_port}")
        else:
            log_server("Failed to start FTP server: No ports available")
            
    except Exception as e:
        log_server(f"[FTP_ERROR] {e}")

# ============================================================================
# File Management Endpoints
# ============================================================================

@app.get("/files")
async def list_files():
    """
    Get list of all uploaded files with ownership information.
    
    Returns:
        JSON: {
            "files": [
                {"name": "document.pdf", "owner": "alice"},
                {"name": "image.png", "owner": "bob"}
            ]
        }
    
    Each file object contains:
    - name: Filename
    - owner: Username of uploader
    """
    try:
        # List all files in the files directory
        files = os.listdir(FILES_DIR)
        
        # Load ownership metadata
        metadata = load_metadata()
        
        # Build file list with ownership info
        file_list = []
        for f in files:
            file_list.append({
                "name": f,
                "owner": metadata.get(f, "Unknown")  # Default to "Unknown" if not in metadata
            })
        return {"files": file_list}
    except Exception as e:
        return {"error": str(e), "files": []}

from fastapi import UploadFile, File, Form, HTTPException

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), username: str = Form(...)):
    """
    Upload a file and record ownership.
    
    Args:
        file: File to upload (multipart/form-data)
        username: Username of uploader (form field)
    
    Process:
    1. Save file to data/files/ directory
    2. Record ownership in metadata.json
    3. Log the upload
    4. Return success response
    
    Returns:
        JSON: {"filename": "...", "message": "File uploaded successfully"}
        or {"error": "..."} on failure
    """
    try:
        # Construct file path
        file_path = os.path.join(FILES_DIR, file.filename)
        
        # Save file to disk
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Record ownership in metadata
        metadata = load_metadata()
        metadata[file.filename] = username
        save_metadata(metadata)
        
        # Log the upload
        log_server(f"[UPLOAD] {username} uploaded {file.filename}")
        return {"filename": file.filename, "message": "File uploaded successfully"}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/delete/{filename}")
async def delete_file(filename: str, username: str):
    """
    Delete a file (only if requester is the owner).
    
    Args:
        filename: Name of file to delete (path parameter)
        username: Username of requester (query parameter)
    
    Security:
    - Validates file exists (404 if not)
    - Validates ownership (403 if not owner)
    - Only owner can delete their files
    
    Process:
    1. Check if file exists
    2. Load metadata and get owner
    3. Compare owner with requester
    4. If match: delete file and update metadata
    5. If no match: return 403 Forbidden
    
    Returns:
        200: {"message": "File deleted successfully"}
        403: Forbidden (not owner)
        404: File not found
    """
    try:
        # Construct file path
        file_path = os.path.join(FILES_DIR, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
            
        # Load metadata to check ownership
        metadata = load_metadata()
        owner = metadata.get(filename)
        
        # Validate ownership (SECURITY CHECK)
        if owner != username:
            raise HTTPException(status_code=403, detail="You can only delete your own files")
            
        # Delete file from filesystem
        os.remove(file_path)
        
        # Remove from metadata
        if filename in metadata:
            del metadata[filename]
            save_metadata(metadata)
            
        # Log the deletion
        log_server(f"[DELETE] {username} deleted {filename}")
        return {"message": "File deleted successfully"}
        
    except HTTPException as he:
        # Re-raise HTTP exceptions (403, 404)
        raise he
    except Exception as e:
        # Catch-all for unexpected errors
        return {"error": str(e)}



# ============================================================================
# Application Startup
# ============================================================================

@app.on_event("startup")
def on_startup():
    """
    Run initialization tasks when the server starts.
    
    Tasks:
    1. Ensure log directory exists
    2. Start FTP server in background thread
    3. Log server startup
    
    This runs once when uvicorn starts the application.
    """
    ensure_dir(LOG_DIR)
    start_ftp_server()
    log_server("FastAPI WebSocket server started")

