import json
import os
from PIL import Image, ImageTk
from modules.log import TaPetKeyLogger
from .assets import ImageAsset
import glob


def get_all_skins() -> list[dict]:
    """_获取所有皮肤的信息_

    扫描 assets/skins 下的每个目录，读取其 info.json 作为菜单描述。

    Returns:
        list[dict]: _每项为 {id, name, description, version, author, icon}_
    """
    skins_dir = os.path.join("assets", "skins")
    skins = []
    if not os.path.exists(skins_dir):
        TaPetKeyLogger.warning(f"未找到皮肤目录: {skins_dir}")
        return skins

    for name in sorted(os.listdir(skins_dir)):
        skin_path = os.path.join(skins_dir, name)
        if not os.path.isdir(skin_path):
            continue
        info = {}
        info_path = os.path.join(skin_path, "info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                TaPetKeyLogger.error(f"读取皮肤配置失败 {info_path}: {e}")
        skins.append({
            "id": name,
            "name": info.get("name", name),
            "description": info.get("description", ""),
            "version": info.get("version", ""),
            "author": info.get("author", ""),
            "icon": info.get("icon", ""),
        })
    return skins

# 皮肤 info.json 的可选字段默认值（缺失时回退）
DEFAULT_SKIN_INFO = {
    "scale": 0.5,               # 角色基准缩放比例
    "combo_offset": [0, 0],     # 气泡 combo 窗口相对主窗口左上角的偏移
    "effect_offset": [70, 20],  # 特效文本窗口相对主窗口中心的偏移
}


def get_skin_info(asset_id: str) -> dict:
    """_读取指定皮肤的完整配置_

    返回 info.json 的全部字段，并补齐可选字段的默认值。

    Args:
        asset_id (str): _皮肤ID（目录名）_

    Returns:
        dict: _皮肤配置_
    """
    info = dict(DEFAULT_SKIN_INFO)
    info_path = os.path.join("assets", "skins", asset_id, "info.json")
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info.update(json.load(f))
        except (OSError, json.JSONDecodeError) as e:
            TaPetKeyLogger.error(f"读取皮肤配置失败 {info_path}: {e}")
    else:
        TaPetKeyLogger.warning(f"未找到皮肤配置: {info_path}")
    return info


def get_skin_path_by_id(asset_id:str) -> str | None:
    """_获取皮肤路径_

    Args:
        asset_id (_type_): _皮肤ID，默认文件夹名称_

    Returns:
        str | None: _皮肤路径, 未找到时返回 None_
    """
    path_info = os.path.join("assets", "skins", asset_id)
    if os.path.exists(path_info):
        TaPetKeyLogger.info(f"获取到皮肤路径: {path_info}")
    else:
        TaPetKeyLogger.warning(f"未找到皮肤路径: {path_info}")
        return None
    return path_info

def get_all_assets_tk_by_id(asset_id:str) -> list[ImageAsset]:
    """_获取指定ID的所有皮肤图像（Tkinter格式）_

    Args:
        asset_id (_type_): _皮肤ID_

    Returns:
        list[ImageAsset]: _所有皮肤图像（Tkinter格式）_
    """
    skin_path = get_skin_path_by_id(asset_id)
    if not skin_path:
        return []
    all_png_path = glob.glob(os.path.join(skin_path, "*.png"))
    all_images = []
    # 载入
    for path in all_png_path:
        img = Image.open(path)
        all_images.append(ImageAsset(path, img))
    return all_images