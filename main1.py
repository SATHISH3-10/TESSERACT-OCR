import tkinter as tk
from tkinter import filedialog
import os
import sys
import pytesseract
import cv2
import re
import requests
from gtts import gTTS
import pygame
import time

def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        print("⚠ Could not read .env:", e)


load_dotenv()

# 🔴 Tesseract Path
pytesseract.pytesseract.tesseract_cmd = r"C:\Tesseract-OCR\tesseract.exe"

# 🔴 OPENROUTER API KEY
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


def check_openrouter_key():
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "OCR LLM Project"
    }
    data = {
        "model": "openrouter/auto",
        "messages": [{"role": "user", "content": "Reply only with: OK"}],
        "max_tokens": 5,
    }

    if not OPENROUTER_API_KEY:
        print("❌ OPENROUTER_API_KEY not set")
        return False

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            print("✅ OpenRouter key is working")
            return True

        print(f"❌ OpenRouter key check failed ({response.status_code})")
        print(response.text)
        return False
    except Exception as e:
        print("❌ Key check error:", e)
        return False


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
# 3. OCR
# -------------------------------
def extract_text(image):
    return pytesseract.image_to_string(image, lang='eng+tam')


# -------------------------------
# 4. Clean Text
# -------------------------------
def clean_text(text):
    text = re.sub(r'[^\u0B80-\u0BFFA-Za-z0-9.,!? ]+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# -------------------------------
# 5. LLM SUMMARY (OpenRouter)
# -------------------------------
def llm_summary(text):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "OCR LLM Project"
    }

    prompt = f"""
Summarize the following text clearly and shortly.
If the text is Tamil, keep summary in Tamil.

Text:
{text}
"""

    data = {
        "model": "openrouter/auto",   # 🔥 FIXED
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 150
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=20)

        if response.status_code != 200:
            print("❌ LLM API Error:", response.text)
            return None

        result = response.json()
        return result["choices"][0]["message"]["content"]

    except Exception as e:
        print("❌ LLM Error:", str(e))
        return None

# -------------------------------
# 6. Basic Summary (Fallback)
# -------------------------------
def basic_summary(text):
    sentences = text.split('.')
    summary = '.'.join(sentences[:2])
    return summary[:300]


# -------------------------------
# 7. Language Detection
# -------------------------------
def detect_language(text):
    if any('\u0B80' <= c <= '\u0BFF' for c in text):
        return "ta"
    return "en"


# -------------------------------
# 8. Text to Speech
# -------------------------------
def generate_audio(text, lang):
    file = "output.mp3"
    try:
        gTTS(text=text, lang=lang).save(file)
        return file
    except Exception as e:
        print("❌ Audio Error:", e)
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
        time.sleep(0.5)


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

    print("\n🧠 Generating Smart Summary (LLM)...")
    final_text = llm_summary(clean)

    # 🔥 fallback
    if not final_text:
        print("⚠ LLM failed, using basic summary")
        final_text = basic_summary(clean)

    print("\n📝 Final Summary:\n", final_text)

    lang = detect_language(final_text)
    print("\n🌍 Language:", lang)

    audio_file = generate_audio(final_text, lang)

    if audio_file:
        print("▶ Playing Audio...")
        play_audio(audio_file)
    else:
        print("❌ Audio failed")

    print("✅ Done!")


# Run
if __name__ == "__main__":
    if "--check-key" in sys.argv:
        check_openrouter_key()
        sys.exit(0)
    main()