#!/usr/bin/env bash
# setup.sh — Termux bootstrap for HCO-OTPsnag (consent-first demo)
set -e
echo "[*] Updating packages..."
pkg update -y
pkg upgrade -y

echo "[*] Installing python and git..."
pkg install -y python git

python -m pip install --upgrade pip
pip install flask python-dotenv

echo "[*] Done. Create .env if you want and run: python3 main.py"
