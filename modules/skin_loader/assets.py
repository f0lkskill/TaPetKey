from PIL import ImageTk
from os.path import basename

class ImageAsset:
    """_基本素材类_
    """
    def __init__(self, path: str, image: ImageTk.PhotoImage):
        """_初始化图像素材_

        Args:
            path (str): _图像路径_
            image (ImageTk.PhotoImage): _图像对象_
        """
        self.path = path
        self.image = image
        self.width = image.width()
        self.height = image.height()
        self.size = image.__size
        self.base_name = basename(self.path).split('.')[0]