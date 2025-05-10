import requests
from PIL import Image
from io import BytesIO
import matplotlib.pyplot as plt

# serp api key 
SERPAPI_KEY = "90fe1cea1cc4c3c6bb28aeaccde3b0bc7d3016b4be3de14932b8c661bc1205b5"

# test prompt
# prompt = "neural network"

def show_image(image, title="Generated Image"):
    plt.imshow(image)
    plt.axis('off')
    plt.title(title)
    plt.show()

def fetch_image_serpapi(query):
    params = {
        "q": query,
        "tbm": "isch",
        "ijn": "0",
        "api_key": SERPAPI_KEY
    }
    response = requests.get("https://serpapi.com/search.json", params=params)
    data = response.json()

    if "images_results" in data:
        first_image_url = data["images_results"][0]["original"]
        image = Image.open(BytesIO(requests.get(first_image_url).content))
        # return image
        show_image(image, title = query)
    else:
        print("No images found from SerpAPI.")

def fetch_image(prompt):
    try:
        image = fetch_image_serpapi(prompt)
    except Exception as e:
        print(f"SerpAPI failed: {e}")
        return
    return image

# fetch_image(prompt)
