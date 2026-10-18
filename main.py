import time, os
import os
import tkinter as tk
from modules.log import *
from modules.skin_loader import *
from modules.widgets import *
from modules.keyborad import *
from modules.window import *
from random import randint

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
        self.app_tray:AppTray = AppTray(self._exit_app)
        self._drag_start_x = 0
        self._drag_start_y = 0
        self.grvaity:float = 3
        self.update_internal:float = 0.01
        self.combo_window = CounterWindow(master = self)
        self.effect_windows:list[EffectWindow] = []
        self.max_effect_windows:int = 3
        self.last_press_time:float = time.time()
        self.restore_time:float = 1.0

        # 弹跳动画状态
        self._is_bounce:bool = False
        self._bounce_initial_y:int = 0
        self._bounce_total:float = 0.0
        self._bounce_strength:float = 0.0
        self._bounce_phase:str = "up"
        self._bounce_on_finish = None

        self.transparentcolor = "#000000"

        # 初始化键盘触发器
        self.keyboard_trigger = KeyboardTrigger()
        
        # 进入窗口挂起阶段
        self.init_window_attr()

        # 加载控件资源
        self.init_app_widgets()

        # 主线程轮询事件队列（避免子线程操作 tkinter 导致窗口闪烁/崩溃）
        self.after(int(self.update_internal * 1000), self.main_process)
        self.after(int(self.update_internal * 1000), self.restore_check)

    def process_press_event(self) -> None:
        """_处理按下事件_"""

        event = self.keyboard_trigger.queue_press_events[0]

        # 清理已经销毁的窗口，避免列表无限增长
        self.effect_windows = [w for w in self.effect_windows if w.winfo_exists()]
        # 限制同时存在的效果窗口数量，防止长按时 CPU 打满
        if len(self.effect_windows) < self.max_effect_windows:
            # 可以创建新的窗口
            self.effect_windows.append(
                EffectWindow(show_text=event.name if event.name != 'backspace' else 'delete', master=self,
                             on_close=self._remove_effect_window))

        if self.current_charactor.exists_id(f"key_{event.name}"):
            # 存在合法id，特殊事件解析成功
            self.current_charactor.base_switch(f"key_{event.name}")
        else:
            # 正常动画处理
            self.current_charactor.normal_round()

        # 防止idle自恢复的打断。
        if self.keyboard_trigger.queue_press_events:
            self.last_press_time = time.time()
            self.keyboard_trigger.queue_press_events.pop(0)

    def restore_check(self):
        """检查是否要进行贴图恢复"""
        if time.time() - self.last_press_time > self.restore_time:
            if len(self.keyboard_trigger.queue_press_events) == 0 and \
                'normal' not in self.current_charactor.current_image.base_name:
                # 这里排除最后一个动画是正常打字
                if 'miss' not in self.current_charactor.current_image.base_name:
                    # 正常进行轮换
                    TaPetKeyLogger.debug(f"detail: {self.current_charactor.current_image.base_name}," \
                                            f" current: {len(self.keyboard_trigger.queue_press_events)}")
                    self.current_charactor.normal_round()
                    TaPetKeyLogger.success("自恢复进程条件满足，进行恢复。")

        # 循环检测
        self.after(int(self.update_internal * 1000), self.restore_check)

    def process_release_event(self) -> None:
        """_处理释放事件_"""
        self.combo_window.add_one()
        self.keyboard_trigger.queue_release_events.pop(0)

    def _remove_effect_window(self, window) -> None:
        """_效果窗口关闭时从列表中移除_"""
        if window in self.effect_windows:
            self.effect_windows.remove(window)

    def main_process(self) -> None:
        # 每帧限量处理，长按连发时也要让主线程及时返回事件循环，避免卡死
        max_per_tick = 2
        processed = 0
        while processed < max_per_tick and \
              len(self.keyboard_trigger.queue_press_events) + \
              len(self.keyboard_trigger.queue_release_events) > 0:
            try:
                if len(self.keyboard_trigger.queue_press_events) > 0:
                    # 开始处理事件
                    self.process_press_event()
                elif len(self.keyboard_trigger.queue_release_events) > 0:
                    # 开始处理释放事件
                    self.process_release_event()

            except Exception as e:
                TaPetKeyLogger.error(f"处理键盘事件时发生错误：{e}")
            processed += 1

        # 主线程 after 轮询
        self.after(int(self.update_internal * 1000), self.main_process)

    def random_bounce_event(self, on_finish=None):
        self.bounce_event(randint(5, 15), on_finish)

    def bounce_event(self, strength:float, on_finish=None):
        """_触发窗口_

        Args:
            strength (float): _弹跳力度大小_
        """
        # TaPetKeyLogger.debug(f"弹跳事件触发，力度: {strength}")
        if self._is_bounce:
            return

        self._is_bounce = True
        self._bounce_initial_y = self.winfo_y()
        self._bounce_total = 0.0
        self._bounce_strength = float(strength)
        self._bounce_phase = "up"
        self._bounce_on_finish = on_finish
        self._bounce_step()

    def _bounce_step(self):
        """_弹跳动画单帧（主线程 after 驱动）_"""
        interval = max(1, int(self.update_internal * 1000))

        if self._bounce_phase == "up":
            if self._bounce_strength > 0:
                # 向上动量消耗
                self._bounce_total += self._bounce_strength
                self.geometry(f"+{self.winfo_x()}+{int(self.winfo_y()-self._bounce_strength)}")
                self.combo_window.geometry(f"+{self.winfo_x()}+{int(self.winfo_y()-self._bounce_strength)}")
                self._bounce_strength -= self.grvaity
                self.after(interval, self._bounce_step)
                return
            self._bounce_phase = "down"
            self.after(interval, self._bounce_step)
            return

        if self._bounce_total > 0:
            # 重力向下
            self._bounce_total -= self._bounce_strength
            self.geometry(f"+{self.winfo_x()}+{int(self.winfo_y()+self._bounce_strength)}")
            self.combo_window.geometry(f"+{self.winfo_x()}+{int(self.winfo_y()+self._bounce_strength)}")
            self._bounce_strength += self.grvaity
            self.after(interval, self._bounce_step)
            return

        # 回归初始坐标
        self.geometry(f"+{self.winfo_x()}+{self._bounce_initial_y}")
        self.combo_window.geometry(f"+{self.combo_window.winfo_x()}+{self._bounce_initial_y}")

        if self._bounce_on_finish:
            callback = self._bounce_on_finish
            self._is_bounce = False
            self._bounce_on_finish = None
            callback()

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
        self.combo_window.geometry(f"+{x_new}+{y_new}")

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

    def _exit_app(self):
        TaPetKeyLogger.info("程序触发退出事件。")

        # 托盘菜单回调运行在 pystray 线程上，这里只做关闭与强制退出，
        # 避免跨线程操作 tkinter 抛异常导致 os._exit 执行不到。
        try:
            self.app_tray.stop()
        except Exception:
            pass
        try:
            self.keyboard_trigger.unhook_all_event()
        except Exception:
            pass

        os._exit(0)

if __name__=="__main__":

    app = TaPetKeyMain()
    app.mainloop()