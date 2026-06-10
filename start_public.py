"""
老师助手 - 一键启动
====================
启动网页服务 + Cloudflare 隧道，生成公开 https 链接。
"""
import subprocess
import sys
import time
import socket
import urllib.request
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


print("=" * 55)
print("  老 师 助 手")
print("=" * 55)

# 启动网页服务器
print("\n[1/2] 启动网页服务器...")
server_proc = subprocess.Popen(
    [sys.executable, "web_app.py"],
    cwd=str(BASE_DIR),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
time.sleep(8)

try:
    urllib.request.urlopen("http://localhost:8000/api/health", timeout=5)
    print("  [OK] 服务器已启动")
except Exception as e:
    err_msg = str(e).encode('ascii', 'ignore').decode('ascii')
    print(f"  [FAIL] 服务器启动失败: {err_msg}")
    sys.exit(1)

# 启动 Cloudflare Tunnel
print("\n[2/2] 连接 Cloudflare 全球网络...\n")
cf_path = BASE_DIR / "cloudflared.exe"

if cf_path.exists():
    cf_proc = subprocess.Popen(
        [str(cf_path), "tunnel", "--url", "http://localhost:8000", "--no-autoupdate"],
        cwd=str(BASE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    public_url = None
    for i in range(30):
        time.sleep(1)
        try:
            resp = urllib.request.urlopen(
                "http://127.0.0.1:20241/metrics", timeout=3
            )
            text = resp.read().decode()
            m = re.search(
                r'userHostname="(https://[^"]+)"', text
            )
            if m:
                public_url = m.group(1)
                break
        except Exception:
            pass

    local_ip = get_local_ip()

    print("\n" + "=" * 55)
    if public_url:
        print(f"\n  *** 公开链接已生成! ***\n")
        print(f"  {public_url}\n")
        print(f"  把这个链接发到微信群")
        print(f"  中国和菲律宾的老师都能用\n")
    else:
        print(f"\n  链接生成超时，可使用局域网地址\n")

    print(f"\n  局域网地址: http://{local_ip}:8000")
    print("=" * 55)
    print("\n按 Ctrl+C 停止服务\n")

    try:
        cf_proc.wait()
    except KeyboardInterrupt:
        print("\n正在停止...")
        cf_proc.terminate()
        server_proc.terminate()
        print("已停止")
else:
    print("\n  cloudflared 未找到，启动局域网模式")
    local_ip = get_local_ip()
    print(f"\n  本机: http://localhost:8000")
    print(f"  手机: http://{local_ip}:8000\n")
    server_proc.wait()
