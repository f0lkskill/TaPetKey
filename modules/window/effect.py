from .lib import *
from PIL import ImageChops
from .layered import LayeredWindow

class EffectWindow(tk.Toplevel):
    """_特效文本窗口（分层窗口 + 每帧 PIL 合成）_

    只维护一个透明窗口，所有旋转坠落的文字每帧用 PIL 合成一张 RGBA 图后
    通过 UpdateLayeredWindow 推送给系统，边缘为真正的每像素 alpha，
    不再有颜色键的误扣 / 扣不干净问题。

    注意：窗口位置只在粒子生成（add）和拖拽同步（sync_position）时
    更新，不会每帧跟随主窗口，因此主窗口弹跳时特效不会跟着一起跳。
    """

    gravity:float = 0.2
    max_particles:int = 3
    # 初始锚点相对窗口中心的整体下移量（基准像素，随整体缩放）
    start_offset_y:int = 60
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
        self._pos:tuple = (0, 0)
        self._last_frame:Image.Image = None # type: ignore

        self.init_window_attr()
        self.surface = LayeredWindow(self)
        self.surface.bind()

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
        self.overrideredirect(True)

    def sync_position(self):
        """_按主窗口当前位置重新对齐（仅在拖拽等时机调用）_"""
        side = max(1, int(self._master_size() * 2))
        self._side = side

        assert self.master_app is not None
        if hasattr(self.master_app, "current_window_geometry"):
            # 使用主窗口逻辑几何，避免 winfo 滞后导致对齐错位
            mx, my, mw, mh = self.master_app.current_window_geometry()
        else:
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
        self._pos = (int(x), int(y))
        if self._alive and self._last_frame is not None:
            self.surface.set_frame(self._last_frame, self._pos[0], self._pos[1])

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
            "fade": 1.0,
            "base": self._get_base_img(show_text),
            "frame": 0,
        }
        self.particles.append(particle)

        if not self._alive:
            self._alive = True
            self._last_time = time.time()
            self._tick()          # 立即合成并推送首帧
            self.deiconify()

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
        """_用亮度衰减模拟淡入/淡出_

        使用 C 实现的 ImageChops.multiply，避免逐像素 Python 回调造成的卡顿。
        """
        v = max(0, min(255, int(255 * factor)))
        mask = Image.new("RGBA", img.size, (v, v, v, 255))
        return ImageChops.multiply(img, mask)

    def _render_frame(self) -> Image.Image:
        """_把所有粒子合成为一张 RGBA 图_"""
        side = self._side
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        for particle in self.particles:
            img = particle["base"].rotate(
                particle["rotate"], expand=True, resample=Image.BILINEAR) # type: ignore
            fade = particle.get("fade", 1.0)
            if fade < 1.0:
                img = self._apply_brightness(img, fade)
            px = int(particle["x"] - img.width / 2)
            py = int(particle["y"] - img.height / 2)
            canvas.alpha_composite(img, (px, py))
        return canvas

    def _tick(self):
        """_单帧：物理更新 + 合成 + 推送（单条 after 链驱动全部粒子）_"""
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
                self.particles.remove(particle)
                continue
            particle["fade"] = fade

            # 坠落出窗口底部则回收
            if particle["y"] > self._side:
                self.particles.remove(particle)

        if not self.particles:
            self._alive = False
            self.withdraw()
            return

        frame = self._render_frame()
        self._last_frame = frame
        self.surface.set_frame(frame, self._pos[0], self._pos[1])

        self.after(self._interval, self._tick)

    def clear(self):
        """_清空全部粒子_"""
        self.particles.clear()
        self._alive = False
        self.withdraw()
