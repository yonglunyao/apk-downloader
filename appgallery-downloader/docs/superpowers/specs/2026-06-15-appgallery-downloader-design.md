# AppGallery APK Downloader 设计文档

- **日期**: 2026-06-15
- **状态**: 已批准,待实现
- **作者**: Yonglun Yao

## 1. 目标

一个极简的命令行工具,从华为海外版/网页版 AppGallery 下载指定应用的 Android APK 安装包,供移动应用安全分析使用。

输入一个应用的 AppGallery APPID 或详情页 URL,输出对应的 APK 文件到本地。

## 2. 非目标 (YAGNI)

明确不做:

- 批量下载(读列表文件)
- 按应用名搜索(逆向搜索接口)
- 断点续传
- 下载失败重试
- APK 完整性/签名校验
- 鸿蒙原生包(.hap/.app)下载
- GUI

这些可在后续迭代按需扩展。

## 3. 技术背景(已实测验证)

华为 AppGallery 网页版应用的 APK 可通过 URL 直链转换获取:

- 详情页 URL: `https://appgallery.huawei.com/#/app/{APPID}`
- APK 直链: 把域名 `appgallery.huawei.com` 改为 `appgallery.cloud.huawei.com`,路径 `/app/` 改为 `/appdl/`
- 即直链为: `https://appgallery.cloud.huawei.com/appdl/{APPID}`

其中 APPID 为 C 开头的数字串(如 `C10406921`)。

实测下载链路(2026-06-15 验证):

1. GET `https://appgallery.cloud.huawei.com/appdl/{APPID}`
2. 302 → `store-drcn.hispace.dbankcloud.com/dl/appdl/.../{包名}.apk`
3. 302 → `appdl-1-drcn.dbankcdn.com/dl/appdl/.../{包名}.apk`
4. 200,`Content-Type: application/vnd.android.package-archive`

注意:

- 必须用 GET;HEAD 返回 405。
- 最终 CDN URL 的 path 含真实包名和文件名(如 `com.huawei.smarthome.2606131023.apk`)。
- 仅对上架网页版且提供 APK 的应用有效;鸿蒙原生包、部分国内合规应用无此直链。

## 4. 架构

单文件 CLI 脚本,纯 Python 标准库,零运行时依赖。

### 4.1 命令行接口

```
python appgallery_downloader.py <APPID|URL> [-o OUTPUT_DIR]
```

- 位置参数 `target`:AppGallery APPID 或详情页 URL。
- 可选参数 `-o/--output`:输出目录,默认当前目录 `.`。

### 4.2 模块结构

`appgallery_downloader.py` 包含:

| 函数 | 职责 | 纯函数 |
|------|------|--------|
| `parse_appid(target)` | 从 APPID 或 URL 提取 C 开头 APPID | 是 |
| `extract_filename(url, appid)` | 从最终 CDN URL 解析文件名,失败回退 `{appid}.apk` | 是 |
| `build_download_url(appid)` | 构造直链 URL | 是 |
| `download(appid, output_dir)` | 请求、流式下载、进度打印 | 否(网络) |
| `main()` | 参数解析、编排、错误处理 | 否 |

## 5. 核心流程

1. **参数解析**:`argparse` 解析 `target` 与 `-o`。
2. **归一化输入**:`parse_appid(target)`:
   - 若 `target` 含 `http`:用正则 `C\d+` 提取第一个匹配作为 APPID。
   - 否则:当纯 APPID,校验 `^C\d+$`;不匹配则报错退出。
3. **构造直链**:`build_download_url(appid)` → `https://appgallery.cloud.huawei.com/appdl/{appid}`。
4. **发起请求**:urllib `Request`,带浏览器 User-Agent,全局 socket 超时 30s。urllib 默认 `HTTPRedirectHandler` 自动跟随 302 到最终 CDN。
5. **解析文件名**:`extract_filename(response.geturl(), appid)`:`urlsplit` 取 path 的 basename,urldecode 后 strip query;若无 `.apk` 后缀则回退 `{appid}.apk`。
6. **流式下载**:`read(64KB)` 循环写入输出文件;从 `Content-Length` 取总字节数,每累计下载 1MB 打印一行进度(`{已下载MB}/{总MB} ({百分比}%)`)。
7. **完成**:打印最终保存路径,退出码 0。

## 6. 错误处理

- **输入非法**(APPID 不匹配 `C\d+`):打印错误提示,退出码 2。
- **HTTP 错误状态码**(非 2xx):打印状态码与提示。常见原因:应用无网页版 APK、APPID 不存在、可能为鸿蒙原生包。退出码 1。
- **网络异常**(`URLError`/`socket.timeout`):打印错误,退出码 1。

退出码约定:0 成功,1 运行时错误(网络/HTTP),2 输入错误。

## 7. 测试策略

遵循"轻量可验证"原则(平衡极简诉求与全局测试要求):

- **纯函数单测**(`test_downloader.py`,pytest):
  - `parse_appid`:纯 APPID、`#/app/` URL、`/app/` URL、非法输入。
  - `extract_filename`:正常 CDN URL、带 query、无 `.apk` 后缀的回退。
- **端到端冒烟**:实现时选取一个小体积应用实际下载,确认产出有效 APK(文件非空、魔数头 `PK`)。冒烟用例与验证步骤写入 README。

不追求 80% 覆盖率;网络相关入口通过冒烟验证。

## 8. 文件结构

```
appgallery-downloader/
├── appgallery_downloader.py   # 主脚本
├── test_downloader.py          # pytest 纯函数单测
├── requirements.txt            # 仅开发依赖: pytest
└── README.md                   # 用法、APPID 获取方式、限制说明
```

运行时零依赖(纯标准库);pytest 仅开发/测试时需要。

## 9. 依赖

- 运行时:Python 3.11+ 标准库(`urllib.request`、`urllib.parse`、`argparse`、`re`、`os`、`socket`)。无第三方包。
- 开发/测试:`pytest`。
