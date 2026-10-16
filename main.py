import tkinter as tk
from modules.log import *
from modules.skin_loader import *

class TaPetKeyMain(tk.Tk):
    """TaPetKey 程序的主窗口类体。

    Args:
        tk (_type_): _继承自原生tkinter_
    """
    def __init__(self):
        """
        初始化主程序。
        同时进行主窗口程序的拉起。
        """
        super().__init__()

        TaPetKeyLogger.info("主程序进入初始化流程")

        self.skin_assets = {}

        # 进入窗口挂起阶段
        self.init_window_attr()

        # 载入皮肤资源
        self.load_skin_res()

    def load_skin_res(self, asset_id='base'):
        """_为程序载入皮肤资源_

        Args:
            asset_id (str, optional): _皮肤ID_. 默认是 'base'.
        """
        self.skin_assets = get_all_assets_tk_by_id(asset_id)

    def init_window_attr(self):
        self.title("TaPetKey")
        self.geometry("400x300")
        self.attributes("-topmost", True)
        self.attributes('-transparentcolor', 'black')

    def test(self):
        TaPetKeyLogger.debug(f"获取到 base 皮肤图像表单：{get_all_assets_tk_by_id('base')[1]}")

if __name__=="__main__":
    app = TaPetKeyMain()
    app.mainloop()