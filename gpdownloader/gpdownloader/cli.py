"""命令行入口。

用法:
  python -m gpdownloader auth -e <email> --oauth-token <oauth2_4/...>
                                    # 用一次性 OAuth token 换取 AAS token 并写回 config
  python -m gpdownloader download <package> [-c VERSION] [选项]
  python -m gpdownloader batch <file>      # 每行一个包名，#开头为注释
  python -m gpdownloader fix-stack          # 修复 Windows 上 apkeep 栈溢出（一键）
  python -m gpdownloader doctor             # 检查 apkeep / 凭证 / 栈大小是否就绪
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import Config, ConfigNotFoundError, update_credentials
from .downloader import (
    ApkeepNotFoundError,
    Downloader,
    DownloadError,
    fix_stack_size,
    read_stack_reserve,
)

# Windows 上低于此值（字节）认为栈偏小，可能栈溢出
_MIN_STACK = 16 * 1024 * 1024


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _load_config(args) -> Config:
    try:
        return Config.load(getattr(args, "config", None))
    except ConfigNotFoundError as e:
        logging.error("%s", e)
        sys.exit(2)


def _stack_label(stk: int | None) -> str:
    return f"{stk / 1024 / 1024:.1f} MB" if stk else "未知"


def cmd_auth(args) -> int:
    """用一次性 OAuth token 换取长期 AAS token，并写回 config.toml。"""
    if not args.oauth_token.startswith("oauth2_4/"):
        logging.warning("OAuth token 通常以 'oauth2_4/' 开头，请确认是否复制完整")

    config = _load_config(args)
    try:
        dl = Downloader(config)
    except ApkeepNotFoundError as e:
        logging.error("%s", e)
        return 3

    try:
        aas_token = dl.request_aas_token(args.email, args.oauth_token)
    except DownloadError as e:
        logging.error("%s", e)
        return 1

    logging.info("成功获取 AAS token（长度 %d）", len(aas_token))

    cfg_path = Config.resolve_path(getattr(args, "config", None))
    update_credentials(cfg_path, email=args.email, aas_token=aas_token)
    logging.info("已写入 config: %s", cfg_path)
    logging.info("AAS token 是长期有效的，以后可直接用 download/batch 命令。")
    logging.info("下一步: python -m gpdownloader doctor")
    return 0


def cmd_download(args) -> int:
    config = _load_config(args)
    try:
        dl = Downloader(config)
    except ApkeepNotFoundError as e:
        logging.error("%s", e)
        return 3

    try:
        result = dl.download(
            package=args.package,
            version=args.version,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
    except DownloadError as e:
        logging.error("%s", e)
        return 1

    return result.returncode


def cmd_batch(args) -> int:
    config = _load_config(args)
    try:
        dl = Downloader(config)
    except ApkeepNotFoundError as e:
        logging.error("%s", e)
        return 3

    packages = _read_package_list(Path(args.file))
    if not packages:
        logging.warning("包名列表为空")
        return 0

    logging.info("共 %d 个包待下载", len(packages))
    failed: list[str] = []
    for i, pkg in enumerate(packages, 1):
        logging.info("[%d/%d] %s", i, len(packages), pkg)
        try:
            r = dl.download(pkg, version=args.version)
            if r.returncode != 0:
                failed.append(pkg)
        except DownloadError as e:
            logging.error("%s: %s", pkg, e)
            failed.append(pkg)

    logging.info("完成。成功 %d，失败 %d", len(packages) - len(failed), len(failed))
    if failed:
        logging.warning("失败包名:\n  %s", "\n  ".join(failed))
        return 1
    return 0


def cmd_fix_stack(args) -> int:
    """增大 apkeep.exe 主线程栈，修复 Windows 栈溢出（STATUS_STACK_OVERFLOW）。"""
    config = _load_config(args)
    try:
        dl = Downloader(config)
    except ApkeepNotFoundError as e:
        logging.error("%s", e)
        return 3

    exe = dl._apkeep
    target = args.size * 1024 * 1024
    before = read_stack_reserve(exe)
    logging.info("apkeep: %s", exe)
    logging.info("当前栈保留: %s", _stack_label(before))

    if before and before >= target:
        logging.info("栈已 >= %d MB，无需修复。", args.size)
        return 0

    bak = Path(exe + ".bak")
    try:
        shutil.copy(exe, bak)
        logging.info("已备份: %s", bak)
    except OSError as e:
        logging.warning("备份失败（继续）: %s", e)

    ok, msg = fix_stack_size(exe, target)
    if not ok:
        logging.error("修复失败: %s", msg)
        logging.error("备选：用 docker 运行 apkeep（Linux 栈大，不溢出）。")
        return 1

    after = read_stack_reserve(exe)
    logging.info("[OK] 修复成功（editbin: %s）", msg)
    logging.info("栈保留: %s -> %s", _stack_label(before), _stack_label(after))
    return 0


def cmd_doctor(args) -> int:
    """自检：apkeep / 凭证 / 栈大小是否就绪。"""
    config = _load_config(args)
    ok = True

    try:
        dl = Downloader(config)
        logging.info("[OK] apkeep 可用: %s", dl._apkeep)
    except ApkeepNotFoundError as e:
        logging.error("[X] %s", e)
        return 1  # apkeep 不可用则后续检查无意义

    # 栈大小检测（Windows 常见坑）
    stk = read_stack_reserve(dl._apkeep)
    if stk is None:
        logging.info("[--] 栈大小: 非 PE32+，跳过（可能非 Windows 二进制）")
    elif stk < _MIN_STACK:
        logging.warning("[!] apkeep 栈仅 %s，Windows 下载可能栈溢出(0xC00000FD)", _stack_label(stk))
        logging.warning("    运行 'python -m gpdownloader fix-stack' 一键修复")
        ok = False
    else:
        logging.info("[OK] apkeep 栈: %s", _stack_label(stk))

    # 凭证检测
    if config.credentials.is_complete:
        logging.info("[OK] 凭证完整: email=%s, aas_token=***(%d 字符)",
                     config.credentials.email, len(config.credentials.aas_token))
    else:
        logging.error("[X] 凭证不完整，请用 'auth' 命令或手动设置 credentials.email/aas_token")
        ok = False

    logging.info("  下载源: %s", config.source)
    logging.info("  设备 profile: %s", config.options.device or "(默认 px_9a)")
    logging.info("  输出目录: %s", config.output_dir)
    return 0 if ok else 1


def _read_package_list(path: Path) -> list[str]:
    pkgs: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkgs.append(line)
    return pkgs


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gpdownloader",
        description="输入包名从 Google Play 下载 APK 样本（封装 apkeep）",
    )
    p.add_argument("--version", action="version", version=f"gpdownloader {__version__}")
    p.add_argument("-v", "--verbose", action="store_true", help="调试日志")
    p.add_argument("-c", "--config", help="配置文件路径（默认自动查找）")

    sub = p.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("auth", help="用 OAuth token 换取 AAS token 并写回配置")
    pa.add_argument("-e", "--email", required=True, help="Google 账号邮箱")
    pa.add_argument("--oauth-token", required=True,
                    help="一次性 OAuth token（从浏览器 EmbeddedSetup 抓取，以 oauth2_4/ 开头）")
    pa.set_defaults(func=cmd_auth)

    pd = sub.add_parser("download", help="下载单个包")
    pd.add_argument("package", help="应用包名，如 com.example.app")
    pd.add_argument("-c", "--version", dest="version", help="指定版本号")
    pd.add_argument("-o", "--output-dir", help="覆盖配置中的输出目录")
    pd.set_defaults(func=cmd_download)

    pb = sub.add_parser("batch", help="从文件批量下载（每行一个包名）")
    pb.add_argument("file", help="包名列表文件")
    pb.add_argument("-c", "--version", dest="version", help="统一指定版本号（可选）")
    pb.set_defaults(func=cmd_batch)

    pfs = sub.add_parser("fix-stack", help="增大 apkeep.exe 栈，修复 Windows 栈溢出")
    pfs.add_argument("-s", "--size", type=int, default=32, help="栈大小（MB，默认 32）")
    pfs.set_defaults(func=cmd_fix_stack)

    pdoc = sub.add_parser("doctor", help="自检 apkeep / 凭证 / 栈大小")
    pdoc.set_defaults(func=cmd_doctor)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
