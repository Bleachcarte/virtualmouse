import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import math
import time


def distance(point1, point2):
    return math.hypot(point2[0] - point1[0], point2[1] - point1[1])
def is_fist(hand_landmarks):
    wrist = hand_landmarks.landmark[0]
    folded_fingers = 0
    for tip_id in [8, 12, 16, 20]:
        tip = hand_landmarks.landmark[tip_id]
        dist = ((tip.x - wrist.x)**2 + (tip.y - wrist.y)**2)**0.5
        if dist < 0.08:  # tune this threshold
            folded_fingers += 1
    return folded_fingers >= 3



# Initialize webcam
cap = cv2.VideoCapture(0)

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2, model_complexity=1, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

# Get the screen size
screen_width, screen_height = pyautogui.size()

from collections import deque

smooth_cursor = deque(maxlen=7)  # store last 7 positions
click_threshold = 30  # pixel distance threshold for a click gesture
last_click_time = 0
click_cooldown = 1  # seconds between allowed clicks
right_click_threshold = 40  # pixels; adjust this if needed
right_click_cooldown = 1.5  # seconds
last_right_click_time = 0
# Distance thresholds to reduce jitter
drag_start_threshold = 30
drag_end_threshold = 50  # must be > drag_start_threshold
drag_activation_frames = 5
drag_frame_counter = 0
dragging = False
scroll_threshold = 30
scroll_up_thresh = 0.04
scroll_down_thresh = 0.04

scroll_cooldown = 0.5
last_scroll_time = 0



