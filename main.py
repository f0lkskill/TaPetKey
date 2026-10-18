import time, os, queue, sys
import tkinter as tk
from modules.log import *
from modules.skin_loader import *
from modules.widgets import *
from modules.keyborad import *
from modules.window import *
from modules.config import (
    get_config, set_config,
    SKIN_VALUE, SCALE_VALUE, POS_X_VALUE, POS_Y_VALUE,
)
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
        # 托盘线程与主线程之间的换肤 / 缩放请求队列
        self._skin_queue:queue.Queue = queue.Queue()
        self._scale_queue:queue.Queue = queue.Queue()
        self.app_tray:AppTray = AppTray(self._exit_app, self._request_switch_skin,
                                        self._request_zoom)
        self._drag_start_x = 0
        self._drag_start_y = 0
        self.grvaity:float = 3
        self.update_internal:float = 0.01

        # 整体缩放与皮肤布局配置（偏移来自皮肤 info.json）
        self.user_scale:float = self._load_user_scale()
        self._initial_skin:str = self._load_last_skin()
        self._last_pos:tuple = self._load_last_pos() or (0, 0)
        # 逻辑静止坐标：窗口"应处"的位置（弹跳/拖拽的基准，避免 winfo 时序滞后）
        self._rest_x:int = int(self._last_pos[0])
        self._rest_y:int = int(self._last_pos[1])
        self._skin_scale:float = 0.5
        self._combo_offset_base:tuple = (0, 0)
        self._effect_offset_base:tuple = (70, 20)
        self.combo_offset:tuple = (0, 0)
        self.effect_offset:tuple = (70, 20)
        self._load_skin_layout(self._initial_skin)

        self.combo_window = CounterWindow(master = self, scale = self.user_scale)
        self.effect_window:EffectWindow = None # type: ignore
        self.last_press_time:float = time.time()
        self.restore_time:float = 1.0
        self.last_event_name:str = ''

        # 弹跳动画状态（基于逻辑静止坐标，不依赖 winfo 的时序滞后）
        self._is_bounce:bool = False
        self._bounce_offset:float = 0.0
        self._bounce_v:float = 0.0
        self._bounce_on_finish = None

        # 分层窗口当前帧缓存（角色 RGBA 图）
        self._current_frame = None

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

        # 添加注册热键
        self.keyboard_trigger.apply_hot_keys(self.current_charactor.combine_keys)

    def process_hot_key(self):
        """_处理热键事件_"""
        # 是否有热键事件
        key_str = self.keyboard_trigger.queue_hot_keys.pop(0)
        if key_str in self.current_charactor.combine_keys:
            # 存在这个对应的热键，进行切换图像
            self.current_charactor.base_switch(self.current_charactor.combine_keys[key_str].base_name)

    def process_press_event(self) -> None:
        """_处理按下事件_"""

        event = self.keyboard_trigger.queue_press_events[0]

        try:
            # 新增一个文字粒子（单个透明窗口 + PIL 合成渲染，
            # 避免长按连发时反复创建/销毁 Toplevel 造成卡顿）
            self.effect_window.add(
                event.name if event.name != 'backspace' else 'delete')

            if self.current_charactor.exists_id(f"key_{event.name}"):
                # 存在合法id，特殊事件解析成功
                self.current_charactor.base_switch(f"key_{event.name}")
            else:
                # 正常动画处理
                if self.last_event_name != event.name:
                    self.current_charactor.normal_round()
                else:self.random_bounce_event()
                self.last_event_name = event.name
        finally:
            # 必须无条件出队：否则一旦上面抛异常，同一事件会被反复处理
            # （毒丸卡死），导致之后只切贴图、不再弹跳。
            if self.keyboard_trigger.queue_press_events:
                self.keyboard_trigger.queue_press_events.pop(0)
            # 防止idle自恢复的打断。
            self.last_press_time = time.time()

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
        try:
            self.combo_window.add_one()
        finally:
            # 同样无条件出队，避免毒丸卡死
            self.keyboard_trigger.queue_release_events.pop(0)

    def main_process(self) -> None:
        # 处理托盘线程发来的换肤请求（跨线程仅通过队列传递，主线程应用）
        while not self._skin_queue.empty():
            try:
                self._apply_skin(self._skin_queue.get_nowait())
            except Exception as e:
                TaPetKeyLogger.error(f"切换皮肤失败：{e}")

        # 处理托盘线程发来的缩放请求
        while not self._scale_queue.empty():
            try:
                self._apply_zoom(self._scale_queue.get_nowait())
            except Exception as e:
                TaPetKeyLogger.error(f"调整缩放失败：{e}")

        # 每帧限量处理，长按连发时也要让主线程及时返回事件循环，避免卡死
        max_per_tick = 2
        processed = 0
        while processed < max_per_tick and \
              len(self.keyboard_trigger.queue_press_events) + \
              len(self.keyboard_trigger.queue_release_events) + \
              len(self.keyboard_trigger.queue_hot_keys) > 0:
            try:
                if len(self.keyboard_trigger.queue_press_events) > 0:
                    # 开始处理事件
                    self.process_press_event()
                elif len(self.keyboard_trigger.queue_release_events) > 0:
                    # 开始处理释放事件
                    self.process_release_event()
                elif len(self.keyboard_trigger.queue_hot_keys) > 0:
                    # 开始处理热键事件
                    self.process_hot_key()

            except Exception as e:
                TaPetKeyLogger.error(f"处理键盘事件时发生错误：{e}")
            processed += 1

        # 记录窗口静止坐标（退出时持久化；用逻辑坐标避免弹跳中途记录到中间值）
        self._last_pos = (self._rest_x, self._rest_y)

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
            # 已有弹跳进行中：忽略本次请求（如有回调则立即回收，避免调用方等待）
            if on_finish:
                on_finish()
            return

        self._is_bounce = True
        # 速度积分：向上为负偏移，重力（grvaity）逐渐把速度拉回向下
        # 全程只基于逻辑静止坐标运算，不读取 winfo_y()，避免时序滞后造成漂移
        self._bounce_offset = 0.0
        self._bounce_v = -float(strength)
        self._bounce_on_finish = on_finish
        self._bounce_step()

    def _push_frame(self) -> None:
        """_把当前角色帧推送到分层窗口（含弹跳偏移），并同步气泡窗_"""
        if self._current_frame is None:
            return
        y = self._rest_y
        if self._is_bounce:
            y = int(round(self._rest_y + self._bounce_offset))
        self.surface.set_frame(self._current_frame, self._rest_x, y)
        self._place_combo_window()

    def _render_character(self) -> None:
        """_角色图像变化时回调：缓存帧并重绘分层窗口_"""
        char = getattr(self, "current_charactor", None)
        rgba = getattr(char, "current_rgba", None)
        if rgba is None:
            return
        self._current_frame = rgba
        self._push_frame()

    def _apply_bounce_frame(self):
        """_把当前弹跳偏移应用到窗口（位置＝静止坐标＋偏移）_"""
        self._push_frame()

    def _bounce_step(self):
        """_弹跳动画单帧（主线程 after 驱动）_"""
        # 拖拽等操作会通过置 False 打断弹跳
        if not self._is_bounce:
            return
        interval = max(1, int(self.update_internal * 1000))

        try:
            # 速度积分：位置 += 速度；速度 += 重力（向下为正）
            self._bounce_offset += self._bounce_v
            self._bounce_v += self.grvaity

            # 回到静止位置（或已越过向下）时结束，并精确归位
            if self._bounce_offset >= 0:
                self._bounce_offset = 0.0
                self._apply_bounce_frame()
                # 无条件复位，避免 on_finish 为空时卡住状态
                self._is_bounce = False
                callback = self._bounce_on_finish
                self._bounce_on_finish = None
                if callback:
                    callback()
                return

            self._apply_bounce_frame()
        except Exception as e:
            # 渲染等中途异常时兜底复位，避免 after 链断裂、状态永久卡死
            TaPetKeyLogger.error(f"弹跳动画异常，已复位：{e}")
            self._is_bounce = False
            callback = self._bounce_on_finish
            self._bounce_on_finish = None
            if callback:
                callback()
            return

        self.after(interval, self._bounce_step)

    def start_move(self, event) -> None:
        """_开始拖拽：打断进行中的弹跳，避免位置冲突_

        Args:
            event (_type_): _TK标准事件_
        """
        # 打断弹跳，避免弹跳动画在拖拽时把窗口拽回原位；
        # 把弹跳的当前偏移并入静止基准（分层窗口下 winfo 不可靠，不用它）
        if self._is_bounce:
            self._is_bounce = False
            self._rest_y = int(round(self._rest_y + self._bounce_offset))
            self._bounce_offset = 0.0
            self._bounce_v = 0.0
            # 若本次弹跳带回调，务必触发，避免调用方一直等待
            callback = self._bounce_on_finish
            self._bounce_on_finish = None
            if callback:
                callback()

        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def update_move(self, event) -> None:
        """_更新窗口位置（基于逻辑静止坐标累加，避免 winfo 滞后漂移）_

        Args:
            event (_type_): _TK标准事件_
        """
        self._rest_x += event.x_root - self._drag_start_x
        self._rest_y += event.y_root - self._drag_start_y
        self._push_frame()
        if self.effect_window:
            self.effect_window.sync_position()

        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def _on_drag_end(self, event=None) -> None:
        """_拖拽结束：更新缓存坐标并立即持久化（强杀进程也能记住位置）_"""
        self._last_pos = (self._rest_x, self._rest_y)
        self._save_window_pos()

    def _save_window_pos(self) -> None:
        """_把主窗口静止坐标写入配置_"""
        try:
            set_config(POS_X_VALUE, int(self._rest_x))
            set_config(POS_Y_VALUE, int(self._rest_y))
        except Exception as e:
            TaPetKeyLogger.error(f"保存窗口位置失败：{e}")

    def bind_window_event(self):
        """_绑定窗口事件_"""
        self.bind("<Button-1>", self.start_move)
        self.bind("<B1-Motion>", self.update_move)
        # 拖拽结束立即持久化位置
        self.bind("<ButtonRelease-1>", self._on_drag_end)

    def init_window_attr(self):
        self.title("TaPetKey")
        size = self.main_size()
        self._rest_x, self._rest_y = int(self._last_pos[0]), int(self._last_pos[1])
        self.geometry(f"{size}x{size}+{self._rest_x}+{self._rest_y}")
        self.attributes("-topmost", True)
        self.config(bg=self.transparentcolor)
        self.overrideredirect(True)

        # 改造成每像素 alpha 的分层窗口（彻底替代 -transparentcolor 色键）
        self.surface = LayeredWindow(self)
        self.surface.bind()

        self.bind_window_event()

    def init_app_widgets(self):
        """_初始化应用程序部件_"""
        size = self.main_size()
        self.current_charactor = \
        Charactor(
            asset_id=self._initial_skin, bg = self.transparentcolor,
            master=self, image_scale=self._skin_scale * self.user_scale,
            switch_func=self.random_bounce_event,
            on_render=self._render_character,
            width=size, height=size
        )
        # 角色逻辑在此创建（构造期间 current_charactor 尚未赋值，回调会跳过），
        # 这里显式渲染首帧
        self._render_character()

        # 单个特效文本窗口（复用于所有按键粒子）
        self.effect_window = EffectWindow(master=self)

        # 窗口映射后再按皮肤偏移对齐气泡窗口
        self.after(1, self._place_combo_window)

    def _request_switch_skin(self, asset_id: str) -> None:
        """_托盘线程请求换肤（仅入队，由主线程应用）_

        Args:
            asset_id (str): _皮肤ID（皮肤目录名）_
        """
        self._skin_queue.put(asset_id)

    def _apply_skin(self, asset_id: str) -> None:
        """_主线程应用新皮肤（同时套用该皮肤的缩放与偏移）_

        Args:
            asset_id (str): _皮肤ID（皮肤目录名）_
        """
        self.current_charactor.set_skin(asset_id)
        self._load_skin_layout(asset_id)
        self._apply_scale()
        # 换肤即持久化（即使进程被强杀也能记住选择）
        try:
            set_config(SKIN_VALUE, asset_id)
        except Exception as e:
            TaPetKeyLogger.error(f"保存皮肤配置失败：{e}")

    def _load_user_scale(self) -> float:
        """_从配置读取用户缩放比例（限定 50%~200%）_"""
        try:
            value = float(get_config(SCALE_VALUE, 1.0)) # type: ignore
        except (TypeError, ValueError):
            value = 1.0
        return min(2.0, max(0.5, value))

    def _load_last_skin(self) -> str:
        """_读取上次使用的皮肤（无效时回退 base）_"""
        skin = get_config(SKIN_VALUE, "base")
        if isinstance(skin, str) and \
                os.path.isdir(os.path.join("assets", "skins", skin)):
            return skin
        return "base"

    def _load_last_pos(self):
        """_读取上次窗口位置，返回 (x, y) 或 None_"""
        try:
            return int(get_config(POS_X_VALUE)), int(get_config(POS_Y_VALUE)) # type: ignore
        except (TypeError, ValueError):
            return None

    def _save_state(self) -> None:
        """_退出时持久化当前皮肤与窗口位置_"""
        try:
            set_config(SKIN_VALUE, self.current_charactor.id_name)
        except Exception as e:
            TaPetKeyLogger.error(f"保存皮肤配置失败：{e}")
        try:
            pos_x, pos_y = self._last_pos
            set_config(POS_X_VALUE, int(pos_x))
            set_config(POS_Y_VALUE, int(pos_y))
        except Exception as e:
            TaPetKeyLogger.error(f"保存窗口位置失败：{e}")

    def _load_skin_layout(self, asset_id: str) -> None:
        """_载入皮肤布局配置（基准缩放与窗口偏移）_"""
        info = get_skin_info(asset_id)
        self._skin_scale = float(info.get("scale", 0.5))
        self._combo_offset_base = tuple(info.get("combo_offset", (0, 0)))
        self._effect_offset_base = tuple(info.get("effect_offset", (70, 20)))
        self._refresh_scaled_offsets()

    def _refresh_scaled_offsets(self) -> None:
        """_按当前缩放把皮肤偏移换算成像素_"""
        cx, cy = self._combo_offset_base
        ex, ey = self._effect_offset_base
        self.combo_offset = (int(cx * self.user_scale), int(cy * self.user_scale))
        self.effect_offset = (int(ex * self.user_scale), int(ey * self.user_scale))

    def main_size(self) -> int:
        """_主窗口当前边长（按缩放）_"""
        return max(1, int(250 * self.user_scale))

    def current_window_geometry(self) -> tuple:
        """_主窗口当前逻辑几何 (x, y, w, h)_
        
        基于静止坐标 + 弹跳偏移计算，不依赖 winfo 的时序（避免滞后导致子窗口错位）。
        """
        x, y = self._rest_x, self._rest_y
        if self._is_bounce:
            y = int(round(self._rest_y + self._bounce_offset))
        size = self.main_size()
        return x, y, size, size

    def _place_combo_window(self) -> None:
        """_按皮肤偏移把气泡窗口对齐到主窗口_"""
        ox, oy = self.combo_offset
        x, y, _, _ = self.current_window_geometry()
        self.combo_window.set_position(x + ox, y + oy)

    def _request_zoom(self, delta: float) -> None:
        """_托盘线程请求缩放（仅入队，由主线程应用）_

        Args:
            delta (float): _缩放步进，正数为放大_
        """
        self._scale_queue.put(delta)

    def _apply_zoom(self, delta: float) -> None:
        """_按步进调整整体缩放并持久化到配置_"""
        new_scale = round(min(2.0, max(0.5, self.user_scale + delta)), 2)
        if new_scale == self.user_scale:
            return
        self.user_scale = new_scale
        set_config("scale", new_scale)
        self._refresh_scaled_offsets()
        self._apply_scale()
        TaPetKeyLogger.info(f"整体缩放调整为 {int(new_scale * 100)}%")

    def _apply_scale(self) -> None:
        """_按当前缩放刷新主窗口、角色与气泡窗口尺寸_"""
        size = self.main_size()
        # 同步 Tk 的尺寸与位置认知（含逻辑坐标，避免 Tk 用陈旧位置回挪窗口）
        self.geometry(f"{size}x{size}+{self._rest_x}+{self._rest_y}")
        if hasattr(self, "current_charactor"):
            self.current_charactor.config(width=size, height=size)
            self.current_charactor.apply_scale(self._skin_scale * self.user_scale)
        if hasattr(self, "combo_window"):
            self.combo_window.apply_scale(self.user_scale)
            self._place_combo_window()

    def _exit_app(self):
        TaPetKeyLogger.info("程序触发退出事件。")

        # 退出前持久化皮肤与窗口位置（只读普通属性，不触碰 tkinter）
        self._save_state()

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

    # 打包运行时把工作目录切到资源目录（_MEIPASS），
    # 保证代码里 "assets/..." 这类相对路径可正确寻址
    if getattr(sys, "frozen", False):
        os.chdir(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))

    app = TaPetKeyMain()
    app.mainloop()