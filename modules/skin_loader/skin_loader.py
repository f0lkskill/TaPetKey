import os
from PIL import Image, ImageTk
from modules.log import TaPetKeyLogger
from .assets import ImageAsset
import glob

def get_skin_path_by_id(asset_id) -> str | None:
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

def get_all_assets_tk_by_id(asset_id) -> list[ImageAsset]:
    """_获取指定ID的所有皮肤图像（Tkinter格式）_

    Args:
        asset_id (_type_): _皮肤ID_

    Returns:
        list[ImageAsset]: _所有皮肤图像（Tkinter格式）_
    """
    all_png_path = glob.glob(os.path.join("assets", "skins", asset_id, "*.png"))
    all_images = []
    for path in all_png_path:
        img = Image.open(path)
        img_tk = ImageTk.PhotoImage(img)
        all_images.append(ImageAsset(path, img_tk))
    return all_images