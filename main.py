import tkinter as tk
from modules.log import *
from modules.skin_loader import *
from modules.widgets.charactor import *
from modules.keyborad import *
from random import randint
import time

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
        self.grvaity:float = 3
        self.update_internal:float = 0.01

        self.transparentcolor = "#000000"

        # 初始化键盘触发器
        self.keyboard_trigger = KeyboardTrigger()

        # 进入窗口挂起阶段
        self.init_window_attr()

        # 加载控件资源
        self.init_app_widgets()

        Thread(target=self.main_process, daemon=True).start()

    def main_process(self) -> None:
        while(1):
            time.sleep(self.update_internal)
            while(len(self.keyboard_trigger.queue_events) > 0):
                event = self.keyboard_trigger.queue_events[0]

                if self.current_charactor.exists_id(f"key_{event.name}"):
                    # 存在合法id，特殊事件解析成功
                    self.current_charactor.base_switch(f"key_{event.name}")
                else:
                    # 正常动画处理
                    self.current_charactor.normal_round()

                if len(self.keyboard_trigger.queue_events) != 0:
                    # 有队列，进行 pop 完成处理。
                    self.keyboard_trigger.queue_events.pop(0)
                    
                # 切出
                if len(self.keyboard_trigger.queue_events) == 0:
                    self.after(300, lambda:
                    # 符合没有剩下的事件，进行恢复
                    self.current_charactor.normal_round() \
                    if len(self.keyboard_trigger.queue_events) == 0 \
                    else TaPetKeyLogger.warning("idle 自恢复进程被打断。"))

    def random_bounce_event(self):
        self.bounce_event(randint(5, 15))

    def bounce_event(self, strength:float):
        """_触发窗口_

        Args:
            strength (float): _弹跳力度大小_
        """
        initial_y = self.winfo_y()
        total_offset = 0

        TaPetKeyLogger.debug(f"弹跳事件触发，力度: {strength}")

        while(strength > 0):
            # 向上动量消耗
            total_offset += strength
            self.geometry(f"+{self.winfo_x()}+{int(self.winfo_y()-strength)}")
            strength -= self.grvaity
            time.sleep(self.update_internal)

        while(total_offset > 0):
            # 重力向下
            total_offset -= strength
            self.geometry(f"+{self.winfo_x()}+{int(self.winfo_y()+strength)}")
            strength += self.grvaity
            time.sleep(self.update_internal)

        # 回归初始坐标
        self.geometry(f"+{self.winfo_x()}+{initial_y}")

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
        self.config(bg=self.transparentcolor)
        self.attributes('-transparentcolor', self.transparentcolor)
        self.overrideredirect(True)

        # self.attributes('-disabled', True)  # 忽略鼠标事件，实现穿透

        self.bind_window_event()

    def init_app_widgets(self):
        """_初始化应用程序部件_"""
        self.current_charactor = \
        Charactor(
            asset_id='base', bg = self.transparentcolor,
            master=self, image_scale=0.5,
            switch_func=self.random_bounce_event,
            width=250, height=250
        )
        self.current_charactor.pack(side=tk.TOP)

    def test(self):
        TaPetKeyLogger.debug(f"获取到 base 皮肤图像表单：{get_all_assets_tk_by_id('base')[1]}")

if __name__=="__main__":
    app = TaPetKeyMain()
    app.mainloop()