import socket
import threading
import random
import time

HOST = ""      # Listen on all LAN interfaces
PORT = 5000

players = {}  # {conn: name}
scores = {}   # {name: score}
banana_pos = (0, 0)

def broadcast(msg):
    for conn in players:
        conn.sendall(msg.encode())

def handle_player(conn):
    global banana_pos

    name = conn.recv(1024).decode().strip()
    players[conn] = name
    scores[name] = 0

    broadcast(f"🟢 {name} joined the Banana Hunt!\n")

    try:
        while True:
            guess = conn.recv(1024).decode().strip()
            if not guess:
                break

            try:
                x, y = map(int, guess.split(","))
            except:
                conn.sendall("Invalid guess! Use: number,number\n".encode())
                continue

            if (x, y) == banana_pos:
                scores[name] += 1
                broadcast(f"🍌 {name} found the BANANA! Score: {scores[name]}\n")

                if scores[name] >= 5:
                    broadcast(f"🏆 {name} WINS THE BANANA HUNT! 🏆\n")
                    broadcast("Server closing...\n")
                    time.sleep(2)
                    exit()

                banana_pos = (random.randint(0, 4), random.randint(0, 4))
                broadcast(f"A new banana has appeared somewhere!\n")
            else:
                conn.sendall("❌ Nope! Wrong spot.\n".encode())

    except:
        pass
    finally:
        broadcast(f"🔴 {players[conn]} left the game.\n")
        del scores[players[conn]]
        del players[conn]
        conn.close()


def banana_spawner():
    global banana_pos
    while True:
        banana_pos = (random.randint(0, 4), random.randint(0, 4))
        broadcast("\n🍌 A new banana has appeared!\nGuess a coordinate (0-4,0-4):\n")
        time.sleep(10)


def main():
    print(f"Starting Banana Hunt Server on port {PORT}…")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()

    threading.Thread(target=banana_spawner, daemon=True).start()

    while True:
        conn, addr = server.accept()
        print(f"{addr} connected.")
        threading.Thread(target=handle_player, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    main()
