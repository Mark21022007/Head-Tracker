import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow C++ warnings
os.environ['GLOG_minloglevel'] = '2'      # Suppress MediaPipe glog warnings
import cv2
import time
import argparse
import json
import threading
import tkinter as tk
from tkinter import ttk
import numpy as np
from tracker import PastorTracker
from ptz_controller import PTZController
import ctypes
from PIL import Image

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "camera_ip": "192.168.38.150",
    "camera_port": 52381,
    "camera_stream": "1",
    "inner_deadzone": 0.03,
    "outer_deadzone": 0.15,
    "target_x": 0.5,
    "target_y": 0.4,
    "command_interval": 0.1,
    "manual_pan_speed": 4,
    "manual_tilt_speed": 3,
    "manual_zoom_speed": 3,
    "key_bindings": {
        "move_up": {"type": "keyboard", "code": 119, "name": "W"},
        "move_down": {"type": "keyboard", "code": 115, "name": "S"},
        "move_left": {"type": "keyboard", "code": 97, "name": "A"},
        "move_right": {"type": "keyboard", "code": 100, "name": "D"},
        "zoom_in": {"type": "keyboard", "code": 122, "name": "Z"},
        "zoom_out": {"type": "keyboard", "code": 120, "name": "X"},
        "toggle_auto": {"type": "keyboard", "code": 116, "name": "T"},
        "stop": {"type": "keyboard", "code": 32, "name": "Space"}
    }
}

