"""_项目配置库，所有配置统一由注册表管理。_
"""

from .config import (
    CONFIG_KEY,
    RUN_KEY,
    AUTOSTART_VALUE,
    get_exe_path,
    get_config,
    set_config,
    is_autostart_enabled,
    set_autostart,
)

__all__ = [
    'CONFIG_KEY',
    'RUN_KEY',
    'AUTOSTART_VALUE',
    'get_exe_path',
    'get_config',
    'set_config',
    'is_autostart_enabled',
    'set_autostart',
]
