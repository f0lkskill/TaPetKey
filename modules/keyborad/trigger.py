import keyboard, time
from threading import Thread
from modules.log import TaPetKeyLogger

class KeyboardTrigger:
    def __init__(self, refresh_interval: float = 1, update_internal: float = 0.01) -> None:
        self.queue_press_events:list = []
        self.queue_release_events:list = []
        self.refresh_interval = refresh_interval
        self.update_internal = update_internal

        # 绑定事件
        Thread(target=self.bind_event, daemon=True).start()

        # 循环线程进行清理
        Thread(target=self.auto_refresh, daemon=True).start()

    def auto_refresh(self):
        while 1:
            time.sleep(self.refresh_interval)
            self.queue_press_events.clear()

    def bind_event(self):
        """绑定所有相关事件"""
        import queue
        import time

        event_queue = queue.Queue()

        def handle_event(e):
            event_queue.put(e)

        def process_events():
            while True:
                try:
                    event = event_queue.get(timeout=0.1)
                    if event.event_type == "up":
                        self.on_any_release(event)
                    else:
                        self.on_any_press(event)

                    time.sleep(self.update_internal)
                except queue.Empty:
                    pass

        Thread(target=process_events, daemon=True).start()

        keyboard.hook(handle_event)
        keyboard.wait()  # 阻塞主线程

    def on_any_press(self, event):
        if len(self.queue_press_events) >= 10:
            # 不得制造过多的队列
            return
        self.queue_press_events.append(event)

        # TaPetKeyLogger.debug("键盘按键按下 {0}，当前队列数量: {1}" \
        #     .format(event.name, len(self.queue_press_events)))

    def on_any_release(self, event):
        # if len(self.queue_release_events) >= 10:
        #     # 不得制造过多的队列
        #     return
        self.queue_release_events.append(event)

        # TaPetKeyLogger.info("键盘按键释放 {0}，当前队列数量: {1}" \
        #     .format(event.name, len(self.queue_release_events)))