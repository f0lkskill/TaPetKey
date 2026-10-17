import tkinter as tk
from modules.log import *
from modules.skin_loader import *
from modules.widgets.charactor import *

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

        self.current_charactor:Charactor
        self._offset_x = 0
        self._offset_y = 0

        # 进入窗口挂起阶段
        self.init_window_attr()

        # 加载控件资源
        self.init_app_widgets()

    def start_move():
        pass

    def init_window_attr(self):
        self.title("TaPetKey")
        self.geometry("250x250")
        self.attributes("-topmost", True)
        self.config(bg='black')
        self.attributes('-transparentcolor', 'black')
        self.overrideredirect(True)

    def init_app_widgets(self):
        self.current_charactor = Charactor(asset_id='base',image_scale=0.5, bg = 'black', width=250, height=250)
        self.current_charactor.pack(side=tk.TOP)

    def test(self):
        TaPetKeyLogger.debug(f"获取到 base 皮肤图像表单：{get_all_assets_tk_by_id('base')[1]}")

if __name__=="__main__":
    app = TaPetKeyMain()
    app.mainloop()