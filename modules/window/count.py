import tkinter as tk
from PIL import Image, ImageTk

class CounterWindow(tk.Toplevel):
    """_combo计数器窗口_

    Args:
        tk (_type_): _tk_
    """

    def __init__(self, *args, **kwargs):
        """_初始化计数器窗口_"""
        super().__init__(*args, **kwargs)
        self.mainframe:tk.Canvas
        self.bubble_img_tk:ImageTk.PhotoImage
        self.text_id:int = -1
        self.current_count:int = 0

        self.init_window_attr()
        self.init_window_widget()
        self.draw_image()

    def init_window_attr(self):
        """_初始化窗口属性_"""
        self.title("计数器")
        self.geometry("125x125")
        self.attributes("-topmost", True)
        self.config(bg="black")
        self.attributes("-transparentcolor", "black")
        self.overrideredirect(True)

        # self.withdraw()

    def init_window_widget(self):
        """_初始化窗口小部件_"""
        self.mainframe = tk.Canvas(self)
        self.mainframe.pack(fill=tk.BOTH, expand=True)

    def add_one(self):
        """_添加一个计数_"""
        self.current_count += 1
        self.draw_image()

    def draw_image(self):
        """_初始化图像_"""
        self.mainframe.delete(self.text_id)

        img = Image.open("assets/ui/bubble.png")
        img = img.resize((125, 125))
        self.bubble_img_tk = ImageTk.PhotoImage(img)
        self.mainframe.create_image(62.5, 62.5, image=self.bubble_img_tk)

        self.text_id = self.mainframe.create_text(62.5, 62.5,
             text=str(self.current_count), fill="#151515",
               font=("Consolas", 30, 'bold'))