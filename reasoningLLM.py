"""Financial assistant that captures screen regions and provides AI-powered budget advice."""

from google import genai
from google.genai import types
from pathlib import Path
import numpy as np
import cv2
import mss
from pynput import mouse, keyboard
import json
from google.genai import types
from datetime import date


# Configuration
CROP_SIZE = 400
MONITOR = 1
API_KEY = "AIzaSyB5bbAoEbVsZRpA2KtqxqdtEpa54fvmTEI"
MODEL = "models/gemini-2.5-flash"

# Initialize and create screenshots folder if it doesn't exist
screenshots_dir = Path("screenshots")
screenshots_dir.mkdir(exist_ok=True)
expenses_file = Path("expenses.json")
client = genai.Client(api_key=API_KEY)
listener = None  # Global listener reference


def capture_cursor_region(x, y):
    """Capture a region around the cursor position and save it."""
    with mss.mss() as sct:
        monitor = sct.monitors[MONITOR]
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)

        # Calculate crop boundaries
        # left = int(max(x - CROP_SIZE // 2, 0))
        # top = int(max(y - CROP_SIZE // 2, 0))
        # right = int(min(left + CROP_SIZE, img.shape[1]))
        # bottom = int(min(top + CROP_SIZE, img.shape[0]))

        # crop_img = img[top:bottom, left:right]

        # Save cropped image
        screenshot_num = get_next_screenshot_number()
        filename = screenshots_dir / f"screen{screenshot_num}.png"
        cv2.imwrite(str(filename), img)
        print(f"Screenshot saved: {filename}")
        return str(filename)


def send_to_gemini(image_path):
    """Send image to Gemini for financial analysis and get advice."""
    extraction_prompt = """You are a financial assistant analyzing a product/shopping screenshot.

**TASK: Extract ALL financial and product information**

Look for:
- Product names, model numbers, descriptions
- Prices (individual items and totals)
- Quantities
- Store names
- Any monetary values visible

**REQUIRED OUTPUT: Return ONLY valid JSON, nothing else:**

{
  "items": [
    {"name": "exact product name/description", "price": numerical_value},
    {"name": "another product", "price": numerical_value}
  ],
  "total": numerical_total_or_0,
  "category": "shopping|food|electronics|appliances|other",
  "description": "specific description of what products are shown"
}

**CRITICAL RULES:**
- Extract ACTUAL text and prices you see - do not guess
- If you see a product, capture its name and price exactly as shown
- Total should be the sum of items or final price visible
- Return only the JSON object, no other text"""

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

    raw_response = response.text.strip()
    print(f"\nDEBUG - Raw Gemini response:\n{raw_response}\n")
    
    # Try to clean and parse the response
    # Remove markdown code blocks if present
    if raw_response.startswith("```"):
        raw_response = raw_response.split("```")[1]
        if raw_response.startswith("json"):
            raw_response = raw_response[4:]
        print(f"DEBUG - After stripping markdown:\n{raw_response}\n")
    
    try:
        extracted_data = json.loads(raw_response)
        print(f"DEBUG - Successfully parsed JSON: {json.dumps(extracted_data, indent=2)}\n")
    except json.JSONDecodeError as e:
        print(f"DEBUG - Failed to parse JSON: {e}\n")
        print(f"DEBUG - Attempted to parse: {raw_response}\n")
        extracted_data = {
            "items": [],
            "total": 0,
            "category": "error",
            "description": "Failed to parse model response",
            "raw_response": raw_response
        }

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


def add_expense_to_history(extracted_data):
    """Add expense data to the expenses history JSON file."""
    try:
        with open(expenses_file, "r") as f:
            expenses = json.load(f)
    except FileNotFoundError:
        expenses = []
    
    expense_entry = {
        "date": str(date.today()),
        "hour": date.today().strftime("%H:%M:%S"),
        "total": extracted_data.get("total", 0),
        "category": extracted_data.get("category", ""),
        "description": extracted_data.get("description", ""),
        "items": extracted_data.get("items", [])
    }
    
    expenses.append(expense_entry)
    
    with open(expenses_file, "w") as f:
        json.dump(expenses, f, indent=2)
    
    print(f"✓ Expense saved to {expenses_file}")


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
        
        # Save to expense history
        add_expense_to_history(result["extracted_data"])


def on_key_press(key):
    """Handle keyboard key press events."""
    global listener
    try:
        if key == keyboard.Key.esc:
            print("\n\nESC pressed → Exiting...")
            listener.stop()
            return False
    except AttributeError:
        pass


if __name__ == "__main__":
    print("Financial Assistant Running")
    print("- Click anywhere to analyze")
    print("- Press ESC to exit\n")
    
    mouse_listener = mouse.Listener(on_click=on_click)
    keyboard_listener = keyboard.Listener(on_press=on_key_press)
    listener = keyboard_listener  # Store reference for ESC handler
    
    mouse_listener.start()
    keyboard_listener.start()
    
    keyboard_listener.join()
