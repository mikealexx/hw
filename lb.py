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
# =====================

# === Round-robin index ===
next_server_index = 0
server_lock = threading.Lock()
# =========================

# === Backend Server Sockets ===
server1_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server1_socket.connect(BACKEND_SERVERS[0])

server2_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server2_socket.connect(BACKEND_SERVERS[1])

server3_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server3_socket.connect(BACKEND_SERVERS[2])

backend_sockets = [
    server1_socket,
    server2_socket,
    server3_socket
]
# =============================


def choose_next_server():
    global next_server_index
    server_lock.acquire()
    server_index = next_server_index
    next_server_index = (next_server_index + 1) % len(BACKEND_SERVERS)
    server_lock.release()
    return server_index


def handle_client(client_socket):
    try:
        request_data = client_socket.recv(1024)
        if not request_data:
            client_socket.close()
            return

        server_index = choose_next_server()

        backend_sockets[server_index].sendall(request_data)

        while True:
            response = backend_sockets[server_index].recv(1024)
            if not response:
                break
            client_socket.sendall(response)

    except Exception as e:
        print("[ERROR] {}".format(e))

    finally:
        client_socket.close()


def start_load_balancer():
    print("Starting Load Balancer on {}:{}".format(LB_HOST, LB_PORT))

    lb_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lb_socket.bind((LB_HOST))
    lb_socket.listen()

    try:
        while True:
            client_socket, addr = lb_socket.accept()
            print("Connection from {}:{}".format(addr[0], addr[1]))
            t = threading.Thread(target=handle_client, args=(client_socket))
            t.daemon = True
            t.start()
    except KeyboardInterrupt:
        print("Shutting down.")
    finally:
        lb_socket.close()
        for sock in backend_sockets:
            sock.close()


if __name__ == "__main__":
    start_load_balancer()
