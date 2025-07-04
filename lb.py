import socket
import threading

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
backend_locks = []

# === Initialize backend connections ===
def setup_backend_connections():
    global backend_sockets, backend_locks
    for ip, port in BACKEND_SERVERS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, port))
        backend_sockets.append(s)
        backend_locks.append(threading.Lock())

# === Round robin server selection ===
def choose_next_server():
    global next_server_index
    index_lock.acquire()
    i = next_server_index
    next_server_index = (next_server_index + 1) % len(BACKEND_SERVERS)
    index_lock.release()
    return i

# === Handle one client request ===
def handle_client(client_socket):
    try:
        request_data = client_socket.recv(1024)
        if not request_data:
            client_socket.close()
            return

        server_index = choose_next_server()
        backend_socket = backend_sockets[server_index]
        backend_lock = backend_locks[server_index]

        # Lock the socket so only one thread can use it at a time
        backend_lock.acquire()

        try:
            backend_socket.sendall(request_data)

            response = backend_socket.recv(4096)
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

    lb_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lb_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
