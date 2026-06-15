# gpdownloader

输入**包名**从 Google Play 下载 APK 样本的命令行工具。封装 [EFForg/apkeep](https://github.com/EFForg/apkeep)，提供凭证自动换取、批量下载、SHA-256 校验、结构化日志，以及 Windows 栈溢出一键修复。

面向移动安全研究 / 样本采集场景。

## 依赖

- **Python 3.10+**（3.11+ 内置 `tomllib`，3.10 需 `pip install tomli`）
- **apkeep**（见下方安装）

## 一、安装 apkeep

### Windows（推荐：预编译二进制，无需编译）

从 [apkeep releases](https://github.com/EFForg/apkeep/releases) 下载 `apkeep-x86_64-pc-windows-msvc.exe`，解压后：

- 把 `apkeep.exe` 放进 `PATH`，**或**
- 在 `config/config.toml` 的 `[general] apkeep_path` 填完整路径

> 如需从源码编译（`cargo install apkeep`），Windows 下需要 MinGW 的 `dlltool.exe`（`mingw-w64` 工具链）。缺该工具会报 `dlltool.exe: program not found`。

### Windows 必做：增大 apkeep 栈

Rust 程序在 Windows 主线程默认栈仅 1MB，下载 Google Play 时会栈溢出（`thread 'main' has overflowed its stack`，退出码 `0xC00000FD` = STATUS_STACK_OVERFLOW）。Linux/Docker 默认 8MB 所以不触发。

```bash
python -m gpdownloader fix-stack
```

脚本自动用 Visual Studio 的 `editbin /STACK:32M` 改大 PE 栈保留（需 VS Build Tools，会自动定位并备份原文件）。无 VS 环境可改用 Docker 跑 apkeep（`docker run --rm -v "$PWD/downloads":/out ghcr.io/efforg/apkeep:stable ...`）。`doctor` 会自动检测栈大小并提示。

### macOS / Linux

```bash
cargo install apkeep
# 或下载对应平台 release 二进制
```

## 二、初始化配置

```bash
cp config/config.example.toml config/config.toml
```

如果你已把 `apkeep.exe` 放到工程 `bin/` 下，把路径填入 `apkeep_path`（或用 `PATH`）。其余字段（email / aas_token）留空，下一步自动填。

自检：

```bash
python -m gpdownloader doctor
```

## 三、获取凭证（OAuth token → AAS token）

Google Play 下载必须认证。流程是：**浏览器抓一次性 OAuth token → 用 apkeep 换成长期 AAS token**（脚本自动完成换取并写回 config）。

### 第 1 步：抓取一次性 OAuth token（浏览器手动）

1. 浏览器打开 https://accounts.google.com/EmbeddedSetup
2. `F12` → **Network** 标签
3. 登录 Google 账号（建议专用低价值账号）
4. 若弹出"服务条款"，点 `I agree`（卡住可忽略）
5. 在 Network 找最后一个 `accounts.google.com` 请求，打开其 **Cookies** 标签
6. 找到 `oauth_token`，复制 value（以 `oauth2_4/` 开头）

> 这个 token **只能用一次**，立刻执行第 2 步。

### 第 2 步：换 AAS token 并自动写回配置（脚本自动）

```bash
python -m gpdownloader auth -e 你的@gmail.com --oauth-token "oauth2_4/你复制的token"
```

脚本会调用 apkeep 换取 AAS token，自动写回 `config/config.toml` 的 `email` 和 `aas_token` 字段（保留其他配置与注释）。AAS token **长期有效**，只需换取一次。

> ⚠️ 建议用专用低价值 Google 账号。这是对账号的自动化访问，存在被风控/封禁风险。详见 [apkeep USAGE-google-play.md](https://github.com/EFForg/apkeep/blob/master/USAGE-google-play.md)。

## 四、使用

```bash
# 自检（确认 apkeep + 凭证就绪）
python -m gpdownloader doctor

# 下载单个包
python -m gpdownloader download com.example.app
python -m gpdownloader download com.example.app -c 1.2.3      # 指定版本
python -m gpdownloader download com.example.app -o ./out      # 指定输出目录

# 批量下载（每行一个包名，# 开头为注释）
python -m gpdownloader batch packages.txt
```

示例 `packages.txt`：

```
# 待采集样本
com.whatsapp
com.instagram.android
enterprises.dating.boo
```

## 五、输出

每个包下载到 `downloads/<package>/`（apkeep 自建 appid 子目录，含 base + 各 split），并在日志中打印每个产物的 **SHA-256**，便于与官方/镜像包体做等价性比对。

> **可复现性**：同一凭证 + 同一 `device` profile 下，重复下载的产物 SHA-256 完全一致——这本身就是"等价性"的最强证据，无需对比镜像站。

```
============================================================
包名: com.example.app
输出: downloads/com.example.app
  a1b2c3...  base.apk
  d4e5f6...  config.xxhdpi.apk
============================================================
```

## 目录结构

```
gpdownloader/
├── gpdownloader/
│   ├── __init__.py
│   ├── __main__.py      # python -m gpdownloader 入口
│   ├── cli.py           # 命令解析：auth / download / batch / fix-stack / doctor
│   ├── downloader.py    # apkeep 封装核心（下载 + token 换取 + 校验 + 栈修复）
│   └── config.py        # 凭证与下载配置 + 原地写回
├── config/
│   └── config.example.toml
├── bin/                 # apkeep 二进制（可选，gitignore）
├── downloads/           # 下载产物（gitignore）
├── pyproject.toml
└── README.md
```

## 命令一览

| 命令 | 作用 |
|------|------|
| `auth -e EMAIL --oauth-token TOKEN` | OAuth 换 AAS token 并写回 config |
| `download <package> [-c VER] [-o DIR]` | 下载单个包 |
| `batch <file> [-c VER]` | 批量下载 |
| `fix-stack [-s MB]` | 修复 Windows apkeep 栈溢出（一键，自动定位 editbin） |
| `doctor` | 自检 apkeep / 凭证 / 栈大小 |

## 备选方案

- **匿名 token**：apkeep 支持 `--auth-token`（来自 Aurora token dispenser），无需个人账号，但 dispenser 可用性不稳定。
- 若不便准备 Google 账号，可考虑 [rehmatworks/gplaydl](https://github.com/rehmatworks/gplaydl)（匿名认证，纯 Python）。

## 安全提示

- `config/config.toml` 含敏感凭证，已加入 `.gitignore`，勿提交。
- 日志中 AAS token / OAuth token 均掩码为 `***`。
- OAuth token 失效（被 Google 反自动化拦截）时，重新执行第三节抓取新 token 即可。
- 建议使用专用账号，遵守当地法律法规与 Google 服务条款。
