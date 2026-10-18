from .lib import *
from PIL import ImageChops

class EffectWindow(tk.Toplevel):
    """_特效文本窗口（单窗口 + Canvas 多粒子）_

    只维护一个透明窗口，所有旋转坠落的文字以 Canvas item 的形式
    在其中渲染。相比每次按键都新建一个 Toplevel，长按连发时不会
    反复创建/销毁窗口，显著降低卡顿。

    注意：窗口位置只在粒子生成（add）和拖拽同步（sync_position）时
    更新，不会每帧跟随主窗口，因此主窗口弹跳时特效不会跟着一起跳。
    """

    gravity:float = 0.2
    max_particles:int = 3
    # 初始锚点相对窗口中心的整体下移量（基准像素，随整体缩放）
    start_offset_y:int = 60
    # 重绘（旋转）间隔帧数：中间帧只更新坐标，显著降低 CPU 占用
    redraw_every:int = 2
    # 生命周期（秒）：渐入 -> 保持 -> 渐出
    fade_in:float = 0.10
    hold:float = 0.05
    fade_out:float = 0.22

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
            assert self.master_app is not None
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

    def sync_position(self):
        """_按主窗口当前位置重新对齐（仅在拖拽等时机调用）_"""
        side = max(1, int(self._master_size() * 2))
        self._side = side

        assert self.master_app is not None
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
        self.sync_position()
        # 达到上限时静默忽略，不再顶掉旧粒子
        if len(self.particles) >= self.max_particles:
            return

        half = self._side / 2
        # 初始锚点整体下移（随整体缩放），让文字从角色偏下位置生成
        anchor_y = half + self.start_offset_y * self._master_scale()
        particle = {
            "x": half + randint(-30, 30),
            "y": anchor_y + randint(-30, 30),
            "vy": 0.0,
            "rotate": 0.0,
            "rotate_tick": 3 * choice([i for i in list(range(-2, 2)) if i != 0]),
            "life": 0.0,
            "base": self._get_base_img(show_text),
            "photo": None,
            "item": None,
            "frame": 0,
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

    def _fade_at(self, life: float) -> float:
        """_按已存活时间计算透明度（先渐入，保持，再渐出）_"""
        if life < self.fade_in:
            return life / self.fade_in
        if life < self.fade_in + self.hold:
            return 1.0
        t = (life - self.fade_in - self.hold) / self.fade_out
        return max(0.0, 1.0 - t)

    def _apply_brightness(self, img: Image.Image, factor: float) -> Image.Image:
        """_用亮度衰减模拟淡入/淡出（Canvas 无法单独设置 item 透明度）_

        使用 C 实现的 ImageChops.multiply，避免逐像素 Python 回调造成的卡顿。
        """
        v = max(0, min(255, int(255 * factor)))
        mask = Image.new("RGBA", img.size, (v, v, v, 255))
        return ImageChops.multiply(img, mask)

    def _remove_particle(self, particle: dict):
        """_移除粒子及其实体化 item_"""
        if particle["item"] is not None:
            self.mainframe.delete(particle["item"])
            particle["item"] = None
        if particle in self.particles:
            self.particles.remove(particle)

    def _tick(self):
        """_单帧：旋转绘制 + 下落 + 渐入/渐出（单条 after 链驱动全部粒子）_"""
        if not self._alive:
            return

        # 真实时间步进补偿：帧率被拖慢时放大步进，保证动画速度恒定
        now = time.time()
        factor = min((now - self._last_time) / self.update_internal, 3.0)
        self._last_time = now

        for particle in list(self.particles):
            particle["rotate"] += particle["rotate_tick"] * factor
            particle["vy"] += self.gravity * factor
            particle["y"] += particle["vy"] * factor
            particle["life"] += self.update_internal * factor
            particle["frame"] += 1

            # 渐入 -> 保持 -> 渐出
            fade = self._fade_at(particle["life"])
            if fade <= 0:
                self._remove_particle(particle)
                continue
            particle["fade"] = fade

            # 渐变期间每帧重绘以保证平滑，稳定后按间隔重绘
            need_redraw = (particle["item"] is None
                           or fade != 1.0
                           or particle["frame"] % self.redraw_every == 0)
            if need_redraw:
                img = particle["base"].rotate(
                    particle["rotate"], expand=True, resample=Image.BILINEAR) # type: ignore
                if fade < 1.0:
                    img = self._apply_brightness(img, fade)
                particle["photo"] = ImageTk.PhotoImage(img)
                if particle["item"] is None:
                    particle["item"] = self.mainframe.create_image(
                        particle["x"], particle["y"], image=particle["photo"])
                else:
                    self.mainframe.itemconfig(particle["item"],
                                              image=particle["photo"])
            if particle["item"] is not None:
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
