import tkinter as tk
from PIL import Image, ImageTk

class CounterWindow(tk.Toplevel):
    """_combo计数器窗口_

    Args:
        tk (_type_): _tk_
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mainframe:tk.Canvas
        self.bubble_img_tk:ImageTk.PhotoImage

        self.init_window_attr()
        self.init_window_widget()
        self.init_image()

    def init_window_attr(self):
        self.title("计数器")
        self.geometry("125x125")
        self.attributes("-topmost", True)
        self.config(bg="black")
        self.attributes("-transparentcolor", "black")
        self.overrideredirect(True)

    def init_window_widget(self):
        self.mainframe = tk.Canvas(self)
        self.mainframe.pack(fill=tk.BOTH, expand=True)

    def init_image(self):
        img = Image.open("assets/ui/bubble.png")
        img = img.resize((125, 125))
        self.bubble_img_tk = ImageTk.PhotoImage(img)
        self.mainframe.create_image(62.5, 62.5, image=self.bubble_img_tk)

if __name__ == "__main__":
    root = tk.Tk()

    cw = CounterWindow(root)

    root.mainloop()