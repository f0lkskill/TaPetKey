import keyboard, time
from threading import Thread
from modules.log import TaPetKeyLogger

class KeyboardTrigger:
    def __init__(self, refresh_interval: float = 1) -> None:
        self.queue_events:list = []
        self.refresh_interval = refresh_interval

        self.bind_event()

        # 循环线程进行清理
        Thread(target=self.auto_refresh, daemon=True).start()

    def auto_refresh(self):
        while 1:
            time.sleep(self.refresh_interval)
            self.queue_events.clear()

    def bind_event(self):
        """绑定所有相关事件"""
        keyboard.on_press(self.on_any_press)

    def on_any_press(self, event):
        if len(self.queue_events) >= 10:
            # 不得制造过多的队列
            return
        self.queue_events.append(event)

        TaPetKeyLogger.debug("键盘按键按下 {0}，当前队列数量: {1}".format(event.name, len(self.queue_events)))