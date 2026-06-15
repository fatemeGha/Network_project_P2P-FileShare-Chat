import socket
import threading
from constants import CTRL

class Client:
    def __init__(self):
        self.socket = None
        self.logged_in = False
        self.username = None
    
    def connect(self, host, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))
        print("[CONNECTED] to server")
    
    def send_command(self, command, *args):
        message = command
        for arg in args:
            message += " " + str(arg)
        send_packet(self.socket, CTRL, message)
    
    def handle_user_input(self, user_input):
        parts = user_input.strip().split()
        if not parts:
            return
        
        cmd = parts[0].upper()
        args = parts[1:]
        
        if cmd == "REGISTER":
            if len(args) == 2:
                self.send_command("REGISTER", args[0], args[1])
            else:
                print("Usage: REGISTER <username> <password>")
        
        elif cmd == "LOGIN":
            if len(args) == 2:
                self.send_command("LOGIN", args[0], args[1])
            else:
                print("Usage: LOGIN <username> <password>")
        
        elif cmd == "EXIT":
            self.send_command("EXIT")
            return False
        
        elif not self.logged_in:
            print("You must login first")
        
        elif cmd == "LOGOUT":
            self.send_command("LOGOUT")
            self.logged_in = False
            self.username = None
        
        elif cmd == "LIST_USERS":
            self.send_command("LIST_USERS")
        
        elif cmd == "LIST_FILES":
            self.send_command("LIST_FILES")
        
        elif cmd == "CHAT":
            if len(args) >= 2:
                target = args[0]
                message = " ".join(args[1:])
                self.send_command("CHAT", target, message)
            else:
                print("Usage: CHAT <username> <message>")
        
        elif cmd == "SHARE":
            if len(args) == 2:
                self.send_command("SHARE", args[0], args[1])
            else:
                print("Usage: SHARE <filename> <target_user>")
        
        elif cmd == "UPLOAD":
            if len(args) == 2:
                self.send_command("UPLOAD", args[0], args[1])
            else:
                print("Usage: UPLOAD <filename> <filesize>")
        
        else:
            print(f"Unknown command: {cmd}")
        
        return True
    
    def receive_messages(self):
        while True:
            try:
                data = self.socket.recv(1024)
                if not data:
                    break
                
                response = data.decode('utf-8')
                
                if response == "AUTH_SUCCESS":
                    self.logged_in = True
                    print("[LOGIN SUCCESS] You are now logged in")
                elif response == "AUTH_FAILED":
                    print("[LOGIN FAILED] Invalid username or password")
                elif response.startswith("USER_LIST"):
                    print("Online users:", response)
                elif response.startswith("FILE_LIST"):
                    print("Files:", response)
                elif response.startswith("SHARE_REQUEST"):
                    print(f"[SHARE REQUEST] {response}")
                    print("Type ACCEPT_FILE <filename> or REJECT_FILE <filename> to respond")
                else:
                    print(f"[SERVER] {response}")
                    
            except:
                break
    
    def run(self):
        recv_thread = threading.Thread(target=self.receive_messages)
        recv_thread.daemon = True
        recv_thread.start()
        
        # حلقه دریافت ورودی کاربر
        while True:
            user_input = input("> ")
            if not self.handle_user_input(user_input):
                break
        
        self.socket.close()


def start_client():
    client = Client()
    client.connect('127.0.0.1', 8084)
    client.run()


if __name__ == "__main__":
    start_client()