import tkinter as tk
import ctypes
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
        self._drag_start_x = 0
        self._drag_start_y = 0

        # 进入窗口挂起阶段
        self.init_window_attr()

        # 加载控件资源
        self.init_app_widgets()

    def apply_ctypes(self):
        """_效用 ctypes 的属性_"""
        # 获取窗口句柄
        hwnd = ctypes.windll.user32.GetParent(self.winfo_id())

        # 修改窗口样式：添加 WS_EX_TRANSPARENT 和 WS_EX_LAYERED
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x80000
        WS_EX_TRANSPARENT = 0x20

        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)

    def start_move(self, event) -> None:
        """_更新窗口偏移量_

        Args:
            event (_type_): _TK标准事件_
        """
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def update_move(self, event) -> None:
        """_更新窗口位置_

        Args:
            event (_type_): _TK标准事件_
        """
        delta_x = event.x_root - self._drag_start_x
        delta_y = event.y_root - self._drag_start_y
        x_new = self.winfo_x() + delta_x
        y_new = self.winfo_y() + delta_y
        self.geometry(f"+{x_new}+{y_new}")

        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def bind_window_event(self):
        """_绑定窗口事件_"""
        self.bind("<Button-1>", self.start_move)
        self.bind("<B1-Motion>", self.update_move)

    def init_window_attr(self):
        self.title("TaPetKey")
        self.geometry("250x250")
        self.attributes("-topmost", True)
        self.config(bg='black')
        self.attributes('-transparentcolor', 'black')
        self.overrideredirect(True)
        
        # self.attributes('-disabled', True)  # 忽略鼠标事件，实现穿透

        self.bind_window_event()

    def init_app_widgets(self):
        self.current_charactor = Charactor(asset_id='base',image_scale=0.5, bg = 'black', width=250, height=250)
        self.current_charactor.pack(side=tk.TOP)

    def test(self):
        TaPetKeyLogger.debug(f"获取到 base 皮肤图像表单：{get_all_assets_tk_by_id('base')[1]}")

if __name__=="__main__":
    app = TaPetKeyMain()
    app.mainloop()