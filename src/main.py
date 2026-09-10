import time
import network
import socket
import ujson
import math

# ---- M5Stack UIFlow MicroPython ----
from m5stack import lcd

# IMU: intentamos soportar varias APIs de M5Stack
imu_obj = None
try:
    from m5stack import imu
    imu_obj = imu.IMU()
except:
    try:
        from imu import IMU
        imu_obj = IMU()
    except:
        imu_obj = None

# ------------- CONFIG -------------
WIFI_SSID = "GTDM"
WIFI_PASS = "12345678"

MASTER_RX_PORT = 5005   # maestro recibe input del esclavo aquí
SLAVE_RX_PORT  = 5006   # esclavo recibe estado aquí (maestro envía a este puerto)

SLAVE_IP = "192.168.0.124"   

# Pantalla M5Stack (FIRE suele ir en 320x240)
W, H = 320, 240

PADDLE_W = 6
PADDLE_H = 40
BALL_SZ  = 6

# Físicas (px/s)
BALL_VX0 = 160.0
BALL_VYMAX = 140.0

# IMU control
LPF = 0.85
K   = 0.90
DEADBAND = 1.2

# envío estado
SEND_EVERY_MS = 25  # ~40 Hz

# ------------- UTIL -------------
def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)

def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASS)
        t0 = time.ticks_ms()
        while not wlan.isconnected():
            time.sleep_ms(150)
            if time.ticks_diff(time.ticks_ms(), t0) > 15000:
                raise RuntimeError("No conecta a WiFi (timeout)")
    return wlan.ifconfig()[0]

def lcd_text(y, msg):
    lcd.rect(0, y, W, 20, lcd.BLACK, lcd.BLACK)
    lcd.text(10, y+4, msg, lcd.WHITE)

def imu_pitch_deg():
    """
    Pitch aproximado desde acelerómetro:
    pitch = atan2(ax, sqrt(ay^2 + az^2)) * 180/pi
    Intentamos leer accel en distintas APIs.
    """
    if imu_obj is None:
        return 0.0

    ax = ay = az = 0.0

    # UIFlow suele tener getAccelData() o acceleration
    try:
        ax, ay, az = imu_obj.getAccelData()
    except:
        try:
            a = imu_obj.acceleration
            ax, ay, az = a[0], a[1], a[2]
        except:
            try:
                ax, ay, az = imu_obj.acceleration()  # algunos drivers lo exponen así
            except:
                return 0.0

    pitch = math.atan2(ax, math.sqrt(ay*ay + az*az)) * 57.2958
    return pitch

# ------------- JUEGO -------------
p1_y = (H - PADDLE_H) / 2
p2_y = (H - PADDLE_H) / 2

ball_x = W / 2
ball_y = H / 2
ball_vx = BALL_VX0
ball_vy = 60.0

s1 = 0
s2 = 0

pitch0 = 0.0
pitch_f = 0.0

prev_p1y = prev_p2y = prev_bx = prev_by = -1

def reset_ball(direction):
    global ball_x, ball_y, ball_vx, ball_vy
    ball_x = W / 2
    ball_y = H / 2
    ball_vx = BALL_VX0 if direction > 0 else -BALL_VX0
    ball_vy = (time.ticks_ms() % 160) - 80  # pseudo-random simple

