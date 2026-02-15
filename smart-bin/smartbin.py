import cv2
import numpy as np
from PIL import Image
import tensorflow as tf
import serial
import time
import json
from datetime import datetime
import winsound  # Simple beeps for Windows

# Configuration
MODEL_PATH = "models/model_unquant.tflite"
LABELS_PATH = "models/labels.txt"
DEVICE_INDEX = 1
PICO_PORT = "COM5"
CONFIDENCE_THRESHOLD = 0.70
LED_HOLD_TIME = 5.0
AUTO_CLASSIFY_INTERVAL = 2.0
STATS_FILE = "waste_stats.json"

# Environmental impact data (per item)
ENVIRONMENTAL_IMPACT = {
    "recycle": {
        "co2_saved_kg": 0.8,
        "water_saved_l": 15,
        "energy_saved_kwh": 2.5,
        "trees_equivalent": 0.02,
        "facts": [
            "Recycling 1 ton of plastic saves 16.3 barrels of oil",
            "Recycled aluminum uses 95% less energy than new",
            "1 recycled plastic bottle saves enough energy to power a light bulb for 3 hours"
        ]
    },
    "compost": {
        "co2_saved_kg": 0.5,
        "water_saved_l": 8,
        "energy_saved_kwh": 1.2,
        "trees_equivalent": 0.01,
        "facts": [
            "Composting reduces methane emissions by 50%",
            "Compost enriches soil and reduces need for chemical fertilizers",
            "Food waste in landfills produces harmful greenhouse gases"
        ]
    },
    "hazard": {
        "co2_saved_kg": 0.3,
        "water_saved_l": 5,
        "energy_saved_kwh": 0.8,
        "trees_equivalent": 0.005,
        "facts": [
            "Proper battery disposal prevents toxic chemicals from contaminating soil",
            "1 battery can contaminate 600,000 liters of water",
            "Electronic waste contains valuable materials that can be recovered"
        ]
    },
    "landfill": {
        "co2_saved_kg": 0.0,
        "water_saved_l": 0,
        "energy_saved_kwh": 0,
        "trees_equivalent": 0,
        "facts": [
            "This item cannot be recycled or composted",
            "Consider choosing reusable alternatives next time",
            "Reducing landfill waste starts with better purchasing choices"
        ]
    }
}

# Common wishcycling mistakes - items people think are recyclable but aren't
WISHCYCLING_DATABASE = {
    "greasy pizza box": {"correct": "compost", "wishcycled_as": "recycle", 
                         "explanation": "Grease contaminates recycling. Clean boxes can be recycled, greasy ones go to compost or landfill."},
    "plastic bag": {"correct": "landfill", "wishcycled_as": "recycle",
                    "explanation": "Plastic bags jam recycling machines. Return to grocery stores for special recycling."},
    "styrofoam": {"correct": "landfill", "wishcycled_as": "recycle",
                  "explanation": "Most facilities can't recycle styrofoam. Look for reusable alternatives."},
    "coffee cup": {"correct": "landfill", "wishcycled_as": "recycle",
                   "explanation": "Paper cups have plastic lining that can't be recycled. Use a reusable mug!"},
    "plastic utensils": {"correct": "landfill", "wishcycled_as": "recycle",
                         "explanation": "Too small and contaminated. Single-use plastics rarely recycle. Choose reusable!"},
    "glass mirror": {"correct": "hazard", "wishcycled_as": "recycle",
                     "explanation": "Mirrors have different melting point than bottles. Take to special glass recycling."},
    "shredded paper": {"correct": "compost", "wishcycled_as": "recycle",
                       "explanation": "Pieces too small for recycling machines. Compost clean paper or use as packing."},
}

# Educational content focused on habit building
EDUCATIONAL_CONTENT = {
    "recycle": [
        "CLEAN, DRY, EMPTY - The recycling golden rule!",
        "When in doubt, check! Contamination ruins entire batches",
        "Greasy = Not recyclable. Pizza boxes with cheese go to compost",
        "Caps OFF bottles. Machines can't handle attached caps",
        "Plastic bags? Return to grocery stores, not curbside bins"
    ],
    "compost": [
        "Food scraps + yard waste = nutrient-rich soil!",
        "NO meat, dairy, or oils in home composting",
        "Composting reduces landfill methane by 50%",
        "Coffee grounds, tea bags, fruit peels - all compostable!",
        "Even paper towels and napkins can be composted"
    ],
    "hazard": [
        "Batteries contain toxic metals - NEVER trash them",
        "Electronics, paint, chemicals need special handling",
        "1 battery can contaminate 600,000 liters of water",
        "Find local hazardous waste drop-off locations",
        "Fluorescent bulbs contain mercury - handle with care"
    ],
    "landfill": [
        "Can't recycle this? Think: Can I REDUCE or REUSE instead?",
        "Landfill is last resort - prevention is key",
        "Contaminated items ruin entire recycling batches",
        "Mixed materials (chip bags) can't be separated",
        "Your purchasing choices matter - choose less packaging!"
    ]
}

