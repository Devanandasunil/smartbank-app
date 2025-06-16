import cv2
import face_recognition

def capture_face_encoding():
    video_capture = cv2.VideoCapture(0)
    if not video_capture.isOpened():
        print("Camera not detected.")
        return None

    print("[INFO] Capturing face. Press 'q' to cancel.")

    encoding = None
    while True:
        ret, frame = video_capture.read()
        if not ret:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)

        if face_locations:
            encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            if encodings:
                encoding = encodings[0]
                print("[INFO] Face encoding captured.")
                break

        cv2.imshow('Face Authentication', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video_capture.release()
    cv2.destroyAllWindows()
    return encoding
