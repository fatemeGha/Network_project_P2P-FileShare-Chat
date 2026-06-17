import datetime
import socket
import threading
import struct
from constants import CTRL , CHAT , FILE_CHUNK , END_FILE
import os


HOST = '0.0.0.0' 
PORT = 8080     
BACKLOG = 5
UPLOAD_DIR = "uploads"

users = {}  # username -> password

online_users = {}  
# username -> client_socket

client_info = {}
# client_socket -> username
files = {}
pending_shares = {}
active_uploads = {}
#  "filename": filename,
#     "size": filesize,
#     "received": 0,
#     "expected_chunk": 1,
#     "last_chunk": 0,
#     "file": 

pending_shares = {}
# pending_shares[receiver] = {
#     "sender": sender,
#     "filename": filename
# }
chat_history = []
#      {
#         "sender": sender,
#         "target": target,
#         "message": message
#     }

offline_messages = {}
# {
#     username : []
# }

def log_event(text):

    with open(
        "server.log",
        "a",
        encoding="utf8"
    ) as f:

        f.write(
            f"{datetime.now()} {text}\n"
        )

def chat_history(text):

    with open(
        "chat_history.log",
        "a",
        encoding="utf8"
    ) as f:

        f.write(
            f"{datetime.now()} {text}\n"
        )

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

    return msg_type[0], payload


def handle_client(client_socket, address):
    print(f"[NEW CONNECTION] {address} connected")
    while True:
        try:
            msg_type, payload = receive_packet(client_socket)
            if msg_type == CTRL:
                payload = payload.decode("utf-8")

            elif msg_type == CHAT:
                payload = payload.decode("utf-8")
            elif msg_type == FILE_CHUNK:
                handle_file_chunk(client_socket,payload)
                continue

            elif msg_type == END_FILE:
                handle_end_file(client_socket)
                continue
            
            if payload is None:
                break

            print(payload)            
            
            if payload.startswith("REGISTER"):
                    handle_register(client_socket, payload)

            elif payload.startswith("LOGIN"):
                    handle_login(client_socket, payload)

            elif payload == "LOGOUT":   
                handle_logout(client_socket)

            elif payload == "LIST_USERS":   
                handle_list_users(client_socket)

            elif payload == "LIST_FILES":   
                handle_list_files(client_socket)

            elif payload.startswith("UPLOAD"):
                handle_upload(client_socket, payload)

            elif payload.startswith("SHARE_FILE"):
                handle_share(client_socket, payload)

            elif payload.startswith("ACCEPT_FILE"):
                handle_accept_file(client_socket, payload)

            elif payload.startswith("REJECT_FILE"):
                handle_reject_file(client_socket, payload)            
            else:
                send_packet(client_socket,CTRL,"ERROR invalid command")
        except Exception as e:
            break
    
    if client_socket in client_info:
        username = client_info[client_socket]

        if username in online_users:
            del online_users[username]

        del client_info[client_socket]


    print(f"[DISCONNECT] {address} disconnected")
    client_socket.close()
def handle_share(sock , command):
    if sock not in client_info:
        send_packet(
            sock,
            CTRL,
            "ERROR authentication required"
        )
        return

    parts = command.split(" ", 2)

    if len(parts) < 3:
        send_packet(
            sock,
            CHAT,
            "ERROR invalid CHAT"
        )
        return

    target_user = parts[1]
    filename = parts[2]

    if target_user not in users:
        send_packet(
            sock,
            CTRL,
            "ERROR target user not found"
        )
        return

    if target_user not in online_users:
        send_packet(
            sock,
            CTRL,
            "ERROR target user is offline"
        )
        return

    sender = client_info[sock]

    target_socket = online_users[target_user]

    send_packet(
        target_socket,
        CTRL,
        f"SHARE_FILE_REQUEST {sender} {filename}"
    )

    send_packet(
        sock,
        CTRL,
        "WAITING FOR RESPONSE"
    )
def handle_end_file(sock):

    upload = active_uploads[sock]

    upload["file"].close()

    files[upload["filename"]] = {
        "owner": client_info[sock],
        "size": upload["size"]
    }

    del active_uploads[sock]

    send_packet(
        sock,
        CTRL,
        "UPLOAD_COMPLETE"
    )


def handle_file_chunk(sock, payload):

    first = payload.find(b'|')

    if first == -1:
        send_packet(sock, CTRL, "ERROR invalid chunk")
        return

    chunk_no = int(payload[:first].decode())

    chunk_data = payload[first + 1:]

    upload = active_uploads[sock]

    if chunk_no != upload["expected_chunk"]:
        send_packet(sock, CTRL, "ERROR invalid chunk")
        return

    upload["file"].write(chunk_data)

    upload["received"] += len(chunk_data)

    upload["last_chunk"] = chunk_no

    upload["expected_chunk"] += 1

    send_packet(sock,CTRL,f"ACK {chunk_no}")

    progress = (upload["received"] * 100) / upload["size"]
    send_packet(sock,CTRL,f"PROGRESS {progress:.1f}")