# Initialize voice engine
def play_success_sound():
    """Play happy beep for successful classification"""
    try:
        winsound.Beep(800, 200)  # 800 Hz for 200ms - happy tone
    except:
        pass  # Silently fail if sound not available

def play_uncertain_sound():
    """Play alert beep for uncertain classification"""
    try:
        winsound.Beep(400, 300)  # 400 Hz for 300ms - lower warning tone
    except:
        pass

# Load or initialize stats
def load_stats():
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "total_items": 0,
            "recycle": 0,
            "compost": 0,
            "hazard": 0,
            "landfill": 0,
            "uncertain": 0,
            "total_co2_saved": 0.0,
            "total_water_saved": 0.0,
            "total_energy_saved": 0.0,
            "total_trees": 0.0,
            "session_start": datetime.now().isoformat(),
            "current_streak": 0,
            "best_streak": 0,
            "contamination_prevented": 0,
            "last_sort_time": None
        }

def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)

stats = load_stats()

# Load labels
with open(LABELS_PATH, "r") as f:
    labels = []
    for line in f.readlines():
        label = line.strip()
        if ' ' in label:
            label = label.split(' ', 1)[1]
        labels.append(label)

# Initialize TFLite model
interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()
in_det = interpreter.get_input_details()[0]
out_det = interpreter.get_output_details()[0]
H, W = in_det["shape"][1], in_det["shape"][2]

# Connect to Pico
print(f"Connecting to Pico on {PICO_PORT}...")
ser = serial.Serial(PICO_PORT, 115200, timeout=1)
time.sleep(2)

if ser.in_waiting:
    response = ser.readline().decode().strip()
    print(f"Pico says: {response}")

# Colors
COLORS = {
    "recycle": (0, 191, 255),
    "compost": (34, 139, 34),
    "hazard": (255, 69, 0),
    "landfill": (128, 128, 128),
    "unknown": (255, 255, 0)
}

def predict(frame_bgr):
    rgb = frame_bgr[:, :, ::-1]
    img = Image.fromarray(rgb).resize((W, H))
    x = np.array(img).astype(np.float32) / 255.0
    x = np.expand_dims(x, axis=0)

    interpreter.set_tensor(in_det["index"], x)
    interpreter.invoke()
    y = interpreter.get_tensor(out_det["index"])[0]

    idx = int(np.argmax(y))
    return labels[idx], float(y[idx]), y

def update_stats(label, confidence):
    """Update environmental impact statistics and habit-building metrics"""
    global stats

    stats["total_items"] += 1

    if confidence >= CONFIDENCE_THRESHOLD:
        category = label.lower()
        stats[category] = stats.get(category, 0) + 1

        # Add environmental impact
        impact = ENVIRONMENTAL_IMPACT.get(category, {})
        stats["total_co2_saved"] += impact.get("co2_saved_kg", 0)
        stats["total_water_saved"] += impact.get("water_saved_l", 0)
        stats["total_energy_saved"] += impact.get("energy_saved_kwh", 0)
        stats["total_trees"] += impact.get("trees_equivalent", 0)

        # Streak tracking for habit building
        current_time = datetime.now()
        last_sort = stats.get("last_sort_time")

        if last_sort:
            last_time = datetime.fromisoformat(last_sort)
            time_diff = (current_time - last_time).total_seconds()

            # If sorted within 24 hours, continue streak
            if time_diff < 86400:  # 24 hours
                stats["current_streak"] = stats.get("current_streak", 0) + 1
            else:
                stats["current_streak"] = 1
        else:
            stats["current_streak"] = 1

        # Update best streak
        if stats["current_streak"] > stats.get("best_streak", 0):
            stats["best_streak"] = stats["current_streak"]

        stats["last_sort_time"] = current_time.isoformat()

    else:
        stats["uncertain"] = stats.get("uncertain", 0) + 1
        # Uncertain items prevented from contaminating recycling!
        stats["contamination_prevented"] = stats.get("contamination_prevented", 0) + 1

    save_stats(stats)

