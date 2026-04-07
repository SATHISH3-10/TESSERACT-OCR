import tkinter as tk
from tkinter import filedialog
import pytesseract
import cv2
import re
import requests
import base64
from gtts import gTTS
import pygame

# 🔴 Tesseract Path
pytesseract.pytesseract.tesseract_cmd = r"C:\Tesseract-OCR\tesseract.exe"

# 🔴 ADD NEW BHASHINI KEY (REGENERATE)
BHASHINI_API_KEY = "your_api"


# -------------------------------
# 1. Select Image
# -------------------------------
def select_image():
    root = tk.Tk()
    root.withdraw()
    return filedialog.askopenfilename(
        title="Select Image",
        filetypes=[("Image Files", "*.png *.jpg *.jpeg")]
    )


# -------------------------------
# 2. Preprocess Image
# -------------------------------
def preprocess_image(path):
    img = cv2.imread(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=1.5, fy=1.5)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    return thresh


# -------------------------------
# 3. OCR (Tamil + English)
# -------------------------------
def extract_text(image):
    return pytesseract.image_to_string(image, lang='eng+tam')


# -------------------------------
# 4. Clean Text (Tamil SAFE)
# -------------------------------
def clean_text(text):
    text = re.sub(r'[^\u0B80-\u0BFFA-Za-z0-9.,!? ]+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# -------------------------------
# 5. Page Detection
# -------------------------------
def is_acknowledgement(text):
    keywords = ["acknowledgement", "thanks", "gratitude", "dedicated"]
    return any(word in text.lower() for word in keywords)


# -------------------------------
# 6. Summary
# -------------------------------
def summarize(text):
    sentences = text.split('.')
    summary = '.'.join(sentences[:2])   # 🔥 reduce size
    return summary[:300]  # 🔥 max 300 chars

# -------------------------------
# 7. Detect Language (Tamil Safe)
# -------------------------------
def detect_language(text):
    # Tamil Unicode range check
    if any('\u0B80' <= c <= '\u0BFF' for c in text):
        return "ta"
    return "en"


# -------------------------------
# 8A. gTTS (English)
# -------------------------------
def gtts_audio(text):
    file = "output.mp3"
    gTTS(text=text, lang='en').save(file)
    return file


# -------------------------------
# 8B. BHASHINI TTS
# -------------------------------
def bhashini_tts(text):
    url = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

    headers = {
        "Authorization": BHASHINI_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "pipelineTasks": [
            {
                "taskType": "tts",
                "config": {
                    "language": {
                        "sourceLanguage": "ta"
                    },
                    "audioConfig": {
                        "samplingRate": 16000
                    }
                }
            }
        ],
        "inputData": {
            "input": [
                {"source": text}
            ]
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data)

        if response.status_code != 200:
            print("❌ API Error:", response.text)
            return None

        result = response.json()

        audio_base64 = result['pipelineResponse'][0]['audio'][0]['audioContent']
        audio_bytes = base64.b64decode(audio_base64)

        file = "output.wav"
        with open(file, "wb") as f:
            f.write(audio_bytes)

        return file

    except Exception as e:
        print("❌ Bhashini Error:", e)
        return None


# -------------------------------
# 9. Play Audio
# -------------------------------
def play_audio(file):
    pygame.init()
    pygame.mixer.init()
    pygame.mixer.music.load(file)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        continue


# -------------------------------
# MAIN
# -------------------------------
def main():
    print("📂 Select Image")
    path = select_image()

    if not path:
        print("❌ No file selected")
        return

    print("🖼 Processing...")
    image = preprocess_image(path)

    print("🔍 OCR Running...")
    text = extract_text(image)
    print("\n📄 Raw Text:\n", text)

    clean = clean_text(text)
    print("\n🧹 Clean Text:\n", clean)

    # Page type
    if is_acknowledgement(clean):
        print("\n📌 Acknowledgement Page Detected")
        final_text = clean
    else:
        print("\n✂ Generating Summary...")
        final_text = summarize(clean)

    print("\n📝 Final Text:\n", final_text)

    # Language detect
    lang = detect_language(final_text)
    print("\n🌍 Language:", lang)

    # Audio
    if lang == "en":
        print("🔊 Using gTTS")
        audio_file = gtts_audio(final_text)

    else:
        print("🔊 Using Bhashini (Tamil)")
        audio_file = bhashini_tts(final_text)

    # 🔥 FALLBACK if Bhashini fails
        if audio_file is None:
            print("⚠ Bhashini failed, using gTTS fallback")
            audio_file = gtts_audio(final_text)
    # Safe play
    if audio_file:
        print("▶ Playing Audio...")
        play_audio(audio_file)
    else:
        print("❌ Audio generation failed")

    print("✅ Done!")


# Run
if __name__ == "__main__":
    main()