"""apkeep 封装核心：构建命令、执行下载、换取 token、校验产物。

只做一件事：把"包名/凭证 + 配置"翻译成正确的 apkeep 调用，并收集结果。
不重新实现 Google Play 协议，保持与上游 apkeep 一致。
"""
from __future__ import annotations

import glob
import hashlib
import logging
import os
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Config, Credentials, DownloadOptions

log = logging.getLogger("gpdownloader")


class ApkeepNotFoundError(RuntimeError):
    """PATH 中找不到 apkeep 可执行文件。"""


class DownloadError(RuntimeError):
    """apkeep 执行返回非零退出码或未能取到预期结果。"""


@dataclass(frozen=True)
class DownloadResult:
    package: str
    version: str | None
    output_dir: Path
    artifacts: list[Path]            # 实际下载到的文件
    sha256: dict[Path, str]          # 每个产物的 SHA-256
    returncode: int


# 其值需在日志中掩码的 flag
_SENSITIVE_FLAGS = {"-t", "--oauth-token", "--auth-token"}


class Downloader:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._apkeep = self._locate_apkeep()

    def _locate_apkeep(self) -> str:
        if self.config.apkeep_path:
            return self.config.apkeep_path
        found = shutil.which("apkeep")
        if not found:
            raise ApkeepNotFoundError(
                "找不到 apkeep。请安装 apkeep（见 README），"
                "或在配置文件 [general] apkeep_path 指定完整路径。"
            )
        return found

    def _build_command(
        self,
        package: str,
        version: str | None,
        output_dir: Path,
    ) -> list[str]:
        """构建 apkeep 下载命令行。

        参考 apkeep 用法：
          apkeep -a <pkg>[@<ver>] -d google-play -e <email> -t <token>
                 -o device=... -o split_apk=true <output_dir>
        """
        app = f"{package}@{version}" if version else package
        cmd = [self._apkeep, "-a", app, "-d", self.config.source]

        cred: Credentials = self.config.credentials
        if not cred.is_complete:
            raise DownloadError(
                "凭证不完整：需要在配置中设置 credentials.email 和 credentials.aas_token。"
            )
        cmd += ["-e", cred.email, "-t", cred.aas_token]

        if self.config.options.accept_tos:
            cmd.append("--accept-tos")

        opts: DownloadOptions = self.config.options
        for kv in opts.to_apkeep_options():
            cmd += ["-o", kv]

        cmd.append(str(output_dir))
        return cmd

    def request_aas_token(self, email: str, oauth_token: str) -> str:
        """用一次性 OAuth token 通过 apkeep 换取长期 AAS token。

        apkeep 输出格式（见 google_play.rs::request_aas_token）：
          成功 -> "AAS Token: <token>"
          失败 -> "Error: was not able to retrieve AAS token ..."

        注意：OAuth token 是单次有效的，调用一次即被消耗。
        """
        cmd = [self._apkeep, "-e", email, "--oauth-token", oauth_token]
        device = self.config.options.device
        if device:
            cmd += ["-o", f"device={device}"]

        log.info("向 apkeep 请求 AAS token（OAuth token 一次性，将被消耗）")
        log.debug("执行: %s", self._mask_command(cmd))

        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        combined = (proc.stdout + "\n" + proc.stderr).strip()
        if combined:
            log.debug("[apkeep] %s", combined)

        token = None
        for line in proc.stdout.splitlines():
            if line.strip().startswith("AAS Token:"):
                token = line.split("AAS Token:", 1)[1].strip()
                break

        if not token:
            raise DownloadError(
                "未能获取 AAS token。apkeep 输出:\n"
                f"{combined or '(无输出)'}\n"
                "OAuth token 已被消耗，请重新从浏览器抓取新的 OAuth token 再试。"
            )
        return token

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def download(
        self,
        package: str,
        version: str | None = None,
        output_dir: Path | None = None,
    ) -> DownloadResult:
        package = package.strip()
        if not package:
            raise DownloadError("包名为空")

        # apkeep 会在 outpath 下自建 <appid>/ 子目录存放 split，这里不再拼接包名
        out = output_dir or self.config.output_dir
        out.mkdir(parents=True, exist_ok=True)

        # 记录下载前已有文件，用于精确识别本次新增产物
        before = {p for p in out.rglob("*") if p.is_file()}

        cmd = self._build_command(package, version, out)
        log.info("执行: %s", self._mask_command(cmd))

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.stdout:
            log.info("[apkeep stdout]\n%s", proc.stdout.strip())
        if proc.stderr:
            log.warning("[apkeep stderr]\n%s", proc.stderr.strip())

        artifacts = sorted(p for p in out.rglob("*") if p.is_file() and p not in before)
        # 若目录本就为空（before 为空），fallback 到全部文件
        if not artifacts and not before:
            artifacts = sorted(p for p in out.rglob("*") if p.is_file())

        sha = {p: self._sha256(p) for p in artifacts}

        result = DownloadResult(
            package=package,
            version=version,
            output_dir=out,
            artifacts=artifacts,
            sha256=sha,
            returncode=proc.returncode,
        )

        if proc.returncode != 0:
            log.error("apkeep 退出码 %s，下载可能失败", proc.returncode)

        self._log_result(result)
        return result

    @staticmethod
    def _mask_command(cmd: list[str]) -> str:
        """记录命令时屏蔽敏感 flag 的取值（-t / --oauth-token / --auth-token）。"""
        out = []
        skip_next = False
        for token in cmd:
            if skip_next:
                out.append("***")
                skip_next = False
            elif token in _SENSITIVE_FLAGS:
                out.append(token)
                skip_next = True
            else:
                out.append(token)
        return " ".join(out)

    @staticmethod
    def _log_result(result: DownloadResult) -> None:
        log.info("=" * 60)
        log.info("包名: %s%s", result.package,
                 f"  版本: {result.version}" if result.version else "")
        log.info("输出: %s", result.output_dir)
        if not result.artifacts:
            log.warning("未下载到任何产物文件")
        for p, digest in result.sha256.items():
            log.info("  %s  %s", digest, p.name)
        log.info("=" * 60)


