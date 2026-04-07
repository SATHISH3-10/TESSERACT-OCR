from PIL import Image
import pytesseract
import os
from tkinter import Tk, filedialog
from gtts import gTTS
import pygame
import re

# -------------------------------
# STEP 1: Configure Tesseract
# -------------------------------
pytesseract.pytesseract.tesseract_cmd = r"C:\Tesseract-OCR\tesseract.exe"
os.environ['TESSDATA_PREFIX'] = r"C:\Tesseract-OCR\tessdata"

# -------------------------------
# STEP 2: Select Image
# -------------------------------
Tk().withdraw()
image_path = filedialog.askopenfilename(
    title="Select Image",
    filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")]
)

if not image_path:
    print("❌ No image selected")
    exit()

# -------------------------------
# STEP 3: OCR
# -------------------------------
image = Image.open(image_path)

custom_config = r'--oem 3 --psm 6'
text = pytesseract.image_to_string(image, lang='tam+eng', config=custom_config)

print("\n📄 Extracted Text:\n")
print(text)

# -------------------------------
# STEP 4: SMART SUMMARY (FIXED)
# -------------------------------

# -------------------------------
# STEP 4: SMART CLEAN SUMMARY (FINAL)
# -------------------------------

# 1. Clean text
clean_text = text.replace('\n', ' ')
clean_text = re.sub(r'\s+', ' ', clean_text)

# ❗ Remove page numbers & unwanted symbols
clean_text = re.sub(r'\b\d+\b', '', clean_text)   # remove numbers
clean_text = re.sub(r'[^\u0B80-\u0BFFa-zA-Z.,!? ]', '', clean_text)  # keep Tamil + basic punctuation

# 2. Split sentences
sentences = re.split(r'[.!?]', clean_text)

# 3. Filter meaningful sentences
filtered = []
for s in sentences:
    s = s.strip()
    
    word_count = len(s.split())
    
    # Keep only good sentences
    if (
        10 <= word_count <= 25 and   # ideal length
        s.count(',') < 3 and         # not too complex
        not any(char.isdigit() for char in s) and  # no numbers
        len(s) > 60                  # avoid broken lines
    ):
        filtered.append(s)

# 4. Avoid first noisy lines (titles/headers)
filtered = filtered[1:]

# 5. Final selection
if len(filtered) >= 2:
    summary = ". ".join(filtered[:2]) + "."
else:
    summary = ". ".join(sentences[:2]) + "."

print("\n✨ Summary:\n")
print(summary)
# -------------------------------
# STEP 5: Detect Language
# -------------------------------
if any('\u0B80' <= c <= '\u0BFF' for c in summary):
    lang = 'ta'
else:
    lang = 'en'

# -------------------------------
# STEP 6: Convert to Audio
# -------------------------------
audio_file = "summary.mp3"

try:
    tts = gTTS(summary, lang=lang)
    tts.save(audio_file)
except Exception as e:
    print("❌ Audio generation failed:", e)
    exit()

# -------------------------------
# STEP 7: Play Audio
# -------------------------------
print("\n🔊 Playing Audio...")

pygame.mixer.init()
pygame.mixer.music.load(audio_file)
pygame.mixer.music.play()

while pygame.mixer.music.get_busy():
    continue