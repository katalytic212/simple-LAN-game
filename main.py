import socket
import threading
import tkinter as tk
import random
import time
import math

# Configurações
MAP_WIDTH, MAP_HEIGHT = 800, 600
PLAYER_SIZE = 30
COIN_SIZE = 20
BULLET_SIZE = 8
SPEED = 10
BULLET_SPEED = 15
GAME_TIME = 60

DISCOVERY_PORT = 5001
GAME_PORT = 5000

def sendmsg(conn, msg):
    try:
        conn.send((msg + ";").encode())
    except:
        pass

class Game:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Battle Game")
        self.root.geometry(f"{MAP_WIDTH}x{MAP_HEIGHT}")
        self.root.minsize(MAP_WIDTH, MAP_HEIGHT)

        # Menu
        self.menu_frame = tk.Frame(self.root)
        self.menu_frame.pack(pady=50)
        tk.Label(self.menu_frame, text="Escolha o modo", font=("Arial", 18)).pack(pady=10)
        tk.Button(self.menu_frame, text="Host", width=20, command=self.start_host).pack(pady=5)
        tk.Button(self.menu_frame, text="Cliente", width=20, command=self.start_client).pack(pady=5)

        # Canvas e objetos do jogo (serão criados só quando iniciar o jogo)
        self.canvas = None
        self.p1 = None
        self.p2 = None
        self.coin = None
        self.text = None
        self.bullets = []

        # Host/Cliente
        self.is_host = False
        self.conn = None  # conexão TCP host <-> cliente
        self.sock = None  # socket cliente TCP

        # Placar e tempo
        self.score1 = 0
        self.score2 = 0
        self.time_left = GAME_TIME

        # Movimento
        self.keys_pressed = set()
        self.shoot_direction = (0, -1)
        self.root.bind("<KeyPress>", self.key_press)
        self.root.bind("<KeyRelease>", self.key_release)
        self.root.bind("<space>", self.shoot)

        self.game_started = False

        self.root.mainloop()

    # --- Menu ---
    def start_host(self):
        self.is_host = True
        self.menu_frame.pack_forget()
        self.status_label = tk.Label(self.root, text="Aguardando cliente...")
        self.status_label.pack()
        threading.Thread(target=self.broadcast_host, daemon=True).start()
        threading.Thread(target=self.start_server, daemon=True).start()

    def start_client(self):
        self.is_host = False
        self.menu_frame.pack_forget()
        self.status_label = tk.Label(self.root, text="Procurando host...")
        self.status_label.pack()
        threading.Thread(target=self.discover_host, daemon=True).start()

    # --- Teclado ---
    def key_press(self, event):
        self.keys_pressed.add(event.keysym)
        if event.keysym in ["Up", "Down", "Left", "Right"]:
            dx = dy = 0
            if "Up" in self.keys_pressed:
                dy = -1
            if "Down" in self.keys_pressed:
                dy = 1
            if "Left" in self.keys_pressed:
                dx = -1
            if "Right" in self.keys_pressed:
                dx = 1
            if dx != 0 or dy != 0:
                norm = math.sqrt(dx * dx + dy * dy)
                self.shoot_direction = (dx / norm, dy / norm)

    def key_release(self, event):
        self.keys_pressed.discard(event.keysym)

    # --- Host: broadcast UDP para discovery ---
    def broadcast_host(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while not self.game_started:
            udp.sendto(b"GAME_HOST_AVAILABLE", ("255.255.255.255", DISCOVERY_PORT))
            time.sleep(1)
        udp.close()

    # --- Host TCP ---
    def start_server(self):
        s = socket.socket()
        s.bind(("0.0.0.0", GAME_PORT))
        s.listen(1)
        self.conn, addr = s.accept()
        self.status_label.config(text=f"Cliente conectado: {addr}")
        threading.Thread(target=self.receive, daemon=True).start()

        # Botão iniciar só aparece após cliente conectado
        self.start_button = tk.Button(self.root, text="Iniciar Jogo", command=self.host_start_game)
        self.start_button.pack(pady=5)

    # --- Cliente discovery UDP ---
    def discover_host(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.bind(("", DISCOVERY_PORT))
        while True:
            data, addr = udp.recvfrom(1024)
            if data == b"GAME_HOST_AVAILABLE":
                self.host_ip = addr[0]
                self.status_label.config(text=f"Host encontrado: {self.host_ip}")
                self.connect_button = tk.Button(self.root, text="Conectar", command=self.connect_to_host)
                self.connect_button.pack(pady=5)
                udp.close()
                break

    def connect_to_host(self):
        try:
            self.sock = socket.socket()
            self.sock.connect((self.host_ip, GAME_PORT))
            self.status_label.config(text="Conectado. Aguarde início do jogo...")
            self.connect_button.destroy()
            threading.Thread(target=self.receive, daemon=True).start()
        except Exception as e:
            self.status_label.config(text=f"Falha ao conectar: {e}")

    # --- Receber mensagens TCP ---
    def receive(self):
        buffer = ""
        s = self.conn if self.is_host else self.sock
        while True:
            try:
                data = s.recv(1024)
                if not data:
                    break  # conexão fechada
                buffer += data.decode()
                while ";" in buffer:
                    part, buffer = buffer.split(";", 1)
                    self.handle_message(part)
            except:
                break
        # conexão perdida
        self.root.quit()

    # --- Manipular mensagens ---
    def handle_message(self, msg):
        parts = msg.split()
        if not parts:
            return
        cmd = parts[0]
        if cmd == "START":
            # inicia o jogo no cliente
            self.root.after(0, self.start_game)
        elif cmd in ["HOSTMOVE", "MOVE"]:
            dx = int(parts[1])
            dy = int(parts[2])
            target = self.p1 if cmd == "HOSTMOVE" else self.p2
            if target:
                self.canvas.move(target, dx, dy)
        elif cmd == "COIN":
            x = int(parts[1])
            y = int(parts[2])
            self.spawn_coin(x, y)
        elif cmd == "SCORE":
            self.score1 = int(parts[1])
            self.score2 = int(parts[2])
            self.update_score_text()
        elif cmd == "TIME":
            self.time_left = int(parts[1])
            self.update_score_text()
        elif cmd == "BULLET":
            x = float(parts[1])
            y = float(parts[2])
            dx = float(parts[3])
            dy = float(parts[4])
            self.create_bullet(x, y, dx, dy)
        elif cmd == "END":
            self.canvas.create_text(MAP_WIDTH // 2, MAP_HEIGHT // 2, text="FIM", fill="white", font=("Arial", 32))

    # --- Host inicia o jogo, envia START para cliente ---
    def host_start_game(self):
        if self.is_host and self.conn:
            sendmsg(self.conn, "START")
        self.game_started = True
        self.status_label.pack_forget()
        if hasattr(self, "start_button"):
            self.start_button.pack_forget()
        self.start_game()

    # --- Start game: criar canvas e objetos ---
    def start_game(self):
        # Cria canvas se não existir
        if not self.canvas:
            self.canvas = tk.Canvas(self.root, width=MAP_WIDTH, height=MAP_HEIGHT, bg="black")
            self.canvas.pack()

        self.setup_game_objects()
        if self.is_host:
            self.root.after(1000, self.update_timer)
        self.root.after(30, self.update)

    def setup_game_objects(self):
        if self.p1:
            self.canvas.delete(self.p1)
        if self.p2:
            self.canvas.delete(self.p2)
        if self.coin:
            self.canvas.delete(self.coin)
        for b in self.bullets:
            self.canvas.delete(b['id'])
        self.bullets.clear()

        self.p1 = self.canvas.create_rectangle(50, 50, 50 + PLAYER_SIZE, 50 + PLAYER_SIZE, fill="red")
        self.p2 = self.canvas.create_rectangle(200, 200, 200 + PLAYER_SIZE, 200 + PLAYER_SIZE, fill="blue")
        if self.text:
            self.canvas.delete(self.text)
        self.text = self.canvas.create_text(MAP_WIDTH // 2, 20, fill="white", font=("Arial", 16),
                                            text=f"P1:{self.score1} P2:{self.score2} Tempo:{self.time_left}")
        # Spawn inicial da moeda
        if self.is_host:
            self.spawn_coin()
        else:
            # Cliente só mostra quando recebe a posição da moeda do host
            pass

    def spawn_coin(self, x=None, y=None):
        if self.coin:
            self.canvas.delete(self.coin)
        if x is None:
            x = random.randint(0, MAP_WIDTH - COIN_SIZE)
        if y is None:
            y = random.randint(0, MAP_HEIGHT - COIN_SIZE)
        self.coin = self.canvas.create_oval(x, y, x + COIN_SIZE, y + COIN_SIZE, fill="yellow")
        if self.is_host and self.conn:
            sendmsg(self.conn, f"COIN {x} {y}")
            sendmsg(self.conn, f"SCORE {self.score1} {self.score2}")

    def update_score_text(self):
        if self.text:
            self.canvas.itemconfig(self.text,
                                   text=f"P1:{self.score1} P2:{self.score2} Tempo:{self.time_left}")

    def update_timer(self):
        if self.time_left > 0:
            self.time_left -= 1
            self.update_score_text()
            if self.conn:
                sendmsg(self.conn, f"TIME {self.time_left}")
            self.root.after(1000, self.update_timer)
        else:
            self.canvas.create_text(MAP_WIDTH // 2, MAP_HEIGHT // 2, text="FIM", fill="white", font=("Arial", 32))
            if self.conn:
                sendmsg(self.conn, "END")

    def update(self):
        if not self.canvas:
            return
        dx = dy = 0
        keys = self.keys_pressed
        if self.is_host:
            if "w" in keys:
                dy -= SPEED
            if "s" in keys:
                dy += SPEED
            if "a" in keys:
                dx -= SPEED
            if "d" in keys:
                dx += SPEED
            if self.p1 and (dx != 0 or dy != 0):
                self.canvas.move(self.p1, dx, dy)
                if self.conn:
                    sendmsg(self.conn, f"HOSTMOVE {dx} {dy}")
        else:
            if "Up" in keys:
                dy -= SPEED
            if "Down" in keys:
                dy += SPEED
            if "Left" in keys:
                dx -= SPEED
            if "Right" in keys:
                dx += SPEED
            if self.p2 and (dx != 0 or dy != 0):
                self.canvas.move(self.p2, dx, dy)
                if self.sock:
                    try:
                        self.sock.send(f"MOVE {dx} {dy};".encode())
                    except:
                        pass

        # Coleta moedas host
        if self.is_host and self.coin:
            x1, y1, x2, y2 = self.canvas.coords(self.p1)
            x3, y3, x4, y4 = self.canvas.coords(self.p2)
            cx, cy, cx2, cy2 = self.canvas.coords(self.coin)
            if x1 < cx2 and x2 > cx and y1 < cy2 and y2 > cy:
                self.score1 += 1
                self.spawn_coin()
            elif x3 < cx2 and x4 > cx and y3 < cy2 and y4 > cy:
                self.score2 += 1
                self.spawn_coin()
            if self.conn:
                sendmsg(self.conn, f"SCORE {self.score1} {self.score2}")

        # Atualiza balas
        for bullet in self.bullets[:]:
            self.canvas.move(bullet['id'], bullet['dx'], bullet['dy'])
            bx, by, bx2, by2 = self.canvas.coords(bullet['id'])
            target_coords = self.canvas.coords(self.p2 if bullet['owner'] == 1 else self.p1)
            if bx < target_coords[2] and bx2 > target_coords[0] and by < target_coords[3] and by2 > target_coords[1]:
                # Dano ao jogador atingido
                if bullet['owner'] == 1:
                    self.score2 = max(0, self.score2 - 1)
                else:
                    self.score1 = max(0, self.score1 - 1)
                self.canvas.delete(bullet['id'])
                self.bullets.remove(bullet)
                if self.is_host and self.conn:
                    sendmsg(self.conn, f"SCORE {self.score1} {self.score2}")
            elif bx < 0 or by < 0 or bx2 > MAP_WIDTH or by2 > MAP_HEIGHT:
                self.canvas.delete(bullet['id'])
                self.bullets.remove(bullet)

        self.update_score_text()
        self.root.after(30, self.update)

    def shoot(self, event):
        if not self.canvas:
            return
        owner = 1 if self.is_host else 2
        player = self.p1 if owner == 1 else self.p2
        x1, y1, x2, y2 = self.canvas.coords(player)
        dx, dy = self.shoot_direction
        dx *= BULLET_SPEED
        dy *= BULLET_SPEED
        bullet_id = self.canvas.create_oval(x1 + PLAYER_SIZE // 2 - BULLET_SIZE // 2,
                                            y1 + PLAYER_SIZE // 2 - BULLET_SIZE // 2,
                                            x1 + PLAYER_SIZE // 2 + BULLET_SIZE // 2,
                                            y1 + PLAYER_SIZE // 2 + BULLET_SIZE // 2, fill="white")
        self.bullets.append({'id': bullet_id, 'dx': dx, 'dy': dy, 'owner': owner})
        if self.is_host and self.conn:
            sendmsg(self.conn, f"BULLET {x1 + PLAYER_SIZE // 2} {y1 + PLAYER_SIZE // 2} {dx} {dy}")

    def create_bullet(self, x, y, dx, dy):
        bullet_id = self.canvas.create_oval(x - BULLET_SIZE // 2, y - BULLET_SIZE // 2,
                                            x + BULLET_SIZE // 2, y + BULLET_SIZE // 2, fill="white")
        self.bullets.append({'id': bullet_id, 'dx': dx, 'dy': dy, 'owner': 2})


Game()
