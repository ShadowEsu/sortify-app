from machine import Pin
import sys
import time

# LED pin mappings
leds = {
    "recycle": Pin(2, Pin.OUT),
    "compost": Pin(3, Pin.OUT),
    "hazard": Pin(4, Pin.OUT),
    "landfill": Pin(5, Pin.OUT),
}

def all_off():
    for p in leds.values():
        p.value(0)

def set_label(label: str):
    label = label.strip().lower()
    
    # Handle "off" command
    if label == "off":
        all_off()
        print("OK: all off")
        return
    
    all_off()
    
    if label in leds:
        leds[label].value(1)
        print(f"OK: {label}")
    else:
        print(f"UNKNOWN: {label}")
        # Blink all
        for _ in range(3):
            for p in leds.values():
                p.value(1)
            time.sleep(0.15)
            all_off()
            time.sleep(0.15)

all_off()
print("PICO READY")

while True:
    line = sys.stdin.readline()
    if line:
        set_label(line) 