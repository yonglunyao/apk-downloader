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
pytest -v                                                  # 纯函数单测
python appgallery_downloader.py C10406921 -o _smoke_test   # 端到端冒烟(需网络)
```

## 退出码

- `0`:成功
- `1`:运行时错误(网络/HTTP)
- `2`:输入错误(APPID 格式非法)
