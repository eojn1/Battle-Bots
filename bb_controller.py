'''
Battle Bots - laptop controller
QUB Robotics Society

Setup
  1. Power the router ESP32 and the robot.
  2. Join the "QUBRobots" WiFi on this laptop.

  3. Pick your bot: set BOT_NUMBER below, or run
         python battle_bot_controller.py 3
     Bot N is the robot whose ROBOT_IP is 192.168.1.N.

Controls
  Drive   W A S D, the arrow keys, or click / tap the on-screen arrows
  Stop    Space, Esc, or the STOP button


'''

import socket
import sys
import tkinter as tk

#Settings
BOT_NUMBER = 1
BASE_IP = "192.168.1."    
PORT = 42069
NUM_BOTS = 6
HEARTBEAT_MS = 100          

SWAP_TURN = True

#Colours
BG = "#ffffff"
BUTTON = "#e5e7eb"
ARROW = "#374151"
ACCENT = "#ff3131"
ACCENT_ARROW = "#ffffff"
TEXT = "#111827"
MUTED = "#6b7280"
STOP_BG = "#374151"

DIRS = ("up", "down", "left", "right")
KEYMAP = {
    "up": "up", "w": "up",
    "down": "down", "s": "down",
    "left": "left", "a": "left",
    "right": "right", "d": "right",
}
SHAPES = {
    "up":    ((0, -0.9), (1, 0.8), (-1, 0.8)),
    "down":  ((0, 0.9), (1, -0.8), (-1, -0.8)),
    "left":  ((-0.9, 0), (0.8, 1), (0.8, -1)),
    "right": ((0.9, 0), (-0.8, 1), (-0.8, -1)),
}
STOP_PACKET = bytes((0, 0, 0, 0))


class ArrowButton:
    """A flat square button with a triangle on it."""

    def __init__(self, parent, direction, on_press, on_release):
        self.direction = direction
        self.active = False
        self.cv = tk.Canvas(parent, bg=BUTTON, highlightthickness=0,
                            bd=0, cursor="hand2", width=120, height=120)
        self.cv.bind("<Configure>", lambda e: self.draw())
        self.cv.bind("<ButtonPress-1>", lambda e: on_press())
        self.cv.bind("<ButtonRelease-1>", lambda e: on_release())

    def set_active(self, on):
        if on != self.active:
            self.active = on
            self.draw()

    def draw(self):
        cv = self.cv
        cv.delete("all")
        cv.config(bg=ACCENT if self.active else BUTTON)
        w, h = cv.winfo_width(), cv.winfo_height()
        s = min(w, h) * 0.22
        pts = []
        for x, y in SHAPES[self.direction]:
            pts += [w / 2 + x * s, h / 2 + y * s]
        cv.create_polygon(*pts, fill=ACCENT_ARROW if self.active else ARROW,
                          outline="")