# Start video loop
while True:
    success, frame = cap.read()
    if not success:
        break

    # Flip the frame for natural interaction
    frame = cv2.flip(frame, 1)
    h, w, c = frame.shape
    frame_h, frame_w, _ = frame.shape
    # Set margins (tune these values based on your camera and comfort)
    margin_x = 25
    margin_y = 25

    # Define active region
    active_left = margin_x
    active_right = frame_w - margin_x
    active_top = margin_y
    active_bottom = frame_h - margin_y


    # Convert BGR to RGB for MediaPipe
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(img_rgb)

    # Draw landmarks if a hand is detected
    if results.multi_hand_landmarks:
        right_hand = None
        left_hand = None

        for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
            hand_label = results.multi_handedness[idx].classification[0].label  # 'Left' or 'Right'

            if hand_label == 'Right':
                right_hand = hand_landmarks
            elif hand_label == 'Left':
                left_hand = hand_landmarks

        if right_hand:
            mp_draw.draw_landmarks(frame, right_hand, mp_hands.HAND_CONNECTIONS)
             # Get index finger tip (landmark 8)
            # --- Extract landmark positions
            index_tip = right_hand.landmark[8]
            thumb_tip = right_hand.landmark[4]
            pinky_tip = right_hand.landmark[20]

            # Convert to pixels
            ix, iy = int(index_tip.x * w), int(index_tip.y * h)
            tx, ty = int(thumb_tip.x * w), int(thumb_tip.y * h)
            px, py = int(pinky_tip.x * w), int(pinky_tip.y * h)

            # Clamp to active region
            ix = max(active_left, min(ix, active_right))
            iy = max(active_top, min(iy, active_bottom))

            # Calculate distances
            pinch_dist = math.hypot(ix - tx, iy - ty)
            right_click_dist = math.hypot(px - tx, py - ty)
            # Scroll distances
            # Scroll distances
            middle_tip = hand_landmarks.landmark[12]
            ring_tip = hand_landmarks.landmark[16]

            middle_scroll_dist = distance((middle_tip.x, middle_tip.y), (thumb_tip.x, thumb_tip.y))
            ring_scroll_dist = distance((ring_tip.x, ring_tip.y), (thumb_tip.x, thumb_tip.y))



            # Convert to screen coords
            screen_x = np.interp(ix, [active_left, active_right], [0, screen_width])
            screen_y = np.interp(iy, [active_top, active_bottom], [0, screen_height])

            # Smoothing
            smooth_cursor.append((screen_x, screen_y))
            avg_x = int(sum(x for x, _ in smooth_cursor) / len(smooth_cursor))
            avg_y = int(sum(y for _, y in smooth_cursor) / len(smooth_cursor))

            # Gesture Priority ------------------------
            current_time = time.time()

            # --- Gesture Control Logic ---

            # 1. RIGHT CLICK (pinky tapping thumb)
            if right_click_dist < right_click_threshold and current_time - last_right_click_time > right_click_cooldown:
                pyautogui.rightClick()
                last_right_click_time = current_time
                cv2.putText(frame, 'Right Click!', (px + 20, py - 20), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 100, 0), 2)
            # 2. SCROLLING
            # Scroll Up
            if middle_scroll_dist < scroll_up_thresh and current_time - last_scroll_time > scroll_cooldown:
                pyautogui.scroll(20)
                last_scroll_time = current_time
                cv2.putText(frame, 'Scroll Up', (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 200, 0), 2)

            # Scroll Down
            elif ring_scroll_dist < scroll_down_thresh and current_time - last_scroll_time > scroll_cooldown:
                pyautogui.scroll(-20)
                last_scroll_time = current_time
                cv2.putText(frame, 'Scroll Down', (50, 140), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 100, 0), 2)


            # 2. DRAG (using fist gesture)
            elif is_fist(hand_landmarks):
                if not dragging:
                    pyautogui.mouseDown()
                    dragging = True
                cv2.putText(frame, 'Dragging (Fist)...', (ix + 20, iy + 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 200), 2)

            elif dragging:
                pyautogui.mouseUp()
                dragging = False

            # 3. LEFT CLICK (pinch index-thumb)
            elif pinch_dist < click_threshold and not dragging:
                if current_time - last_click_time > click_cooldown:
                    pyautogui.click()
                    last_click_time = current_time
                    cv2.putText(frame, 'Click!', (ix + 20, iy - 20), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # 4. MOVE MOUSE (only if not dragging)
            if not dragging:
                pyautogui.moveTo(avg_x, avg_y)


    # ------------------------------------------
        # LEFT HAND LOGIC (MacBook Shortcuts)
        # ------------------------------------------
        if left_hand:
            mp_draw.draw_landmarks(frame, left_hand, mp_hands.HAND_CONNECTIONS)
            # Extract tip landmarks
            l_thumb = left_hand.landmark[4]
            l_index = left_hand.landmark[8]
            l_middle = left_hand.landmark[12]
            l_ring = left_hand.landmark[16]
            l_pinky = left_hand.landmark[20]

            # Convert to pixel positions
            ltx, lty = int(l_thumb.x * w), int(l_thumb.y * h)
            lix, liy = int(l_index.x * w), int(l_index.y * h)
            lmx, lmy = int(l_middle.x * w), int(l_middle.y * h)
            lrx, lry = int(l_ring.x * w), int(l_ring.y * h)
            lpx, lpy = int(l_pinky.x * w), int(l_pinky.y * h)

            # Distances
            pinch_dist = math.hypot(ltx - lix, lty - liy)
            pinky_pinch = math.hypot(ltx - lpx, lty - lpy)
            peace_gap = math.hypot(lix - lmx, liy - lmy)
            fist_closed = (
                math.hypot(lix - lrx, liy - lry) < 40 and
                math.hypot(lmx - lrx, lmy - lry) < 40 and
                math.hypot(lpx - lrx, lpy - lry) < 40
            )
            shaka = (
                math.hypot(ltx - lpx, lty - lpy) > 100 and
                math.hypot(lix - lmx, liy - lmy) < 30  # index + middle down
            )

            # Gesture: Thumb + Index = Mission Control
            if pinch_dist < click_threshold and time.time() - last_click_time > click_cooldown:
                pyautogui.hotkey('ctrl', 'up')
                last_click_time = time.time()
                cv2.putText(frame, 'Mission Control', (lix, liy), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 200, 0), 2)

            # Gesture: Full Fist = App Exposé
            elif fist_closed and not is_fist(right_hand):
                pyautogui.hotkey('ctrl', 'down')
                cv2.putText(frame, 'App Exposé', (lrx, lry), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 100, 255), 2)

            # Gesture: Pinky + Thumb = Minimize
            elif pinky_pinch < right_click_threshold:
                pyautogui.hotkey('command', 'm')
                cv2.putText(frame, 'Minimize', (ltx, lty), cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 255, 100), 2)

            
            # Gesture: Peace Sign = Spotlight (macOS)
            index_up = liy < left_hand.landmark[6].y * h
            middle_up = lmy < left_hand.landmark[10].y * h
            ring_down = lry > left_hand.landmark[14].y * h
            pinky_down = lpy > left_hand.landmark[18].y * h

            peace_gap = distance((lix, liy), (lmx, lmy))

            if (
                index_up and middle_up and ring_down and pinky_down
                and peace_gap > 40
                and time.time() - last_click_time > click_cooldown
            ):
                pyautogui.hotkey('command', 'space')
                last_click_time = time.time()
                cv2.putText(frame, 'Spotlight', (lix, liy), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)


            
        #    # Gesture: 3-Finger Spread → Next Desktop
        #     three_finger_spread = (
        #         distance((lix, liy), (lmx, lmy)) > 50 and
        #         distance((lix, liy), (lpx, lpy)) > 50 and
        #         distance((lmx, lmy), (lpx, lpy)) > 50 and
        #         lry > left_hand.landmark[14].y * h and
        #         lpy > left_hand.landmark[18].y * h
        #     )

        #     if three_finger_spread and time.time() - last_click_time > click_cooldown:
        #         pyautogui.hotkey('ctrl', 'right')
        #         last_click_time = time.time()
        #         cv2.putText(frame, 'Next Desktop', (lix, liy), cv2.FONT_HERSHEY_SIMPLEX, 1, (150, 255, 255), 2)
        #     # Gesture: 3-Finger Pinch → Previous Desktop
        #     three_finger_pinch = (
        #         distance((lix, liy), (lmx, lmy)) < 30 and
        #         distance((lix, liy), (lpx, lpy)) < 30 and
        #         distance((lmx, lmy), (lpx, lpy)) < 30 and
        #         lry > left_hand.landmark[14].y * h and
        #         lpy > left_hand.landmark[18].y * h
        #     )

        #     if three_finger_pinch and time.time() - last_click_time > click_cooldown:
        #         pyautogui.hotkey('ctrl', 'left')
        #         last_click_time = time.time()
        #         cv2.putText(frame, 'Prev Desktop', (lix, liy), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 200, 150), 2)


     # Show frame
     # Draw the active region rectangle
    cv2.rectangle(frame, (active_left, active_top), (active_right, active_bottom), (0, 255, 0), 2)
    cv2.imshow("Hand Tracking", frame)

    # Break loop with 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release resources
cap.release()
cv2.destroyAllWindows()
