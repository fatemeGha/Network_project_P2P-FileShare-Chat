import socket
import threading
import struct
import time
from constants import CTRL

class ClientState:
    def __init__(self, sock):
        self.socket = sock
        self.logged_in = False
        self.username = None
        self.current_download = None 
        self.pending_username = None

def receive_packet(sock):
    header = recv_exact(sock, 4)
    if not header:
        return None, None

    total_length = struct.unpack("!I", header)[0]
    msg_type = recv_exact(sock, 1)

    if not msg_type:
        return None, None

    payload = recv_exact(sock, total_length - 1)
    if payload is None:
        return None, None

    return msg_type[0], payload.decode("utf-8")


def receive_messages(client_socket, state):

    while True:
        try:
            msg_type, payload = receive_packet(client_socket)
            if payload is None:
                break

            print(f"\n[SERVER] {payload}")

            if payload == "AUTH_SUCCESS":
                state.logged_in = True
                state.username = state.pending_username
                print(f"[INFO] Login successful as {state.username}")
            
            elif payload.startswith("FROM_CHAT"):
                parts = payload.split(" ", 2)
                sender = parts[1]
                message = parts[2]
                print(f"\n[CHAT] {sender}: {message}")

            elif payload == "OK":
                pass
            
        except Exception as e:
            print("Receive error:", e)
            break


def recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data



def send_packet(sock, msg_type, payload):
    
    payload_bytes = payload.encode("utf-8")

    total_length = 1 + len(payload_bytes)

    header = struct.pack("!I", total_length)

    packet = header + bytes([msg_type]) + payload_bytes

    sock.sendall(packet)




def show_menu(state):
    print("\n" + "=" * 40)
    if not state.logged_in:
        print("  MAIN MENU (Not Logged In)")
        print("=" * 40)
        print("  1. Register")
        print("  2. Login")
        print("  3. Exit")
        choice = input("Select: ")
        if choice == "1":
            handle_register(state)
        elif choice =="2" :
            handle_login(state)
        elif choice =="3" :
            handle_Exit(state)
            return False  
        else:
            print("Invalid choice")
        return True
    else:
        print(f"  MAIN MENU (Logged in as: {state.username})")
        print("=" * 40)
        print("  1. Logout")
        print("  2. List Online Users")
        print("  3. List Files")
        print("  4. Upload File")
        print("  5. Share File")
        print("  6. Send Chat")
        print("  7. Exit")
        print("=" * 40)
        choice = input("Select: ")
        if choice == "1":
            handle_logout(state)
        elif choice =="2" :
            handle_list_users(state)
        elif choice =="3" :
            handle_list_files(state)
        elif choice =="4" :
            handle_upload_file(state)
        elif choice =="5" :
            handle_share_file(state)
        elif choice =="6" :
            handle_send_chat(state)
        elif choice =="7" :
            handle_Exit(state)
            return False
        else:
            print("Invalid choice")
        return True
def handle_share_file(state):
    print()

def handle_send_chat(state):
    print()

def handle_upload_file(state):
    print()

def handle_register(state):

    print("\n[REGISTER]")
    username = input("  Username: ").strip()
    password = input("  Password: ").strip()
    
    if username and password:
        send_packet(state.socket, CTRL, f"REGISTER {username} {password}")
        print("  Sending registration request...")
    else:
        print("  [✗] Username and password cannot be empty")

def handle_logout(state):
    send_packet(state.socket, CTRL, f"LOGOUT")
    state.logged_in = False
    state.username = None
    print("  Logging out...")


def handle_list_users(state):
    send_packet(state.socket, CTRL, "LIST_USERS")
    print("  Requesting user list...")

def handle_list_files(state):
    send_packet(state.socket, CTRL, "LIST_FILES")
    print("  Requesting file list...")

def handle_login(state):
    print("\n[LOGIN]")
    username = input("  Username: ").strip()
    password = input("  Password: ").strip()
    state.pending_username = username

    if username and password:
        send_packet(state.socket, CTRL, f"LOGIN {username} {password}")
        print("  Sending login request...")
    else:
        print("  [✗] Username and password cannot be empty")


def handle_send_chat(state):

    target = input("Target User: ").strip()
    msg = input("Message: ").strip()

    if not target or not msg:
        print("Invalid input")
        return

    send_packet(
        state.socket,
        CTRL,
        f"CHAT {target} {msg}"
    )


def handle_Exit(state):
    send_packet(state.socket, CTRL, "EXIT")
    state.socket.close()

def start_client():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(('127.0.0.1', 8080))
    print("[CONNECTED] to server")
    
    state = ClientState(client)  

    receive_thread = threading.Thread(target=receive_messages, args=(client,state),daemon=True)
    receive_thread.start()
    while True:
        time.sleep(0.5)
        if not show_menu(state):
            break

if __name__ == "__main__":
    start_client()