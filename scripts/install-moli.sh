#!/usr/bin/env bash
# ติดตั้ง Moli เวอร์ชันที่ pin ไว้ (headless browser สำหรับ AI)
set -euo pipefail

VERSION="${MOLI_VERSION:-v1.1.21}"
URL="https://github.com/lexmount/moli/releases/download/${VERSION}/moli-installer.sh"

if command -v moli >/dev/null 2>&1; then
  echo "moli มีอยู่แล้ว: $(moli --version)"
  exit 0
fi

echo "ติดตั้ง Moli ${VERSION} จาก ${URL}"
curl --proto '=https' --tlsv1.2 -fsSL "$URL" | sh

if command -v moli >/dev/null 2>&1; then
  echo "ติดตั้งสำเร็จ: $(moli --version)"
  exit 0
fi

for candidate in "$HOME/.local/bin/moli" "/usr/local/bin/moli"; do
  if [ -x "$candidate" ]; then
    echo "ติดตั้งแล้วที่ $candidate — เพิ่ม PATH ก่อนใช้งาน"
    exit 0
  fi
done

echo "ติดตั้งไม่สำเร็จ" >&2
exit 1
