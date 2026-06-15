"""从华为 AppGallery 下载 APK 的极简命令行工具。

用法:
    python appgallery_downloader.py <APPID 或详情页URL> [-o 输出目录]
"""

import argparse
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from urllib.parse import unquote, urlsplit

_APPID_RE = re.compile(r"C\d+")


def parse_appid(target: str) -> str:
    """从 APPID 或详情页 URL 提取 C 开头的 APPID。

    输入含 http 时按 C\\d+ 从 URL 提取;否则当作纯 APPID 校验。
    非法输入抛 ValueError。
    """
    target = target.strip()
    if "http" in target.lower():
        match = _APPID_RE.search(target)
        if not match:
            raise ValueError(f"无法从 URL 提取 APPID: {target}")
        return match.group(0)
    if not re.fullmatch(r"C\d+", target):
        raise ValueError(f"非法 APPID(应为 C 开头数字串): {target}")
    return target


_DOWNLOAD_BASE = "https://appgallery.cloud.huawei.com/appdl/"


def build_download_url(appid: str) -> str:
    """构造 AppGallery APK 直链。"""
    return f"{_DOWNLOAD_BASE}{appid}"


def extract_filename(url: str, appid: str) -> str:
    """从最终 CDN URL 解析文件名;无 .apk 后缀则回退 {appid}.apk。"""
    name = unquote(os.path.basename(urlsplit(url).path))
    if name.lower().endswith(".apk"):
        return name
    return f"{appid}.apk"


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_CHUNK_SIZE = 64 * 1024
_TIMEOUT = 30


def _reason_for_code(code: int) -> str:
    if code == 404:
        return "应用不存在或该应用无网页版 APK"
    if code == 405:
        return "请求方式不被允许"
    return "服务器返回错误"


def download(appid: str, output_dir: str) -> str:
    """下载 APK 到 output_dir,返回保存路径。失败抛 RuntimeError。"""
    url = build_download_url(appid)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    socket.setdefaulttimeout(_TIMEOUT)

    try:
        with urllib.request.urlopen(req) as resp:
            final_url = resp.geturl()
            total = int(resp.headers.get("Content-Length") or 0)
            filename = extract_filename(final_url, appid)
            os.makedirs(output_dir, exist_ok=True)
            dest = os.path.join(output_dir, filename)
            downloaded = 0
            last_mb = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    mb = downloaded // (1024 * 1024)
                    if mb > last_mb:
                        last_mb = mb
                        if total:
                            pct = downloaded * 100 // total
                            print(f"  {downloaded / 1048576:.1f}MB / {total / 1048576:.1f}MB ({pct}%)")
                        else:
                            print(f"  {downloaded / 1048576:.1f}MB")
            return dest
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {_reason_for_code(e.code)}(appid={appid})") from e
    except (urllib.error.URLError, socket.timeout) as e:
        reason = getattr(e, "reason", e)
        raise RuntimeError(f"网络错误: {reason}") from e


def main() -> int:
    # Windows 控制台默认 GBK,强制 UTF-8 避免中文输出乱码
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="从华为 AppGallery 下载 APK")
    parser.add_argument("target", help="AppGallery APPID 或详情页 URL")
    parser.add_argument("-o", "--output", default=".", help="输出目录(默认当前目录)")
    args = parser.parse_args()

    try:
        appid = parse_appid(args.target)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 2

    print(f"APPID: {appid}")
    try:
        dest = download(appid, args.output)
    except RuntimeError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    print(f"已保存: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
