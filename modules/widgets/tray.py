import ctypes
import os
import threading
from ctypes import wintypes

import win32api
import win32con
import win32gui
import win32ui
from PIL import Image, ImageChops

from modules.config import is_autostart_enabled, set_autostart

ICON_DIR = "assets/icon"
AUTOSTART_ON_ICON = os.path.join(ICON_DIR, "on.png")
AUTOSTART_OFF_ICON = os.path.join(ICON_DIR, "off.png")

# 菜单项图标相对勾选栏尺寸的放大倍数
ICON_SCALE = 2
ITEM_MARGIN = 6     # 菜单项左右外边距
ITEM_GAP = 8        # 图标与文字间距
ITEM_VPAD = 4       # 菜单项上下内边距

# uxtheme（用于读取视觉主题的真实颜色）
_uxtheme = ctypes.windll.uxtheme
_uxtheme.OpenThemeData.restype = ctypes.c_void_p
_uxtheme.OpenThemeData.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
_uxtheme.CloseThemeData.argtypes = [ctypes.c_void_p]
_uxtheme.GetThemeColor.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.POINTER(ctypes.c_uint32),
]
_uxtheme.GetThemeColor.restype = ctypes.c_long
_uxtheme.GetThemeSysColor.argtypes = [ctypes.c_void_p, ctypes.c_int]
_uxtheme.GetThemeSysColor.restype = ctypes.c_uint32

# user32（直接调 AppendMenuW，避免 pywin32 对 owner-draw 参数的类型限制）
_user32 = ctypes.windll.user32
_user32.AppendMenuW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_wchar_p]
_user32.AppendMenuW.restype = ctypes.c_int
_user32.DrawTextW.argtypes = [
    ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p,
    ctypes.c_uint]
_user32.DrawTextW.restype = ctypes.c_int


def _append_owner_draw(menu, item_id):
    _user32.AppendMenuW(menu, win32con.MF_OWNERDRAW, item_id, None)

# 托盘消息
WM_TRAYICON = win32con.WM_USER + 20

# 菜单项 ID
ID_AUTOSTART = 1000
ID_EXIT = 1001

# owner-draw 消息
_ODT_MENU = 1


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG), ("top", wintypes.LONG),
        ("right", wintypes.LONG), ("bottom", wintypes.LONG),
    ]


class _MEASUREITEMSTRUCT(ctypes.Structure):
    _fields_ = [
        ("CtlType", wintypes.UINT), ("CtlID", wintypes.UINT),
        ("itemID", wintypes.UINT), ("itemWidth", wintypes.UINT),
        ("itemHeight", wintypes.UINT), ("itemData", ctypes.c_size_t),
    ]


class _DRAWITEMSTRUCT(ctypes.Structure):
    _fields_ = [
        ("CtlType", wintypes.UINT), ("CtlID", wintypes.UINT),
        ("itemID", wintypes.UINT), ("itemAction", wintypes.UINT),
        ("itemState", wintypes.UINT), ("hwndItem", wintypes.HWND),
        ("hDC", wintypes.HDC), ("rcItem", _RECT),
        ("itemData", ctypes.c_size_t),
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER),
                ("bmiColors", wintypes.DWORD * 3)]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte),
    ]


# gdi32（用于创建 32bpp DIB 并 AlphaBlend 实现真透明）
_gdi32 = ctypes.windll.gdi32
_gdi32.CreateDIBSection.restype = ctypes.c_void_p
_gdi32.CreateDIBSection.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
    ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_uint]
_gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
_gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
_gdi32.SelectObject.restype = ctypes.c_void_p
_gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
_gdi32.DeleteDC.argtypes = [ctypes.c_void_p]

# AlphaBlend 由 msimg32.dll 提供
_msimg32 = ctypes.windll.msimg32
_msimg32.AlphaBlend.restype = ctypes.c_int
_msimg32.AlphaBlend.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    _BLENDFUNCTION]


def _to_rgb(colorref):
    return (colorref & 0xff, (colorref >> 8) & 0xff, (colorref >> 16) & 0xff)


def _to_colorref(rgb):
    r, g, b = rgb
    return r | (g << 8) | (b << 16)


