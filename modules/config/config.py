"""_项目配置库，所有配置统一由注册表管理。_
"""
import os
import sys
import winreg

from modules.log import TaPetKeyLogger

# 项目根目录：源码运行时为 main.py 所在目录；打包运行时为 exe 所在目录
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

APP_NAME = "TaPetKey"
EXE_NAME = "TaPetKey.exe"

# 统一配置键
CONFIG_KEY = r"Software\TaPetKey"
# 开机自启动键
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# 自启动在 Run 键中的值名
AUTOSTART_VALUE = APP_NAME

# 其余持久化配置的值名
SKIN_VALUE = "skin"         # 最后使用的皮肤ID
SCALE_VALUE = "scale"       # 整体缩放比例
POS_X_VALUE = "win_x"       # 主窗口最后的 X
POS_Y_VALUE = "win_y"       # 主窗口最后的 Y


def get_exe_path() -> str:
    """_获取默认程序路径_

    指向 main.py 运行根目录下的 TaPetKey.exe（无论该文件是否存在）。
    """
    return os.path.join(BASE_DIR, EXE_NAME)


def _open_config_key(write: bool = False):
    """_打开（必要时创建）统一配置键_"""
    access = winreg.KEY_WRITE if write else winreg.KEY_READ
    try:
        return winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, CONFIG_KEY, 0, access)
    except OSError as e:
        TaPetKeyLogger.error(f"打开配置注册表失败: {e}")
        return None


def get_config(name: str, default=None):
    """_读取配置值_"""
    key = _open_config_key(write=False)
    if key is None:
        return default
    try:
        value, _ = winreg.QueryValueEx(key, name)
        return value
    except FileNotFoundError:
        return default
    except OSError as e:
        TaPetKeyLogger.error(f"读取配置 {name} 失败: {e}")
        return default
    finally:
        winreg.CloseKey(key)


def set_config(name: str, value) -> bool:
    """_写入配置值_"""
    key = _open_config_key(write=True)
    if key is None:
        return False
    try:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
        return True
    except OSError as e:
        TaPetKeyLogger.error(f"写入配置 {name} 失败: {e}")
        return False
    finally:
        winreg.CloseKey(key)


def is_autostart_enabled() -> bool:
    """_是否已设置开机自启动_"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
    except OSError as e:
        TaPetKeyLogger.warning(f"打开自启动注册表失败: {e}")
        return False
    try:
        winreg.QueryValueEx(key, AUTOSTART_VALUE)
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        TaPetKeyLogger.error(f"读取自启动项失败: {e}")
        return False
    finally:
        winreg.CloseKey(key)


def set_autostart(enabled: bool) -> bool:
    """_设置/取消开机自启动_

    自启动项始终指向 main.py 运行根目录下的 TaPetKey.exe（无论是否存在）。
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                             winreg.KEY_SET_VALUE)
    except OSError as e:
        TaPetKeyLogger.error(f"打开自启动注册表失败: {e}")
        return False
    try:
        if enabled:
            winreg.SetValueEx(key, AUTOSTART_VALUE, 0, winreg.REG_SZ,
                              f'"{get_exe_path()}"')
            TaPetKeyLogger.info(f"已启用开机自启动: {get_exe_path()}")
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_VALUE)
            except FileNotFoundError:
                pass
            TaPetKeyLogger.info("已关闭开机自启动")
        return True
    except OSError as e:
        TaPetKeyLogger.error(f"设置自启动失败: {e}")
        return False
    finally:
        winreg.CloseKey(key)
