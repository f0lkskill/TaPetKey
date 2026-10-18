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
from modules.skin_loader import get_all_skins

ICON_DIR = "assets/icon"
AUTOSTART_ON_ICON = os.path.join(ICON_DIR, "on.png")
AUTOSTART_OFF_ICON = os.path.join(ICON_DIR, "off.png")
SKIN_ICON = os.path.join(ICON_DIR, "skin.png")

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
# 绘制子菜单箭头
_user32.DrawFrameControl.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
_user32.DrawFrameControl.restype = ctypes.c_int


def _append_owner_draw(menu, item_id):
    _user32.AppendMenuW(menu, win32con.MF_OWNERDRAW, item_id, None)


# 皮肤子菜单项的起始 ID
SKIN_ITEM_ID_BASE = 2000
# 子菜单箭头占位宽度
ARROW_WIDTH = 16
# DrawFrameControl 常量（子菜单箭头）
_DFC_MENU = 2
_DFCS_MENUARROW = 0x0000

# 托盘消息
WM_TRAYICON = win32con.WM_USER + 20

# 菜单项 ID
ID_AUTOSTART = 1000
ID_EXIT = 1001
ID_SKIN = 1002

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

    def __init__(self, exit_func, on_switch_skin=None):
        self.exit_func = exit_func
        self.on_switch_skin = on_switch_skin
        self.hwnd = None
        self.hicon = None
        self._thread = None
        self._skin_item_map = {}    # 皮肤子菜单项 ID -> 皮肤ID
        self._submenu_builders = {} # 父项 ID -> 返回子菜单句柄的可调用对象

        self._icon_size = 0
        self._item_meta = {}        # item_id -> {text, bitmap, width, height}
        self._bitmaps = []          # 保持位图引用，防止被回收
        self._menu_brush = None
        self._hl_brush = None
        self._text_color = 0
        self._hl_text_color = 0
        self._hfont = None
        self._hfont_owned = False

        # 菜单项（全部 owner-draw 自绘）：
        #   {id, text, icon(路径或返回路径的可调用对象), submenu?}
        #   带 submenu 的项点击时手动弹出子菜单，并在右侧绘制箭头。
        self.menu_items = [
            {
                "id": ID_AUTOSTART,
                "text": "开机自启动",
                "icon": self._autostart_icon,
            },
            {
                "id": ID_SKIN,
                "text": "皮肤",
                "icon": SKIN_ICON,
                "submenu": self._build_skin_submenu,
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

    def _measure_text(self, text):
        """_测量文字尺寸（复用当前菜单字体）_"""
        screen = win32gui.GetDC(0)
        screen_dc = win32ui.CreateDCFromHandle(screen)
        measure_dc = screen_dc.CreateCompatibleDC()
        measure_hdc = measure_dc.GetSafeHdc()
        old_font = None
        if self._hfont:
            old_font = win32gui.SelectObject(measure_hdc, self._hfont)
        try:
            return measure_dc.GetTextExtent(text)
        finally:
            if old_font:
                win32gui.SelectObject(measure_hdc, old_font)
            measure_dc.DeleteDC()
            screen_dc.DeleteDC()
            win32gui.ReleaseDC(0, screen)

    def _load_icon_bitmap(self, icon_path):
        """_加载图标并转为预乘 alpha 位图（真透明）_"""
        if not icon_path or not os.path.exists(icon_path): # type: ignore
            return None
        src = Image.open(icon_path).convert("RGBA").resize( # type: ignore
            (self._icon_size, self._icon_size), Image.LANCZOS) # type: ignore
        bmp = _make_alpha_bitmap(src)
        self._bitmaps.append(bmp)
        return bmp

    def _skin_icon_path(self, skin):
        """_取皮肤预览图路径（info.json 的 icon，缺失则回退目录内首张 png）_"""
        skin_dir = os.path.join("assets", "skins", skin["id"])
        icon = skin.get("icon")
        if icon:
            path = os.path.join(skin_dir, icon)
            if os.path.exists(path):
                return path
        if os.path.isdir(skin_dir):
            for name in sorted(os.listdir(skin_dir)):
                if name.lower().endswith(".png"):
                    return os.path.join(skin_dir, name)
        return None

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

        for item in self.menu_items:
            item_id = item["id"]
            text = item["text"]
            has_sub = "submenu" in item
            if has_sub:
                self._submenu_builders[item_id] = item["submenu"]

            icon_path = item.get("icon")
            if callable(icon_path):
                icon_path = icon_path()
            bmp = self._load_icon_bitmap(icon_path)

            text_w, text_h = self._measure_text(text)
            width = ITEM_MARGIN * 2 + text_w
            if bmp is not None:
                width += icon_size + ITEM_GAP
            if has_sub:
                width += ARROW_WIDTH
            height = max(icon_size, text_h) + ITEM_VPAD * 2

            self._item_meta[item_id] = {
                "text": text, "bitmap": bmp,
                "width": width, "height": height,
                "has_submenu": has_sub,
            }
            _append_owner_draw(menu, item_id)

        return menu

    def _build_skin_submenu(self):
        """_构建皮肤子菜单（自绘，预览图来自各皮肤 info.json 的 icon）_"""
        submenu = win32gui.CreatePopupMenu()
        self._skin_item_map = {}
        icon_size = self._icon_size
        for index, skin in enumerate(get_all_skins()):
            item_id = SKIN_ITEM_ID_BASE + index
            self._skin_item_map[item_id] = skin["id"]

            bmp = self._load_icon_bitmap(self._skin_icon_path(skin))
            text = skin["name"]
            text_w, text_h = self._measure_text(text)
            width = ITEM_MARGIN * 2 + text_w
            if bmp is not None:
                width += icon_size + ITEM_GAP
            height = max(icon_size, text_h) + ITEM_VPAD * 2

            self._item_meta[item_id] = {
                "text": text, "bitmap": bmp,
                "width": width, "height": height,
                "has_submenu": False,
            }
            _append_owner_draw(submenu, item_id)
        return submenu

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
            text_right = rc.right - ITEM_MARGIN
            if meta.get("has_submenu"):
                text_right -= ARROW_WIDTH
            text_rect = _RECT(x, rc.top, text_right, rc.bottom)
            _user32.DrawTextW(
                hdc, meta["text"], -1, ctypes.byref(text_rect),
                win32con.DT_SINGLELINE | win32con.DT_VCENTER | win32con.DT_LEFT)

            # 子菜单箭头
            if meta.get("has_submenu"):
                cy = (rc.top + rc.bottom) // 2
                arrow = _RECT(rc.right - ITEM_MARGIN - 8, cy - 4,
                              rc.right - ITEM_MARGIN, cy + 4)
                _user32.DrawFrameControl(
                    hdc, ctypes.byref(arrow), _DFC_MENU, _DFCS_MENUARROW)
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

    def _show_skin_submenu(self):
        """_点击「皮肤」项时在光标处弹出皮肤子菜单_"""
        builder = self._submenu_builders.get(ID_SKIN)
        if not builder:
            return
        submenu = builder()
        try:
            pos = win32gui.GetCursorPos()
            win32gui.SetForegroundWindow(self.hwnd) # type: ignore
            cmd = win32gui.TrackPopupMenu(
                submenu,
                win32con.TPM_LEFTALIGN | win32con.TPM_TOPALIGN |
                win32con.TPM_RETURNCMD,
                pos[0], pos[1], 0, self.hwnd, None) # type: ignore
            if cmd:
                skin_id = self._skin_item_map.get(cmd)
                if skin_id is not None and self.on_switch_skin:
                    self.on_switch_skin(skin_id)
        finally:
            win32gui.DestroyMenu(submenu) # type: ignore

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
            elif item_id == ID_SKIN:
                self._show_skin_submenu()
            else:
                skin_id = self._skin_item_map.get(item_id)
                if skin_id is not None and self.on_switch_skin:
                    self.on_switch_skin(skin_id)
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
