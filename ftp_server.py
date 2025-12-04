import socket
import threading
import os
import time

class CustomFTPServer:
    def __init__(self, host='0.0.0.0', port=2121, root_dir='data/files'):
        self.host = host
        self.port = port
        self.root_dir = root_dir
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = False
        
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir)

    def start(self):
        try:
            self.sock.bind((self.host, self.port))
            self.sock.listen(5)
            self.running = True
            print(f"Custom FTP Server listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_sock, addr = self.sock.accept()
                    print(f"FTP Connection from {addr}")
                    handler = FTPHandler(client_sock, self.root_dir)
                    threading.Thread(target=handler.handle, daemon=True).start()
                except OSError:
                    break
        except Exception as e:
            print(f"FTP Server Error: {e}")

    def stop(self):
        self.running = False
        self.sock.close()

class FTPHandler:
    def __init__(self, sock, root_dir):
        self.sock = sock
        self.root_dir = os.path.abspath(root_dir)
        self.cwd = self.root_dir
        self.authenticated = False
        self.pasv_mode = False
        self.data_sock = None
        self.data_addr = None
        self.pasv_sock = None

    def send(self, msg):
        try:
            self.sock.sendall((msg + '\r\n').encode('utf-8'))
        except:
            pass

    def handle(self):
        self.send("220 Welcome to Custom FTP Server")
        while True:
            try:
                data = self.sock.recv(1024).decode('utf-8').strip()
                if not data: break
                print(f"FTP CMD: {data}")
                
                cmd_parts = data.split(' ', 1)
                cmd = cmd_parts[0].upper()
                arg = cmd_parts[1] if len(cmd_parts) > 1 else ""

                if cmd == "USER":
                    self.send("331 Please specify the password.")
                elif cmd == "PASS":
                    self.authenticated = True # Accept any password for demo
                    self.send("230 Login successful.")
                elif not self.authenticated and cmd != "QUIT":
                    self.send("530 Please login with USER and PASS.")
                    continue
                elif cmd == "PWD":
                    rel_path = "/" + os.path.relpath(self.cwd, self.root_dir).replace("\\", "/")
                    if rel_path == "/.": rel_path = "/"
                    self.send(f'257 "{rel_path}"')
                elif cmd == "CWD":
                    new_path = os.path.join(self.cwd, arg)
                    if os.path.isdir(new_path) and os.path.abspath(new_path).startswith(self.root_dir):
                        self.cwd = new_path
                        self.send("250 Directory successfully changed.")
                    else:
                        self.send("550 Failed to change directory.")
                elif cmd == "TYPE":
                    self.send("200 Switching to Binary mode.")
                elif cmd == "PASV":
                    self.start_pasv()
                elif cmd == "PORT":
                    self.handle_port(arg)
                elif cmd == "LIST":
                    self.handle_list()
                elif cmd == "RETR":
                    self.handle_retr(arg)
                elif cmd == "STOR":
                    self.handle_stor(arg)
                elif cmd == "QUIT":
                    self.send("221 Goodbye.")
                    break
                else:
                    self.send("502 Command not implemented.")
            except Exception as e:
                print(f"Handler Error: {e}")
                break
        self.close_data()
        self.sock.close()

    def start_pasv(self):
        self.pasv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.pasv_sock.bind(('0.0.0.0', 0))
        self.pasv_sock.listen(1)
        port = self.pasv_sock.getsockname()[1]
        ip = '127,0,0,1' # Hardcoded for local demo
        p1, p2 = port // 256, port % 256
        self.send(f"227 Entering Passive Mode ({ip},{p1},{p2}).")
        self.pasv_mode = True

    def handle_port(self, arg):
        # PORT h1,h2,h3,h4,p1,p2
        parts = arg.split(',')
        ip = '.'.join(parts[:4])
        port = int(parts[4]) * 256 + int(parts[5])
        self.data_addr = (ip, port)
        self.pasv_mode = False
        self.send("200 PORT command successful.")

    def open_data_conn(self):
        if self.pasv_mode:
            conn, addr = self.pasv_sock.accept()
            self.pasv_sock.close()
            self.pasv_sock = None
            return conn
        elif self.data_addr:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect(self.data_addr)
            return conn
        return None

    def close_data(self):
        if self.data_sock:
            self.data_sock.close()
            self.data_sock = None

    def handle_list(self):
        self.send("150 Here comes the directory listing.")
        conn = self.open_data_conn()
        if conn:
            files = os.listdir(self.cwd)
            for f in files:
                # Minimal LIST format
                conn.sendall(f"{f}\r\n".encode('utf-8'))
            conn.close()
            self.send("226 Directory send OK.")
        else:
            self.send("425 Use PORT or PASV first.")

    def handle_retr(self, filename):
        path = os.path.join(self.cwd, filename)
        if os.path.exists(path):
            self.send("150 Opening data connection for file download.")
            conn = self.open_data_conn()
            if conn:
                with open(path, 'rb') as f:
                    while True:
                        data = f.read(4096)
                        if not data: break
                        conn.sendall(data)
                conn.close()
                self.send("226 Transfer complete.")
            else:
                self.send("425 Use PORT or PASV first.")
        else:
            self.send("550 File not found.")

    def handle_stor(self, filename):
        path = os.path.join(self.cwd, filename)
        self.send("150 Opening data connection for file upload.")
        conn = self.open_data_conn()
        if conn:
            with open(path, 'wb') as f:
                while True:
                    data = conn.recv(4096)
                    if not data: break
                    f.write(data)
            conn.close()
            self.send("226 Transfer complete.")
        else:
            self.send("425 Use PORT or PASV first.")

if __name__ == "__main__":
    server = CustomFTPServer()
    server.start()
