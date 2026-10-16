import os
from modules.log import TaPetKeyLogger

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

