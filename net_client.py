# net_client.py
import socket, threading, json, pygame

ENC = "utf-8"
latest_state = {"players":{}, "coin":None, "lasers":[], "round_active": False}
my_pid = None

def _send_json(sock, obj):
    sock.sendall(json.dumps(obj, separators=(",",":")).encode(ENC) + b"\n")

def reader(sock):
    buf = bytearray()
    while True:
        data = sock.recv(4096)
        if not data:
            break
        buf.extend(data)
        while True:
            try:
                i = buf.index(0x0A)
            except ValueError:
                break
            line = buf[:i]; del buf[:i+1]
            if not line: 
                continue
            msg = json.loads(line.decode(ENC))
            t = msg.get("type")
            if t == "welcome":
                global my_pid
                my_pid = msg.get("pid")
            elif t == "state":
                latest_state.update(msg)  # shallow is fine for our keys

def connect(host="127.0.0.1", port=50007, name="player"):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    _send_json(sock, {"type":"join","name":name})
    threading.Thread(target=reader, args=(sock,), daemon=True).start()
    return sock

def send_inputs(sock):
    keys = pygame.key.get_pressed()
    _send_json(sock, {
        "type":"input",
        "keys":{
            "up": bool(keys[pygame.K_UP] or keys[pygame.K_w]),
            "down": bool(keys[pygame.K_DOWN] or keys[pygame.K_s]),
            "left": bool(keys[pygame.K_LEFT] or keys[pygame.K_a]),
            "right": bool(keys[pygame.K_RIGHT] or keys[pygame.K_d]),
        }
    })

def send_start(sock):
    _send_json(sock, {"type":"start"})
