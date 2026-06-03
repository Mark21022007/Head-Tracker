# 🎥 BirdDog Head-Tracker & Camera Controller

A professional, hardware-integrated Python application that leverages computer vision (**OpenCV** & **MediaPipe Pose**) to perform real-time, automated head-tracking and camera control for **BirdDog PTZ cameras** (e.g., P400 4K, P200) via **VISCA over IP**. 

Equipped with a premium **OLED / Dark Slate Settings Panel**, the application supports dynamic stream switching, dual-deadzone proportional tracking speeds, and customizable keyboard and mouse control bindings.

---

## ✨ Features

### 👤 Smart Auto-Tracking
* **MediaPipe Pose Architecture**: Tracks the subject's posture (head, shoulders, hips) in real-time.
* **Proportional Headroom Offset**: Automatically shifts the frame slightly upward from the neck center to minimize excess headroom, providing a professional and natural camera frame.
* **Proportional Control System**: Leverages a dual-deadzone structure (inner/outer deadzones) to drive smooth, speed-scaled pan and tilt commands, preventing jitter while remaining highly responsive.

### ⌨️ Customizable Keyboard & Mouse Bindings
* **Any-Key Mapping**: Map pan, tilt, zoom, toggle, and stop functions to any standard keyboard key (including Arrows, Space, and Enter).
* **Mouse Event Capture**: Bind controls to standard mouse clicks (Left, Middle, Right click).
* **Momentary Mouse Action**: Mouse-bound manual overrides act as momentary switches (hold mouse button down to move camera; release it to instantly halt camera motion).

### 🔄 Dynamic Reconnection & Fallbacks
* **On-the-fly Hot Reloading**: Changing the camera IP, VISCA port, or stream source in settings instantly reconnects the feed and controls without requiring an application restart.
* **Resilient Threading**: Settings UI runs on a dedicated background thread, ensuring settings adjustments never interrupt or freeze the primary tracking thread.

---

## 🛠️ System Prerequisites

1. **Operating System**: Windows 10 / 11
2. **Python**: Python 3.8 to 3.11
3. **Hardware**:
   - A webcam, capture card, NDI Virtual Input, or BirdDog camera RTSP feed.
   - A network-connected BirdDog PTZ camera configured for VISCA over IP (default port `52381`).

---

## 🚀 Quick Start

### 1. Installation
Clone the repository and install dependencies:
```bash
pip install -r requirements.txt
```
> [!NOTE]
> Main dependencies include `opencv-python`, `mediapipe`, and `Pillow`.

### 2. Running the Application
Launch the auto-tracker by executing the packaged batch script:
```bash
Run_Tracker.bat
```
Alternatively, execute the main Python file directly:
```bash
python main.py
```

> [!TIP]
> Command-line arguments can override configuration defaults:
> - `--ip <IP>`: Specify BirdDog camera IP (e.g., `192.168.1.100`)
> - `--port <Port>`: Specify VISCA Port (default: `52381`)
> - `--stream <Index/RTSP>`: Set stream source (e.g., `0` for default webcam, or an RTSP URL)
>
> Executed CLI overrides will automatically sync back and update your local `config.json` file.

---

## ⚙️ How to Configure Settings

### 1. Accessing the Settings Panel
* Move your mouse to the top-right corner of the video tracking window and click the **Settings** button overlay.
* The settings window will pop up in the foreground.

### 2. Binding Keys & Mouse Buttons
1. Scroll down to the **KEY & MOUSE BINDINGS** card inside the settings panel.
2. Locate the command you want to re-bind (e.g., *Move Left*) and click its **Bind** button.
3. The button will pulse into a green `Listening...` state.
4. Press any keyboard key, or click any mouse button (Left Click, Middle Click, Right Click) within the settings window to register the new control.
   * *To cancel binding, press `Escape` on your keyboard.*
5. Click **Save Settings** to write and apply your updates.

---

## 🎮 Controls & Manual Overrides

When **Auto-Tracking** is active, triggering any manual keyboard or mouse command automatically suspends auto-tracking so you can take direct control.

* **Toggle Auto-Tracking**: Mapped to `T` by default (switches tracking `ON` or `OFF`).
* **Instant Stop**: Mapped to `Space` by default (instantly halts all PTZ camera movements).
* **Quit Application**: Press `Q` in the camera viewport window to exit.

---

## 📹 Video Stream Configuration

You can pull your BirdDog video feed into the tracker using two primary methods:

### Method A: NDI Virtual Input (Webcam Driver)
1. Open **NDI Virtual Input** (part of the free NDI Tools suite).
2. Select your BirdDog camera stream.
3. Set your Camera Stream Index in the Settings panel to the webcam index corresponding to the virtual driver (e.g. `0`, `1`, `2`).
   * *You can use `test_cams_gui.py` to identify the correct camera index.*

### Method B: RTSP Stream
1. Open the BirdDog camera web portal (BirdUI).
2. Navigate to **AV Setup** -> **Si2 Encode** and enable the RTSP stream.
3. Copy the RTSP stream URL (usually formatted as `rtsp://<camera-ip>:554/`).
4. Paste the URL into the **Camera Stream Index/URL** field in the Settings panel and click Save.

---

## 📂 Project Structure

```
├── main.py                    # Application entrypoint, GUI manager, & thread loop
├── tracker.py                 # MediaPipe pose extraction & target tracking logic
├── ptz_controller.py          # VISCA over IP commands and network packet dispatcher
├── requirements.txt           # Package dependencies
├── Run_Tracker.bat            # Quick launch batch script
├── test_cams_gui.py           # Helper tool to test local camera indices
├── pose_landmarker_lite.task  # MediaPipe pose estimation model
└── img/
    └── micicon.ico            # Custom window icon
```

---

## 🛡️ License

This project is open-source and available under the MIT License.