config_data = {}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in config:
                        config[k] = v
                # Migrate key bindings if they don't exist
                if "key_bindings" not in config:
                    config["key_bindings"] = DEFAULT_CONFIG["key_bindings"].copy()
                else:
                    for action, binding in DEFAULT_CONFIG["key_bindings"].items():
                        if action not in config["key_bindings"]:
                            config["key_bindings"][action] = binding.copy()
                return config
        except Exception as e:
            print(f"Error loading config, using defaults: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

# Global mouse variables
mouse_x, mouse_y = -1, -1
settings_clicked = False
btn_bounds = (0, 0, 0, 0)  # (x1, y1, x2, y2)
settings_window_open = False
settings_window_ref = None

MOUSE_DOWN_EVENTS = {
    1: cv2.EVENT_LBUTTONDOWN,
    2: cv2.EVENT_MBUTTONDOWN,
    3: cv2.EVENT_RBUTTONDOWN
}

MOUSE_UP_EVENTS = {
    1: cv2.EVENT_LBUTTONUP,
    2: cv2.EVENT_MBUTTONUP,
    3: cv2.EVENT_RBUTTONUP
}

def open_settings_gui(on_save_callback):
    global settings_window_open, settings_window_ref
    if settings_window_open:
        try:
            if settings_window_ref:
                settings_window_ref.lift()
                settings_window_ref.focus_force()
        except Exception:
            pass
        return
        
    settings_window_open = True
    
    def run_gui():
        global settings_window_open, settings_window_ref
        try:
            root = tk.Tk()
            settings_window_ref = root
            root.title("Pastor Tracker Settings")
            root.configure(bg="#0F172A")
            root.geometry("560x700")
            root.resizable(False, False)
            
            # Keep on top initially to avoid getting hidden behind OpenCV window
            root.attributes('-topmost', True)
            root.after(1000, lambda: root.attributes('-topmost', False))
            
            title_lbl = tk.Label(root, text="Pastor Tracker Settings", font=("Segoe UI", 16, "bold"), bg="#0F172A", fg="#F8FAFC")
            title_lbl.pack(pady=(20, 10))
            
            # --- Scrollable Container ---
            canvas = tk.Canvas(root, bg="#0F172A", highlightthickness=0)
            
            # Style the vertical scrollbar to fit dark theme
            try:
                style = ttk.Style()
                style.theme_use('clam')
                style.configure("Vertical.TScrollbar", gripcount=0, background="#1E293B", troughcolor="#0F172A", bordercolor="#0F172A", arrowcolor="#94A3B8")
            except Exception:
                pass
                
            scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
            
            form_frame = tk.Frame(canvas, bg="#0F172A")
            
            form_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas_frame = canvas.create_window((0, 0), window=form_frame, anchor="nw", width=520)
            
            def on_canvas_configure(event):
                canvas.itemconfig(canvas_frame, width=event.width)
            canvas.bind("<Configure>", on_canvas_configure)
            
            canvas.configure(yscrollcommand=scrollbar.set)
            

            
            def on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind_all("<MouseWheel>", on_mousewheel)
            
            def cleanup_mousewheel(event=None):
                try:
                    canvas.unbind_all("<MouseWheel>")
                except Exception:
                    pass
            root.bind("<Destroy>", cleanup_mousewheel)

            def create_card(parent):
                card = tk.Frame(parent, bg="#1E293B", padx=18, pady=18, highlightthickness=1, highlightbackground="#334155")
                card.pack(fill="x", pady=8, padx=10)
                return card

            def create_section_header(parent, text):
                lbl = tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"), bg="#1E293B", fg="#3B82F6", anchor="w")
                lbl.pack(fill="x", pady=(0, 12))
                
            def create_text_field(parent, label_text, var_value):
                frame = tk.Frame(parent, bg="#1E293B")
                frame.pack(fill="x", pady=6)
                lbl = tk.Label(frame, text=label_text, font=("Segoe UI", 10), bg="#1E293B", fg="#94A3B8", width=22, anchor="w")
                lbl.pack(side="left")
                
                entry = tk.Entry(frame, bg="#0F172A", fg="#F8FAFC", insertbackground="white", bd=0, font=("Segoe UI", 10), highlightthickness=1, highlightbackground="#334155", highlightcolor="#3B82F6")
                entry.insert(0, str(var_value))
                entry.pack(side="right", fill="x", expand=True, ipady=4, padx=(10, 0))
                return entry

            def create_slider(parent, label_text, from_val, to_val, current_val):
                frame = tk.Frame(parent, bg="#1E293B")
                frame.pack(fill="x", pady=6)
                
                lbl_frame = tk.Frame(frame, bg="#1E293B")
                lbl_frame.pack(side="left", fill="y")
                
                lbl = tk.Label(lbl_frame, text=label_text, font=("Segoe UI", 10), bg="#1E293B", fg="#94A3B8", width=22, anchor="w")
                lbl.pack(side="left")
                
                val_lbl = tk.Label(frame, text=str(current_val), font=("Segoe UI", 10, "bold"), bg="#1E293B", fg="#3B82F6", width=3)
                
                def on_slider_change(val):
                    val_lbl.config(text=str(int(float(val))))
                
                scale = tk.Scale(frame, from_=from_val, to=to_val, orient="horizontal", bg="#1E293B", fg="#F8FAFC", troughcolor="#0F172A", activebackground="#3B82F6", highlightthickness=0, bd=0, showvalue=False, command=on_slider_change, width=8, sliderlength=15, sliderrelief="flat")
                scale.set(current_val)
                
                val_lbl.pack(side="right")
                scale.pack(side="right", fill="x", expand=True, padx=(0, 10))
                return scale

            def get_action_label(act):
                labels = {
                    "move_up": "Move Up",
                    "move_down": "Move Down",
                    "move_left": "Move Left",
                    "move_right": "Move Right",
                    "zoom_in": "Zoom In (Tele)",
                    "zoom_out": "Zoom Out (Wide)",
                    "toggle_auto": "Toggle Auto-Tracking",
                    "stop": "Stop Camera"
                }
                return labels.get(act, act)
                
            def get_binding_text(bind):
                if not bind:
                    return "None"
                return bind.get("name", "Unknown")

            def create_binding_row(parent, action_key):
                frame = tk.Frame(parent, bg="#1E293B")
                frame.pack(fill="x", pady=6)
                
                lbl = tk.Label(frame, text=get_action_label(action_key) + ":", font=("Segoe UI", 10), bg="#1E293B", fg="#94A3B8", width=18, anchor="w")
                lbl.pack(side="left")
                
                current_bind = config_data["key_bindings"].get(action_key)
                val_lbl = tk.Label(frame, text=get_binding_text(current_bind), font=("Segoe UI", 10, "bold"), bg="#0F172A", fg="#3B82F6", padx=10, pady=4, width=14, anchor="center", highlightthickness=1, highlightbackground="#334155")
                val_lbl.pack(side="left", padx=(0, 10))
                
                def bind_clicked():
                    val_lbl.config(text="Listening...", fg="#10B981", bg="#13231C", highlightbackground="#059669")
                    root.focus_set()
                    
                    def on_key(event):
                        if event.keysym == "Escape":
                            val_lbl.config(text=get_binding_text(config_data["key_bindings"].get(action_key)), fg="#3B82F6", bg="#0F172A", highlightbackground="#334155")
                            cleanup()
                            return
                        
                        code = None
                        name = ""
                        if event.char and len(event.char) == 1 and event.char.isprintable():
                            code = ord(event.char.lower())
                            name = event.char.upper()
                        else:
                            sym = event.keysym
                            if sym == "Up":
                                code, name = 38, "Up Arrow"
                            elif sym == "Down":
                                code, name = 40, "Down Arrow"
                            elif sym == "Left":
                                code, name = 37, "Left Arrow"
                            elif sym == "Right":
                                code, name = 39, "Right Arrow"
                            elif sym == "space":
                                code, name = 32, "Space"
                            elif sym == "Return":
                                code, name = 13, "Enter"
                            else:
                                code, name = event.keycode, sym
                                
                        config_data["key_bindings"][action_key] = {
                            "type": "keyboard",
                            "code": code,
                            "name": name
                        }
                        val_lbl.config(text=name, fg="#3B82F6", bg="#0F172A", highlightbackground="#334155")
                        cleanup()
                        
                    def on_click(event):
                        name = ""
                        if event.num == 1:
                            name = "Mouse Left Click"
                        elif event.num == 2:
                            name = "Mouse Middle Click"
                        elif event.num == 3:
                            name = "Mouse Right Click"
                        else:
                            name = f"Mouse Button {event.num}"
                            
                        config_data["key_bindings"][action_key] = {
                            "type": "mouse",
                            "code": event.num,
                            "name": name
                        }
                        val_lbl.config(text=name, fg="#3B82F6", bg="#0F172A", highlightbackground="#334155")
                        cleanup()
                        
                    def cleanup():
                        root.unbind("<KeyPress>")
                        root.unbind("<Button-1>")
                        root.unbind("<Button-2>")
                        root.unbind("<Button-3>")
                        
                    root.after(100, lambda: [
                        root.bind("<KeyPress>", on_key),
                        root.bind("<Button-1>", on_click),
                        root.bind("<Button-2>", on_click),
                        root.bind("<Button-3>", on_click)
                    ])

                bind_btn = tk.Label(frame, text="Bind", font=("Segoe UI", 9, "bold"), bg="#334155", fg="#F8FAFC", padx=12, pady=4, cursor="hand2")
                bind_btn.pack(side="right")
                bind_btn.bind("<Enter>", lambda e: bind_btn.config(bg="#475569"))
                bind_btn.bind("<Leave>", lambda e: bind_btn.config(bg="#334155"))
                bind_btn.bind("<Button-1>", lambda e: bind_clicked())
            
            # --- Section 1: Connection ---
            card1 = create_card(form_frame)
            create_section_header(card1, "CONNECTION & SOURCE")
            ip_entry = create_text_field(card1, "Camera IP Address:", config_data["camera_ip"])
            port_entry = create_text_field(card1, "VISCA Control Port:", config_data["camera_port"])
            stream_entry = create_text_field(card1, "Camera Stream Index/URL:", config_data["camera_stream"])
            
            # --- Section 2: Manual Control Speeds ---
            card2 = create_card(form_frame)
            create_section_header(card2, "MANUAL SPEED SETTINGS")
            pan_scale = create_slider(card2, "Manual Pan Speed (1-24):", 1, 24, config_data["manual_pan_speed"])
            tilt_scale = create_slider(card2, "Manual Tilt Speed (1-20):", 1, 20, config_data["manual_tilt_speed"])
            zoom_scale = create_slider(card2, "Manual Zoom Speed (1-7):", 1, 7, config_data["manual_zoom_speed"])
            
            # --- Section 3: Auto-Tracking Settings ---
            card3 = create_card(form_frame)
            create_section_header(card3, "AUTO-TRACKING DEADZONES")
            inner_scale = create_slider(card3, "Inner Deadzone (%):", 1, 15, int(config_data["inner_deadzone"] * 100))
            outer_scale = create_slider(card3, "Outer Deadzone (%):", 10, 40, int(config_data["outer_deadzone"] * 100))
            
            # --- Section 4: Key Bindings ---
            card4 = create_card(form_frame)
            create_section_header(card4, "KEY & MOUSE BINDINGS")
            actions_list = ["move_left", "move_right", "move_up", "move_down", "zoom_in", "zoom_out", "toggle_auto", "stop"]
            for action in actions_list:
                create_binding_row(card4, action)
            
            # Error and action buttons pinned to the bottom of the window
            err_lbl = tk.Label(root, text="", font=("Segoe UI", 9), bg="#0F172A", fg="#EF4444")
            btn_frame = tk.Frame(root, bg="#0F172A")
            
            def save_clicked():
                ip = ip_entry.get().strip()
                port_str = port_entry.get().strip()
                stream = stream_entry.get().strip()
                
                if not ip:
                    err_lbl.config(text="Error: IP address cannot be empty")
                    return
                try:
                    port = int(port_str)
                    if port < 1 or port > 65535:
                        raise ValueError()
                except ValueError:
                    err_lbl.config(text="Error: VISCA Port must be a number between 1 and 65535")
                    return
                
                if not stream:
                    err_lbl.config(text="Error: Stream cannot be empty")
                    return
                
                config_data["camera_ip"] = ip
                config_data["camera_port"] = port
                config_data["camera_stream"] = stream
                config_data["manual_pan_speed"] = int(pan_scale.get())
                config_data["manual_tilt_speed"] = int(tilt_scale.get())
                config_data["manual_zoom_speed"] = int(zoom_scale.get())
                config_data["inner_deadzone"] = float(inner_scale.get()) / 100.0
                config_data["outer_deadzone"] = float(outer_scale.get()) / 100.0
                
                # Save key bindings structure as it has already been modified in config_data
                save_config(config_data)
                on_save_callback()
                root.destroy()

            save_btn = tk.Label(btn_frame, text="Save Settings", font=("Segoe UI", 10, "bold"), bg="#22C55E", fg="#FFFFFF", padx=20, pady=8, cursor="hand2")
            save_btn.pack(side="left", padx=10)
            save_btn.bind("<Enter>", lambda e: save_btn.config(bg="#16A34A"))
            save_btn.bind("<Leave>", lambda e: save_btn.config(bg="#22C55E"))
            save_btn.bind("<Button-1>", lambda e: save_clicked())
            
            cancel_btn = tk.Label(btn_frame, text="Cancel", font=("Segoe UI", 10), bg="#334155", fg="#F8FAFC", padx=20, pady=8, cursor="hand2")
            cancel_btn.pack(side="left", padx=10)
            cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg="#475569"))
            cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg="#334155"))
            cancel_btn.bind("<Button-1>", lambda e: root.destroy())

            # Pack the footer elements first so they get priority spacing at the bottom
            btn_frame.pack(side="bottom", pady=15)
            err_lbl.pack(side="bottom", pady=(5, 0))
            
            # Pack the scrollable canvas to expand and fill the remaining space in the middle
            canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=10)
            scrollbar.pack(side="right", fill="y", pady=10)
            
            root.mainloop()
        finally:
            settings_window_open = False
            settings_window_ref = None

    t = threading.Thread(target=run_gui)
    t.daemon = True
    t.start()

