from .lib import *
from .layered import LayeredWindow

class CounterWindow(tk.Toplevel):
    """_combo计数器窗口（分层窗口 + PIL 渲染，支持每像素 alpha）_

    Args:
        tk (_type_): _tk_
    """

    def __init__(self, refresh_internal: float = 3.0, scale: float = 1.0, *args, **kwargs):
        """_初始化计数器窗口_"""
        super().__init__(*args, **kwargs)
        # 先隐藏，避免原生 Toplevel 默认窗口一闪而过
        self.withdraw()
        self.current_count:int = 0
        self.current_alpha:float = 0.0
        self.last_input_time:float = 0.0
        self.refresh_internal:float = refresh_internal
        self.scale:float = scale
        self._fade_gen:int = 0
        self.has_lost = True

        # 分层窗口状态
        self._pos:tuple = (0, 0)
        self._frame:Image.Image = None # type: ignore
        self._bubble_cache:Image.Image = None # type: ignore
        self._bubble_cache_size:int = 0
        self._font_cache:dict = {}
        self.surface = LayeredWindow(self)

        self.init_window_attr()
        self.draw_image()
        # 首帧已推送（alpha=0 不可见），此时显示不会闪黑
        self.deiconify()

        # 主线程 after 轮询（避免子线程操作 tkinter）
        self.after(int(self.refresh_internal * 1000), self.detect_refresh)

    def _size(self) -> int:
        """_按缩放比例计算气泡边长_"""
        return max(1, int(125 * self.scale))

    def apply_scale(self, scale: float):
        """_应用新的缩放比例（窗口尺寸、气泡图与字号同步缩放）_

        Args:
            scale (float): _缩放比例_
        """
        self.scale = scale
        self.draw_image()

    def init_window_attr(self):
        """_初始化窗口属性_"""
        self.title("计数器")
        self.attributes("-topmost", True)
        self.overrideredirect(True)
        # 改造成每像素 alpha 的分层窗口
        self.surface.bind()

    def set_position(self, x: int, y: int):
        """_移动窗口（分层窗口需重新推送帧）_"""
        self._pos = (int(x), int(y))
        self._push()

    def _get_bubble(self, size: int) -> Image.Image:
        """_获取（按尺寸缓存的）气泡底图_"""
        if self._bubble_cache is None or self._bubble_cache_size != size:
            img = Image.open("assets/ui/bubble.png").convert("RGBA")
            self._bubble_cache = img.resize((size, size))
            self._bubble_cache_size = size
        return self._bubble_cache

    def _get_font(self, size: int):
        """_获取（缓存的）粗体等宽字体_"""
        if size not in self._font_cache:
            font = None
            for name in ("consolab.ttf", "consola.ttf"):
                try:
                    font = ImageFont.truetype(name, size)
                    break
                except OSError:
                    continue
            if font is None:
                font = ImageFont.load_default()
            self._font_cache[size] = font
        return self._font_cache[size]

    def draw_image(self):
        """_渲染气泡底图 + 计数字到分层窗口_"""
        size = self._size()
        frame = self._get_bubble(size).copy()
        draw = ImageDraw.Draw(frame)
        font = self._get_font(max(1, int(40 * self.scale)))
        draw.text((size / 2, size / 2), str(self.current_count),
                  fill="#151515", font=font, anchor="mm")
        self._frame = frame
        self._push()

    def _push(self):
        """_把当前帧（含整体透明度）推送到分层窗口_"""
        if self._frame is not None:
            self.surface.set_frame(self._frame, self._pos[0], self._pos[1],
                                   alpha=self.current_alpha)

    def add_one(self):
        """_添加一个计数_"""
        # 置底
        self.lower(self.master)

        # 每次都要进行的事件更新
        self.current_count += 1
        self.last_input_time = time.time()
        self.draw_image()

        if self.has_lost:
            # 初始进行动效已经记录状态
            self.has_lost = False
            self.call_fade(self.fade_in)

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
        self._push()

        v = 0.1

        def step():
            nonlocal v
            if gen != self._fade_gen:
                return
            if v <= 0:
                self.current_alpha = 0.0
                self._push()
                return
            self.current_alpha = max(0.0, self.current_alpha - v)
            v -= 0.005
            self._push()
            self.after(int(self.master.update_internal * 1000), step) # type: ignore

        step()

    def fade_in(self, gen:int):
        """_淡入窗口_"""
        # 初始化重置初始状态
        self.current_alpha = 0.0
        self._push()

        v = 0.1

        def step():
            nonlocal v
            if gen != self._fade_gen:
                return
            if v <= 0:
                self.current_alpha = 1.0
                self._push()
                return
            self.current_alpha = min(1.0, self.current_alpha + v)
            v -= 0.005
            self._push()
            self.after(int(self.master.update_internal * 1000), step) # type: ignore

        step()