# ------------------------------------------------------------------
# Windows 栈溢出修复：apkeep 在 Windows 主线程栈默认 1MB，
# 下载 Google Play 时易 STATUS_STACK_OVERFLOW (0xC00000FD)。
# 用 editbin /STACK 增大 PE 头的 SizeOfStackReserve 即可。
# ------------------------------------------------------------------

def read_stack_reserve(exe_path: str) -> int | None:
    """读取 PE32+ 的 SizeOfStackReserve（字节）；非 PE32+ 或读取失败返回 None。"""
    try:
        with open(exe_path, "rb") as f:
            d = f.read(0x400)
        e_lfanew = struct.unpack("<I", d[0x3c:0x40])[0]
        if d[e_lfanew:e_lfanew + 4] != b"PE\x00\x00":
            return None
        opt = e_lfanew + 24
        if struct.unpack("<H", d[opt:opt + 2])[0] != 0x20b:  # 仅 PE32+
            return None
        return struct.unpack("<Q", d[opt + 0x48:opt + 0x50])[0]
    except OSError:
        return None


def find_editbin() -> str | None:
    """在常见 Visual Studio 安装路径查找 editbin.exe，找不到返回 None。

    用 ProgramFiles 环境变量构造 Windows 原生路径（C:\\...），
    不能用 MSYS 风格的 /c/...，Python 在 win32 不识别。
    """
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    patterns = [
        f"{pf}/Microsoft Visual Studio/*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/editbin.exe",
        f"{pf86}/Microsoft Visual Studio/*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/editbin.exe",
    ]
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return shutil.which("editbin")


def fix_stack_size(exe_path: str, size: int = 32 * 1024 * 1024) -> tuple[bool, str]:
    """用 editbin 增大 apkeep.exe 主线程栈。返回 (成功, editbin路径或错误信息)。"""
    editbin = find_editbin()
    if not editbin:
        return False, "找不到 editbin.exe（需安装 Visual Studio Build Tools）"
    proc = subprocess.run(
        [editbin, f"/STACK:{size}", exe_path],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        return False, f"editbin 退出码 {proc.returncode}: {proc.stderr.strip()}"
    return True, editbin
