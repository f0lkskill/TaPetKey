from .lib import *

class EffectWindow(tk.Toplevel):
    """_效果窗口_

    Args:
        tk (_type_): _tk_
    """
    gravity:float = 0.1

    def __init__(self, show_text: str, update_interval: float = 0.01, on_close=None, *args, **kwargs):
        """_初始化效果窗口_"""
        super().__init__(*args, **kwargs)
        # 先隐藏，避免原生 Toplevel 默认窗口一闪而过
        self.withdraw()
        self._on_close = on_close

        self.init_window_attr()
        self.init_window_widget()

        self.text_img: Image.Image = None  # type: ignore
        self.rotate_img_tk: Image.Image = None # type: ignore
        self.rotate:float = 0.0
        self.update_internal:float = update_interval
        self.position = self.winfo_x(), self.winfo_y()
        self._img_item:int = None # type: ignore
        self.rotate_tick = 3 * choice([i for i in list(range(-2, 2)) if i != 0])

        # 动画状态（单条 after 链驱动，避免每窗口三条链叠加拖垮主线程）
        self._alive:bool = True
        self._fall_v:float = 0.0
        self._fade_alpha:float = 1.0
        self._fade_v:float = 0.1
        self._start_time:float = time.time()
        self._last_time:float = self._start_time
        self._interval:int = max(1, int(self.update_internal * 1000))

        self.set_show_text(show_text)

        # 属性全部就绪后再显示，且以透明状态出现防止黑底闪一下
        self.attributes('-alpha', 0.0)
        self.update_idletasks()
        self.deiconify()
        self.attributes('-alpha', 1.0)

        self.after(self._interval, self._tick)

    def set_show_text(self, text: str):
        self.current_show_text = text
        self.text_img = self.get_text_img(self.current_show_text)

    def init_window_attr(self):
        """_初始化窗口属性_"""

        # 居中于主窗口（角色所在中心），而不是左上角对齐
        master_w = self.master.winfo_width()
        master_h = self.master.winfo_height()
        if master_w <= 1 or master_h <= 1:
            master_w, master_h = 250, 250
        x = self.master.winfo_x() + (master_w - 150) // 2
        y = self.master.winfo_y() + (master_h - 150) // 2
        final_offset_x = 70
        final_offset_y = 20
        random_offset_x, random_offset_y = (randint(-30, 30), randint(-30, 30))
        self.geometry(f"150x150+{x - final_offset_x + random_offset_x}+{y - final_offset_y + random_offset_y}")

        self.attributes("-topmost", True)
        self.config(bg="black")
        self.attributes("-transparentcolor", "black")
        self.overrideredirect(True)

    def init_window_widget(self):
        """_初始化窗口小部件_"""
        self.mainframe = tk.Canvas(self)
        self.mainframe.pack(fill=tk.BOTH, expand=True)

    def _tick(self):
        """_单帧：旋转绘制 + 下落 + 淡出（主线程 after 驱动）_"""
        if not self._alive:
            return

        # 真实时间步进补偿：帧率被拖慢时放大步进，保证动画速度恒定
        now = time.time()
        factor = min((now - self._last_time) / self.update_internal, 3.0)
        self._last_time = now

        # 旋转绘制（复用同一个 canvas item，避免每帧堆积）
        self.rotate_img_tk = ImageTk.PhotoImage(self.text_img.rotate(self.rotate, expand=True
            , resample=Image.BILINEAR)) # type: ignore
        if self._img_item is None:
            self._img_item = self.mainframe.create_image(75, 75, image=self.rotate_img_tk)
        else:
            self.mainframe.itemconfig(self._img_item, image=self.rotate_img_tk)
        self.rotate += self.rotate_tick * factor

        # 自由下落
        self.position = self.winfo_x(), self.winfo_y()
        self._fall_v += self.gravity * factor
        self.geometry(f"+{self.position[0]}+{int(self.position[1] + self._fall_v * factor)}")

        # 停留 0.5s 后淡出
        if now - self._start_time >= 0.5:
            self._fade_alpha -= self._fade_v * factor
            self._fade_v -= 0.005 * factor
            if self._fade_alpha <= 0:
                self.attributes("-alpha", 0.0)
                self._alive = False
                self.after(100, self._close)
                return
            self.attributes("-alpha", self._fade_alpha)

        self.after(self._interval, self._tick)

    def get_text_img(self, text: str) -> Image.Image:
        """_获取文本图像_"""
        img = Image.new("RGBA", (125, 125), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("arial.ttf", 23)
        # 以图像中心为锚点绘制，保证文字在窗口中居中旋转
        draw.text((62.5, 62.5), text, fill=(255, 255, 255, 255), font=font, anchor="mm")
        return img

    def _close(self):
        """_关闭窗口并通知外部移除引用_"""
        if self._on_close:
            try:
                self._on_close(self)
            except Exception:
                pass
        self.destroy()
