# AppGallery APK Downloader 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个单文件、零运行时依赖的 Python CLI,输入 AppGallery APPID 或详情页 URL,下载对应 APK 到本地。

**Architecture:** 单脚本 `appgallery_downloader.py`,纯标准库。三个纯函数(`parse_appid`、`build_download_url`、`extract_filename`)负责输入归一化与文件名解析,用 pytest 单测覆盖;`download` + `main` 负责网络流式下载与 CLI 编排,通过端到端冒烟测试验证。下载走已验证的直链 `https://appgallery.cloud.huawei.com/appdl/{APPID}`,urllib 自动跟随 302 到 CDN。

**Tech Stack:** Python 3.11 标准库(`argparse`、`re`、`os`、`socket`、`sys`、`urllib.request`、`urllib.error`、`urllib.parse`);开发依赖 `pytest`。

**Spec:** `docs/superpowers/specs/2026-06-15-appgallery-downloader-design.md`

---

## 文件结构

| 文件 | 责任 | 创建任务 |
|------|------|----------|
| `appgallery_downloader.py` | 主脚本:纯函数 + download + main + CLI | Task 1(骨架), Task 2-5(增量) |
| `test_downloader.py` | 纯函数 pytest 单测 | Task 2(初始), Task 3-4(增量) |
| `requirements.txt` | 开发依赖 `pytest` | Task 1 |
| `.gitattributes` | 统一 LF 换行,消除 CRLF 警告 | Task 1 |
| `README.md` | 用法、APPID 获取方式、限制、冒烟步骤 | Task 6 |

运行时零依赖;pytest 仅测试时需要。

---

## Task 1: 项目骨架与测试环境

**Files:**
- Create: `requirements.txt`
- Create: `.gitattributes`
- Create: `appgallery_downloader.py`(仅模块 docstring)

- [ ] **Step 1: 创建 requirements.txt**

```
pytest>=7.0
```

- [ ] **Step 2: 创建 .gitattributes(统一 LF,消除 CRLF 警告)**

```
* text=auto eol=lf
```

- [ ] **Step 3: 创建 appgallery_downloader.py 骨架**

```python
"""从华为 AppGallery 下载 APK 的极简命令行工具。

用法:
    python appgallery_downloader.py <APPID 或详情页URL> [-o 输出目录]
"""
```

- [ ] **Step 4: 安装开发依赖**

Run: `pip install -r requirements.txt`
Expected: 成功安装 pytest,末尾出现 `Successfully installed pytest-...`(或 `Requirement already satisfied`)。

- [ ] **Step 5: 验证骨架可 import 且 pytest 可运行**

Run: `python -c "import appgallery_downloader; print('ok')"`
Expected: 输出 `ok`

Run: `pytest -q`
Expected: `no tests ran in ...s`(无测试,无错误)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitattributes appgallery_downloader.py
git commit -m "chore: project scaffold and pytest setup"
```

---

## Task 2: parse_appid 纯函数(TDD)

**Files:**
- Create: `test_downloader.py`
- Modify: `appgallery_downloader.py`

- [ ] **Step 1: 写失败测试**

创建 `test_downloader.py`,完整内容:

```python
import pytest

from appgallery_downloader import parse_appid


def test_parse_appid_plain():
    assert parse_appid("C10406921") == "C10406921"


def test_parse_appid_hash_url():
    url = "https://appgallery.huawei.com/#/app/C100130495"
    assert parse_appid(url) == "C100130495"


def test_parse_appid_plain_url():
    url = "https://appgallery.huawei.com/app/C100130495"
    assert parse_appid(url) == "C100130495"


def test_parse_appid_invalid_raises():
    with pytest.raises(ValueError):
        parse_appid("not-an-appid")
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `pytest test_downloader.py -v`
Expected: 4 个测试全部 FAIL,错误信息为 `ImportError: cannot import name 'parse_appid'`(函数尚未定义)。

- [ ] **Step 3: 实现 parse_appid**

在 `appgallery_downloader.py` 的 docstring 下方追加:

```python
import re

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
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `pytest test_downloader.py -v`
Expected: 4 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add appgallery_downloader.py test_downloader.py
git commit -m "feat: parse AppGallery appid from URL or plain id"
```

