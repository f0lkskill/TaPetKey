import tkinter as tk
from PIL import Image, ImageTk
from threading import Thread, Event
import time
from modules.log import TaPetKeyLogger

class CounterWindow(tk.Toplevel):
    """_combo计数器窗口_

    Args:
        tk (_type_): _tk_
    """

    def __init__(self, refresh_internal: float = 3.0, *args, **kwargs):
        """_初始化计数器窗口_"""
        super().__init__(*args, **kwargs)
        self.mainframe:tk.Canvas
        self.bubble_img_tk:ImageTk.PhotoImage
        self.text_id:int = -1
        self.current_count:int = 0
        self.current_alpha:float = 0.0
        self.last_input_time:float
        self.refresh_internal:float = refresh_internal
        self.fade_thread:Thread = None # type: ignore
        self.stop_event:Event = Event()
        self.has_lost = True

        self.init_window_attr()
        self.init_window_widget()
        self.draw_image()

        Thread(target=self.detect_refresh, daemon=True).start()

    def init_window_attr(self):
        """_初始化窗口属性_"""
        self.title("计数器")
        self.geometry("125x125")
        self.attributes("-topmost", True)
        self.config(bg="black")
        self.attributes("-transparentcolor", "black")
        self.overrideredirect(True)
        self.attributes('-alpha', self.current_alpha)

    def init_window_widget(self):
        """_初始化窗口小部件_"""
        self.mainframe = tk.Canvas(self)
        self.mainframe.pack(fill=tk.BOTH, expand=True)

    def add_one(self):
        """_添加一个计数_"""
        # 置底
        self.lower(self.master)

        # 每次都要进行的事件更新
        self.current_count += 1
        self.last_input_time = time.time()
        self.draw_image()

        TaPetKeyLogger.debug(f"current has lost: {self.has_lost}")

        if self.has_lost:
            # 初始进行动效已经记录状态
            self.has_lost = False
            self.call_fade(self.fade_in)

    def draw_image(self):
        """_初始化图像_"""
        self.mainframe.delete(self.text_id)

        img = Image.open("assets/ui/bubble.png")
        img = img.resize((125, 125))
        self.bubble_img_tk = ImageTk.PhotoImage(img)
        self.mainframe.create_image(62.5, 62.5, image=self.bubble_img_tk)

        self.text_id = self.mainframe.create_text(62.5, 62.5,
             text=str(self.current_count), fill="#151515",
               font=("Consolas", 30, 'bold'))

    def detect_refresh(self):
        """_检测刷新_"""
        while 1:
            time.sleep(self.refresh_internal)
            if self.has_lost:
                continue
            if time.time() - self.last_input_time >= self.refresh_internal:
                # 失去连击！
                self.call_fade(self.fade_away)
                TaPetKeyLogger.debug("失去连击，开始淡出。")

                self.master.current_charactor.miss_round() # type: ignore

                self.current_count = 0
                self.has_lost = True

    def call_fade(self, fade_func):
        TaPetKeyLogger.debug(f"调用渐变透明度效果: <{fade_func.__name__}>")
        if self.fade_thread is None or not self.fade_thread.is_alive():
            self.fade_thread = Thread(target=fade_func, args=(self.stop_event,), daemon=True)
            self.fade_thread.start()
        else:self.stop_event.set()

    def fade_away(self, stop_event:Event):
        """_淡出窗口_"""
        self.current_alpha = 1.0
        self.attributes('-alpha', 1.0)

        a = 0.005
        v = 0.1
        while(v > 0 and not stop_event.is_set()):
            self.current_alpha -= v
            v -= a
            self.attributes('-alpha', self.current_alpha)
            time.sleep(self.master.update_internal) # type: ignore

    def fade_in(self, stop_event:Event):
        """_淡入窗口_"""
        # 初始化重置初始状态
        self.current_alpha = 0
        self.attributes('-alpha', 0)

        a = 0.005
        v = 0.1
        while(v > 0 and not stop_event.is_set()):
            TaPetKeyLogger.debug(f"淡入窗口，透明度: {v}")
            self.current_alpha += v
            v -= a
            self.attributes('-alpha', self.current_alpha)
            time.sleep(self.master.update_internal) # type: ignore

        # 结束状态
        self.current_alpha = 1.0
        self.attributes('-alpha', self.current_alpha)