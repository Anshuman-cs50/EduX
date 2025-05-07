import cv2
import easyocr
from pix2tex.cli import LatexOCR
from PIL import Image
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
    boxes = [box for box in results]
    return boxes

def is_math_block(image_crop):
    try:
        # Try to recognize with Pix2Tex, return True if successful
        pil_img = Image.fromarray(image_crop)
        formula = formula_reader(pil_img)
        return True if formula.strip() else False
    except:
        return False

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

        try:
            text_result = text_reader.readtext(cropped, detail=0)
            text = " ".join(text_result).strip()
        except:
            text = "[Text OCR Error]"

        results.append((y_min, x_min, text))

    # Sort results top-to-bottom, then left-to-right
    results.sort(key=lambda x: (x[0], x[1]))
    return [text for _, _, text in results]

def process_image(image_path):
    image, gray = preprocess_image(image_path)
    boxes = detect_text_boxes(gray)
    texts = recognize_text(image, boxes)
    return "\n".join(texts)

if __name__ == "__main__":
    try:
        image_path = "image.png"  # Replace with actual path
        output = process_image(image_path)
        print("\nExtracted Text:\n")
        print(output)
    except Exception as e:
        print(f"Error: {e}")
