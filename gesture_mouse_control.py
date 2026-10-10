"""
===============================================================================
AI Hand Gesture Control System (Virtual Mouse & System Shortcuts)
===============================================================================
Features Implemented:
 1. Cursor Movement        - Index finger tip controls mouse pointer
 2. Left Click            - Pinch Thumb + Index finger
 3. Right Click           - Pinch Thumb + Middle finger
 4. Double Click          - Two quick pinches (Thumb + Index) in short succession
 5. Drag and Drop         - Hold pinch (Thumb + Index) for >0.3s while moving
 6. Scroll Up/Down        - Two fingers (Index + Middle) moving vertically together
 7. Scroll Left/Right     - Two fingers (Index + Middle) moving horizontally together
 8. Take Screenshot       - Open Palm held for 1 second (saves screenshot file)
 9. Volume Control        - Distance between Thumb & Pinky controls system volume
10. Zoom In/Out           - Spread/Pinch Thumb + Ring finger
11. Minimize/Switch Win   - Fast hand swipe Left (Desktop Win+D) / Right (Switch Window Alt+Tab)
12. Sensitivity Toggle    - Pinch Thumb + Ring briefly to toggle FAST / PRECISE mode
13. Click Cooldown        - Cooldown timer to prevent duplicate click triggers
14. Hand-Presence Detect  - Auto-pauses cursor movement when hand leaves camera view
15. Visual Feedback       - Color-coded circles & lines on fingertips & tracked landmarks
16. Gesture Overlay Text  - Live HUD confirmation text ("LEFT CLICK", "DRAGGING", etc.)
===============================================================================
"""

import cv2
import pyautogui
import numpy as np
import time
import math
import os
import sys
from datetime import datetime

# -----------------------------------------------------------------------------
# Multi-Backend Hand Tracking Initialization (cvzone / mediapipe fallback)
# -----------------------------------------------------------------------------
HAND_TRACKER_BACKEND = None
mp_hands_mod = None
mp_draw_mod = None
cvzone_detector = None

# Attempt 1: Try cvzone (Most robust on Windows)
try:
    from cvzone.HandTrackingModule import HandDetector
    cvzone_detector = HandDetector(detectionCon=0.7, maxHands=1)
    HAND_TRACKER_BACKEND = "cvzone"
    print("[INFO] Hand Tracker Backend: cvzone initialized successfully.")
except Exception as e_cvzone:
    # Attempt 2: Try standard mediapipe solutions
    try:
        import mediapipe as mp
        try:
            import mediapipe.solutions.hands as mp_hands_mod
            import mediapipe.solutions.drawing_utils as mp_draw_mod
        except Exception:
            try:
                from mediapipe.python.solutions import hands as mp_hands_mod
                from mediapipe.python.solutions import drawing_utils as mp_draw_mod
            except Exception:
                mp_hands_mod = mp.solutions.hands
                mp_draw_mod = mp.solutions.drawing_utils
        
        HAND_TRACKER_BACKEND = "mediapipe"
        print("[INFO] Hand Tracker Backend: mediapipe.solutions initialized successfully.")
    except Exception as e_mp:
        print("\n" + "="*70)
        print("[ERROR] Could not load Hand Tracking library (cvzone / mediapipe).")
        print(f"Python Executable: {sys.executable}")
        print("\nFix this by running the following command in your terminal:")
        print("    python -m pip install cvzone mediapipe opencv-python pyautogui numpy pycaw comtypes")
        print("="*70 + "\n")
        sys.exit(1)

# Windows Pycaw Volume Control Integration (With Fallback)
PYCAW_AVAILABLE = False
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume_control = cast(interface, POINTER(IAudioEndpointVolume))
    volume_range = volume_control.GetVolumeRange() # (min, max, step)
    min_vol, max_vol = volume_range[0], volume_range[1]
    PYCAW_AVAILABLE = True
except Exception as e:
    PYCAW_AVAILABLE = False

# PyAutoGUI Configuration
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.001

