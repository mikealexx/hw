import socket
import threading

# === Configuration ===
LB_HOST = '10.0.0.1'        # Load balancer IP (client-facing)
LB_PORT = 80              # Listening port

BACKEND_SERVERS = [
    ('192.168.0.101', 80),
    ('192.168.0.102', 80),
    ('192.168.0.103', 80)
]

# === Round-robin index ===
next_server_index = 0
server_lock = threading.Lock()


def choose_next_server():
    global next_server_index
    server_lock.acquire()
    server = BACKEND_SERVERS[next_server_index]
    next_server_index = (next_server_index + 1) % len(BACKEND_SERVERS)
    server_lock.release()
    return server


def handle_client(client_socket):
    try:
        request_data = client_socket.recv(1024)
        if not request_data:
            client_socket.close()
            return

        backend_host, backend_port = choose_next_server()

        backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        backend_socket.connect((backend_host, backend_port))
        backend_socket.sendall(request_data)

        while True:
            response = backend_socket.recv(4096)
            if not response:
                break
            client_socket.sendall(response)

        backend_socket.close()

    except Exception as e:
        print("[ERROR] {}".format(e))

    finally:
        client_socket.close()


def start_load_balancer():
    print("[LB] Starting Load Balancer on {}:{}".format(LB_HOST, LB_PORT))

    lb_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lb_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    lb_socket.bind((LB_HOST, LB_PORT))
    lb_socket.listen(20)

    try:
        while True:
            client_socket, addr = lb_socket.accept()
            print("[LB] Connection from {}".format(addr))
            t = threading.Thread(target=handle_client, args=(client_socket,))
            t.daemon = True
            t.start()
    except KeyboardInterrupt:
        print("[LB] Shutting down.")
    finally:
        lb_socket.close()


if __name__ == "__main__":
    start_load_balancer()