def main():
    global config_data
    config_data = load_config()

    parser = argparse.ArgumentParser(description="BirdDog Auto-Tracker")
    parser.add_argument("--ip", type=str, default=config_data["camera_ip"], help="IP address of the BirdDog P400")
    parser.add_argument("--stream", type=str, default=config_data["camera_stream"], help="RTSP URL or Camera Index")
    parser.add_argument("--port", type=int, default=config_data["camera_port"], help="VISCA over IP UDP port")
    args = parser.parse_args()

    # Sync parsed arguments back to config_data
    config_data["camera_ip"] = args.ip
    config_data["camera_port"] = args.port
    config_data["camera_stream"] = args.stream
    save_config(config_data)

    # Initialize tracker and PTZ controller
    tracker = PastorTracker()
    
    active_ip = config_data["camera_ip"]
    active_port = config_data["camera_port"]
    active_stream = config_data["camera_stream"]
    ptz = PTZController(ip=active_ip, port=active_port)

    # If stream is a digit, use it as a device index
    if active_stream.isdigit():
        cap = cv2.VideoCapture(int(active_stream), cv2.CAP_DSHOW)
    else:
        # Otherwise use the RTSP/Video string
        cap = cv2.VideoCapture(active_stream)

    if not cap.isOpened():
        print(f"Error: Could not open video stream {active_stream}")
        return

    print("Starting auto-tracker... Press 'q' to quit.")

    # Tracking parameters loaded from config
    INNER_DEADZONE = config_data["inner_deadzone"]
    OUTER_DEADZONE = config_data["outer_deadzone"]
    TARGET_X = config_data["target_x"]
    TARGET_Y = config_data["target_y"]
    COMMAND_INTERVAL = config_data["command_interval"]

    auto_tracking_active = True
    last_manual_key_time = 0

    last_pan_speed = 0
    last_tilt_speed = 0
    last_pan_dir = 3
    last_tilt_dir = 3
    last_zoom_dir = 3
    
    last_command_time = 0

    # Ensure AppUserModelID is set BEFORE window creation so taskbar groups properly
    try:
        myappid = 'birddog.tracker.app.v2'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    active_mouse_action = None

    def trigger_action(action):
        if action == "move_left":
            ptz.move_left(speed=config_data["manual_pan_speed"])
        elif action == "move_right":
            ptz.move_right(speed=config_data["manual_pan_speed"])
        elif action == "move_up":
            ptz.move_up(speed=config_data["manual_tilt_speed"])
        elif action == "move_down":
            ptz.move_down(speed=config_data["manual_tilt_speed"])
        elif action == "zoom_in":
            ptz.zoom_drive(speed=config_data["manual_zoom_speed"], direction=1)
        elif action == "zoom_out":
            ptz.zoom_drive(speed=config_data["manual_zoom_speed"], direction=2)

    def on_mouse(event, x, y, flags, param):
        nonlocal active_mouse_action, auto_tracking_active
        global mouse_x, mouse_y, settings_clicked
        mouse_x, mouse_y = x, y
        
        if event == cv2.EVENT_LBUTTONDOWN:
            if btn_bounds[0] <= x <= btn_bounds[2] and btn_bounds[1] <= y <= btn_bounds[3]:
                settings_clicked = True
                return
                
        for action, binding in config_data.get("key_bindings", {}).items():
            if binding["type"] == "mouse":
                btn_num = binding["code"]
                if event == MOUSE_DOWN_EVENTS.get(btn_num):
                    auto_tracking_active = False
                    active_mouse_action = action
                    trigger_action(action)
                elif event == MOUSE_UP_EVENTS.get(btn_num):
                    if active_mouse_action == action:
                        ptz.stop()
                        active_mouse_action = None

    # Set up flexible UI window and icon
    window_name = "Pastor Tracker"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.setMouseCallback(window_name, on_mouse)

    config_changed = False
    reconnect_stream = False

    def on_config_saved():
        nonlocal config_changed
        config_changed = True
    
    # Change icon using ctypes for Windows
    try:
        import sys
        
        # Convert PNG to ICO
        icon_png_path = os.path.join("img", "micicon.png")
        icon_ico_path = os.path.join("img", "micicon.ico")
        if os.path.exists(icon_png_path):
            img = Image.open(icon_png_path)
            
            # Crop transparent padding so the icon appears larger
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)
                
            # Make it square and apply rounded corners
            from PIL import ImageDraw
            width, height = img.size
            max_dim = max(width, height)
            
            # Place original image onto a square
            square_img = Image.new('RGBA', (max_dim, max_dim), (0, 0, 0, 0))
            offset = ((max_dim - width) // 2, (max_dim - height) // 2)
            square_img.paste(img, offset)
            
            # Create rounded corner mask
            mask = Image.new('L', (max_dim, max_dim), 0)
            draw = ImageDraw.Draw(mask)
            rad = int(max_dim * 0.15) # 15% corner radius
            draw.rounded_rectangle((0, 0, max_dim, max_dim), radius=rad, fill=255)
            
            # Create final white icon with rounded corners
            final_icon = Image.new('RGBA', (max_dim, max_dim), (255, 255, 255, 255))
            final_icon.paste(square_img, (0, 0), mask=square_img)
            final_icon.putalpha(mask)
            
            final_icon.save(icon_ico_path, format='ICO', sizes=[(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)])
            
            hwnd = ctypes.windll.user32.FindWindowW(None, window_name)
            
            hicon_small = ctypes.windll.user32.LoadImageW(0, os.path.abspath(icon_ico_path), 1, 16, 16, 0x0010)
            hicon_big = ctypes.windll.user32.LoadImageW(0, os.path.abspath(icon_ico_path), 1, 32, 32, 0x0010)
            
            if hwnd:
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon_small) # ICON_SMALL
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon_big) # ICON_BIG
                
                # Also set the class icon to force taskbar update
                GCLP_HICON = -14
                GCLP_HICONSM = -34
                if sys.maxsize > 2**32:
                    ctypes.windll.user32.SetClassLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
                    ctypes.windll.user32.SetClassLongPtrW(hwnd, GCLP_HICON, hicon_big)
                    ctypes.windll.user32.SetClassLongPtrW(hwnd, GCLP_HICONSM, hicon_small)
                else:
                    ctypes.windll.user32.SetClassLongW(hwnd, GCLP_HICON, hicon_big)
                    ctypes.windll.user32.SetClassLongW(hwnd, GCLP_HICONSM, hicon_small)
            
            # Apply to Console window to fix taskbar grouping if run from terminal
            console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if console_hwnd:
                ctypes.windll.user32.SendMessageW(console_hwnd, 0x0080, 0, hicon_small)
                ctypes.windll.user32.SendMessageW(console_hwnd, 0x0080, 1, hicon_big)
    except Exception as e:
        print(f"Could not set window icon: {e}")

    retry_count = 0
    max_retries = 30
    while True:
        if config_changed:
            config_changed = False
            # Check for camera connection updates
            if config_data["camera_ip"] != active_ip or config_data["camera_port"] != active_port:
                print(f"Reconnecting PTZ Controller to {config_data['camera_ip']}:{config_data['camera_port']}...")
                active_ip = config_data["camera_ip"]
                active_port = config_data["camera_port"]
                ptz = PTZController(ip=active_ip, port=active_port)
            # Check for stream source updates
            if config_data["camera_stream"] != active_stream:
                print(f"Switching video stream to {config_data['camera_stream']}...")
                active_stream = config_data["camera_stream"]
                reconnect_stream = True

        if reconnect_stream:
            reconnect_stream = False
            cap.release()
            reconnect_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(reconnect_frame, "Reconnecting to stream...", (120, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
            cv2.imshow(window_name, reconnect_frame)
            cv2.waitKey(500)
            
            if active_stream.isdigit():
                cap = cv2.VideoCapture(int(active_stream), cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(active_stream)
                
            if not cap.isOpened():
                print(f"Error: Could not open stream {active_stream}")
                error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(error_frame, f"Error: Cannot open {active_stream}", (80, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.imshow(window_name, error_frame)
                cv2.waitKey(2000)
                continue

        ret, frame = cap.read()
        if not ret:
            print(f"Failed to grab frame (attempt {retry_count+1}/{max_retries}). Retrying...")
            retry_count += 1
            if retry_count >= max_retries:
                print("Exceeded maximum retries. Exiting...")
                break
            time.sleep(0.5)
            continue
        
        # Reset retry count on successful read
        retry_count = 0

        # Process frame
        annotated_frame, center, person_height = tracker.process_frame(frame)
        
        # Update parameters dynamically from config
        INNER_DEADZONE = config_data["inner_deadzone"]
        OUTER_DEADZONE = config_data["outer_deadzone"]
        TARGET_X = config_data["target_x"]
        TARGET_Y = config_data["target_y"]
        COMMAND_INTERVAL = config_data["command_interval"]

        current_time = time.time()
        
        if auto_tracking_active:
            if center[0] is not None and center[1] is not None:
                # Center coordinates are normalized (0.0 to 1.0)
                cx, cy = center
                
                # Calculate error from the target center
                # Range depends on TARGET_X and TARGET_Y
                error_x = cx - TARGET_X
                error_y = cy - TARGET_Y
                
                pan_speed = 1
                tilt_speed = 1
                pan_dir = 3 # Stop
                tilt_dir = 3 # Stop
                
                # Horizontal (Pan)
                if abs(error_x) > OUTER_DEADZONE:
                    # Fast proportional mapping [OUTER_DEADZONE, 0.5] to speed [5, 14]
                    speed = int(((abs(error_x) - OUTER_DEADZONE) / (0.5 - OUTER_DEADZONE)) * 9 + 5)
                    pan_speed = max(5, min(14, speed))
                    pan_dir = 2 if error_x > 0 else 1
                elif abs(error_x) > INNER_DEADZONE:
                    # Slow proportional mapping [INNER_DEADZONE, OUTER_DEADZONE] to speed [1, 4]
                    speed = int(((abs(error_x) - INNER_DEADZONE) / (OUTER_DEADZONE - INNER_DEADZONE)) * 3 + 1)
                    pan_speed = max(1, min(4, speed))
                    pan_dir = 2 if error_x > 0 else 1
    
                # Vertical (Tilt)
                if abs(error_y) > OUTER_DEADZONE:
                    # Fast proportional mapping [OUTER_DEADZONE, 0.5] reduced (Max 7 instead of 10)
                    speed = int(((abs(error_y) - OUTER_DEADZONE) / (0.5 - OUTER_DEADZONE)) * 4 + 3)
                    tilt_speed = max(3, min(7, speed))
                    tilt_dir = 2 if error_y > 0 else 1
                elif abs(error_y) > INNER_DEADZONE:
                    # Hardware absolute minimum speed
                    tilt_speed = 1 
                    tilt_dir = 2 if error_y > 0 else 1
                        
                zoom_speed = 1
                zoom_dir = 3
                # Auto-zoom disabled to prevent infinite zoom loops when the head/feet get cut off.
                # Use manual controls (Z/X keys) to set your desired zoom level!

                        
                # Send command if time interval has passed
                if current_time - last_command_time > COMMAND_INTERVAL:
                    # Only send if changed or we are actively moving
                    if (pan_dir != 3 or tilt_dir != 3) or (last_pan_dir != 3 or last_tilt_dir != 3):
                        ptz.ptz_drive(pan_speed, tilt_speed, pan_dir, tilt_dir)
                    
                    if zoom_dir != 3 or last_zoom_dir != 3:
                        ptz.zoom_drive(zoom_speed, zoom_dir)
                        
                    last_pan_dir = pan_dir
                    last_tilt_dir = tilt_dir
                    last_zoom_dir = zoom_dir
                    last_command_time = current_time
    
            else:
                # If person lost, stop moving
                if current_time - last_command_time > COMMAND_INTERVAL:
                    if last_pan_dir != 3 or last_tilt_dir != 3 or last_zoom_dir != 3:
                        ptz.stop()
                        last_pan_dir = 3
                        last_tilt_dir = 3
                        last_zoom_dir = 3
                    last_command_time = current_time

        # Draw outer deadzone box
        h, w, _ = annotated_frame.shape
        x1_out = int(w * (TARGET_X - OUTER_DEADZONE))
        y1_out = int(h * (TARGET_Y - OUTER_DEADZONE))
        x2_out = int(w * (TARGET_X + OUTER_DEADZONE))
        y2_out = int(h * (TARGET_Y + OUTER_DEADZONE))
        cv2.rectangle(annotated_frame, (x1_out, y1_out), (x2_out, y2_out), (255, 0, 0), 2)

        # Draw inner deadzone box
        x1_in = int(w * (TARGET_X - INNER_DEADZONE))
        y1_in = int(h * (TARGET_Y - INNER_DEADZONE))
        x2_in = int(w * (TARGET_X + INNER_DEADZONE))
        y2_in = int(h * (TARGET_Y + INNER_DEADZONE))
        cv2.rectangle(annotated_frame, (x1_in, y1_in), (x2_in, y2_in), (0, 255, 0), 2)
        
        # Draw status text
        mode_text = "Auto-Tracking: ON" if auto_tracking_active else "Auto-Tracking: OFF"
        color = (0, 255, 0) if auto_tracking_active else (0, 165, 255) # Green or Orange
        cv2.putText(annotated_frame, mode_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Draw settings button in the top right corner
        h_f, w_f, _ = annotated_frame.shape
        btn_w, btn_h = 110, 35
        btn_x1 = w_f - btn_w - 15
        btn_y1 = 15
        btn_x2 = w_f - 15
        btn_y2 = 15 + btn_h
        
        global btn_bounds
        btn_bounds = (btn_x1, btn_y1, btn_x2, btn_y2)
        
        hover = (btn_x1 <= mouse_x <= btn_x2) and (btn_y1 <= mouse_y <= btn_y2)
        bg_color = (80, 80, 80) if hover else (50, 50, 50)
        border_color = (150, 150, 150) if hover else (100, 100, 100)
        
        cv2.rectangle(annotated_frame, (btn_x1, btn_y1), (btn_x2, btn_y2), bg_color, -1)
        cv2.rectangle(annotated_frame, (btn_x1, btn_y1), (btn_x2, btn_y2), border_color, 1)
        
        btn_text = "Settings"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        (text_w, text_h), _ = cv2.getTextSize(btn_text, font, font_scale, thickness)
        text_x = btn_x1 + (btn_w - text_w) // 2
        text_y = btn_y1 + (btn_h + text_h) // 2
        cv2.putText(annotated_frame, btn_text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        # Show the frame
        cv2.imshow("Pastor Tracker", annotated_frame)

        # Handle keyboard inputs
        key = cv2.waitKey(1) & 0xFF
        if key in [ord('q'), ord('Q')]:
            break
            
        # Check settings button click
        global settings_clicked
        if settings_clicked:
            settings_clicked = False
            open_settings_gui(on_config_saved)

        # Match key to bindings (case-insensitive for characters)
        matched_action = None
        for action, binding in config_data.get("key_bindings", {}).items():
            if binding["type"] == "keyboard":
                bind_code = binding["code"]
                if bind_code is not None:
                    if 97 <= bind_code <= 122: # a-z
                        if key == bind_code or key == (bind_code - 32): # e.g. 'a' or 'A'
                            matched_action = action
                            break
                    else:
                        if key == bind_code:
                            matched_action = action
                            break
                            
        if matched_action:
            if matched_action == "toggle_auto":
                auto_tracking_active = not auto_tracking_active
                if not auto_tracking_active:
                    ptz.stop()
                    last_pan_dir = 3
                    last_tilt_dir = 3
                    last_zoom_dir = 3
            elif matched_action == "stop":
                auto_tracking_active = False
                ptz.stop()
                last_manual_key_time = 0
            else:
                auto_tracking_active = False
                trigger_action(matched_action)
                last_manual_key_time = current_time
            
        # Automatically stop the camera if WASD/ZX key was released
        if not auto_tracking_active and current_time - last_manual_key_time > 0.5 and last_manual_key_time > 0:
            ptz.stop()
            last_manual_key_time = 0

    # Cleanup
    ptz.stop()
    tracker.release()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
