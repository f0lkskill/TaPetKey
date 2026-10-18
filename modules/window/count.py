from .lib import *

class CounterWindow(tk.Toplevel):
    """_combo计数器窗口_

    Args:
        tk (_type_): _tk_
    """

    def __init__(self, refresh_internal: float = 3.0, *args, **kwargs):
        """_初始化计数器窗口_"""
        super().__init__(*args, **kwargs)
        # 先隐藏，避免原生 Toplevel 默认窗口一闪而过
        self.withdraw()
        self.mainframe:tk.Canvas
        self.bubble_img_tk:ImageTk.PhotoImage
        self.text_id:int = -1
        self.current_count:int = 0
        self.current_alpha:float = 0.0
        self.last_input_time:float = 0.0
        self.refresh_internal:float = refresh_internal
        self._fade_gen:int = 0
        self.has_lost = True

        self.init_window_attr()
        self.init_window_widget()
        self.draw_image()

        # 属性就绪后再显示
        self.deiconify()

        # 主线程 after 轮询（避免子线程操作 tkinter）
        self.after(int(self.refresh_internal * 1000), self.detect_refresh)

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

        # TaPetKeyLogger.debug(f"current has lost: {self.has_lost}")

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
        """_检测刷新（主线程 after 轮询）_"""
        if not self.has_lost and time.time() - self.last_input_time >= self.refresh_internal:
            # 失去连击！
            self.call_fade(self.fade_away)
            TaPetKeyLogger.debug("失去连击，开始淡出。")

            self.master.current_charactor.miss_round() # type: ignore

            self.current_count = 0
            self.has_lost = True

        self.after(int(self.refresh_internal * 1000), self.detect_refresh)

    def call_fade(self, fade_func):
        TaPetKeyLogger.debug(f"调用渐变透明度效果: <{fade_func.__name__}>")
        # 递增代号，旧动画在下一帧会因代号不符而自动停止
        self._fade_gen += 1
        fade_func(self._fade_gen)

    def fade_away(self, gen:int):
        """_淡出窗口_"""
        self.current_alpha = 1.0
        self.attributes('-alpha', 1.0)

        v = 0.1

        def step():
            nonlocal v
            if gen != self._fade_gen:
                return
            if v <= 0:
                self.current_alpha = 0.0
                self.attributes('-alpha', 0.0)
                return
            self.current_alpha -= v
            v -= 0.005
            self.attributes('-alpha', max(0.0, self.current_alpha))
            self.after(int(self.master.update_internal * 1000), step) # type: ignore

        step()

    def fade_in(self, gen:int):
        """_淡入窗口_"""
        # 初始化重置初始状态
        self.current_alpha = 0.0
        self.attributes('-alpha', 0.0)

        v = 0.1

        def step():
            nonlocal v
            if gen != self._fade_gen:
                return
            if v <= 0:
                self.current_alpha = 1.0
                self.attributes('-alpha', 1.0)
                return
            self.current_alpha += v
            v -= 0.005
            self.attributes('-alpha', min(1.0, self.current_alpha))
            self.after(int(self.master.update_internal * 1000), step) # type: ignore

        step()
