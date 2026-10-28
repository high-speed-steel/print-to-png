import json
import logging
import os
from pathlib import Path
from typing import Dict


DEFAULT_CONFIG = {
    "default_dpi": 1200,
    "last_save_dir": "",
}
SUPPORTED_DPI_OPTIONS = (150, 300, 600, 1200, 2400, 4800)


def load_config(config_file: Path, logger: logging.Logger) -> Dict:
    cfg = dict(DEFAULT_CONFIG)
    if config_file.exists():
        try:
            loaded = json.loads(config_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except Exception as exc:
            logger.warning(f"讀取 config.json 失敗，使用預設值：{exc}")
    else:
        save_config(config_file, cfg, logger)
    return cfg


def save_config(config_file: Path, cfg: Dict, logger: logging.Logger) -> None:
    try:
        config_file.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"寫入 config.json 失敗：{exc}")


def get_default_save_dir(cfg: Dict) -> str:
    last_dir = cfg.get("last_save_dir", "")
    if last_dir and Path(last_dir).exists():
        return str(Path(last_dir).resolve())

    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            val, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
            expanded = Path(os.path.expandvars(val))
            if expanded.exists():
                return str(expanded.resolve())
    except Exception:
        pass

    desktop = Path(os.environ.get("USERPROFILE", "~")).expanduser() / "Desktop"
    return str(desktop.resolve())