---

## Task 3: build_download_url 纯函数(TDD)

**Files:**
- Modify: `test_downloader.py`
- Modify: `appgallery_downloader.py`

- [ ] **Step 1: 追加失败测试**

在 `test_downloader.py` 末尾追加:

```python
from appgallery_downloader import build_download_url


def test_build_download_url():
    assert build_download_url("C10406921") == "https://appgallery.cloud.huawei.com/appdl/C10406921"
```

- [ ] **Step 2: 运行测试,确认新测试失败**

Run: `pytest test_downloader.py -v`
Expected: 新增的 `test_build_download_url` FAIL(`ImportError: cannot import name 'build_download_url'`),其余 PASS。

- [ ] **Step 3: 实现 build_download_url**

在 `appgallery_downloader.py` 的 `parse_appid` 之后追加:

```python
_DOWNLOAD_BASE = "https://appgallery.cloud.huawei.com/appdl/"


def build_download_url(appid: str) -> str:
    """构造 AppGallery APK 直链。"""
    return f"{_DOWNLOAD_BASE}{appid}"
```

- [ ] **Step 4: 运行测试,确认全部通过**

Run: `pytest test_downloader.py -v`
Expected: 5 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add appgallery_downloader.py test_downloader.py
git commit -m "feat: build appdl download url"
```

---

## Task 4: extract_filename 纯函数(TDD)

**Files:**
- Modify: `test_downloader.py`
- Modify: `appgallery_downloader.py`

- [ ] **Step 1: 追加失败测试**

在 `test_downloader.py` 末尾追加:

```python
from appgallery_downloader import extract_filename


def test_extract_filename_from_cdn_url():
    url = (
        "https://appdl-1-drcn.dbankcdn.com/dl/appdl/application/apk/bc/"
        "bc2a32d236ff4485b9d6a1ee0461e19e/com.huawei.smarthome.2606131023.apk"
    )
    assert extract_filename(url, "C10406921") == "com.huawei.smarthome.2606131023.apk"


def test_extract_filename_strips_query():
    url = "https://store-drcn.hispace.dbankcloud.com/dl/appdl/x/com.example.app.apk?maple=0&trackId=0"
    assert extract_filename(url, "C100") == "com.example.app.apk"


def test_extract_filename_fallback_when_no_apk():
    url = "https://appgallery.cloud.huawei.com/appdl/C100130495"
    assert extract_filename(url, "C100130495") == "C100130495.apk"
```

- [ ] **Step 2: 运行测试,确认新测试失败**

Run: `pytest test_downloader.py -v`
Expected: 3 个 `test_extract_filename_*` FAIL(`ImportError: cannot import name 'extract_filename'`),其余 PASS。

- [ ] **Step 3: 实现 extract_filename**

在 `appgallery_downloader.py` 顶部 import 区追加(放在 `import re` 之后):

```python
import os
from urllib.parse import unquote, urlsplit
```

在 `build_download_url` 之后追加:

```python
def extract_filename(url: str, appid: str) -> str:
    """从最终 CDN URL 解析文件名;无 .apk 后缀则回退 {appid}.apk。"""
    name = unquote(os.path.basename(urlsplit(url).path))
    if name.lower().endswith(".apk"):
        return name
    return f"{appid}.apk"
```

- [ ] **Step 4: 运行测试,确认全部通过**

Run: `pytest test_downloader.py -v`
Expected: 8 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add appgallery_downloader.py test_downloader.py
git commit -m "feat: extract apk filename from redirect url"
```

---

## Task 5: download + main + CLI 编排(冒烟验证)

网络入口函数,不写单测;通过端到端冒烟测试验证(spec 测试策略已约定)。

**Files:**
- Modify: `appgallery_downloader.py`

- [ ] **Step 1: 追加网络与 CLI 代码**

在 `appgallery_downloader.py` 顶部 import 区补齐(放在已有 import 之后):

```python
import argparse
import socket
import sys
import urllib.error
import urllib.request
```

在 `extract_filename` 之后、文件末尾追加:

```python
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
```

- [ ] **Step 2: 回归测试,确认纯函数未受影响**

