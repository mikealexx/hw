from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from threading import Thread, Lock
from time import time

# === constants ===
LB_HOST = '10.0.0.1'
LB_PORT = 80

BACKEND_SERVERS = [
    ('192.168.0.101', 80),  # serv1 = VIDEO
    ('192.168.0.102', 80),  # serv2 = VIDEO
    ('192.168.0.103', 80)   # serv3 = MUSIC
]

# === sockets ===
backend_sockets = []
backend_socket_locks = []

# === server locks and server loads ===
server_locks = [Lock() for _ in BACKEND_SERVERS]
server_jobs = [0.0 for _ in BACKEND_SERVERS]  # estimated load per server

# === persistent connections ===
def setup_backend_connections():
    for ip, port in BACKEND_SERVERS:
        s = socket(AF_INET, SOCK_STREAM)
        s.connect((ip, port))
        backend_sockets.append(s)
        backend_socket_locks.append(Lock())

# === request parser ===
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

# === cost per server ===
def get_cost(req_type, duration, server_index):
    if req_type == 'music':
        return duration * (2 if server_index in [0, 1] else 1)
    elif req_type == 'video':
        return duration * (1 if server_index in [0, 1] else 3)
    elif req_type == 'picture':
        return duration * (1 if server_index in [0, 1] else 2)
    return float('inf')

# === choose server with min load ===
def choose_server(parsed):
    req_type, duration = parsed
    now = time()
    best_i = 0
    best_estimate = float('inf')

    for i in range(len(BACKEND_SERVERS)):
        cost = get_cost(req_type, duration, i)
        server_locks[i].acquire()
        load = server_jobs[i]
        server_locks[i].release()
        finish_time = max(now, load) + cost
        if finish_time < best_estimate:
            best_estimate = finish_time
            best_i = i

    return best_i, get_cost(req_type, duration, best_i)

# === client thread func ===
def handle_client(client_socket):
    try:
        request_data = client_socket.recv(2)
        if not request_data:
            return

        parsed = parse_request(request_data)

        server_index, cost = choose_server(parsed)

        print("request {} assigned to server {}".format(
            request_data, server_index+1))

        now = time()
        server_locks[server_index].acquire()
        start_time = max(now, server_jobs[server_index])
        server_jobs[server_index] = start_time + cost
        server_locks[server_index].release()

        backend_socket = backend_sockets[server_index]
        backend_lock = backend_socket_locks[server_index]

        backend_lock.acquire()
        try:
            backend_socket.sendall(request_data)
            response = backend_socket.recv(2)
            client_socket.sendall(response)
        finally:
            backend_lock.release()

        server_locks[server_index].acquire()
        server_jobs[server_index] = time()
        server_locks[server_index].release()

    except Exception as e:
        print("[ERROR] {}".format(e))
    finally:
        client_socket.close()

# === Main LB loop ===
def start_load_balancer():
    print("Starting load balancer on {}:{}".format(LB_HOST, LB_PORT))
    setup_backend_connections()

    lb_socket = socket(AF_INET, SOCK_STREAM)
    lb_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    lb_socket.bind((LB_HOST, LB_PORT))
    lb_socket.listen(10)

    try:
        while True:
            client_socket, addr = lb_socket.accept()
            t = Thread(target=handle_client, args=(client_socket,))
            t.setDaemon(True)
            t.start()
    except KeyboardInterrupt:
        print("Shutting down load balancer")
    finally:
        lb_socket.close()
        for sock in backend_sockets:
            sock.close()

if __name__ == "__main__":
    start_load_balancer()
