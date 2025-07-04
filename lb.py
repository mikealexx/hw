import socket as sckt
from socket import socket
import threading
from time import time

# === configs ===
LB_HOST = '10.0.0.1'
LB_PORT = 80

BACKEND_SERVERS = [
    ('192.168.0.101', 80),  # server 1 - video
    ('192.168.0.102', 80),  # server 2 - video
    ('192.168.0.103', 80)   # server 3 - music
]

# === backend sockets ===
backend_sockets = []
backend_socket_locks = []

# === persistent backend connections ===
def setup_backend_connections():
    for ip, port in BACKEND_SERVERS:
        s = socket(sckt.AF_INET, sckt.SOCK_STREAM)
        s.connect((ip, port))
        backend_sockets.append(s)
        backend_socket_locks.append(threading.Lock())

# === serevr load tracking ===
server_free_at = [time(), time(), time()]
server_free_time_locks = [threading.Lock() for _ in BACKEND_SERVERS]

# === request time calculations per server ===
def get_actual_request_time(parsed_data, server_index):
    req_type, duration = parsed_data

    if req_type == 'music':
        return duration * (2 if server_index in [0, 1] else 1)
    elif req_type == 'video':
        return duration * (1 if server_index in [0, 1] else 3)
    elif req_type == 'picture':
        return duration * (1 if server_index in [0, 1] else 2)

    return float('inf')  # fallback

# === choose best server based on loads ===
def choose_next_server(parsed_data):
    now = time()
    estimated_finish_times = []

    for i in range(len(BACKEND_SERVERS)):
        server_time = get_actual_request_time(parsed_data, i)
        with server_free_time_locks[i]:
            available_at = server_free_at[i]
        finish_time = max(now, available_at) + server_time
        estimated_finish_times.append(finish_time)

    best_index = min(range(len(estimated_finish_times)), key=lambda i: estimated_finish_times[i])
    return best_index, estimated_finish_times[best_index]

# === parse requests, retrun (type,time) ===
def parse_request(data):
    if len(data) != 2 or not data[1].isdigit():
        return None

    type_char = data[0]
    duration = int(data[1])

    if type_char == 'M':
        return ('music', duration)
    elif type_char == 'V':
        return ('video', duration)
    elif type_char == 'P':
        return ('picture', duration)

    return None

# === client connection thread func ===
def handle_client(client_socket):
    try:
        request_data = client_socket.recv(2)
        if not request_data:
            return

        parsed = parse_request(request_data)

        server_index, estimated_finish = choose_next_server(parsed)

        # Update the server's expected available time
        with server_free_time_locks[server_index]:
            server_free_at[server_index] = estimated_finish

        backend_socket = backend_sockets[server_index]
        backend_lock = backend_socket_locks[server_index]

        with backend_lock:
            backend_socket.sendall(request_data)
            response = backend_socket.recv(2)
            client_socket.sendall(response)

    except Exception as e:
        print("[ERROR] {}".format(e))

    finally:
        client_socket.close()

# === Main server loop ===
def start_load_balancer():
    print("Starting Load Balancer on {}:{}".format(LB_HOST, LB_PORT))

    setup_backend_connections()

    lb_socket = socket(sckt.AF_INET, sckt.SOCK_STREAM)
    lb_socket.setsockopt(sckt.SOL_SOCKET, sckt.SO_REUSEADDR, 1)
    lb_socket.bind((LB_HOST, LB_PORT))
    lb_socket.listen(10)

    try:
        while True:
            client_socket, addr = lb_socket.accept()
            print("Connection from {}:{}".format(addr[0], addr[1]))
            t = threading.Thread(target=handle_client, args=(client_socket,))
            t.setDaemon(True)
            t.start()

    except KeyboardInterrupt:
        print("Shutting down Load Balancer.")

    finally:
        lb_socket.close()
        for sock in backend_sockets:
            sock.close()


if __name__ == "__main__":
    start_load_balancer()