def draw_net_and_scores():
    lcd.clear(lcd.BLACK)
    # red
    y = 0
    while y < H:
        lcd.line(W//2, y, W//2, y+4, lcd.DARKGREY)
        y += 10
    draw_scores()

def draw_scores():
    lcd.rect(0, 0, W, 22, lcd.BLACK, lcd.BLACK)
    lcd.text(10, 4, "P1:%d" % s1, lcd.WHITE)
    lcd.text(W-90, 4, "P2:%d" % s2, lcd.WHITE)

def draw_paddle(x, y, color):
    lcd.rect(x, int(y), PADDLE_W, PADDLE_H, color, color)

def draw_ball(x, y, color):
    lcd.rect(int(x), int(y), BALL_SZ, BALL_SZ, color, color)

def calibrate_imu():
    global pitch0, pitch_f
    lcd_text(100, "Calibrando IMU... quieto")
    s = 0.0
    N = 200
    for _ in range(N):
        s += imu_pitch_deg()
        time.sleep_ms(10)
    pitch0 = s / N
    pitch_f = 0.0

def update_p1_from_imu():
    global p1_y, pitch_f
    pitch = imu_pitch_deg() - pitch0
    pitch_f = LPF * pitch_f + (1.0 - LPF) * pitch
    if abs(pitch_f) < DEADBAND:
        pitch_f = 0.0
    p1_y += pitch_f * K
    p1_y = clamp(p1_y, 0, H - PADDLE_H)

def physics(dt):
    global ball_x, ball_y, ball_vx, ball_vy, s1, s2
    global p1_y, p2_y

    ball_x += ball_vx * dt
    ball_y += ball_vy * dt

    # top/bottom
    if ball_y <= 0:
        ball_y = 0
        ball_vy = -ball_vy
    if ball_y >= H - BALL_SZ:
        ball_y = H - BALL_SZ
        ball_vy = -ball_vy

    # paddle left
    if ball_x <= PADDLE_W:
        ball_cy = ball_y + BALL_SZ/2
        p1_cy = p1_y + PADDLE_H/2
        if (ball_cy >= p1_y) and (ball_cy <= p1_y + PADDLE_H):
            ball_x = PADDLE_W
            ball_vx = abs(ball_vx)
            impact = (ball_cy - p1_cy) / (PADDLE_H/2)
            impact = clamp(impact, -1.0, 1.0)
            ball_vy = impact * BALL_VYMAX

    # paddle right
    if ball_x >= W - PADDLE_W - BALL_SZ:
        ball_cy = ball_y + BALL_SZ/2
        p2_cy = p2_y + PADDLE_H/2
        if (ball_cy >= p2_y) and (ball_cy <= p2_y + PADDLE_H):
            ball_x = W - PADDLE_W - BALL_SZ
            ball_vx = -abs(ball_vx)
            impact = (ball_cy - p2_cy) / (PADDLE_H/2)
            impact = clamp(impact, -1.0, 1.0)
            ball_vy = impact * BALL_VYMAX

    # scoring
    if ball_x < -20:
        s2 += 1
        reset_ball(+1)
        draw_net_and_scores()
    if ball_x > W + 20:
        s1 += 1
        reset_ball(-1)
        draw_net_and_scores()

def render():
    global prev_p1y, prev_p2y, prev_bx, prev_by

    # borrar antiguos
    if prev_p1y >= 0: draw_paddle(0, prev_p1y, lcd.BLACK)
    if prev_p2y >= 0: draw_paddle(W - PADDLE_W, prev_p2y, lcd.BLACK)
    if prev_bx  >= 0: draw_ball(prev_bx, prev_by, lcd.BLACK)

    # dibujar nuevos
    draw_paddle(0, p1_y, lcd.WHITE)
    draw_paddle(W - PADDLE_W, p2_y, lcd.WHITE)
    draw_ball(ball_x, ball_y, lcd.WHITE)

    prev_p1y = int(p1_y)
    prev_p2y = int(p2_y)
    prev_bx  = int(ball_x)
    prev_by  = int(ball_y)

    draw_scores()

# ------------- UDP -------------
sock = None
slave_addr = None
seq = 0

def udp_setup():
    global sock, slave_addr
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", MASTER_RX_PORT))
    sock.setblocking(False)
    slave_addr = (SLAVE_IP, SLAVE_RX_PORT)

def recv_from_slave():
    global p2_y
    try:
        data, addr = sock.recvfrom(512)
    except:
        return
    try:
        msg = ujson.loads(data)
    except:
        return
    if msg.get("t") != "inp":
        return
    p2 = msg.get("p2", int(p2_y))
    p2_y = clamp(float(p2), 0, H - PADDLE_H)

def send_state():
    global seq
    msg = {
        "t": "st",
        "seq": seq,
        "p1": int(p1_y),
        "p2": int(p2_y),
        "s1": s1,
        "s2": s2,
        "ball": {"x": int(ball_x), "y": int(ball_y), "vx": int(ball_vx), "vy": int(ball_vy)}
    }
    seq += 1
    try:
        sock.sendto(ujson.dumps(msg), slave_addr)
    except:
        pass

# ------------- MAIN -------------
lcd.clear(lcd.BLACK)
lcd.text(10, 20, "PONG MAESTRO (MicroPython)", lcd.WHITE)

ip = wifi_connect()
lcd.text(10, 50, "IP: %s" % ip, lcd.WHITE)
lcd.text(10, 70, "RX:%d  TX->%s:%d" % (MASTER_RX_PORT, SLAVE_IP, SLAVE_RX_PORT), lcd.WHITE)

calibrate_imu()
draw_net_and_scores()

udp_setup()
reset_ball(+1)

last_ms = time.ticks_ms()
last_send = last_ms

while True:
    now = time.ticks_ms()
    dt_ms = time.ticks_diff(now, last_ms)
    last_ms = now
    if dt_ms < 1:
        dt_ms = 1
    if dt_ms > 50:
        dt_ms = 50
    dt = dt_ms / 1000.0

    recv_from_slave()
    update_p1_from_imu()
    physics(dt)
    render()

    if time.ticks_diff(now, last_send) >= SEND_EVERY_MS:
        send_state()
        last_send = now

    time.sleep_ms(5)
