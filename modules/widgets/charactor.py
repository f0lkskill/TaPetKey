
from modules.log import TaPetKeyLogger
from modules.skin_loader import *
import tkinter as tk
from time import sleep
from threading import Thread
from random import randint

class Charactor(tk.Canvas):
    """_角色类_
    """
    def __init__(self, asset_id='base', image_scale:float=1.0, switch_func=None, **kwargs) -> None:
        """_初始化角色_

        Args:
            asset_id (str, optional): _素材ID_. 默认是 'base'.
            image_scale (float, optional): _图像缩放比例_. 默认是 1.0.
            switch_func (_type_, optional): _切换回调函数_. 默认是 None.
        """
        super().__init__(**kwargs)
        self.skin_assets:list[ImageAsset]
        self.current_image:ImageAsset = None # type: ignore
        self.id_name = asset_id
        self.image_scale:float = image_scale
        self.cache_tk_img:ImageTk.PhotoImage = None # type: ignore
        self.switch_func = switch_func
        self.current_switch_thread:Thread = None # type: ignore
        self.clean_flag = False
        self.switch_frequency = 0

        # 载入皮肤资源
        self.load_skin_res(asset_id)

        # 默认切换到 normal1
        self.switch_image("normal_1")
        
        self.switch_thread = Thread(target=self.base_switch, daemon=True) # type: ignore
        # self.switch_thread.start()

    def switch_image(self, signal_asset_id:str):
        """_切换当前显示的图像_

        Args:
            signal_asset_id (str): _要切换到的图像资产ID_
        """
        image_asset = next((asset for asset in self.skin_assets if asset.base_name == signal_asset_id), None) # type: ignore
        if image_asset:
            TaPetKeyLogger.debug(f"{self.id_name} 切换到图像资产: {signal_asset_id}")
            self.current_image = image_asset

            # 更新控件图像
            self.update_image()

    def get_real_size(self):
        """_根据缩放比例获取实际尺寸_

        Returns:
            _type_: _(width, height)
        """
        return int(self.current_image.width * self.image_scale), \
               int(self.current_image.height * self.image_scale)

    def exists_id(self, asset_id: str):
        return any(asset.base_name == asset_id for asset in self.skin_assets)

    def update_image(self):
        """_更新当前显示的图像_
        """
        if self.current_image:
            real_size:tuple = self.get_real_size()
            new_image = self.current_image.image.resize(
                real_size,
                Image.LANCZOS # type: ignore
            )
            self.cache_tk_img = ImageTk.PhotoImage(new_image)

            # 先清除
            self.delete('all')

            # 更新图像显示逻辑
            self.create_image(
                real_size[0] // 2,
                real_size[1] // 2,
                image = self.cache_tk_img,
                anchor = tk.CENTER
            )
            # TaPetKeyLogger.debug(f"{self.id_name} 更新图像显示: {self.current_image}")

    def load_skin_res(self, asset_id='base'):
        """_为程序载入皮肤资源_

        Args:
            asset_id (str, optional): _皮肤ID_. 默认是 'base'.
        """
        self.skin_assets = get_all_assets_tk_by_id(asset_id)
        TaPetKeyLogger.success(f"{self.id_name} 皮肤资源加载完成")

    def base_switch(self, asset_id: str):
        # TaPetKeyLogger.debug(f"基础切换事件触发 {self.switch_func}")

        # 进入触发切换流程
        self.switch_image(asset_id)
        
        if self.switch_frequency >= 1:
            return False

        if not self.current_switch_thread or not self.current_switch_thread.is_alive():
            # 同一时间只能有一个回调进程
            def pack():
                self.switch_func() # type: ignore
                self.switch_frequency = 0

            # 开跑
            self.current_switch_thread = Thread(target=pack, daemon=True) # type: ignore
            try:self.current_switch_thread.start()
            except Exception as e:TaPetKeyLogger.error("切换线程启动失败, {}", e)

        self.switch_frequency += 1

        return True

    def normal_round(self):
        """_执行正常normal动画_
        """
        total_normal = 0
        for assets in self.skin_assets:
            if assets.base_name.startswith("normal"):
                total_normal += 1
        # 随机图片切换

        self.base_switch(f"normal_{randint(1, total_normal)}")