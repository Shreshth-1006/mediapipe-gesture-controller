# mediapipe-gesture-controller
Real-time AI-powered hand gesture control system built with OpenCV and MediaPipe. Control cursor navigation, clicks, scrolling, volume, and system shortcuts hands-free via webcam.
# 🖐️ VisionMouse: AI Hand Gesture Control System

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Hands%200.10+-00C7B7?style=for-the-badge&logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com)
[![License](https://img.shields.io/badge/License-MIT-success?style=for-the-badge)](LICENSE)

<p align="center">
  <b>A real-time, touchless computer interaction system powered by Computer Vision & Deep Learning.</b><br>
  Control cursor movement, multi-touch gestures, system volume, window switching, and shortcuts using simple hand gestures through any standard webcam.
</p>

[✨ Features](#-core-features) • [📊 System Architecture](#-system-architecture) • [🖐️ Landmark Map](#-hand-landmark-reference) • [🎮 Gesture Matrix](#-gesture-control-matrix) • [🚀 Quickstart](#-quickstart-guide) • [⚙️ Parameter Tuning](#-parameter-tuning)

---

</div>

## 🌟 Key Highlights

- ⚡ **Zero External Hardware**: Runs fluidly at 30–60 FPS on any standard 720p/1080p laptop webcam.
- 🎯 **Dual Sensitivity Modes**: Toggle dynamically between **FAST** (fluid browsing) and **PRECISE** (pixel-perfect drafting) modes.
- 🛡️ **Zero Ghost-Clicks**: Equipped with debouncing cooldowns, distance hysteresis, and automatic tracking loss pauses.
- 🔊 **Native Windows Audio Control**: Integrated with Windows Core Audio APIs (`pycaw`) for hardware-level volume sliders.
- 🖥️ **Live HUD Visualizer**: Color-coded tracking lines, active gesture notification banners, and interactive tracking boundaries.

---

## 📊 System Architecture

The pipeline processes webcam frames in real-time, calculates normalized hand landmark coordinates, applies exponential smoothing, and triggers high-frequency desktop events via PyAutoGUI.

```mermaid
flowchart TD
    subgraph INPUT ["📷 Video Input & Pre-processing"]
        A[Webcam 640x480 Frame] --> B[Horizontal Flip / Mirroring]
        B --> C[ROI Bounding Box Extraction]
    end

    subgraph TRACKING ["🤖 AI Landmark Extraction"]
        C --> D{Tracker Backend}
        D -->|Primary| E[cvzone HandDetector]
        D -->|Fallback| F[MediaPipe Solutions 21 Landmarks]
        E --> G[21 3D Coordinate Points]
        F --> G
    end

    subgraph ENGINE ["🧠 Gesture Engine & Smoothing"]
        G --> H[Exponential Weighted Smoothing Filter]
        H --> I[State Machine & Finger Distance Calculus]
        I --> J{Active Gesture Identified?}
    end

    subgraph ACTIONS ["⚡ Desktop Control & Feedback"]
        J -->|Index Tip Pointing| K[🖱️ Cursor Move]
        J -->|Thumb + Index Pinch| L[👆 Left Click / Drag & Drop]
        J -->|Thumb + Middle Pinch| M[👉 Right Click]
        J -->|Two Fingers Vertical/Horizontal| N[📜 Smooth Scrolling]
        J -->|Thumb + Pinky Distance| O[🔊 Hardware Volume]
        J -->|Full Palm Hold 1s| P[📸 Instant Screenshot]
        J -->|Fast Horizontal Swipe| Q[🪟 Win+D / Alt+Tab]
        I --> R[🎨 Real-time HUD Banner & Landmark Overlay]
    end

    style INPUT fill:#1e1e2e,stroke:#89b4fa,stroke-width:2px,color:#cdd6f4
    style TRACKING fill:#181825,stroke:#a6e3a1,stroke-width:2px,color:#cdd6f4
    style ENGINE fill:#11111b,stroke:#f9e2af,stroke-width:2px,color:#cdd6f4
    style ACTIONS fill:#1e1e2e,stroke:#f38ba8,stroke-width:2px,color:#cdd6f4
```

---

## 🖐️ Hand Landmark Reference

The engine tracks **21 distinct 3D landmarks** per frame. The primary control triggers are mapped to key joint coordinates:

```text
               [8] Index Tip               [12] Middle Tip
                  o                           o
                 /                             \
           [7]  o                               o  [11]
               /          [16] Ring Tip          \
         [6]  o                 o                 o  [10]
             /                   \                 \
       [5]  o               [15]  o                 o  [9]
           /                       \                 \
 [4] Thumb o                  [14]  o       [20] Pinky o
     Tip    \                        \           Tip  /
       [3]   o                  [13]  o              o [19]
              \                        \            /
         [2]   o               o--------o----------o [18]
                \             /   Palm Center     /
           [1]   o-----------o                   o [17]
                              \                 /
                               o---------------o
                                      [0]
                                     Wrist
```

### 📍 Key Finger Landmark Indices

| Landmark ID | Anatomical Point | Role in System |
|:---:|:---|:---|
| **#4** | `THUMB_TIP` | Master trigger anchor for clicks, drag, volume, and zoom |
| **#8** | `INDEX_FINGER_TIP` | Primary pointer navigation, left-click pinch, scroll guide |
| **#12** | `MIDDLE_FINGER_TIP` | Right-click trigger, dual-finger scrolling partner |
| **#16** | `RING_FINGER_TIP` | Sensitivity toggle & zoom trigger |
| **#20** | `PINKY_TIP` | System volume calculation anchor & full-palm detection |
| **#0** | `WRIST` | Base anchor for swipe velocity and orientation checks |

---

## 🔄 Gesture Lifecycle & State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle: Hand Detected

    Idle --> Navigating: Index finger extended
    Navigating --> Idle: Hand leaves ROI / Camera

    state "Pinch Action" as Pinch {
        Navigating --> PinchDetected: Distance(Thumb, Index) < 32px
        PinchDetected --> Holding: Duration >= 0.3s
        Holding --> Dragging: Move hand while pinched (Mouse Down)
        Dragging --> Released: Distance >= 32px (Mouse Up)
        PinchDetected --> SingleClick: Released < 0.3s
        SingleClick --> DoubleClick: 2nd Pinch within 0.35s
    }

    state "Special Gestures" as Special {
        Navigating --> VolumeControl: Thumb & Pinky extended
        Navigating --> Scrolling: Index & Middle fingers extended
        Navigating --> Screenshot: 5 fingers wide for 1.0s
        Navigating --> WindowSwipe: Horizontal velocity > 120px/s
    }

    Released --> Navigating
    DoubleClick --> Navigating
    Special --> Navigating
```

---

## 🎮 Gesture Control Matrix

| Icon | Action | Trigger Gesture | Threshold / Timing | Windows Action |
|:---:|:---|:---|:---|:---|
| 🖱️ | **Cursor Move** | Index finger extended inside ROI box | Continuous tracking | Move pointer with smoothing |
| 👆 | **Left Click** | Pinch Thumb (#4) + Index (#8) | `< 32px`, released `< 0.30s` | `pyautogui.click()` |
| ✌️ | **Double Click** | Quick dual pinch Thumb + Index | 2 pinches within `< 0.35s` | `pyautogui.doubleClick()` |
| ✊ | **Drag & Drop** | Hold pinch Thumb + Index while moving | Hold `> 0.30s` | Mouse Down $\to$ Move $\to$ Drop |
| 🖕 | **Right Click** | Pinch Thumb (#4) + Middle (#12) | `< 32px`, cooldown `0.30s` | `pyautogui.rightClick()` |
| 📜 | **Vertical Scroll** | Index + Middle extended, move up/down | Vertical displacement | Scroll wheel Up / Down |
| ↔️ | **Horizontal Scroll**| Index + Middle extended, move left/right | Horizontal displacement | Shift + Scroll Left / Right |
| 🔊 | **Volume Control** | Thumb + Pinky extended (Hang-Ten 🤙) | Distance `30px - 200px` | Smooth master volume (0–100%) |
| 🔍 | **Zoom In / Out** | Pinch/Spread Thumb (#4) + Ring (#16) | Pinch = Out, Spread = In | `Ctrl +` / `Ctrl -` |
| 📸 | **Screenshot** | Open Palm (all 5 fingers spread) | Hold for `1.0s` continuous | Auto-saved to `screenshots/` |
| 🪟 | **Switch App** | Fast hand swipe to the **Right** | Rapid horizontal velocity | `Alt + Tab` switcher |
| 🖥️ | **Show Desktop** | Fast hand swipe to the **Left** | Rapid horizontal velocity | `Win + D` minimize toggle |
| ⚡ | **Sensitivity** | Brief pinch Thumb (#4) + Ring (#16) | Quick toggle tap | Switch **FAST** $\leftrightarrow$ **PRECISE** |

---

## 📊 Performance & Benchmark Specs

| Metric | Measured Value | Optimization Note |
|:---|:---:|:---|
| **Target Frame Rate** | `30 - 60 FPS` | Dependent on camera sensor rate |
| **Input Latency** | `~15 - 28 ms` | Near-zero perceptible lag |
| **Detection Confidence** | `0.70` | Tuned to eliminate false positives in ambient lighting |
| **Tracking Confidence** | `0.70` | Ensures continuous tracking during rapid finger motion |
| **Smoothing Formula** | $X_t = X_{t-1} + \frac{X_{raw} - X_{t-1}}{\alpha}$ | $\alpha = 3.0$ (Fast) $\vert$ $\alpha = 8.0$ (Precise) |

---

## 🚀 Quickstart Guide

### 1. Prerequisites
Ensure you have **Python 3.8 to 3.11** installed on your Windows PC.

### 2. Clone and Install Dependencies

```bash
# Clone the repository
git clone https://github.com/your-username/ai-gesture-virtual-mouse.git
cd ai-gesture-virtual-mouse

# Install required dependencies
pip install -r requirements.txt
```

*Direct one-line install alternative:*
```bash
pip install opencv-python mediapipe pyautogui numpy pycaw comtypes cvzone
```

### 3. Launch the Application

```bash
python gesture_mouse_control.py
```

### 4. Controls & Exit
- **`q`** or **`ESC`**: Quit the application and release camera resources.
- **Visual Screen**: The top-left corner displays your active FPS, sensitivity mode, and gesture confirmation banner.

---

## ⚙️ Parameter Tuning

<details>
<summary><b>🔧 Click to expand customizable parameters in <code>gesture_mouse_control.py</code></b></summary>

All control parameters can be easily adjusted inside the `GestureController.__init__` method:

```python
# Screen margins for mapping (Smaller margin = wider cursor reach)
self.roi_margin_x = 100   # Horizontal boundary offset
self.roi_margin_y = 80    # Vertical boundary offset

# Gesture trigger distances (in camera pixels)
self.pinch_threshold = 32           # Max distance to register a pinch

# Timing parameters (in seconds)
self.click_cooldown = 0.30          # Minimum wait between consecutive clicks
self.double_click_threshold = 0.35  # Maximum interval for double click
self.drag_hold_duration = 0.30      # Hold duration before entering drag mode

# Smoothing factors (Higher = smoother, Lower = snappier)
self.smooth_factor_fast = 3.0       # Fast mode smoothing
self.smooth_factor_precise = 8.0    # Precise mode smoothing
```

</details>

---

## 🛠️ Project Structure

```text
ai-gesture-virtual-mouse/
├── gesture_mouse_control.py    # Main application logic & gesture engine
├── requirements.txt            # Python dependencies
├── README.md                   # Comprehensive documentation & visual guide
└── screenshots/                # Auto-generated folder for gesture screenshots
```

---

## 🤝 Troubleshooting & FAQs

<details>
<summary><b>❓ Cursor is jittery or jumping around</b></summary>
Switch to <b>PRECISE</b> mode by pinching your Thumb and Ring finger briefly. You can also increase <code>self.smooth_factor_fast</code> from <code>3.0</code> to <code>5.0</code> in <code>gesture_mouse_control.py</code>. Ensure your room has balanced lighting.
</details>

<details>
<summary><b>❓ Volume control does not work</b></summary>
Volume control utilizes <code>pycaw</code> which connects to the Windows Core Audio API. If running in a virtual machine or non-Windows OS, volume adjustment falls back gracefully without interrupting cursor operations.
</details>

<details>
<summary><b>❓ Clicks triggering unintentionally</b></summary>
Ensure your fingers are clearly separated when pointing. If your webcam resolution differs, adjust <code>self.pinch_threshold = 28</code> to require a tighter pinch before activating clicks.
</details>

---

<div align="center">
  <sub>Built with ❤️ using OpenCV, MediaPipe, and PyAutoGUI. Star ⭐ this repo if you found it useful!</sub>
</div>