def get_theme_sys_color(hwnd, color_id, fallback):
    """_读取视觉主题的系统色_

    颜色会随浅色/深色主题自动变化。失败时返回 fallback（RGB 元组）。
    """
    try:
        htheme = _uxtheme.OpenThemeData(hwnd, "Menu")
        if htheme:
            try:
                return _to_rgb(_uxtheme.GetThemeSysColor(htheme, color_id))
            finally:
                _uxtheme.CloseThemeData(htheme)
    except Exception:
        pass
    c = win32api.GetSysColor(color_id)
    return fallback if not c else _to_rgb(c)


def get_menu_bg_color(hwnd=0):
    """_获取菜单背景色（RGB 元组）_"""
    return get_theme_sys_color(hwnd, win32con.COLOR_MENU, (240, 240, 240))


def _get_menu_font(hwnd):
    """_获取菜单字体_

    返回 (HFONT, owned)。owned 为 True 时需要在用完后 DeleteObject。
    """
    try:
        ncm = win32gui.SystemParametersInfo(win32con.SPI_GETNONCLIENTMETRICS)
        if isinstance(ncm, dict) and "lfMenuFont" in ncm:
            return win32gui.CreateFontIndirect(ncm["lfMenuFont"]), True
    except Exception:
        pass
    return win32gui.GetStockObject(win32con.DEFAULT_GUI_FONT), False # type: ignore


def _make_alpha_bitmap(image):
    """_PIL 图像转预乘 alpha 的 32bpp DIB_

    返回 (hbmp, memdc, old_bmp, width, height)，供 _alpha_blend 使用。
    预乘 alpha 后配合 AlphaBlend 可实现真正的透明（透明区显示背景色）。
    """
    image = image.convert("RGBA")
    r, g, b, a = image.split()
    rgb = Image.merge("RGB", (r, g, b))
    a_rgb = Image.merge("RGB", (a, a, a))
    pr, pg, pb = ImageChops.multiply(rgb, a_rgb).split()  # 预乘
    data = Image.merge("RGBA", (pb, pg, pr, a)).tobytes()  # DIB 内存序 BGRA

    w, h = image.size
    bmi = _BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h     # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0  # BI_RGB

    bits = ctypes.c_void_p()
    hbmp = _gdi32.CreateDIBSection(0, ctypes.byref(bmi), 0,
                                   ctypes.byref(bits), None, 0)
    ctypes.memmove(bits, data, len(data))
    memdc = _gdi32.CreateCompatibleDC(0)
    old = _gdi32.SelectObject(memdc, hbmp)
    return hbmp, memdc, old, w, h


def _alpha_blend(hdc, x, y, w, h, src_dc):
    """_在 hdc 上以预乘 alpha 混合绘制 src_dc 的位图_"""
    bf = _BLENDFUNCTION(0, 0, 255, 1)  # AC_SRC_OVER / 0 / 255 / AC_SRC_ALPHA
    _msimg32.AlphaBlend(hdc, x, y, w, h, src_dc, 0, 0, w, h, bf)