class App:
    def __init__(self, root, bot):
        self.root = root
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.bot = bot
        self.held = {d: set() for d in DIRS}
        self.send_ok = True
        self.build()
        self.bind_events()
        self.refresh()
        self.tick()

    #UI
    def build(self):
        r = self.root
        r.title("Battle Bots - Bot %d" % self.bot)
        r.configure(bg=BG)
        r.geometry("400x520")
        r.minsize(300, 400)

        head = tk.Frame(r, bg=BG)
        head.pack(fill="x", padx=24, pady=(22, 0))
        tk.Label(head, text="Battle Bots", font=("Segoe UI", 24, "bold"),
                 fg=TEXT, bg=BG).pack(anchor="w")
        tk.Frame(head, bg=ACCENT, height=3, width=44).pack(anchor="w", pady=(2, 6))
        sub = tk.Frame(head, bg=BG)
        sub.pack(fill="x")
        tk.Label(sub, text="QUB Robotics Society", font=("Segoe UI", 10),
                 fg=MUTED, bg=BG).pack(side="left")
        tk.Label(sub, text="Bot %d" % self.bot, font=("Segoe UI", 12, "bold"),
                 fg=ACCENT, bg=BG).pack(side="right")

        pad = tk.Frame(r, bg=BG)
        pad.pack(expand=True, fill="both", padx=24, pady=18)
        for c in range(3):
            pad.columnconfigure(c, weight=1, uniform="col")
        for rr in range(2):
            pad.rowconfigure(rr, weight=1, uniform="row")
        cells = {"up": (0, 1), "left": (1, 0), "down": (1, 1), "right": (1, 2)}
        self.dir_btns = {}
        for d, (rr, c) in cells.items():
            b = ArrowButton(pad, d,
                            on_press=lambda d=d: self.press(d, "mouse"),
                            on_release=lambda d=d: self.release(d, "mouse"))
            b.cv.grid(row=rr, column=c, sticky="nsew", padx=4, pady=4)
            self.dir_btns[d] = b

        stop = tk.Label(r, text="STOP", font=("Segoe UI", 16, "bold"),
                        bg=STOP_BG, fg="white", pady=12, cursor="hand2")
        stop.pack(fill="x", padx=28, pady=(0, 10))
        stop.bind("<Button-1>", lambda e: self.stop_all())

        self.status = tk.Label(r, text="", font=("Segoe UI", 10),
                               bg=BG, fg=ACCENT, height=1)
        self.status.pack(pady=(0, 14))

    def refresh(self):
        for d, b in self.dir_btns.items():
            b.set_active(bool(self.held[d]))
        self.refresh_status()

    def refresh_status(self):
        if self.send_ok:
            self.status.config(text="")
        else:
            self.status.config(
                text="Can't reach the bots. Join the QUBRobots WiFi.")

    #Events
    def bind_events(self):
        r = self.root
        r.bind("<KeyPress>", self.on_key_press)
        r.bind("<KeyRelease>", self.on_key_release)
        r.bind("<FocusOut>", self.on_focus_out)
        r.protocol("WM_DELETE_WINDOW", self.close)
        r.focus_force()

    @staticmethod
    def keyname(e):
        k = e.keysym.lower()
        if k.startswith("kp_"):
            k = k[3:]
        return k

    def on_key_press(self, e):
        k = self.keyname(e)
        if k in KEYMAP:
            self.press(KEYMAP[k], "key:" + k)
        elif k in ("space", "escape"):
            self.stop_all()

    def on_key_release(self, e):
        k = self.keyname(e)
        if k in KEYMAP:
            self.release(KEYMAP[k], "key:" + k)

    def on_focus_out(self, e):
        if e.widget is self.root:
            self.stop_all()

    #Actions
    def press(self, d, src):
        self.held[d].add(src)
        self.refresh()
        self.send()

    def release(self, d, src):
        self.held[d].discard(src)
        self.refresh()
        self.send()

    def stop_all(self):
        for d in DIRS:
            self.held[d].clear()
        self.refresh()
        self.send()

    def close(self):
        for _ in range(3):
            self.send(STOP_PACKET)
        self.root.destroy()

    #Network
    def packet(self):
        up, down, left, right = (bool(self.held[d]) for d in DIRS)
        if up and down:
            up = down = False
        if left and right:
            left = right = False
        slot_a, slot_b = (right, left) if SWAP_TURN else (left, right)
        return bytes((up, down, slot_a, slot_b))

    def send(self, pkt=None):
        pkt = self.packet() if pkt is None else pkt
        try:
            self.sock.sendto(pkt, (BASE_IP + str(self.bot), PORT))
            return True
        except OSError:
            return False

    def tick(self):
        ok = self.send()
        if ok != self.send_ok:
            self.send_ok = ok
            self.refresh_status()
        self.root.after(HEARTBEAT_MS, self.tick)


def main():
    bot = BOT_NUMBER
    if len(sys.argv) > 1:
        try:
            bot = int(sys.argv[1].split(".")[-1])   
        except ValueError:
            pass
    if not 1 <= bot <= NUM_BOTS:
        sys.exit("Bot number must be between 1 and %d" % NUM_BOTS)
    root = tk.Tk()
    App(root, bot)
    root.mainloop()


if __name__ == "__main__":
    main()
