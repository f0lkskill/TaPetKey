"""每像素 alpha 分层窗口封装。

Tk 的 -transparentcolor 是精确色键匹配，抗锯齿边缘扣不干净、命中键色的像素又会被误扣。
本模块把 Tk 顶层窗口（Tk / Toplevel）改造成 Windows 分层窗口
（WS_EX_LAYERED + UpdateLayeredWindow），直接使用 PIL RGBA 图的 alpha 通道，
彻底摆脱色键问题，并且完全透明的像素会自动点击穿透。
"""
import ctypes
import ctypes.wintypes as wt

from PIL import Image, ImageChops

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

WS_EX_LAYERED = 0x00080000
GWL_EXSTYLE = -20
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
GA_ROOT = 2


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_byte), ("BlendFlags", ctypes.c_byte),
                ("SourceConstantAlpha", ctypes.c_byte), ("AlphaFormat", ctypes.c_byte)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


# 明确声明参数类型，避免 64 位下 HWND / 句柄被截断为 32 位
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
user32.GetAncestor.restype = wt.HWND
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetParent.restype = wt.HWND
user32.GetParent.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.GetDC.argtypes = [wt.HWND]
user32.ReleaseDC.restype = ctypes.c_int
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.UpdateLayeredWindow.restype = wt.BOOL
user32.UpdateLayeredWindow.argtypes = [
    wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE),
    wt.HDC, ctypes.POINTER(wt.POINT), wt.DWORD, ctypes.POINTER(_BLENDFUNCTION), wt.DWORD]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.CreateDIBSection.argtypes = [
    wt.HDC, ctypes.POINTER(_BITMAPINFO), wt.UINT,
    ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.DeleteObject.restype = wt.BOOL
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.restype = wt.BOOL
gdi32.DeleteDC.argtypes = [wt.HDC]


class LayeredWindow:
    """把一个 Tk 顶层窗口变成「每像素 alpha」的分层窗口，用 PIL 图驱动显示。"""

    def __init__(self, window):
        self.window = window
        self._hwnd = 0
        self._adopted = False
        self._size = (0, 0)
        self._screen_dc = 0
        self._mem_dc = 0
        self._hbitmap = 0
        self._bits = None  # type: ignore

    def bind(self) -> int:
        """_取得顶层 HWND 并开启 WS_EX_LAYERED（幂等）_"""
        if self._adopted:
            return self._hwnd
        self.window.update_idletasks()
        wid = self.window.winfo_id()
        # GA_ROOT 对根窗口和 Toplevel 都能拿到真正的顶层窗口
        hwnd = user32.GetAncestor(wid, GA_ROOT) or user32.GetParent(wid) or wid
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED)
        self._hwnd = hwnd
        self._adopted = True
        return hwnd

    def _ensure_buffers(self, width: int, height: int) -> None:
        if self._hbitmap and self._size == (width, height):
            return
        self._release_buffers()
        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height  # 负数 = top-down，行序与 PIL 一致
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  # BI_RGB
        self._screen_dc = user32.GetDC(0)
        self._mem_dc = gdi32.CreateCompatibleDC(self._screen_dc)
        bits = ctypes.c_void_p()
        self._hbitmap = gdi32.CreateDIBSection(
            self._mem_dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        gdi32.SelectObject(self._mem_dc, self._hbitmap)
        self._bits = bits
        self._size = (width, height)

    def _release_buffers(self) -> None:
        if self._hbitmap:
            gdi32.DeleteObject(self._hbitmap)
            self._hbitmap = 0
        if self._mem_dc:
            gdi32.DeleteDC(self._mem_dc)
            self._mem_dc = 0
        if self._screen_dc:
            user32.ReleaseDC(0, self._screen_dc)
            self._screen_dc = 0
        self._bits = None
        self._size = (0, 0)

    @staticmethod
    def _premultiplied_bgra(image: Image.Image) -> bytes:
        """_转成 UpdateLayeredWindow 需要的预乘 BGRA 字节_"""
        red, green, blue, alpha = image.split()
        premul = Image.merge("RGBA", (
            ImageChops.multiply(red, alpha),
            ImageChops.multiply(green, alpha),
            ImageChops.multiply(blue, alpha),
            alpha,
        ))
        return premul.tobytes("raw", "BGRA")

    def set_frame(self, image: Image.Image, x: int, y: int, alpha: float = 1.0) -> None:
        """_把一帧 RGBA 图推送到窗口，并把窗口定位到 (x, y)_

        Args:
            image (Image.Image): _窗口内容（RGBA）_
            x (int): _窗口左上角屏幕坐标 X_
            y (int): _窗口左上角屏幕坐标 Y_
            alpha (float, optional): _整体透明度 0~1_. 默认 1.0.
        """
        self.bind()
        image = image.convert("RGBA")
        width, height = image.size
        self._ensure_buffers(width, height)
        bgra = self._premultiplied_bgra(image)
        ctypes.memmove(self._bits, bgra, len(bgra))
        const_alpha = max(0, min(255, int(round(alpha * 255))))
        blend = _BLENDFUNCTION(AC_SRC_OVER, 0, const_alpha, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(
            self._hwnd, self._screen_dc,
            ctypes.byref(wt.POINT(int(x), int(y))),
            ctypes.byref(wt.SIZE(width, height)),
            self._mem_dc, ctypes.byref(wt.POINT(0, 0)), 0,
            ctypes.byref(blend), ULW_ALPHA)

    def release(self) -> None:
        """_释放 GDI 资源_"""
        self._release_buffers()
