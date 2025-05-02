import cv2
import numpy as np
import easyocr
from pix2tex.cli import LatexOCR
from PIL import Image
import pytesseract
import os

# Initialize OCR tools
text_reader = easyocr.Reader(['en'])
formula_reader = LatexOCR()

def is_image_blurry(image, threshold=100.0):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return variance < threshold

def preprocess_image(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image path '{image_path}' does not exist.")

    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Could not load image. Make sure it's a valid image file and format.")

    if is_image_blurry(image):
        raise ValueError("Image is too blurry for OCR.")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    return image, gray

def detect_text_boxes(image):
    try:
        results = text_reader.detect(image)[0]
    except Exception as e:
        raise RuntimeError(f"Text detection failed: {e}")
    boxes = [box.tolist() for box in results]
    return boxes

def recognize_text(image, boxes):
    results = []
    for box in boxes:
        x_min = max(0, int(min([point[0] for point in box])))
        y_min = max(0, int(min([point[1] for point in box])))
        x_max = min(image.shape[1], int(max([point[0] for point in box])))
        y_max = min(image.shape[0], int(max([point[1] for point in box])))

        if x_max <= x_min or y_max <= y_min:
            continue  # Skip invalid boxes

        cropped = image[y_min:y_max, x_min:x_max]
        pil_img = Image.fromarray(cropped)

        # Attempt text OCR
        try:
            text_result = text_reader.readtext(cropped, detail=0)
            text = " ".join(text_result).strip()
            if not text:
                raise ValueError("Empty text")
        except:
            # Attempt math OCR
            try:
                text = formula_reader(pil_img)
            except Exception as e:
                text = "[Math OCR Error]"

        results.append((x_min, y_min, text))

    # Sort results top-to-bottom, then left-to-right
    results.sort(key=lambda x: (x[1], x[0]))
    return [text for _, _, text in results]

def process_image(image_path):
    image, gray = preprocess_image(image_path)
    boxes = detect_text_boxes(gray)
    texts = recognize_text(image, boxes)
    return "\n".join(texts)



try:
    output = process_image()
    print("\nExtracted Text:\n")
    print(output)
except Exception as e:
    print(f"Error: {e}")
