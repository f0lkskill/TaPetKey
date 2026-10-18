from .lib import *
import win32con
import win32gui

class EffectWindow(tk.Toplevel):
    """_特效文本窗口（单窗口 + Canvas 多粒子）_

    只维护一个透明窗口，所有旋转坠落的文字以 Canvas item 的形式
    在其中渲染。相比每次按键都新建一个 Toplevel，长按连发时不会
    反复创建/销毁窗口，显著降低卡顿。
    """

    gravity:float = 0.1
    max_particles:int = 16

    def __init__(self, update_interval: float = 0.01, master=None, **kwargs):
        """_初始化特效窗口_"""
        super().__init__(master, **kwargs)
        # 先隐藏，避免原生 Toplevel 默认窗口一闪而过
        self.withdraw()
        self.master_app = master
        self.update_internal:float = update_interval
        self._interval:int = max(1, int(update_interval * 1000))
        self._alive:bool = False
        self._last_time:float = time.time()
        self._text_cache:dict = {}      # 文本 -> 基础白色 RGBA 图
        self.particles:list = []        # 活动粒子列表

        self.init_window_attr()
        self.init_window_widget()
        self._make_click_through()

    def _master_scale(self) -> float:
        """_主窗口当前整体缩放比例_"""
        return float(getattr(self.master_app, "user_scale", 1.0))

    def _master_effect_offset(self) -> tuple:
        """_主窗口皮肤配置的特效窗口像素偏移_"""
        offset = getattr(self.master_app, "effect_offset", (70, 20))
        return int(offset[0]), int(offset[1])

    def _master_size(self) -> int:
        """_主窗口当前边长_"""
        if hasattr(self.master_app, "main_size"):
            return self.master_app.main_size()
        return 250

    def init_window_attr(self):
        """_初始化窗口属性_"""
        side = max(1, int(self._master_size() * 2))
        self._side = side
        self.geometry(f"{side}x{side}")
        self.attributes("-topmost", True)
        self.config(bg="black")
        self.attributes("-transparentcolor", "black")
        self.overrideredirect(True)

    def init_window_widget(self):
        """_初始化窗口小部件_"""
        self.mainframe = tk.Canvas(self, bg="black", highlightthickness=0)
        self.mainframe.pack(fill=tk.BOTH, expand=True)

    def _make_click_through(self):
        """_让窗口鼠标穿透，避免遮挡主窗口的拖动/点击_"""
        try:
            hwnd = win32gui.GetAncestor(self.winfo_id(), win32con.GA_ROOT)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                hwnd, win32con.GWL_EXSTYLE,
                ex_style | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED)
        except Exception as e:
            TaPetKeyLogger.warning(f"设置特效窗口鼠标穿透失败: {e}")

    def _sync_geometry(self):
        """_跟随主窗口：尺寸随缩放、中心对齐并叠加皮肤偏移_"""
        side = max(1, int(self._master_size() * 2))
        self._side = side

        mx = self.master_app.winfo_x()
        my = self.master_app.winfo_y()
        mw = self.master_app.winfo_width()
        mh = self.master_app.winfo_height()
        if mw <= 1 or mh <= 1:
            mw = mh = self._master_size()

        # 窗口中心对齐主窗口中心，再减去皮肤配置的偏移（像素）
        offset_x, offset_y = self._master_effect_offset()
        x = mx + mw // 2 - side // 2 - offset_x
        y = my + mh // 2 - side // 2 - offset_y
        self.geometry(f"{side}x{side}+{x}+{y}")

    def add(self, show_text: str):
        """_新增一个文字粒子_

        Args:
            show_text (str): _要显示的文本_
        """
        self._sync_geometry()
        if len(self.particles) >= self.max_particles:
            self._remove_particle(self.particles[0])

        half = self._side / 2
        particle = {
            "x": half + randint(-30, 30),
            "y": half + randint(-30, 30),
            "vy": 0.0,
            "rotate": 0.0,
            "rotate_tick": 3 * choice([i for i in list(range(-2, 2)) if i != 0]),
            "life": 0.0,
            "fade": 1.0,
            "fade_v": 0.1,
            "base": self._get_base_img(show_text),
            "photo": None,
            "item": None,
        }
        self.particles.append(particle)

        if not self._alive:
            self._alive = True
            self._last_time = time.time()
            self.deiconify()
            self._tick()

    def _get_base_img(self, text: str) -> Image.Image:
        """_获取（带缓存的）基础文本图像_"""
        if text not in self._text_cache:
            self._text_cache[text] = self._render_text(text)
        return self._text_cache[text]

    def _render_text(self, text: str) -> Image.Image:
        """_把文本渲染成白色 RGBA 图（字号随整体缩放）_"""
        scale = self._master_scale()
        size = max(1, int(125 * scale))
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("arial.ttf", max(1, int(23 * scale)))
        # 以图像中心为锚点绘制，保证文字在窗口中居中旋转
        draw.text((size / 2, size / 2), text, fill=(255, 255, 255, 255),
                  font=font, anchor="mm")
        return img

    def _apply_brightness(self, img: Image.Image, factor: float) -> Image.Image:
        """_用亮度衰减模拟淡出（Canvas 无法单独设置 item 透明度）_"""
        r, g, b, a = img.split()
        r = r.point(lambda v: int(v * factor))
        g = g.point(lambda v: int(v * factor))
        b = b.point(lambda v: int(v * factor))
        return Image.merge("RGBA", (r, g, b, a))

    def _remove_particle(self, particle: dict):
        """_移除粒子及其实体化 item_"""
        if particle["item"] is not None:
            self.mainframe.delete(particle["item"])
            particle["item"] = None
        if particle in self.particles:
            self.particles.remove(particle)

    def _tick(self):
        """_单帧：旋转绘制 + 下落 + 淡出（单条 after 链驱动全部粒子）_"""
        if not self._alive:
            return

        # 真实时间步进补偿：帧率被拖慢时放大步进，保证动画速度恒定
        now = time.time()
        factor = min((now - self._last_time) / self.update_internal, 3.0)
        self._last_time = now

        self._sync_geometry()

        for particle in list(self.particles):
            particle["rotate"] += particle["rotate_tick"] * factor
            particle["vy"] += self.gravity * factor
            particle["y"] += particle["vy"] * factor
            particle["life"] += self.update_internal * factor

            # 停留 0.5s 后淡出
            if particle["life"] >= 0.5:
                particle["fade"] -= particle["fade_v"] * factor
                particle["fade_v"] += 0.005 * factor
                if particle["fade"] <= 0:
                    self._remove_particle(particle)
                    continue

            # 旋转绘制并复用同一个 canvas item，避免每帧堆积
            img = particle["base"].rotate(
                particle["rotate"], expand=True, resample=Image.BILINEAR)
            if particle["fade"] < 1.0:
                img = self._apply_brightness(img, particle["fade"])
            particle["photo"] = ImageTk.PhotoImage(img)
            if particle["item"] is None:
                particle["item"] = self.mainframe.create_image(
                    particle["x"], particle["y"], image=particle["photo"])
            else:
                self.mainframe.itemconfig(particle["item"], image=particle["photo"])
                self.mainframe.coords(particle["item"],
                                      particle["x"], particle["y"])

            # 坠落出窗口底部则回收
            if particle["y"] > self._side:
                self._remove_particle(particle)

        if not self.particles:
            self._alive = False
            self.withdraw()
            return

        self.after(self._interval, self._tick)

    def clear(self):
        """_清空全部粒子_"""
        for particle in list(self.particles):
            self._remove_particle(particle)
        self._alive = False
        self.withdraw()
