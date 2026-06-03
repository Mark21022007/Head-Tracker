import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow C++ warnings
os.environ['GLOG_minloglevel'] = '2'      # Suppress MediaPipe glog warnings (W0000)

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class PastorTracker:
    def __init__(self):
        # Set up MediaPipe Tasks API
        base_options = python.BaseOptions(model_asset_path='pose_landmarker_lite.task')
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO)
        
        self.landmarker = vision.PoseLandmarker.create_from_options(options)
        self.frame_idx = 0

    def process_frame(self, frame):
        """
        Process the frame and return the (x, y) coordinates of the pastor's center
        relative to the frame dimensions (normalized 0.0 to 1.0).
        Also returns the modified frame with annotations.
        """
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert to MediaPipe Image format
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        
        # Calculate timestamp for video mode (strictly increasing)
        self.frame_idx += 1
        timestamp_ms = self.frame_idx * 33 # Approximate 30fps
        
        # Process the image and find pose
        results = self.landmarker.detect_for_video(mp_image, timestamp_ms)
        
        center_x, center_y = None, None
        person_height = None
        
        # If landmarks were found
        if results.pose_landmarks and len(results.pose_landmarks) > 0:
            landmarks = results.pose_landmarks[0] # Get first person found
            
            # MediaPipe Pose Landmark Indices:
            # 0: Nose, 11: Left Shoulder, 12: Right Shoulder, 23: Left Hip, 24: Right Hip
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            nose = landmarks[0]
            
            # Primary: Try to use hips and shoulders to find the exact stomach/center of torso
            if left_shoulder.visibility > 0.5 and right_shoulder.visibility > 0.5 and left_hip.visibility > 0.5 and right_hip.visibility > 0.5:
                center_x = (left_shoulder.x + right_shoulder.x + left_hip.x + right_hip.x) / 4
                center_y = (left_shoulder.y + right_shoulder.y + left_hip.y + right_hip.y) / 4
            
            # Secondary: If hips are hidden (behind podium or zoomed in), use shoulders + proportional offset
            elif left_shoulder.visibility > 0.5 and right_shoulder.visibility > 0.5:
                center_x = (left_shoulder.x + right_shoulder.x) / 2
                shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
                
                if nose.visibility > 0.5:
                    # Estimate stomach position based on the distance from head to shoulders
                    # This scales perfectly even when zoomed in!
                    head_to_shoulder = shoulder_y - nose.y
                    center_y = shoulder_y + (head_to_shoulder * 1.5)
                else:
                    center_y = shoulder_y + 0.2 # Arbitrary fallback
                    
            # Fallback: Just nose
            else:
                if nose.visibility > 0.5:
                    center_x = nose.x
                    center_y = nose.y + 0.3 # Arbitrary fallback below head
                    
            h, w, _ = frame.shape
                    
            # Calculate the visible height of the person
            min_y = 1.0
            max_y = 0.0
            for lm in landmarks:
                if lm.visibility > 0.5:
                    if lm.y < min_y: min_y = lm.y
                    if lm.y > max_y: max_y = lm.y
            
            person_height = max_y - min_y if max_y > min_y else None
                    
            # Draw tracking center point
            if center_x is not None and center_y is not None:
                cx, cy = int(center_x * w), int(center_y * h)
                cv2.circle(frame, (cx, cy), 10, (0, 255, 0), cv2.FILLED)

            # Draw basic stick figure/landmarks for visualization
            for lm in landmarks:
                if lm.visibility > 0.5:
                    x, y = int(lm.x * w), int(lm.y * h)
                    cv2.circle(frame, (x, y), 3, (0, 0, 255), -1)

        return frame, (center_x, center_y), person_height

    def release(self):
        self.landmarker.close()