class GestureController:
    def __init__(self):
        # Screen dimensions
        self.screen_w, self.screen_h = pyautogui.size()
        
        # Camera dimensions
        self.cam_w, self.cam_h = 640, 480
        
        # Smoothing & Sensitivity parameters
        self.sensitivity_mode = "FAST"  # "FAST" or "PRECISE"
        self.smooth_factor_fast = 3.0
        self.smooth_factor_precise = 8.0
        
        # Cursor tracking state
        self.prev_x, self.prev_y = self.screen_w // 2, self.screen_h // 2
        self.curr_x, self.curr_y = self.prev_x, self.prev_y
        
        # Region of Interest (ROI) mapping box margins
        self.roi_margin_x = 100
        self.roi_margin_y = 80
        
        # Gestures thresholds & cooldowns
        self.pinch_threshold = 32           # pixels distance for pinch
        self.double_click_threshold = 0.35  # seconds max between pinches
        self.click_cooldown = 0.30          # seconds minimum between clicks
        self.drag_hold_duration = 0.30      # seconds to enter drag mode
        
        # Timestamps and flags
        self.last_left_click_time = 0.0
        self.last_right_click_time = 0.0
        self.last_action_time = 0.0
        self.pinch_start_time = None
        self.is_dragging = False
        
        # Gesture feedback string & display duration
        self.feedback_text = "SYSTEM READY"
        self.feedback_time = time.time()
        self.feedback_color = (0, 255, 0)
        
        # Open Palm Screenshot state
        self.palm_start_time = None
        self.last_screenshot_time = 0.0
        
        # Scroll tracking
        self.prev_scroll_x = None
        self.prev_scroll_y = None
        
        # Zoom state cooldown
        self.last_zoom_time = 0.0
        
        # Sensitivity toggle cooldown
        self.last_mode_toggle_time = 0.0
        
        # Swipe tracking
        self.recent_x_positions = []
        self.last_swipe_time = 0.0
        
        # MediaPipe object if using mediapipe backend
        if HAND_TRACKER_BACKEND == "mediapipe":
            self.mp_hands = mp_hands_mod
            self.mp_draw = mp_draw_mod
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=1,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7
            )

    def set_feedback(self, text, color=(0, 255, 255), duration=1.5):
        """Update live HUD text feedback."""
        self.feedback_text = text
        self.feedback_color = color
        self.feedback_time = time.time() + duration

    def distance(self, p1, p2):
        """Calculate Euclidean distance between two 2D points."""
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    def get_finger_states(self, lm_pts):
        """Determines which fingers are extended (True) or folded (False)."""
        index_open = lm_pts[8][1] < lm_pts[6][1]
        middle_open = lm_pts[12][1] < lm_pts[10][1]
        ring_open = lm_pts[16][1] < lm_pts[14][1]
        pinky_open = lm_pts[20][1] < lm_pts[18][1]
        
        thumb_dist = self.distance(lm_pts[4], lm_pts[17])
        thumb_base_dist = self.distance(lm_pts[2], lm_pts[17])
        thumb_open = thumb_dist > thumb_base_dist * 1.2
        
        return (thumb_open, index_open, middle_open, ring_open, pinky_open)

    def process_frame(self, frame):
        frame_h, frame_w, _ = frame.shape
        self.cam_w, self.cam_h = frame_w, frame_h
        
        # Mirror frame for intuitive interaction
        frame = cv2.flip(frame, 1)
        now = time.time()

        # Render ROI Bounding Box
        cv2.rectangle(
            frame,
            (self.roi_margin_x, self.roi_margin_y),
            (self.cam_w - self.roi_margin_x, self.cam_h - self.roi_margin_y),
            (255, 255, 0), 1, cv2.LINE_AA
        )
        cv2.putText(
            frame, "TRACKING ZONE",
            (self.roi_margin_x + 5, self.roi_margin_y - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1
        )

        lm_pts = {}
        hand_detected = False

        # Detect hands based on active backend
        if HAND_TRACKER_BACKEND == "cvzone":
            hands, frame = cvzone_detector.findHands(frame, draw=True)
            if hands:
                hand_detected = True
                lm_list = hands[0]['lmList']
                for idx, pt in enumerate(lm_list):
                    lm_pts[idx] = (pt[0], pt[1])
        else: # mediapipe backend
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)
            if results.multi_hand_landmarks:
                hand_detected = True
                hand_landmarks = results.multi_hand_landmarks[0]
                for idx, lm in enumerate(hand_landmarks.landmark):
                    cx, cy = int(lm.x * self.cam_w), int(lm.y * self.cam_h)
                    lm_pts[idx] = (cx, cy)
                
                self.mp_draw.draw_landmarks(
                    frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                    self.mp_draw.DrawingSpec(color=(100, 100, 100), thickness=2, circle_radius=2),
                    self.mp_draw.DrawingSpec(color=(0, 255, 255), thickness=2)
                )

        # ---------------------------------------------------------------------
        # Feature 14: Hand-Presence Detection
        # ---------------------------------------------------------------------
        if not hand_detected:
            if self.is_dragging:
                pyautogui.mouseUp()
                self.is_dragging = False
                self.set_feedback("DRAG RELEASED (HAND LOST)", (0, 0, 255))
            
            self.pinch_start_time = None
            self.palm_start_time = None
            self.prev_scroll_x = None
            self.prev_scroll_y = None
            self.recent_x_positions.clear()
            
            cv2.putText(
                frame, "NO HAND DETECTED - PAUSED",
                (self.cam_w // 2 - 150, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2
            )
            self.render_hud(frame, now)
            return frame

        # ---------------------------------------------------------------------
        # Feature 15: Visual Feedback on Screen (Fingertips Color Coding)
        # ---------------------------------------------------------------------
        fingertip_colors = {
            4:  (255, 0, 255),  # Thumb
            8:  (0, 255, 255),  # Index
            12: (0, 255, 0),    # Middle
            16: (255, 255, 0),  # Ring
            20: (0, 165, 255)   # Pinky
        }
        for lm_id, color in fingertip_colors.items():
            if lm_id in lm_pts:
                cv2.circle(frame, lm_pts[lm_id], 8, color, -1)
                cv2.circle(frame, lm_pts[lm_id], 10, (255, 255, 255), 1)

        thumb_open, index_open, middle_open, ring_open, pinky_open = self.get_finger_states(lm_pts)
        
        thumb_tip = lm_pts[4]
        index_tip = lm_pts[8]
        middle_tip = lm_pts[12]
        ring_tip = lm_pts[16]
        pinky_tip = lm_pts[20]
        wrist_pt = lm_pts[0]

        # Track recent wrist X positions for swipe gesture
        self.recent_x_positions.append((now, wrist_pt[0]))
        self.recent_x_positions = [p for p in self.recent_x_positions if now - p[0] <= 0.4]

        # ---------------------------------------------------------------------
        # Feature 12: Cursor Speed/Sensitivity Toggle (Thumb + Ring Pinch)
        # ---------------------------------------------------------------------
        thumb_ring_dist = self.distance(thumb_tip, ring_tip)
        if thumb_ring_dist < self.pinch_threshold and not index_open and not pinky_open:
            if now - self.last_mode_toggle_time > 1.0:
                if self.sensitivity_mode == "FAST":
                    self.sensitivity_mode = "PRECISE"
                    self.set_feedback("MODE: PRECISE SENSITIVITY", (255, 191, 0))
                else:
                    self.sensitivity_mode = "FAST"
                    self.set_feedback("MODE: FAST SENSITIVITY", (0, 255, 0))
                self.last_mode_toggle_time = now

        # ---------------------------------------------------------------------
        # Feature 8: Take Screenshot (Open Palm held for 1s)
        # ---------------------------------------------------------------------
        all_open = thumb_open and index_open and middle_open and ring_open and pinky_open
        if all_open:
            if self.palm_start_time is None:
                self.palm_start_time = now
            elif now - self.palm_start_time >= 1.0 and now - self.last_screenshot_time > 3.0:
                os.makedirs("screenshots", exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join("screenshots", f"screenshot_{timestamp}.png")
                screenshot = pyautogui.screenshot()
                screenshot.save(filename)
                
                self.set_feedback(f"SCREENSHOT TAKEN! Saved: {filename}", (0, 255, 0), duration=2.5)
                self.last_screenshot_time = now
                self.palm_start_time = None
        else:
            self.palm_start_time = None

        # ---------------------------------------------------------------------
        # Feature 11: Minimize / Switch Window (Rapid Swipe Left/Right)
        # ---------------------------------------------------------------------
        if len(self.recent_x_positions) >= 4 and (now - self.last_swipe_time > 1.2):
            dx_swipe = self.recent_x_positions[-1][1] - self.recent_x_positions[0][1]
            dt_swipe = self.recent_x_positions[-1][0] - self.recent_x_positions[0][0]
            if dt_swipe > 0:
                velocity = dx_swipe / dt_swipe
                if velocity > 900:  # Fast Right Swipe
                    pyautogui.hotkey('alt', 'tab')
                    self.set_feedback("SWIPE RIGHT: SWITCH WINDOW (ALT+TAB)", (255, 0, 255))
                    self.last_swipe_time = now
                    self.recent_x_positions.clear()
                elif velocity < -900:  # Fast Left Swipe
                    pyautogui.hotkey('win', 'd')
                    self.set_feedback("SWIPE LEFT: TOGGLE DESKTOP (WIN+D)", (255, 0, 255))
                    self.last_swipe_time = now
                    self.recent_x_positions.clear()

        # ---------------------------------------------------------------------
        # Feature 1: Cursor Movement (Index Finger Tracking)
        # ---------------------------------------------------------------------
        mapped_x = np.interp(
            index_tip[0],
            [self.roi_margin_x, self.cam_w - self.roi_margin_x],
            [0, self.screen_w]
        )
        mapped_y = np.interp(
            index_tip[1],
            [self.roi_margin_y, self.cam_h - self.roi_margin_y],
            [0, self.screen_h]
        )

        smooth_val = self.smooth_factor_fast if self.sensitivity_mode == "FAST" else self.smooth_factor_precise
        self.curr_x = self.prev_x + (mapped_x - self.prev_x) / smooth_val
        self.curr_y = self.prev_y + (mapped_y - self.prev_y) / smooth_val

        # ---------------------------------------------------------------------
        # Feature 2, 4, 5: Left Click, Double Click, Drag and Drop
        # ---------------------------------------------------------------------
        thumb_index_dist = self.distance(thumb_tip, index_tip)

        if thumb_index_dist < self.pinch_threshold:
            cv2.line(frame, thumb_tip, index_tip, (0, 255, 0), 3)

            if self.pinch_start_time is None:
                self.pinch_start_time = now

            if not self.is_dragging and (now - self.pinch_start_time >= self.drag_hold_duration):
                self.is_dragging = True
                pyautogui.mouseDown()
                self.set_feedback("DRAG MODE ACTIVATED", (0, 255, 255))

            if self.is_dragging:
                pyautogui.moveTo(self.curr_x, self.curr_y)
                self.set_feedback("DRAGGING...", (0, 255, 255), duration=0.2)
        else:
            if self.is_dragging:
                pyautogui.mouseUp()
                self.is_dragging = False
                self.set_feedback("ITEM DROPPED", (0, 255, 0))
                self.pinch_start_time = None
            elif self.pinch_start_time is not None:
                pinch_duration = now - self.pinch_start_time
                self.pinch_start_time = None

                if pinch_duration < self.drag_hold_duration:
                    time_since_last_click = now - self.last_left_click_time

                    if time_since_last_click < self.double_click_threshold and time_since_last_click > 0.05:
                        pyautogui.doubleClick()
                        self.set_feedback("DOUBLE CLICK", (0, 255, 255))
                        self.last_left_click_time = 0.0
                    elif now - self.last_action_time > self.click_cooldown:
                        pyautogui.click()
                        self.set_feedback("LEFT CLICK", (0, 255, 0))
                        self.last_left_click_time = now
                        self.last_action_time = now

        if not self.is_dragging and index_open and not all_open:
            pyautogui.moveTo(self.curr_x, self.curr_y)

        self.prev_x, self.prev_y = self.curr_x, self.curr_y

        # ---------------------------------------------------------------------
        # Feature 3: Right Click (Thumb + Middle Pinch)
        # ---------------------------------------------------------------------
        thumb_middle_dist = self.distance(thumb_tip, middle_tip)
        if thumb_middle_dist < self.pinch_threshold:
            cv2.line(frame, thumb_tip, middle_tip, (255, 0, 255), 3)
            if now - self.last_right_click_time > self.click_cooldown:
                pyautogui.rightClick()
                self.set_feedback("RIGHT CLICK", (255, 0, 255))
                self.last_right_click_time = now

        # ---------------------------------------------------------------------
        # Feature 6 & 7: Scroll Up/Down & Left/Right (Index + Middle extended together)
        # ---------------------------------------------------------------------
        index_middle_dist = self.distance(index_tip, middle_tip)
        is_scrolling_gesture = index_open and middle_open and not ring_open and not pinky_open and (index_middle_dist < 45)

        if is_scrolling_gesture:
            cv2.line(frame, index_tip, middle_tip, (0, 255, 255), 2)
            
            if self.prev_scroll_y is not None and self.prev_scroll_x is not None:
                dy = index_tip[1] - self.prev_scroll_y
                dx = index_tip[0] - self.prev_scroll_x
                
                if abs(dy) > 4:
                    scroll_amount = int(-dy * 3)
                    pyautogui.scroll(scroll_amount)
                    direction = "UP" if dy < 0 else "DOWN"
                    self.set_feedback(f"SCROLL {direction}", (255, 255, 0), duration=0.2)
                
                if abs(dx) > 6:
                    hscroll_amount = int(dx * 3)
                    pyautogui.hscroll(hscroll_amount)
                    direction = "RIGHT" if dx > 0 else "LEFT"
                    self.set_feedback(f"SCROLL {direction}", (255, 255, 0), duration=0.2)

            self.prev_scroll_y = index_tip[1]
            self.prev_scroll_x = index_tip[0]
        else:
            self.prev_scroll_y = None
            self.prev_scroll_x = None

        # ---------------------------------------------------------------------
        # Feature 9: Volume Control (Thumb & Pinky Distance)
        # ---------------------------------------------------------------------
        is_volume_gesture = thumb_open and pinky_open and not index_open and not middle_open and not ring_open
        if is_volume_gesture:
            cv2.line(frame, thumb_tip, pinky_tip, (0, 165, 255), 2)
            tp_dist = self.distance(thumb_tip, pinky_tip)
            
            vol_pct = np.interp(tp_dist, [40, 200], [0, 100])
            vol_pct = int(np.clip(vol_pct, 0, 100))

            if PYCAW_AVAILABLE:
                volume_control.SetMasterVolumeLevelScalar(vol_pct / 100.0, None)
                self.set_feedback(f"VOLUME: {vol_pct}%", (0, 165, 255), duration=0.2)
            else:
                if vol_pct > 60:
                    pyautogui.press('volumeup')
                elif vol_pct < 40:
                    pyautogui.press('volumedown')
                self.set_feedback(f"VOLUME ({vol_pct}%)", (0, 165, 255), duration=0.2)

        # ---------------------------------------------------------------------
        # Feature 10: Zoom In/Out (Thumb + Ring Finger Spread/Pinch)
        # ---------------------------------------------------------------------
        is_zoom_gesture = thumb_open and ring_open and not index_open and not middle_open
        if is_zoom_gesture:
            tr_dist = self.distance(thumb_tip, ring_tip)
            cv2.line(frame, thumb_tip, ring_tip, (255, 255, 0), 2)
            
            if now - self.last_zoom_time > 0.4:
                if tr_dist < 30:
                    pyautogui.hotkey('ctrl', '-')
                    self.set_feedback("ZOOM OUT", (255, 255, 0))
                    self.last_zoom_time = now
                elif tr_dist > 120:
                    pyautogui.hotkey('ctrl', '+')
                    self.set_feedback("ZOOM IN", (255, 255, 0))
                    self.last_zoom_time = now

        self.render_hud(frame, now)
        return frame

    def render_hud(self, frame, now):
        """Draw Top Status Bar & Feature 16: Gesture Confirmation Text."""
        cv2.rectangle(frame, (0, 0), (self.cam_w, 35), (20, 20, 20), -1)
        
        cv2.putText(
            frame, f"AI GESTURE MOUSE | MODE: {self.sensitivity_mode} | BACKEND: {HAND_TRACKER_BACKEND.upper()}",
            (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA
        )
        
        cv2.putText(
            frame, "[ESC/Q: Exit]",
            (self.cam_w - 100, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1, cv2.LINE_AA
        )

        if now < self.feedback_time:
            cv2.rectangle(frame, (0, self.cam_h - 40), (self.cam_w, self.cam_h), (0, 0, 0), -1)
            cv2.putText(
                frame, f">>> {self.feedback_text} <<<",
                (20, self.cam_h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.feedback_color, 2, cv2.LINE_AA
            )

def main():
    print("=================================================================")
    print("      AI HAND GESTURE VIRTUAL MOUSE & SYSTEM CONTROL             ")
    print(f"      ACTIVE HAND TRACKING BACKEND: {HAND_TRACKER_BACKEND.upper()} ")
    print("=================================================================")
    print("Starting webcam camera stream...")
    print("Press 'q' or 'ESC' on the camera window to exit.")
    
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("ERROR: Could not open webcam camera. Please verify webcam connection.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    controller = GestureController()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab camera frame.")
            break

        processed_frame = controller.process_frame(frame)
        cv2.imshow("AI Hand Gesture Control Window", processed_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord('q'):
            print("Exiting Gesture Control System.")
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
