import socket
import threading
import struct
import time
from constants import CTRL , CHAT , FILE_CHUNK , END_FILE
import os

DOWNLOAD_DIR = "downloads"

class ClientState:
    def __init__(self, sock):
        self.socket = sock
        self.logged_in = False
        self.username = None
        self.current_download = None 
        self.pending_username = None
        self.last_ack = 0
        self.waiting_response = False
        self.show_menu = True
        self.uploading_path = {}
        # {
        #     [filename] = path
        # }
        self.pending_shares = []
        # {
        # "sender":"ali",
        # "filename":"test.pdf"
        # }
        self.current_download = {}
        # "filename": None,
        #     "file": None,
        #     "expected_chunk": 1

def receive_packet( sock):
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
    
    return msg_type[0], payload



def receive_messages(client_socket, state):

    while True:
        try:
            msg_type, payload = receive_packet(client_socket)
            if payload is None:
                break
            if msg_type == CTRL:
                state.waiting_response = False
                payload = payload.decode("utf-8")

            elif msg_type == CHAT:
                state.waiting_response = False
                payload = payload.decode("utf-8")

            elif msg_type == FILE_CHUNK:
                state.waiting_response = True
                handle_receive_file(state , payload)
                continue
            elif msg_type == END_FILE :
                filename = payload.decode("utf-8")
                if state.current_download:
                    state.current_download["file"].close()
                    print(f"\n[DOWNLOAD COMPLETE] "f"{filename}")
                    state.current_download = None
                state.waiting_response = False
                continue  

            print(f"\n[SERVER] {payload}")

            if payload == "AUTH_SUCCESS":
                state.logged_in = True
                state.username = state.pending_username
                print(f"[INFO] Login successful as {state.username}")
                state.waiting_response = False
            
            elif payload.startswith("FROM_CHAT"):
                parts = payload.split(" ", 2)
                sender = parts[1]
                message = parts[2]
                print(f"\n[CHAT] {sender}: {message}")


            elif payload.startswith("ACK"):
                ack_no = int(payload.split()[1])
                print(f"ACK chunk {ack_no}")
                state.waiting_response = True
                continue

            elif payload.startswith("PROGRESS"):
                percent = payload.split()[1]
                print(f"\rUploading... {percent}%",end="")
                state.waiting_response = True
                continue

            elif payload.startswith("SHARE_FILE_REQUEST"):
                parts = payload.split(" ",2)
                state.pending_shares.append({"sender": parts[1],"filename": parts[2]})
                print("\n[NEW SHARE REQUEST]")

            elif payload.startswith("START_FILE"):
                state.show_menu = False
                filename = payload.split(" ", 1)[1]

                folder = f"{DOWNLOAD_DIR}_{state.username}"
                os.makedirs(folder, exist_ok=True)

                path = os.path.join(folder, filename)

                state.current_download = {
                    "filename": filename,
                    "file": open(path, "wb"),
                    "expected_chunk": 1
                }
            elif payload.startswith("waiting_for_file_chunks"):
                parts = payload.split(" ", 1)

                start_upload(state ,parts[1])

                state.waiting_response = True
                continue

            elif payload == "UPLOAD_COMPLETE":
                print("\nUpload completed.")
                state.waiting_response = False
                time.sleep(0.2)
                state.show_menu = True

            elif payload.startswith("ONLINE_USERS") | payload.startswith("FILES") | payload.startswith("Rejected")  |  payload.startswith("Message sent successfully.") | payload.startswith("Registration is done")  | payload.startswith("Logged out") | payload.startswith("ERROR"):
                state.waiting_response = False

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

def send_binary_chunk(sock,chunk_no,chunk):
    meta = f"{chunk_no}|".encode("utf-8")

    payload = meta + chunk

    total_length = 1 + len(payload)
    header = struct.pack("!I", total_length)

    packet = (
        header +
        bytes([FILE_CHUNK]) +
        payload
    )
    sock.sendall(packet)

