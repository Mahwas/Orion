"""Financial assistant that captures screen regions and provides AI-powered budget advice."""

from google import genai
from google.genai import types
from pathlib import Path
import numpy as np
import cv2
import mss
from pynput import mouse
import json
from google.genai import types


# Configuration
CROP_SIZE = 400
MONITOR = 1
API_KEY = "AIzaSyB5bbAoEbVsZRpA2KtqxqdtEpa54fvmTEI"
MODEL = "models/gemini-2.5-flash"

# Initialize and create screenshots folder if it doesn't exist
screenshots_dir = Path("screenshots")
screenshots_dir.mkdir(exist_ok=True)
client = genai.Client(api_key=API_KEY)


def capture_cursor_region(x, y):
    """Capture a region around the cursor position and save it."""
    with mss.mss() as sct:
        monitor = sct.monitors[MONITOR]
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)

        # Calculate crop boundaries
        left = int(max(x - CROP_SIZE // 2, 0))
        top = int(max(y - CROP_SIZE // 2, 0))
        right = int(min(left + CROP_SIZE, img.shape[1]))
        bottom = int(min(top + CROP_SIZE, img.shape[0]))

        crop_img = img[top:bottom, left:right]

        # Save cropped image
        screenshot_num = get_next_screenshot_number()
        filename = screenshots_dir / f"screen{screenshot_num}.png"
        cv2.imwrite(str(filename), crop_img)
        print(f"Screenshot saved: {filename}")
        return str(filename)


def send_to_gemini(image_path):
    """Send image to Gemini for financial analysis and get advice."""
    extraction_prompt = """You are a financial assistant. Analyze this image of a screen region.

Extract:
- transactions
- prices
- category
- short description

Output ONLY valid JSON:
{ "items": [], "total": 0, "category": "", "description": "" }"""

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # Extract financial data from image
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(text=extraction_prompt),
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="image/png",
                            data=image_bytes
                        )
                    )
                ],
            )
        ],
    )

    try:
        extracted_data = json.loads(response.text.strip())
    except json.JSONDecodeError:
        extracted_data = {"raw_response": response.text}

    # Get AI advice based on extracted data
    advice_prompt = f"""Based on this financial data extracted from a screenshot:
{json.dumps(extracted_data)}

Provide:
1. Budget advice
2. Spending pattern insights
3. Recommendations to save money

Be concise and actionable."""

    advice_response = client.models.generate_content(
        model=MODEL,
        contents=[advice_prompt]
    )

    return {
        "extracted_data": extracted_data,
        "gemini_advice": advice_response.text
    }


def get_next_screenshot_number():
    """Get the next available screenshot number."""
    existing_files = list(screenshots_dir.glob("screen*.png"))
    if not existing_files:
        return 1
    numbers = [int(f.stem.replace("screen", "")) for f in existing_files]
    return max(numbers) + 1


def on_click(x, y, button, pressed):
    """Handle mouse click events."""
    if pressed:
        print(f"Clicked at {x},{y} → capturing region")
        image_path = capture_cursor_region(x, y)
        result = send_to_gemini(image_path)

        print("\n" + "=" * 60)
        print("EXTRACTED DATA:")
        print("=" * 60)
        print(json.dumps(result["extracted_data"], indent=2))
        print("\n" + "=" * 60)
        print("GEMINI ADVICE & PREDICTIONS:")
        print("=" * 60)
        print(result["gemini_advice"])
        print("=" * 60 + "\n")


if __name__ == "__main__":
    print("Financial Assistant Running - Click anywhere to analyze...")
    with mouse.Listener(on_click=on_click) as listener:
        listener.join()
