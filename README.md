# apk-downloader

从主流应用商店下载 Android APK 样本的命令行工具集，面向**移动应用安全分析**场景。

## 子项目

| 工具 | 目标商店 | 技术方案 | 认证要求 |
|------|----------|----------|----------|
| [appgallery-downloader](./appgallery-downloader/) | 华为 AppGallery（海外版） | 纯 Python 标准库，零运行时依赖 | 无需认证 |
| [gpdownloader](./gpdownloader/) | Google Play | 封装 [EFForg/apkeep](https://github.com/EFForg/apkeep) | Google 账号 + OAuth token 换取 AAS token |

## 快速开始

### appgallery-downloader

```bash
# 用 APPID 下载
python appgallery-downloader/appgallery_downloader.py C10406921

# 用详情页 URL 下载
python appgallery-downloader/appgallery_downloader.py "https://appgallery.huawei.com/#/app/C100130495"

# 指定输出目录
python appgallery-downloader/appgallery_downloader.py C10406921 -o ./apks
```

详见 [appgallery-downloader/README.md](./appgallery-downloader/README.md)。

### gpdownloader

> **所有命令必须在 `gpdownloader/` 目录下执行**，`python -m gpdownloader` 会从此目录查找 `config/config.toml` 和 `bin/apkeep.exe`。

```bash
cd gpdownloader

# 1. 安装 apkeep（见子项目 README），然后初始化配置
cp config/config.example.toml config/config.toml
# 编辑 config.toml，填入 apkeep_path（指向 apkeep 可执行文件）

# 2. 增大栈（Windows 必做，详见子项目 README）
python -m gpdownloader fix-stack

# 3. 换取凭证（一次性）
python -m gpdownloader auth -e you@gmail.com --oauth-token "oauth2_4/..."

# 4. 自检
python -m gpdownloader doctor

# 5. 下载 APK
python -m gpdownloader download com.example.app

# 6. 批量下载
python -m gpdownloader batch packages.txt
```

详见 [gpdownloader/README.md](./gpdownloader/README.md)。

## 目录结构

```
apk-downloader/
├── appgallery-downloader/   # 华为 AppGallery 下载器
│   ├── appgallery_downloader.py   # 单文件工具
│   ├── test_downloader.py         # 测试
│   └── README.md
├── gpdownloader/            # Google Play 下载器
│   ├── gpdownloader/        # Python 包
│   │   ├── cli.py           # 命令行入口
│   │   ├── downloader.py    # apkeep 封装核心
│   │   └── config.py        # 凭证管理
│   ├── config/
│   │   └── config.example.toml
│   ├── pyproject.toml
│   └── README.md
└── README.md                # 本文件
```

## 安全提示

- `config.toml` 含 Google 账号凭证，已加入 `.gitignore`，**切勿提交**。
- 建议使用专用低价值 Google 账号操作 gpdownloader，存在被风控风险。
- 下载的 APK 样本请妥善保管，遵守当地法律法规与应用商店服务条款。
