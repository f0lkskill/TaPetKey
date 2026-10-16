from PIL import Image
from os.path import basename

class ImageAsset:
    """_基本素材类_
    """
    def __init__(self, path: str, image: Image.Image):
        """_初始化图像素材_

        Args:
            path (str): _图像路径_
            image (Image): _图像对象_
        """
        self.path = path
        self.image = image
        self.width = image.width
        self.height = image.height
        self.base_name = basename(self.path).split('.')[0]

    def __str__(self) -> str:
        return f"<ImageAsset: {self.base_name}, {self.width}x{self.height}, {self.path}>"