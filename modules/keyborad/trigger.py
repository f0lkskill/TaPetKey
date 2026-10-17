import keyboard, time
from threading import Thread
from modules.log import TaPetKeyLogger

class KeyboardTrigger:
    def __init__(self, refresh_interval: float = 1) -> None:
        self.queue_press_count = 0
        self.refresh_interval = refresh_interval

        self.bind_event()

        # 循环线程进行清理
        Thread(target=self.auto_refresh, daemon=True).start()

    def auto_refresh(self):
        while 1:
            time.sleep(self.refresh_interval)
            self.queue_press_count = 0

    def bind_event(self):
        """绑定所有相关事件"""
        keyboard.on_press(self.on_any_press)

    def on_any_press(self, event):
        if self.queue_press_count >= 10:
            # 不得制造过多的队列
            return
        self.queue_press_count += 1
        TaPetKeyLogger.debug("键盘按键被按下，当前队列数量: {}".format(self.queue_press_count))