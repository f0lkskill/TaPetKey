import tkinter as tk
from modules.log import *

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

        # 进入窗口挂起阶段
        self.init_window()

    def init_window(self):
        self.title("TaPetKey")
        self.geometry("400x300")
        self.attributes("-topmost", True)
        self.attributes('-transparentcolor', 'black')


if __name__=="__main__":
    app = TaPetKeyMain()
    app.mainloop()