def send_to_pico(label, confidence):
    """Send classification to Pico and provide feedback focused on preventing wishcycling"""
    if confidence >= CONFIDENCE_THRESHOLD:
        command = label.strip().lower()

        # Check if this is a commonly wishcycled item
        educational_tip = np.random.choice(EDUCATIONAL_CONTENT.get(command, ["Good job sorting!"]))

        # Happy beep for successful classification
        play_success_sound()

        print(f"✅ {label.upper()} | {educational_tip}")

    else:
        command = "unknown"
        # Low confidence = potential wishcycling attempt prevented!
        play_uncertain_sound()

        print(f"⚠️ UNCERTAIN - Contamination prevented!")
        stats["contamination_prevented"] = stats.get("contamination_prevented", 0) + 1

    ser.write((command + "\n").encode("utf-8"))
    ser.flush()

    time.sleep(0.05)
    if ser.in_waiting:
        response = ser.readline().decode().strip()
        print(f"Pico: {response}")

    # Update statistics
    update_stats(label, confidence)

    return command, time.time() + LED_HOLD_TIME

def turn_off_led():
    ser.write(("off\n").encode("utf-8"))
    ser.flush()

def draw_stats_panel(frame, stats):
    """Draw environmental impact statistics panel with habit-building metrics"""
    h, w = frame.shape[:2]
    panel_w = int(w * 0.22)  # 22% of window width

    # Semi-transparent panel on right side
    overlay = frame.copy()
    cv2.rectangle(overlay, (w - panel_w, 0), (w, h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)  # More transparent

    x = w - panel_w + 10
    y = int(h * 0.04)  # Scale with height
    font_scale = w / 1280  # Scale fonts with width

    # Title - smaller
    cv2.putText(frame, "IMPACT", (x, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5 * font_scale, (0, 255, 0), max(1, int(font_scale)))
    y += int(h * 0.04)

    # CO2 Saved - condensed
    cv2.putText(frame, f"CO2: {stats['total_co2_saved']:.1f} kg", (x, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5 * font_scale, (100, 200, 255), max(1, int(font_scale)))
    y += int(h * 0.035)

    # Trees Saved
    cv2.putText(frame, f"Trees: {stats['total_trees']:.3f}", (x, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5 * font_scale, (34, 139, 34), max(1, int(font_scale)))
    y += int(h * 0.035)

    # Water Saved
    cv2.putText(frame, f"Water: {stats['total_water_saved']:.0f} L", (x, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5 * font_scale, (255, 200, 100), max(1, int(font_scale)))
    y += int(h * 0.035)

    # Energy Saved
    cv2.putText(frame, f"Energy: {stats['total_energy_saved']:.0f} kWh", (x, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5 * font_scale, (255, 255, 100), max(1, int(font_scale)))
    y += int(h * 0.045)

    # Contamination Prevention - KEY METRIC
    cv2.putText(frame, "CONTAMINATION", (x, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4 * font_scale, (255, 100, 100), max(1, int(font_scale)))
    y += int(h * 0.025)
    contamination = stats.get("contamination_prevented", 0)
    cv2.putText(frame, f"Prevented: {contamination}", (x, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5 * font_scale, (255, 50, 50), max(1, int(font_scale)))
    y += int(h * 0.035)

    # Divider
    cv2.line(frame, (x, y), (w - 10, y), (80, 80, 80), max(1, int(font_scale)))
    y += int(h * 0.03)

    # Habit Building - Streak System
    cv2.putText(frame, "STREAKS", (x, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4 * font_scale, (255, 200, 0), max(1, int(font_scale)))
    y += int(h * 0.03)

    current_streak = stats.get("current_streak", 0)
    best_streak = stats.get("best_streak", 0)

    cv2.putText(frame, f"Now: {current_streak} | Best: {best_streak}", (x, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.45 * font_scale, (200, 200, 200), max(1, int(font_scale)))
    y += int(h * 0.035)

    # Divider
    cv2.line(frame, (x, y), (w - 10, y), (80, 80, 80), max(1, int(font_scale)))
    y += int(h * 0.03)

    # Items sorted - condensed
    cv2.putText(frame, "SORTED", (x, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4 * font_scale, (200, 200, 200), max(1, int(font_scale)))
    y += int(h * 0.03)

    categories = [
        ("R", stats.get("recycle", 0), COLORS["recycle"]),
        ("C", stats.get("compost", 0), COLORS["compost"]),
        ("H", stats.get("hazard", 0), COLORS["hazard"]),
        ("L", stats.get("landfill", 0), COLORS["landfill"])
    ]

    for cat_name, count, color in categories:
        cv2.putText(frame, f"{cat_name}:{count}", (x, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45 * font_scale, color, max(1, int(font_scale)))
        y += int(h * 0.025)

    y += int(h * 0.01)
    cv2.putText(frame, f"Total: {stats['total_items']}", (x, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5 * font_scale, (255, 255, 255), max(1, int(font_scale)))

    return frame

def draw_overlay(frame, label, confidence, auto_mode, led_active, time_remaining, show_education):
    """Draw main classification overlay with anti-wishcycling messaging"""
    h, w = frame.shape[:2]
    overlay = frame.copy()
    font_scale = w / 1280  # Scale fonts based on width
    panel_w = int(w * 0.22)  # Match stats panel width

    # Smaller top bar - scaled
    top_height = int(h * 0.17)
    cv2.rectangle(overlay, (0, 0), (w - panel_w, top_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)  # More transparent

    # Mode indicator - smaller
    mode_text = "AUTO" if auto_mode else "MANUAL"
    mode_color = (0, 255, 0) if auto_mode else (200, 200, 200)
    cv2.putText(frame, mode_text, (10, int(h * 0.035)), cv2.FONT_HERSHEY_SIMPLEX, 0.6 * font_scale, mode_color, max(1, int(2 * font_scale)))

    # Current classification
    if label:
        if confidence >= CONFIDENCE_THRESHOLD:
            display_label = label.upper()
            label_color = COLORS.get(label.lower(), (255, 255, 255))
        else:
            display_label = "UNCERTAIN"
            label_color = (255, 255, 0)

        cv2.putText(frame, display_label, (10, int(h * 0.083)),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2 * font_scale, label_color, max(1, int(2 * font_scale)))

        # Confidence bar - smaller
        conf_text = f"{int(confidence * 100)}%"
        conf_color = (0, 255, 0) if confidence >= CONFIDENCE_THRESHOLD else (255, 100, 100)
        cv2.putText(frame, conf_text, (10, int(h * 0.125)),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6 * font_scale, conf_color, max(1, int(2 * font_scale)))

        # Smaller confidence bar - scaled
        bar_start_x = int(80 * font_scale)
        bar_width = int(200 * confidence * font_scale)
        bar_total_width = int(200 * font_scale)
        bar_y1 = int(h * 0.108)
        bar_y2 = int(h * 0.128)

        bar_color = (0, 255, 0) if confidence >= CONFIDENCE_THRESHOLD else (0, 165, 255)
        cv2.rectangle(frame, (bar_start_x, bar_y1), (bar_start_x + bar_width, bar_y2), bar_color, -1)
        cv2.rectangle(frame, (bar_start_x, bar_y1), (bar_start_x + bar_total_width, bar_y2), (255, 255, 255), max(1, int(font_scale)))

        # Educational tip - only if enabled and space allows
        if show_education and confidence < CONFIDENCE_THRESHOLD:
            cv2.putText(frame, "When in doubt, ASK!",
                       (10, int(h * 0.155)), cv2.FONT_HERSHEY_SIMPLEX, 0.45 * font_scale, (255, 100, 100), max(1, int(font_scale)))

    # Compact bottom instructions - scaled
    bottom_height = int(h * 0.05)
    cv2.rectangle(overlay, (0, h - bottom_height), (w - panel_w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    cv2.putText(frame, "SPACE:Scan | A:Auto | E:Tips | R:Reset | Q:Quit",
               (10, h - int(h * 0.017)), cv2.FONT_HERSHEY_SIMPLEX, 0.45 * font_scale, (255, 255, 255), max(1, int(font_scale)))

    return frame

# Open webcam
cap = cv2.VideoCapture(DEVICE_INDEX)
if not cap.isOpened():
    raise RuntimeError(f"Could not open camera at index {DEVICE_INDEX}")

print(f"Testing camera at index {DEVICE_INDEX}...")
for attempt in range(10):
    ok, test_frame = cap.read()
    if ok:
        print(f"✅ Camera working! Frame size: {test_frame.shape}")
        break
    time.sleep(0.1)
else:
    cap.release()
    raise RuntimeError(f"Camera opened but cannot grab frames")

# Create window (do it before the loop)
window_name = "Smart Bin Classification"

# Start in windowed mode so toggling fullscreen is reliable
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 1280, 720)
cv2.moveWindow(window_name, 100, 100)

print("\n=== 🌍 SMART BIN - Environmental Impact Tracker ===")
print("Controls:")
print("  SPACE - Classify item")
print("  A - Toggle auto-classify")
print("  E - Toggle educational tips")
print("  R - Reset statistics")
print("  Q - Quit")
print("  F - Toggle fullscreen")

# State variables
auto_mode = False
show_education = True
last_classification = None
last_confidence = 0.0
last_auto_classify = 0
led_end_time = 0
is_fullscreen = False

try:
    frame_count = 0
    failed_frames = 0

    while True:
        ok, frame = cap.read()

        if not ok:
            failed_frames += 1
            if failed_frames > 30:
                print("\n❌ Cannot grab frames!")
                break
            time.sleep(0.1)
            continue

        failed_frames = 0
        frame_count += 1
        current_time = time.time()

        # Auto-classify
        if auto_mode and (current_time - last_auto_classify) >= AUTO_CLASSIFY_INTERVAL:
            label, conf, scores = predict(frame)
            last_classification = label
            last_confidence = conf

            print(f"\n[AUTO] {label} | {round(conf, 3)}")
            current_command, led_end_time = send_to_pico(label, conf)
            last_auto_classify = current_time

        # Turn off LED
        if led_end_time > 0 and current_time >= led_end_time:
            turn_off_led()
            led_end_time = 0

        time_remaining = max(0, led_end_time - current_time) if led_end_time > 0 else 0
        led_active = led_end_time > 0

        # Draw UI
        display_frame = draw_overlay(frame, last_classification, last_confidence,
                                     auto_mode, led_active, time_remaining, show_education)
        display_frame = draw_stats_panel(display_frame, stats)

        cv2.imshow(window_name, display_frame)
        k = cv2.waitKey(1) & 0xFF

        if k in (ord("q"), ord("Q")):
            break

        # Toggle fullscreen (F)
        if k in (ord("f"), ord("F")):
            is_fullscreen = not is_fullscreen

            if is_fullscreen:
                cv2.setWindowProperty(
                    window_name,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN
                )
                print("\n🖥️ FULLSCREEN ON")
            else:
                cv2.setWindowProperty(
                    window_name,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_NORMAL
                )
                cv2.resizeWindow(window_name, 1280, 720)
                cv2.moveWindow(window_name, 100, 100)
                print("\n🖥️ FULLSCREEN OFF")

        if k in (ord("a"), ord("A")):
            auto_mode = not auto_mode
            print(f"\n{'🟢 AUTO MODE ON' if auto_mode else '🔴 AUTO MODE OFF'}")
            if auto_mode:
                last_auto_classify = 0

        if k in (ord("e"), ord("E")):
            show_education = not show_education
            print(f"\n{'📚 EDUCATION ON' if show_education else '📚 EDUCATION OFF'}")

        if k in (ord("r"), ord("R")):
            stats = {
                "total_items": 0,
                "recycle": 0,
                "compost": 0,
                "hazard": 0,
                "landfill": 0,
                "uncertain": 0,
                "total_co2_saved": 0.0,
                "total_water_saved": 0.0,
                "total_energy_saved": 0.0,
                "total_trees": 0.0,
                "session_start": datetime.now().isoformat()
            }
            save_stats(stats)
            print("\n🔄 STATS RESET")

        if k == ord(" "):
            label, conf, scores = predict(frame)
            last_classification = label
            last_confidence = conf

            print(f"\n[MANUAL] {label} | {round(conf, 3)}")
            current_command, led_end_time = send_to_pico(label, conf)

except KeyboardInterrupt:
    print("\n\nInterrupted")
finally:
    turn_off_led()
    cap.release()
    cv2.destroyAllWindows()
    ser.close()

    # Print final stats
    print("\n" + "="*50)
    print("SESSION SUMMARY - STOPPING WISHCYCLING!")
    print("="*50)
    print(f"Total Items Sorted: {stats['total_items']}")
    print(f"Contamination Prevented: {stats.get('contamination_prevented', 0)} items")
    print(f"Current Streak: {stats.get('current_streak', 0)} days")
    print(f"Best Streak: {stats.get('best_streak', 0)} days")
    print("\nENVIRONMENTAL IMPACT:")
    print(f"  CO2 Saved: {stats['total_co2_saved']:.2f} kg")
    print(f"  Trees Saved: {stats['total_trees']:.3f}")
    print(f"  Water Saved: {stats['total_water_saved']:.1f} L")
    print(f"  Energy Saved: {stats['total_energy_saved']:.1f} kWh")
    print("="*50)
    print("\nShutdown complete")
