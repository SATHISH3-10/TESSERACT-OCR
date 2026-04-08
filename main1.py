import cv2
import pytesseract
import numpy as np
import time
import requests
import re
import os
from gtts import gTTS
import pygame

# ---------------- CONFIG ----------------
pytesseract.pytesseract.tesseract_cmd = r"C:\Tesseract-OCR\tesseract.exe"
OPENROUTER_API_KEY = "YOUR_OPENROUTER_KEY"

# ---------------- AUDIO CONTROL ----------------
last_audio_time = 0

def play_audio(text, filename, lang='en', wait=True):
    global last_audio_time

    if not text.strip():
        return

    # 🔥 prevent spam
    if time.time() - last_audio_time < 2:
        return

    try:
        last_audio_time = time.time()

        # 🔥 stop previous audio
        try:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except:
            pass

        time.sleep(0.2)

        # 🔥 delete file safely
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except:
                pass

        gTTS(text=text, lang=lang).save(filename)

        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()

        if wait:
            while pygame.mixer.music.get_busy():
                time.sleep(0.3)

    except Exception as e:
        print("❌ Audio error:", e)

# ---------------- CLEAN TEXT ----------------
def clean_text(text):
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'[^\u0B80-\u0BFFA-Za-z0-9.,!? ]+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def is_valid_text(text):
    return len(text.split()) > 8

def detect_language(text):
    if any('\u0B80' <= c <= '\u0BFF' for c in text):
        return 'ta'
    return 'en'

# ---------------- LLM ----------------
def llm_summary(text):
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "Smart Camera AI"
            },
            json={
                "model": "openrouter/auto",
                "messages": [{"role": "user", "content": f"Summarize:\n{text}"}],
                "max_tokens": 120
            },
            timeout=15
        )
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"]
    except:
        pass
    return None

# ---------------- BLUR ----------------
def is_blurry(gray):
    return cv2.Laplacian(gray, cv2.CV_64F).var() < 80

# ---------------- PAGE DETECTION ----------------
def detect_page(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.convertScaleAbs(gray, alpha=1.8, beta=30)

    blur = cv2.GaussianBlur(gray, (5,5), 0)
    edges = cv2.Canny(blur, 30, 200)

    edges = cv2.dilate(edges, None, iterations=2)
    edges = cv2.erode(edges, None, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)

    if w*h < 30000:
        return None

    return (x, y, w, h)

# ---------------- SAME PAGE ----------------
def is_same_page(prev, curr):
    if prev is None:
        return False

    prev = cv2.resize(prev, (200,200))
    curr = cv2.resize(curr, (200,200))

    diff = np.mean(cv2.absdiff(prev, curr))
    return diff < 15

# ---------------- MAIN ----------------
def main():
    cap = cv2.VideoCapture(0)

    prev_page = None
    state = "READY"

    stable_start = None
    last_capture = 0
    cooldown = 4

    last_guidance = ""

    print("📷 Smart AI Camera Started (Press Q to Exit)")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display = frame.copy()
        page = detect_page(frame)

        if page:
            x, y, w, h = page
            cv2.rectangle(display, (x,y), (x+w,y+h), (0,255,0), 2)

            roi = frame[y:y+h, x:x+w]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

            # -------- GUIDANCE --------
            center_x = x + w//2
            center_y = y + h//2

            frame_cx = frame.shape[1]//2
            frame_cy = frame.shape[0]//2

            frame_area = frame.shape[0] * frame.shape[1]
            page_area = w * h

            message = ""

            if center_x < frame_cx - 80:
                message = "Move Right"
            elif center_x > frame_cx + 80:
                message = "Move Left"
            elif center_y < frame_cy - 80:
                message = "Move Down"
            elif center_y > frame_cy + 80:
                message = "Move Up"
            elif page_area < frame_area * 0.3:
                message = "Move Closer"
            elif page_area > frame_area * 0.9:
                message = "Move Back"
            elif is_blurry(gray):
                message = "Hold Steady, Not Clear"

            if message != "":
                stable_start = None
                cv2.putText(display, message, (30,50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

                if message != last_guidance:
                    print("🔊 Guide:", message)
                    play_audio(message, "guide_audio.mp3", "en", wait=False)
                    last_guidance = message
            else:
                last_guidance = ""

                # -------- STABLE --------
                if stable_start is None:
                    stable_start = time.time()

                elapsed = time.time() - stable_start

                cv2.putText(display, f"Hold Still: {int(elapsed)}s",
                            (30,50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

                # -------- CAPTURE --------
                if elapsed >= 2 and time.time() - last_capture > cooldown:

                    print("📸 Capturing page...")
                    stable_start = None
                    last_capture = time.time()

                    center = roi[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]

                    if is_same_page(prev_page, center):
                        print("⚠ Same page")
                        play_audio("Please move to next page", "guide_audio.mp3")
                        state = "WAIT_NEW"
                        continue

                    prev_page = center.copy()

                    # OCR
                    proc = cv2.adaptiveThreshold(
                        gray, 255,
                        cv2.ADAPTIVE_THRESH_MEAN_C,
                        cv2.THRESH_BINARY,
                        15, 5
                    )

                    text = pytesseract.image_to_string(proc, lang='eng+tam')
                    clean = clean_text(text)

                    if not is_valid_text(clean):
                        print("❌ Text not clear")
                        play_audio("Text not clear adjust page", "guide_audio.mp3")
                        continue

                    print("\n📄 Text:", clean[:200])

                    summary = llm_summary(clean)
                    if not summary:
                        summary = clean[:200]

                    print("\n📝 Summary:", summary)

                    lang = detect_language(summary)
                    play_audio(summary, "read_audio.mp3", lang)

                    print("📖 Done. Show next page.")
                    play_audio("Reading complete show next page", "guide_audio.mp3")

                    state = "WAIT_NEW"

        else:
            stable_start = None
            cv2.putText(display, "Show Page", (30,50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

            if last_guidance != "Show page":
                play_audio("Show page to camera", "guide_audio.mp3", wait=False)
                last_guidance = "Show page"

        # -------- WAIT NEW PAGE --------
        if state == "WAIT_NEW" and page:
            center = roi[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]
            if not is_same_page(prev_page, center):
                print("✅ New page detected")
                play_audio("New page detected", "guide_audio.mp3")
                state = "READY"

        cv2.imshow("Smart AI Reader", display)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("🛑 Stopping...")
            play_audio("Stopping system", "guide_audio.mp3")
            break

    cap.release()
    cv2.destroyAllWindows()
    pygame.mixer.quit()

# ---------------- RUN ----------------
if __name__ == "__main__":
    main()