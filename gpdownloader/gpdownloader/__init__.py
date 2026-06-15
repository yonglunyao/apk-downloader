"""gpdownloader: 输入包名从 Google Play 下载 APK 样本的命令行工具。

封装 EFForg/apkeep，提供：OAuth→AAS 凭证自动换取、批量下载、
SHA-256 校验、结构化日志，以及 Windows 栈溢出一键修复（fix-stack）。
"""
from .downloader import Downloader, ApkeepNotFoundError
from .config import Config, ConfigNotFoundError

__version__ = "0.1.0"
__all__ = ["Downloader", "ApkeepNotFoundError", "Config", "ConfigNotFoundError"]
