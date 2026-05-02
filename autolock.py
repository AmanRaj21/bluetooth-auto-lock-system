"""
Bluetooth Auto Lock System

Automatically locks the system when a trusted Bluetooth device disconnects.
Runs in background with smart checks to avoid unwanted locking.
"""

import asyncio
import logging
import os
import threading
from bleak import BleakScanner
from winotify import Notification, audio
import keyboard
import subprocess
import win32gui
import win32process
import psutil

# ------------------------
# Configuration
# ------------------------
DEVICES_TO_MONITOR = ["Device_Name_Here"]

SCAN_INTERVAL = 5
LOCK_DELAY = 2

MANUAL_OFF_KEY = "ctrl+alt+q"
MANUAL_ON_KEY = "ctrl+alt+w"

LOG_FILE = "auto_lock_log.txt"
TOAST_TITLE = "AutoLock"

# Reset log file
with open(LOG_FILE, "w") as f:
    f.write("")

# ------------------------
# Logging Setup
# ------------------------
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ------------------------
# GPU Check (Prevent false lock)
# ------------------------
def is_igd_active():
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        usage = result.stdout.strip()
        if usage:
            return int(usage.split("\n")[0]) == 0
        return True
    except:
        return True

# ------------------------
# Fullscreen Detection
# ------------------------
def is_fullscreen():
    try:
        fg_window = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(fg_window)
        proc = psutil.Process(pid)
        exe = proc.name().lower()

        blocked_apps = ["game.exe", "steam.exe", "epicgameslauncher.exe"]
        return exe in blocked_apps
    except:
        return False

# ------------------------
# Notifications
# ------------------------
def show_notification(msg):
    if is_fullscreen():
        return

    try:
        toast = Notification(
            app_id="AutoLock",
            title=TOAST_TITLE,
            msg=msg,
            duration="short"
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
    except:
        pass

# ------------------------
# Manual Controls
# ------------------------
manual_off = False
manual_on = True

def listen_keys():
    global manual_off, manual_on

    while True:
        keyboard.wait(MANUAL_OFF_KEY)
        manual_off = True
        manual_on = False
        logging.info("Auto-lock disabled manually")
        show_notification("Auto-lock disabled")

        keyboard.wait(MANUAL_ON_KEY)
        manual_off = False
        manual_on = True
        logging.info("Auto-lock resumed")
        show_notification("Auto-lock resumed")

# ------------------------
# BLE Monitoring
# ------------------------
device_connected = False
armed = False

def start_ble_loop():
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(ble_loop())

async def ble_loop():
    global device_connected, armed

    while True:
        try:
            if not manual_on:
                await asyncio.sleep(SCAN_INTERVAL)
                continue

            devices = await BleakScanner.discover(timeout=SCAN_INTERVAL)
            names = [d.name for d in devices if d.name]

            detected = any(
                device.lower() in (n.lower() for n in names)
                for device in DEVICES_TO_MONITOR
            )

            igd_active = is_igd_active()

            if detected:
                if not device_connected:
                    logging.info("Device connected")
                    show_notification("Device connected. Auto-lock armed.")
                    armed = True

                device_connected = True

            else:
                if device_connected:
                    logging.info("Device disconnected")
                    show_notification(f"Device disconnected. Locking in {LOCK_DELAY}s")

                    device_connected = False

                    if armed and igd_active and not manual_off:
                        await asyncio.sleep(LOCK_DELAY)
                        logging.info("Locking system")
                        show_notification("Locking system now")
                        os.system("rundll32.exe user32.dll,LockWorkStation")

        except Exception as e:
            logging.error(f"Error: {e}")

        await asyncio.sleep(SCAN_INTERVAL)

# ------------------------
# Main Entry
# ------------------------
if __name__ == "__main__":
    logging.info("Auto Lock System Started")

    threading.Thread(target=listen_keys, daemon=True).start()
    threading.Thread(target=start_ble_loop, daemon=True).start()

    while True:
        pass