class AppTray:
    """_系统托盘_

    基于 pywin32 原生实现；右键菜单为 owner-draw 自绘，
    因此图标可以自由放大，且菜单项高度会随图标自适应。
    """

    def __init__(self, exit_func):
        self.exit_func = exit_func
        self.hwnd = None
        self.hicon = None
        self._thread = None

        self._icon_size = 0
        self._item_meta = {}        # item_id -> {text, bitmap, width, height}
        self._bitmaps = []          # 保持位图引用，防止被回收
        self._menu_brush = None
        self._hl_brush = None
        self._text_color = 0
        self._hl_text_color = 0
        self._hfont = None
        self._hfont_owned = False

        # 菜单项：id / 文本 / 图标（路径或返回路径的可调用对象）
        self.menu_items = [
            {
                "id": ID_AUTOSTART,
                "text": "开机自启动",
                "icon": self._autostart_icon,
            },
            {
                "id": ID_EXIT,
                "text": "退出",
                "icon": os.path.join(ICON_DIR, "exit.png"),
            },
        ]

        self.start()

    def start(self):
        """_启动托盘线程_"""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        hinst = win32api.GetModuleHandle(None)

        wc = win32gui.WNDCLASS()
        wc.hInstance = hinst # type: ignore
        wc.lpszClassName = "TaPetKeyTrayWindow" # type: ignore
        wc.lpfnWndProc = self._wnd_proc # type: ignore
        wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW # type: ignore
        try:
            class_atom = win32gui.RegisterClass(wc)
        except win32gui.error:
            class_atom = "TaPetKeyTrayWindow"

        self.hwnd = win32gui.CreateWindow(
            class_atom, "TaPetKeyTray", 0, 0, 0, 0, 0, 0, 0, hinst, None
        )

        # 托盘图标（使用单独的 ico，与菜单项图标互不影响）
        self.hicon = win32gui.LoadImage(
            hinst, os.path.join(ICON_DIR, "icon.ico"), win32con.IMAGE_ICON,
            0, 0, win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
        )

        nid = (self.hwnd, 0,
               win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
               WM_TRAYICON, self.hicon, "TaPetKey")
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid) # type: ignore

        win32gui.PumpMessages()

        # 退出清理
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0)) # type: ignore
        if self.hicon:
            win32gui.DestroyIcon(self.hicon)
        self._release_resources()

    def _release_resources(self):
        """_释放上一轮菜单占用的 GDI 资源_"""
        for entry in self._bitmaps:
            try:
                hbmp, memdc, old, _w, _h = entry
                if old:
                    _gdi32.SelectObject(memdc, old)
                _gdi32.DeleteObject(hbmp)
                _gdi32.DeleteDC(memdc)
            except Exception:
                pass
        self._bitmaps.clear()
        self._item_meta.clear()
        for attr in ("_menu_brush", "_hl_brush"):
            brush = getattr(self, attr, None)
            if brush:
                try:
                    win32gui.DeleteObject(brush)
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._hfont and self._hfont_owned:
            try:
                win32gui.DeleteObject(self._hfont)
            except Exception:
                pass
        self._hfont = None
        self._hfont_owned = False

    def _build_menu(self):
        """_构建 owner-draw 自绘菜单_"""
        menu = win32gui.CreatePopupMenu()
        # 上一轮菜单已销毁，先回收旧资源
        self._release_resources()

        hwnd = self.hwnd
        menu_bg = get_menu_bg_color(hwnd) # type: ignore
        menu_text = get_theme_sys_color(hwnd, win32con.COLOR_MENUTEXT, (0, 0, 0))
        hl_bg = get_theme_sys_color(hwnd, win32con.COLOR_HIGHLIGHT, (0, 120, 215))
        hl_text = get_theme_sys_color(hwnd, win32con.COLOR_HIGHLIGHTTEXT, (255, 255, 255))

        self._menu_brush = win32gui.CreateSolidBrush(_to_colorref(menu_bg))
        self._hl_brush = win32gui.CreateSolidBrush(_to_colorref(hl_bg))
        self._text_color = _to_colorref(menu_text)
        self._hl_text_color = _to_colorref(hl_text)
        self._hfont, self._hfont_owned = _get_menu_font(hwnd)

        # 图标尺寸 = 勾选栏尺寸 * 放大倍数
        check = win32api.GetSystemMetrics(win32con.SM_CXMENUCHECK) or 16
        self._icon_size = check * ICON_SCALE
        icon_size = self._icon_size

        # 用于测量文字尺寸
        screen = win32gui.GetDC(0)
        screen_dc = win32ui.CreateDCFromHandle(screen)
        measure_dc = screen_dc.CreateCompatibleDC()
        measure_hdc = measure_dc.GetSafeHdc()
        old_measure_font = None
        if self._hfont:
            old_measure_font = win32gui.SelectObject(measure_hdc, self._hfont)

        try:
            for item in self.menu_items:
                item_id = item["id"]
                text = item["text"]
                icon_path = item["icon"]
                if callable(icon_path):
                    icon_path = icon_path()

                bmp = None
                if icon_path and os.path.exists(icon_path): # type: ignore
                    src = Image.open(icon_path).convert("RGBA").resize( # type: ignore
                        (icon_size, icon_size), Image.LANCZOS) # type: ignore
                    bmp = _make_alpha_bitmap(src)   # 真透明（预乘 alpha）
                    self._bitmaps.append(bmp)

                text_w, text_h = measure_dc.GetTextExtent(text)
                width = ITEM_MARGIN * 2 + text_w
                if bmp is not None:
                    width += icon_size + ITEM_GAP
                height = max(icon_size, text_h) + ITEM_VPAD * 2

                self._item_meta[item_id] = {
                    "text": text, "bitmap": bmp,
                    "width": width, "height": height,
                }
                _append_owner_draw(menu, item_id)
        finally:
            if old_measure_font:
                win32gui.SelectObject(measure_hdc, old_measure_font)
            measure_dc.DeleteDC()
            screen_dc.DeleteDC()
            win32gui.ReleaseDC(0, screen)

        return menu

    def _on_measure_item(self, lparam):
        try:
            mis = ctypes.cast(lparam, ctypes.POINTER(_MEASUREITEMSTRUCT)).contents
        except Exception:
            return False
        if mis.CtlType != _ODT_MENU:
            return False
        meta = self._item_meta.get(mis.itemID)
        if not meta:
            return False
        mis.itemWidth = meta["width"]
        mis.itemHeight = meta["height"]
        return True

    def _on_draw_item(self, lparam):
        try:
            dis = ctypes.cast(lparam, ctypes.POINTER(_DRAWITEMSTRUCT)).contents
        except Exception:
            return False
        if dis.CtlType != _ODT_MENU:
            return False
        self._draw_item(dis)
        return True

    def _draw_item(self, dis):
        meta = self._item_meta.get(dis.itemID)
        if not meta:
            return

        hdc = dis.hDC
        rc = dis.rcItem
        selected = bool(dis.itemState & win32con.ODS_SELECTED)

        # 背景
        win32gui.FillRect(
            hdc, (rc.left, rc.top, rc.right, rc.bottom), # type: ignore
            self._hl_brush if selected else self._menu_brush) # type: ignore

        old_font = None
        if self._hfont:
            old_font = win32gui.SelectObject(hdc, self._hfont)
        try:
            x = rc.left + ITEM_MARGIN
            bmp = meta["bitmap"]
            if bmp is not None:
                sz = self._icon_size
                y = rc.top + ((rc.bottom - rc.top) - sz) // 2
                _alpha_blend(hdc, x, y, sz, sz, bmp[1])
                x += sz + ITEM_GAP

            win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
            win32gui.SetTextColor(
                hdc, self._hl_text_color if selected else self._text_color)
            text_rect = _RECT(x, rc.top, rc.right - ITEM_MARGIN, rc.bottom)
            _user32.DrawTextW(
                hdc, meta["text"], -1, ctypes.byref(text_rect),
                win32con.DT_SINGLELINE | win32con.DT_VCENTER | win32con.DT_LEFT)
        finally:
            if old_font:
                win32gui.SelectObject(hdc, old_font)

    def _autostart_icon(self):
        """_按当前自启动状态返回对应图标_"""
        return AUTOSTART_OFF_ICON if is_autostart_enabled() else AUTOSTART_ON_ICON

    def _toggle_autostart(self):
        """_切换开机自启动_"""
        set_autostart(not is_autostart_enabled())

    def _show_menu(self):
        menu = self._build_menu()
        pos = win32gui.GetCursorPos()
        # 需要先置前台，否则菜单点击外部不会消失
        win32gui.SetForegroundWindow(self.hwnd) # type: ignore
        win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, pos[0], pos[1],
                                0, self.hwnd, None) # type: ignore
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
        win32gui.DestroyMenu(menu) # type: ignore

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON:
            if lparam in (win32con.WM_RBUTTONUP, win32con.WM_LBUTTONUP):
                self._show_menu()
        elif msg == win32con.WM_COMMAND:
            item_id = win32api.LOWORD(wparam)
            if item_id == ID_EXIT:
                self.exit_func()
            elif item_id == ID_AUTOSTART:
                self._toggle_autostart()
        elif msg == win32con.WM_MEASUREITEM:
            return self._on_measure_item(lparam)
        elif msg == win32con.WM_DRAWITEM:
            return self._on_draw_item(lparam)
        elif msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def stop(self):
        """_停止托盘_"""
        if self.hwnd:
            try:
                win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            # 等待消息循环退出，确保托盘图标被移除
            self._thread.join(timeout=1.0)
