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


_APK_MAGIC = b"PK\x03\x04"


def _is_valid_apk(path: str) -> bool:
    """检查文件是否以 APK/ZIP magic 开头。"""
    try:
        with open(path, "rb") as f:
            return f.read(4)[:2] == b"PK"
    except OSError:
        return False


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
_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

# 可切换的 UA 列表：桌面端不行时换移动端
_UA_LIST = [_USER_AGENT, _MOBILE_UA]
_CHUNK_SIZE = 64 * 1024
_TIMEOUT = 30


def _reason_for_code(code: int) -> str:
    if code == 404:
        return "应用不存在或该应用无网页版 APK"
    if code == 405:
        return "请求方式不被允许"
    return "服务器返回错误"


def _try_download(url: str, ua: str) -> tuple | None:
    """尝试下载，返回 (final_url, content_type, body) 或 None（HTTP 错误）。"""
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req) as resp:
            return (resp.geturl(), resp.headers.get("Content-Type", "?"), resp.read())
    except urllib.error.HTTPError:
        return None


def download(appid: str, output_dir: str) -> str:
    """下载 APK 到 output_dir，返回保存路径。失败抛 RuntimeError。

    尝试多种 User-Agent（桌面→移动端），并用 APK magic 校验结果。
    """
    url = build_download_url(appid)
    socket.setdefaulttimeout(_TIMEOUT)

    last_detail = ""
    for ua in _UA_LIST:
        result = _try_download(url, ua)
        if result is None:
            last_detail = f"HTTP 错误（UA={ua[:30]}...）"
            continue

        final_url, content_type, body = result
        print(f"  UA: {ua[:50]}...")
        print(f"  Content-Type: {content_type}")
        print(f"  Final URL: {final_url[:120]}")

        # 检查是否是 APK（通过 magic）
        if body[:2] == b"PK":
            filename = extract_filename(final_url, appid)
            os.makedirs(output_dir, exist_ok=True)
            dest = os.path.join(output_dir, filename)
            with open(dest, "wb") as f:
                f.write(body)
            print(f"  ✓ 下载成功 {len(body) / 1048576:.1f}MB")
            return dest

        # 不是 APK——如果只是 HTML 重定向到首页，记录细节并尝试下一个 UA
        last_detail = (
            f"返回的不是 APK（{len(body)} 字节, Content-Type={content_type}），"
            f"UA={ua[:40]}..."
        )
        # 保存一份供调试
        if b"<html" in body[:200].lower() or content_type.startswith("text/html"):
            html_dest = os.path.join(output_dir or ".", f"{appid}.html")
            with open(html_dest, "wb") as f:
                f.write(body)
            last_detail += f"，原始 HTML 已保存为 {html_dest}"

    # 所有 UA 都失败
    raise RuntimeError(
        f"下载失败（已尝试 {len(_UA_LIST)} 种 User-Agent）。\n"
        f"  最后错误: {last_detail}\n"
        "可能原因:\n"
        "  1. 该应用仅提供 AAB 格式（App Bundle），无公开 APK 直链\n"
        "  2. 该应用需要 AppGallery 客户端内下载（带 HMS Core 认证）\n"
        "  3. 该应用有区域/设备限制\n"
        f"\n备选方案:\n"
        f"  - 在 Android 设备上安装 AppGallery 客户端下载\n"
        f"  - 通过 APKPure/APKMirror 搜索同包名 APK\n"
        f"  - 若为 Google Play 应用，用 cd ../gpdownloader && python -m gpdownloader download <包名>"
    )


def main() -> int:
    # Windows 控制台默认 GBK,强制 UTF-8 避免中文输出乱码
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="从华为 AppGallery 下载 APK")
    parser.add_argument("target", help="AppGallery APPID 或详情页 URL")
    parser.add_argument("-o", "--output", default="downloads", help="输出目录(默认 ./downloads)")
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
