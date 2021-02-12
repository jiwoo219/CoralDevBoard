import numpy as np
import argparse
import cv2
from glob import glob
from os.path import sep
from edgetpu.detection.engine import DetectionEngine

def resize_to_square(img, size, keep_aspect_ratio=False, interpolation=cv2.INTER_AREA):
    # Resize image to square shape.
    (h, w) = img.shape[:2]

    if h == w or keep_aspect_ratio == False:
        return cv2.resize(img, (size, size), interpolation)

    # Check if image is color. 
    chan = None if len(img.shape) < 3 else img.shape[2]

    # Determine size of black mask.
    mask_size = h if h > w else w

    if chan is None:
        mask = np.zeros((mask_size, mask_size), dtype=img.dtype)
        mask[:h, :w] = img[:h, :w]
    else:
        mask = np.zeros((mask_size, mask_size, chan), dtype=img.dtype)
        mask[:h, :w, :] = img[:h, :w, :]

    return cv2.resize(mask, (size, size), interpolation)

def tpu_face_det(image):
    # Detect faces using TPU engine.
    CONFIDENCE_THRES = 0.05
    
    # Resize image for face detection.
    # The tpu face det model used requires (320, 320).
    res = resize_to_square(img=image, size=320, keep_aspect_ratio=True,
        interpolation=cv2.INTER_AREA)

    detection = face_engine.DetectWithInputTensor(input_tensor=res.reshape(-1),
        threshold=CONFIDENCE_THRES, top_k=1)

    if not detection:
        print('*** no face found! ***')
        return None

    box = (detection[0].bounding_box.flatten().tolist()) * np.array([w, h, w, h])
    (face_left, face_top, face_right, face_bottom) = box.astype('int')

    # Return bounding box coords in dlib format. 
    return [(face_top, face_right, face_bottom, face_left)]

def cv2_encoder(image, boxes):
    # Carve out face from bbox.
    (face_top, face_right, face_bottom, face_left) = boxes[0]
    face_roi = image[face_top:face_bottom, face_left:face_right, :]

    faceBlob = cv2.dnn.blobFromImage(
        face_roi, 1.0 / 255, (96, 96), (0, 0, 0), swapRB=True, crop=False)
    embedder.setInput(faceBlob)

    encoding = embedder.forward()[0]

    return encoding

if __name__ == '__main__':
    import argparse
    import signal
    import time
    import os

    ap = argparse.ArgumentParser()
    ap.add_argument("inputfile",
                    help="video file to detect or '0' to detect from web cam")
    ap.add_argument("-t", "--threshold", default=0.4, type=float,
                    help="threshold of the similarity (default=0.44)")
    ap.add_argument("-S", "--seconds", default=1, type=float,
                    help="seconds between capture")
    ap.add_argument("-s", "--stop", default=0, type=int,
                    help="stop detecting after # seconds")
    ap.add_argument("-k", "--skip", default=0, type=int,
                    help="skip detecting for # seconds from the start")
    ap.add_argument("-d", "--display", action='store_true',
                    help="display the frame in real time")
    ap.add_argument("-c", "--capture", type=str,
                    help="save the frames with face in the CAPTURE directory")
    ap.add_argument("-r", "--resize-ratio", default=1.0, type=float,
                    help="resize the frame to process (less time, less accuracy)")
    args = ap.parse_args()

    src_file = args.inputfile
    if src_file == "0":
        src_file = 0

    DET_MODEL_PATH = './mobilenet_ssd_v2_face_quant_postprocess_edgetpu.tflite'
    face_engine = DetectionEngine(DET_MODEL_PATH)

    src = cv2.VideoCapture(src_file)
    if not src.isOpened():
        print("cannot open inputfile", src_file)
        exit(1)

    while True:
        ret, frame = src.read()

        print('...finding face in image')
        boxes = tpu_face_det(frame)

        if boxes is None:
            continue

        print('...encoding face')
        encoding = cv2_encoder(frame, boxes)

        print(encoding)

        if key == ord("q"):
            break
    
    cv2.destroyAllWindows()
    print('finish')