Run: `pytest test_downloader.py -v`
Expected: 8 个测试全部 PASS(新增代码不应破坏纯函数)。

- [ ] **Step 3: 验证 CLI 帮助正常**

Run: `python appgallery_downloader.py -h`
Expected: 打印 usage,显示 `target` 位置参数和 `-o/--output` 选项。

- [ ] **Step 4: 验证非法输入退出码**

Run: `python appgallery_downloader.py "not-valid"; echo "exit=$?"`
Expected: stderr 打印 `错误: 非法 APPID(应为 C 开头数字串): not-valid`,`exit=2`。

- [ ] **Step 5: 端到端冒烟测试(真实下载,需要网络)**

用已知可用的 APPID `C10406921`(华为智慧生活,APK 约 192MB——体积大,只需验证开始下载后中断)。

Run: `python appgallery_downloader.py C10406921 -o _smoke_test`
Expected:
- 打印 `APPID: C10406921`
- 出现形如 `  5.0MB / 191.8MB (2%)` 的进度行(数字随实时变化)
- `_smoke_test/` 目录下生成文件,文件名为真实包名(形如 `com.huawei.smarthome.2606131023.apk`,而非 `C10406921.apk`)

**看到进度行后按 Ctrl+C 中断**(无需下载完整 192MB)。

- [ ] **Step 6: 确认冒烟产物**

Run: `ls -la _smoke_test/`
Expected: 存在一个 `com.huawei.smarthome.*.apk` 文件,大小 > 0。

清理: `rm -rf _smoke_test`

- [ ] **Step 7: Commit**

```bash
git add appgallery_downloader.py
git commit -m "feat: stream download with progress and cli"
```

---

## Task 6: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建 README.md**

```markdown
# AppGallery APK Downloader

从华为海外版/网页版 AppGallery 下载应用 Android APK 的极简命令行工具,用于移动应用安全分析。纯 Python 标准库,零运行时依赖。

## 安装

仅测试时需要 pytest:

```bash
pip install -r requirements.txt
```

运行无需安装任何第三方包(Python 3.11+)。

## 用法

```bash
python appgallery_downloader.py <APPID 或详情页URL> [-o 输出目录]
```

示例:

```bash
# 直接用 APPID
python appgallery_downloader.py C10406921

# 用详情页 URL
python appgallery_downloader.py "https://appgallery.huawei.com/#/app/C100130495"

# 指定输出目录
python appgallery_downloader.py C10406921 -o ./apks
```

下载的文件以真实包名命名(如 `com.huawei.smarthome.2606131023.apk`)。

## 如何获取 APPID

1. 浏览器打开 `https://appgallery.huawei.com`,搜索目标应用。
2. 进入应用详情页,URL 形如 `https://appgallery.huawei.com/#/app/C10406921`。
3. 其中 `C` 开头的数字串(`C10406921`)即为 APPID。

## 工作原理

AppGallery 网页版应用的 APK 可通过 URL 直链转换获取:

- 详情页:`https://appgallery.huawei.com/#/app/{APPID}`
- 直链:域名加 `.cloud`、路径 `/app/` 改 `/appdl/` → `https://appgallery.cloud.huawei.com/appdl/{APPID}`

直链会 302 重定向到华为 CDN,本工具自动跟随并流式下载。

## 限制

- 仅对上架网页版且提供 APK 的应用有效。
- **鸿蒙原生包(`.hap`/`.app`)无法通过此方式下载**。
- 部分国内合规应用未上架网页版,无此直链。
- 无断点续传、无失败重试(极简设计)。

## 测试

```bash
pytest -v          # 纯函数单测
python appgallery_downloader.py C10406921 -o _smoke_test   # 端到端冒烟(需网络)
```

## 退出码

- `0`:成功
- `1`:运行时错误(网络/HTTP)
- `2`:输入错误(APPID 格式非法)
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add readme with usage and appid guide"
```

---

## 完成标准

- `pytest -v` 全部 8 个纯函数测试通过。
- `python appgallery_downloader.py -h` 正常显示帮助。
- 非法输入返回退出码 2。
- 端到端冒烟:真实 APPID 能开始下载、进度正确、文件名为真实包名。
- README 完整。
- 6 个 commit,每个任务一个,符合 conventional commits。
