import time, os, queue
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

        # 新增一个文字粒子（单个透明窗口 + Canvas 多 item 渲染，
        # 避免长按连发时反复创建/销毁 Toplevel 造成卡顿）
        self.effect_window.add(
            event.name if event.name != 'backspace' else 'delete')

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

        # 记录窗口位置（在主线程读取，退出时持久化到配置）
        self._last_pos = (self.winfo_x(), self.winfo_y())

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
                self._place_combo_window()
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
            self._place_combo_window()
            self._bounce_strength += self.grvaity
            self.after(interval, self._bounce_step)
            return

        # 回归初始坐标
        self.geometry(f"+{self.winfo_x()}+{self._bounce_initial_y}")
        self._place_combo_window()

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
        self._place_combo_window()

        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def bind_window_event(self):
        """_绑定窗口事件_"""
        self.bind("<Button-1>", self.start_move)
        self.bind("<B1-Motion>", self.update_move)

    def init_window_attr(self):
        self.title("TaPetKey")
        size = self.main_size()
        pos_x, pos_y = self._last_pos
        self.geometry(f"{size}x{size}+{pos_x}+{pos_y}")
        self.attributes("-topmost", True)
        self.config(bg=self.transparentcolor)
        self.attributes('-transparentcolor', self.transparentcolor)
        self.overrideredirect(True)

        self.bind_window_event()

    def init_app_widgets(self):
        """_初始化应用程序部件_"""
        size = self.main_size()
        self.current_charactor = \
        Charactor(
            asset_id=self._initial_skin, bg = self.transparentcolor,
            master=self, image_scale=self._skin_scale * self.user_scale,
            switch_func=self.random_bounce_event,
            width=size, height=size
        )
        self.current_charactor.pack(side=tk.TOP)

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

    def _place_combo_window(self) -> None:
        """_按皮肤偏移把气泡窗口对齐到主窗口_"""
        ox, oy = self.combo_offset
        self.combo_window.geometry(
            f"+{self.winfo_x() + ox}+{self.winfo_y() + oy}")

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
        self.geometry(f"{size}x{size}")
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

    app = TaPetKeyMain()
    app.mainloop()