def handle_receive_file(state, payload):

    if state.current_download is None:
        print("ERROR: no active download")
        return

    first = payload.find(b"|")

    if first == -1:
        print("ERROR: invalid chunk")
        return

    chunk_no = int(payload[:first].decode())

    chunk_data = payload[first + 1:]

    if chunk_no != state.current_download["expected_chunk"]:
        print(
            f"ERROR: expected "
            f"{state.current_download['expected_chunk']} "
            f"got {chunk_no}"
        )
        return

    state.current_download["file"].write(chunk_data)

    state.current_download["expected_chunk"] += 1


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
        print("  7. Share file requests")
        print("  8. Exit")
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
            show_share_file_menu(state)
        elif choice =="8" :
            handle_Exit(state)
            return False
        else:
            print("Invalid choice")
        return True
    
def show_share_file_menu(state, index=0):

    if not state.pending_shares:
        print("No pending requests")
        return

    if index >= len(state.pending_shares):
        print("No more requests")
        return

    req = state.pending_shares[index]

    sender = req["sender"]
    filename = req["filename"]

    print("\n" + "=" * 40)
    print(" SHARE FILE MENU ")
    print("=" * 40)

    print(f"Sender   : {sender}")
    print(f"Filename : {filename}")

    print("1. Accept")
    print("2. Reject")
    print("3. Next request")
    print("4. Back")

    choice = input("Select: ")

    if choice == "1":
        state.pending_shares.pop(index)
        state.waiting_response = True
        send_packet(
            state.socket,
            CTRL,
            f"ACCEPT_FILE {sender} {filename}"
        )

    elif choice == "2":
        state.pending_shares.pop(index)
        state.waiting_response = True
        send_packet(
            state.socket,
            CTRL,
            f"REJECT_FILE {sender} {filename}"
        )

    elif choice == "3":
        show_share_file_menu(state, index + 1)
    
def handle_share_file(state):
    target = input("Target User: ").strip()
    path = input("file path: ").strip()
    filename = os.path.basename(path)
    if not target or not path:
        print("Invalid input")
        return
    state.waiting_response = True

    send_packet(
        state.socket,
        CTRL,
        f"SHARE_FILE {target} {filename}"
    )


def handle_upload_file(state):

    path = input("File path: ").strip()
    if not os.path.exists(path):
        print("File not found")
        return

    filename = os.path.basename(path)
    filesize = os.path.getsize(path)
    state.waiting_response = True
    state.uploading_path[filename] = path
    send_packet(
        state.socket,
        CTRL,
        f"UPLOAD {filename} {filesize}"
    )

def start_upload(state ,filename):
    path = state.uploading_path[filename]
    with open(path, "rb") as f:
        chunk_no = 1
        while True:
            chunk = f.read(1024)
            if not chunk:
                break

            send_binary_chunk(
                state.socket,
                chunk_no,
                chunk
            )
            chunk_no += 1
    state.waiting_response = True

    send_packet(
        state.socket,
        END_FILE,
        f"{filename}"
    )


def handle_register(state):

    print("\n[REGISTER]")
    username = input("  Username: ").strip()
    password = input("  Password: ").strip()
    
    if username and password:
        state.waiting_response = True
        send_packet(state.socket, CTRL, f"REGISTER {username} {password}")
        print("  Sending registration request...")
    else:
        print("  [✗] Username and password cannot be empty")

def handle_logout(state):
    state.waiting_response = True
    send_packet(state.socket, CTRL, f"LOGOUT")
    state.logged_in = False
    state.username = None
    print("  Logging out...")


def handle_list_users(state):
    state.waiting_response = True
    send_packet(state.socket, CTRL, "LIST_USERS")
    print("  Requesting user list...")

def handle_list_files(state):
    state.waiting_response = True
    send_packet(state.socket, CTRL, "LIST_FILES")
    print("  Requesting file list...")

def handle_login(state):
    print("\n[LOGIN]")
    username = input("  Username: ").strip()
    password = input("  Password: ").strip()
    state.pending_username = username

    if username and password:
        state.waiting_response = True
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
    state.waiting_response = True

    send_packet(
        state.socket,
        CHAT,
        f"{target} {msg}"
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

        if state.waiting_response | (not state.show_menu ):
            time.sleep(0.2)
            continue

        if not show_menu(state):
            break

if __name__ == "__main__":
    start_client()