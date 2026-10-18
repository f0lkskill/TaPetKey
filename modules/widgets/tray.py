import pystray
from PIL import Image
from threading import Thread

class AppTray:
    def __init__(self, exit_func):
        self.icon = None
        self.menu = None

        self.exit_func = exit_func

        self.init_tray()

        Thread(target=self.run, daemon=True).start()

    def create_icon(self):
        return Image.open("assets/icon/icon.png")

    def init_tray(self):
        exit_icon = Image.open("assets/icon/exit.png")
        self.menu = pystray.Menu(
            pystray.MenuItem('退出', lambda icon, item: self.exit_func())
        )
        self.icon = pystray.Icon('my_app', self.create_icon(), \
            title = "TaPetKey", menu = self.menu)

    def run(self):
        assert self.icon is not None
        self.icon.run()

    def stop(self):
        if self.icon:
            self.icon.stop()