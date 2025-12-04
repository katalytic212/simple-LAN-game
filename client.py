import socket

SERVER_IP = input("Enter server IP: ")  # Example: 192.168.1.10
PORT = 5000

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((SERVER_IP, PORT))

name = input("Enter your name: ")
client.sendall(name.encode())

print("Connected! Start guessing like: 3,2")

def listen():
    while True:
        try:
            msg = client.recv(1024).decode()
            if not msg:
                break
            print(msg)
        except:
            break

import threading
threading.Thread(target=listen, daemon=True).start()

while True:
    guess = input("")
    client.sendall(guess.encode())