def handle_upload(sock, command):

    if sock not in client_info:
        send_packet(
            sock,
            CTRL,
            "ERROR authentication required"
        )
        return

    parts = command.split()

    if len(parts) != 3:
        send_packet(
            sock,
            CTRL,
            "ERROR invalid UPLOAD"
        )
        return

    filename = parts[1]

    try:
        filesize = int(parts[2])
    except:
        send_packet(
            sock,
            CTRL,
            "ERROR invalid filesize"
        )
        return
    if filename in files.keys() :
        send_packet(
            sock,
            CTRL,
            "ERROR The file exists on the server."
        )
        return
    filepath = os.path.join(
        UPLOAD_DIR,
        filename
    )

    f = open(filepath, "wb")

    active_uploads[sock] = {
        "filename": filename,
        "size": filesize,
        "received": 0,
        "expected_chunk": 1,
        "last_chunk": 0,
        "file": f
    }


    send_packet(sock, CTRL, "waiting for file chunks")

def handle_reject_file(sock , command):
    if sock not in client_info:
        send_packet(
            sock,
            CTRL,
            "ERROR authentication required"
        )
        return

    parts = command.split(" ", 2)

    if len(parts) < 3:
        send_packet(
            sock,
            CTRL,
            "ERROR invalid CHAT"
        )
        return

    target_user = parts[1]
    filename = parts[2]

    if target_user not in users:
        send_packet(
            sock,
            CTRL,
            "ERROR target user not found"
        )
        return

    if target_user not in online_users:
        send_packet(
            sock,
            CTRL,
            "ERROR target user is offline"
        )
        return

    sender = client_info[sock]

    target_socket = online_users[target_user]

    send_packet(
        target_socket,
        CTRL,
        f"REJECT_FILE {sender} {filename}"
    )

    send_packet(
        sock,
        CTRL,
        "OK"
    )
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

def handle_send_file( sock , filename , sender):
    filepath = os.path.join(
        UPLOAD_DIR,
        filename)
    send_packet(sock,CTRL,f"START_FILE {filename}")

    with open(filepath,"rb") as f:

        chunk_no = 1

        while True:

            chunk = f.read(1024)

            if not chunk:
                break

            send_binary_chunk(
                sock,
                chunk_no,
                chunk)

            chunk_no += 1
    
    send_packet(
        online_users[sender],
        END_FILE,
        "File sent successfully.")

    send_packet(
        sock,
        END_FILE,
        filename)



def handle_accept_file(sock , command):
    parts = command.split(" ", 2)

    if len(parts) < 3:
        send_packet(
            sock,
            CHAT,
            "ERROR invalid CHAT"
        )
        return

    sender = parts[1]
    filename = parts[2]
    
    handle_send_file(sock , filename , sender)

def handle_list_files(sock):
    files_list = ",".join(files.keys())

    if not files_list:
        files_list = "empty"
    send_packet(sock, CTRL,  f"FILES_LIST {files_list}")


def handle_list_users(sock):
    user_list = ",".join(online_users.keys())

    if not user_list:
        user_list = "empty"
    send_packet(sock, CTRL,  f"USER_LIST {user_list}")


def handle_chat(sock, command):

    if sock not in client_info:
        send_packet(
            sock,
            CTRL,
            "ERROR authentication required"
        )
        return

    parts = command.split(" ", 2)

    if len(parts) < 3:
        send_packet(
            sock,
            CHAT,
            "ERROR invalid CHAT"
        )
        return

    target_user = parts[1]
    message = parts[2]

    if target_user not in users:
        send_packet(
            sock,
            CTRL,
            "ERROR target user not found"
        )
        return
    sender = client_info[sock]

    target_socket = online_users[target_user]

    if target_user not in online_users:
        if target_user not in offline_messages :
            offline_messages.setdefault(target_user,[])
        offline_messages[target_user].append((sender,message))
        send_packet(sock , CTRL , "MESSAGE STORED")
        return

    send_packet(
        target_socket,
        CTRL,
        f"FROM_CHAT {sender} {message}"
    )

    send_packet(
        sock,
        CTRL,
        "OK"
    )




def handle_register(sock, command):
    parts = command.split()

    if len(parts) != 3:
        send_packet(sock, CTRL, "ERROR invalid REGISTER")
        return

    username = parts[1]
    password = parts[2]

    if username in users:
        send_packet(
            sock,
            CTRL,
            "ERROR username already exists"
        )
        return
    users[username] = password
    send_packet(sock, CTRL, "OK")






def handle_login(sock, command):
    parts = command.split()

    if len(parts) != 3:
        send_packet(sock, CTRL, "ERROR invalid LOGIN")
        return

    username = parts[1]
    password = parts[2]

    if username not in users:
        send_packet(sock, CTRL, "AUTH_FAILED")
        return

    if users[username] != password:
        send_packet(sock, CTRL, "INCORRECT PASSWORD")
        return

    if username in online_users:
        send_packet(
            sock,
            CTRL,
            "ERROR user already logged in"
        )
        return
    
    if username in offline_messages:        
        for m in offline_messages.get(username, []):
            send_packet(sock , CHAT ,f"FROM_CHAT {m["sender"]} {m["message"]}")
        offline_messages[username].clear()
    online_users[username] = sock
    client_info[sock] = username

    send_packet(sock, CTRL, "AUTH_SUCCESS")



def handle_logout(sock):

    if sock not in client_info:
        send_packet(
            sock,
            CTRL,
            "ERROR authentication required"
        )

        return

    username = client_info[sock]
    del client_info[sock]
    del online_users[username]

    send_packet(sock, CTRL, "OK")



def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(BACKLOG)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    print(f"[SERVER] Listening on {HOST}:{PORT}")
    
    while True:
        client_socket, address = server.accept()
        thread = threading.Thread(target=handle_client, args=(client_socket, address))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

if __name__ == "__main__":
    start_server()
