import socket
import threading

# === Configuration ===
LB_HOST = '10.0.0.1'         # IP on client network
LB_PORT = 80               # Listening port

BACKEND_SERVERS = [
    ('192.168.0.101', 80),
    ('192.168.0.102', 80),
    ('192.168.0.103', 80),
]

# === Global round-robin counter ===
next_server_index = 0
server_lock = threading.Lock()


def choose_next_server():
    global next_server_index
    with server_lock:
        server = BACKEND_SERVERS[next_server_index]
        next_server_index = (next_server_index + 1) % len(BACKEND_SERVERS)
        return server


def handle_client(client_socket):
    try:
        request_data = client_socket.recv(1024)
        if not request_data:
            client_socket.close()
            return

        backend_host, backend_port = choose_next_server()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as backend_socket:
            backend_socket.connect((backend_host, backend_port))
            backend_socket.sendall(request_data)

            # Forward response back to client
            while True:
                response = backend_socket.recv(4096)
                if not response:
                    break
                client_socket.sendall(response)

    except Exception as e:
        print("[ERROR] {}".format(e))

    finally:
        client_socket.close()


def start_load_balancer():
    print("[LB] Starting Load Balancer on {}:{}".format(LB_HOST, LB_PORT))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as lb_socket:
        lb_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lb_socket.bind((LB_HOST, LB_PORT))
        lb_socket.listen(20)

        while True:
            client_socket, addr = lb_socket.accept()
            print(f"[LB] Connection from {addr}")
            threading.Thread(target=handle_client, args=(client_socket,), daemon=True).start()


if __name__ == "__main__":
    start_load_balancer()