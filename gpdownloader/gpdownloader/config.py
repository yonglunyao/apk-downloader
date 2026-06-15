"""凭证与下载配置管理。

配置查找顺序（优先级从高到低）：
  1. CLI --config 指定的路径
  2. 环境变量 GPDOWNLOADER_CONFIG
  3. 当前目录 config/config.toml
  4. 用户目录 ~/.gpdownloader/config.toml

任何 Google 凭证都应放在配置文件中，切勿硬编码或提交到版本库。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


class ConfigNotFoundError(FileNotFoundError):
    """找不到可用的配置文件。"""


@dataclass(frozen=True)
class Credentials:
    """Google Play 认证凭证（apkeep 的 -e / -t 参数）。"""
    email: str
    aas_token: str

    @property
    def is_complete(self) -> bool:
        return bool(self.email) and bool(self.aas_token)


@dataclass(frozen=True)
class DownloadOptions:
    """apkeep 下载选项（映射到 -o key=value）。"""
    device: str | None = None          # 设备 profile，如 redfin
    split_apk: bool = True             # 下载 split APK（App Bundle 拆包）
    obb: bool = False                  # 下载 OBB 扩展文件
    accept_tos: bool = False           # 首次使用需接受 Play 条款

    def to_apkeep_options(self) -> list[str]:
        opts: list[str] = []
        if self.device:
            opts.append(f"device={self.device}")
        opts.append(f"split_apk={'true' if self.split_apk else 'false'}")
        if self.obb:
            opts.append("obb=true")
        return opts


@dataclass(frozen=True)
class Config:
    credentials: Credentials
    options: DownloadOptions = field(default_factory=DownloadOptions)
    source: str = "google-play"
    output_dir: Path = Path("downloads")
    apkeep_path: str | None = None     # None 表示用 PATH 中的 apkeep

    # 配置文件候选位置
    ENV_VAR = "GPDOWNLOADER_CONFIG"
    LOCAL_PATH = Path("config/config.toml")
    USER_PATH = Path.home() / ".gpdownloader" / "config.toml"

    @classmethod
    def resolve_path(cls, explicit: str | None = None) -> Path:
        """按优先级解析配置文件路径。"""
        candidates: list[Path] = []
        if explicit:
            candidates.append(Path(explicit))
        env = os.environ.get(cls.ENV_VAR)
        if env:
            candidates.append(Path(env))
        candidates.append(cls.LOCAL_PATH.resolve())
        candidates.append(cls.USER_PATH)
        for p in candidates:
            if p.is_file():
                return p
        raise ConfigNotFoundError(
            "未找到配置文件。已查找:\n  - "
            + "\n  - ".join(str(c) for c in candidates)
            + "\n请参照 config/config.example.toml 创建。"
        )

    @classmethod
    def load(cls, explicit: str | None = None) -> "Config":
        path = cls.resolve_path(explicit)
        with open(path, "rb") as f:
            data = tomllib.load(f)

        cred = data.get("credentials", {})
        credentials = Credentials(
            email=cred.get("email", ""),
            aas_token=cred.get("aas_token", ""),
        )

        opt = data.get("options", {})
        options = DownloadOptions(
            device=opt.get("device"),
            split_apk=opt.get("split_apk", True),
            obb=opt.get("obb", False),
            accept_tos=opt.get("accept_tos", False),
        )

        general = data.get("general", {})
        return cls(
            credentials=credentials,
            options=options,
            source=general.get("source", "google-play"),
            output_dir=Path(general.get("output_dir", "downloads")),
            apkeep_path=general.get("apkeep_path"),
        )


# 敏感凭证赋值行的正则（限定为 TOML 键名）
_CRED_LINE = {
    "email": re.compile(r'^(\s*)email\s*=.*$', re.MULTILINE),
    "aas_token": re.compile(r'^(\s*)aas_token\s*=.*$', re.MULTILINE),
}


def update_credentials(
    path: Path,
    email: str | None = None,
    aas_token: str | None = None,
) -> None:
    """原地更新 config.toml 中的 email / aas_token，保留其他字段与注释。

    用行级正则替换而非全量重写，以保留下方的中文注释和格式。
    """
    if email is None and aas_token is None:
        return
    text = path.read_text(encoding="utf-8")
    if email is not None:
        text = _CRED_LINE["email"].sub(
            lambda m: f'{m.group(1)}email = "{email}"', text
        )
    if aas_token is not None:
        text = _CRED_LINE["aas_token"].sub(
            lambda m: f'{m.group(1)}aas_token = "{aas_token}"', text
        )
    path.write_text(text, encoding="utf-8")
