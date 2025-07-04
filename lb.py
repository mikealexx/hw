import socket as sckt
from socket import socket
import threading
from time import time

# === Configuration ===
LB_HOST = '10.0.0.1'       # Your LB IP in the client-facing network
LB_PORT = 80               # Listening port (clients connect here)

BACKEND_SERVERS = [
    ('192.168.0.101', 80),
    ('192.168.0.102', 80),
    ('192.168.0.103', 80)
]

# === Global state ===
next_server_index = 0
index_lock = threading.Lock()
backend_sockets = []
backend_socket_locks = []

server_free_at = [time(), time(), time()]
server_free_time_locks = [threading.Lock() for _ in range(len(BACKEND_SERVERS))]

# === Initialize backend connections ===
def setup_backend_connections():
    global backend_sockets, backend_socket_locks
    for ip, port in BACKEND_SERVERS:
        s = socket(sckt.AF_INET, sckt.SOCK_STREAM)
        s.connect((ip, port))
        backend_sockets.append(s)
        backend_socket_locks.append(threading.Lock())

def get_actual_request_time(parsed_data, server_index):
    type = parsed_data[0]
    time = parsed_data[1]

    if type == 'music':
        if server_index == 0:
            return time * 2
        elif server_index == 1:
            return time * 2
        elif server_index == 2:
            return time
        
    elif type == 'video':
        if server_index == 0:
            return time
        elif server_index == 1:
            return time
        else:
            return time * 3
        
    else:
        if server_index == 0:
            return time
        elif server_index == 1:
            return time
        else:
            return time * 2

# === Best wait time server selection ===
def choose_next_server(parsed_data):
    server_times = [
        get_actual_request_time(parsed_data, 0) + server_free_at[0],
        get_actual_request_time(parsed_data, 1) + server_free_at[1],
        get_actual_request_time(parsed_data, 2) + server_free_at[2]
    ]
    return min(range(len(server_times)), key=lambda i: server_times[i]), min(server_times)

def parse_request(request_data):
    type = None
    if request_data[0] == 'M':
        type = 'music'
    elif request_data[0] == 'V':
        type = 'video'
    else:
        type = 'picture'
    return type, int(request_data[1])

# === Handle one client request ===
def handle_client(client_socket):
    try:
        request_data = client_socket.recv(2)
        if not request_data:
            client_socket.close()
            return
        
        server_index, serve_time = choose_next_server(parse_request(request_data))
        server_free_time_locks[server_index].acquire()
        try:
            server_free_at[server_index] = serve_time
        finally:
            server_free_time_locks[server_index].release()

        backend_socket = backend_sockets[server_index]
        backend_lock = backend_socket_locks[server_index]

        # Lock the socket so only one thread can use it at a time
        backend_lock.acquire()

        try:
            backend_socket.sendall(request_data)

            response = backend_socket.recv(2)
            print("response: {}".format(response))
            client_socket.sendall(response)


        except Exception as e:
            print("[ERROR] Backend communication failed: {}".format(e))

        finally:
            backend_lock.release()

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
            t.daemon = True
            t.start()
    except KeyboardInterrupt:
        print("Shutting down.")
    finally:
        lb_socket.close()
        for s in backend_sockets:
            s.close()

if __name__ == "__main__":
    start_load_balancer()
