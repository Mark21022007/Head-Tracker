import cv2

print("Opening cameras 0-4. Press 'q' to quit the window when you find the right one.")
caps = []
for i in range(5):
    # Try with DSHOW since we know it prevents hanging
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if cap.isOpened():
        caps.append((i, cap))

while True:
    frames = []
    for i, cap in caps:
        ret, frame = cap.read()
        if ret and frame is not None:
            # Resize frame for displaying in a grid
            frame = cv2.resize(frame, (320, 240))
            cv2.putText(frame, f"Cam {i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            frames.append(frame)
        else:
            # Create a black frame if read fails
            import numpy as np
            black = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.putText(black, f"Cam {i} Failed", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            frames.append(black)

    if not frames:
        print("No cameras could be read.")
        break
        
    # Combine frames side-by-side
    import numpy as np
    combined = np.hstack(frames)
    
    cv2.imshow("Camera Test - Press Q to Quit", combined)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

for _, cap in caps:
    cap.release()
cv2.destroyAllWindows()
