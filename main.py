import atexit
import ctypes
import hashlib
import importlib.util
import json
import math
import os
import platform
import queue
import random
import re
import secrets
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import requests
import struct
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timedelta


def _enable_windows_dpi_awareness() -> None:
    """在创建任何 GUI 窗口前显式启用 Windows Per-Monitor V2 高 DPI 感知，避免多屏不同缩放导致的坐标错位。"""
    if sys.platform != "win32":
        return
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _get_virtual_screen_rect() -> tuple[int, int, int, int]:
    """通过 Win32 GetSystemMetrics 获取真实物理虚拟屏幕原点 (vx, vy) 与宽高 (vw, vh)。"""
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            vx = int(user32.GetSystemMetrics(76))  # SM_XVIRTUALSCREEN
            vy = int(user32.GetSystemMetrics(77))  # SM_YVIRTUALSCREEN
            vw = int(user32.GetSystemMetrics(78))  # SM_CXVIRTUALSCREEN
            vh = int(user32.GetSystemMetrics(79))  # SM_CYVIRTUALSCREEN
            if vw > 0 and vh > 0:
                return vx, vy, vw, vh
        except Exception:
            pass
    return 0, 0, 0, 0


def _get_physical_cursor_pos() -> tuple[int, int] | None:
    """获取当前鼠标在 Windows 物理虚拟桌面中的精确像素坐标。"""
    if sys.platform != "win32":
        return None
    try:
        class _POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = _POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            return int(pt.x), int(pt.y)
    except Exception:
        pass
    return None


_enable_windows_dpi_awareness()
from PySide6.QtCore import (
    Qt,
    QObject,
    QTimer,
    QPoint,
    QPointF,
    QRectF,
    QTime,
    QDate,
    QThread,
    Signal,
    QMimeData,
    QSize,
    QUrl,
    QEvent,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
    QBrush,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTimeEdit,
    QDoubleSpinBox,
    QSpinBox,
    QRadioButton,
    QCheckBox,
    QButtonGroup,
    QScrollArea,
    QSizePolicy,
    QFrame,
    QToolTip,
    QSystemTrayIcon,
    QMenu,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QSizeGrip,
)

from core import (
    APP_VERSION,
    BASE_DIR,
    DATA_DIR,
    SHARE_CACHE_DIR,
    SHARE_REGISTRY,
    AppConfig,
    TimeCalculator,
    HolidayService,
    CompTimeManager,
    FastDownloader,
    LanTransferServer,
    CacheManager,
    SlackingStatsManager,
    AlarmManager,
    set_windows_autostart,
)
from widgets import (
    MAIN_WIDTH,
    SmoothProgressBar,
    CapsuleToggleSwitch,
    VectorIconButton,
    CardFrame,
    RollingStatusTicker,
    CustomRestCalendarDialog,
    CompTimeDialog,
    ThemedToolTipManager,
    CloseConfirmDialog,
    ToastPopup,
    UpdateDialog,
    FeedbackDialog,
    HolidayCalendarDialog,
    DownloadConfirmDialog,
)


STATUS_QUOTE_INTERVAL_MS = 5000
SALARY_QUOTE_INTERVAL_MS = 8000
QUOTE_MIN_GAP_MS = 1800

# 在线检测更新与 Cloudflare Worker 专属加速配置
APP_BRAND_NAME = "IdleMeter"
APP_BRAND_TITLE = "IdleMeter · 摸鱼与高效工作双模小工具"
CURRENT_VERSION = "2.1.0"
GITHUB_OWNER = "Bluen01"
GITHUB_REPO = "PayTick-Releases"
PROXY_DOMAIN = "https://update.bluen01.ccwu.cc"
SILENT_UPDATE_DELAY_MS = 2000
SILENT_UPDATE_INTERVAL_MS = 4 * 60 * 60 * 1000

# 云端配置拉取与意见反馈接口配置
CLOUD_API_DOMAIN = "https://api.bluen01.ccwu.cc"
CLOUD_FETCH_INTERVAL_MS = 10 * 1000
FEEDBACK_COOLDOWN_SEC = 30
EXE_DIR = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else BASE_DIR
MESSAGES_CACHE_FILE = os.path.join(DATA_DIR, "messages_cache.json")


def _ensure_spin_arrow_icons(color_hex: str) -> tuple[str, str]:
    """生成带圆角的上下三角形微调箭头图标，供 QSS url(...) 使用。"""
    tag = color_hex.lstrip("#")
    tmp_dir = tempfile.gettempdir()
    up_path = os.path.join(tmp_dir, f"moyu_spin_up_{tag}.png")
    down_path = os.path.join(tmp_dir, f"moyu_spin_down_{tag}.png")

    for path, points in (
        (up_path, [QPointF(12.0, 4.5), QPointF(5.5, 13.5), QPointF(18.5, 13.5)]),
        (down_path, [QPointF(5.5, 4.5), QPointF(18.5, 4.5), QPointF(12.0, 13.5)]),
    ):
        if not os.path.exists(path):
            img = QImage(24, 18, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            color = QColor(color_hex)
            p.setPen(QPen(color, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(QBrush(color))
            p.drawPolygon(QPolygonF(points))
            p.end()
            img.save(path, "PNG")

    return up_path.replace("\\", "/"), down_path.replace("\\", "/")


MORNING_QUOTES = [
    "☕ 咖啡还没喝，灵魂未上线",
    "💧 早安打工人，先喝口水润润",
    "🚽 带薪晨间如厕，开启美好一天",
    "🐟 上午不摸鱼，下午没精神",
    "👀 刚开机，先让大脑预热十分钟",
    "🌿 伸个懒腰，别让颈椎太早抗议",
    "💸 别急，今天的工资正在慢慢到账",
    "🪑 坐太久了，去茶水间巡视一圈",
    "🍱 人生终极难题：中午吃什么？",
    "⏳ 撑住，离午休干饭不远了",
]

AFTERNOON_QUOTES = [
    "😴 午后犯困是人类的出厂设置",
    "🧋 下午茶时间，点杯快乐水续命？",
    "🔋 电量低于 20%，正在后台充电",
    "👀 盯屏幕太久了，眺望下窗外吧",
    "🎧 戴上耳机，进入沉浸式摸鱼结界",
    "🚶 起来走两步，别和椅子融为一体",
    "🧠 大脑内存已满，建议放空两分钟",
    "🚽 下午茶消化完毕，带薪如厕去",
    "🌤️ 看看窗外，云朵都在自由飘荡",
    "🐟 稳住，下午的每一秒都在白嫖",
]

LAST_30M_QUOTES = [
    "📦 别开新任务了，准备收尾吧",
    "🧹 清理桌面，进入下班倒计时状态",
    "🚽 下班前最后一趟带薪厕所，冲！",
    "🎒 背包已就位，灵魂正在提前撤离",
    "👀 频繁看表，是下班前的标准动作",
    "🌅 夕阳已上线，自由即将到账",
]

LAST_5M_QUOTES = [
    "⚡ 引擎预热中，随时准备弹射起步",
    "🔓 自由倒计时，准备关闭所有窗口",
    "🏃 脚尖已朝向门口，读秒开始！",
    "🎉 今日搬砖圆满结束，准备开溜！",
]

SALARY_TIER_UNDER_3K = [
    "💸 上班还得倒贴？你到底在图什么？",
    "🙏 老板，我这叫来公司体验生活",
    "🍃 这点钱，多呼吸一口都是我亏了",
    "🪑 坐着不动，已经是对公司最大的仁慈",
    "💧 顺便接两杯水，勉强回个车费本",
    "🔋 薪资低电量模式：仅维持基础呼吸",
    "🐢 别催，这个价位只支持慢动作模式",
    "🔌 手机充满电再走，不然今天白干了",
    "🐟 摸鱼不是偷懒，是合理的成本止损",
    "🎭 老板画的饼，我已经吃撑了",
]

SALARY_TIER_3K_TO_10K = [
    "🛑 月薪几千块，你玩什么命啊！",
    "💼 拿多少钱办多少事，多一分算我输",
    "⏳ 准点下班是底线，加班是不可能的",
    "☕ 咖啡喝到位，工作全靠演技撑",
    "🐟 适当摸鱼，是对微薄薪水的基本尊重",
    "🧠 复杂问题别问我，不在薪资覆盖范围",
    "📉 情绪稳定，全靠把预期降到最低",
    "🚽 每天三趟带薪厕所，夺回定价权",
    "🛌 精神内耗？不存在的，又没给精神损失费",
    "🏃 到点就撤，多待一秒都是对自由的背叛",
]

SALARY_TIER_10K_TO_20K = [
    "😎 装装样子稍微努力下，很给面子了",
    "🎩 拿这份薪水，总得演得像个精英",
    "⌨️ 键盘敲得响一点，情绪价值拉满",
    "⚖️ 劳逸结合，优雅地完成 KPI",
    "🍵 喝口好茶，保持职场体面与松弛感",
    "📈 稍微出点力，对得起银行卡短信就行",
    "🎯 精准摸鱼，既要拿高薪也要保发际线",
    "🤝 老板客气，我也就顺手把活干了吧",
    "🧘 遇事不慌，这个价位包含情绪管理",
    "✨ 表面岁月静好，其实已高效搞定",
]

SALARY_TIER_OVER_20K = [
    "🔥 打工人不奋斗，什么时候奋斗？",
    "💰 只要钱给够，公司就是我第二个家",
    "🚀 哪里有需求，哪里就有我的身影",
    "⚡ 每一秒都在爆金币，根本停不下来",
    "🦁 老板说往东，我绝不往西看一眼",
    "🏆 熬的不是夜，是通往财富自由的阶梯",
    "💎 钞能力充能完毕，今日战斗力爆表",
    "🦾 谁说我摸鱼？我这叫战略性思考",
    "🌟 努力不一定成功，但高薪是真的香",
    "👑 扶我起来，我还能再为公司创收！",
]

GREEN_ACCENT = "#10B981"
ORANGE_ACCENT = "#FF6B00"
INVALID_RED = "#EF4444"


def get_source_han_font(size_pt: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """
    统一使用思源黑体 (Source Han Sans CN)
    """
    font = QFont("Source Han Sans CN", size_pt, weight)
    font.setFamilies(["Source Han Sans CN", "思源黑体 CN", "Source Han Sans SC", "思源黑体", "Noto Sans SC", "SimHei"])
    return font


class HolidayFetchWorker(QThread):
    finished_signal = Signal(int, dict, bool)

    def __init__(self, year: int, parent=None):
        super().__init__(parent)
        self.year = year

    def run(self) -> None:
        raw_data, is_online = HolidayService.fetch_year_raw_online(self.year)
        self.finished_signal.emit(self.year, raw_data, is_online)


def _parse_version_tuple(ver_str: str) -> tuple[int, ...]:
    cleaned = str(ver_str or "").strip().lstrip("vV")
    parts: list[int] = []
    for seg in cleaned.split("."):
        seg = seg.strip()
        if seg.isdigit():
            parts.append(int(seg))
        else:
            m = re.match(r"(\d+)", seg)
            if m:
                parts.append(int(m.group(1)))
    return tuple(parts) if parts else (0,)


def _build_latest_release_url() -> str:
    return f"{PROXY_DOMAIN}/api/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def _fetch_latest_release_info(timeout_sec: int = 8) -> dict:
    if "【" in GITHUB_OWNER or "【" in GITHUB_REPO:
        raise ValueError("请先配置 GITHUB_OWNER 与 GITHUB_REPO")
    api_url = _build_latest_release_url()
    headers = {
        "User-Agent": f"IdleMeter/{CURRENT_VERSION}",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    resp = requests.get(api_url, headers=headers, timeout=timeout_sec)
    if resp.status_code != 200:
        raise RuntimeError(f"检测更新失败 (HTTP {resp.status_code})")
    data = resp.json()
    tag_name = str(data.get("tag_name", "")).strip()
    latest_ver = tag_name.lstrip("vV")
    if not latest_ver:
        raise RuntimeError("未获取到有效版本号")
    assets = data.get("assets") or []
    if not assets or not assets[0].get("browser_download_url"):
        raise RuntimeError("当前 Release 未包含可下载安装包")
    raw_url = str(assets[0]["browser_download_url"])
    return {
        "latest_version": latest_ver,
        "changelog": str(data.get("body") or ""),
        "download_url": _rewrite_download_url(raw_url),
    }


def _rewrite_download_url(raw_url: str) -> str:
    if raw_url.startswith("https://github.com"):
        return f"{PROXY_DOMAIN}/dl" + raw_url[len("https://github.com"):]
    return raw_url


def _cleanup_update_artifacts() -> None:
    """启动时自动清理同目录下残留的 update_temp.exe 与 install_update.bat。"""
    dirs_to_check = {os.path.dirname(os.path.abspath(sys.executable)), BASE_DIR}
    for folder in dirs_to_check:
        if not folder or not os.path.isdir(folder):
            continue
        for fname in ("update_temp.exe", "install_update.bat"):
            fpath = os.path.join(folder, fname)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass


class UpdateCheckWorker(QThread):
    """后台异步检测 GitHub Releases 最新版本（经由 Cloudflare Worker 代理）。"""

    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def run(self) -> None:
        try:
            info = _fetch_latest_release_info(timeout_sec=8)
            self.finished_signal.emit(info)
        except ValueError as exc:
            self.error_signal.emit(str(exc))
        except RuntimeError as exc:
            self.error_signal.emit(str(exc))
        except Exception as exc:
            self.error_signal.emit(f"网络请求失败：{exc}")


class UpdateDownloadWorker(QThread):
    """流式下载更新包至运行目录 update_temp.exe。"""

    progress_signal = Signal(int, str)
    finished_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, url: str, dest_path: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.dest_path = dest_path

    def run(self) -> None:
        try:
            with requests.get(self.url, stream=True, timeout=20) as resp:
                if resp.status_code != 200:
                    self.error_signal.emit(f"下载失败 (HTTP {resp.status_code})")
                    return
                total = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                with open(self.dest_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = int(downloaded * 100 / total)
                            mb_done = downloaded / (1024 * 1024)
                            mb_total = total / (1024 * 1024)
                            self.progress_signal.emit(pct, f"已下载 {mb_done:.1f} MB / {mb_total:.1f} MB ({pct}%)")
                        else:
                            mb_done = downloaded / (1024 * 1024)
                            self.progress_signal.emit(50, f"已下载 {mb_done:.1f} MB...")
            self.finished_signal.emit(self.dest_path)
        except Exception as exc:
            self.error_signal.emit(f"下载出错：{exc}")


def _load_messages_cache() -> dict:
    """读取本地 messages_cache.json；若不存在或损坏，则关闭云端开关回退本地文案。"""
    if os.path.exists(MESSAGES_CACHE_FILE):
        try:
            with open(MESSAGES_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"top_enabled": False, "salary_enabled": False}


def _save_messages_cache(data: dict) -> None:
    try:
        merged = dict(data) if isinstance(data, dict) else {}
        if "chat_messages" not in merged and os.path.exists(MESSAGES_CACHE_FILE):
            try:
                with open(MESSAGES_CACHE_FILE, "r", encoding="utf-8") as rf:
                    existing = json.load(rf)
                if isinstance(existing, dict) and isinstance(existing.get("chat_messages"), dict):
                    merged["chat_messages"] = existing["chat_messages"]
            except Exception:
                pass
        with open(MESSAGES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class CloudConfigBridge(QObject):
    """独立后台守护线程拉取云端配置并附带临时账号在线心跳，通过 Qt 信号安全通知主线程。"""

    config_ready = Signal(dict)

    def __init__(self, client_id: str, device_id: str, parent=None):
        super().__init__(parent)
        self._client_id = client_id
        self._device_id = device_id
        self._running = True
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()

    def _fetch_once(self) -> None:
        if not self._running:
            return
        url = f"{CLOUD_API_DOMAIN}/api/messages"
        params = {
            "cid": self._client_id,
            "did": self._device_id,
            "ver": CURRENT_VERSION,
            "os": platform.system(),
            "t": int(time.time() * 1000),
        }
        headers = {
            "User-Agent": f"IdleMeter/{CURRENT_VERSION}",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "close",
        }
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=4)
            if not self._running:
                return
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    _save_messages_cache(data)
                    if self._running:
                        self.config_ready.emit(data)
        except Exception:
            pass

    def start_polling(self, interval_sec: float = 15.0) -> None:
        """启动即刻执行首轮拉取，之后每 interval_sec 秒轮询一次。"""
        def _loop() -> None:
            while self._running:
                self._fetch_once()
                if self._stop_event.wait(interval_sec):
                    break

        threading.Thread(target=_loop, daemon=True).start()

    def fetch_async(self) -> None:
        if not self._running:
            return
        threading.Thread(target=self._fetch_once, daemon=True).start()


class FeedbackSubmitWorker(QThread):
    """后台线程提交用户反馈。"""

    success_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, content: str, contact: str, device_id: str, parent=None):
        super().__init__(parent)
        self.content = content
        self.contact = contact
        self.device_id = device_id

    def run(self) -> None:
        url = f"{CLOUD_API_DOMAIN}/api/feedback"
        headers = {
            "User-Agent": f"IdleMeter/{CURRENT_VERSION}",
            "Content-Type": "application/json",
        }
        payload = {
            "content": self.content,
            "contact": self.contact,
            "device_id": self.device_id,
            "version": CURRENT_VERSION,
            "os": platform.platform(),
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("ok") is True:
                    self.success_signal.emit()
                    return
            self.error_signal.emit(f"提交失败 ({resp.status_code})，请稍后重试")
        except Exception as exc:
            self.error_signal.emit(f"网络异常：{exc}")


class UpdateBadgeButton(QPushButton):
    """支持在右上角绘制醒目小红点徽标的按钮。"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._has_badge = False

    def set_badge(self, visible: bool) -> None:
        if self._has_badge != visible:
            self._has_badge = visible
            self.update()

    def has_badge(self) -> bool:
        return self._has_badge

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._has_badge:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#EF4444"))
            painter.drawEllipse(self.width() - 8, 2, 6, 6)


class SilentUpdateBridge(QObject):
    """后台守护线程静默检测更新（超时 5 秒，异常静默忽略）。"""

    update_found = Signal(dict)

    def check_async(self) -> None:
        def _worker() -> None:
            try:
                info = _fetch_latest_release_info(timeout_sec=5)
                if _parse_version_tuple(info["latest_version"]) > _parse_version_tuple(CURRENT_VERSION):
                    self.update_found.emit(info)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()


class FastDownloadBridge(QObject):
    """后台守护线程执行 4 线程分段极速下载，并通过 Qt 信号安全更新主线程 UI。"""

    progress_signal = Signal(float, str, str, str)
    finished_signal = Signal(str)
    error_signal = Signal(str)
    cancelled_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel_event: threading.Event | None = None
        self._pause_event: threading.Event | None = None
        self._is_downloading = False

    def is_downloading(self) -> bool:
        return self._is_downloading

    def is_paused(self) -> bool:
        return self._is_downloading and self._pause_event is not None and self._pause_event.is_set()

    def set_paused(self, paused: bool) -> None:
        if not self._is_downloading or self._pause_event is None:
            return
        if paused:
            self._pause_event.set()
        else:
            self._pause_event.clear()

    def toggle_pause(self) -> bool:
        if not self._is_downloading or self._pause_event is None:
            return False
        if self._pause_event.is_set():
            self._pause_event.clear()
            return False
        self._pause_event.set()
        return True

    def cancel(self) -> None:
        if self._pause_event is not None:
            self._pause_event.clear()
        if self._cancel_event is not None:
            self._cancel_event.set()

    def start_download(
        self,
        url: str,
        dest_path: str,
        total_bytes: int,
        supports_range: bool,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        if self._is_downloading:
            return
        self._is_downloading = True
        cancel_ev = threading.Event()
        pause_ev = threading.Event()
        self._cancel_event = cancel_ev
        self._pause_event = pause_ev

        def _worker() -> None:
            try:
                final_path = FastDownloader.download_file(
                    url=url,
                    dest_path=dest_path,
                    total_bytes=total_bytes,
                    supports_range=supports_range,
                    cancel_event=cancel_ev,
                    on_progress=lambda pct, spd, sz, td: self.progress_signal.emit(pct, spd, sz, td),
                    pause_event=pause_ev,
                    extra_headers=extra_headers,
                )
                self._is_downloading = False
                self.finished_signal.emit(final_path)
            except InterruptedError:
                self._is_downloading = False
                self.cancelled_signal.emit()
            except Exception as exc:
                self._is_downloading = False
                self.error_signal.emit(str(exc))

        threading.Thread(target=_worker, daemon=True).start()


def _parse_hex_rgb(hex_color: str, fallback: tuple[int, int, int] = (245, 158, 11)) -> tuple[int, int, int]:
    s = str(hex_color or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) == 6:
        try:
            return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        except Exception:
            pass
    return fallback


def generate_app_icon(accent_hex: str, size: int = 64):
    """【方案 A：纯净白底 · IM 律动三柱】动态矢量应用图标（Pillow 4× 超采样 + LANCZOS 抗锯齿渲染）。"""
    from PIL import Image, ImageDraw

    out_size = max(16, int(size))
    scale = 4
    S = out_size * scale
    nearest_filter = Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST
    lanczos_filter = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # 1. 纯净亮白超椭圆底座（Squircle）：四周留 4% 透明安全边距，圆角半径约 24%
    margin = max(1, round(S * 0.04))
    x0, y0 = margin, margin
    x1, y1 = S - margin - 1, S - margin - 1
    bw = float(x1 - x0)
    bh = float(y1 - y0)
    radius = round(S * 0.24)

    # 微垂直渐变：顶部 #FFFFFF -> 底部 #F8FAFC
    grad_col = Image.new("RGBA", (1, S), (0, 0, 0, 0))
    gpix = grad_col.load()
    span_y = max(1.0, float(y1 - y0))
    for y in range(S):
        t = max(0.0, min(1.0, (y - y0) / span_y))
        r = round(255 + (248 - 255) * t)
        g = round(255 + (250 - 255) * t)
        b = round(255 + (252 - 255) * t)
        gpix[0, y] = (r, g, b, 255)
    grad_bg = grad_col.resize((S, S), nearest_filter)

    squircle_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(squircle_mask).rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=255)
    canvas.paste(grad_bg, (0, 0), squircle_mask)

    draw = ImageDraw.Draw(canvas, "RGBA")
    # 1px 按比例极细高质感描边 #E2E8F0（确保在纯白 Win11 任务栏上边界分明）
    stroke_w = max(3, round(S * 0.016))
    draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=radius,
        outline=(226, 232, 240, 255),
        width=stroke_w,
    )

    # 2. IM 律动三柱几何图形（居中对齐，两端全圆角胶囊端头，纯净零多余装饰）
    bar_w = bw * 0.13
    gap = bw * 0.09
    total_w = 3.0 * bar_w + 2.0 * gap
    start_x = (S - total_w) / 2.0
    pill_r = bar_w / 2.0

    # 第 1 根立柱（I，左侧）：高度约 52%，垂直居中，深邃石板灰 #1E293B
    h1 = bh * 0.52
    top1 = (S - h1) / 2.0
    bot1 = top1 + h1
    b1_x0 = start_x
    b1_x1 = b1_x0 + bar_w
    draw.rounded_rectangle(
        [b1_x0, top1, b1_x1, bot1],
        radius=pill_r,
        fill=(30, 41, 59, 255),
    )

    ar, ag, ab = _parse_hex_rgb(accent_hex)

    # 第 2 根立柱（M 左峰，中间）：高度约 38%，与第 1 根立柱底部对齐，填充当前主题强调色
    h2 = bh * 0.38
    bot2 = bot1
    top2 = bot2 - h2
    b2_x0 = b1_x1 + gap
    b2_x1 = b2_x0 + bar_w
    draw.rounded_rectangle(
        [b2_x0, top2, b2_x1, bot2],
        radius=pill_r,
        fill=(ar, ag, ab, 255),
    )

    # 第 3 根立柱（M 右峰，右侧）：高度约 45%，底部对齐，强调色叠加轻微明度过渡增加通透层次感
    h3 = bh * 0.45
    bot3 = bot1
    top3 = bot3 - h3
    b3_x0 = b2_x1 + gap
    b3_x1 = b3_x0 + bar_w
    top_r = min(255, round(ar + (255 - ar) * 0.16))
    top_g = min(255, round(ag + (255 - ag) * 0.16))
    top_b = min(255, round(ab + (255 - ab) * 0.16))

    bar3_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(bar3_mask).rounded_rectangle([b3_x0, top3, b3_x1, bot3], radius=pill_r, fill=255)
    bar3_col = Image.new("RGBA", (1, S), (0, 0, 0, 0))
    b3pix = bar3_col.load()
    span3 = max(1.0, float(bot3 - top3))
    for y in range(max(0, int(top3) - 1), min(S, int(bot3) + 2)):
        t = max(0.0, min(1.0, (y - top3) / span3))
        cr = round(top_r + (ar - top_r) * t)
        cg = round(top_g + (ag - top_g) * t)
        cb = round(top_b + (ab - top_b) * t)
        b3pix[0, y] = (cr, cg, cb, 255)
    bar3_grad = bar3_col.resize((S, S), nearest_filter)
    canvas.paste(bar3_grad, (0, 0), bar3_mask)

    return canvas.resize((out_size, out_size), lanczos_filter)


def _pil_rgba_to_qpixmap(pil_img, device_pixel_ratio: float = 1.0) -> QPixmap:
    rgba = pil_img.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()
    pm = QPixmap.fromImage(qimg)
    if device_pixel_ratio > 1.0:
        pm.setDevicePixelRatio(device_pixel_ratio)
    return pm


def _build_app_qicon(accent_hex: str, sizes: tuple[int, ...] = (16, 32, 64)) -> QIcon:
    """生成包含 16x16 / 32x32 / 64x64 多分辨率位图的动态矢量 QIcon，适配托盘、任务栏与窗口标题栏。"""
    qicon = QIcon()
    for sz in sizes:
        qicon.addPixmap(_pil_rgba_to_qpixmap(generate_app_icon(accent_hex, size=sz)))
    return qicon


def _build_app_qpixmap(accent_hex: str, size: int = 64, hidpi: bool = True) -> QPixmap:
    """生成用于标题栏 / 关于弹窗名片的高清 QPixmap。"""
    if hidpi:
        return _pil_rgba_to_qpixmap(generate_app_icon(accent_hex, size=size * 2), device_pixel_ratio=2.0)
    return _pil_rgba_to_qpixmap(generate_app_icon(accent_hex, size=size))


def _make_grayscale_mode_icon(kind: str, color_hex: str) -> QIcon:
    """绘制纯灰阶单色线条模式切换图标（16x16 @2x）。"""
    pm = QPixmap(32, 32)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color_hex), 1.45, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "fish":
        # 简洁单色鱼形线条
        p.drawEllipse(QRectF(2.2, 4.4, 8.6, 7.2))
        tail = QPolygonF([QPointF(10.6, 8.0), QPointF(13.8, 5.2), QPointF(13.8, 10.8)])
        p.drawPolygon(tail)
        p.setBrush(QBrush(QColor(color_hex)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(4.8, 7.4), 0.9, 0.9)
    else:
        # 简洁单色公文包线条（工作模式）
        p.drawRoundedRect(QRectF(2.4, 5.2, 11.2, 8.0), 1.8, 1.8)
        p.drawRoundedRect(QRectF(5.6, 3.0, 4.8, 2.2), 0.9, 0.9)
        p.drawLine(QPointF(2.8, 8.6), QPointF(13.2, 8.6))
    p.end()
    return QIcon(pm)


def _make_proxy_shield_pixmap(color_hex: str, size: int = 28) -> QPixmap:
    """绘制高清晰度圆润矢量盾牌警告图标（用于互联网模式 TUN/代理拦截卡片）。"""
    dpr = 2.0
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    col = QColor(color_hex)
    fill_col = QColor(col)
    fill_col.setAlpha(30)

    # 居中矢量盾牌轮廓（基于 28x28 坐标系缩放）
    s = size / 28.0
    path = QPainterPath()
    path.moveTo(14.0 * s, 2.8 * s)
    path.cubicTo(18.0 * s, 4.6 * s, 21.4 * s, 5.2 * s, 23.4 * s, 5.6 * s)
    path.lineTo(23.4 * s, 13.4 * s)
    path.cubicTo(23.4 * s, 19.2 * s, 19.5 * s, 23.1 * s, 14.0 * s, 25.2 * s)
    path.cubicTo(8.5 * s, 23.1 * s, 4.6 * s, 19.2 * s, 4.6 * s, 13.4 * s)
    path.lineTo(4.6 * s, 5.6 * s)
    path.cubicTo(6.6 * s, 5.2 * s, 10.0 * s, 4.6 * s, 14.0 * s, 2.8 * s)
    path.closeSubpath()

    p.setBrush(QBrush(fill_col))
    p.setPen(QPen(col, 1.85 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPath(path)

    # 内部居中感叹号
    p.setPen(QPen(col, 2.0 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(14.0 * s, 9.4 * s), QPointF(14.0 * s, 15.4 * s))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(col))
    p.drawEllipse(QPointF(14.0 * s, 18.8 * s), 1.25 * s, 1.25 * s)
    p.end()
    return pm


def _make_tool_vector_icon(kind: str, color_hex: str) -> QIcon:
    """绘制简约单色矢量线条图标（16x16 @2x）：支持 ocr / picker / wifi / globe。"""
    pm = QPixmap(32, 32)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    col = QColor(color_hex)
    pen = QPen(col, 1.45, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "ocr":
        # 简约扫描四角框 + 内部文字线条
        c = 3.0
        # 左上
        p.drawLine(QPointF(2.4, 2.4 + c), QPointF(2.4, 2.4))
        p.drawLine(QPointF(2.4, 2.4), QPointF(2.4 + c, 2.4))
        # 右上
        p.drawLine(QPointF(13.6 - c, 2.4), QPointF(13.6, 2.4))
        p.drawLine(QPointF(13.6, 2.4), QPointF(13.6, 2.4 + c))
        # 左下
        p.drawLine(QPointF(2.4, 13.6 - c), QPointF(2.4, 13.6))
        p.drawLine(QPointF(2.4, 13.6), QPointF(2.4 + c, 13.6))
        # 右下
        p.drawLine(QPointF(13.6 - c, 13.6), QPointF(13.6, 13.6))
        p.drawLine(QPointF(13.6, 13.6), QPointF(13.6, 13.6 - c))
        # 内部两行极简文字线
        p.drawLine(QPointF(5.0, 6.6), QPointF(11.0, 6.6))
        p.drawLine(QPointF(5.0, 9.6), QPointF(9.2, 9.6))
    elif kind == "picker":
        # 简约取色准星圆环 + 中心采样点
        p.drawEllipse(QRectF(3.5, 3.5, 9.0, 9.0))
        p.drawLine(QPointF(8.0, 1.8), QPointF(8.0, 3.5))
        p.drawLine(QPointF(8.0, 12.5), QPointF(8.0, 14.2))
        p.drawLine(QPointF(1.8, 8.0), QPointF(3.5, 8.0))
        p.drawLine(QPointF(12.5, 8.0), QPointF(14.2, 8.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(col))
        p.drawEllipse(QPointF(8.0, 8.0), 1.4, 1.4)
    elif kind == "wifi":
        # 简约 Wi-Fi 三重扇形信号弧 + 底部圆点
        p.drawArc(QRectF(1.6, 3.6, 12.8, 12.8), 45 * 16, 90 * 16)
        p.drawArc(QRectF(3.8, 5.8, 8.4, 8.4), 45 * 16, 90 * 16)
        p.drawArc(QRectF(5.9, 8.0, 4.2, 4.2), 45 * 16, 90 * 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(col))
        p.drawEllipse(QPointF(8.0, 12.6), 1.1, 1.1)
    elif kind == "globe":
        # 简约互联网经纬球体
        p.drawEllipse(QRectF(2.2, 2.2, 11.6, 11.6))
        p.drawEllipse(QRectF(5.4, 2.2, 5.2, 11.6))
        p.drawLine(QPointF(2.4, 8.0), QPointF(13.6, 8.0))
        thin_pen = QPen(col, 1.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(thin_pen)
        p.drawLine(QPointF(3.6, 5.1), QPointF(12.4, 5.1))
        p.drawLine(QPointF(3.6, 10.9), QPointF(12.4, 10.9))
    elif kind == "emoji":
        # 简约笑脸表情图标
        p.drawEllipse(QRectF(2.2, 2.2, 11.6, 11.6))
        p.drawArc(QRectF(5.0, 6.2, 6.0, 5.0), 205 * 16, 130 * 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(col))
        p.drawEllipse(QPointF(6.0, 6.8), 0.9, 0.9)
        p.drawEllipse(QPointF(10.0, 6.8), 0.9, 0.9)
    elif kind == "folder":
        # 简约文件夹图标
        p.drawRoundedRect(QRectF(2.0, 4.6, 12.0, 8.8), 1.6, 1.6)
        p.drawLine(QPointF(2.4, 4.6), QPointF(3.4, 2.8))
        p.drawLine(QPointF(3.4, 2.8), QPointF(6.8, 2.8))
        p.drawLine(QPointF(6.8, 2.8), QPointF(8.0, 4.6))
    elif kind == "scissors":
        # 简约截图剪刀图标
        p.drawEllipse(QRectF(2.2, 9.6, 3.6, 3.6))
        p.drawEllipse(QRectF(2.2, 2.8, 3.6, 3.6))
        p.drawLine(QPointF(5.4, 5.5), QPointF(13.4, 11.8))
        p.drawLine(QPointF(5.4, 10.5), QPointF(13.4, 4.2))
    elif kind == "voice_wave":
        # 简约声波图标
        p.drawArc(QRectF(3.2, 5.0, 6.0, 6.0), -45 * 16, 90 * 16)
        p.drawArc(QRectF(1.2, 3.0, 10.0, 10.0), -45 * 16, 90 * 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(col))
        p.drawEllipse(QPointF(4.2, 8.0), 1.1, 1.1)
    elif kind == "gear":
        # 简约齿轮图标（自定义隧道高级配置）
        p.drawEllipse(QRectF(5.2, 5.2, 5.6, 5.6))
        for deg in range(0, 360, 45):
            rad = math.radians(deg)
            x1 = 8.0 + math.cos(rad) * 4.4
            y1 = 8.0 + math.sin(rad) * 4.4
            x2 = 8.0 + math.cos(rad) * 6.0
            y2 = 8.0 + math.sin(rad) * 6.0
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    elif kind == "popout_window":
        # 精致外弹独立窗口图标（类似 ⧉ 外弹窗口）
        p.drawRoundedRect(QRectF(2.2, 4.6, 8.8, 9.0), 1.8, 1.8)
        p.drawLine(QPointF(2.2, 7.2), QPointF(11.0, 7.2))
        p.drawLine(QPointF(8.6, 2.4), QPointF(13.6, 2.4))
        p.drawLine(QPointF(13.6, 2.4), QPointF(13.6, 7.4))
        p.drawLine(QPointF(8.4, 7.6), QPointF(13.4, 2.6))
    elif kind == "clock_off":
        # 下班倒计时极简时钟图标
        p.drawEllipse(QRectF(2.2, 2.2, 11.6, 11.6))
        p.drawLine(QPointF(8.0, 5.0), QPointF(8.0, 8.2))
        p.drawLine(QPointF(8.0, 8.2), QPointF(10.6, 9.6))
    elif kind == "weekend_sun":
        # 周末/休假极简太阳图标
        p.drawEllipse(QRectF(5.0, 5.0, 6.0, 6.0))
        for deg in range(0, 360, 45):
            rad = math.radians(deg)
            p.drawLine(
                QPointF(8.0 + math.cos(rad) * 4.5, 8.0 + math.sin(rad) * 4.5),
                QPointF(8.0 + math.cos(rad) * 6.1, 8.0 + math.sin(rad) * 6.1),
            )
    elif kind == "payday_coin":
        # 发薪日极简金币 ¥ 图标
        p.drawEllipse(QRectF(2.2, 2.2, 11.6, 11.6))
        p.drawLine(QPointF(6.0, 5.2), QPointF(8.0, 7.8))
        p.drawLine(QPointF(10.0, 5.2), QPointF(8.0, 7.8))
        p.drawLine(QPointF(8.0, 7.8), QPointF(8.0, 11.4))
        p.drawLine(QPointF(5.8, 8.4), QPointF(10.2, 8.4))
        p.drawLine(QPointF(6.2, 10.1), QPointF(9.8, 10.1))

    p.end()
    return QIcon(pm)


_AVATAR_PIXMAP_CACHE: dict[tuple[int, int], QPixmap] = {}


def _make_pillow_device_avatar(avatar_idx: int, size: int = 30) -> QPixmap:
    """使用 Pillow 绘制 6 款简约高级双色几何头像（0=电脑端，1..5=多部手机端专属配色与几何徽标）。"""
    idx = max(0, min(5, int(avatar_idx)))
    key = (idx, int(size))
    cached = _AVATAR_PIXMAP_CACHE.get(key)
    if cached is not None:
        return cached

    palettes = [
        ("#2B3345", "#F8FAFC", "#60A5FA"),  # 0: 电脑端 (深岩蓝)
        ("#10B981", "#FFFFFF", "#A7F3D0"),  # 1: 手机端-1 (翡翠绿)
        ("#3B82F6", "#FFFFFF", "#BFDBFE"),  # 2: 手机端-2 (钴蓝)
        ("#8B5CF6", "#FFFFFF", "#DDD6FE"),  # 3: 手机端-3 (星云紫)
        ("#F59E0B", "#FFFFFF", "#FEF3C7"),  # 4: 手机端-4 (琥珀金)
        ("#EC4899", "#FFFFFF", "#FBCFE8"),  # 5: 手机端-5 (玫瑰粉)
    ]
    bg_hex, fg_hex, acc_hex = palettes[idx]

    try:
        from PIL import Image, ImageDraw

        scale = 4
        s = size * scale
        im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        r = int(s * 0.26)
        d.rounded_rectangle((2, 2, s - 3, s - 3), radius=r, fill=bg_hex)

        lw = max(2, int(s * 0.055))
        if idx == 0:
            # 桌面显示器简约几何造型
            d.rounded_rectangle(
                (int(s * 0.20), int(s * 0.23), int(s * 0.80), int(s * 0.62)),
                radius=int(s * 0.06),
                outline=fg_hex,
                width=lw,
            )
            # 支架与底座
            cx = s // 2
            d.line((cx, int(s * 0.62), cx, int(s * 0.74)), fill=fg_hex, width=lw)
            d.line((int(s * 0.34), int(s * 0.76), int(s * 0.66), int(s * 0.76)), fill=fg_hex, width=lw)
            # 屏幕中心几何点缀圆点
            dot_r = int(s * 0.06)
            d.ellipse((cx - dot_r, int(s * 0.425) - dot_r, cx + dot_r, int(s * 0.425) + dot_r), fill=acc_hex)
        else:
            # 智能手机简约几何造型 + 5 种不同屏幕几何标识
            d.rounded_rectangle(
                (int(s * 0.30), int(s * 0.17), int(s * 0.70), int(s * 0.83)),
                radius=int(s * 0.08),
                outline=fg_hex,
                width=lw,
            )
            # 听筒细线与底部圆点
            d.line((int(s * 0.43), int(s * 0.25), int(s * 0.57), int(s * 0.25)), fill=acc_hex, width=max(2, lw - 1))
            cx = s // 2
            dr = int(s * 0.036)
            d.ellipse((cx - dr, int(s * 0.74) - dr, cx + dr, int(s * 0.74) + dr), fill=fg_hex)

            # 按 1..5 区分屏幕内简约几何符号
            cy = int(s * 0.49)
            if idx == 1:
                mr = int(s * 0.065)
                d.ellipse((cx - mr, cy - mr, cx + mr, cy + mr), fill=acc_hex)
            elif idx == 2:
                d.line((int(s * 0.40), cy - int(s * 0.04), int(s * 0.60), cy - int(s * 0.04)), fill=acc_hex, width=max(2, lw - 1))
                d.line((int(s * 0.43), cy + int(s * 0.05), int(s * 0.57), cy + int(s * 0.05)), fill=acc_hex, width=max(2, lw - 1))
            elif idx == 3:
                md = int(s * 0.075)
                d.polygon([(cx, cy - md), (cx + md, cy), (cx, cy + md), (cx - md, cy)], fill=acc_hex)
            elif idx == 4:
                md = int(s * 0.07)
                d.rounded_rectangle((cx - md, cy - md, cx + md, cy + md), radius=int(s * 0.02), fill=acc_hex)
            else:
                md = int(s * 0.075)
                d.ellipse((cx - md, cy - md, cx + md, cy + md), outline=acc_hex, width=max(2, lw - 1))

        resamp = getattr(getattr(Image, "Resampling", Image), "LANCZOS", getattr(Image, "LANCZOS", 1))
        im = im.resize((size * 2, size * 2), resamp)
        raw = im.tobytes("raw", "RGBA")
        qimg = QImage(raw, im.width, im.height, QImage.Format.Format_RGBA8888).copy()
        pm = QPixmap.fromImage(qimg)
        pm.setDevicePixelRatio(2.0)
        _AVATAR_PIXMAP_CACHE[key] = pm
        return pm
    except Exception:
        pm = QPixmap(size, size)
        pm.fill(QColor(bg_hex))
        _AVATAR_PIXMAP_CACHE[key] = pm
        return pm


def _make_clip_type_icon(kind: str, color_hex: str) -> QIcon:
    """绘制复制历史条目类型单色小图标（14x14 @2x）。"""
    pm = QPixmap(28, 28)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color_hex), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "link":
        p.drawRoundedRect(QRectF(2.0, 5.0, 5.8, 4.0), 1.8, 1.8)
        p.drawRoundedRect(QRectF(6.2, 5.0, 5.8, 4.0), 1.8, 1.8)
    elif kind == "file":
        p.drawRoundedRect(QRectF(3.0, 2.2, 8.0, 9.6), 1.2, 1.2)
        p.drawLine(QPointF(5.0, 5.2), QPointF(9.0, 5.2))
        p.drawLine(QPointF(5.0, 7.6), QPointF(9.0, 7.6))
    elif kind == "image":
        p.drawRoundedRect(QRectF(2.2, 3.0, 9.6, 8.0), 1.2, 1.2)
        p.drawEllipse(QPointF(5.0, 5.6), 0.9, 0.9)
        p.drawPolyline([QPointF(3.2, 9.6), QPointF(6.0, 7.0), QPointF(8.0, 8.6), QPointF(9.4, 7.6), QPointF(10.8, 9.6)])
    else:
        p.drawLine(QPointF(2.6, 4.0), QPointF(11.4, 4.0))
        p.drawLine(QPointF(2.6, 7.0), QPointF(11.4, 7.0))
        p.drawLine(QPointF(2.6, 10.0), QPointF(8.4, 10.0))
    p.end()
    return QIcon(pm)


def _collapse_clip_preview_text(raw_text: str) -> str:
    """将粘贴板原始文本中的换行/制表符折叠为单空格并去除首尾空白，避免撑变形。"""
    return re.sub(r"[\r\n\t]+", " ", str(raw_text or "")).strip()


class _ClipHoverPreviewPopup(QWidget):
    """粘贴板悬停完整内容预览悬浮窗：250ms 延迟触发、主题配色同步、320px 自动换行、屏幕边缘防溢出。"""

    MAX_PREVIEW_CHARS = 800
    HOVER_DELAY_MS = 250

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._is_light = False
        self._pending_text = ""
        self._pending_anchor: QWidget | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        self._label = QLabel(self)
        self._label.setFont(get_source_han_font(8))
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(320)
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._label)

        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.setInterval(self.HOVER_DELAY_MS)
        self._delay_timer.timeout.connect(self._show_pending)
        self._apply_colors()

    def set_light_mode(self, is_light: bool) -> None:
        self._is_light = bool(is_light)
        self._apply_colors()

    def _apply_colors(self) -> None:
        fg = "#1D1E22" if self._is_light else "#F0F0F5"
        self._label.setStyleSheet(f"color: {fg}; background: transparent; border: none;")
        self.update()

    @classmethod
    def format_display_text(cls, full_text: str) -> str:
        text = str(full_text or "").strip()
        if len(text) > cls.MAX_PREVIEW_CHARS:
            return f"{text[:cls.MAX_PREVIEW_CHARS]}\n\n……（共 {len(text)} 字，已预览前 {cls.MAX_PREVIEW_CHARS} 字）"
        return text

    def schedule_show(self, full_text: str, anchor: QWidget) -> None:
        cleaned = str(full_text or "").strip()
        if not cleaned:
            self.cancel_and_hide()
            return
        self._pending_text = cleaned
        self._pending_anchor = anchor
        self._delay_timer.start(self.HOVER_DELAY_MS)

    def cancel_and_hide(self) -> None:
        self._delay_timer.stop()
        self._pending_text = ""
        self._pending_anchor = None
        if self.isVisible():
            self.hide()

    def _show_pending(self) -> None:
        anchor = self._pending_anchor
        text = self._pending_text
        if not text or anchor is None:
            return
        try:
            if not anchor.isVisible():
                return
        except RuntimeError:
            self.cancel_and_hide()
            return

        global_pos = QCursor.pos()
        self.show_at(text, global_pos)

    def show_at(self, full_text: str, global_pos: QPoint) -> None:
        display_text = self.format_display_text(full_text)
        if not display_text:
            self.hide()
            return
        self._label.setText(display_text)
        self._label.adjustSize()
        self.adjustSize()

        w = self.width()
        h = self.height()
        x = global_pos.x() + 12
        y = global_pos.y() + 16

        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            if x + w > avail.right() - 6:
                x = global_pos.x() - w - 12
            if y + h > avail.bottom() - 6:
                y = global_pos.y() - h - 12
            x = max(avail.left() + 6, min(x, max(avail.left() + 6, avail.right() - w - 6)))
            y = max(avail.top() + 6, min(y, max(avail.top() + 6, avail.bottom() - h - 6)))

        self.move(int(x), int(y))
        self.show()
        self.raise_()

    def eventFilter(self, obj, event) -> bool:
        try:
            if event.type() in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.Wheel,
                QEvent.Type.WindowDeactivate,
            ):
                if self.isVisible() or self._delay_timer.isActive():
                    self.cancel_and_hide()
        except RuntimeError:
            return False
        return False

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#FFFFFF") if self._is_light else QColor("#1E1E25")
        border = QColor("#DCDFE6") if self._is_light else QColor("#32323E")

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 10.0, 10.0)
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, 1.0))
        painter.drawPath(path)
        painter.end()


class _ClipPreviewLabel(QLabel):
    """粘贴板单行防挤压预览标签：强制 Ignored 水平策略防止挤压右侧按钮，按实际像素宽度动态截断省略号，并绑定 250ms 悬停完整预览。"""

    def __init__(
        self,
        raw_preview: str,
        full_text: str,
        enable_hover: bool,
        hover_popup: _ClipHoverPreviewPopup | None,
        fallback_width: int = 124,
        parent=None,
    ):
        super().__init__(parent)
        self._single_line = _collapse_clip_preview_text(raw_preview)
        self._full_text = str(full_text or "")
        self._enable_hover = bool(enable_hover and self._full_text.strip())
        self._hover_popup = hover_popup
        self._fallback_width = max(40, int(fallback_width))

        self.setWordWrap(False)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(22)

    def update_elided_text(self, avail_px: int | None = None) -> None:
        w = avail_px if (avail_px is not None and avail_px > 20) else (self.width() if self.width() > 20 else self._fallback_width)
        fm = QFontMetrics(self.font())
        self.setText(fm.elidedText(self._single_line, Qt.TextElideMode.ElideRight, max(20, w - 2)))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_elided_text(self.width())

    def enterEvent(self, event) -> None:
        if self._enable_hover and self._hover_popup is not None:
            self._hover_popup.schedule_show(self._full_text, self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._hover_popup is not None:
            self._hover_popup.cancel_and_hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if self._hover_popup is not None:
            self._hover_popup.cancel_and_hide()
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:
        if self._hover_popup is not None:
            self._hover_popup.cancel_and_hide()
        super().wheelEvent(event)


class ClipboardWatcherBridge(QObject):
    """后台守护线程每 0.6s 轮询 Windows 剪贴板序列号，变化时通知主线程读取。"""

    clipboard_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_event = threading.Event()
        self._skip_lock = threading.Lock()
        self._skip_next = False
        self._last_seq = self._get_seq()
        self._thread: threading.Thread | None = None

    @staticmethod
    def _get_seq() -> int:
        try:
            return int(ctypes.windll.user32.GetClipboardSequenceNumber())
        except Exception:
            return 0

    def mark_self_write(self) -> None:
        with self._skip_lock:
            self._skip_next = True

    def sync_sequence(self) -> None:
        with self._skip_lock:
            self._last_seq = self._get_seq()
            self._skip_next = False

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._last_seq = self._get_seq()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(0.6)
            if self._stop_event.is_set():
                break
            seq = self._get_seq()
            if seq == 0 or seq == self._last_seq:
                continue
            with self._skip_lock:
                self._last_seq = seq
                if self._skip_next:
                    self._skip_next = False
                    continue
            self.clipboard_changed.emit()


class ClipboardHistoryStore:
    """复制历史持久化与缓存图片管理（最多保留 100 条）。"""

    MAX_ITEMS = 100
    HISTORY_FILE = os.path.join(BASE_DIR, "clipboard_history.json")
    CACHE_DIR = os.path.join(BASE_DIR, "clipboard_cache")

    @classmethod
    def set_root_dir(cls, root_dir: str) -> None:
        if root_dir:
            cls.HISTORY_FILE = os.path.join(root_dir, "clipboard_history.json")
            cls.CACHE_DIR = os.path.join(root_dir, "clipboard_cache")

    @classmethod
    def ensure_cache_dir(cls) -> None:
        os.makedirs(cls.CACHE_DIR, exist_ok=True)

    @classmethod
    def _remove_image_file(cls, entry: dict) -> None:
        img_path = str(entry.get("image_path") or "")
        if img_path and os.path.isfile(img_path):
            try:
                os.remove(img_path)
            except Exception:
                pass

    @classmethod
    def prune_non_today(cls, items: list[dict]) -> tuple[list[dict], bool]:
        today_str = datetime.now().strftime("%Y-%m-%d")
        kept: list[dict] = []
        changed = False
        for it in items:
            if it.get("date_str") == today_str:
                kept.append(it)
            else:
                cls._remove_image_file(it)
                changed = True
        return kept, changed

    @classmethod
    def load(cls, keep_next_day: bool) -> list[dict]:
        items: list[dict] = []
        if os.path.isfile(cls.HISTORY_FILE):
            try:
                with open(cls.HISTORY_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    items = [x for x in raw if isinstance(x, dict)]
            except Exception:
                items = []
        if not keep_next_day:
            items, changed = cls.prune_non_today(items)
            if changed:
                cls.save(items)
        return items[: cls.MAX_ITEMS]

    @classmethod
    def save(cls, items: list[dict]) -> None:
        try:
            with open(cls.HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(items[: cls.MAX_ITEMS], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def clear_all(cls, items: list[dict]) -> list[dict]:
        for it in items:
            cls._remove_image_file(it)
        if os.path.isdir(cls.CACHE_DIR):
            for fn in os.listdir(cls.CACHE_DIR):
                fp = os.path.join(cls.CACHE_DIR, fn)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
        cls.save([])
        return []

    @classmethod
    def add_or_bump(cls, items: list[dict], entry: dict) -> list[dict]:
        etype = entry.get("type")
        filtered: list[dict] = []
        for it in items:
            same = False
            if it.get("type") == etype:
                if etype in ("text", "link"):
                    same = it.get("content") == entry.get("content")
                elif etype == "image":
                    same = bool(entry.get("image_hash")) and it.get("image_hash") == entry.get("image_hash")
                elif etype == "file":
                    if entry.get("image_hash") and it.get("image_hash") == entry.get("image_hash"):
                        same = True
                    else:
                        same = it.get("file_paths") == entry.get("file_paths")
            if same:
                if entry.get("image_path") and it.get("image_path") != entry.get("image_path"):
                    cls._remove_image_file(it)
                continue
            filtered.append(it)
        result = [entry] + filtered
        if len(result) > cls.MAX_ITEMS:
            for evicted in result[cls.MAX_ITEMS :]:
                cls._remove_image_file(evicted)
            result = result[: cls.MAX_ITEMS]
        cls.save(result)
        return result


class GlobalButtonPressFeedbackFilter(QObject):
    """全局按钮按压态微动效过滤器：统一监听全站按钮鼠标按下/松开，触发图标微缩与按压态刷新。"""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        et = event.type()
        if et == QEvent.Type.MouseButtonPress and isinstance(watched, QPushButton):
            try:
                if getattr(event, "button", lambda: None)() == Qt.MouseButton.LeftButton and watched.isEnabled():
                    watched.setProperty("_im_pressed", True)
                    ico = watched.icon()
                    if ico is not None and not ico.isNull():
                        orig_sz = watched.property("_im_orig_icon_sz")
                        if orig_sz is None:
                            orig_sz = watched.iconSize()
                            watched.setProperty("_im_orig_icon_sz", orig_sz)
                        if isinstance(orig_sz, QSize) and orig_sz.width() > 6:
                            watched.setIconSize(QSize(max(6, orig_sz.width() - 1), max(6, orig_sz.height() - 1)))
                    watched.update()
            except RuntimeError:
                pass
        elif et in (QEvent.Type.MouseButtonRelease, QEvent.Type.Leave) and isinstance(watched, QPushButton):
            try:
                if watched.property("_im_pressed"):
                    watched.setProperty("_im_pressed", False)
                    orig_sz = watched.property("_im_orig_icon_sz")
                    if isinstance(orig_sz, QSize) and orig_sz.width() > 0:
                        watched.setIconSize(orig_sz)
                    watched.update()
            except RuntimeError:
                pass
        return super().eventFilter(watched, event)


class HamburgerMenuButton(QPushButton):
    """版本号右侧三条圆头横线菜单按钮（QPainter RoundCap + 5px 右上角小红点）。"""

    def __init__(self, parent=None, accent_color: str = "#FF6B00"):
        super().__init__("", parent)
        self.setFixedSize(24, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._accent = QColor(accent_color)
        self._line_color = QColor("#8B8C98")
        self._hover_bg = QColor("#232329")
        self._hovered = False
        self._has_badge = False

    def set_theme_colors(self, line_hex: str, accent_hex: str, hover_bg_hex: str) -> None:
        self._line_color = QColor(line_hex)
        self._accent = QColor(accent_hex)
        self._hover_bg = QColor(hover_bg_hex)
        self.update()

    def set_badge(self, visible: bool) -> None:
        if self._has_badge != bool(visible):
            self._has_badge = bool(visible)
            self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pressed = self.isDown()
        if pressed:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._hover_bg.darker(112))
            p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0), 6.0, 6.0)
        elif self._hovered:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._hover_bg)
            p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0), 6.0, 6.0)

        if pressed:
            cx, cy = self.width() / 2.0, self.height() / 2.0
            p.translate(cx, cy + 0.6)
            p.scale(0.92, 0.92)
            p.translate(-cx, -cy)

        color = self._accent if (self._hovered or pressed) else self._line_color
        pen = QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for y in (6.5, 11.0, 15.5):
            p.drawLine(QPointF(5.5, y), QPointF(18.5, y))

        if self._has_badge:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#EF4444"))
            p.drawEllipse(QRectF(16.5, 2.0, 5.0, 5.0))
        p.end()


class ChangelogHoverCard(QFrame):
    """版本号旁侧边更新日志悬浮预览卡片（支持鼠标滚轮滚动，随主题自适应）。"""

    DEFAULT_CHANGELOG_TEXT = (
        "• 界面精修：顶部栏紧凑布局、时间日期居中排布、底部滚动状态栏；\n"
        "• 连接手机：支持局域网与公网跨网互传、右键复制网址及代理/TUN前置检测；\n"
        "• 文件快传：拖入文件或文件夹生成单次有效高速直链（15分钟自动过期）；\n"
        "• 效率工具：内置 6 线程分片下载、剪贴板历史、截图识字与屏幕取色。"
    )

    hovered_changed = Signal(bool)

    def __init__(self, version: str, changelog: str, theme_mode: str, accent_color: str, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._is_light = theme_mode == "light"
        self.setFixedSize(244, 188)

        bg = "#F5F6F8" if self._is_light else "#1E1E24"
        border = "#DCDFE6" if self._is_light else "#2E2E38"
        fg = "#1D1E22" if self._is_light else "#F5F5F7"
        muted = "#6E707A" if self._is_light else "#9A9AA6"
        scroll_handle = "#C5C8D4" if self._is_light else "#3A3A46"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(self)
        card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 10px; }}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 10, 10, 10)
        cl.setSpacing(6)

        title = QLabel(f"更新日志 · v{version}", card)
        title.setFont(get_source_han_font(9, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {accent_color}; border: none;")
        cl.addWidget(title)

        scroll = QScrollArea(card)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 4px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: {scroll_handle}; min-height: 20px; border-radius: 2px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            """
        )
        body_text = (changelog or "").strip() or self.DEFAULT_CHANGELOG_TEXT
        body = QLabel(body_text, scroll)
        body.setFont(get_source_han_font(8))
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body.setStyleSheet(f"color: {fg if not self._is_light else muted}; border: none; background: transparent;")
        scroll.setWidget(body)
        cl.addWidget(scroll, 1)

        outer.addWidget(card)

    def enterEvent(self, event) -> None:
        self.hovered_changed.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered_changed.emit(False)
        super().leaveEvent(event)


class VersionMenuPopup(QFrame):
    """版本号菜单下拉浮动框（随系统主题自适应，失焦自动关闭）。"""

    action_triggered = Signal(str)

    def __init__(
        self,
        theme_mode: str,
        accent_color: str,
        changelog_ver: str = "",
        changelog_text: str = "",
        parent=None,
    ):
        super().__init__(
            parent,
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._is_light = theme_mode == "light"
        self._accent = accent_color
        self._theme_mode = theme_mode

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        text_fg = "#1D1E22" if self._is_light else "#F5F5F7"
        hover_bg = "#ECEDF2" if self._is_light else "#2A2A34"
        press_bg = "#DCE0EA" if self._is_light else "#343442"
        item_qss = f"""
            QPushButton {{
                background: transparent;
                color: {text_fg};
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                color: {accent_color};
            }}
            QPushButton:pressed {{
                background-color: {press_bg};
                color: {accent_color};
                padding-top: 7px;
            }}
        """

        for key, label in (
            ("feedback", "反馈"),
            ("update", "版本更新"),
            ("download_link", "下载链接"),
            ("cache", "缓存文件"),
            ("about", "关于"),
        ):
            btn = QPushButton(label, self)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(get_source_han_font(9))
            btn.setMinimumWidth(104)
            btn.setStyleSheet(item_qss)
            btn.clicked.connect(lambda checked=False, k=key: self._on_item_clicked(k))
            layout.addWidget(btn)

        self.adjustSize()

    def _on_item_clicked(self, key: str) -> None:
        self.close()
        self.action_triggered.emit(key)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#FFFFFF") if self._is_light else QColor("#1E1E24")
        border = QColor("#DCDFE6") if self._is_light else QColor("#2E2E38")
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(border, 1.0))
        p.drawRoundedRect(rect, 10.0, 10.0)
        p.end()


class AboutDialog(QDialog):
    """非模态【关于】品牌名片弹窗（展示 72x72 动态矢量图标、同行品牌名与版本号胶囊，悬停版本号弹出更新日志浮窗）。"""

    def __init__(
        self,
        config: AppConfig,
        changelog_ver: str = "",
        changelog_text: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._config = config
        self._changelog_ver = changelog_ver or CURRENT_VERSION
        self._changelog_text = changelog_text
        self._hover_card: ChangelogHoverCard | None = None
        self._ver_pill_hovered = False
        self._card_hovered = False
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._check_hide_hover_card)
        self._drag_pos: QPoint | None = None
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle(f"关于 {APP_BRAND_NAME}")
        self.setFixedWidth(MAIN_WIDTH)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card = QFrame(self)
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(16, 10, 16, 16)
        cl.setSpacing(0)
        cl.setAlignment(Qt.AlignmentFlag.AlignTop)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)
        self._lbl_header = QLabel(f"关于 {APP_BRAND_NAME}", self._card)
        self._lbl_header.setFont(get_source_han_font(10, QFont.Weight.Bold))
        self._lbl_header.setFixedHeight(22)

        self._btn_min = QPushButton("—", self._card)
        self._btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_min.setFixedSize(22, 22)
        self._btn_min.setToolTip("最小化")
        self._btn_min.clicked.connect(self.showMinimized)

        self._btn_close = QPushButton("✕", self._card)
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.setFixedSize(22, 22)
        self._btn_close.clicked.connect(self.close)

        top.addWidget(self._lbl_header)
        top.addStretch(1)
        top.addWidget(self._btn_min)
        top.addWidget(self._btn_close)
        cl.addLayout(top)
        cl.addSpacing(6)

        # 居中 72x72 动态矢量名片图标
        icon_row = QHBoxLayout()
        icon_row.setContentsMargins(0, 0, 0, 0)
        icon_row.setSpacing(0)
        icon_row.addStretch(1)
        self._lbl_icon = QLabel(self._card)
        self._lbl_icon.setFixedSize(72, 72)
        self._lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_row.addWidget(self._lbl_icon)
        icon_row.addStretch(1)
        cl.addLayout(icon_row)
        cl.addSpacing(8)

        # 英文名称 IdleMeter 与浅绿色版本号胶囊同行紧凑排布（悬停版本号弹出更新日志）
        brand_ver_row = QHBoxLayout()
        brand_ver_row.setContentsMargins(0, 0, 0, 0)
        brand_ver_row.setSpacing(6)
        brand_ver_row.addStretch(1)

        self._lbl_brand = QLabel(APP_BRAND_NAME, self._card)
        self._lbl_brand.setFont(get_source_han_font(11, QFont.Weight.Bold))
        self._lbl_brand.setFixedHeight(20)
        self._lbl_brand.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self._lbl_brand.setWordWrap(False)

        self._lbl_ver_pill = QLabel(f"v{CURRENT_VERSION}", self._card)
        self._lbl_ver_pill.setFont(get_source_han_font(7, QFont.Weight.Bold))
        self._lbl_ver_pill.setFixedHeight(18)
        self._lbl_ver_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_ver_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lbl_ver_pill.installEventFilter(self)

        brand_ver_row.addWidget(self._lbl_brand, 0, Qt.AlignmentFlag.AlignVCenter)
        brand_ver_row.addWidget(self._lbl_ver_pill, 0, Qt.AlignmentFlag.AlignVCenter)
        brand_ver_row.addStretch(1)
        cl.addLayout(brand_ver_row)
        cl.addSpacing(12)

        # 合规与安全说明（柔和卡片式排版、次级灰调字体，随全站深浅主题动态适配）
        self._compliance_box = QFrame(self._card)
        self._compliance_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        cb_l = QVBoxLayout(self._compliance_box)
        cb_l.setContentsMargins(12, 10, 12, 10)
        cb_l.setSpacing(4)

        self._lbl_compliance_title = QLabel("合规与安全说明", self._compliance_box)
        self._lbl_compliance_title.setFont(get_source_han_font(8, QFont.Weight.Bold))
        cb_l.addWidget(self._lbl_compliance_title)

        self._lbl_compliance_1 = QLabel(
            "• 开源透明承诺：本项目已在 GitHub 完整开源，全部代码公开可审计；",
            self._compliance_box,
        )
        self._lbl_compliance_1.setFont(get_source_han_font(7))
        self._lbl_compliance_1.setWordWrap(True)

        self._lbl_compliance_2 = QLabel(
            "• 本地隐私零上传：所有剪贴板历史、截图 OCR、屏幕取色、调休日历、月薪配置及摸鱼统计数据均仅保存在本地设备，不向任何第三方服务器上传；",
            self._compliance_box,
        )
        self._lbl_compliance_2.setFont(get_source_han_font(7))
        self._lbl_compliance_2.setWordWrap(True)

        self._lbl_compliance_3 = QLabel(
            "• 跨设备互传与穿透安全：局域网直连仅限内网点对点传输，退出会话自动清空聊天记录（保留本地文件）；公网穿透基于 Cloudflare Tunnel（Apache 2.0 协议）按需本地启动且启用一次性校验；",
            self._compliance_box,
        )
        self._lbl_compliance_3.setFont(get_source_han_font(7))
        self._lbl_compliance_3.setWordWrap(True)

        self._lbl_compliance_4 = QLabel(
            "• 可选匿名统计说明：在线摸鱼人数统计默认关闭，仅在用户手动开启并处于摸鱼状态时发送随机生成的本地 UUID 匿名心跳，不包含任何身份或硬件信息；",
            self._compliance_box,
        )
        self._lbl_compliance_4.setFont(get_source_han_font(7))
        self._lbl_compliance_4.setWordWrap(True)

        self._lbl_compliance_5 = QLabel(
            "• 通用工具中立声明：内置多线程下载器仅作为通用效率组件，不提供任何受版权保护资源链接或解析服务。",
            self._compliance_box,
        )
        self._lbl_compliance_5.setFont(get_source_han_font(7))
        self._lbl_compliance_5.setWordWrap(True)

        cb_l.addWidget(self._lbl_compliance_1)
        cb_l.addWidget(self._lbl_compliance_2)
        cb_l.addWidget(self._lbl_compliance_3)
        cb_l.addWidget(self._lbl_compliance_4)
        cb_l.addWidget(self._lbl_compliance_5)
        cl.addWidget(self._compliance_box)

        outer.addWidget(self._card)
        self.apply_theme(self._config.theme_mode, self._config.accent_color)
        self._fit_compact_height()

    def _fit_compact_height(self) -> None:
        """按主窗统一宽度精确计算所有折行文本的实际所需高度，彻底消除 QDialog.adjustSize() 过高撑出的空白断层。"""
        w = MAIN_WIDTH
        inner_text_w = w - 32 - 2 - 24 - 2  # card(16*2+border 2) + compliance_box(12*2+border 2)
        for lbl in (
            self._lbl_compliance_title,
            self._lbl_compliance_1,
            self._lbl_compliance_2,
            self._lbl_compliance_3,
            self._lbl_compliance_4,
            self._lbl_compliance_5,
        ):
            lbl.setFixedWidth(inner_text_w)
            h = lbl.heightForWidth(inner_text_w)
            if h <= 0:
                h = lbl.sizeHint().height()
            lbl.setFixedHeight(h)
        if self._compliance_box.layout() is not None:
            self._compliance_box.layout().activate()
            comp_h = self._compliance_box.layout().sizeHint().height() + 2
            self._compliance_box.setFixedHeight(comp_h)
        if self._card.layout() is not None:
            self._card.layout().activate()
            req_h = self._card.layout().sizeHint().height() + 2
            self.setFixedSize(w, req_h)

    def adjustSize(self) -> None:
        self._fit_compact_height()

    def set_changelog_info(self, version: str, changelog: str) -> None:
        self._changelog_ver = str(version or CURRENT_VERSION)
        self._changelog_text = str(changelog or "")
        if self._hover_card is not None:
            self._hover_card.close()
            self._hover_card = None

    def eventFilter(self, obj, event) -> bool:
        if obj is getattr(self, "_lbl_ver_pill", None):
            if event.type() == QEvent.Type.Enter:
                self._ver_pill_hovered = True
                self._hide_timer.stop()
                self._show_changelog_hover_card()
            elif event.type() == QEvent.Type.Leave:
                self._ver_pill_hovered = False
                self._hide_timer.start(140)
        return super().eventFilter(obj, event)

    def _show_changelog_hover_card(self) -> None:
        if self._hover_card is None:
            self._hover_card = ChangelogHoverCard(
                version=self._changelog_ver,
                changelog=self._changelog_text,
                theme_mode=self._config.theme_mode,
                accent_color=self._config.accent_color,
                parent=self,
            )
            self._hover_card.hovered_changed.connect(self._on_hover_card_entered)

        pill_global = self._lbl_ver_pill.mapToGlobal(QPoint(self._lbl_ver_pill.width() + 8, -6))
        card_w = self._hover_card.width()
        card_h = self._hover_card.height()
        screen = QApplication.screenAt(pill_global) or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else QRectF(0, 0, 1920, 1080).toRect()

        x = pill_global.x()
        if x + card_w > avail.right() - 8:
            left_global = self._lbl_ver_pill.mapToGlobal(QPoint(-card_w - 8, -6))
            x = max(avail.left() + 8, left_global.x())
        y = min(pill_global.y(), avail.bottom() - card_h - 8)
        y = max(avail.top() + 8, y)
        self._hover_card.move(x, y)
        self._hover_card.show()
        self._hover_card.raise_()

    def _on_hover_card_entered(self, hovered: bool) -> None:
        self._card_hovered = hovered
        if hovered:
            self._hide_timer.stop()
        else:
            self._hide_timer.start(140)

    def _check_hide_hover_card(self) -> None:
        if not self._ver_pill_hovered and not self._card_hovered:
            if self._hover_card is not None:
                self._hover_card.hide()

    def closeEvent(self, event) -> None:
        if self._hover_card is not None:
            self._hover_card.close()
            self._hover_card = None
        super().closeEvent(event)

    def apply_theme(self, theme_mode: str, accent_color: str) -> None:
        is_light = theme_mode == "light"
        bg = "#F5F6F8" if is_light else "#18181D"
        border = "#DCDFE6" if is_light else "#2C2C36"
        fg = "#1D1E22" if is_light else "#F5F5F7"
        muted = "#6E707A" if is_light else "#9A9AA6"
        sub_muted = "#767985" if is_light else "#8C8C98"
        comp_bg = "#EFF1F6" if is_light else "#1C1C23"
        pill_hover = "#E2E4EC" if is_light else "#2D2D38"
        pill_press = "#D5D8E2" if is_light else "#363644"

        self._card.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}"
        )
        self._lbl_header.setStyleSheet(f"color: {fg}; border: none; background: transparent;")
        self._lbl_brand.setStyleSheet(f"color: {fg}; border: none; background: transparent;")
        self._lbl_icon.setStyleSheet("border: none; background: transparent;")
        win_btn_qss = (
            f"QPushButton {{ background: transparent; color: {muted}; border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ background-color: {pill_hover}; color: {fg}; }}"
            f"QPushButton:pressed {{ background-color: {pill_press}; color: {accent_color}; padding-top: 1px; }}"
        )
        self._btn_min.setStyleSheet(win_btn_qss)
        self._btn_close.setStyleSheet(win_btn_qss)

        ver_bg = "#ECFDF5" if is_light else "#132920"
        ver_bd = "#A7F3D0" if is_light else "#1F4D3A"
        self._lbl_ver_pill.setStyleSheet(
            f"color: {GREEN_ACCENT}; background-color: {ver_bg}; border: 1px solid {ver_bd}; "
            "border-radius: 8px; padding: 1px 7px;"
        )

        self._compliance_box.setStyleSheet(
            f"QFrame {{ background-color: {comp_bg}; border: 1px solid {border}; border-radius: 10px; }}"
        )
        self._lbl_compliance_title.setStyleSheet(f"color: {accent_color}; border: none; background: transparent;")
        for lbl_c in (
            self._lbl_compliance_1,
            self._lbl_compliance_2,
            self._lbl_compliance_3,
            self._lbl_compliance_4,
            self._lbl_compliance_5,
        ):
            lbl_c.setStyleSheet(f"color: {sub_muted}; border: none; background: transparent;")

        if self._hover_card is not None:
            self._hover_card.close()
            self._hover_card = None
        self._lbl_icon.setPixmap(_build_app_qpixmap(accent_color, size=72, hidpi=True))
        self.setWindowIcon(_build_app_qicon(accent_color))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class CacheManagerDialog(QDialog):
    """非模态缓存文件管理窗口（支持拖动、定位目录、自定义目录与后台自动迁移）。"""

    migration_done = Signal(bool, str)

    def __init__(
        self,
        config: AppConfig,
        on_migrated=None,
        is_internet_active_fn=None,
        parent=None,
    ):
        super().__init__(parent)
        self._config = config
        self._on_migrated = on_migrated
        self._is_internet_active_fn = is_internet_active_fn
        self._is_light = config.theme_mode == "light"
        self._accent = config.accent_color
        self._drag_pos: QPoint | None = None
        self._migrating = False
        self._msg_kind = "success"
        self._internet_blocked_tip = False

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)
        self.setFixedWidth(MAIN_WIDTH)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame(self)
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(4)
        self._lbl_title = QLabel("缓存文件管理", self._card)
        self._lbl_title.setFont(get_source_han_font(10, QFont.Weight.Bold))
        self._btn_min = QPushButton("—", self._card)
        self._btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_min.setFixedSize(22, 22)
        self._btn_min.setToolTip("最小化")
        self._btn_min.clicked.connect(self.showMinimized)
        self._btn_close = QPushButton("✕", self._card)
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.setFixedSize(22, 22)
        self._btn_close.clicked.connect(self.close)
        top.addWidget(self._lbl_title)
        top.addStretch(1)
        top.addWidget(self._btn_min)
        top.addWidget(self._btn_close)
        cl.addLayout(top)

        self._lbl_path_caption = QLabel("当前缓存目录", self._card)
        self._lbl_path_caption.setFont(get_source_han_font(8))
        cl.addWidget(self._lbl_path_caption)

        self._lbl_path = QLabel("", self._card)
        self._lbl_path.setFont(get_source_han_font(8))
        self._lbl_path.setWordWrap(True)
        cl.addWidget(self._lbl_path)

        self._lbl_size = QLabel("", self._card)
        self._lbl_size.setFont(get_source_han_font(8, QFont.Weight.Bold))
        cl.addWidget(self._lbl_size)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_locate = QPushButton("定位当前位置", self._card)
        self._btn_locate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_locate.setFixedHeight(32)
        self._btn_locate.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._btn_locate.clicked.connect(self._on_locate_clicked)

        self._btn_custom = QPushButton("自定义缓存位置", self._card)
        self._btn_custom.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_custom.setFixedHeight(32)
        self._btn_custom.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._btn_custom.clicked.connect(self._on_custom_clicked)

        btn_row.addWidget(self._btn_locate, 1)
        btn_row.addWidget(self._btn_custom, 1)
        cl.addLayout(btn_row)

        self._lbl_msg = QLabel("", self._card)
        self._lbl_msg.setFont(get_source_han_font(8))
        self._lbl_msg.setWordWrap(True)
        self._lbl_msg.setVisible(False)
        cl.addWidget(self._lbl_msg)

        outer.addWidget(self._card)
        self.migration_done.connect(self._handle_migration_done)
        self.refresh_info()
        self.apply_theme(config.theme_mode, config.accent_color)
        self.adjustSize()

    def _is_internet_blocked_now(self) -> bool:
        return (
            bool(self._is_internet_active_fn and self._is_internet_active_fn())
            or _has_active_cloudflared_proc()
        )

    def clear_internet_blocked_tip(self) -> None:
        self._internet_blocked_tip = False
        self.refresh_info()

    def refresh_info(self) -> None:
        cur_dir = CacheManager.get_effective_cache_dir(self._config)
        size_b = CacheManager.calc_cache_size_bytes(cur_dir)
        self._lbl_path.setText(cur_dir)
        if self._internet_blocked_tip and self._is_internet_blocked_now():
            self._lbl_size.setStyleSheet(f"color: {INVALID_RED}; border: none;")
            self._lbl_size.setText("请在连接手机  管理 关闭互联网模式")
        else:
            self._internet_blocked_tip = False
            self._lbl_size.setStyleSheet(f"color: {self._accent}; border: none;")
            self._lbl_size.setText(f"已占用 {FastDownloader.format_size(size_b)}")

    def apply_theme(self, theme_mode: str, accent_color: str) -> None:
        self._is_light = theme_mode == "light"
        self._accent = accent_color
        bg = "#F5F6F8" if self._is_light else "#18181D"
        border = "#DCDFE6" if self._is_light else "#2C2C36"
        fg = "#1D1E22" if self._is_light else "#F5F5F7"
        muted = "#6E707A" if self._is_light else "#9A9AA6"
        pill_bg = "#ECEDF2" if self._is_light else "#22222A"
        pill_hover = "#E2E4EC" if self._is_light else "#2D2D38"

        self._card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}")
        self._lbl_title.setStyleSheet(f"color: {fg}; border: none;")
        self._lbl_path_caption.setStyleSheet(f"color: {muted}; border: none;")
        self._lbl_path.setStyleSheet(
            f"color: {fg}; background-color: {pill_bg}; border: 1px solid {border}; border-radius: 8px; padding: 6px 8px;"
        )
        self._lbl_size.setStyleSheet(
            f"color: {INVALID_RED if self._internet_blocked_tip else accent_color}; border: none;"
        )
        win_btn_qss = (
            f"QPushButton {{ background: transparent; color: {muted}; border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ background-color: {pill_hover}; color: {fg}; }}"
        )
        self._btn_min.setStyleSheet(win_btn_qss)
        self._btn_close.setStyleSheet(win_btn_qss)
        self._btn_locate.setStyleSheet(
            f"QPushButton {{ background-color: {pill_bg}; color: {fg}; border: 1px solid {border}; border-radius: 8px; }}"
            f"QPushButton:hover {{ background-color: {pill_hover}; border-color: {accent_color}; color: {accent_color}; }}"
        )
        self._btn_custom.setStyleSheet(
            f"QPushButton {{ background-color: {accent_color}; color: #FFFFFF; border: none; border-radius: 8px; }}"
        )
        self._apply_msg_style()
        self.update()

    def _apply_msg_style(self) -> None:
        if self._msg_kind == "warning":
            w_bg = "#FFFBEB" if self._is_light else "#2B2314"
            w_border = "#FCD34D" if self._is_light else "#78521A"
            w_fg = "#B45309" if self._is_light else "#FBBF24"
            self._lbl_msg.setStyleSheet(
                f"color: {w_fg}; background-color: {w_bg}; border: 1px solid {w_border}; border-radius: 8px; padding: 6px 8px;"
            )
        elif self._msg_kind == "error":
            self._lbl_msg.setStyleSheet(f"color: {INVALID_RED}; border: none; background: transparent;")
        elif self._msg_kind == "info":
            self._lbl_msg.setStyleSheet(f"color: {self._accent}; border: none; background: transparent;")
        else:
            self._lbl_msg.setStyleSheet(f"color: {GREEN_ACCENT}; border: none; background: transparent;")

    def _show_status_msg(self, text: str, kind: str = "info") -> None:
        self._msg_kind = kind
        self._apply_msg_style()
        self._lbl_msg.setText(text)
        self._lbl_msg.setVisible(True)
        self.adjustSize()

    def _on_locate_clicked(self) -> None:
        cur_dir = CacheManager.get_effective_cache_dir(self._config)
        os.makedirs(cur_dir, exist_ok=True)
        try:
            os.startfile(cur_dir)
        except Exception:
            pass

    def _on_custom_clicked(self) -> None:
        if self._migrating:
            return
        # 迁移前置检测：若【互联网】模式或 cloudflared 穿透进程正在运行，立即拦截并在“已占用”位置原地警示
        if self._is_internet_blocked_now():
            self._internet_blocked_tip = True
            self._lbl_msg.setVisible(False)
            self._lbl_size.setStyleSheet(f"color: {INVALID_RED}; border: none;")
            self._lbl_size.setText("请在连接手机  管理 关闭互联网模式")
            return
        if self._internet_blocked_tip:
            self.clear_internet_blocked_tip()

        cur_dir = CacheManager.get_effective_cache_dir(self._config)
        new_dir = QFileDialog.getExistingDirectory(self, "选择新的缓存存储目录", cur_dir)
        if not new_dir:
            return
        self._migrating = True
        self._btn_custom.setEnabled(False)
        self._btn_custom.setText("迁移中...")
        self._show_status_msg("正在迁移缓存文件，请稍候...", kind="info")

        def _worker() -> None:
            ok, msg = CacheManager.migrate_cache(cur_dir, new_dir)
            self.migration_done.emit(ok, msg)

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_migration_done(self, ok: bool, msg: str) -> None:
        self._migrating = False
        self._btn_custom.setEnabled(True)
        self._btn_custom.setText("自定义缓存位置")
        if ok:
            self._config.cache_dir = msg
            self._config.save()
            if self._on_migrated:
                self._on_migrated(msg)
            self.refresh_info()
            self._show_status_msg("✓ 缓存已迁移至新位置", kind="success")
        else:
            self._show_status_msg(msg, kind="error")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


def _run_windows_ocr(image_path: str) -> str:
    """调用 Windows 10/11 原生离线 OCR 引擎（自动小图 2x LANCZOS 放大 + Bgra8/Premultiplied 转换 + UTF-8）。"""
    target_path = os.path.abspath(image_path)
    upscaled_path = ""
    try:
        from PIL import Image

        with Image.open(target_path) as im:
            w, h = im.size
            if w < 100 or h < 100:
                resampling = getattr(Image, "Resampling", Image)
                lanczos = getattr(resampling, "LANCZOS", getattr(Image, "LANCZOS", 1))
                resized = im.convert("RGB").resize((max(1, w * 2), max(1, h * 2)), lanczos)
                base, _ext = os.path.splitext(target_path)
                upscaled_path = f"{base}_2x.png"
                resized.save(upscaled_path, "PNG")
                target_path = upscaled_path
    except Exception:
        pass

    safe_path = target_path.replace("'", "''")
    ps_script = f"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null = [Windows.Storage.FileAccessMode,Windows.Storage,ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapPixelFormat,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapAlphaMode,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult,Windows.Foundation,ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
function Await($WinRtTask, $ResultType) {{
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    return $netTask.GetAwaiter().GetResult()
}}
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync('{safe_path}')) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$bitmap = $null
try {{
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $rawBitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    if ($rawBitmap.BitmapPixelFormat -ne [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8 -or $rawBitmap.BitmapAlphaMode -ne [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied) {{
        $bitmap = [Windows.Graphics.Imaging.SoftwareBitmap]::Convert(
            $rawBitmap,
            [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
            [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied
        )
        $rawBitmap.Dispose()
    }} else {{
        $bitmap = $rawBitmap
    }}
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) {{
        $langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
        if ($langs.Count -gt 0) {{
            $zh = $langs | Where-Object {{ $_.LanguageTag -like 'zh*' }} | Select-Object -First 1
            $chosen = if ($null -ne $zh) {{ $zh }} else {{ $langs[0] }}
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($chosen)
        }}
    }}
    if ($null -eq $engine) {{ exit 2 }}
    $res = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    if ($null -ne $res.Lines -and $res.Lines.Count -gt 0) {{
        ($res.Lines | ForEach-Object {{ $_.Text }}) -join "`n"
    }} else {{
        Write-Output $res.Text
    }}
}} finally {{
    if ($null -ne $bitmap) {{ $bitmap.Dispose() }}
    if ($null -ne $stream) {{ $stream.Dispose() }}
}}
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=25,
        )
        return (proc.stdout or "").strip()
    finally:
        if upscaled_path and os.path.isfile(upscaled_path):
            try:
                os.remove(upscaled_path)
            except Exception:
                pass


class OcrWorkerBridge(QObject):
    finished = Signal(str, str)


class ScreenCaptureOverlay(QWidget):
    """全屏多显示器截图识字 / 截图发送到手机 / 实时放大镜屏幕取色浮层（支持多屏不同 DPI 1:1 精确对齐）。"""

    ocr_captured = Signal(str)
    transfer_captured = Signal(str)
    color_picked = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        mode: str,
        pil_img,
        cache_dir: str,
        accent_color: str = "#FF6B00",
        virt_rect: tuple[int, int, int, int] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._mode = mode  # "ocr" | "picker"
        self._pil_img = pil_img.convert("RGBA")
        self._cache_dir = cache_dir
        self._accent = QColor(accent_color)

        raw = self._pil_img.tobytes("raw", "RGBA")
        qimg = QImage(raw, self._pil_img.width, self._pil_img.height, QImage.Format.Format_RGBA8888)
        self._pixmap = QPixmap.fromImage(qimg)
        self._pixmap.setDevicePixelRatio(1.0)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # 使用 Win32 GetSystemMetrics 真实物理虚拟屏幕坐标 (vx, vy, vw, vh)
        if virt_rect and virt_rect[2] > 0 and virt_rect[3] > 0:
            self._vx, self._vy, self._vw, self._vh = virt_rect
        else:
            vx, vy, vw, vh = _get_virtual_screen_rect()
            if vw > 0 and vh > 0:
                self._vx, self._vy, self._vw, self._vh = vx, vy, vw, vh
            else:
                self._vx, self._vy = 0, 0
                self._vw, self._vh = self._pil_img.width, self._pil_img.height

        # 预设单屏逻辑几何（随后在 showEvent 中通过 GetAncestor + SetWindowPos 精确贴合该物理显示器）
        screens = QApplication.screens()
        matched_geo = None
        if screens:
            cx, cy = self._vx + self._vw / 2.0, self._vy + self._vh / 2.0
            for sc in screens:
                dpr = sc.devicePixelRatio() or 1.0
                g = sc.geometry()
                px1, py1 = g.x() * dpr, g.y() * dpr
                px2, py2 = (g.x() + g.width()) * dpr, (g.y() + g.height()) * dpr
                if px1 <= cx <= px2 and py1 <= cy <= py2:
                    matched_geo = g
                    break
            if matched_geo is None:
                matched_geo = screens[0].geometry()
        else:
            matched_geo = QRectF(0, 0, self._vw, self._vh).toRect()
        self._virt_geo = matched_geo
        self.setGeometry(matched_geo)

        self._dragging = False
        self._start_img_xy = (0, 0)
        self._end_img_xy = (0, 0)
        cur_pos = _get_physical_cursor_pos()
        if cur_pos is not None:
            self._cursor_img_xy = self._phys_to_img_xy(cur_pos[0], cur_pos[1])
        else:
            self._cursor_img_xy = (self._pil_img.width // 2, self._pil_img.height // 2)

    def _sync_native_geometry(self) -> None:
        """在 Windows 下通过 GetAncestor 获取根窗口句柄并调用 SetWindowPos 精确定位到对应物理显示器。"""
        if sys.platform != "win32" or self._vw <= 0 or self._vh <= 0:
            return
        try:
            user32 = ctypes.windll.user32
            hwnd = int(self.winId())
            GA_ROOT = 2
            root_hwnd = int(user32.GetAncestor(hwnd, GA_ROOT) or hwnd)
            HWND_TOPMOST = -1
            SWP_SHOWWINDOW = 0x0040
            SWP_NOACTIVATE = 0x0010
            user32.SetWindowPos(
                root_hwnd,
                HWND_TOPMOST,
                int(self._vx),
                int(self._vy),
                int(self._vw),
                int(self._vh),
                SWP_SHOWWINDOW | SWP_NOACTIVATE,
            )
            self.update()
        except Exception:
            pass

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_native_geometry()
        QTimer.singleShot(0, self._sync_native_geometry)
        QTimer.singleShot(30, self._sync_native_geometry)

    def _phys_to_img_xy(self, px: int, py: int) -> tuple[int, int]:
        rx = (px - self._vx) * (self._pil_img.width / max(1, self._vw))
        ry = (py - self._vy) * (self._pil_img.height / max(1, self._vh))
        ix = max(0, min(self._pil_img.width - 1, int(round(rx))))
        iy = max(0, min(self._pil_img.height - 1, int(round(ry))))
        return ix, iy

    def _widget_to_img_xy(self, pt: QPoint) -> tuple[int, int]:
        sx = self._pil_img.width / max(1, self.width())
        sy = self._pil_img.height / max(1, self.height())
        ix = max(0, min(self._pil_img.width - 1, int(pt.x() * sx)))
        iy = max(0, min(self._pil_img.height - 1, int(pt.y() * sy)))
        return ix, iy

    def _event_to_img_xy(self, event) -> tuple[int, int]:
        cur = _get_physical_cursor_pos()
        if cur is not None:
            return self._phys_to_img_xy(cur[0], cur[1])
        return self._widget_to_img_xy(event.position().toPoint())

    def _img_to_widget_pt(self, ix: int, iy: int) -> QPointF:
        wx = ix * (self.width() / max(1.0, float(self._pil_img.width)))
        wy = iy * (self.height() / max(1.0, float(self._pil_img.height)))
        return QPointF(wx, wy)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()
            self.close()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            ix, iy = self._event_to_img_xy(event)
            self._cursor_img_xy = (ix, iy)
            if self._mode == "picker":
                r, g, b, _ = self._pil_img.getpixel((ix, iy))
                self.color_picked.emit(f"#{r:02X}{g:02X}{b:02X}")
                self.close()
                return
            self._dragging = True
            self._start_img_xy = (ix, iy)
            self._end_img_xy = (ix, iy)
            self.update()

    def mouseMoveEvent(self, event) -> None:
        ix, iy = self._event_to_img_xy(event)
        self._cursor_img_xy = (ix, iy)
        if self._mode in ("ocr", "transfer") and self._dragging:
            self._end_img_xy = (ix, iy)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._mode in ("ocr", "transfer") and event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._end_img_xy = self._event_to_img_xy(event)
            x1, y1 = self._start_img_xy
            x2, y2 = self._end_img_xy
            left, right = min(x1, x2), max(x1, x2)
            top, bottom = min(y1, y2), max(y1, y2)
            if (right - left) >= 6 and (bottom - top) >= 6:
                crop = self._pil_img.crop((left, top, right, bottom)).convert("RGB")
                os.makedirs(self._cache_dir, exist_ok=True)
                if self._mode == "transfer":
                    ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
                    shot_path = os.path.join(self._cache_dir, f"screenshot_{ts_tag}_{uuid.uuid4().hex[:4]}.png")
                    crop.save(shot_path, "PNG")
                    self.transfer_captured.emit(shot_path)
                else:
                    temp_path = os.path.join(self._cache_dir, f"ocr_temp_{uuid.uuid4().hex[:8]}.png")
                    crop.save(temp_path, "PNG")
                    self.ocr_captured.emit(temp_path)
            else:
                self.cancelled.emit()
            self.close()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        target_rect = QRectF(0.0, 0.0, float(self.width()), float(self.height()))
        full_src = QRectF(0.0, 0.0, float(self._pixmap.width()), float(self._pixmap.height()))
        p.drawPixmap(target_rect, self._pixmap, full_src)

        if self._mode in ("ocr", "transfer"):
            p.fillRect(self.rect(), QColor(0, 0, 0, 110))
            if self._dragging:
                x1, y1 = self._start_img_xy
                x2, y2 = self._end_img_xy
                left_i, right_i = min(x1, x2), max(x1, x2)
                top_i, bottom_i = min(y1, y2), max(y1, y2)
                if (right_i - left_i) > 0 and (bottom_i - top_i) > 0:
                    tl = self._img_to_widget_pt(left_i, top_i)
                    br = self._img_to_widget_pt(right_i, bottom_i)
                    sel_f = QRectF(tl, br)
                    sel = sel_f.toRect()
                    src_rect = QRectF(left_i, top_i, right_i - left_i, bottom_i - top_i)
                    p.drawPixmap(sel_f, self._pixmap, src_rect)
                    p.setPen(QPen(self._accent, 2.0))
                    p.drawRect(sel)
                    dim_txt = f"{int(right_i - left_i)} × {int(bottom_i - top_i)}"
                    p.setFont(get_source_han_font(9, QFont.Weight.Bold))
                    ty = max(18, sel.top() - 8)
                    p.fillRect(sel.left(), ty - 16, 92, 18, QColor(0, 0, 0, 180))
                    p.setPen(QColor("#FFFFFF"))
                    p.drawText(sel.left() + 6, ty - 2, dim_txt)
        else:
            # 11x11 实时像素放大镜卡片（仅在鼠标位于当前显示器内时绘制）
            cur_phys = _get_physical_cursor_pos()
            if cur_phys is not None:
                px_cur, py_cur = cur_phys
                if not (self._vx <= px_cur < self._vx + self._vw and self._vy <= py_cur < self._vy + self._vh):
                    p.end()
                    return
            ix, iy = self._cursor_img_xy
            r, g, b, _ = self._pil_img.getpixel((ix, iy))
            hex_str = f"#{r:02X}{g:02X}{b:02X}"
            cur_w = self._img_to_widget_pt(ix, iy)
            card_w, card_h = 148, 166
            cx = int(cur_w.x()) + 18
            cy = int(cur_w.y()) + 18
            if cx + card_w > self.width() - 8:
                cx = int(cur_w.x()) - card_w - 18
            if cy + card_h > self.height() - 8:
                cy = int(cur_w.y()) - card_h - 18

            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(QColor(24, 24, 29, 240))
            p.setPen(QPen(QColor(70, 70, 82), 1.0))
            p.drawRoundedRect(QRectF(cx, cy, card_w, card_h), 10.0, 10.0)

            # 11x11 网格（每格 10px -> 110x110）
            grid_x, grid_y, cell = cx + 19, cy + 10, 10
            for dy in range(-5, 6):
                for dx in range(-5, 6):
                    px = max(0, min(self._pil_img.width - 1, ix + dx))
                    py = max(0, min(self._pil_img.height - 1, iy + dy))
                    pr, pg, pb, _ = self._pil_img.getpixel((px, py))
                    p.fillRect(grid_x + (dx + 5) * cell, grid_y + (dy + 5) * cell, cell, cell, QColor(pr, pg, pb))
            p.setPen(QPen(QColor(255, 255, 255, 180), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(grid_x + 5 * cell, grid_y + 5 * cell, cell, cell)

            # 下半部分：色块 + #HEX + RGB
            p.fillRect(cx + 12, cy + 128, 26, 26, QColor(r, g, b))
            p.setPen(QPen(QColor(255, 255, 255, 120), 1.0))
            p.drawRect(cx + 12, cy + 128, 26, 26)
            p.setPen(QColor("#F5F5F7"))
            p.setFont(get_source_han_font(9, QFont.Weight.Bold))
            p.drawText(cx + 46, cy + 139, hex_str)
            p.setPen(QColor("#9A9AA6"))
            p.setFont(get_source_han_font(7))
            p.drawText(cx + 46, cy + 154, f"RGB({r}, {g}, {b})")
        p.end()


class LanTransferBridge(QObject):
    """将后台 HTTP 线程接收到的手机文本/文件安全转发至 Qt 主线程。"""

    text_received = Signal(str)
    file_received = Signal(str)


_ACTIVE_TUNNEL_PROCS: set[subprocess.Popen] = set()
_ACTIVE_TUNNEL_PROCS_LOCK = threading.Lock()


def _has_active_cloudflared_proc() -> bool:
    """检查当前是否仍有正在运行的 cloudflared 穿透子进程。"""
    with _ACTIVE_TUNNEL_PROCS_LOCK:
        procs = list(_ACTIVE_TUNNEL_PROCS)
    for proc in procs:
        try:
            if proc is not None and proc.poll() is None:
                return True
        except Exception:
            pass
    return False


def _cleanup_all_cloudflared_procs() -> None:
    """进程退出兜底：销毁所有残留的 cloudflared 子进程。"""
    with _ACTIVE_TUNNEL_PROCS_LOCK:
        procs = list(_ACTIVE_TUNNEL_PROCS)
        _ACTIVE_TUNNEL_PROCS.clear()
    for proc in procs:
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except Exception:
                    proc.kill()
        except Exception:
            pass


atexit.register(_cleanup_all_cloudflared_procs)
atexit.register(LanTransferServer.cleanup_all_share_cache)


class _TunnelLoadingSpinner(QWidget):
    """二维码区域内嵌动态旋转加载动画 + 状态文本 + 可选下载进度条。"""

    def __init__(self, accent_color: str = "#FF6B00", is_light: bool = False, parent=None):
        super().__init__(parent)
        self._accent = QColor(accent_color)
        self._is_light = is_light
        self._angle = 0
        self._status_text = "正在打通安全公网隧道..."
        self._show_progress = False
        self._progress_val = 0.0

        self.setFixedSize(148, 148)
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)

    def set_theme(self, is_light: bool, accent_color: str) -> None:
        self._is_light = is_light
        self._accent = QColor(accent_color)
        self.update()

    def set_state(self, text: str, show_progress: bool = False, progress: float = 0.0) -> None:
        self._status_text = text
        self._show_progress = show_progress
        self._progress_val = max(0.0, min(100.0, float(progress)))
        self.update()

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()

    def _tick(self) -> None:
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = QColor("#ECEDF2" if self._is_light else "#22222A")
        border = QColor("#DCDFE6" if self._is_light else "#2C2C36")
        track = QColor("#D5D8E2" if self._is_light else "#32323D")
        fg = QColor("#4E505C" if self._is_light else "#C8C8D4")

        p.setBrush(QBrush(bg))
        p.setPen(QPen(border, 1.0))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0), 10.0, 10.0)

        # 中上部旋转加载圆弧
        ring_d = 38.0
        ring_x = (self.width() - ring_d) / 2.0
        ring_y = 24.0 if self._show_progress else 32.0
        ring_rect = QRectF(ring_x, ring_y, ring_d, ring_d)

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(track, 3.2))
        p.drawEllipse(ring_rect)

        arc_pen = QPen(self._accent, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(arc_pen)
        p.drawArc(ring_rect, int(-self._angle * 16), int(105 * 16))

        # 居中状态提示文案（自动换行）
        txt_y = ring_y + ring_d + 10.0
        txt_h = 38.0 if self._show_progress else 48.0
        p.setPen(fg)
        p.setFont(get_source_han_font(8, QFont.Weight.Bold))
        p.drawText(
            QRectF(10.0, txt_y, self.width() - 20.0, txt_h),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            self._status_text,
        )

        # 下载阶段绘制精巧进度条
        if self._show_progress:
            bar_x, bar_y, bar_w, bar_h = 16.0, self.height() - 20.0, self.width() - 32.0, 6.0
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(track))
            p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3.0, 3.0)
            if self._progress_val > 0.0:
                fill_w = max(bar_h, bar_w * (self._progress_val / 100.0))
                p.setBrush(QBrush(self._accent))
                p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 3.0, 3.0)
        p.end()


class _CloudflaredDownloadConfirmDialog(QDialog):
    """首次启用【互联网】模式或组件缺失时的下载引导确认框。"""

    def __init__(self, target_path: str, is_light: bool, accent_color: str, parent=None):
        super().__init__(parent)
        self._drag_pos: QPoint | None = None
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFixedWidth(MAIN_WIDTH)

        bg = "#F5F6F8" if is_light else "#18181D"
        border = "#DCDFE6" if is_light else "#2C2C36"
        fg = "#1D1E22" if is_light else "#F5F5F7"
        muted = "#6E707A" if is_light else "#9A9AA6"
        pill_bg = "#ECEDF2" if is_light else "#22222A"
        pill_hover = "#E2E4EC" if is_light else "#2D2D38"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(self)
        card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(4)
        lbl_title = QLabel("需要下载跨网穿透组件", card)
        lbl_title.setFont(get_source_han_font(10, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {fg}; border: none;")
        win_btn_qss = (
            f"QPushButton {{ background: transparent; color: {muted}; border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ background-color: {pill_hover}; color: {fg}; }}"
        )
        btn_min = QPushButton("—", card)
        btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_min.setFixedSize(22, 22)
        btn_min.setToolTip("最小化")
        btn_min.setStyleSheet(win_btn_qss)
        btn_min.clicked.connect(self.showMinimized)
        btn_close = QPushButton("✕", card)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setFixedSize(22, 22)
        btn_close.setStyleSheet(win_btn_qss)
        btn_close.clicked.connect(self.reject)
        top.addWidget(lbl_title)
        top.addStretch(1)
        top.addWidget(btn_min)
        top.addWidget(btn_close)
        cl.addLayout(top)

        lbl_desc = QLabel(
            "【互联网】模式支持手机 5G 流量跨网扫码访问，首次使用需自动下载约 35MB 的 Cloudflare 安全穿透组件（cloudflared.exe）。",
            card,
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setFont(get_source_han_font(8))
        lbl_desc.setStyleSheet(f"color: {muted}; border: none; line-height: 1.4;")
        cl.addWidget(lbl_desc)

        lbl_path = QLabel(f"组件路径：{target_path}", card)
        lbl_path.setWordWrap(True)
        lbl_path.setFont(get_source_han_font(7))
        lbl_path.setStyleSheet(
            f"background-color: {pill_bg}; color: {muted}; border: 1px solid {border}; border-radius: 8px; padding: 6px 8px;"
        )
        cl.addWidget(lbl_path)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_cancel = QPushButton("暂不下载", card)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setFixedHeight(30)
        btn_cancel.setFont(get_source_han_font(9, QFont.Weight.Bold))
        btn_cancel.setStyleSheet(
            f"QPushButton {{ background-color: {pill_bg}; color: {fg}; border: 1px solid {border}; border-radius: 8px; }}"
            f"QPushButton:hover {{ background-color: {pill_hover}; }}"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("立即下载", card)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.setFixedHeight(30)
        btn_ok.setFont(get_source_han_font(9, QFont.Weight.Bold))
        btn_ok.setStyleSheet(
            f"QPushButton {{ background-color: {accent_color}; color: #FFFFFF; border: none; border-radius: 8px; }}"
            f"QPushButton:hover {{ background-color: {QColor(accent_color).lighter(110).name()}; }}"
        )
        btn_ok.clicked.connect(self.accept)

        btn_row.addWidget(btn_cancel, 1)
        btn_row.addWidget(btn_ok, 1)
        cl.addLayout(btn_row)
        outer.addWidget(card)
        self.adjustSize()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


_TUN_STRONG_KEYWORDS = (
    "wintun",
    "wireguard",
    "sing-tun",
    "sing-box",
    "clash",
    "meta",
    "mihomo",
    "v2ray",
    "nekoray",
    "utun",
    "tap-windows",
)
_TUN_WORD_RE = re.compile(r"(?:^|[^a-z0-9])tun(?:[0-9]+|[^a-z0-9]|$)", re.IGNORECASE)


def _match_tun_adapter_name(name: str) -> bool:
    low = str(name or "").strip().lower()
    if not low:
        return False
    if any(kw in low for kw in _TUN_STRONG_KEYWORDS):
        return True
    return bool(_TUN_WORD_RE.search(low))


def detect_proxy_or_tun() -> str | None:
    """毫秒级本地检测 Windows 系统代理与 TUN 虚拟网卡模式（全异常保护，永不阻塞或崩溃）。
    返回: "代理与TUN模式" | "TUN模式" | "系统代理" | None
    """
    has_proxy = False
    has_tun = False

    # 1. 检测系统代理：Windows 注册表 ProxyEnable == 1 或环境变量 HTTP_PROXY / HTTPS_PROXY 非空
    try:
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            if str(os.environ.get(k) or "").strip():
                has_proxy = True
                break
    except Exception:
        pass

    if not has_proxy and sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            ) as reg_key:
                val, _ = winreg.QueryValueEx(reg_key, "ProxyEnable")
                if int(val) == 1:
                    has_proxy = True
        except Exception:
            pass

    # 2. 检测 TUN 虚拟网卡模式：优先 psutil.net_if_addrs()（微秒级），未安装则安全回退 ipconfig
    checked_psutil = False
    try:
        import psutil
        checked_psutil = True
        addrs = psutil.net_if_addrs() or {}
        stats = {}
        try:
            stats = psutil.net_if_stats() or {}
        except Exception:
            stats = {}
        for if_name in addrs.keys():
            if _match_tun_adapter_name(if_name):
                st = stats.get(if_name)
                if st is None or getattr(st, "isup", True):
                    has_tun = True
                    break
    except Exception:
        pass

    if not has_tun and not checked_psutil and sys.platform == "win32":
        try:
            res = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                encoding="mbcs",
                errors="ignore",
                timeout=1.5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for line in (res.stdout or "").splitlines():
                if ":" in line and not line.startswith(" ") and _match_tun_adapter_name(line):
                    has_tun = True
                    break
        except Exception:
            pass

    if has_proxy and has_tun:
        return "代理与TUN模式"
    if has_tun:
        return "TUN模式"
    if has_proxy:
        return "系统代理"
    return None


def format_proxy_tun_warning(detected: str | None) -> str:
    if not detected:
        return ""
    return f"⚠ 检测到已开启「{detected}」，可能导致隧道握手或扫码异常；若连接失败请尝试关闭代理或放行 cloudflared"


class _QuickShareDropZone(QFrame):
    """文件快传拖放区：原生支持 Windows 资源管理器拖入单文件、多文件或任意文件夹，悬停高亮主题强调色。"""

    paths_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._dragging_over = False
        self._is_light = False
        self._accent = ORANGE_ACCENT

    def set_theme(self, is_light: bool, accent_color: str) -> None:
        self._is_light = bool(is_light)
        self._accent = accent_color
        self._apply_style()

    def _apply_style(self) -> None:
        if self._dragging_over:
            ac = QColor(self._accent)
            bg = f"rgba({ac.red()}, {ac.green()}, {ac.blue()}, {'0.10' if self._is_light else '0.16'})"
            bd = self._accent
        else:
            bg = "#F7F8FA" if self._is_light else "#1C1C23"
            bd = "#CFD4E0" if self._is_light else "#333340"
        self.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1.5px dashed {bd}; border-radius: 12px; }}"
        )

    def dragEnterEvent(self, event) -> None:
        md = event.mimeData()
        if md is not None and md.hasUrls():
            local_paths = [u.toLocalFile() for u in md.urls() if u.isLocalFile() and os.path.exists(u.toLocalFile())]
            if local_paths:
                self._dragging_over = True
                self._apply_style()
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._dragging_over = False
        self._apply_style()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._dragging_over = False
        self._apply_style()
        md = event.mimeData()
        if md is not None and md.hasUrls():
            local_paths = [u.toLocalFile() for u in md.urls() if u.isLocalFile() and os.path.exists(u.toLocalFile())]
            if local_paths:
                self.paths_dropped.emit(local_paths)
                event.acceptProposedAction()
                return
        event.ignore()


class _LanAsyncBridge(QObject):
    """主线程异步回调桥接：用于在后台线程完成网卡 IP 获取、本地服务启动、二维码渲染、文件打包与收图后处理后零阻塞刷新 UI。"""

    lan_ready = Signal(int, str, object)
    lan_failed = Signal(int, str)
    qr_ready = Signal(int, str, object)
    file_post_ready = Signal(str, object, bool)
    share_packed = Signal(int, str, str, int, bool)
    share_pack_failed = Signal(int, str)
    share_downloaded = Signal(str, int, bool)
    share_state_changed = Signal(str, str, str)


class CloudflaredTunnelManager(QObject):
    """Cloudflare Tunnel 跨网穿透管理器：纯 IPv4 HTTP/2 回源局域网 IP 免疫 VPN/TUN 劫持、持续排空管道防假死、实时同步边缘注册状态。"""

    MIN_EXE_BYTES = 5 * 1024 * 1024  # 5 MB
    HANDSHAKE_TIMEOUT_SEC = 10.0
    EDGE_REGISTER_TIMEOUT_SEC = 10.0
    CUSTOM_READY_MAX_WAIT_SEC = 1.0
    REGISTERED_MARKER = "registered tunnel connection"
    EDGE_REGISTERED_RE = re.compile(r"(registered tunnel connection|connection\s+.*\s+registered)", re.IGNORECASE)
    EDGE_ACTIVATING_TIP = "二维码已生成，正在激活边缘节点..."
    EDGE_READY_TIP = "边缘节点已就绪 · 手机可直接扫码"
    EDGE_TIMEOUT_ERROR = "边缘节点激活超时，请检查代理/VPN 规则或点击重新连接"
    DEFAULT_TIMEOUT_ERROR = "连接超时，请检查代理是否放行 cloudflare.com"
    CUSTOM_TIMEOUT_ERROR = "连接超时，请检查代理是否放行 cloudflare.com 或核对 Token 配置"
    DOWNLOAD_URLS = (
        "https://ghfast.top/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
        "https://gh-proxy.com/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
    )
    TRY_URL_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
    TOKEN_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    LOG_ERROR_RULES = (
        ("provided tunnel token is not valid", "自定义隧道 Token 无效，请检查高级设置中的 Token 后重试"),
        ("invalid token", "自定义隧道 Token 无效，请检查高级设置中的 Token 后重试"),
        ("unauthorized", "自定义隧道鉴权失败，请检查 Token 是否有效后重试"),
        ("failed to request quick tunnel", "连接超时，请检查代理是否放行 cloudflare.com"),
        ("context deadline exceeded", "连接超时，请检查代理是否放行 cloudflare.com"),
        ("dial tcp", "连接超时，请检查代理是否放行 cloudflare.com"),
        ("no such host", "连接超时，请检查代理是否放行 cloudflare.com"),
        ("i/o timeout", "连接超时，请检查代理是否放行 cloudflare.com"),
    )

    download_progress = Signal(float, str)
    download_finished = Signal(str)
    download_failed = Signal(str)
    tunnel_status = Signal(str)
    tunnel_ready = Signal(str, str, str)
    edge_state_changed = Signal(str, str)
    tunnel_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._cancel_event: threading.Event | None = None
        self._session_id: int = 0
        self._state: str = "idle"  # "idle" | "downloading" | "connecting" | "ready" | "error"
        self._status_text: str = ""
        self._ready_tip: str = ""
        self._edge_ready: bool = False
        self._download_pct: float = 0.0
        self._public_base_url: str = ""
        self._active_token: str = ""
        self._prewarm_only: bool = False
        self._on_prepare_token = None

    @classmethod
    def resolve_origin_ip(cls, lan_ip: str = "") -> str:
        """优先使用真实局域网 IPv4（防止 VPN TUN 虚拟网卡劫持 127.0.0.1），无局域网 IP 时回退 127.0.0.1。"""
        candidates = [str(lan_ip or "").strip()]
        if not candidates[0]:
            try:
                candidates.append(str(LanTransferServer.get_lan_ip() or "").strip())
            except Exception:
                pass
        for ip in candidates:
            if not ip or not cls.IPV4_RE.match(ip):
                continue
            if ip.startswith("127.") or ip == "0.0.0.0" or ip.startswith("169.254."):
                continue
            return ip
        return "127.0.0.1"

    @classmethod
    def build_tunnel_env(cls, origin_ip: str = "") -> dict[str, str]:
        """保留系统 HTTP_PROXY/HTTPS_PROXY/ALL_PROXY 保障外网连通，仅在 NO_PROXY 中豁免 127.0.0.1,localhost,<本机局域网IP>。"""
        env = os.environ.copy()
        existing = str(env.get("NO_PROXY") or env.get("no_proxy") or "").strip()
        parts = [p.strip() for p in existing.split(",") if p.strip()] if existing else []
        exempt_hosts = ["127.0.0.1", "localhost"]
        resolved = cls.resolve_origin_ip(origin_ip)
        if resolved and resolved not in exempt_hosts:
            exempt_hosts.append(resolved)
        for host in exempt_hosts:
            if host not in parts:
                parts.append(host)
        merged = ",".join(parts)
        env["NO_PROXY"] = merged
        env["no_proxy"] = merged
        return env

    @classmethod
    def normalize_custom_domain(cls, domain: str) -> str:
        val = str(domain or "").strip().rstrip("/")
        if not val:
            return ""
        if not re.match(r"^https?://", val, flags=re.IGNORECASE):
            val = "https://" + val
        return val.rstrip("/")

    @classmethod
    def build_tunnel_cmd(
        cls,
        exe_path: str,
        local_port: int,
        cf_tunnel_token: str = "",
        cf_custom_domain: str = "",
        origin_ip: str = "",
    ) -> tuple[list[str], bool, str, str]:
        """构造纯 IPv4 HTTP/2 启动参数（免疫 TUN 劫持与代理不转发 UDP），返回 (cmd, is_custom, custom_domain, resolved_origin_ip)。"""
        tok = str(cf_tunnel_token or "").strip()
        dom = cls.normalize_custom_domain(cf_custom_domain)
        resolved_ip = cls.resolve_origin_ip(origin_ip)
        if tok and dom:
            return (
                [
                    exe_path,
                    "tunnel",
                    "--no-autoupdate",
                    "--protocol",
                    "http2",
                    "run",
                    "--token",
                    tok,
                ],
                True,
                dom,
                resolved_ip,
            )
        return (
            [
                exe_path,
                "tunnel",
                "--no-autoupdate",
                "--edge-ip-version",
                "4",
                "--protocol",
                "http2",
                "--url",
                f"http://{resolved_ip}:{local_port}",
            ],
            False,
            "",
            resolved_ip,
        )

    @classmethod
    def match_log_error(cls, line: str, is_custom: bool = False) -> str:
        low = str(line or "").lower()
        for needle, friendly in cls.LOG_ERROR_RULES:
            if needle in low:
                return friendly
        return ""

    @classmethod
    def get_exe_path(cls, config: AppConfig) -> str:
        cache_dir = CacheManager.get_effective_cache_dir(config)
        return os.path.join(cache_dir, "bin", "cloudflared.exe")

    @classmethod
    def is_component_ready(cls, config: AppConfig) -> tuple[bool, str]:
        exe_path = cls.get_exe_path(config)
        try:
            ok = os.path.isfile(exe_path) and os.path.getsize(exe_path) > cls.MIN_EXE_BYTES
        except Exception:
            ok = False
        return ok, exe_path

    @classmethod
    def generate_security_token(cls, length: int = 6) -> str:
        return "".join(secrets.choice(cls.TOKEN_ALPHABET) for _ in range(length))

    def get_snapshot(self) -> dict:
        with self._lock:
            proc = self._proc
            state = self._state
            status_text = self._status_text
            ready_tip = self._ready_tip
            edge_ready = self._edge_ready
            dl_pct = self._download_pct
            pub_url = self._public_base_url
            tok = self._active_token
            prewarm_only = self._prewarm_only
        alive = False
        if proc is not None:
            try:
                alive = proc.poll() is None
            except Exception:
                alive = False
        if state == "ready" and not alive:
            state = "idle"
            pub_url = ""
            tok = ""
            ready_tip = ""
            edge_ready = False
            prewarm_only = False
        return {
            "state": state,
            "status_text": status_text,
            "ready_tip": ready_tip,
            "edge_ready": edge_ready,
            "download_pct": dl_pct,
            "public_base_url": pub_url,
            "token": tok,
            "alive": alive,
            "prewarm_only": prewarm_only,
        }

    def is_running(self) -> bool:
        with self._lock:
            proc = self._proc
            cancel_ev = self._cancel_event
        try:
            if proc is not None and proc.poll() is None:
                return True
        except Exception:
            pass
        if cancel_ev is not None and not cancel_ev.is_set() and _has_active_cloudflared_proc():
            return True
        return False

    def is_prewarm_only(self) -> bool:
        snap = self.get_snapshot()
        return bool(snap.get("prewarm_only")) and snap.get("state") in ("connecting", "ready")

    def is_active(self) -> bool:
        snap = self.get_snapshot()
        return snap["state"] in ("downloading", "connecting", "ready") or self.is_running()

    def promote_prewarm(self, on_prepare_token=None) -> dict:
        """用户切换至【互联网】模式时，原子复用后台静默预热中/已就绪的同一个隧道进程，绝不销毁重建。"""
        with self._lock:
            proc = self._proc
            state = self._state
            pub_url = self._public_base_url
            tok = self._active_token
            ready_tip = self._ready_tip
            edge_ready = self._edge_ready
            status_text = self._status_text
            alive = False
            if proc is not None:
                try:
                    alive = proc.poll() is None
                except Exception:
                    alive = False
            if state == "ready" and alive and pub_url and tok:
                self._prewarm_only = False
                if on_prepare_token is not None:
                    self._on_prepare_token = on_prepare_token
                result = {
                    "status": "ready",
                    "public_base_url": pub_url,
                    "token": tok,
                    "ready_tip": ready_tip,
                    "edge_ready": edge_ready,
                }
            elif state == "connecting" and (proc is None or alive):
                self._prewarm_only = False
                if on_prepare_token is not None:
                    self._on_prepare_token = on_prepare_token
                result = {
                    "status": "connecting",
                    "status_text": status_text or "正在打通安全公网隧道...",
                }
            else:
                result = {"status": "none"}

        if result["status"] == "ready" and on_prepare_token is not None:
            try:
                on_prepare_token(result["token"])
            except Exception:
                pass
        return result

    def stop_all(self) -> None:
        with self._lock:
            self._session_id += 1
            cancel_ev = self._cancel_event
            self._cancel_event = None
            proc = self._proc
            self._proc = None
            self._state = "idle"
            self._status_text = ""
            self._ready_tip = ""
            self._edge_ready = False
            self._download_pct = 0.0
            self._public_base_url = ""
            self._active_token = ""
            self._prewarm_only = False
            self._on_prepare_token = None

        if cancel_ev is not None:
            cancel_ev.set()

        if proc is not None:
            with _ACTIVE_TUNNEL_PROCS_LOCK:
                _ACTIVE_TUNNEL_PROCS.discard(proc)
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.2)
                    except Exception:
                        proc.kill()
            except Exception:
                pass

    def start_download(self, target_path: str) -> None:
        self.stop_all()
        with self._lock:
            sid = self._session_id
            cancel_ev = threading.Event()
            self._cancel_event = cancel_ev
            self._state = "downloading"
            self._download_pct = 0.0
            self._status_text = "正在下载跨网穿透组件 0%..."

        def _worker() -> None:
            part_path = target_path + ".part"
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            last_err = "下载失败"
            headers = {
                "User-Agent": FastDownloader.USER_AGENT,
                "Accept": "*/*",
            }
            for idx, url in enumerate(self.DOWNLOAD_URLS):
                if cancel_ev.is_set():
                    return
                src_label = "加速镜像" if idx < len(self.DOWNLOAD_URLS) - 1 else "官方源"
                with self._lock:
                    if sid == self._session_id:
                        self._status_text = f"正在连接{src_label}下载组件..."
                self.download_progress.emit(0.0, f"正在连接{src_label}下载组件...")
                try:
                    with requests.get(url, headers=headers, stream=True, timeout=(12, 30)) as resp:
                        if resp.status_code != 200:
                            last_err = f"HTTP {resp.status_code}"
                            continue
                        total = int(resp.headers.get("Content-Length") or 0)
                        got = 0
                        last_emit = 0.0
                        with open(part_path, "wb") as fh:
                            for chunk in resp.iter_content(chunk_size=65536):
                                if cancel_ev.is_set():
                                    break
                                if not chunk:
                                    continue
                                fh.write(chunk)
                                got += len(chunk)
                                now = time.monotonic()
                                if now - last_emit >= 0.08:
                                    last_emit = now
                                    if total > 0:
                                        pct = min(99.0, (got * 100.0) / total)
                                        stxt = f"正在下载跨网穿透组件 {int(pct)}%..."
                                    else:
                                        pct = 50.0
                                        mb = got / (1024 * 1024)
                                        stxt = f"正在下载组件 {mb:.1f} MB..."
                                    with self._lock:
                                        if sid == self._session_id:
                                            self._download_pct = pct
                                            self._status_text = stxt
                                    self.download_progress.emit(pct, stxt)
                        if cancel_ev.is_set():
                            try:
                                if os.path.exists(part_path):
                                    os.remove(part_path)
                            except Exception:
                                pass
                            return
                        actual = os.path.getsize(part_path) if os.path.exists(part_path) else 0
                        if actual <= self.MIN_EXE_BYTES:
                            last_err = f"下载文件不完整 ({actual} B)"
                            try:
                                os.remove(part_path)
                            except Exception:
                                pass
                            continue
                        os.replace(part_path, target_path)
                        with self._lock:
                            if sid != self._session_id:
                                return
                            self._download_pct = 100.0
                            self._status_text = "组件下载完成，正在启动隧道..."
                        self.download_progress.emit(100.0, "组件下载完成，正在启动隧道...")
                        self.download_finished.emit(target_path)
                        return
                except Exception as exc:
                    last_err = f"{type(exc).__name__}: {exc}"
                    try:
                        if os.path.exists(part_path):
                            os.remove(part_path)
                    except Exception:
                        pass
                    continue

            with self._lock:
                if sid != self._session_id or cancel_ev.is_set():
                    return
                self._state = "idle"
            self.download_failed.emit(last_err)

        threading.Thread(target=_worker, daemon=True).start()

    def start_tunnel(
        self,
        exe_path: str,
        local_port: int,
        on_prepare_token=None,
        cf_tunnel_token: str = "",
        cf_custom_domain: str = "",
        handshake_timeout_sec: float | None = None,
        silent_prewarm: bool = False,
        origin_ip: str = "",
        edge_register_timeout_sec: float | None = None,
    ) -> None:
        self.stop_all()
        cmd, is_custom, custom_domain, resolved_origin_ip = self.build_tunnel_cmd(
            exe_path=exe_path,
            local_port=local_port,
            cf_tunnel_token=cf_tunnel_token,
            cf_custom_domain=cf_custom_domain,
            origin_ip=origin_ip,
        )
        timeout_val = (
            self.HANDSHAKE_TIMEOUT_SEC
            if handshake_timeout_sec is None
            else max(0.5, float(handshake_timeout_sec))
        )
        edge_reg_timeout = (
            self.EDGE_REGISTER_TIMEOUT_SEC
            if edge_register_timeout_sec is None
            else max(0.5, float(edge_register_timeout_sec))
        )
        init_status = "正在连接自定义固定隧道..." if is_custom else "正在极速打通公网隧道..."

        with self._lock:
            sid = self._session_id
            cancel_ev = threading.Event()
            self._cancel_event = cancel_ev
            self._state = "connecting"
            self._status_text = init_status
            self._ready_tip = ""
            self._edge_ready = False
            self._prewarm_only = bool(silent_prewarm)
            self._on_prepare_token = None if silent_prewarm else on_prepare_token

        def _worker() -> None:
            env = self.build_tunnel_env(resolved_origin_ip)
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception as exc:
                err_text = f"启动穿透进程失败：{exc}"
                with self._lock:
                    if sid != self._session_id or cancel_ev.is_set():
                        return
                    is_silent = self._prewarm_only
                    if is_silent:
                        self._state = "idle"
                        self._status_text = ""
                        self._prewarm_only = False
                        return
                    self._state = "error"
                    self._status_text = err_text
                self.tunnel_failed.emit(err_text)
                return

            with self._lock:
                if sid != self._session_id or cancel_ev.is_set():
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    return
                self._proc = proc
            with _ACTIVE_TUNNEL_PROCS_LOCK:
                _ACTIVE_TUNNEL_PROCS.add(proc)

            # 独立读线程始终执行 while True: proc.stdout.readline() 持续排空输出管道，
            # 绝不因捕获 URL 而中断读取，彻底避免 Windows 4KB PIPE 缓冲区写满导致 cloudflared 假死报 1033
            line_q: "queue.Queue[str | None]" = queue.Queue()

            def _reader() -> None:
                try:
                    stream = proc.stdout
                    if stream is not None:
                        while True:
                            raw_line = stream.readline()
                            if not raw_line:
                                break
                            if not cancel_ev.is_set():
                                line_q.put(raw_line)
                except Exception:
                    pass
                finally:
                    line_q.put(None)

            threading.Thread(target=_reader, daemon=True).start()

            found_url = custom_domain if is_custom else ""
            ready_now = False
            edge_ready = False
            err_msg = ""
            last_log_line = ""
            last_err_line = ""
            wait_limit = min(timeout_val, self.CUSTOM_READY_MAX_WAIT_SEC) if is_custom else timeout_val
            deadline = time.monotonic() + wait_limit

            # 阶段 1：等待捕获公网 URL（免费模式捕获即刻出码；自定义模式等待注册或 1.0s 秒出）
            while not cancel_ev.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    if is_custom and found_url and not err_msg and proc.poll() is None:
                        ready_now = True
                    break
                try:
                    line = line_q.get(timeout=min(0.15, remaining))
                except queue.Empty:
                    if proc.poll() is not None:
                        break
                    continue

                if line is None:
                    break

                stripped = line.strip()
                if stripped:
                    last_log_line = stripped
                    low = stripped.lower()
                    if any(k in low for k in ("err", "error", "fail", "fatal")):
                        last_err_line = stripped
                    if self.EDGE_REGISTERED_RE.search(stripped):
                        edge_ready = True

                matched_err = self.match_log_error(line, is_custom=is_custom)
                if matched_err:
                    err_msg = matched_err
                    break

                if not is_custom:
                    # 免费 Quick Tunnel：正则捕获 *.trycloudflare.com 即刻通知主线程出码
                    m = self.TRY_URL_RE.search(line)
                    if m:
                        found_url = m.group(0).rstrip("/")
                        ready_now = True
                        break
                else:
                    if edge_ready:
                        ready_now = True
                        break

            with self._lock:
                still_valid = sid == self._session_id and not cancel_ev.is_set()
            if not still_valid:
                return

            if ready_now and found_url:
                token = self.generate_security_token(6)
                init_tip = self.EDGE_READY_TIP if edge_ready else self.EDGE_ACTIVATING_TIP
                with self._lock:
                    still_valid = sid == self._session_id and not cancel_ev.is_set()
                    if not still_valid:
                        return
                    self._state = "ready"
                    self._edge_ready = edge_ready
                    self._status_text = init_tip
                    self._ready_tip = init_tip
                    self._public_base_url = found_url
                    self._active_token = token
                    is_silent = self._prewarm_only
                    prep_cb = self._on_prepare_token

                if not is_silent:
                    if prep_cb is not None:
                        try:
                            prep_cb(token)
                        except Exception:
                            pass
                    self.tunnel_ready.emit(found_url, token, init_tip)

                # 阶段 2：持续消费并监测后续日志（同步边缘注册成功 + 10s 注册超时监测 + 进程异常退出兜底）
                reg_deadline = time.monotonic() + edge_reg_timeout
                reg_timed_out = False
                while not cancel_ev.is_set():
                    if not edge_ready and time.monotonic() > reg_deadline:
                        reg_timed_out = True
                        break
                    try:
                        line = line_q.get(timeout=0.3)
                    except queue.Empty:
                        if proc.poll() is not None:
                            break
                        continue

                    if line is None:
                        break

                    stripped = line.strip()
                    if not stripped:
                        continue
                    last_log_line = stripped
                    low = stripped.lower()
                    if any(k in low for k in ("err", "error", "fail", "fatal")):
                        last_err_line = stripped

                    if not edge_ready and self.EDGE_REGISTERED_RE.search(stripped):
                        edge_ready = True
                        with self._lock:
                            if sid != self._session_id or cancel_ev.is_set():
                                return
                            self._edge_ready = True
                            self._ready_tip = self.EDGE_READY_TIP
                            self._status_text = self.EDGE_READY_TIP
                            cur_silent = self._prewarm_only
                        if not cur_silent:
                            self.edge_state_changed.emit("ready", self.EDGE_READY_TIP)

                # 进程在未被用户主动停止的情况下退出或 10s 未完成注册 -> 清理并上报真实原因与重新连接按钮
                with self._lock:
                    still_valid = sid == self._session_id and not cancel_ev.is_set()
                    cur_silent = self._prewarm_only
                    prep_cb = self._on_prepare_token
                if not still_valid:
                    return

                if reg_timed_out:
                    crash_log = (last_err_line or self.EDGE_TIMEOUT_ERROR).strip()
                else:
                    crash_log = (last_err_line or last_log_line or "cloudflared 进程异常退出").strip()
                if len(crash_log) > 140:
                    crash_log = crash_log[:137] + "..."
                self.stop_all()
                if cur_silent:
                    return
                with self._lock:
                    self._state = "error"
                    self._status_text = crash_log
                if prep_cb is not None:
                    try:
                        prep_cb("")
                    except Exception:
                        pass
                self.tunnel_failed.emit(crash_log)
                return

            # 阶段 1 未捕获到 URL 即失败或超时：若进程已异常退出则优先展示真实最后一行错误日志
            if proc.poll() is not None:
                real_err = (last_err_line or last_log_line or err_msg or "cloudflared 进程异常退出").strip()
                if len(real_err) > 140:
                    real_err = real_err[:137] + "..."
                err_msg = real_err
            elif not err_msg:
                err_msg = self.CUSTOM_TIMEOUT_ERROR if is_custom else self.DEFAULT_TIMEOUT_ERROR

            with self._lock:
                is_silent = self._prewarm_only
                prep_cb = self._on_prepare_token

            self.stop_all()
            if is_silent:
                return

            with self._lock:
                self._state = "error"
                self._status_text = err_msg
            if prep_cb is not None:
                try:
                    prep_cb("")
                except Exception:
                    pass
            self.tunnel_failed.emit(err_msg)

        threading.Thread(target=_worker, daemon=True).start()


class _DesktopImagePreviewDialog(QDialog):
    """桌面端图片气泡大图预览弹窗。"""

    def __init__(self, image_path: str, is_light: bool, accent_color: str, parent=None):
        super().__init__(parent)
        self._image_path = image_path
        self._drag_pos: QPoint | None = None
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)

        bg = "#F5F6F8" if is_light else "#16161B"
        border = "#DCDFE6" if is_light else "#2C2C36"
        fg = "#1D1E22" if is_light else "#F5F5F7"
        pill_bg = "#ECEDF2" if is_light else "#22222A"
        pill_hover = "#E2E4EC" if is_light else "#2D2D38"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(self)
        card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 14px; }}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(10)

        top = QHBoxLayout()
        lbl_name = QLabel(os.path.basename(image_path), card)
        lbl_name.setFont(get_source_han_font(9, QFont.Weight.Bold))
        lbl_name.setStyleSheet(f"color: {fg}; border: none;")
        btn_close = QPushButton("✕", card)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {fg}; border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ background-color: {pill_hover}; }}"
        )
        btn_close.clicked.connect(self.close)
        top.addWidget(lbl_name, 1)
        top.addWidget(btn_close)
        cl.addLayout(top)

        pm = QPixmap(image_path)
        screen = QApplication.primaryScreen()
        max_w = int(screen.availableGeometry().width() * 0.72) if screen else 860
        max_h = int(screen.availableGeometry().height() * 0.72) if screen else 620
        img_lbl = QLabel(card)
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet("border: none; background: transparent;")
        if not pm.isNull():
            if pm.width() > max_w or pm.height() > max_h:
                pm = pm.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            img_lbl.setPixmap(pm)
        else:
            img_lbl.setText("无法加载图片")
        cl.addWidget(img_lbl)

        bot = QHBoxLayout()
        bot.addStretch(1)
        btn_locate = QPushButton("在文件夹中显示", card)
        btn_locate.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_locate.setFixedHeight(28)
        btn_locate.setFont(get_source_han_font(8, QFont.Weight.Bold))
        btn_locate.setStyleSheet(
            f"QPushButton {{ background-color: {pill_bg}; color: {fg}; border: 1px solid {border}; border-radius: 7px; padding: 0px 12px; }}"
            f"QPushButton:hover {{ border-color: {accent_color}; color: {accent_color}; }}"
        )
        btn_locate.clicked.connect(self._locate_file)
        bot.addWidget(btn_locate)
        cl.addLayout(bot)

        outer.addWidget(card)
        self.adjustSize()

    def _locate_file(self) -> None:
        if os.path.isfile(self._image_path):
            try:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(self._image_path)])
            except Exception:
                try:
                    os.startfile(os.path.dirname(self._image_path))
                except Exception:
                    pass

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class _DesktopEmojiPopup(QFrame):
    """仿微信 PC 桌面端迷你 Emoji 表情选择浮层。"""

    emoji_selected = Signal(str)

    EMOJIS = (
        "😀", "😁", "😂", "🤣", "😊", "😎", "😍", "🥳",
        "🤔", "😅", "😭", "😤", "🥺", "😱", "😴", "🤗",
        "👍", "👎", "👌", "✌️", "🤝", "👏", "🙏", "💪",
        "❤️", "🔥", "✨", "🎉", "💯", "⚡", "📌", "📎",
        "📁", "💻", "📱", "☕", "🍵", "🚀", "✅", "❗",
    )

    def __init__(self, is_light: bool, accent_color: str, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._is_light = is_light
        self._accent = accent_color

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame(self)
        grid = QGridLayout(self._card)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(2)
        self._btns: list[QPushButton] = []
        for idx, em in enumerate(self.EMOJIS):
            b = QPushButton(em, self._card)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedSize(28, 28)
            b.setFont(QFont("Segoe UI Emoji", 12))
            b.clicked.connect(lambda checked=False, ch=em: self._pick(ch))
            grid.addWidget(b, idx // 8, idx % 8)
            self._btns.append(b)
        outer.addWidget(self._card)
        self.apply_theme(is_light, accent_color)
        self.adjustSize()

    def _pick(self, ch: str) -> None:
        self.emoji_selected.emit(ch)
        self.hide()

    def apply_theme(self, is_light: bool, accent_color: str) -> None:
        self._is_light = is_light
        self._accent = accent_color
        bg = "#FFFFFF" if is_light else "#1F1F27"
        border = "#DCDFE6" if is_light else "#32323E"
        hover = "#ECEDF2" if is_light else "#2D2D3A"
        self._card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 10px; }}")
        btn_qss = (
            f"QPushButton {{ background: transparent; border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ background-color: {hover}; }}"
        )
        for b in self._btns:
            b.setStyleSheet(btn_qss)


class _WeChatInputEdit(QTextEdit):
    """仿微信 PC 超级输入框：Enter 发送、Shift+Enter 换行、Ctrl+V 智能拦截本地文件与剪贴板图片直接发送。"""

    send_requested = Signal()
    files_pasted = Signal(list)
    image_pasted = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setPlaceholderText("输入消息，Enter 发送，Ctrl+V 可直接粘贴图片或文件...")

    def _try_intercept_clipboard_media(self) -> bool:
        # 1. 优先检查 Qt 剪贴板 URL 文件列表
        cb = QApplication.clipboard()
        if cb is not None:
            mime = cb.mimeData()
            if mime is not None and mime.hasUrls():
                local_files = [u.toLocalFile() for u in mime.urls() if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
                if local_files:
                    self.files_pasted.emit(local_files)
                    return True

        # 2. 通过 PIL.ImageGrab.grabclipboard() 捕获 Windows CF_HDROP 文件列表或截图图像
        try:
            from PIL import Image, ImageGrab

            grabbed = ImageGrab.grabclipboard()
            if isinstance(grabbed, list):
                local_files = [str(p) for p in grabbed if isinstance(p, str) and os.path.isfile(p)]
                if local_files:
                    self.files_pasted.emit(local_files)
                    return True
            elif isinstance(grabbed, Image.Image):
                self.image_pasted.emit(grabbed)
                return True
        except Exception:
            pass

        # 3. 兜底检查 Qt 剪贴板图像
        if cb is not None:
            mime = cb.mimeData()
            if mime is not None and mime.hasImage():
                qimg = cb.image()
                if not qimg.isNull():
                    self.image_pasted.emit(qimg)
                    return True
        return False

    def keyPressEvent(self, event) -> None:
        key = event.key()
        mods = event.modifiers()
        # Ctrl+V：优先拦截文件或截图并直接发送，纯文本走默认粘贴
        if key == Qt.Key.Key_V and (mods & Qt.KeyboardModifier.ControlModifier):
            if self._try_intercept_clipboard_media():
                event.accept()
                return
            super().keyPressEvent(event)
            return
        # Alt+S 快捷发送
        if key == Qt.Key.Key_S and (mods & Qt.KeyboardModifier.AltModifier):
            self.send_requested.emit()
            event.accept()
            return
        # Enter 发送 / Shift+Enter 换行
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
                event.accept()
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source) -> None:
        if source is not None:
            if source.hasUrls():
                local_files = [u.toLocalFile() for u in source.urls() if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
                if local_files:
                    self.files_pasted.emit(local_files)
                    return
            if source.hasText():
                self.insertPlainText(source.text())
                return
        super().insertFromMimeData(source)


class _ClickableChatBubble(QFrame):
    """可点击聊天气泡容器（继承 QFrame 以使内部 QVBoxLayout 正常参与 sizeHint 计算，彻底避免 QPushButton 嵌套布局导致单字竖排与截断）。"""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class LanTransferDialog(QDialog):
    """连接手机管理弹窗：上半部保持双模开关+二维码+安全提示不变，下半部接入仿微信 PC 桌面双向聊天框。"""

    def __init__(
        self,
        server: LanTransferServer,
        config: AppConfig,
        theme_mode: str,
        accent_color: str,
        on_copy_url=None,
        on_share_clipboard=None,
        on_mode_changed=None,
        on_toast=None,
        on_request_screenshot=None,
        tunnel_mgr: CloudflaredTunnelManager | None = None,
        initial_loading: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._server = server
        self._config = config
        self._is_light = theme_mode == "light"
        self._accent = accent_color
        self._on_copy_url = on_copy_url
        self._on_share_clipboard = on_share_clipboard
        self._on_mode_changed = on_mode_changed
        self._on_toast = on_toast
        self._on_request_screenshot = on_request_screenshot
        self._drag_pos: QPoint | None = None

        self._initial_loading: bool = bool(initial_loading)
        self._mode: str = "lan"  # "lan" | "internet"
        self._active_url: str = "" if self._initial_loading else server.get_url()
        self._internet_token: str = ""
        self._last_chat_sig: list[tuple[str, str]] = []
        self._emoji_popup: _DesktopEmojiPopup | None = None
        self._preview_dlgs: list[_DesktopImagePreviewDialog] = []
        self._signals_detached: bool = False
        self._qr_req_seq: int = 0
        self._qr_cache: dict[str, QPixmap] = {}
        self._img_thumb_cache: dict[str, QPixmap] = {}
        self._qr_bridge = _LanAsyncBridge(self)
        self._qr_bridge.qr_ready.connect(self._on_async_qr_ready)

        self._tunnel_mgr = tunnel_mgr if tunnel_mgr is not None else CloudflaredTunnelManager(self)
        self._tunnel_mgr.download_progress.connect(self._on_cf_download_progress)
        self._tunnel_mgr.download_finished.connect(self._on_cf_download_finished)
        self._tunnel_mgr.download_failed.connect(self._on_cf_download_failed)
        self._tunnel_mgr.tunnel_status.connect(self._on_tunnel_status)
        self._tunnel_mgr.tunnel_ready.connect(self._on_tunnel_ready)
        self._tunnel_mgr.edge_state_changed.connect(self._on_edge_state_changed)
        self._tunnel_mgr.tunnel_failed.connect(self._on_tunnel_failed)

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(MAIN_WIDTH, 636)

        bg = "#F5F6F8" if self._is_light else "#18181D"
        border = "#DCDFE6" if self._is_light else "#2C2C36"
        fg = "#1D1E22" if self._is_light else "#F5F5F7"
        muted = "#6E707A" if self._is_light else "#9A9AA6"
        pill_bg = "#ECEDF2" if self._is_light else "#22222A"
        pill_hover = "#E2E4EC" if self._is_light else "#2D2D38"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(self)
        card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 12)
        cl.setSpacing(8)

        # ==================== 上半部分：完全保持原有双模开关 + 二维码 + 网址 + 安全提示不变 ====================
        top = QHBoxLayout()
        top.setSpacing(8)

        self._mode_seg_box = QFrame(card)
        self._mode_seg_box.setFixedHeight(30)
        seg_l = QHBoxLayout(self._mode_seg_box)
        seg_l.setContentsMargins(3, 3, 3, 3)
        seg_l.setSpacing(3)

        self._btn_mode_lan = QPushButton(" 局域网", self._mode_seg_box)
        self._btn_mode_lan.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_mode_lan.setFixedHeight(24)
        self._btn_mode_lan.setIconSize(QSize(13, 13))
        self._btn_mode_lan.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._btn_mode_lan.setToolTip("同一 Wi-Fi 下局域网极速直连")
        self._btn_mode_lan.clicked.connect(lambda: self._on_select_mode("lan"))

        self._btn_mode_net = QPushButton(" 互联网", self._mode_seg_box)
        self._btn_mode_net.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_mode_net.setFixedHeight(24)
        self._btn_mode_net.setIconSize(QSize(13, 13))
        self._btn_mode_net.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._btn_mode_net.setToolTip("支持手机 5G 流量跨网远程访问（带安全码校验）")
        self._btn_mode_net.clicked.connect(lambda: self._on_select_mode("internet"))

        seg_l.addWidget(self._btn_mode_lan)
        seg_l.addWidget(self._btn_mode_net)

        win_btn_qss = (
            f"QPushButton {{ background: transparent; color: {muted}; border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ background-color: {pill_hover}; color: {fg}; }}"
        )
        btn_min = QPushButton("—", card)
        btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_min.setFixedSize(22, 22)
        btn_min.setToolTip("最小化")
        btn_min.setStyleSheet(win_btn_qss)
        btn_min.clicked.connect(self.showMinimized)

        btn_close = QPushButton("✕", card)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setFixedSize(22, 22)
        btn_close.setStyleSheet(win_btn_qss)
        btn_close.clicked.connect(self.close)
        top.addWidget(self._mode_seg_box)
        top.addStretch(1)
        top.addWidget(btn_min)
        top.addWidget(btn_close)
        cl.addLayout(top)

        # 二维码 / 加载动画 / 失败重试切换容器（148x148）
        self._qr_stack = QStackedWidget(card)
        self._qr_stack.setFixedSize(148, 148)

        self.qr_lbl = QLabel(self._qr_stack)
        self.qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_lbl.setFixedSize(148, 148)
        self.qr_lbl.setStyleSheet(
            f"background-color: {pill_bg}; border: 1px solid {border}; border-radius: 10px; padding: 6px;"
        )

        self._loading_spinner = _TunnelLoadingSpinner(
            accent_color=accent_color,
            is_light=self._is_light,
            parent=self._qr_stack,
        )

        self._error_box = QFrame(self._qr_stack)
        self._error_box.setFixedSize(148, 148)
        eb_l = QVBoxLayout(self._error_box)
        eb_l.setContentsMargins(10, 14, 10, 14)
        eb_l.setSpacing(8)
        eb_l.addStretch(1)
        self._lbl_err_title = QLabel("连接异常", self._error_box)
        self._lbl_err_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_err_title.setFont(get_source_han_font(9, QFont.Weight.Bold))
        self._lbl_err_sub = QLabel("请查看下方原因或重试", self._error_box)
        self._lbl_err_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_err_sub.setFont(get_source_han_font(7))
        self._lbl_err_sub.setWordWrap(True)
        self._btn_retry_tunnel = QPushButton("重新连接", self._error_box)
        self._btn_retry_tunnel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_retry_tunnel.setFixedHeight(26)
        self._btn_retry_tunnel.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._btn_retry_tunnel.clicked.connect(self._retry_internet_tunnel)
        eb_l.addWidget(self._lbl_err_title)
        eb_l.addWidget(self._lbl_err_sub)
        eb_l.addWidget(self._btn_retry_tunnel)
        eb_l.addStretch(1)

        self._proxy_block_box = QFrame(self._qr_stack)
        self._proxy_block_box.setFixedSize(148, 148)
        pb_l = QVBoxLayout(self._proxy_block_box)
        pb_l.setContentsMargins(12, 14, 12, 14)
        pb_l.setSpacing(6)
        pb_l.addStretch(1)

        self._lbl_proxy_block_icon = QLabel(self._proxy_block_box)
        self._lbl_proxy_block_icon.setFixedSize(28, 28)
        self._lbl_proxy_block_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_proxy_block_icon.setStyleSheet("border: none; background: transparent;")
        pb_l.addWidget(self._lbl_proxy_block_icon, 0, Qt.AlignmentFlag.AlignHCenter)

        self._lbl_proxy_block_title = QLabel("暂无法开启公网连接", self._proxy_block_box)
        self._lbl_proxy_block_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_proxy_block_title.setFont(get_source_han_font(9, QFont.Weight.Bold))
        pb_l.addWidget(self._lbl_proxy_block_title)

        self._lbl_proxy_block_msg = QLabel(
            "检测到代理或 TUN 模式，请关闭后重试",
            self._proxy_block_box,
        )
        self._lbl_proxy_block_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_proxy_block_msg.setFont(get_source_han_font(7))
        self._lbl_proxy_block_msg.setWordWrap(True)
        pb_l.addWidget(self._lbl_proxy_block_msg)
        pb_l.addStretch(1)

        self._qr_stack.addWidget(self.qr_lbl)
        self._qr_stack.addWidget(self._loading_spinner)
        self._qr_stack.addWidget(self._error_box)
        self._qr_stack.addWidget(self._proxy_block_box)
        self._qr_stack.setCurrentIndex(0)

        qr_row = QHBoxLayout()
        qr_row.addStretch(1)
        qr_row.addWidget(self._qr_stack)
        qr_row.addStretch(1)
        cl.addLayout(qr_row)

        # 访问地址（严格居中对齐，右键菜单「复制网址」，移除独立复制按钮与明文安全码提示）
        lbl_url = QLabel(self._active_url, card)
        lbl_url.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_url.setFixedHeight(20)
        lbl_url.setFont(get_source_han_font(8, QFont.Weight.Bold))
        lbl_url.setCursor(Qt.CursorShape.PointingHandCursor)
        lbl_url.setStyleSheet(f"color: {accent_color}; border: none; background: transparent;")
        lbl_url.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        lbl_url.customContextMenuRequested.connect(self._show_url_context_menu)
        cl.addWidget(lbl_url)

        # 保留隐藏占位引用避免外部属性访问报错，界面上彻底隐藏校验码与冗余提示栏
        self._lbl_token_badge = QLabel("", card)
        self._lbl_token_badge.setVisible(False)
        self._lbl_tunnel_tip = QLabel("", card)
        self._lbl_tunnel_tip.setVisible(False)
        self._lbl_proxy_warn = QLabel("", card)
        self._lbl_proxy_warn.setVisible(False)

        # ==================== 细分割线：下方全部为仿微信 PC 桌面版聊天区域 ====================
        self._chat_top_divider = QFrame(card)
        self._chat_top_divider.setFixedHeight(1)
        cl.addWidget(self._chat_top_divider)

        # 中间：仿微信 PC 双向聊天气泡流（固定高度，确保切换模式/收发消息/代理提示时高度稳定不变形）
        self._chat_scroll = QScrollArea(card)
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._chat_scroll.setFixedHeight(284)
        self._chat_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._chat_box = QWidget()
        self._chat_layout = QVBoxLayout(self._chat_box)
        self._chat_layout.setContentsMargins(6, 8, 6, 8)
        self._chat_layout.setSpacing(10)
        self._chat_layout.addStretch(1)
        self._chat_scroll.setWidget(self._chat_box)
        cl.addWidget(self._chat_scroll)

        # 底部：细分割线 + 微信 PC 快捷图标工具条 + 超级输入框 + 发送(S)
        self._chat_bot_divider = QFrame(card)
        self._chat_bot_divider.setFixedHeight(1)
        cl.addWidget(self._chat_bot_divider)

        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(2, 0, 2, 0)
        toolbar_row.setSpacing(6)

        self._btn_chat_emoji = QPushButton(card)
        self._btn_chat_emoji.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_chat_emoji.setFixedSize(26, 24)
        self._btn_chat_emoji.setIconSize(QSize(15, 15))
        self._btn_chat_emoji.setToolTip("发送表情")
        self._btn_chat_emoji.clicked.connect(self._on_chat_emoji_clicked)

        self._btn_chat_file = QPushButton(card)
        self._btn_chat_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_chat_file.setFixedSize(26, 24)
        self._btn_chat_file.setIconSize(QSize(15, 15))
        self._btn_chat_file.setToolTip("发送文件给手机（支持多选）")
        self._btn_chat_file.clicked.connect(self._on_add_files)

        self._btn_chat_shot = QPushButton(card)
        self._btn_chat_shot.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_chat_shot.setFixedSize(26, 24)
        self._btn_chat_shot.setIconSize(QSize(15, 15))
        self._btn_chat_shot.setToolTip("截图并发送给手机")
        self._btn_chat_shot.clicked.connect(self._on_chat_screenshot_clicked)

        self._btn_open_recv = QPushButton("接收目录", card)
        self._btn_open_recv.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_recv.setFixedHeight(22)
        self._btn_open_recv.setFont(get_source_han_font(7))
        self._btn_open_recv.setToolTip("打开手机文件接收目录")
        self._btn_open_recv.clicked.connect(self._on_open_recv)

        toolbar_row.addWidget(self._btn_chat_emoji)
        toolbar_row.addWidget(self._btn_chat_file)
        toolbar_row.addWidget(self._btn_chat_shot)
        toolbar_row.addStretch(1)
        toolbar_row.addWidget(self._btn_open_recv)
        cl.addLayout(toolbar_row)

        self._chat_input = _WeChatInputEdit(card)
        self._chat_input.setFixedHeight(62)
        self._chat_input.setFont(get_source_han_font(9))
        self._chat_input.send_requested.connect(self._on_chat_send_text)
        self._chat_input.files_pasted.connect(self._on_chat_files_pasted)
        self._chat_input.image_pasted.connect(self._on_chat_image_pasted)
        cl.addWidget(self._chat_input)

        send_row = QHBoxLayout()
        send_row.setContentsMargins(2, 0, 2, 0)
        self._lbl_input_hint = QLabel("Enter 发送 · Shift+Enter 换行 · Ctrl+V 粘贴图/文件", card)
        self._lbl_input_hint.setFont(get_source_han_font(7))
        self._btn_chat_send = QPushButton("发送(S)", card)
        self._btn_chat_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_chat_send.setFixedSize(68, 26)
        self._btn_chat_send.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._btn_chat_send.clicked.connect(self._on_chat_send_text)
        send_row.addWidget(self._lbl_input_hint, 1)
        send_row.addWidget(self._btn_chat_send)
        cl.addLayout(send_row)

        self._card = card
        self._btn_min = btn_min
        self._btn_close = btn_close
        self._lbl_url = lbl_url

        outer.addWidget(card)
        # 每次打开【连接手机】窗口自动清空历史聊天会话（严格保留本地已接收文件）
        self._server.clear_chat_messages()
        self._apply_chat_styles()
        self._sync_initial_tunnel_view()
        self.refresh_chat_messages(force=True)

        # 定时增量同步手机/多端消息流（1s）
        self._chat_sync_timer = QTimer(self)
        self._chat_sync_timer.setInterval(1000)
        self._chat_sync_timer.timeout.connect(self.refresh_chat_messages)
        self._chat_sync_timer.start()

    def _sync_mode_chat_channel(self, mode: str, refresh: bool = True) -> None:
        """切换局域网/互联网模式时同步服务端当前通道并立即清空旧气泡、仅渲染目标模式聊天记录。"""
        norm = "internet" if str(mode or "").strip().lower() == "internet" else "lan"
        self._mode = norm
        self._server.set_active_mode(norm)
        self._last_chat_sig = []
        if refresh and hasattr(self, "_chat_layout"):
            self.refresh_chat_messages(force=True)

    def _sync_initial_tunnel_view(self) -> None:
        """打开/重开管理窗时：若本地服务正在异步启动则立即展示加载圈；否则复用已有互联网隧道或局域网地址。"""
        if self._initial_loading or not self._server.is_running():
            self._sync_mode_chat_channel("lan", refresh=False)
            self._internet_token = ""
            self._update_mode_segment_styles()
            self._show_loading_state(
                "正在获取局域网地址...",
                show_progress=False,
                progress=0.0,
                url_hint="正在获取局域网地址...",
            )
            return

        snap = self._tunnel_mgr.get_snapshot()
        state = snap.get("state", "idle")
        prewarm_only = bool(snap.get("prewarm_only"))
        if not prewarm_only and state in ("ready", "downloading", "connecting", "error"):
            if detect_proxy_or_tun():
                self._show_proxy_tun_blocked_state()
                return
        if not prewarm_only and state == "ready" and snap.get("public_base_url") and snap.get("token"):
            self._sync_mode_chat_channel("internet", refresh=False)
            self._internet_token = snap["token"]
            self._server.set_internet_token(self._internet_token)
            full_url = f"{snap['public_base_url']}/?token={self._internet_token}"
            self._update_mode_segment_styles()
            self._render_qr_and_url(full_url)
        elif not prewarm_only and state == "downloading":
            self._sync_mode_chat_channel("internet", refresh=False)
            self._update_mode_segment_styles()
            self._show_loading_state(
                snap.get("status_text") or "正在下载跨网穿透组件...",
                show_progress=True,
                progress=float(snap.get("download_pct") or 0.0),
            )
        elif not prewarm_only and state == "connecting":
            self._sync_mode_chat_channel("internet", refresh=False)
            self._update_mode_segment_styles()
            self._show_loading_state(
                snap.get("status_text") or "正在极速打通公网隧道...",
                show_progress=False,
                progress=0.0,
            )
        elif not prewarm_only and state == "error":
            self._sync_mode_chat_channel("internet", refresh=False)
            self._update_mode_segment_styles()
            self._show_error_state(snap.get("status_text") or CloudflaredTunnelManager.DEFAULT_TIMEOUT_ERROR)
        else:
            self._sync_mode_chat_channel("lan", refresh=False)
            self._internet_token = ""
            self._update_mode_segment_styles()
            self._render_qr_and_url(self._server.get_url())

    def on_lan_server_ready(self, lan_url: str, qr_pil_img=None) -> None:
        """后台线程完成网卡 IP 枚举、本地 HTTP 服务启动与二维码 PIL 渲染后，无缝替换为真实二维码与链接。"""
        self._initial_loading = False
        if self._mode == "lan":
            self._render_qr_and_url(lan_url, prebuilt_pil=qr_pil_img)

    def _apply_chat_styles(self) -> None:
        is_light = self._is_light
        acc = self._accent
        border = "#DCDFE6" if is_light else "#2C2C36"
        fg = "#1D1E22" if is_light else "#F5F5F7"
        muted = "#6E707A" if is_light else "#9A9AA6"
        chat_bg = "#ECEEF2" if is_light else "#121216"
        input_bg = "#FFFFFF" if is_light else "#1E1E26"
        pill_hover = "#E2E4EC" if is_light else "#2D2D38"
        scroll_handle = "#C5C8D4" if is_light else "#3A3A46"
        icon_col = "#5A5D6A" if is_light else "#A1A1AE"

        self._chat_top_divider.setStyleSheet(f"background-color: {border}; border: none;")
        self._chat_bot_divider.setStyleSheet(f"background-color: {border}; border: none;")
        self._chat_box.setStyleSheet(f"background-color: {chat_bg};")
        self._chat_scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background-color: {chat_bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {chat_bg};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 5px;
                margin: 2px 0px 2px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {scroll_handle};
                min-height: 22px;
                border-radius: 2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            """
        )
        tool_qss = (
            f"QPushButton {{ background: transparent; border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ background-color: {pill_hover}; }}"
            f"QPushButton:pressed {{ background-color: {'#D2D6E2' if is_light else '#383846'}; padding-top: 1px; }}"
        )
        for b, kind in (
            (self._btn_chat_emoji, "emoji"),
            (self._btn_chat_file, "folder"),
            (self._btn_chat_shot, "scissors"),
        ):
            b.setStyleSheet(tool_qss)
            b.setIcon(_make_tool_vector_icon(kind, icon_col))

        self._btn_open_recv.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {muted}; border: none; border-radius: 5px; padding: 0px 6px; }}"
            f"QPushButton:hover {{ background-color: {pill_hover}; color: {acc}; }}"
            f"QPushButton:pressed {{ background-color: {'#D2D6E2' if is_light else '#383846'}; color: {acc}; padding-top: 1px; }}"
        )
        self._chat_input.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {input_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 5px 8px;
            }}
            QTextEdit:focus {{
                border-color: {acc};
            }}
            """
        )
        self._lbl_input_hint.setStyleSheet(f"color: {muted}; border: none;")
        self._btn_chat_send.setStyleSheet(
            f"QPushButton {{ background-color: {acc}; color: #FFFFFF; border: none; border-radius: 7px; }}"
            f"QPushButton:hover {{ background-color: {QColor(acc).lighter(110).name()}; }}"
            f"QPushButton:pressed {{ background-color: {QColor(acc).darker(118).name()}; padding-top: 2px; padding-left: 1px; }}"
        )
        if self._emoji_popup is not None:
            self._emoji_popup.apply_theme(is_light, acc)

    def _update_mode_segment_styles(self) -> None:
        is_light = self._is_light
        acc = self._accent
        track_bg = "#E6E8F0" if is_light else "#23232C"
        track_border = "#D8DBE6" if is_light else "#30303C"
        inactive_fg = "#646775" if is_light else "#9A9AA8"
        hover_bg = "#DCDEE8" if is_light else "#2C2C38"

        self._mode_seg_box.setStyleSheet(
            f"QFrame {{ background-color: {track_bg}; border: 1px solid {track_border}; border-radius: 15px; }}"
        )
        active_qss = (
            f"QPushButton {{ background-color: {acc}; color: #FFFFFF; border: none; border-radius: 12px; padding: 0px 10px; }}"
        )
        inactive_qss = (
            f"QPushButton {{ background: transparent; color: {inactive_fg}; border: none; border-radius: 12px; padding: 0px 10px; }}"
            f"QPushButton:hover {{ background-color: {hover_bg}; }}"
        )

        is_lan = self._mode == "lan"
        self._btn_mode_lan.setStyleSheet(active_qss if is_lan else inactive_qss)
        self._btn_mode_net.setStyleSheet(inactive_qss if is_lan else active_qss)
        self._btn_mode_lan.setIcon(_make_tool_vector_icon("wifi", "#FFFFFF" if is_lan else inactive_fg))
        self._btn_mode_net.setIcon(_make_tool_vector_icon("globe", inactive_fg if is_lan else "#FFFFFF"))

        badge_bg = "#ECFDF5" if is_light else "#132920"
        badge_border = "#A7F3D0" if is_light else "#1F4D3A"
        self._lbl_token_badge.setStyleSheet(
            f"background-color: {badge_bg}; color: {GREEN_ACCENT}; border: 1px solid {badge_border}; border-radius: 6px; padding: 0px 8px;"
        )

        fg = "#1D1E22" if is_light else "#F5F5F7"
        muted = "#6E707A" if is_light else "#9A9AA6"
        border = "#DCDFE6" if is_light else "#2C2C36"
        pill_bg = "#ECEDF2" if is_light else "#22222A"

        self._error_box.setStyleSheet(
            f"QFrame {{ background-color: {pill_bg}; border: 1px solid {border}; border-radius: 10px; }}"
        )
        err_fg = "#DC2626" if is_light else "#F87171"
        self._lbl_err_title.setStyleSheet(f"color: {err_fg}; border: none; background: transparent;")
        self._lbl_err_sub.setStyleSheet(f"color: {muted}; border: none; background: transparent;")
        self._btn_retry_tunnel.setStyleSheet(
            f"QPushButton {{ background-color: {acc}; color: #FFFFFF; border: none; border-radius: 6px; padding: 0px 12px; }}"
            f"QPushButton:hover {{ background-color: {QColor(acc).lighter(110).name()}; }}"
            f"QPushButton:pressed {{ background-color: {QColor(acc).darker(118).name()}; padding-top: 2px; }}"
        )
        warn_bg = "#FFFBF2" if is_light else "#221D15"
        warn_bd = "#F3DFC1" if is_light else "#453823"
        warn_icon_col = "#D97706" if is_light else "#F59E0B"
        warn_title_fg = "#1F2329" if is_light else "#F5F5F7"
        warn_sub_fg = "#6E7380" if is_light else "#9A9AA8"
        self._proxy_block_box.setStyleSheet(
            f"QFrame {{ background-color: {warn_bg}; border: 1px solid {warn_bd}; border-radius: 12px; }}"
        )
        self._lbl_proxy_block_icon.setPixmap(_make_proxy_shield_pixmap(warn_icon_col, 28))
        self._lbl_proxy_block_title.setStyleSheet(
            f"color: {warn_title_fg}; border: none; background: transparent;"
        )
        self._lbl_proxy_block_msg.setStyleSheet(
            f"color: {warn_sub_fg}; border: none; background: transparent; padding: 0px 2px;"
        )

    def _refresh_proxy_warning(self) -> None:
        self._lbl_proxy_warn.setVisible(False)

    def _apply_tunnel_tip_style(self, kind: str = "info") -> None:
        self._lbl_tunnel_tip.setVisible(False)

    def _set_tunnel_tip(self, text: str, is_error: bool = False, kind: str | None = None) -> None:
        self._tunnel_tip_kind = kind if kind is not None else ("error" if is_error else "info")
        self._lbl_tunnel_tip.setText("")
        self._lbl_tunnel_tip.setVisible(False)

    def _show_proxy_tun_blocked_state(self) -> None:
        """检测到开启系统代理或 TUN 虚拟网卡模式：停止启动隧道、不生成二维码，原位居中提示关闭代理。"""
        self._tunnel_mgr.stop_all()
        self._loading_spinner.stop()
        self._sync_mode_chat_channel("internet", refresh=True)
        self._internet_token = ""
        self._server.set_internet_token("")
        self._active_url = ""
        self._update_mode_segment_styles()
        self._qr_stack.setCurrentIndex(3)
        self._lbl_url.setText("")
        self._lbl_url.setToolTip("")
        if self._on_mode_changed:
            self._on_mode_changed("internet", "", "")

    def _on_async_qr_ready(self, seq: int, url: str, pil_img) -> None:
        if seq != self._qr_req_seq or url != self._active_url:
            return
        pm = self._pil_to_qr_pixmap(pil_img, 134) if pil_img is not None else None
        if pm is not None:
            self._qr_cache[url] = pm
            self.qr_lbl.setPixmap(pm)
        else:
            self.qr_lbl.setText("QR 生成失败")
        self._loading_spinner.stop()
        self._qr_stack.setCurrentIndex(0)

    def _render_qr_and_url(self, url: str, prebuilt_pil=None) -> None:
        self._active_url = url
        self._qr_req_seq += 1
        pm = None
        if prebuilt_pil is not None:
            pm = self._pil_to_qr_pixmap(prebuilt_pil, 134)
            if pm is not None:
                self._qr_cache[url] = pm
        elif url in self._qr_cache:
            pm = self._qr_cache[url]
        else:
            pm = self._make_qr_pixmap(url, 134)
            if pm is not None:
                self._qr_cache[url] = pm
        self._loading_spinner.stop()
        self._qr_stack.setCurrentIndex(0)
        if pm is not None:
            self.qr_lbl.setPixmap(pm)
        else:
            self.qr_lbl.setText("QR 生成失败")
        fm = QFontMetrics(self._lbl_url.font())
        self._lbl_url.setText(fm.elidedText(url, Qt.TextElideMode.ElideMiddle, 326))
        self._lbl_url.setToolTip(f"{url}\n（右键点击复制网址）" if url else "")

    def _show_loading_state(
        self,
        text: str,
        show_progress: bool = False,
        progress: float = 0.0,
        url_hint: str = "正在准备安全公网地址...",
    ) -> None:
        self._loading_spinner.set_state(text, show_progress=show_progress, progress=progress)
        self._loading_spinner.start()
        self._qr_stack.setCurrentIndex(1)
        self._lbl_url.setText(url_hint)
        self._lbl_url.setToolTip("")
        self._lbl_token_badge.setVisible(False)
        self._set_tunnel_tip("", is_error=False)

    def _show_error_state(self, err_msg: str) -> None:
        self._loading_spinner.stop()
        self._qr_stack.setCurrentIndex(2)
        self._lbl_url.setText("公网隧道连接超时")
        self._lbl_url.setToolTip(err_msg)
        self._lbl_token_badge.setVisible(False)
        self._set_tunnel_tip("", is_error=True)

    def _start_internet_tunnel(self, cf_path: str) -> None:
        if detect_proxy_or_tun():
            self._show_proxy_tun_blocked_state()
            return
        tok = str(getattr(self._config, "cf_tunnel_token", "") or "").strip()
        dom = CloudflaredTunnelManager.normalize_custom_domain(getattr(self._config, "cf_custom_domain", ""))
        init_txt = "正在连接自定义固定隧道..." if (tok and dom) else "正在极速打通公网隧道..."
        self._show_loading_state(init_txt, show_progress=False, progress=0.0)
        self._tunnel_mgr.start_tunnel(
            cf_path,
            self._server.port,
            on_prepare_token=self._server.set_internet_token,
            cf_tunnel_token=tok,
            cf_custom_domain=dom,
            silent_prewarm=False,
            origin_ip=str(getattr(self._server, "ip", "") or ""),
        )

    def _retry_internet_tunnel(self) -> None:
        if self._initial_loading or not self._server.is_running():
            if self._on_toast:
                self._on_toast("本地服务正在启动中，请稍候片刻")
            return
        if detect_proxy_or_tun():
            self._show_proxy_tun_blocked_state()
            return
        ready, cf_path = CloudflaredTunnelManager.is_component_ready(self._config)
        if not ready:
            dlg = _CloudflaredDownloadConfirmDialog(
                target_path=cf_path,
                is_light=self._is_light,
                accent_color=self._accent,
                parent=self,
            )
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            self._sync_mode_chat_channel("internet", refresh=True)
            self._internet_token = ""
            self._server.set_internet_token("")
            self._update_mode_segment_styles()
            self._show_loading_state("正在下载跨网穿透组件 0%...", show_progress=True, progress=0.0)
            self._tunnel_mgr.start_download(cf_path)
            return

        self._sync_mode_chat_channel("internet", refresh=True)
        self._internet_token = ""
        self._server.set_internet_token("")
        self._update_mode_segment_styles()
        self._start_internet_tunnel(cf_path)

    def _on_select_mode(self, target_mode: str) -> None:
        if target_mode == self._mode:
            return
        if target_mode == "lan":
            self._switch_to_lan_mode()
            return

        if self._initial_loading or not self._server.is_running():
            if self._on_toast:
                self._on_toast("本地服务正在启动中，请稍候片刻")
            return

        # 切换到互联网模式前，前置检测系统代理与 TUN 虚拟网卡模式
        if detect_proxy_or_tun():
            self._show_proxy_tun_blocked_state()
            return

        # 优先零延迟复用后台静默预热中 / 已就绪的同一个隧道进程（绝不销毁重建）
        promo = self._tunnel_mgr.promote_prewarm(on_prepare_token=self._server.set_internet_token)
        if promo["status"] == "ready":
            self._sync_mode_chat_channel("internet", refresh=True)
            self._update_mode_segment_styles()
            self._on_tunnel_ready(
                promo["public_base_url"],
                promo["token"],
                promo.get("ready_tip", ""),
            )
            return
        if promo["status"] == "connecting":
            self._sync_mode_chat_channel("internet", refresh=True)
            self._internet_token = ""
            self._update_mode_segment_styles()
            self._show_loading_state(promo.get("status_text") or "正在极速打通公网隧道...", show_progress=False, progress=0.0)
            return

        # 若无预热进程（如组件尚未下载或此前已切回局域网），走实时校验与启动流程
        self._retry_internet_tunnel()

    def _switch_to_lan_mode(self) -> None:
        self._tunnel_mgr.stop_all()
        self._sync_mode_chat_channel("lan", refresh=True)
        self._internet_token = ""
        self._server.set_internet_token("")
        self._set_tunnel_tip("", is_error=False)
        self._update_mode_segment_styles()
        self._render_qr_and_url(self._server.get_url())
        lan_tok = self._server.get_active_token()
        if self._on_mode_changed:
            self._on_mode_changed("lan", self._server.get_url(), lan_tok)

    def _on_cf_download_progress(self, pct: float, status_text: str) -> None:
        if self._mode != "internet":
            return
        self._show_loading_state(status_text, show_progress=True, progress=pct)

    def _on_cf_download_finished(self, exe_path: str) -> None:
        if self._mode != "internet":
            return
        self._start_internet_tunnel(exe_path)

    def _on_cf_download_failed(self, err_msg: str) -> None:
        if self._mode != "internet":
            return
        self._show_error_state(f"穿透组件下载失败：{err_msg[:48]}，请点击重新连接")
        if self._on_toast:
            self._on_toast(f"组件下载失败：{err_msg[:36]}")

    def _on_tunnel_status(self, status_text: str) -> None:
        if self._mode != "internet":
            return
        self._show_loading_state(status_text, show_progress=False, progress=0.0)

    def _on_tunnel_ready(self, public_base_url: str, token: str, ready_tip: str = "") -> None:
        if self._mode != "internet":
            return
        if detect_proxy_or_tun():
            self._show_proxy_tun_blocked_state()
            return
        self._internet_token = token
        self._server.set_internet_token(token)
        full_url = f"{public_base_url}/?token={token}"
        self._render_qr_and_url(full_url)
        if self._on_mode_changed:
            self._on_mode_changed("internet", full_url, token)

    def _on_edge_state_changed(self, state_kind: str, text: str) -> None:
        return

    def _on_tunnel_failed(self, err_msg: str) -> None:
        if self._mode != "internet":
            return
        self._internet_token = ""
        self._server.set_internet_token("")
        self._show_error_state(err_msg)
        if self._on_mode_changed:
            self._on_mode_changed("internet", "", "")

    def _detach_tunnel_signals(self) -> None:
        """关闭管理窗时仅解绑 UI 监听并停本地计时器，保持后台 cloudflared 互联网隧道持续存活。"""
        if hasattr(self, "_chat_sync_timer"):
            self._chat_sync_timer.stop()
        self._loading_spinner.stop()
        if self._signals_detached:
            return
        self._signals_detached = True
        for sig, slot in (
            (self._tunnel_mgr.download_progress, self._on_cf_download_progress),
            (self._tunnel_mgr.download_finished, self._on_cf_download_finished),
            (self._tunnel_mgr.download_failed, self._on_cf_download_failed),
            (self._tunnel_mgr.tunnel_status, self._on_tunnel_status),
            (self._tunnel_mgr.tunnel_ready, self._on_tunnel_ready),
            (self._tunnel_mgr.edge_state_changed, self._on_edge_state_changed),
            (self._tunnel_mgr.tunnel_failed, self._on_tunnel_failed),
        ):
            try:
                sig.disconnect(slot)
            except Exception:
                pass

    def cleanup_tunnel(self) -> None:
        """显式销毁 cloudflared 子进程并清空公网安全 Token（仅在切换局域网/关闭服务/退出主程序时调用）。"""
        self._detach_tunnel_signals()
        self._tunnel_mgr.stop_all()
        self._internet_token = ""
        self._server.set_internet_token("")
        if self._mode == "internet":
            self._sync_mode_chat_channel("lan", refresh=False)
            if self._on_mode_changed:
                self._on_mode_changed("lan", self._server.get_url(), "")

    def closeEvent(self, event) -> None:
        self._server.clear_chat_messages()
        if not LanTransferServer.has_active_shares():
            self.cleanup_tunnel()
        else:
            self._detach_tunnel_signals()
        super().closeEvent(event)

    def done(self, result: int) -> None:
        self._server.clear_chat_messages()
        if not LanTransferServer.has_active_shares():
            self.cleanup_tunnel()
        else:
            self._detach_tunnel_signals()
        super().done(result)

    def apply_theme(self, theme_mode: str, accent_color: str) -> None:
        self._is_light = theme_mode == "light"
        self._accent = accent_color
        bg = "#F5F6F8" if self._is_light else "#18181D"
        border = "#DCDFE6" if self._is_light else "#2C2C36"
        fg = "#1D1E22" if self._is_light else "#F5F5F7"
        muted = "#6E707A" if self._is_light else "#9A9AA6"
        pill_bg = "#ECEDF2" if self._is_light else "#22222A"
        pill_hover = "#E2E4EC" if self._is_light else "#2D2D38"

        self._card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}")
        self._update_mode_segment_styles()
        self._loading_spinner.set_theme(self._is_light, accent_color)
        win_btn_qss = (
            f"QPushButton {{ background: transparent; color: {muted}; border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ background-color: {pill_hover}; color: {fg}; }}"
        )
        self._btn_min.setStyleSheet(win_btn_qss)
        self._btn_close.setStyleSheet(win_btn_qss)
        self.qr_lbl.setStyleSheet(
            f"background-color: {pill_bg}; border: 1px solid {border}; border-radius: 10px; padding: 6px;"
        )
        self._lbl_url.setStyleSheet(f"color: {accent_color}; border: none; background: transparent;")
        self._apply_chat_styles()
        self.refresh_chat_messages(force=True)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    @staticmethod
    def _make_qr_pil_image(url: str):
        try:
            import qrcode
            qr = qrcode.QRCode(border=1, box_size=6)
            qr.add_data(url)
            qr.make(fit=True)
            return qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        except Exception:
            return None

    @staticmethod
    def _pil_to_qr_pixmap(img, size_px: int) -> QPixmap | None:
        if img is None:
            return None
        try:
            rgba = img.convert("RGBA")
            data = rgba.tobytes("raw", "RGBA")
            qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()
            return QPixmap.fromImage(qimg).scaled(
                size_px,
                size_px,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        except Exception:
            return None

    @classmethod
    def _make_qr_pixmap(cls, url: str, size_px: int) -> QPixmap | None:
        return cls._pil_to_qr_pixmap(cls._make_qr_pil_image(url), size_px)

    def _show_url_context_menu(self, pos: QPoint) -> None:
        if not self._active_url:
            return
        menu = QMenu(self)
        bg = "#FFFFFF" if self._is_light else "#1E1E24"
        fg = "#1D1E22" if self._is_light else "#F5F5F7"
        bd = "#DCDFE6" if self._is_light else "#2E2E38"
        hov = "#ECEDF2" if self._is_light else "#2A2A34"
        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {bd};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 5px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {hov};
                color: {self._accent};
            }}
            """
        )
        act_copy = menu.addAction("复制网址")
        chosen = menu.exec(self._lbl_url.mapToGlobal(pos))
        if chosen is act_copy:
            self._copy_url()

    def _copy_url(self) -> None:
        if not self._active_url:
            return
        if self._on_copy_url:
            self._on_copy_url(self._active_url)
        else:
            cb = QApplication.clipboard()
            if cb is not None:
                cb.setText(self._active_url)
            if self._on_toast:
                self._on_toast("✓ 已复制互传网址")

    # ------------------------------------------------------------------
    # 仿微信 PC 桌面版聊天交互：发送文本 / 表情 / 文件 / 截图 / Ctrl+V 粘贴
    # ------------------------------------------------------------------
    def _on_chat_emoji_clicked(self) -> None:
        if self._emoji_popup is None:
            self._emoji_popup = _DesktopEmojiPopup(self._is_light, self._accent, self)
            self._emoji_popup.emoji_selected.connect(self._insert_emoji)
        else:
            self._emoji_popup.apply_theme(self._is_light, self._accent)
        pos = self._btn_chat_emoji.mapToGlobal(QPoint(0, -self._emoji_popup.height() - 6))
        self._emoji_popup.move(pos)
        self._emoji_popup.show()

    def _insert_emoji(self, ch: str) -> None:
        self._chat_input.insertPlainText(ch)
        self._chat_input.setFocus()

    def _on_chat_send_text(self) -> None:
        txt = self._chat_input.toPlainText()
        if not txt.strip():
            return
        self._chat_input.clear()
        self._server.add_shared_text(txt, mode=self._mode)
        self.refresh_chat_messages(force=True)

    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "选择要传给手机的文件", "", "所有文件 (*.*)")
        if paths:
            self._on_chat_files_pasted(paths)

    def _on_chat_files_pasted(self, paths: list) -> None:
        sent = 0
        for p in paths:
            if isinstance(p, str) and os.path.isfile(p):
                if self._server.add_shared_file(p, mode=self._mode) is not None:
                    sent += 1
        if sent > 0:
            self.refresh_chat_messages(force=True)
            if self._on_toast:
                self._on_toast(f"✓ 已发送 {sent} 个文件到聊天流")

    def _on_chat_image_pasted(self, img_obj) -> None:
        try:
            cache_dir = CacheManager.get_effective_cache_dir(self._config)
            img_dir = os.path.join(cache_dir, "clipboard_cache")
            os.makedirs(img_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(img_dir, f"paste_img_{ts}_{uuid.uuid4().hex[:4]}.png")
            if isinstance(img_obj, QImage):
                img_obj.save(out_path, "PNG")
            else:
                img_obj.convert("RGB").save(out_path, "PNG")
            if os.path.isfile(out_path):
                self._server.add_shared_file(out_path, mode=self._mode)
                self.refresh_chat_messages(force=True)
                if self._on_toast:
                    self._on_toast("✓ 已发送粘贴的图片到手机")
        except Exception as exc:
            if self._on_toast:
                self._on_toast(f"发送剪贴板图片失败：{exc}")

    def _on_chat_screenshot_clicked(self) -> None:
        if self._on_request_screenshot:
            self._on_request_screenshot()

    def _on_open_recv(self) -> None:
        os.makedirs(self._server.receive_dir, exist_ok=True)
        try:
            os.startfile(self._server.receive_dir)
        except Exception:
            pass

    def _copy_chat_text(self, text: str) -> None:
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(text)
        if self._on_toast:
            self._on_toast("✓ 已复制消息全文")

    def _open_image_preview(self, fpath: str) -> None:
        if not fpath or not os.path.isfile(fpath):
            return
        dlg = _DesktopImagePreviewDialog(fpath, self._is_light, self._accent, self)
        dlg.finished.connect(lambda _r, d=dlg: self._preview_dlgs.remove(d) if d in self._preview_dlgs else None)
        self._preview_dlgs.append(dlg)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _locate_local_file(self, fpath: str) -> None:
        if not fpath or not os.path.exists(fpath):
            self._on_open_recv()
            return
        try:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(fpath)])
        except Exception:
            try:
                os.startfile(os.path.dirname(fpath))
            except Exception:
                pass

    def _play_voice_file(self, fpath: str) -> None:
        if not fpath or not os.path.isfile(fpath):
            if self._on_toast:
                self._on_toast("音频文件不存在")
            return
        try:
            os.startfile(fpath)
        except Exception as exc:
            if self._on_toast:
                self._on_toast(f"无法播放语音：{exc}")

    @staticmethod
    def _file_ext_badge_info(filename: str) -> tuple[str, str]:
        ext = os.path.splitext(str(filename or ""))[1].lstrip(".").upper() or "FILE"
        color_map = {
            "PDF": "#E11D48", "DOC": "#2563EB", "DOCX": "#2563EB",
            "XLS": "#16A34A", "XLSX": "#16A34A", "PPT": "#EA580C", "PPTX": "#EA580C",
            "ZIP": "#D97706", "RAR": "#D97706", "7Z": "#D97706",
            "MP4": "#7C3AED", "MOV": "#7C3AED", "MP3": "#0891B2", "WAV": "#0891B2",
            "EXE": "#4F46E5", "APK": "#10B981", "TXT": "#64748B",
        }
        return ext[:4], color_map.get(ext, "#6366F1")

    def refresh_shared_list(self) -> None:
        """兼容旧调用接口：强制刷新双向聊天流。"""
        self.refresh_chat_messages(force=True)

    def cache_image_thumbnail(self, fpath: str, pil_thumb) -> None:
        """缓存后台线程异步生成的聊天缩略图，避免主线程同步解码相机大图造成卡顿。"""
        if not fpath or pil_thumb is None:
            return
        try:
            pm = _pil_rgba_to_qpixmap(pil_thumb)
            if not pm.isNull():
                self._img_thumb_cache[fpath] = pm
        except Exception:
            pass

    def refresh_chat_messages(self, force: bool = False) -> None:
        msgs = self._server.list_chat_messages(mode=self._mode)
        sig = (self._mode, [(m["id"], m.get("sender_name", "")) for m in msgs])
        if not force and sig == self._last_chat_sig:
            return
        self._last_chat_sig = sig

        while self._chat_layout.count() > 0:
            it = self._chat_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

        is_light = self._is_light
        acc = self._accent
        fg = "#1D1E22" if is_light else "#F5F5F7"
        muted = "#7A7D88" if is_light else "#8E8E9C"
        pc_bubble_bg = acc
        phone_bubble_bg = "#FFFFFF" if is_light else "#23232C"
        card_bg = "#FFFFFF" if is_light else "#23232C"
        border = "#E0E2EA" if is_light else "#30303C"

        if not msgs:
            self._chat_layout.addStretch(1)
            return

        # 自适应计算气泡最大内容宽度（防止窗口初始未渲染 viewport().width() <= 1 时算出极窄宽度导致单字竖排）
        vp_w = self._chat_scroll.viewport().width()
        chat_area_width = vp_w if vp_w > 120 else 316
        max_bubble_width = min(236, max(200, int(chat_area_width * 0.72)))
        msg_font = get_source_han_font(8)
        fm_msg = QFontMetrics(msg_font)

        for m in msgs:
            is_pc = m.get("direction") == "pc"
            mtype = m.get("msg_type", "text")
            if mtype in ("system", "notice"):
                sys_row = QWidget(self._chat_box)
                sys_row.setStyleSheet("background: transparent; border: none;")
                sys_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                sr_l = QHBoxLayout(sys_row)
                sr_l.setContentsMargins(8, 6, 8, 6)
                sr_l.setSpacing(0)
                sys_lbl = QLabel(str(m.get("text") or ""), sys_row)
                sys_lbl.setFont(get_source_han_font(7))
                sys_lbl.setWordWrap(True)
                sys_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sys_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                sys_lbl.setStyleSheet(f"color: {muted}; background: transparent; border: none;")
                sr_l.addWidget(sys_lbl, 1, Qt.AlignmentFlag.AlignCenter)
                self._chat_layout.addWidget(sys_row)
                continue
            sender_name = str(m.get("sender_name") or ("电脑端" if is_pc else "手机端-1"))
            av_idx = int(m.get("avatar_idx", 0 if is_pc else 1))
            time_str = str(m.get("time_str") or "")
            fpath = self._server.resolve_media_path(m["id"]) if mtype != "text" else ""

            row = QWidget(self._chat_box)
            row.setStyleSheet("background: transparent; border: none;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(2, 0, 2, 0)
            rl.setSpacing(7)

            av_lbl = QLabel(row)
            av_lbl.setFixedSize(30, 30)
            av_lbl.setPixmap(_make_pillow_device_avatar(av_idx, 30))
            av_lbl.setStyleSheet("background: transparent; border: none;")

            col = QVBoxLayout()
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(3)

            meta_lbl = QLabel(f"{sender_name}  {time_str}".strip(), row)
            meta_lbl.setFont(get_source_han_font(7))
            meta_lbl.setStyleSheet(f"color: {muted}; background: transparent; border: none;")
            meta_lbl.setAlignment(Qt.AlignmentFlag.AlignRight if is_pc else Qt.AlignmentFlag.AlignLeft)
            col.addWidget(meta_lbl)

            if mtype == "text":
                txt_val = str(m.get("text") or "")
                raw_lines = txt_val.splitlines() or [txt_val]
                max_line_w = max((fm_msg.horizontalAdvance(ln) for ln in raw_lines), default=0)
                is_short_single = len(raw_lines) == 1 and max_line_w <= max_bubble_width
                content_w = max(20, max_line_w + 4) if is_short_single else min(max_bubble_width, max(20, max_line_w + 4))

                bubble = _ClickableChatBubble(row)
                bubble.setToolTip("点击复制消息全文")
                bubble.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
                bubble.clicked.connect(lambda t=txt_val: self._copy_chat_text(t))

                bl = QVBoxLayout(bubble)
                bl.setContentsMargins(10, 7, 10, 7)
                bl.setSpacing(0)

                lbl_t = QLabel(txt_val, bubble)
                lbl_t.setFont(msg_font)
                lbl_t.setWordWrap(not is_short_single)
                lbl_t.setFixedWidth(content_w)
                lbl_t.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                lbl_t.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
                lbl_t.setStyleSheet(f"color: {'#FFFFFF' if is_pc else fg}; background: transparent; border: none;")

                if is_short_single:
                    text_h = max(fm_msg.height(), lbl_t.sizeHint().height())
                else:
                    br_h = fm_msg.boundingRect(
                        0,
                        0,
                        content_w,
                        100000,
                        Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere,
                        txt_val,
                    ).height()
                    hfw = lbl_t.heightForWidth(content_w)
                    text_h = max(fm_msg.height(), br_h, hfw if hfw > 0 else 0)
                lbl_t.setMinimumHeight(text_h + 2)
                bl.addWidget(lbl_t)

                bubble.setFixedWidth(content_w + 20)
                if is_pc:
                    bubble.setStyleSheet(
                        f"QFrame {{ background-color: {pc_bubble_bg}; border: none; border-radius: 10px; }}"
                    )
                else:
                    bubble.setStyleSheet(
                        f"QFrame {{ background-color: {phone_bubble_bg}; border: 1px solid {border}; border-radius: 10px; }}"
                        f"QFrame:hover {{ border-color: {acc}; }}"
                    )
                col.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight if is_pc else Qt.AlignmentFlag.AlignLeft)

            elif mtype == "image" and fpath and os.path.isfile(fpath):
                img_btn = QPushButton(row)
                img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                img_btn.setToolTip("点击查看大图")
                scaled = self._img_thumb_cache.get(fpath)
                if scaled is None or scaled.isNull():
                    pm = QPixmap(fpath)
                    if not pm.isNull():
                        scaled = pm.scaled(162, 136, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self._img_thumb_cache[fpath] = scaled
                if scaled is not None and not scaled.isNull():
                    img_btn.setIcon(QIcon(scaled))
                    img_btn.setIconSize(scaled.size())
                    img_btn.setFixedSize(scaled.width() + 8, scaled.height() + 8)
                else:
                    img_btn.setText("[图片]")
                    img_btn.setFixedSize(80, 32)
                img_btn.setStyleSheet(
                    f"QPushButton {{ background-color: {card_bg}; border: 1px solid {border}; border-radius: 9px; padding: 3px; }}"
                    f"QPushButton:hover {{ border-color: {acc}; }}"
                )
                img_btn.clicked.connect(lambda checked=False, p=fpath: self._open_image_preview(p))
                col.addWidget(img_btn, 0, Qt.AlignmentFlag.AlignRight if is_pc else Qt.AlignmentFlag.AlignLeft)

            elif mtype == "audio":
                dur = max(1, int(m.get("duration") or 1))
                v_btn = QPushButton(f' {dur}"', row)
                v_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                v_btn.setToolTip("点击播放语音")
                v_btn.setFixedHeight(32)
                v_btn.setFixedWidth(min(176, max(78, 62 + dur * 4)))
                v_btn.setIcon(_make_tool_vector_icon("voice_wave", "#FFFFFF" if is_pc else fg))
                v_btn.setIconSize(QSize(14, 14))
                v_btn.setFont(get_source_han_font(8, QFont.Weight.Bold))
                if is_pc:
                    v_btn.setStyleSheet(
                        f"QPushButton {{ background-color: {pc_bubble_bg}; color: #FFFFFF; border: none; border-radius: 10px; padding: 0px 10px; }}"
                    )
                else:
                    v_btn.setStyleSheet(
                        f"QPushButton {{ background-color: {phone_bubble_bg}; color: {fg}; border: 1px solid {border}; border-radius: 10px; padding: 0px 10px; }}"
                        f"QPushButton:hover {{ border-color: {acc}; color: {acc}; }}"
                    )
                v_btn.clicked.connect(lambda checked=False, p=fpath: self._play_voice_file(p))
                col.addWidget(v_btn, 0, Qt.AlignmentFlag.AlignRight if is_pc else Qt.AlignmentFlag.AlignLeft)

            else:
                # 仿微信文件卡片气泡
                fname = str(m.get("name") or "文件")
                fsize = str(m.get("size_str") or "")
                ext_txt, ext_col = self._file_ext_badge_info(fname)
                f_card = QPushButton(row)
                f_card.setCursor(Qt.CursorShape.PointingHandCursor)
                f_card.setFixedSize(214, 52)
                f_card.setToolTip("点击打开文件夹并定位文件")
                f_card.setStyleSheet(
                    f"QPushButton {{ background-color: {card_bg}; border: 1px solid {border}; border-radius: 10px; }}"
                    f"QPushButton:hover {{ border-color: {acc}; }}"
                )
                f_card.clicked.connect(lambda checked=False, p=fpath: self._locate_local_file(p))

                fl = QHBoxLayout(f_card)
                fl.setContentsMargins(9, 6, 9, 6)
                fl.setSpacing(8)

                f_info = QVBoxLayout()
                f_info.setContentsMargins(0, 0, 0, 0)
                f_info.setSpacing(2)
                fm_f = QFontMetrics(get_source_han_font(8, QFont.Weight.Bold))
                lbl_fn = QLabel(fm_f.elidedText(fname, Qt.TextElideMode.ElideMiddle, 148), f_card)
                lbl_fn.setFont(get_source_han_font(8, QFont.Weight.Bold))
                lbl_fn.setStyleSheet(f"color: {fg}; background: transparent; border: none;")
                lbl_fs = QLabel(fsize, f_card)
                lbl_fs.setFont(get_source_han_font(7))
                lbl_fs.setStyleSheet(f"color: {muted}; background: transparent; border: none;")
                f_info.addWidget(lbl_fn)
                f_info.addWidget(lbl_fs)

                badge = QLabel(ext_txt, f_card)
                badge.setFixedSize(34, 36)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge.setFont(get_source_han_font(7, QFont.Weight.Bold))
                badge.setStyleSheet(
                    f"background-color: {ext_col}; color: #FFFFFF; border: none; border-radius: 6px;"
                )

                fl.addLayout(f_info, 1)
                fl.addWidget(badge)
                col.addWidget(f_card, 0, Qt.AlignmentFlag.AlignRight if is_pc else Qt.AlignmentFlag.AlignLeft)

            if is_pc:
                rl.addStretch(1)
                rl.addLayout(col)
                rl.addWidget(av_lbl, 0, Qt.AlignmentFlag.AlignTop)
            else:
                rl.addWidget(av_lbl, 0, Qt.AlignmentFlag.AlignTop)
                rl.addLayout(col)
                rl.addStretch(1)

            self._chat_layout.addWidget(row)

        self._chat_layout.addStretch(1)
        QTimer.singleShot(20, self._scroll_chat_to_bottom)

    def _scroll_chat_to_bottom(self) -> None:
        try:
            sb = self._chat_scroll.verticalScrollBar()
            sb.setValue(sb.maximum())
        except RuntimeError:
            pass


def _decouple_win32_window_owner(widget: QWidget, decouple: bool = True, owner_widget: QWidget | None = None) -> None:
    """
    通过 Win32 SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT=-8, 0) 解耦或恢复子窗口所有权，
    确保当 keep_children_on_hide=True 时主窗口最小化或隐藏至托盘不会连带隐藏已打开的子窗口。
    """
    if sys.platform != "win32" or widget is None:
        return
    try:
        hwnd = int(widget.winId())
        if not hwnd:
            return
        target_owner = 0
        if not decouple and owner_widget is not None:
            target_owner = int(owner_widget.winId())
        user32 = ctypes.windll.user32
        set_fn = getattr(user32, "SetWindowLongPtrW", getattr(user32, "SetWindowLongW", None))
        if set_fn is not None:
            set_fn(ctypes.c_void_p(hwnd), -8, ctypes.c_void_p(target_owner))
    except Exception:
        pass


class SlackingCurveCanvas(QWidget):
    """平滑摸鱼曲线示意图（支持渐进式放大生长与今日时段 / 近7日 / 近30日及峰值标记）。"""

    clicked = Signal()

    def __init__(self, parent=None, embedded: bool = False):
        super().__init__(parent)
        self._embedded = embedded
        self.setFixedHeight(52 if embedded else 138)
        if embedded:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._labels: list[str] = []
        self._values: list[float] = []
        self._peak_idx: int = 0
        self._is_light: bool = False
        self._accent: str = "#FF6B00"

    def mousePressEvent(self, event) -> None:
        if self._embedded and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def set_data(self, labels: list[str], values: list[float], peak_idx: int) -> None:
        self._labels = list(labels)
        self._values = list(values)
        self._peak_idx = peak_idx
        self.update()

    def set_theme(self, is_light: bool, accent_color: str) -> None:
        self._is_light = is_light
        self._accent = accent_color
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = float(self.width()), float(self.height())
        pad_l, pad_r, pad_t, pad_b = 12.0, 12.0, 22.0, 22.0
        plot_w = max(20.0, w - pad_l - pad_r)
        plot_h = max(20.0, h - pad_t - pad_b)

        grid_color = QColor("#E4E6EE") if self._is_light else QColor("#2A2A34")
        text_color = QColor("#7A7C88") if self._is_light else QColor("#8A8A96")
        acc = QColor(self._accent)

        # 背景水平参考线
        p.setPen(QPen(grid_color, 1.0, Qt.PenStyle.DashLine))
        for frac in (0.0, 0.5, 1.0):
            gy = pad_t + plot_h * frac
            p.drawLine(QPointF(pad_l, gy), QPointF(w - pad_r, gy))

        vals = self._values or [0.0]
        n = len(vals)
        max_v = max(vals) if max(vals) > 0.0 else 1.0
        pts: list[QPointF] = []
        for idx, v in enumerate(vals):
            x = pad_l + (plot_w * idx / max(1, n - 1)) if n > 1 else (pad_l + plot_w / 2.0)
            y = pad_t + plot_h - (v / max_v) * (plot_h - 4.0)
            pts.append(QPointF(x, y))

        if len(pts) >= 2:
            path = QPainterPath(pts[0])
            for i in range(len(pts) - 1):
                mid_x = (pts[i].x() + pts[i + 1].x()) / 2.0
                c1 = QPointF(mid_x, pts[i].y())
                c2 = QPointF(mid_x, pts[i + 1].y())
                path.cubicTo(c1, c2, pts[i + 1])

            fill_path = QPainterPath(path)
            fill_path.lineTo(pts[-1].x(), pad_t + plot_h)
            fill_path.lineTo(pts[0].x(), pad_t + plot_h)
            fill_path.closeSubpath()

            c_top = QColor(acc)
            c_top.setAlpha(70)
            c_bot = QColor(acc)
            c_bot.setAlpha(4)
            from PySide6.QtGui import QLinearGradient
            grad = QLinearGradient(0, pad_t, 0, pad_t + plot_h)
            grad.setColorAt(0.0, c_top)
            grad.setColorAt(1.0, c_bot)
            p.fillPath(fill_path, grad)

            p.setPen(QPen(acc, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        # 峰值标记
        if pts and 0 <= self._peak_idx < len(pts):
            pk = pts[self._peak_idx]
            pk_val = vals[self._peak_idx]
            p.setPen(QPen(QColor("#FFFFFF"), 1.6))
            p.setBrush(acc)
            p.drawEllipse(pk, 4.0, 4.0)
            if pk_val > 0.0:
                pk_label = f"峰值 {pk_val:.1f}m"
                p.setFont(get_source_han_font(7, QFont.Weight.Bold))
                p.setPen(acc)
                tx = max(pad_l, min(w - pad_r - 58.0, pk.x() - 24.0))
                p.drawText(QPointF(tx, max(12.0, pk.y() - 7.0)), pk_label)

        # 首尾/中间 X 轴刻度
        if self._labels:
            p.setFont(get_source_han_font(7))
            p.setPen(text_color)
            p.drawText(QPointF(pad_l, h - 5.0), self._labels[0])
            if len(self._labels) > 2:
                mid_i = len(self._labels) // 2
                p.drawText(QPointF(pad_l + plot_w * 0.45, h - 5.0), self._labels[mid_i])
            if len(self._labels) > 1:
                p.drawText(QPointF(w - pad_r - 28.0, h - 5.0), self._labels[-1])
        p.end()


class SlackingDashboardDialog(QDialog):
    """摸鱼数据看板子窗口（宽度与主界面一致，带最小化与关闭，支持全主题动态切换）。"""

    def __init__(
        self,
        stats_mgr: SlackingStatsManager,
        theme_mode: str,
        accent_color: str,
        online_count_text: str = "--",
        live_secs: float = 0.0,
        live_earned: float = 0.0,
        has_salary: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._stats_mgr = stats_mgr
        self._is_light = theme_mode == "light"
        self._accent = accent_color
        self._curve_mode = "today"
        self._live_secs = live_secs
        self._live_earned = live_earned
        self._has_salary = has_salary
        self._online_text = online_count_text
        self._drag_pos: QPoint | None = None

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)
        self.setFixedWidth(MAIN_WIDTH)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame(self)
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(16, 13, 16, 14)
        cl.setSpacing(10)

        top = QHBoxLayout()
        self._lbl_title = QLabel("摸鱼数据看板", self._card)
        self._lbl_title.setFont(get_source_han_font(10, QFont.Weight.Bold))
        self._lbl_online = QLabel(f"🟢 在线：{online_count_text} 人", self._card)
        self._lbl_online.setFont(get_source_han_font(8))
        self._btn_min = VectorIconButton("min", self._card, accent_color)
        self._btn_min.setFixedSize(22, 22)
        self._btn_min.clicked.connect(self.showMinimized)
        self._btn_close = VectorIconButton("close", self._card, accent_color)
        self._btn_close.setFixedSize(22, 22)
        self._btn_close.clicked.connect(self.close)
        top.addWidget(self._lbl_title)
        top.addSpacing(6)
        top.addWidget(self._lbl_online)
        top.addStretch(1)
        top.addWidget(self._btn_min)
        top.addWidget(self._btn_close)
        cl.addLayout(top)

        # 日 / 周 / 月 汇总卡片
        sum_row = QHBoxLayout()
        sum_row.setSpacing(8)
        self._sum_boxes: list[tuple[QFrame, QLabel, QLabel, QLabel]] = []
        for title_txt in ("今日摸鱼", "近7日", "近30日"):
            box = QFrame(self._card)
            bl = QVBoxLayout(box)
            bl.setContentsMargins(8, 8, 8, 8)
            bl.setSpacing(2)
            l_cap = QLabel(title_txt, box)
            l_cap.setFont(get_source_han_font(8))
            l_dur = QLabel("0分", box)
            l_dur.setFont(get_source_han_font(10, QFont.Weight.Bold))
            l_amt = QLabel("--", box)
            l_amt.setFont(get_source_han_font(8, QFont.Weight.Bold))
            bl.addWidget(l_cap)
            bl.addWidget(l_dur)
            bl.addWidget(l_amt)
            sum_row.addWidget(box, 1)
            self._sum_boxes.append((box, l_cap, l_dur, l_amt))
        cl.addLayout(sum_row)

        # 曲线切换标签
        tab_row = QHBoxLayout()
        tab_row.setSpacing(6)
        self._lbl_curve_cap = QLabel("摸鱼时长曲线（分钟）", self._card)
        self._lbl_curve_cap.setFont(get_source_han_font(8))
        tab_row.addWidget(self._lbl_curve_cap)
        tab_row.addStretch(1)
        self._curve_btns: dict[str, QPushButton] = {}
        for mk, ml in (("today", "今日时段"), ("7d", "近7日"), ("30d", "近30日")):
            b = QPushButton(ml, self._card)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(22)
            b.setFont(get_source_han_font(7, QFont.Weight.Bold))
            b.clicked.connect(lambda checked=False, k=mk: self._switch_curve_mode(k))
            self._curve_btns[mk] = b
            tab_row.addWidget(b)
        cl.addLayout(tab_row)

        self._curve_box = QFrame(self._card)
        cbl = QVBoxLayout(self._curve_box)
        cbl.setContentsMargins(4, 4, 4, 4)
        self._canvas = SlackingCurveCanvas(self._curve_box)
        cbl.addWidget(self._canvas)
        cl.addWidget(self._curve_box)

        outer.addWidget(self._card)
        self.refresh_stats(live_secs, live_earned, has_salary, online_count_text)
        self.apply_theme(theme_mode, accent_color)
        self.adjustSize()

    @staticmethod
    def _fmt_dur(secs: float) -> str:
        m = int(secs // 60)
        h, rem_m = divmod(m, 60)
        if h > 0:
            return f"{h}h{rem_m:02d}m"
        return f"{rem_m}分"

    def _switch_curve_mode(self, mode: str) -> None:
        self._curve_mode = mode
        self._refresh_curve()
        self._apply_tab_styles()

    def _refresh_curve(self) -> None:
        labels, vals, pk = self._stats_mgr.get_curve_data(self._curve_mode, self._live_secs)
        self._canvas.set_data(labels, vals, pk)

    def refresh_stats(
        self,
        live_secs: float,
        live_earned: float,
        has_salary: bool,
        online_count_text: str | None = None,
    ) -> None:
        self._live_secs = live_secs
        self._live_earned = live_earned
        self._has_salary = has_salary
        if online_count_text is not None:
            self._online_text = online_count_text
            self._lbl_online.setText(f"🟢 在线：{online_count_text} 人")

        summary = self._stats_mgr.get_summary(live_secs, live_earned)
        for idx, key in enumerate(("today", "week", "month")):
            _box, _cap, l_dur, l_amt = self._sum_boxes[idx]
            d = summary[key]
            l_dur.setText(self._fmt_dur(d["seconds"]))
            l_amt.setText(f"¥{d['earned']:.2f}" if has_salary else "--")
        self._refresh_curve()

    def _apply_tab_styles(self) -> None:
        muted = "#6E707A" if self._is_light else "#9A9AA6"
        pill_bg = "#ECEDF2" if self._is_light else "#22222A"
        for k, b in self._curve_btns.items():
            if k == self._curve_mode:
                b.setStyleSheet(
                    f"QPushButton {{ background-color: {self._accent}; color: #FFFFFF; border: none; border-radius: 6px; padding: 0px 7px; }}"
                )
            else:
                b.setStyleSheet(
                    f"QPushButton {{ background-color: {pill_bg}; color: {muted}; border: none; border-radius: 6px; padding: 0px 7px; }}"
                )

    def apply_theme(self, theme_mode: str, accent_color: str) -> None:
        self._is_light = theme_mode == "light"
        self._accent = accent_color
        bg = "#F5F6F8" if self._is_light else "#18181D"
        border = "#DCDFE6" if self._is_light else "#2C2C36"
        fg = "#1D1E22" if self._is_light else "#F5F5F7"
        muted = "#6E707A" if self._is_light else "#9A9AA6"
        sub_bg = "#ECEDF2" if self._is_light else "#202027"

        self._card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}")
        self._lbl_title.setStyleSheet(f"color: {fg}; border: none;")
        self._lbl_online.setStyleSheet(f"color: {GREEN_ACCENT}; border: none;")
        self._lbl_curve_cap.setStyleSheet(f"color: {muted}; border: none;")
        for b in (self._btn_min, self._btn_close):
            b.set_accent_color(accent_color)
            b.set_light_mode(self._is_light)
        for box, l_cap, l_dur, l_amt in self._sum_boxes:
            box.setStyleSheet(f"QFrame {{ background-color: {sub_bg}; border: 1px solid {border}; border-radius: 10px; }}")
            l_cap.setStyleSheet(f"color: {muted}; border: none;")
            l_dur.setStyleSheet(f"color: {fg}; border: none;")
            l_amt.setStyleSheet(f"color: {accent_color}; border: none;")
        self._curve_box.setStyleSheet(f"QFrame {{ background-color: {sub_bg}; border: 1px solid {border}; border-radius: 10px; }}")
        self._canvas.set_theme(self._is_light, accent_color)
        self._apply_tab_styles()
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class ProgressTargetConfigDialog(QDialog):
    """进度条三槽位独立自定义目标设置子窗口。"""

    def __init__(self, config: AppConfig, on_saved=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._on_saved = on_saved
        self._is_light = config.theme_mode == "light"
        self._accent = config.accent_color
        self._drag_pos: QPoint | None = None

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)
        self.setFixedWidth(MAIN_WIDTH)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame(self)
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(16, 13, 16, 14)
        cl.setSpacing(10)

        top = QHBoxLayout()
        self._lbl_title = QLabel("进度条目标设置", self._card)
        self._lbl_title.setFont(get_source_han_font(10, QFont.Weight.Bold))
        self._btn_min = VectorIconButton("min", self._card, config.accent_color)
        self._btn_min.setFixedSize(22, 22)
        self._btn_min.clicked.connect(self.showMinimized)
        self._btn_close = VectorIconButton("close", self._card, config.accent_color)
        self._btn_close.setFixedSize(22, 22)
        self._btn_close.clicked.connect(self.close)
        top.addWidget(self._lbl_title)
        top.addStretch(1)
        top.addWidget(self._btn_min)
        top.addWidget(self._btn_close)
        cl.addLayout(top)

        self._slot_rows: list[tuple[int, QFrame, QCheckBox, QCheckBox, QLineEdit, QLineEdit, QLineEdit]] = []
        slot_titles = (
            (1, "槽位 1（默认：距离下班）"),
            (2, "槽位 2（默认：距离周末）"),
            (3, "槽位 3（默认：距离发薪）"),
        )
        for idx, title_txt in slot_titles:
            box = QFrame(self._card)
            bl = QVBoxLayout(box)
            bl.setContentsMargins(10, 8, 10, 8)
            bl.setSpacing(6)

            hdr_row = QHBoxLayout()
            hdr_row.setSpacing(6)
            chk = QCheckBox(f"{title_txt} · 自定义", box)
            chk.setFont(get_source_han_font(8, QFont.Weight.Bold))
            chk.setChecked(bool(getattr(config, f"slot{idx}_custom_enabled", False)))

            exact_on = bool(getattr(config, f"slot{idx}_exact_time", False))
            chk_exact = QCheckBox("精确时间", box)
            chk_exact.setFont(get_source_han_font(8))
            chk_exact.setChecked(exact_on)
            hdr_row.addWidget(chk, 1)
            hdr_row.addWidget(chk_exact)

            ed_name = QLineEdit(box)
            ed_name.setFixedHeight(26)
            ed_name.setFont(get_source_han_font(8))
            ed_name.setPlaceholderText("目标标题")
            ed_name.setText(str(getattr(config, f"slot{idx}_custom_name", "") or ""))

            inp_row = QHBoxLayout()
            inp_row.setSpacing(6)
            ph = "YYYY-MM-DD HH:MM" if exact_on else "YYYY-MM-DD"

            ed_start = QLineEdit(box)
            ed_start.setFixedHeight(26)
            ed_start.setFont(get_source_han_font(8))
            ed_start.setPlaceholderText(f"开始: {ph}")
            ed_start.setText(str(getattr(config, f"slot{idx}_custom_start", "") or ""))

            ed_dt = QLineEdit(box)
            ed_dt.setFixedHeight(26)
            ed_dt.setFont(get_source_han_font(8))
            ed_dt.setPlaceholderText(f"结束: {ph}")
            ed_dt.setText(str(getattr(config, f"slot{idx}_custom_date", "") or ""))

            def _on_exact_toggled(checked: bool, s_ed=ed_start, e_ed=ed_dt) -> None:
                fmt_ph = "YYYY-MM-DD HH:MM" if checked else "YYYY-MM-DD"
                s_ed.setPlaceholderText(f"开始: {fmt_ph}")
                e_ed.setPlaceholderText(f"结束: {fmt_ph}")

            chk_exact.toggled.connect(_on_exact_toggled)

            inp_row.addWidget(ed_start, 1)
            inp_row.addWidget(ed_dt, 1)
            bl.addLayout(hdr_row)
            bl.addWidget(ed_name)
            bl.addLayout(inp_row)
            cl.addWidget(box)
            self._slot_rows.append((idx, box, chk, chk_exact, ed_name, ed_start, ed_dt))

        self._lbl_err = QLabel("", self._card)
        self._lbl_err.setFont(get_source_han_font(8))
        self._lbl_err.setVisible(False)
        cl.addWidget(self._lbl_err)

        self._btn_save = QPushButton("保存并生效", self._card)
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.setFixedHeight(34)
        self._btn_save.setFont(get_source_han_font(9, QFont.Weight.Bold))
        self._btn_save.clicked.connect(self._on_save)
        cl.addWidget(self._btn_save)

        outer.addWidget(self._card)
        self.apply_theme(config.theme_mode, config.accent_color)
        self.adjustSize()

    def _on_save(self) -> None:
        for idx, _box, chk, _chk_ex, _ed_name, ed_start, ed_dt in self._slot_rows:
            if chk.isChecked():
                if TimeCalculator.parse_target_datetime(ed_dt.text().strip()) is None:
                    self._lbl_err.setText(f"槽位 {idx} 结束时间格式无效")
                    self._lbl_err.setVisible(True)
                    self.adjustSize()
                    return
                s_txt = ed_start.text().strip()
                if s_txt and TimeCalculator.parse_target_datetime(s_txt) is None:
                    self._lbl_err.setText(f"槽位 {idx} 开始时间格式无效")
                    self._lbl_err.setVisible(True)
                    self.adjustSize()
                    return
        self._lbl_err.setVisible(False)
        for idx, _box, chk, chk_exact, ed_name, ed_start, ed_dt in self._slot_rows:
            on = chk.isChecked()
            ex = chk_exact.isChecked()
            nm = ed_name.text().strip()
            st_s = ed_start.text().strip()
            dt_s = ed_dt.text().strip()
            if on and not st_s:
                st_s = datetime.now().strftime("%Y-%m-%d %H:%M" if ex else "%Y-%m-%d")
            setattr(self._config, f"slot{idx}_custom_enabled", on)
            setattr(self._config, f"slot{idx}_exact_time", ex)
            setattr(self._config, f"slot{idx}_custom_name", nm)
            setattr(self._config, f"slot{idx}_custom_start", st_s)
            setattr(self._config, f"slot{idx}_custom_date", dt_s)
        self._config.save()
        if self._on_saved:
            self._on_saved()
        self.close()

    def apply_theme(self, theme_mode: str, accent_color: str) -> None:
        self._is_light = theme_mode == "light"
        self._accent = accent_color
        bg = "#F5F6F8" if self._is_light else "#18181D"
        border = "#DCDFE6" if self._is_light else "#2C2C36"
        fg = "#1D1E22" if self._is_light else "#F5F5F7"
        muted = "#6E707A" if self._is_light else "#9A9AA6"
        sub_bg = "#ECEDF2" if self._is_light else "#202027"
        inp_bg = "#FFFFFF" if self._is_light else "#16161B"

        self._card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}")
        self._lbl_title.setStyleSheet(f"color: {fg}; border: none;")
        for b in (self._btn_min, self._btn_close):
            b.set_accent_color(accent_color)
            b.set_light_mode(self._is_light)

        chk_qss = (
            f"QCheckBox {{ color: {fg}; spacing: 6px; border: none; }}"
            f"QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 7px; border: 1.5px solid {muted}; background: {inp_bg}; }}"
            f"QCheckBox::indicator:checked {{ border-color: {accent_color}; background: {accent_color}; }}"
        )
        inp_qss = (
            f"QLineEdit {{ background: {inp_bg}; color: {fg}; border: 1px solid {border}; border-radius: 6px; padding: 2px 8px; }}"
            f"QLineEdit:focus {{ border-color: {accent_color}; }}"
        )
        for _idx, box, chk, chk_exact, ed_name, ed_start, ed_dt in self._slot_rows:
            box.setStyleSheet(f"QFrame {{ background-color: {sub_bg}; border: 1px solid {border}; border-radius: 10px; }}")
            chk.setStyleSheet(chk_qss)
            chk_exact.setStyleSheet(chk_qss)
            ed_name.setStyleSheet(inp_qss)
            ed_start.setStyleSheet(inp_qss)
            ed_dt.setStyleSheet(inp_qss)
        self._lbl_err.setStyleSheet(f"color: {INVALID_RED}; border: none;")
        self._btn_save.setStyleSheet(
            f"QPushButton {{ background-color: {accent_color}; color: #FFFFFF; border: none; border-radius: 8px; }}"
        )
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class SlackingSettingsDialog(QDialog):
    """独立摸鱼设置子窗口（月薪配置 + 匿名在线摸鱼统计开关）。"""

    def __init__(self, config: AppConfig, on_saved=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._on_saved = on_saved
        self._is_light = config.theme_mode == "light"
        self._accent = config.accent_color
        self._drag_pos: QPoint | None = None

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)
        self.setFixedWidth(MAIN_WIDTH)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame(self)
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(16, 13, 16, 14)
        cl.setSpacing(10)

        top = QHBoxLayout()
        self._lbl_title = QLabel("摸鱼设置", self._card)
        self._lbl_title.setFont(get_source_han_font(10, QFont.Weight.Bold))
        self._btn_min = VectorIconButton("min", self._card, config.accent_color)
        self._btn_min.setFixedSize(22, 22)
        self._btn_min.clicked.connect(self.showMinimized)
        self._btn_close = VectorIconButton("close", self._card, config.accent_color)
        self._btn_close.setFixedSize(22, 22)
        self._btn_close.clicked.connect(self.close)
        top.addWidget(self._lbl_title)
        top.addStretch(1)
        top.addWidget(self._btn_min)
        top.addWidget(self._btn_close)
        cl.addLayout(top)

        self._lbl_sal = QLabel("税后月薪 (¥，设为 0 则隐藏金额)", self._card)
        self._lbl_sal.setFont(get_source_han_font(8))
        cl.addWidget(self._lbl_sal)

        self.spin_salary = QDoubleSpinBox(self._card)
        self.spin_salary.setRange(0.0, 9999999.0)
        self.spin_salary.setDecimals(0)
        self.spin_salary.setSingleStep(500.0)
        self.spin_salary.setPrefix("¥ ")
        self.spin_salary.setFixedHeight(34)
        self.spin_salary.setFont(get_source_han_font(11, QFont.Weight.Bold))
        self.spin_salary.setValue(float(getattr(config, "monthly_salary", 0.0) or 0.0))
        cl.addWidget(self.spin_salary)

        self.chk_online = QCheckBox("开启匿名在线摸鱼状态统计", self._card)
        self.chk_online.setFont(get_source_han_font(9))
        self.chk_online.setChecked(bool(getattr(config, "slacking_online_enabled", False)))
        cl.addWidget(self.chk_online)

        self._btn_save = QPushButton("保存并生效", self._card)
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.setFixedHeight(34)
        self._btn_save.setFont(get_source_han_font(9, QFont.Weight.Bold))
        self._btn_save.clicked.connect(self._on_save)
        cl.addWidget(self._btn_save)

        outer.addWidget(self._card)
        self.apply_theme(config.theme_mode, config.accent_color)
        self.adjustSize()

    def _on_save(self) -> None:
        self._config.monthly_salary = float(self.spin_salary.value())
        on = self.chk_online.isChecked()
        self._config.slacking_online_enabled = on
        if on and not (getattr(self._config, "slacking_anon_uuid", "") or "").strip():
            self._config.slacking_anon_uuid = uuid.uuid4().hex
        self._config.save()
        if self._on_saved:
            self._on_saved()
        self.close()

    def apply_theme(self, theme_mode: str, accent_color: str) -> None:
        self._is_light = theme_mode == "light"
        self._accent = accent_color
        bg = "#F5F6F8" if self._is_light else "#18181D"
        border = "#DCDFE6" if self._is_light else "#2C2C36"
        fg = "#1D1E22" if self._is_light else "#F5F5F7"
        muted = "#6E707A" if self._is_light else "#9A9AA6"
        inp_bg = "#FFFFFF" if self._is_light else "#16161B"

        self._card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}")
        self._lbl_title.setStyleSheet(f"color: {fg}; border: none;")
        self._lbl_sal.setStyleSheet(f"color: {muted}; border: none;")
        for b in (self._btn_min, self._btn_close):
            b.set_accent_color(accent_color)
            b.set_light_mode(self._is_light)
        self.spin_salary.setStyleSheet(
            f"QDoubleSpinBox {{ background: {inp_bg}; color: {fg}; border: 1px solid {border}; border-radius: 8px; padding: 4px 10px; }}"
            f"QDoubleSpinBox:focus {{ border-color: {accent_color}; }}"
        )
        self.chk_online.setStyleSheet(
            f"QCheckBox {{ color: {fg}; spacing: 6px; border: none; }}"
            f"QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 7px; border: 1.5px solid {muted}; background: {inp_bg}; }}"
            f"QCheckBox::indicator:checked {{ border-color: {accent_color}; background: {accent_color}; }}"
        )
        self._btn_save.setStyleSheet(
            f"QPushButton {{ background-color: {accent_color}; color: #FFFFFF; border: none; border-radius: 8px; }}"
        )
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class _AlarmNoteTooltipPopup(QWidget):
    """圆角深色悬停备注提示卡。"""

    _instance: "_AlarmNoteTooltipPopup | None" = None

    @classmethod
    def instance(cls) -> "_AlarmNoteTooltipPopup":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame(self)
        self._card.setStyleSheet(
            "QFrame { background-color: #1E1E26; border: 1px solid #353545; border-radius: 10px; }"
        )
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(10, 7, 10, 7)
        self._lbl = QLabel(self._card)
        self._lbl.setFont(get_source_han_font(8))
        self._lbl.setStyleSheet("color: #F5F5F7; border: none; background: transparent;")
        self._lbl.setWordWrap(True)
        self._lbl.setMaximumWidth(240)
        cl.addWidget(self._lbl)
        outer.addWidget(self._card)

    def show_for(self, target: QWidget, text: str) -> None:
        if not text:
            return
        self._lbl.setText(text)
        self._lbl.adjustSize()
        self._card.adjustSize()
        self.adjustSize()
        pos = target.mapToGlobal(QPoint(0, target.height() + 6))
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            x = min(max(avail.left() + 8, pos.x()), avail.right() - self.width() - 8)
            y = pos.y()
            if y + self.height() > avail.bottom() - 8:
                y = target.mapToGlobal(QPoint(0, -self.height() - 6)).y()
            pos = QPoint(x, y)
        self.move(pos)
        self.show()
        self.raise_()


class HoverNoteLabel(QLabel):
    """支持超长省略并在鼠标悬停时显示圆角深色完整备注卡片的标签。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._is_truncated = False

    def set_note_text(self, full_text: str, max_width: int) -> None:
        self._full_text = full_text
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(full_text, Qt.TextElideMode.ElideRight, max(20, max_width))
        self._is_truncated = (elided != full_text)
        self.setText(elided)

    def enterEvent(self, event) -> None:
        if self._is_truncated and self._full_text:
            _AlarmNoteTooltipPopup.instance().show_for(self, self._full_text)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if _AlarmNoteTooltipPopup._instance is not None:
            _AlarmNoteTooltipPopup._instance.hide()
        super().leaveEvent(event)

    def hideEvent(self, event) -> None:
        if _AlarmNoteTooltipPopup._instance is not None:
            _AlarmNoteTooltipPopup._instance.hide()
        super().hideEvent(event)


class AlarmAudioPlayer:
    """跨格式闹钟铃声播放器：支持内置合成 WAV 铃声与自定义 MP3/WAV 循环及试听。"""

    _RINGTONE_DIR = os.path.join(DATA_DIR, "ringtones")
    _mci_open = False

    @classmethod
    def _ensure_builtin_wav(cls, ringtone_id: str) -> str:
        os.makedirs(cls._RINGTONE_DIR, exist_ok=True)
        path = os.path.join(cls._RINGTONE_DIR, f"{ringtone_id}.wav")
        if os.path.isfile(path):
            return path
        sr = 22050
        patterns = {
            "builtin_chime": [(880, 0.16), (1174, 0.22), (0, 0.35)],
            "builtin_bell": [(1046, 0.18), (1318, 0.18), (1567, 0.28), (0, 0.4)],
            "builtin_pulse": [(784, 0.12), (0, 0.08), (784, 0.12), (0, 0.45)],
            "builtin_radar": [(987, 0.09), (0, 0.06), (987, 0.09), (0, 0.06), (1318, 0.16), (0, 0.45)],
        }
        seq = patterns.get(ringtone_id, patterns["builtin_chime"])
        frames = bytearray()
        for freq, dur in seq:
            n_samples = int(sr * dur)
            for i in range(n_samples):
                if freq <= 0:
                    val = 0
                else:
                    env = min(1.0, i / 200.0) * min(1.0, (n_samples - i) / 400.0)
                    val = int(14000 * env * math.sin(2.0 * math.pi * freq * i / sr))
                frames.extend(struct.pack("<h", val))
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(bytes(frames))
        return path

    @classmethod
    def resolve_path(cls, ringtone: str) -> str:
        if ringtone in AlarmManager.BUILTIN_RINGTONE_LABELS:
            return cls._ensure_builtin_wav(ringtone)
        return str(ringtone or "")

    @classmethod
    def stop(cls) -> None:
        if sys.platform != "win32":
            return
        try:
            import winsound
            winsound.PlaySound(None, 0)
        except Exception:
            pass
        if cls._mci_open:
            try:
                ctypes.windll.winmm.mciSendStringW("stop alarm_mci", None, 0, 0)
                ctypes.windll.winmm.mciSendStringW("close alarm_mci", None, 0, 0)
            except Exception:
                pass
            cls._mci_open = False

    @classmethod
    def play(cls, ringtone: str, loop: bool = False) -> None:
        cls.stop()
        if not ringtone or ringtone == "none":
            return
        if sys.platform != "win32":
            return
        path = cls.resolve_path(ringtone)
        if not path or not os.path.isfile(path):
            path = cls._ensure_builtin_wav("builtin_chime")
        if path.lower().endswith(".wav"):
            try:
                import winsound
                flags = winsound.SND_FILENAME | winsound.SND_ASYNC
                if loop:
                    flags |= winsound.SND_LOOP
                winsound.PlaySound(path, flags)
                return
            except Exception:
                pass
        try:
            winmm = ctypes.windll.winmm
            winmm.mciSendStringW(f'open "{path}" type mpegvideo alias alarm_mci', None, 0, 0)
            cls._mci_open = True
            cmd = "play alarm_mci repeat" if loop else "play alarm_mci"
            winmm.mciSendStringW(cmd, None, 0, 0)
        except Exception:
            pass


class AlarmEditorDialog(QDialog):
    """独立闹钟编辑面板（支持 6 种提醒模式、每月工作日顺延选择、试听与自定义铃声、列表管理）。"""

    def __init__(self, alarm_mgr: AlarmManager, config: AppConfig, on_changed=None, parent=None):
        super().__init__(parent)
        self._mgr = alarm_mgr
        self._config = config
        self._on_changed = on_changed
        self._is_light = config.theme_mode == "light"
        self._accent = config.accent_color
        self._drag_pos: QPoint | None = None
        self._editing_id: str = ""
        self._editing_enabled: bool = True
        self._editing_pinned: bool = False
        self._previewing = False
        self._last_valid_ringtone_idx = 0

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)
        self.setFixedWidth(MAIN_WIDTH)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame(self)
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(16, 12, 16, 14)
        cl.setSpacing(8)

        top = QHBoxLayout()
        self._lbl_title = QLabel("编辑闹钟", self._card)
        self._lbl_title.setFont(get_source_han_font(10, QFont.Weight.Bold))
        self._btn_min = VectorIconButton("min", self._card, config.accent_color)
        self._btn_min.setFixedSize(22, 22)
        self._btn_min.clicked.connect(self.showMinimized)
        self._btn_close = VectorIconButton("close", self._card, config.accent_color)
        self._btn_close.setFixedSize(22, 22)
        self._btn_close.clicked.connect(self.close)
        top.addWidget(self._lbl_title)
        top.addStretch(1)
        top.addWidget(self._btn_min)
        top.addWidget(self._btn_close)
        cl.addLayout(top)

        # 表单容器
        self._form_box = QFrame(self._card)
        fl = QVBoxLayout(self._form_box)
        fl.setContentsMargins(10, 9, 10, 9)
        fl.setSpacing(7)

        r1 = QHBoxLayout()
        r1.setSpacing(6)
        self._time_edit = QTimeEdit(self._form_box)
        self._time_edit.setDisplayFormat("HH:mm")
        self._time_edit.setTime(QTime(9, 30))
        self._time_edit.setFixedHeight(30)
        self._time_edit.setFont(get_source_han_font(10, QFont.Weight.Bold))

        self._cmb_mode = QComboBox(self._form_box)
        self._cmb_mode.setFixedHeight(30)
        self._cmb_mode.setFont(get_source_han_font(8))
        for mk, ml in AlarmManager.MODES:
            self._cmb_mode.addItem(ml, mk)
        self._cmb_mode.currentIndexChanged.connect(self._on_mode_changed)

        r1.addWidget(self._time_edit, 1)
        r1.addWidget(self._cmb_mode, 2)
        fl.addLayout(r1)

        # 日期 / 日号行
        self._date_row_widget = QWidget(self._form_box)
        dr_l = QHBoxLayout(self._date_row_widget)
        dr_l.setContentsMargins(0, 0, 0, 0)
        dr_l.setSpacing(6)
        self._lbl_date_cap = QLabel("触发日期", self._date_row_widget)
        self._lbl_date_cap.setFont(get_source_han_font(8))
        self._date_edit = QDateEdit(self._date_row_widget)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setFixedHeight(28)
        self._date_edit.setFont(get_source_han_font(8))

        self._spin_month_day = QSpinBox(self._date_row_widget)
        self._spin_month_day.setRange(1, 31)
        self._spin_month_day.setPrefix("每月 ")
        self._spin_month_day.setSuffix(" 日")
        self._spin_month_day.setValue(QDate.currentDate().day())
        self._spin_month_day.setFixedHeight(28)
        self._spin_month_day.setFont(get_source_han_font(8))
        self._spin_month_day.valueChanged.connect(self._update_monthly_workday_preview)

        dr_l.addWidget(self._lbl_date_cap)
        dr_l.addWidget(self._date_edit, 1)
        dr_l.addWidget(self._spin_month_day, 1)
        fl.addWidget(self._date_row_widget)

        # 每月工作日顺延提示框
        self._adj_box = QFrame(self._form_box)
        al = QVBoxLayout(self._adj_box)
        al.setContentsMargins(8, 6, 8, 6)
        al.setSpacing(4)
        self._lbl_adj_warn = QLabel("所选日期恰逢周末/节假日，请选择调整方式：", self._adj_box)
        self._lbl_adj_warn.setFont(get_source_han_font(7, QFont.Weight.Bold))
        adj_radios = QHBoxLayout()
        adj_radios.setSpacing(8)
        self._rb_adj_prev = QRadioButton("提前到最近工作日", self._adj_box)
        self._rb_adj_next = QRadioButton("延后到最近工作日", self._adj_box)
        self._rb_adj_prev.setFont(get_source_han_font(7))
        self._rb_adj_next.setFont(get_source_han_font(7))
        self._rb_adj_next.setChecked(True)
        self._rb_adj_prev.toggled.connect(self._update_monthly_workday_preview)
        adj_radios.addWidget(self._rb_adj_prev)
        adj_radios.addWidget(self._rb_adj_next)
        self._lbl_adj_preview = QLabel("", self._adj_box)
        self._lbl_adj_preview.setFont(get_source_han_font(7, QFont.Weight.Bold))
        al.addWidget(self._lbl_adj_warn)
        al.addLayout(adj_radios)
        al.addWidget(self._lbl_adj_preview)
        self._adj_box.setVisible(False)
        fl.addWidget(self._adj_box)

        # 备注
        self._edit_note = QLineEdit(self._form_box)
        self._edit_note.setFixedHeight(28)
        self._edit_note.setFont(get_source_han_font(8))
        self._edit_note.setPlaceholderText("备注内容（可选）")
        fl.addWidget(self._edit_note)

        # 铃声选择 + 试听
        r_ring = QHBoxLayout()
        r_ring.setSpacing(6)
        self._cmb_ring = QComboBox(self._form_box)
        self._cmb_ring.setFixedHeight(28)
        self._cmb_ring.setFont(get_source_han_font(8))
        self._cmb_ring.currentIndexChanged.connect(self._on_ringtone_changed)

        self._btn_preview = QPushButton("试听", self._form_box)
        self._btn_preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_preview.setFixedSize(52, 28)
        self._btn_preview.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._btn_preview.clicked.connect(self._toggle_preview)

        r_ring.addWidget(self._cmb_ring, 1)
        r_ring.addWidget(self._btn_preview)
        fl.addLayout(r_ring)

        # 保存 / 重置
        r_act = QHBoxLayout()
        r_act.setSpacing(6)
        self._btn_reset = QPushButton("重置表单", self._form_box)
        self._btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_reset.setFixedHeight(30)
        self._btn_reset.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._btn_reset.clicked.connect(self._reset_form)

        self._btn_save = QPushButton("保存闹钟", self._form_box)
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.setFixedHeight(30)
        self._btn_save.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._btn_save.clicked.connect(self._on_save_clicked)

        r_act.addWidget(self._btn_reset)
        r_act.addWidget(self._btn_save, 1)
        fl.addLayout(r_act)

        cl.addWidget(self._form_box)

        self._lbl_list_cap = QLabel("已设置闹钟", self._card)
        self._lbl_list_cap.setFont(get_source_han_font(8, QFont.Weight.Bold))
        cl.addWidget(self._lbl_list_cap)

        self._scroll = QScrollArea(self._card)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(130)
        self._list_box = QWidget()
        self._list_layout = QVBoxLayout(self._list_box)
        self._list_layout.setContentsMargins(0, 0, 2, 0)
        self._list_layout.setSpacing(5)
        self._scroll.setWidget(self._list_box)
        cl.addWidget(self._scroll)

        outer.addWidget(self._card)
        self._reload_ringtones("none")
        self._on_mode_changed()
        self.refresh_list()
        self.apply_theme(config.theme_mode, config.accent_color)
        self.adjustSize()

    def _reload_ringtones(self, select_val: str | None = None) -> None:
        self._cmb_ring.blockSignals(True)
        self._cmb_ring.clear()
        self._cmb_ring.addItem("没有铃声", "none")
        for rk, rl in AlarmManager.BUILTIN_RINGTONES:
            self._cmb_ring.addItem(rl, rk)
        for path in self._mgr.list_custom_ringtones():
            self._cmb_ring.addItem(os.path.basename(path), path)
        self._cmb_ring.addItem("添加铃声...", "__ADD_CUSTOM__")
        target_idx = 0
        if select_val:
            idx = self._cmb_ring.findData(select_val)
            if idx >= 0:
                target_idx = idx
        self._cmb_ring.setCurrentIndex(target_idx)
        self._last_valid_ringtone_idx = target_idx
        self._cmb_ring.blockSignals(False)
        self._sync_preview_btn_state()

    def _sync_preview_btn_state(self) -> None:
        val = str(self._cmb_ring.currentData() or "none")
        has_sound = val != "none" and val != "__ADD_CUSTOM__"
        if not has_sound and self._previewing:
            AlarmAudioPlayer.stop()
            self._previewing = False
            self._btn_preview.setText("试听")
        self._btn_preview.setEnabled(has_sound)
        self._btn_preview.setCursor(
            Qt.CursorShape.PointingHandCursor if has_sound else Qt.CursorShape.ArrowCursor
        )

    def _on_ringtone_changed(self, idx: int) -> None:
        val = self._cmb_ring.itemData(idx)
        if val == "__ADD_CUSTOM__":
            path, _ = QFileDialog.getOpenFileName(
                self,
                "选择本地铃声文件",
                "",
                "音频文件 (*.mp3 *.wav)",
            )
            if path and os.path.isfile(path):
                self._mgr.add_custom_ringtone(path)
                self._reload_ringtones(os.path.abspath(path))
            else:
                self._cmb_ring.blockSignals(True)
                self._cmb_ring.setCurrentIndex(self._last_valid_ringtone_idx)
                self._cmb_ring.blockSignals(False)
                self._sync_preview_btn_state()
        else:
            self._last_valid_ringtone_idx = idx
            self._sync_preview_btn_state()

    def _toggle_preview(self) -> None:
        val = str(self._cmb_ring.currentData() or "none")
        if val == "none":
            return
        if self._previewing:
            AlarmAudioPlayer.stop()
            self._previewing = False
            self._btn_preview.setText("试听")
        else:
            AlarmAudioPlayer.play(val, loop=False)
            self._previewing = True
            self._btn_preview.setText("停止")
            QTimer.singleShot(2500, self._stop_preview_label)

    def _stop_preview_label(self) -> None:
        if self._previewing:
            self._previewing = False
            self._btn_preview.setText("试听")

    def _on_mode_changed(self) -> None:
        mode = str(self._cmb_mode.currentData() or "daily")
        is_date = mode in ("once", "next_day")
        is_month = mode in ("monthly", "monthly_workday")
        self._date_row_widget.setVisible(is_date or is_month)
        self._date_edit.setVisible(is_date)
        self._spin_month_day.setVisible(is_month)
        if mode == "next_day" and not self._editing_id:
            self._date_edit.setDate(QDate.currentDate().addDays(1))
        elif mode == "once" and not self._editing_id:
            self._date_edit.setDate(QDate.currentDate())
        self._update_monthly_workday_preview()
        self.adjustSize()

    def _update_monthly_workday_preview(self) -> None:
        mode = str(self._cmb_mode.currentData() or "daily")
        if mode != "monthly_workday":
            self._adj_box.setVisible(False)
            self.adjustSize()
            return
        now = datetime.now()
        day_num = self._spin_month_day.value()
        adj = "prev" if self._rb_adj_prev.isChecked() else "next"
        adj_d, was_adj, _raw_d = AlarmManager.adjust_monthly_workday(now.year, now.month, day_num, adj, self._config)
        t = self._time_edit.time()
        if datetime(adj_d.year, adj_d.month, adj_d.day, t.hour(), t.minute()) <= now:
            ny, nm = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
            adj_d, was_adj, _raw_d = AlarmManager.adjust_monthly_workday(ny, nm, day_num, adj, self._config)
        self._adj_box.setVisible(was_adj)
        if was_adj:
            self._lbl_adj_preview.setText(f"实际触发日期：{adj_d.strftime('%Y-%m-%d')}")
        self.adjustSize()

    def _reset_form(self) -> None:
        self._editing_id = ""
        self._editing_enabled = True
        self._editing_pinned = False
        self._time_edit.setTime(QTime(9, 30))
        self._cmb_mode.setCurrentIndex(2)
        self._date_edit.setDate(QDate.currentDate())
        self._spin_month_day.setValue(QDate.currentDate().day())
        self._rb_adj_next.setChecked(True)
        self._edit_note.clear()
        self._reload_ringtones("none")
        self._btn_save.setText("保存闹钟")
        self._on_mode_changed()

    def _on_save_clicked(self) -> None:
        t = self._time_edit.time()
        mode = str(self._cmb_mode.currentData() or "daily")
        item = {
            "id": self._editing_id,
            "enabled": self._editing_enabled if self._editing_id else True,
            "pinned": self._editing_pinned if self._editing_id else False,
            "hour": t.hour(),
            "minute": t.minute(),
            "mode": mode,
            "target_date": self._date_edit.date().toString("yyyy-MM-dd"),
            "month_day": self._spin_month_day.value(),
            "workday_adjust": "prev" if self._rb_adj_prev.isChecked() else "next",
            "note": self._edit_note.text().strip(),
            "ringtone": str(self._cmb_ring.currentData() or "none"),
            "snooze_until": 0.0,
            "last_fired_key": "",
        }
        self._mgr.upsert_alarm(item)
        self._reset_form()
        self.refresh_list()
        if self._on_changed:
            self._on_changed()

    def _edit_alarm(self, alarm: dict) -> None:
        self._editing_id = str(alarm.get("id") or "")
        self._editing_enabled = bool(alarm.get("enabled", True))
        self._editing_pinned = bool(alarm.get("pinned", False))
        self._time_edit.setTime(QTime(int(alarm.get("hour", 9)), int(alarm.get("minute", 30))))
        m_idx = self._cmb_mode.findData(str(alarm.get("mode") or "daily"))
        if m_idx >= 0:
            self._cmb_mode.setCurrentIndex(m_idx)
        qd = QDate.fromString(str(alarm.get("target_date") or ""), "yyyy-MM-dd")
        if qd.isValid():
            self._date_edit.setDate(qd)
        self._spin_month_day.setValue(int(alarm.get("month_day") or 1))
        if alarm.get("workday_adjust") == "prev":
            self._rb_adj_prev.setChecked(True)
        else:
            self._rb_adj_next.setChecked(True)
        self._edit_note.setText(str(alarm.get("note") or ""))
        self._reload_ringtones(str(alarm.get("ringtone") or "none"))
        self._btn_save.setText("更新闹钟")
        self._on_mode_changed()

    def _delete_alarm(self, alarm_id: str) -> None:
        self._mgr.delete_alarm(alarm_id)
        if self._editing_id == alarm_id:
            self._reset_form()
        self.refresh_list()
        if self._on_changed:
            self._on_changed()

    def _on_toggle_alarm(self, alarm_id: str, enabled: bool) -> None:
        self._mgr.set_enabled(alarm_id, enabled)
        if self._editing_id == alarm_id:
            self._editing_enabled = bool(enabled)
        if self._on_changed:
            self._on_changed()

    def _on_pin_toggled(self, alarm_id: str, pinned: bool) -> None:
        self._mgr.set_pinned(alarm_id, pinned)
        if self._editing_id == alarm_id:
            self._editing_pinned = bool(pinned)
        elif pinned:
            self._editing_pinned = False
        self.refresh_list()
        if self._on_changed:
            self._on_changed()

    def refresh_list(self) -> None:
        while self._list_layout.count() > 0:
            it = self._list_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        fg = "#1D1E22" if self._is_light else "#F5F5F7"
        muted = "#6E707A" if self._is_light else "#9A9AA6"
        row_bg = "#F7F8FA" if self._is_light else "#202028"
        border = "#E6E8EF" if self._is_light else "#2D2D38"
        inp_bg = "#FFFFFF" if self._is_light else "#16161B"
        dis_fg = "#B5B8C2" if self._is_light else "#555562"

        alarms = self._mgr.list_alarms()
        if not alarms:
            empty = QLabel("暂无已设置闹钟", self._list_box)
            empty.setFont(get_source_han_font(8))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFixedHeight(70)
            empty.setStyleSheet(f"color: {muted}; border: none; background: transparent;")
            self._list_layout.addWidget(empty)
            self._list_layout.addStretch(1)
            return

        pinned_id = next((str(a.get("id") or "") for a in alarms if a.get("pinned")), "")
        pin_chk_qss = (
            f"QCheckBox {{ color: {muted}; spacing: 3px; border: none; background: transparent; }}"
            f"QCheckBox:checked {{ color: {self._accent}; }}"
            f"QCheckBox:disabled {{ color: {dis_fg}; }}"
            f"QCheckBox::indicator {{ width: 12px; height: 12px; border-radius: 6px; border: 1.5px solid {muted}; background: {inp_bg}; }}"
            f"QCheckBox::indicator:checked {{ border-color: {self._accent}; background: {self._accent}; }}"
            f"QCheckBox::indicator:disabled {{ border-color: {dis_fg}; background: transparent; }}"
        )

        for a in alarms:
            aid = str(a.get("id") or "")
            row = QFrame(self._list_box)
            row.setFixedHeight(34)
            row.setStyleSheet(f"QFrame {{ background-color: {row_bg}; border: 1px solid {border}; border-radius: 7px; }}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 2, 6, 2)
            rl.setSpacing(5)

            t_str = f"{int(a.get('hour', 9)):02d}:{int(a.get('minute', 30)):02d}"
            m_lbl = AlarmManager.MODE_LABELS.get(str(a.get("mode") or "daily"), "每日")
            note_txt = str(a.get("note") or "").strip()

            lbl_head = QLabel(f"{t_str} · {m_lbl}", row)
            lbl_head.setFont(get_source_han_font(8, QFont.Weight.Bold))
            lbl_head.setStyleSheet(f"color: {fg}; border: none; background: transparent;")
            rl.addWidget(lbl_head)

            if note_txt:
                lbl_note = HoverNoteLabel(row)
                lbl_note.setFont(get_source_han_font(8))
                lbl_note.setStyleSheet(f"color: {muted}; border: none; background: transparent;")
                lbl_note.set_note_text(note_txt, 68)
                rl.addWidget(lbl_note, 1)
            else:
                rl.addStretch(1)

            sw = CapsuleToggleSwitch(row, accent_color=self._accent, is_light=self._is_light)
            sw.setToolTip("启用/关闭闹钟")
            sw.blockSignals(True)
            sw.set_checked(bool(a.get("enabled", True)))
            sw.blockSignals(False)
            sw.toggled.connect(lambda checked, target_id=aid: self._on_toggle_alarm(target_id, checked))

            chk_pin = QCheckBox("置顶", row)
            chk_pin.setFont(get_source_han_font(7))
            chk_pin.setStyleSheet(pin_chk_qss)
            is_pinned = bool(a.get("pinned", False))
            chk_pin.blockSignals(True)
            chk_pin.setChecked(is_pinned)
            chk_pin.blockSignals(False)
            if pinned_id and aid != pinned_id:
                chk_pin.setEnabled(False)
                chk_pin.setCursor(Qt.CursorShape.ArrowCursor)
            else:
                chk_pin.setEnabled(True)
                chk_pin.setCursor(Qt.CursorShape.PointingHandCursor)
            chk_pin.toggled.connect(lambda checked, target_id=aid: self._on_pin_toggled(target_id, checked))

            btn_ed = QPushButton("编辑", row)
            btn_ed.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_ed.setFixedSize(28, 20)
            btn_ed.setFont(get_source_han_font(7, QFont.Weight.Bold))
            btn_ed.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {self._accent}; border: none; }}"
                f"QPushButton:hover {{ text-decoration: underline; }}"
            )
            btn_ed.clicked.connect(lambda checked=False, item=dict(a): self._edit_alarm(item))

            btn_del = QPushButton("删除", row)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setFixedSize(28, 20)
            btn_del.setFont(get_source_han_font(7))
            btn_del.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {muted}; border: none; }}"
                f"QPushButton:hover {{ color: {INVALID_RED}; }}"
            )
            btn_del.clicked.connect(lambda checked=False, target_id=aid: self._delete_alarm(target_id))

            rl.addWidget(sw)
            rl.addWidget(chk_pin)
            rl.addWidget(btn_ed)
            rl.addWidget(btn_del)
            self._list_layout.addWidget(row)
        self._list_layout.addStretch(1)

    def apply_theme(self, theme_mode: str, accent_color: str) -> None:
        self._is_light = theme_mode == "light"
        self._accent = accent_color
        bg = "#F5F6F8" if self._is_light else "#18181D"
        border = "#DCDFE6" if self._is_light else "#2C2C36"
        fg = "#1D1E22" if self._is_light else "#F5F5F7"
        muted = "#6E707A" if self._is_light else "#9A9AA6"
        sub_bg = "#ECEDF2" if self._is_light else "#202027"
        inp_bg = "#FFFFFF" if self._is_light else "#16161B"
        scroll_handle = "#C5C8D4" if self._is_light else "#3A3A46"

        self._card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}")
        self._lbl_title.setStyleSheet(f"color: {fg}; border: none;")
        self._lbl_date_cap.setStyleSheet(f"color: {muted}; border: none;")
        self._lbl_list_cap.setStyleSheet(f"color: {muted}; border: none;")
        self._form_box.setStyleSheet(f"QFrame {{ background-color: {sub_bg}; border: 1px solid {border}; border-radius: 12px; }}")
        self._adj_box.setStyleSheet(f"QFrame {{ background-color: {inp_bg}; border: 1px solid {accent_color}; border-radius: 8px; }}")
        self._lbl_adj_warn.setStyleSheet(f"color: {accent_color}; border: none;")
        self._lbl_adj_preview.setStyleSheet(f"color: {GREEN_ACCENT}; border: none;")
        for b in (self._btn_min, self._btn_close):
            b.set_accent_color(accent_color)
            b.set_light_mode(self._is_light)

        inp_qss = (
            f"QTimeEdit, QDateEdit, QSpinBox, QComboBox, QLineEdit {{ background: {inp_bg}; color: {fg}; border: 1px solid {border}; border-radius: 6px; padding: 2px 6px; }}"
            f"QTimeEdit:focus, QDateEdit:focus, QSpinBox:focus, QComboBox:focus, QLineEdit:focus {{ border-color: {accent_color}; }}"
        )
        for w in (self._time_edit, self._cmb_mode, self._date_edit, self._spin_month_day, self._edit_note, self._cmb_ring):
            w.setStyleSheet(inp_qss)
        chk_qss = (
            f"QCheckBox, QRadioButton {{ color: {fg}; spacing: 5px; border: none; }}"
            f"QCheckBox::indicator, QRadioButton::indicator {{ width: 13px; height: 13px; border-radius: 6px; border: 1.5px solid {muted}; background: {inp_bg}; }}"
            f"QCheckBox::indicator:checked, QRadioButton::indicator:checked {{ border-color: {accent_color}; background: {accent_color}; }}"
        )
        for w in (self._rb_adj_prev, self._rb_adj_next):
            w.setStyleSheet(chk_qss)
        dis_btn_fg = "#B5B8C2" if self._is_light else "#555562"
        sub_btn = (
            f"QPushButton {{ background-color: {inp_bg}; color: {fg}; border: 1px solid {border}; border-radius: 7px; }}"
            f"QPushButton:hover {{ border-color: {accent_color}; color: {accent_color}; }}"
            f"QPushButton:pressed {{ padding-top: 2px; }}"
            f"QPushButton:disabled {{ color: {dis_btn_fg}; border-color: {border}; }}"
        )
        self._btn_preview.setStyleSheet(sub_btn)
        self._btn_reset.setStyleSheet(sub_btn)
        self._btn_save.setStyleSheet(
            f"QPushButton {{ background-color: {accent_color}; color: #FFFFFF; border: none; border-radius: 7px; }}"
            f"QPushButton:pressed {{ padding-top: 2px; }}"
        )
        self._list_box.setStyleSheet("background: transparent;")
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background: transparent; }}"
            f"QScrollBar:vertical {{ background: transparent; width: 5px; }}"
            f"QScrollBar::handle:vertical {{ background: {scroll_handle}; border-radius: 2px; }}"
        )
        self.refresh_list()
        self.update()

    def closeEvent(self, event) -> None:
        if self._previewing:
            AlarmAudioPlayer.stop()
            self._previewing = False
        super().closeEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class AlarmAlertDialog(QDialog):
    """闹钟到点无边框置顶圆角提醒浮窗（循环响铃 + 5分钟稍后提醒 / 关闭提醒）。"""

    def __init__(self, alarm: dict, alarm_mgr: AlarmManager, theme_mode: str, accent_color: str, on_closed=None, parent=None):
        super().__init__(parent)
        self._alarm = dict(alarm)
        self._mgr = alarm_mgr
        self._on_closed = on_closed
        self._is_light = theme_mode == "light"
        self._accent = accent_color
        self._drag_pos: QPoint | None = None

        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)
        self.setFixedWidth(308)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame(self)
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(8)

        t_str = f"{int(alarm.get('hour', 9)):02d}:{int(alarm.get('minute', 30)):02d}"
        m_lbl = AlarmManager.MODE_LABELS.get(str(alarm.get("mode") or "daily"), "闹钟提醒")
        note_str = str(alarm.get("note") or "").strip() or "时间到了"

        self._lbl_badge = QLabel(f"闹钟提醒 · {m_lbl}", self._card)
        self._lbl_badge.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._lbl_time = QLabel(t_str, self._card)
        self._lbl_time.setFont(get_source_han_font(26, QFont.Weight.Bold))
        self._lbl_note = QLabel(note_str, self._card)
        self._lbl_note.setFont(get_source_han_font(9))
        self._lbl_note.setWordWrap(True)

        cl.addWidget(self._lbl_badge)
        cl.addWidget(self._lbl_time)
        cl.addWidget(self._lbl_note)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_snooze = QPushButton("稍后提醒 (5分钟)", self._card)
        self._btn_snooze.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_snooze.setFixedHeight(32)
        self._btn_snooze.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._btn_snooze.clicked.connect(self._on_snooze)

        self._btn_dismiss = QPushButton("关闭提醒", self._card)
        self._btn_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_dismiss.setFixedHeight(32)
        self._btn_dismiss.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self._btn_dismiss.clicked.connect(self._on_dismiss)

        btn_row.addWidget(self._btn_snooze, 1)
        btn_row.addWidget(self._btn_dismiss, 1)
        cl.addLayout(btn_row)

        outer.addWidget(self._card)
        self.apply_theme(theme_mode, accent_color)
        self.adjustSize()
        self._position_bottom_right()
        ringtone = str(alarm.get("ringtone") or "none")
        if ringtone != "none":
            AlarmAudioPlayer.play(ringtone, loop=True)

    def _position_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            self.move(avail.right() - self.width() - 18, avail.bottom() - self.height() - 18)

    def _on_snooze(self) -> None:
        AlarmAudioPlayer.stop()
        self._mgr.snooze_alarm(str(self._alarm.get("id") or ""), 300)
        if self._on_closed:
            self._on_closed()
        self.close()

    def _on_dismiss(self) -> None:
        AlarmAudioPlayer.stop()
        if self._on_closed:
            self._on_closed()
        self.close()

    def closeEvent(self, event) -> None:
        AlarmAudioPlayer.stop()
        super().closeEvent(event)

    def apply_theme(self, theme_mode: str, accent_color: str) -> None:
        self._is_light = theme_mode == "light"
        self._accent = accent_color
        bg = "#F5F6F8" if self._is_light else "#18181D"
        border = "#DCDFE6" if self._is_light else "#2C2C36"
        fg = "#1D1E22" if self._is_light else "#F5F5F7"
        muted = "#6E707A" if self._is_light else "#9A9AA6"
        pill_bg = "#ECEDF2" if self._is_light else "#22222A"

        self._card.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1.5px solid {accent_color}; border-radius: 16px; }}")
        self._lbl_badge.setStyleSheet(f"color: {accent_color}; border: none;")
        self._lbl_time.setStyleSheet(f"color: {fg}; border: none;")
        self._lbl_note.setStyleSheet(f"color: {muted}; border: none;")
        self._btn_snooze.setStyleSheet(
            f"QPushButton {{ background-color: {pill_bg}; color: {fg}; border: 1px solid {border}; border-radius: 8px; }}"
            f"QPushButton:hover {{ border-color: {accent_color}; color: {accent_color}; }}"
            f"QPushButton:pressed {{ padding-top: 2px; }}"
        )
        self._btn_dismiss.setStyleSheet(
            f"QPushButton {{ background-color: {accent_color}; color: #FFFFFF; border: none; border-radius: 8px; }}"
            f"QPushButton:pressed {{ padding-top: 2px; }}"
        )
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = AppConfig.load()
        self.comp_manager = CompTimeManager()

        # 法定节假日年份与数据缓存
        self.base_year = datetime.now().year
        self.selected_holiday_year = self.base_year
        self.raw_holidays_by_year = {
            self.base_year: HolidayService.get_initial_raw_data(self.base_year),
            self.base_year + 1: HolidayService.get_initial_raw_data(self.base_year + 1),
        }
        self._last_holiday_render_date: date | None = None
        self._holiday_workers: list[HolidayFetchWorker] = []
        self._synced_holiday_years: set[int] = set()
        self._holiday_popout_dlg: HolidayCalendarDialog | None = None
        self._active_comp_dlg: CompTimeDialog | None = None

        # 设置页自定义休息暂存状态（点击保存并生效时写入 config）
        self._temp_custom_rest = {
            "custom_rest_dates": list(self.config.custom_rest_dates),
            "custom_fixed_weekdays": list(self.config.custom_fixed_weekdays),
            "custom_monthly_selected_days_enabled": self.config.custom_monthly_selected_days_enabled,
        }

        self._drag_pos: QPoint | None = None

        self._tooltip_manager = ThemedToolTipManager(self)
        self._clip_hover_popup = _ClipHoverPreviewPopup()
        self._btn_feedback_filter = GlobalButtonPressFeedbackFilter(self)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self._tooltip_manager)
            app.installEventFilter(self._clip_hover_popup)
            app.installEventFilter(self._btn_feedback_filter)

        self.setFixedSize(MAIN_WIDTH, 720)
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        if self.config.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle(APP_BRAND_TITLE)

        self._force_quit = False
        self._quote_idx = 0
        self._active_quote_pool_key = ""
        self._client_id: str = f"PT-{uuid.uuid4().hex[:6].upper()}"
        self._cloud_cfg: dict = _load_messages_cache()
        self._my_feedbacks: list[dict] = list(self._cloud_cfg.get("my_feedbacks") or [])
        self._latest_today_earned: float = 0.0
        self._last_feedback_success_ts: float = 0.0
        self._update_check_worker: UpdateCheckWorker | None = None
        self._update_download_worker: UpdateDownloadWorker | None = None
        self._feedback_worker: FeedbackSubmitWorker | None = None
        self._active_feedback_dlg: FeedbackDialog | None = None
        self._active_update_dlg: UpdateDialog | None = None
        self._active_cache_dlg: CacheManagerDialog | None = None
        self._active_about_dlg: AboutDialog | None = None
        self._app_qicon: QIcon | None = None
        self._pending_update_info: dict | None = None
        self._has_new_update: bool = False
        self._has_unread_feedback: bool = False
        self._toast = ToastPopup(self)
        self._cloud_bridge = CloudConfigBridge(self._client_id, self.config.device_id, self)
        self._cloud_bridge.config_ready.connect(self._on_cloud_config_ready)
        self._silent_update_bridge = SilentUpdateBridge(self)
        self._silent_update_bridge.update_found.connect(self._on_silent_update_found)
        self._dl_bridge = FastDownloadBridge(self)
        self._dl_bridge.progress_signal.connect(self._on_dl_progress)
        self._dl_bridge.finished_signal.connect(self._on_dl_finished)
        self._dl_bridge.error_signal.connect(self._on_dl_error)
        self._dl_bridge.cancelled_signal.connect(self._on_dl_cancelled)
        self._last_completed_file: str = ""

        # IdleMeter 启动自检：保持与现有统一配置/缓存目录（C:\Users\<用户名>\.摸鱼小工具）完全兼容，不破坏已有用户配置与缓存
        effective_cache_dir = CacheManager.get_effective_cache_dir(self.config)
        ClipboardHistoryStore.set_root_dir(effective_cache_dir)
        self._clip_filter: str = "all"
        self._clip_items: list[dict] = ClipboardHistoryStore.load(
            bool(getattr(self.config, "clipboard_keep_next_day", False))
        )
        self._clip_last_date: str = datetime.now().strftime("%Y-%m-%d")
        self._clip_watcher = ClipboardWatcherBridge(self)
        self._clip_watcher.clipboard_changed.connect(self._on_system_clipboard_changed)

        self._lan_bridge = LanTransferBridge(self)
        self._lan_bridge.text_received.connect(self._on_lan_text_received)
        self._lan_bridge.file_received.connect(self._on_lan_file_received)
        self._lan_server = LanTransferServer(
            receive_dir=os.path.join(effective_cache_dir, "手机互传接收"),
            on_receive_text=self._lan_bridge.text_received.emit,
            on_receive_file=self._lan_bridge.file_received.emit,
            theme_mode=self.config.theme_mode,
            accent_color=self.config.accent_color,
        )
        self._tunnel_mgr = CloudflaredTunnelManager(self)
        self._tunnel_mgr.download_finished.connect(self._on_global_cf_download_finished)
        self._tunnel_mgr.tunnel_ready.connect(self._on_global_tunnel_ready)
        self._tunnel_mgr.edge_state_changed.connect(self._on_global_edge_state_changed)
        self._tunnel_mgr.tunnel_failed.connect(self._on_global_tunnel_failed)
        self._lan_async_bridge = _LanAsyncBridge(self)
        self._lan_async_bridge.lan_ready.connect(self._on_lan_async_ready)
        self._lan_async_bridge.lan_failed.connect(self._on_lan_async_failed)
        self._lan_async_bridge.file_post_ready.connect(self._on_lan_file_post_ready)
        self._lan_async_bridge.share_packed.connect(self._on_share_packed)
        self._lan_async_bridge.share_pack_failed.connect(self._on_share_pack_failed)
        self._lan_async_bridge.share_downloaded.connect(self._on_share_downloaded)
        self._lan_async_bridge.share_state_changed.connect(self._on_share_state_changed)
        self._share_reset_timer = QTimer(self)
        self._share_reset_timer.setSingleShot(True)
        self._share_reset_timer.timeout.connect(lambda: self._on_share_stop_clicked(silent=True))
        self._share_badge_state: str = "ready"  # "ready" | "downloading" | "completed"
        self._lan_start_seq: int = 0
        self._lan_starting: bool = False
        self._phone_switch_on: bool = False
        self._share_seq: int = 0
        self._share_active_id: str = ""
        self._share_public_url: str = ""
        self._share_auto_copied: bool = False
        self._share_tunnel_pending: bool = False
        self._active_lan_dlg: LanTransferDialog | None = None
        self._ocr_bridge = OcrWorkerBridge(self)
        self._ocr_bridge.finished.connect(self._on_ocr_done)
        self._active_overlays: list[ScreenCaptureOverlay] = []

        self._mini_mode: bool = False
        self._slacking_stats = SlackingStatsManager()
        self.is_slacking_active: bool = False
        self._slacking_active: bool = False
        self._slacking_start_ts: float = 0.0
        self._visible_fish_seconds: float = 0.0
        self._last_tick_ts: float = time.monotonic()
        self._active_slacking_dlg: SlackingDashboardDialog | None = None
        self._active_progress_cfg_dlg: ProgressTargetConfigDialog | None = None
        self._active_slacking_cfg_dlg: SlackingSettingsDialog | None = None
        self._alarm_mgr = AlarmManager()
        self._active_alarm_editor_dlg: AlarmEditorDialog | None = None
        self._active_alarm_alerts: list[AlarmAlertDialog] = []
        self._slacking_heartbeat_timer = QTimer(self)
        self._slacking_heartbeat_timer.setInterval(180 * 1000)
        self._slacking_heartbeat_timer.timeout.connect(self._send_slacking_anon_heartbeat)
        self._slacking_heartbeat_timer.start()

        self._init_ui()
        self._init_tray_icon()
        self._apply_theme()
        self._apply_app_mode(save=False)
        self._rebuild_clipboard_list()
        self._refresh_alarm_card()
        self._clip_watcher.start()
        self._update_feedback_badge()
        self._rebuild_holiday_rows()
        self._refresh_comp_time_card()
        self._sync_initial_quote()
        self._refresh_metrics()

        self._start_holiday_online_sync(self.base_year)
        self._start_holiday_online_sync(self.base_year + 1)

        # 核心定时器：200ms 刷新一次
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(200)

        # 状态文案自动向上无缝滚动切换（5 秒轮播）
        self._last_status_quote_ms = 0
        self._save_btn_confirming: bool = False
        self._save_btn_timer = QTimer(self)
        self._save_btn_timer.setSingleShot(True)
        self._save_btn_timer.timeout.connect(self._restore_save_cfg_btn_state)

        self.quote_timer = QTimer(self)
        self.quote_timer.timeout.connect(self._on_quote_timer)
        self.quote_timer.start(self._get_status_quote_interval_ms())

        # 启动即刻执行首轮云端同步，之后每 15 秒后台轮询一次
        self._cloud_bridge.start_polling(CLOUD_FETCH_INTERVAL_MS / 1000.0)

        # 启动 3 秒后及每隔 6 小时静默检测更新
        QTimer.singleShot(SILENT_UPDATE_DELAY_MS, self._silent_update_bridge.check_async)
        self.silent_update_timer = QTimer(self)
        self.silent_update_timer.timeout.connect(self._silent_update_bridge.check_async)
        self.silent_update_timer.start(SILENT_UPDATE_INTERVAL_MS)

    def _refresh_app_icons(self) -> None:
        """按当前主题强调色实时重绘多尺寸（16/32/64）动态矢量应用图标，并同步刷新任务栏、标题栏、托盘与关于窗口。"""
        acc = self.config.accent_color
        qicon = _build_app_qicon(acc, sizes=(16, 32, 64))
        self._app_qicon = qicon
        app = QApplication.instance()
        if app is not None:
            app.setWindowIcon(qicon)
        self.setWindowIcon(qicon)
        if hasattr(self, "lbl_app_icon"):
            self.lbl_app_icon.setPixmap(_build_app_qpixmap(acc, size=20, hidpi=True))
        if hasattr(self, "tray_icon"):
            self.tray_icon.setIcon(qicon)
            self.tray_icon.setToolTip(APP_BRAND_TITLE)

    def _init_tray_icon(self) -> None:
        tray_icon_obj = _build_app_qicon(self.config.accent_color, sizes=(16, 32, 64))
        self._app_qicon = tray_icon_obj
        self.tray_icon = QSystemTrayIcon(tray_icon_obj, self)
        self.tray_icon.setToolTip(APP_BRAND_TITLE)

        self.tray_menu = QMenu(self)
        self.act_tray_open = QAction("打开", self)
        self.act_tray_open.triggered.connect(self._restore_from_tray)
        self.act_tray_quit = QAction("退出", self)
        self.act_tray_quit.triggered.connect(self._quit_app)
        self.tray_menu.addAction(self.act_tray_open)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.act_tray_quit)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_tray()

    def _get_managed_child_windows(self) -> list[QWidget]:
        candidates = (
            getattr(self, "_holiday_popout_dlg", None),
            getattr(self, "_active_lan_dlg", None),
            getattr(self, "_active_comp_dlg", None),
            getattr(self, "_active_cache_dlg", None),
            getattr(self, "_active_about_dlg", None),
            getattr(self, "_active_feedback_dlg", None),
            getattr(self, "_active_update_dlg", None),
            getattr(self, "_active_slacking_dlg", None),
            getattr(self, "_active_progress_cfg_dlg", None),
            getattr(self, "_active_slacking_cfg_dlg", None),
            getattr(self, "_active_alarm_editor_dlg", None),
            *list(getattr(self, "_active_alarm_alerts", [])),
        )
        res: list[QWidget] = []
        for w in candidates:
            if w is not None:
                try:
                    _ = w.isVisible()
                    res.append(w)
                except RuntimeError:
                    pass
        return res

    def _sync_children_win32_ownership(self) -> None:
        keep = bool(getattr(self.config, "keep_children_on_hide", False))
        for w in self._get_managed_child_windows():
            _decouple_win32_window_owner(w, decouple=keep, owner_widget=self)

    def _on_keep_children_on_hide_toggled(self, checked: bool) -> None:
        self.config.keep_children_on_hide = bool(checked)
        self.config.save()
        self._sync_children_win32_ownership()

    def _on_minimize_main_window(self) -> None:
        keep = bool(getattr(self.config, "keep_children_on_hide", False))
        visible_children = [w for w in self._get_managed_child_windows() if w.isVisible() and not w.isMinimized()]
        if keep:
            for w in visible_children:
                _decouple_win32_window_owner(w, decouple=True, owner_widget=self)
            self.showMinimized()
            for w in visible_children:
                try:
                    if not w.isVisible() or w.isMinimized():
                        w.showNormal()
                    _decouple_win32_window_owner(w, decouple=True, owner_widget=self)
                except RuntimeError:
                    pass
        else:
            self._children_hidden_with_main = list(visible_children)
            for w in visible_children:
                try:
                    w.hide()
                except RuntimeError:
                    pass
            self.showMinimized()

    def _minimize_to_tray(self) -> None:
        if getattr(self, "_slacking_active", False):
            self._stop_slacking()
        if not self.tray_icon.isVisible():
            self.tray_icon.show()
        keep = bool(getattr(self.config, "keep_children_on_hide", False))
        visible_children = [w for w in self._get_managed_child_windows() if w.isVisible() and not w.isMinimized()]
        if keep:
            for w in visible_children:
                _decouple_win32_window_owner(w, decouple=True, owner_widget=self)
            self.hide()
            for w in visible_children:
                try:
                    if not w.isVisible():
                        w.showNormal()
                    _decouple_win32_window_owner(w, decouple=True, owner_widget=self)
                except RuntimeError:
                    pass
        else:
            self._children_hidden_with_main = list(visible_children)
            for w in visible_children:
                try:
                    w.hide()
                except RuntimeError:
                    pass
            self.hide()

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._restore_children_hidden_with_main()

    def _restore_children_hidden_with_main(self) -> None:
        hidden_list = list(getattr(self, "_children_hidden_with_main", None) or [])
        self._children_hidden_with_main = []
        for w in hidden_list:
            try:
                w.showNormal()
                w.raise_()
            except RuntimeError:
                pass
        self._sync_children_win32_ownership()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if not self.isMinimized() and self.isVisible():
                QTimer.singleShot(10, self._restore_children_hidden_with_main)

    def _quit_app(self) -> None:
        self._force_quit = True
        self.close()

    def closeEvent(self, event) -> None:
        if not self._force_quit:
            behavior = getattr(self.config, "close_behavior", "ask")
            if behavior == "tray":
                event.ignore()
                self._minimize_to_tray()
                return
            if behavior == "ask":
                dlg = CloseConfirmDialog(
                    theme_mode=self.config.theme_mode,
                    accent_color=self.config.accent_color,
                    parent=self,
                )
                dlg.exec()
                if dlg.choice == "yes":
                    event.ignore()
                    self._minimize_to_tray()
                    return
                if dlg.choice == "no":
                    self._force_quit = True
                else:
                    event.ignore()
                    return

        if hasattr(self, "_clip_hover_popup"):
            self._clip_hover_popup.cancel_and_hide()
        if getattr(self, "_slacking_active", False):
            self._stop_slacking()
        if hasattr(self, "_cloud_bridge"):
            self._cloud_bridge.stop()
        if hasattr(self, "_clip_watcher"):
            self._clip_watcher.stop()
        if hasattr(self, "_active_lan_dlg") and self._active_lan_dlg is not None:
            try:
                self._active_lan_dlg.cleanup_tunnel()
                self._active_lan_dlg.close()
            except Exception:
                pass
        if hasattr(self, "_tunnel_mgr"):
            self._tunnel_mgr.stop_all()
        AlarmAudioPlayer.stop()
        for dlg in list(getattr(self, "_active_alarm_alerts", [])):
            try:
                dlg.close()
            except Exception:
                pass
        if getattr(self, "_active_alarm_editor_dlg", None) is not None:
            try:
                self._active_alarm_editor_dlg.close()
            except Exception:
                pass
        _cleanup_all_cloudflared_procs()
        LanTransferServer.cleanup_all_share_cache()
        if hasattr(self, "_lan_server"):
            self._lan_server.stop()
        if hasattr(self, "cloud_fetch_timer"):
            self.cloud_fetch_timer.stop()
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
        for w in self._holiday_workers:
            if w.isRunning():
                w.wait(1000)
        super().closeEvent(event)
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        is_light = self.config.theme_mode == "light"
        bg_color = QColor("#F5F6F8") if is_light else QColor("#121214")
        border_color = QColor("#DCDFE6") if is_light else QColor("#26262C")

        rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1.2))
        painter.drawRoundedRect(rect, 20.0, 20.0)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # 子窗口智能侧边定位（多屏工作区感知、左右避障、顶部对齐防底溢出）
    # ------------------------------------------------------------------
    def _get_current_monitor_work_area(self) -> tuple[int, int, int, int]:
        """获取主窗口当前所在显示器的真实工作区边界 (mon_left, mon_top, mon_right, mon_bottom)。"""
        screen = self.screen() or QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()

        if sys.platform == "win32":
            try:
                class _RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", ctypes.c_long),
                        ("top", ctypes.c_long),
                        ("right", ctypes.c_long),
                        ("bottom", ctypes.c_long),
                    ]

                class _MONITORINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", ctypes.c_ulong),
                        ("rcMonitor", _RECT),
                        ("rcWork", _RECT),
                        ("dwFlags", ctypes.c_ulong),
                    ]

                user32 = ctypes.windll.user32
                user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                user32.MonitorFromWindow.restype = ctypes.c_void_p
                user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MONITORINFO)]
                user32.GetMonitorInfoW.restype = ctypes.c_int

                MONITOR_DEFAULTTONEAREST = 2
                hmon = user32.MonitorFromWindow(int(self.winId()), MONITOR_DEFAULTTONEAREST)
                if hmon:
                    mi = _MONITORINFO()
                    mi.cbSize = ctypes.sizeof(_MONITORINFO)
                    if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                        rc_m = mi.rcMonitor
                        rc_w = mi.rcWork
                        if screen is not None:
                            sg = screen.geometry()
                            dpr = max(1.0, float(screen.devicePixelRatio()))
                            mon_left = sg.x() + int(round((rc_w.left - rc_m.left) / dpr))
                            mon_top = sg.y() + int(round((rc_w.top - rc_m.top) / dpr))
                            mon_right = sg.x() + int(round((rc_w.right - rc_m.left) / dpr))
                            mon_bottom = sg.y() + int(round((rc_w.bottom - rc_m.top) / dpr))
                            if mon_right > mon_left and mon_bottom > mon_top:
                                return mon_left, mon_top, mon_right, mon_bottom
                        else:
                            dpr = max(1.0, float(self.devicePixelRatioF()))
                            mon_left = int(round(rc_w.left / dpr))
                            mon_top = int(round(rc_w.top / dpr))
                            mon_right = int(round(rc_w.right / dpr))
                            mon_bottom = int(round(rc_w.bottom / dpr))
                            if mon_right > mon_left and mon_bottom > mon_top:
                                return mon_left, mon_top, mon_right, mon_bottom
            except Exception:
                pass

        if screen is not None:
            avail = screen.availableGeometry()
            return avail.x(), avail.y(), avail.x() + avail.width(), avail.y() + avail.height()
        return 0, 0, 1920, 1080

    def _collect_occupied_window_rects(self, exclude_win: QWidget | None = None) -> list[tuple[int, int, int, int]]:
        """收集主窗口及所有当前已打开可见的功能子窗口屏幕坐标矩形 (x1, y1, x2, y2)，排除 Tooltip/Toast 等临时浮层。"""
        rects: list[tuple[int, int, int, int]] = []
        main_geo = self.frameGeometry()
        rects.append((main_geo.x(), main_geo.y(), main_geo.x() + max(1, main_geo.width()), main_geo.y() + max(1, main_geo.height())))

        skip_types = (ToastPopup, _ClipHoverPreviewPopup, VersionMenuPopup, ScreenCaptureOverlay)
        for w in QApplication.topLevelWidgets():
            if w is None or w is self or w is exclude_win:
                continue
            try:
                if not w.isVisible():
                    continue
                if isinstance(w, skip_types):
                    continue
                wtype = w.windowFlags() & Qt.WindowType.WindowType_Mask
                if wtype in (Qt.WindowType.ToolTip, Qt.WindowType.Popup):
                    continue
                if w.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents):
                    continue
                fg = w.frameGeometry()
                if fg.width() <= 1 or fg.height() <= 1:
                    continue
                rects.append((fg.x(), fg.y(), fg.x() + fg.width(), fg.y() + fg.height()))
            except RuntimeError:
                continue
        return rects

    @staticmethod
    def _rect_overlap_area(r1: tuple[int, int, int, int], r2: tuple[int, int, int, int]) -> int:
        dx = max(0, min(r1[2], r2[2]) - max(r1[0], r2[0]))
        dy = max(0, min(r1[3], r2[3]) - max(r1[1], r2[1]))
        return dx * dy

    def position_beside_main(
        self,
        win: QWidget,
        win_w: int | None = None,
        win_h: int | None = None,
        gap: int = 10,
    ) -> tuple[int, int]:
        """全局多窗口智能避障定位：不遮挡主窗口，也不遮挡任何已打开的功能子窗口，并严格限定在当前显示器工作区内。"""
        QApplication.processEvents()
        main_geo = self.frameGeometry()
        main_x = main_geo.x()
        main_y = main_geo.y()
        main_w = max(1, main_geo.width())
        main_h = max(1, main_geo.height())

        if win_w is None or win_w <= 0 or win_h is None or win_h <= 0:
            win.adjustSize()
            hint = win.sizeHint()
            if win_w is None or win_w <= 0:
                win_w = win.width() if win.width() > 0 else max(1, hint.width())
            if win_h is None or win_h <= 0:
                win_h = win.height() if win.height() > 0 else max(1, hint.height())
        win_w = int(win_w)
        win_h = int(win_h)

        mon_left, mon_top, mon_right, mon_bottom = self._get_current_monitor_work_area()
        occupied_rects = self._collect_occupied_window_rects(exclude_win=win)
        main_rect = occupied_rects[0]
        sub_rects = occupied_rects[1:]

        # 统计主窗口右侧 / 左侧已开子窗口的最底边界
        main_mid_x = main_x + main_w / 2.0
        right_bottoms = [r[3] for r in sub_rects if r[0] >= main_x + main_w - 4 or ((r[0] + r[2]) / 2.0) > main_mid_x]
        left_bottoms = [r[3] for r in sub_rects if r[2] <= main_x + 4 or ((r[0] + r[2]) / 2.0) <= main_mid_x]

        raw_candidates: list[tuple[int, int]] = []
        # 候选 1：主窗口右侧，顶部对齐
        raw_candidates.append((main_x + main_w + gap, main_y))
        # 候选 2：主窗口右侧，已占右侧最底部子窗口的下方
        if right_bottoms:
            raw_candidates.append((main_x + main_w + gap, max(right_bottoms) + gap))
        # 候选 3：主窗口左侧，顶部对齐
        raw_candidates.append((main_x - win_w - gap, main_y))
        # 候选 4：主窗口左侧，已占左侧最底部子窗口的下方
        if left_bottoms:
            raw_candidates.append((main_x - win_w - gap, max(left_bottoms) + gap))
        # 候选 5：主窗口正下方 / 正上方
        raw_candidates.append((main_x, main_y + main_h + gap))
        raw_candidates.append((main_x, main_y - win_h - gap))
        # 候选 6：每个已打开子窗口的右侧、左侧、下方、上方邻接点
        for ox1, oy1, ox2, oy2 in sub_rects:
            raw_candidates.append((ox2 + gap, oy1))
            raw_candidates.append((ox1 - win_w - gap, oy1))
            raw_candidates.append((ox1, oy2 + gap))
            raw_candidates.append((ox1, oy1 - win_h - gap))

        # 展开候选列表（若原始 y 略超底部工作区，补充一个底部贴齐微调候选）
        candidates: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for cx, cy in raw_candidates:
            pt = (int(cx), int(cy))
            if pt not in seen:
                seen.add(pt)
                candidates.append(pt)
            if cy + win_h > mon_bottom or cy < mon_top:
                adj_y = max(mon_top, min(int(cy), mon_bottom - win_h))
                pt2 = (int(cx), adj_y)
                if pt2 not in seen:
                    seen.add(pt2)
                    candidates.append(pt2)

        def _in_work_area(cx: int, cy: int) -> bool:
            return (
                cx >= mon_left
                and cy >= mon_top
                and cx + win_w <= mon_right
                and cy + win_h <= mon_bottom
            )

        # 第一优先：寻找完全位于工作区内且与所有已占窗口零重叠的首个候选点
        chosen: tuple[int, int] | None = None
        for cx, cy in candidates:
            if not _in_work_area(cx, cy):
                continue
            cand_rect = (cx, cy, cx + win_w, cy + win_h)
            if all(self._rect_overlap_area(cand_rect, occ) == 0 for occ in occupied_rects):
                chosen = (cx, cy)
                break

        # 极端兜底：屏幕极小无法完全零重叠时，钳制至工作区内并选取重叠面积最小的候选点
        if chosen is None:
            max_x = max(mon_left, mon_right - win_w)
            max_y = max(mon_top, mon_bottom - win_h)
            best_score: tuple[int, int, int] | None = None
            for idx, (cx, cy) in enumerate(candidates):
                clx = max(mon_left, min(int(cx), max_x))
                cly = max(mon_top, min(int(cy), max_y))
                cand_rect = (clx, cly, clx + win_w, cly + win_h)
                total_ov = sum(self._rect_overlap_area(cand_rect, occ) for occ in occupied_rects)
                main_ov = self._rect_overlap_area(cand_rect, main_rect)
                score = (total_ov, main_ov, idx)
                if best_score is None or score < best_score:
                    best_score = score
                    chosen = (clx, cly)

        final_x, final_y = chosen if chosen is not None else (mon_left, mon_top)
        win.resize(win_w, win_h)
        win.move(int(final_x), int(final_y))
        return int(final_x), int(final_y)


    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        central = QWidget(self)
        central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 15, 18, 16)
        root_layout.setSpacing(10)
        self._root_layout = root_layout

        self.top_bar_widget = self._build_top_bar()
        root_layout.addWidget(self.top_bar_widget)

        self.mini_bar_widget = self._build_mini_bar()
        self.mini_bar_widget.setVisible(False)
        root_layout.addWidget(self.mini_bar_widget)

        self.stack = QStackedWidget(self)
        self.dashboard_page = self._build_dashboard_page()
        self.settings_page = self._build_settings_page()
        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.settings_page)

        root_layout.addWidget(self.stack, 1)

    def _build_mini_bar(self) -> QWidget:
        bar = QWidget(self)
        bar.setFixedHeight(36)
        ml = QHBoxLayout(bar)
        ml.setContentsMargins(2, 0, 2, 0)
        ml.setSpacing(8)

        self.lbl_mini_icon = QLabel(bar)
        self.lbl_mini_icon.setFixedSize(18, 18)
        self.lbl_mini_icon.setPixmap(_build_app_qpixmap(self.config.accent_color, size=18, hidpi=True))

        self.lbl_mini_time = QLabel("10:26", bar)
        self.lbl_mini_time.setFont(get_source_han_font(12, QFont.Weight.Bold))

        mid_col = QVBoxLayout()
        mid_col.setContentsMargins(0, 2, 0, 2)
        mid_col.setSpacing(3)
        self.lbl_mini_metric = QLabel("下班 --:--", bar)
        self.lbl_mini_metric.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.mini_progress_bar = SmoothProgressBar(bar, self.config.accent_color)
        self.mini_progress_bar.setFixedHeight(4)
        mid_col.addWidget(self.lbl_mini_metric)
        mid_col.addWidget(self.mini_progress_bar)

        self.btn_mini_restore = VectorIconButton("restore", bar, self.config.accent_color)
        self.btn_mini_restore.setFixedSize(24, 24)
        self.btn_mini_restore.setToolTip("还原完整窗口")
        self.btn_mini_restore.clicked.connect(self._toggle_mini_mode)

        ml.addWidget(self.lbl_mini_icon)
        ml.addWidget(self.lbl_mini_time)
        ml.addLayout(mid_col, 1)
        ml.addWidget(self.btn_mini_restore)
        return bar

    def _build_top_bar(self) -> QWidget:
        bar = QWidget(self)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 2, 0)
        layout.setSpacing(6)

        self.lbl_app_icon = QLabel(bar)
        self.lbl_app_icon.setFixedSize(20, 20)
        self.lbl_app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_app_icon.setToolTip(APP_BRAND_NAME)
        self.lbl_app_icon.setPixmap(_build_app_qpixmap(self.config.accent_color, size=20, hidpi=True))

        # 左上角：仅保留应用图标，并将【摸鱼 / 工作】模式切换开关紧贴放置在应用图标右侧
        self.mode_capsule = QFrame(bar)
        self.mode_capsule.setFixedHeight(22)
        cap_layout = QHBoxLayout(self.mode_capsule)
        cap_layout.setContentsMargins(2, 2, 2, 2)
        cap_layout.setSpacing(2)

        self.btn_app_fish = QPushButton("", self.mode_capsule)
        self.btn_app_fish.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_app_fish.setFixedSize(26, 18)
        self.btn_app_fish.setIconSize(QSize(14, 14))
        self.btn_app_fish.clicked.connect(lambda: self._switch_app_mode("fish"))

        self.btn_app_work = QPushButton("", self.mode_capsule)
        self.btn_app_work.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_app_work.setFixedSize(26, 18)
        self.btn_app_work.setIconSize(QSize(14, 14))
        self.btn_app_work.clicked.connect(lambda: self._switch_app_mode("work"))

        cap_layout.addWidget(self.btn_app_fish)
        cap_layout.addWidget(self.btn_app_work)

        layout.addWidget(self.lbl_app_icon)
        layout.addWidget(self.mode_capsule)
        layout.addStretch(1)

        self.btn_pin = VectorIconButton("pin", bar, self.config.accent_color)
        self.btn_pin.setToolTip("窗口置顶 (Pin)")
        self.btn_pin.set_active(self.config.always_on_top)
        self.btn_pin.clicked.connect(self._toggle_always_on_top)

        self.btn_gear = VectorIconButton("gear", bar, self.config.accent_color)
        self.btn_gear.setToolTip("偏好设置")
        self.btn_gear.clicked.connect(self._toggle_settings_page)

        self.btn_mini = VectorIconButton("mini", bar, self.config.accent_color)
        self.btn_mini.setToolTip("迷你悬浮窗")
        self.btn_mini.clicked.connect(self._toggle_mini_mode)

        self.btn_min = VectorIconButton("min", bar, self.config.accent_color)
        self.btn_min.setToolTip("最小化窗口")
        self.btn_min.clicked.connect(self._on_minimize_main_window)

        self.btn_close = VectorIconButton("close", bar, self.config.accent_color)
        self.btn_close.setToolTip("关闭窗口")
        self.btn_close.clicked.connect(self.close)

        layout.addWidget(self.btn_pin)
        layout.addWidget(self.btn_gear)
        layout.addWidget(self.btn_mini)
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_close)
        return bar

    def _build_dashboard_page(self) -> QWidget:
        outer = QWidget(self)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.mode_stack = QStackedWidget(outer)
        outer_layout.addWidget(self.mode_stack)

        page = QWidget(self.mode_stack)
        self.fish_dashboard_widget = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(8)

        # 2. 主视觉时钟区（大号时间 + 正下方居中当前日期）
        self.clock_card = CardFrame(page, radius=16)
        clock_layout = QVBoxLayout(self.clock_card)
        clock_layout.setContentsMargins(16, 10, 16, 10)
        clock_layout.setSpacing(4)

        time_row = QHBoxLayout()
        time_row.setSpacing(0)
        time_row.addStretch(1)

        clock_font = get_source_han_font(36, QFont.Weight.Bold)
        self.lbl_time_hm = QLabel("11:28", self.clock_card)
        self.lbl_time_hm.setFont(clock_font)
        self.lbl_time_hm.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        self.lbl_time_s = QLabel(":33", self.clock_card)
        self.lbl_time_s.setFont(clock_font)
        self.lbl_time_s.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        time_row.addWidget(self.lbl_time_hm)
        time_row.addWidget(self.lbl_time_s)
        time_row.addStretch(1)
        clock_layout.addLayout(time_row)

        self.date_label = QLabel("2026年11月21日 星期六", self.clock_card)
        self.date_label.setFont(get_source_han_font(10, QFont.Weight.Bold))
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clock_layout.addWidget(self.date_label)

        layout.addWidget(self.clock_card)

        # 3. 目标倒计时板块（左上角标题 + 右上角设置图标，三槽位支持独立自定义）
        self.progress_card = CardFrame(page, radius=14)
        prog_layout = QVBoxLayout(self.progress_card)
        prog_layout.setContentsMargins(15, 8, 12, 10)
        prog_layout.setSpacing(5)

        prog_top = QHBoxLayout()
        prog_top.setContentsMargins(0, 0, 0, 0)
        self.lbl_progress_title = QLabel("目标倒计时", self.progress_card)
        self.lbl_progress_title.setFont(get_source_han_font(9, QFont.Weight.Bold))
        prog_top.addWidget(self.lbl_progress_title)
        prog_top.addStretch(1)
        self.btn_progress_cfg = VectorIconButton("gear", self.progress_card, self.config.accent_color)
        self.btn_progress_cfg.setFixedSize(20, 20)
        self.btn_progress_cfg.setToolTip("目标倒计时设置")
        self.btn_progress_cfg.clicked.connect(self._open_progress_target_dialog)
        prog_top.addWidget(self.btn_progress_cfg)
        prog_layout.addLayout(prog_top)

        prog_grid = QGridLayout()
        prog_grid.setContentsMargins(0, 0, 0, 0)
        prog_grid.setHorizontalSpacing(6)
        prog_grid.setVerticalSpacing(7)
        prog_grid.setColumnStretch(1, 1)

        # 行 0：下班倒计时
        work_tag_box = QWidget(self.progress_card)
        wt_l = QHBoxLayout(work_tag_box)
        wt_l.setContentsMargins(0, 0, 0, 0)
        wt_l.setSpacing(4)
        self.lbl_icon_work = QLabel(work_tag_box)
        self.lbl_icon_work.setFixedSize(13, 13)
        self.lbl_tag_work = QLabel("下班", work_tag_box)
        self.lbl_tag_work.setFont(get_source_han_font(9, QFont.Weight.Bold))
        wt_l.addWidget(self.lbl_icon_work)
        wt_l.addWidget(self.lbl_tag_work)
        work_tag_box.setFixedWidth(48)

        self.progress_bar = SmoothProgressBar(self.progress_card, self.config.accent_color)
        self.progress_bar.setFixedHeight(7)

        self.lbl_countdown = QLabel("03:42:18", self.progress_card)
        self.lbl_countdown.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.lbl_countdown.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_countdown.setFixedWidth(74)

        self.lbl_progress_pct = QLabel("68.4%", self.progress_card)
        self.lbl_progress_pct.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.lbl_progress_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_progress_pct.setFixedWidth(42)

        prog_grid.addWidget(work_tag_box, 0, 0)
        prog_grid.addWidget(self.progress_bar, 0, 1)
        prog_grid.addWidget(self.lbl_countdown, 0, 2)
        prog_grid.addWidget(self.lbl_progress_pct, 0, 3)

        # 行 1：周末 / 休假倒计时
        wk_tag_box = QWidget(self.progress_card)
        wkt_l = QHBoxLayout(wk_tag_box)
        wkt_l.setContentsMargins(0, 0, 0, 0)
        wkt_l.setSpacing(4)
        self.lbl_icon_weekend = QLabel(wk_tag_box)
        self.lbl_icon_weekend.setFixedSize(13, 13)
        self.lbl_tag_weekend = QLabel("周末", wk_tag_box)
        self.lbl_tag_weekend.setFont(get_source_han_font(9, QFont.Weight.Bold))
        wkt_l.addWidget(self.lbl_icon_weekend)
        wkt_l.addWidget(self.lbl_tag_weekend)
        wk_tag_box.setFixedWidth(48)

        self.weekend_bar = SmoothProgressBar(self.progress_card, self.config.accent_color)
        self.weekend_bar.setFixedHeight(7)

        self.lbl_weekend_countdown = QLabel("1天06:08", self.progress_card)
        self.lbl_weekend_countdown.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.lbl_weekend_countdown.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_weekend_countdown.setFixedWidth(74)

        self.lbl_weekend_pct = QLabel("72.5%", self.progress_card)
        self.lbl_weekend_pct.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.lbl_weekend_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_weekend_pct.setFixedWidth(42)

        prog_grid.addWidget(wk_tag_box, 1, 0)
        prog_grid.addWidget(self.weekend_bar, 1, 1)
        prog_grid.addWidget(self.lbl_weekend_countdown, 1, 2)
        prog_grid.addWidget(self.lbl_weekend_pct, 1, 3)

        # 行 2：发薪日倒计时
        pd_tag_box = QWidget(self.progress_card)
        pdt_l = QHBoxLayout(pd_tag_box)
        pdt_l.setContentsMargins(0, 0, 0, 0)
        pdt_l.setSpacing(4)
        self.lbl_icon_payday = QLabel(pd_tag_box)
        self.lbl_icon_payday.setFixedSize(13, 13)
        self.lbl_tag_payday = QLabel("发薪", pd_tag_box)
        self.lbl_tag_payday.setFont(get_source_han_font(9, QFont.Weight.Bold))
        pdt_l.addWidget(self.lbl_icon_payday)
        pdt_l.addWidget(self.lbl_tag_payday)
        pd_tag_box.setFixedWidth(48)

        self.payday_bar = SmoothProgressBar(self.progress_card, self.config.accent_color)
        self.payday_bar.setFixedHeight(7)

        self.lbl_payday_countdown = QLabel("26天", self.progress_card)
        self.lbl_payday_countdown.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.lbl_payday_countdown.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_payday_countdown.setFixedWidth(74)

        self.lbl_payday_pct = QLabel("15.0%", self.progress_card)
        self.lbl_payday_pct.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.lbl_payday_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_payday_pct.setFixedWidth(42)

        prog_grid.addWidget(pd_tag_box, 2, 0)
        prog_grid.addWidget(self.payday_bar, 2, 1)
        prog_grid.addWidget(self.lbl_payday_countdown, 2, 2)
        prog_grid.addWidget(self.lbl_payday_pct, 2, 3)

        prog_layout.addLayout(prog_grid)
        layout.addWidget(self.progress_card)

        # 3.5 带薪摸鱼模块（精准控制高度并保留清晰间距）
        self.slacking_card = CardFrame(page, radius=14)
        self.slacking_card.setFixedHeight(128)
        sl_layout = QVBoxLayout(self.slacking_card)
        sl_layout.setContentsMargins(15, 8, 12, 7)
        sl_layout.setSpacing(3)

        sl_top = QHBoxLayout()
        sl_top.setSpacing(6)
        self.lbl_slacking_title = QLabel("带薪摸鱼", self.slacking_card)
        self.lbl_slacking_title.setFont(get_source_han_font(9, QFont.Weight.Bold))
        self.btn_slacking_cfg = VectorIconButton("gear", self.slacking_card, self.config.accent_color)
        self.btn_slacking_cfg.setFixedSize(20, 20)
        self.btn_slacking_cfg.setToolTip("摸鱼设置")
        self.btn_slacking_cfg.clicked.connect(self._open_slacking_settings_dialog)
        self.btn_slacking_toggle = QPushButton("开始摸鱼", self.slacking_card)
        self.btn_slacking_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_slacking_toggle.setFixedSize(70, 22)
        self.btn_slacking_toggle.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.btn_slacking_toggle.clicked.connect(self._on_slacking_toggle_clicked)
        sl_top.addWidget(self.lbl_slacking_title)
        sl_top.addStretch(1)
        sl_top.addWidget(self.btn_slacking_cfg)
        sl_top.addWidget(self.btn_slacking_toggle)
        sl_layout.addLayout(sl_top)

        sl_mid = QHBoxLayout()
        sl_mid.setSpacing(6)
        self.lbl_slacking_stats = QLabel("今日 00:00  ·  所得 --", self.slacking_card)
        self.lbl_slacking_stats.setFont(get_source_han_font(9, QFont.Weight.Bold))
        self.btn_slacking_dash = QPushButton("数据看板 >", self.slacking_card)
        self.btn_slacking_dash.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_slacking_dash.setFixedHeight(18)
        self.btn_slacking_dash.setFont(get_source_han_font(8))
        self.btn_slacking_dash.clicked.connect(self._open_slacking_dashboard)
        sl_mid.addWidget(self.lbl_slacking_stats, 1)
        sl_mid.addWidget(self.btn_slacking_dash)
        sl_layout.addLayout(sl_mid)

        self.slacking_mini_canvas = SlackingCurveCanvas(self.slacking_card, embedded=True)
        self.slacking_mini_canvas.setFixedHeight(44)
        self.slacking_mini_canvas.clicked.connect(self._open_slacking_dashboard)
        sl_layout.addWidget(self.slacking_mini_canvas)

        layout.addWidget(self.slacking_card)

        # 4. 法定节假日与补班查询框（今年 / 下一年，4列严格对齐）
        self.holiday_card = CardFrame(page, radius=14)
        hol_layout = QVBoxLayout(self.holiday_card)
        hol_layout.setContentsMargins(14, 9, 12, 9)
        hol_layout.setSpacing(5)

        hol_header = QHBoxLayout()
        hol_header.setContentsMargins(0, 0, 2, 0)
        hol_header.setSpacing(6)

        self.lbl_holiday_title = QLabel("法定节假日", self.holiday_card)
        self.lbl_holiday_title.setFont(get_source_han_font(9, QFont.Weight.Bold))

        self.btn_holiday_calendar = QPushButton("日历", self.holiday_card)
        self.btn_holiday_calendar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_holiday_calendar.setFixedSize(40, 20)
        self.btn_holiday_calendar.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.btn_holiday_calendar.setToolTip("打开独立日历窗口")
        self.btn_holiday_calendar.clicked.connect(self._open_holiday_popout_window)

        self.btn_year_cur = QPushButton("今年", self.holiday_card)
        self.btn_year_cur.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_year_cur.setFixedSize(40, 20)
        self.btn_year_cur.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.btn_year_cur.clicked.connect(lambda: self._switch_holiday_year(self.base_year))

        self.btn_year_next = QPushButton("明年", self.holiday_card)
        self.btn_year_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_year_next.setFixedSize(40, 20)
        self.btn_year_next.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.btn_year_next.clicked.connect(lambda: self._switch_holiday_year(self.base_year + 1))

        hol_header.addWidget(self.lbl_holiday_title)
        hol_header.addStretch(1)
        hol_header.addWidget(self.btn_holiday_calendar)
        hol_header.addWidget(self.btn_year_cur)
        hol_header.addWidget(self.btn_year_next)
        hol_layout.addLayout(hol_header)

        self.holiday_scroll = QScrollArea(self.holiday_card)
        self.holiday_scroll.setWidgetResizable(True)
        self.holiday_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.holiday_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.holiday_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.holiday_scroll.setFixedHeight(72)

        self.holiday_list_container = QWidget()
        self.holiday_list_layout = QVBoxLayout(self.holiday_list_container)
        self.holiday_list_layout.setContentsMargins(0, 2, 4, 2)
        self.holiday_list_layout.setSpacing(6)
        self.holiday_scroll.setWidget(self.holiday_list_container)

        hol_layout.addWidget(self.holiday_scroll)
        layout.addWidget(self.holiday_card)

        # 5. 调休余额板块
        self.comp_card = CardFrame(page, radius=14)
        comp_layout = QVBoxLayout(self.comp_card)
        comp_layout.setContentsMargins(15, 9, 15, 10)
        comp_layout.setSpacing(6)

        comp_top = QHBoxLayout()
        self.lbl_comp_title = QLabel("调休余额", self.comp_card)
        self.lbl_comp_title.setFont(get_source_han_font(9, QFont.Weight.Bold))
        comp_top.addWidget(self.lbl_comp_title)
        comp_top.addStretch(1)

        comp_stats_row = QHBoxLayout()
        comp_stats_row.setSpacing(12)

        bal_col = QVBoxLayout()
        bal_col.setSpacing(2)
        self.lbl_comp_bal_cap = QLabel("剩余调休余额", self.comp_card)
        self.lbl_comp_bal_cap.setFont(get_source_han_font(9))
        self.lbl_comp_bal_val = QLabel("0.0 小时", self.comp_card)
        self.lbl_comp_bal_val.setFont(get_source_han_font(15, QFont.Weight.Bold))
        bal_col.addWidget(self.lbl_comp_bal_cap)
        bal_col.addWidget(self.lbl_comp_bal_val)

        ot_col = QVBoxLayout()
        ot_col.setSpacing(2)
        self.lbl_comp_ot_cap = QLabel("上次加班时长", self.comp_card)
        self.lbl_comp_ot_cap.setFont(get_source_han_font(9))
        self.lbl_comp_ot_cap.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_comp_ot_val = QLabel("0.0 小时", self.comp_card)
        self.lbl_comp_ot_val.setFont(get_source_han_font(15, QFont.Weight.Bold))
        self.lbl_comp_ot_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ot_col.addWidget(self.lbl_comp_ot_cap)
        ot_col.addWidget(self.lbl_comp_ot_val)

        comp_stats_row.addLayout(bal_col, 1)
        comp_stats_row.addLayout(ot_col, 1)

        self.btn_manage_comp = QPushButton("管理我的调休", self.comp_card)
        self.btn_manage_comp.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_manage_comp.setFixedHeight(32)
        self.btn_manage_comp.setFont(get_source_han_font(10, QFont.Weight.Bold))
        self.btn_manage_comp.clicked.connect(self._open_comp_time_dialog)

        comp_layout.addLayout(comp_top)
        comp_layout.addLayout(comp_stats_row)
        comp_layout.addWidget(self.btn_manage_comp)

        layout.addWidget(self.comp_card)
        layout.addStretch(1)

        # 6. 主页面最底部固定展示：工作/休息滚动状态提示栏（移除薪资挂钩状态栏）
        self.status_ticker = RollingStatusTicker(page)
        self.status_ticker.setToolTip("每 5 秒自动切换，点击可立即切换")
        self.status_ticker.clicked.connect(self._on_quote_clicked)
        layout.addWidget(self.status_ticker)

        self.work_dashboard_widget = self._build_work_dashboard_widget()
        self.mode_stack.addWidget(self.fish_dashboard_widget)
        self.mode_stack.addWidget(self.work_dashboard_widget)
        return outer

    def _build_work_dashboard_widget(self) -> QWidget:
        page = QWidget(self.mode_stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(7)

        self.work_card = CardFrame(page, radius=16)
        self.work_card.setFixedHeight(142)
        w_layout = QVBoxLayout(self.work_card)
        w_layout.setContentsMargins(16, 12, 16, 12)
        w_layout.setSpacing(7)

        self.lbl_work_title = QLabel("多线程下载器", self.work_card)
        self.lbl_work_title.setFont(get_source_han_font(9, QFont.Weight.Bold))
        w_layout.addWidget(self.lbl_work_title)

        self.lbl_work_sub = QLabel("支持 6 线程 16MB 分片加速，自动断点续传", self.work_card)
        self.lbl_work_sub.setFont(get_source_han_font(8))
        w_layout.addWidget(self.lbl_work_sub)

        # 链接输入框 + 主操作按钮（下载 ↔ 取消 动态联动）
        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        self.edit_dl_url = QLineEdit(self.work_card)
        self.edit_dl_url.setFixedHeight(34)
        self.edit_dl_url.setFont(get_source_han_font(9))
        self.edit_dl_url.setPlaceholderText("请粘贴 HTTP/HTTPS 下载链接...")

        self.btn_dl_start = QPushButton("下载", self.work_card)
        self.btn_dl_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dl_start.setFixedSize(72, 34)
        self.btn_dl_start.setFont(get_source_han_font(9, QFont.Weight.Bold))
        self.btn_dl_start.clicked.connect(self._on_dl_start_clicked)

        url_row.addWidget(self.edit_dl_url, 1)
        url_row.addWidget(self.btn_dl_start)
        w_layout.addLayout(url_row)

        # 进度与单行状态展示区（右侧精巧暂停/继续按钮，无多余底部留白）
        prog_header = QHBoxLayout()
        prog_header.setSpacing(6)
        self.lbl_dl_status = QLabel("准备就绪", self.work_card)
        self.lbl_dl_status.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.lbl_dl_status.setWordWrap(False)
        self.lbl_dl_status.setFixedHeight(20)

        self.lbl_dl_pct = QLabel("0%", self.work_card)
        self.lbl_dl_pct.setFont(get_source_han_font(9, QFont.Weight.Bold))
        self.lbl_dl_pct.setFixedHeight(20)
        self.lbl_dl_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.btn_dl_pause = QPushButton("⏸", self.work_card)
        self.btn_dl_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dl_pause.setFixedSize(22, 20)
        self.btn_dl_pause.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.btn_dl_pause.setToolTip("暂停下载")
        self.btn_dl_pause.clicked.connect(self._on_dl_pause_clicked)
        self.btn_dl_pause.setVisible(False)

        self.btn_dl_open_dir = QPushButton("打开", self.work_card)
        self.btn_dl_open_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dl_open_dir.setFixedHeight(20)
        self.btn_dl_open_dir.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.btn_dl_open_dir.setToolTip("打开文件所在文件夹")
        self.btn_dl_open_dir.clicked.connect(self._on_dl_open_dir_clicked)
        self.btn_dl_open_dir.setVisible(False)

        prog_header.addWidget(self.lbl_dl_status, 1)
        prog_header.addWidget(self.lbl_dl_pct)
        prog_header.addWidget(self.btn_dl_pause)
        prog_header.addWidget(self.btn_dl_open_dir)
        w_layout.addLayout(prog_header)

        self.work_progress_bar = SmoothProgressBar(self.work_card, self.config.accent_color)
        self.work_progress_bar.set_value(0.0)
        w_layout.addWidget(self.work_progress_bar)

        # 文件分享链接 · 拖入生成直链（严格单次领取即销毁 + 15 分钟自动过期）
        self.share_card = CardFrame(page, radius=16)
        s_layout = QVBoxLayout(self.share_card)
        s_layout.setContentsMargins(12, 8, 12, 7)
        s_layout.setSpacing(5)

        self.lbl_share_title = QLabel("文件分享链接", self.share_card)
        self.lbl_share_title.setFont(get_source_han_font(9, QFont.Weight.Bold))
        s_layout.addWidget(self.lbl_share_title)

        # 默认紧凑拖放区 + 底部淡色合规说明
        self.share_idle_box = QWidget(self.share_card)
        si_l = QVBoxLayout(self.share_idle_box)
        si_l.setContentsMargins(0, 0, 0, 0)
        si_l.setSpacing(4)

        self.share_drop_zone = _QuickShareDropZone(self.share_idle_box)
        self.share_drop_zone.setFixedHeight(46)
        self.share_drop_zone.paths_dropped.connect(self._on_share_paths_selected)
        dz_l = QHBoxLayout(self.share_drop_zone)
        dz_l.setContentsMargins(10, 4, 8, 4)
        dz_l.setSpacing(6)

        self.lbl_share_drop_hint = QLabel("将任意文件或文件夹拖入此处，生成高速下载直链", self.share_drop_zone)
        self.lbl_share_drop_hint.setFont(get_source_han_font(7))
        self.lbl_share_drop_hint.setWordWrap(True)

        self.btn_share_pick_file = QPushButton("选文件", self.share_drop_zone)
        self.btn_share_pick_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_share_pick_file.setFixedHeight(26)
        self.btn_share_pick_file.setFont(get_source_han_font(7, QFont.Weight.Bold))
        self.btn_share_pick_file.clicked.connect(self._on_share_pick_file_clicked)

        self.btn_share_pick_dir = QPushButton("选文件夹", self.share_drop_zone)
        self.btn_share_pick_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_share_pick_dir.setFixedHeight(26)
        self.btn_share_pick_dir.setFont(get_source_han_font(7, QFont.Weight.Bold))
        self.btn_share_pick_dir.clicked.connect(self._on_share_pick_dir_clicked)

        dz_l.addWidget(self.lbl_share_drop_hint, 1)
        dz_l.addWidget(self.btn_share_pick_file)
        dz_l.addWidget(self.btn_share_pick_dir)
        si_l.addWidget(self.share_drop_zone)
        s_layout.addWidget(self.share_idle_box)

        # 展开态分享信息与实时单次销毁状态区（默认隐藏）
        self.share_active_box = QWidget(self.share_card)
        self.share_active_box.setVisible(False)
        sa_l = QVBoxLayout(self.share_active_box)
        sa_l.setContentsMargins(2, 2, 2, 2)
        sa_l.setSpacing(6)

        sa_top = QHBoxLayout()
        sa_top.setSpacing(6)
        self.lbl_share_file_info = QLabel("正在快速打包...", self.share_active_box)
        self.lbl_share_file_info.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.lbl_share_tunnel_state = QLabel("连接中...", self.share_active_box)
        self.lbl_share_tunnel_state.setFont(get_source_han_font(7, QFont.Weight.Bold))
        sa_top.addWidget(self.lbl_share_file_info, 1)
        sa_top.addWidget(self.lbl_share_tunnel_state)
        sa_l.addLayout(sa_top)

        sa_link_row = QHBoxLayout()
        sa_link_row.setSpacing(6)
        self.lbl_share_link = QLabel("正在建立高速公网直链...", self.share_active_box)
        self.lbl_share_link.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.btn_share_copy = QPushButton("复制链接", self.share_active_box)
        self.btn_share_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_share_copy.setFixedHeight(24)
        self.btn_share_copy.setFont(get_source_han_font(7, QFont.Weight.Bold))
        self.btn_share_copy.setEnabled(False)
        self.btn_share_copy.clicked.connect(self._on_share_copy_clicked)
        sa_link_row.addWidget(self.lbl_share_link, 1)
        sa_link_row.addWidget(self.btn_share_copy)
        sa_l.addLayout(sa_link_row)

        # 一次性有效 / 接收中锁定 / 已销毁状态徽标 + 停止分享按钮
        sa_bot = QHBoxLayout()
        sa_bot.setSpacing(6)
        self.lbl_share_badge = QLabel("一次性有效 · 仅限首人下载（15分钟内有效）", self.share_active_box)
        self.lbl_share_badge.setFont(get_source_han_font(7, QFont.Weight.Bold))
        self.lbl_share_badge.setWordWrap(True)

        self.btn_share_stop = QPushButton("停止分享", self.share_active_box)
        self.btn_share_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_share_stop.setFixedHeight(22)
        self.btn_share_stop.setFont(get_source_han_font(7, QFont.Weight.Bold))
        self.btn_share_stop.clicked.connect(lambda: self._on_share_stop_clicked(silent=False))

        sa_bot.addWidget(self.lbl_share_badge, 1)
        sa_bot.addWidget(self.btn_share_stop)
        sa_l.addLayout(sa_bot)

        # 代理 / TUN 非阻塞温和风险提示条（未检测到时自动隐藏）
        self.lbl_share_proxy_warn = QLabel("", self.share_active_box)
        self.lbl_share_proxy_warn.setFont(get_source_han_font(7))
        self.lbl_share_proxy_warn.setWordWrap(True)
        self.lbl_share_proxy_warn.setVisible(False)
        sa_l.addWidget(self.lbl_share_proxy_warn)

        s_layout.addWidget(self.share_active_box)

        # 下方：粘贴板模块（固定紧凑高度可滚动列表，预留下方扩展空间）
        self.clip_card = CardFrame(page, radius=16)
        c_layout = QVBoxLayout(self.clip_card)
        c_layout.setContentsMargins(14, 10, 14, 10)
        c_layout.setSpacing(6)

        clip_header = QHBoxLayout()
        clip_header.setSpacing(4)
        self.lbl_clip_title = QLabel("粘贴板", self.clip_card)
        self.lbl_clip_title.setFont(get_source_han_font(9, QFont.Weight.Bold))
        clip_header.addWidget(self.lbl_clip_title)
        clip_header.addSpacing(4)

        self._clip_tab_btns: dict[str, QPushButton] = {}
        for tab_key, tab_label in (
            ("all", "全部"),
            ("text", "文本"),
            ("link", "链接"),
            ("file", "文件"),
        ):
            tb = QPushButton(tab_label, self.clip_card)
            tb.setCursor(Qt.CursorShape.PointingHandCursor)
            tb.setFixedHeight(20)
            tb.setFont(get_source_han_font(8))
            tb.clicked.connect(lambda checked=False, k=tab_key: self._set_clip_filter(k))
            self._clip_tab_btns[tab_key] = tb
            clip_header.addWidget(tb)

        clip_header.addStretch(1)
        self.btn_clip_clear = QPushButton("清空", self.clip_card)
        self.btn_clip_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clip_clear.setFixedHeight(20)
        self.btn_clip_clear.setFont(get_source_han_font(8))
        self.btn_clip_clear.clicked.connect(self._on_clip_clear_clicked)
        clip_header.addWidget(self.btn_clip_clear)
        c_layout.addLayout(clip_header)

        self.clip_scroll = QScrollArea(self.clip_card)
        self.clip_scroll.setWidgetResizable(True)
        self.clip_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.clip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.clip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.clip_scroll.setFixedHeight(76)

        self.clip_list_container = QWidget()
        self.clip_list_layout = QVBoxLayout(self.clip_list_container)
        self.clip_list_layout.setContentsMargins(0, 0, 2, 0)
        self.clip_list_layout.setSpacing(5)
        self.clip_list_layout.addStretch(1)
        self.clip_scroll.setWidget(self.clip_list_container)
        self.clip_scroll.verticalScrollBar().valueChanged.connect(
            lambda _v: self._clip_hover_popup.cancel_and_hide() if hasattr(self, "_clip_hover_popup") else None
        )
        c_layout.addWidget(self.clip_scroll)

        # 最下方：连接手机紧凑卡片（仅约 2 行高度）
        self.lan_card = CardFrame(page, radius=16)
        self.lan_card.setFixedHeight(58)
        l_layout = QHBoxLayout(self.lan_card)
        l_layout.setContentsMargins(14, 8, 14, 8)
        l_layout.setSpacing(8)

        lan_info_col = QVBoxLayout()
        lan_info_col.setSpacing(2)
        self.lbl_lan_title = QLabel("连接手机", self.lan_card)
        self.lbl_lan_title.setFont(get_source_han_font(9, QFont.Weight.Bold))
        self.lbl_lan_status = QLabel("苹果、安卓无需安装扫码直连", self.lan_card)
        self.lbl_lan_status.setFont(get_source_han_font(7))
        self.lbl_lan_status.setWordWrap(False)
        lan_info_col.addWidget(self.lbl_lan_title)
        lan_info_col.addWidget(self.lbl_lan_status)
        l_layout.addLayout(lan_info_col, 1)

        self.btn_lan_manage = QPushButton("管理", self.lan_card)
        self.btn_lan_manage.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lan_manage.setFixedSize(50, 28)
        self.btn_lan_manage.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.btn_lan_manage.clicked.connect(self._on_lan_manage_clicked)
        self.btn_lan_manage.setVisible(False)

        self.lan_toggle_switch = CapsuleToggleSwitch(
            self.lan_card,
            accent_color=self.config.accent_color,
            is_light=(self.config.theme_mode == "light"),
        )
        self.lan_toggle_switch.setToolTip("开启/关闭连接手机")
        self.lan_toggle_switch.toggled.connect(self._on_lan_toggled)

        l_layout.addWidget(self.btn_lan_manage)
        l_layout.addWidget(self.lan_toggle_switch)

        # 闹钟提醒卡片
        self.alarm_card = CardFrame(page, radius=16)
        self.alarm_card.setFixedHeight(84)
        al_layout = QVBoxLayout(self.alarm_card)
        al_layout.setContentsMargins(14, 10, 14, 10)
        al_layout.setSpacing(6)

        al_header = QHBoxLayout()
        al_header.setSpacing(6)
        self.lbl_alarm_title = QLabel("闹钟提醒", self.alarm_card)
        self.lbl_alarm_title.setFont(get_source_han_font(9, QFont.Weight.Bold))
        al_header.addWidget(self.lbl_alarm_title)
        al_header.addStretch(1)
        self.btn_alarm_edit = QPushButton("编辑闹钟", self.alarm_card)
        self.btn_alarm_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_alarm_edit.setFixedSize(96, 32)
        self.btn_alarm_edit.setFont(get_source_han_font(8, QFont.Weight.Bold))
        self.btn_alarm_edit.clicked.connect(self._open_alarm_editor_dialog)
        al_header.addWidget(self.btn_alarm_edit)
        al_layout.addLayout(al_header)

        self.alarm_empty_lbl = QLabel("暂无闹钟，点击右上角「编辑闹钟」添加", self.alarm_card)
        self.alarm_empty_lbl.setFont(get_source_han_font(8))
        al_layout.addWidget(self.alarm_empty_lbl)

        self.alarm_row_widget = QWidget(self.alarm_card)
        al_row = QHBoxLayout(self.alarm_row_widget)
        al_row.setContentsMargins(0, 0, 0, 0)
        al_row.setSpacing(8)

        self.lbl_alarm_time = QLabel("09:00", self.alarm_row_widget)
        self.lbl_alarm_time.setFont(get_source_han_font(15, QFont.Weight.Bold))
        al_row.addWidget(self.lbl_alarm_time)

        self.lbl_alarm_mode = QLabel("每日提醒", self.alarm_row_widget)
        self.lbl_alarm_mode.setFont(get_source_han_font(7, QFont.Weight.Bold))
        self.lbl_alarm_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        al_row.addWidget(self.lbl_alarm_mode)

        self.lbl_alarm_note = HoverNoteLabel(self.alarm_row_widget)
        self.lbl_alarm_note.setFont(get_source_han_font(8))
        self.lbl_alarm_note.setMinimumWidth(40)
        al_row.addWidget(self.lbl_alarm_note, 1)
        al_layout.addWidget(self.alarm_row_widget)

        # 最下方：截图识字 + 屏幕取色紧凑卡片（简约单色灰色矢量图标）
        self.tool_card = CardFrame(page, radius=16)
        self.tool_card.setFixedHeight(48)
        t_layout = QHBoxLayout(self.tool_card)
        t_layout.setContentsMargins(12, 8, 12, 8)
        t_layout.setSpacing(10)

        self.btn_tool_ocr = QPushButton(" 截图识字", self.tool_card)
        self.btn_tool_ocr.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tool_ocr.setFixedHeight(30)
        self.btn_tool_ocr.setIconSize(QSize(14, 14))
        self.btn_tool_ocr.setFont(get_source_han_font(9, QFont.Weight.Bold))
        self.btn_tool_ocr.clicked.connect(self._on_ocr_clicked)

        self.btn_tool_picker = QPushButton(" 屏幕取色", self.tool_card)
        self.btn_tool_picker.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tool_picker.setFixedHeight(30)
        self.btn_tool_picker.setIconSize(QSize(14, 14))
        self.btn_tool_picker.setFont(get_source_han_font(9, QFont.Weight.Bold))
        self.btn_tool_picker.clicked.connect(self._on_picker_clicked)

        t_layout.addWidget(self.btn_tool_ocr, 1)
        t_layout.addWidget(self.btn_tool_picker, 1)

        layout.addWidget(self.lan_card)
        layout.addWidget(self.work_card)
        layout.addWidget(self.share_card)
        layout.addWidget(self.clip_card)
        layout.addWidget(self.alarm_card)
        layout.addWidget(self.tool_card)
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------
    # 法定节假日年份切换、异步联网更新 & 4列严格对齐渲染
    # ------------------------------------------------------------------
    def _open_holiday_popout_window(self) -> None:
        if self._holiday_popout_dlg is not None and self._holiday_popout_dlg.isVisible():
            self._holiday_popout_dlg.raise_()
            self._holiday_popout_dlg.activateWindow()
            return
        dlg = HolidayCalendarDialog(
            theme_mode=self.config.theme_mode,
            accent_color=self.config.accent_color,
            raw_by_year=self.raw_holidays_by_year,
            parent=self,
        )
        dlg.setModal(False)
        dlg.month_changed.connect(self._on_holiday_calendar_month_changed)
        cal_year, _ = dlg.calendar.current_year_month()
        if cal_year not in self._synced_holiday_years:
            self._start_holiday_online_sync(cal_year)
        self._holiday_popout_dlg = dlg
        dlg.adjustSize()
        self.position_beside_main(dlg, dlg.width(), dlg.height(), gap=10)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_holiday_calendar_month_changed(self, year: int, month: int) -> None:
        if year not in self.raw_holidays_by_year:
            self.raw_holidays_by_year[year] = HolidayService.get_initial_raw_data(year)
        if self._holiday_popout_dlg is not None and self._holiday_popout_dlg.isVisible():
            self._holiday_popout_dlg.set_holiday_data(self.raw_holidays_by_year)
        if year not in self._synced_holiday_years:
            self._start_holiday_online_sync(year)

    def _switch_holiday_year(self, target_year: int) -> None:
        if self.selected_holiday_year == target_year:
            return
        self.selected_holiday_year = target_year
        self._update_year_toggle_styles()
        self._rebuild_holiday_rows()
        if not self.raw_holidays_by_year.get(target_year):
            self._start_holiday_online_sync(target_year)

    def _start_holiday_online_sync(self, year: int) -> None:
        self._synced_holiday_years.add(year)
        worker = HolidayFetchWorker(year, self)
        worker.finished_signal.connect(self._on_holiday_synced)
        self._holiday_workers.append(worker)
        worker.start()

    def _on_holiday_synced(self, year: int, raw_data: dict, is_online: bool) -> None:
        if raw_data:
            self.raw_holidays_by_year[year] = raw_data
        if year == self.selected_holiday_year:
            self._rebuild_holiday_rows()
        if self._holiday_popout_dlg is not None and self._holiday_popout_dlg.isVisible():
            self._holiday_popout_dlg.set_holiday_data(self.raw_holidays_by_year)

    def _update_year_toggle_styles(self) -> None:
        acc = self.config.accent_color
        is_light = self.config.theme_mode == "light"
        idle_bg = "#F0F1F5" if is_light else "#22222A"
        idle_fg = "#686874" if is_light else "#92929E"

        self.btn_holiday_calendar.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {idle_bg};
                color: {idle_fg};
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                color: {acc};
            }}
            """
        )
        if self._holiday_popout_dlg is not None and self._holiday_popout_dlg.isVisible():
            self._holiday_popout_dlg.apply_theme(is_light, acc)

        for btn, yr in ((self.btn_year_cur, self.base_year), (self.btn_year_next, self.base_year + 1)):
            is_selected = self.selected_holiday_year == yr
            if is_selected:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {acc};
                        color: #FFFFFF;
                        border: none;
                        border-radius: 6px;
                    }}
                    """
                )
            else:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {idle_bg};
                        color: {idle_fg};
                        border: none;
                        border-radius: 6px;
                    }}
                    QPushButton:hover {{
                        color: {acc};
                    }}
                    """
                )

    def _rebuild_holiday_rows(self) -> None:
        today = date.today()
        self._last_holiday_render_date = today
        raw_data = self.raw_holidays_by_year.get(self.selected_holiday_year, {})
        entries = HolidayService.parse_holidays(raw_data, today)

        while self.holiday_list_layout.count():
            item = self.holiday_list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        is_light = self.config.theme_mode == "light"
        acc = self.config.accent_color
        irrelevant = self.config.holiday_irrelevant

        if is_light:
            row_bg_active = "#F5F6FA"
            row_bg_expired = "#F9F9FB"
            expired_text_color = "#B0B2BC"
            active_name_color = "#18181C"
            active_detail_color = "#5A5A66"
            makeup_warn_color = "#D9534F"
        else:
            row_bg_active = "#1E1E24"
            row_bg_expired = "#19191E"
            expired_text_color = "#555560"
            active_name_color = "#F4F4F6"
            active_detail_color = "#9E9EA8"
            makeup_warn_color = "#FF8566"

        pending_green = GREEN_ACCENT
        remaining_festivals = 0
        remaining_days_total = 0

        for entry in entries:
            if not entry.is_expired:
                remaining_festivals += 1
                remaining_days_total += entry.holiday_days

            row_frame = QFrame(self.holiday_list_container)
            row_bg = row_bg_expired if entry.is_expired else row_bg_active
            row_frame.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {row_bg};
                    border-radius: 7px;
                }}
                """
            )
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(4)

            # 1. 节日名称列 (56px)
            lbl_name = QLabel(entry.name, row_frame)
            lbl_name.setFixedWidth(56)
            lbl_name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            lbl_name.setFont(get_source_han_font(9, QFont.Weight.Bold if not entry.is_expired else QFont.Weight.Normal))

            # 2. 状态列 (54px)
            if not entry.is_expired and irrelevant:
                status_text = "无效"
                status_tip = "已开启「节假日与我无关」"
            else:
                status_text = entry.status_col_text
                status_tip = entry.hover_countdown_tip

            lbl_status = QLabel(status_text, row_frame)
            lbl_status.setFixedWidth(54)
            lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_status.setFont(get_source_han_font(9, QFont.Weight.Bold if not entry.is_expired else QFont.Weight.Normal))
            lbl_status.setToolTip(status_tip)

            # 3. 休息天数列 (52px)
            lbl_rest = QLabel(entry.rest_col_text, row_frame)
            lbl_rest.setFixedWidth(52)
            lbl_rest.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_rest.setFont(get_source_han_font(9))

            # 4. 补班天数列 (64px)
            lbl_makeup = QLabel(entry.makeup_col_text, row_frame)
            lbl_makeup.setFixedWidth(64)
            lbl_makeup.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_makeup.setFont(get_source_han_font(9))

            if entry.is_expired:
                for lbl in (lbl_name, lbl_status, lbl_rest, lbl_makeup):
                    lbl.setStyleSheet(f"color: {expired_text_color}; background: transparent;")
            else:
                lbl_name.setStyleSheet(f"color: {active_name_color}; background: transparent;")
                if irrelevant:
                    lbl_status.setStyleSheet(f"color: {INVALID_RED}; background: transparent;")
                elif entry.is_ongoing:
                    lbl_status.setStyleSheet(f"color: {acc}; background: transparent;")
                else:
                    lbl_status.setStyleSheet(f"color: {pending_green}; background: transparent;")

                lbl_rest.setStyleSheet(f"color: {active_detail_color}; background: transparent;")
                mk_color = makeup_warn_color if entry.makeup_days > 0 else active_detail_color
                lbl_makeup.setStyleSheet(f"color: {mk_color}; background: transparent;")

            if entry.makeup_dates:
                lbl_makeup.setToolTip(f"补班日期：{', '.join(entry.makeup_dates)}")

            row_layout.addWidget(lbl_name)
            row_layout.addWidget(lbl_status)
            row_layout.addStretch(1)
            row_layout.addWidget(lbl_rest)
            row_layout.addWidget(lbl_makeup)
            self.holiday_list_layout.addWidget(row_frame)

        self.holiday_list_layout.addStretch(1)

    # ------------------------------------------------------------------
    # 调休余额卡片与弹窗
    # ------------------------------------------------------------------
    def _refresh_comp_time_card(self) -> None:
        bal = self.comp_manager.get_balance_hours()
        last_ot = self.comp_manager.get_last_overtime_hours()
        self.lbl_comp_bal_val.setText(f"{bal:.1f} 小时")
        self.lbl_comp_ot_val.setText(f"{last_ot:.1f} 小时")

    def _open_comp_time_dialog(self) -> None:
        if self._active_comp_dlg is not None and self._active_comp_dlg.isVisible():
            self._active_comp_dlg.showNormal()
            self._active_comp_dlg.raise_()
            self._active_comp_dlg.activateWindow()
            return
        dlg = CompTimeDialog(
            comp_manager=self.comp_manager,
            work_end_str=self.config.work_end,
            theme_mode=self.config.theme_mode,
            accent_color=self.config.accent_color,
            lunch_start_str=self.config.lunch_start,
            lunch_end_str=self.config.lunch_end,
            today_is_workday=not TimeCalculator.is_rest_day(date.today(), self.config),
            parent=self,
        )
        dlg.setModal(False)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        dlg.data_changed.connect(self._refresh_comp_time_card)
        dlg.finished.connect(self._on_comp_time_dialog_closed)
        self._active_comp_dlg = dlg
        dlg.adjustSize()
        self.position_beside_main(dlg, dlg.width(), dlg.height(), gap=10)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_comp_time_dialog_closed(self, _res: int = 0) -> None:
        self._active_comp_dlg = None
        self._refresh_comp_time_card()

    # ------------------------------------------------------------------
    # 设置面板
    # ------------------------------------------------------------------
    def _build_settings_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(10)

        self.settings_card = CardFrame(page, radius=16)
        c_layout = QVBoxLayout(self.settings_card)
        c_layout.setContentsMargins(18, 16, 18, 16)
        c_layout.setSpacing(12)

        self.lbl_cfg_title = QLabel("PREFERENCES · 参数设置", self.settings_card)
        self.lbl_cfg_title.setFont(get_source_han_font(11, QFont.Weight.Bold))
        c_layout.addWidget(self.lbl_cfg_title)

        # 摸鱼模式专属设置分组（工作模式下自动隐藏）
        self.fish_settings_widget = QWidget(self.settings_card)
        fs_layout = QVBoxLayout(self.fish_settings_widget)
        fs_layout.setContentsMargins(0, 0, 0, 0)
        fs_layout.setSpacing(12)

        # 1. 上班时间 & 下班时间
        time_group = QHBoxLayout()
        time_group.setSpacing(10)

        start_col = QVBoxLayout()
        start_col.setSpacing(4)
        self.lbl_cfg_start = QLabel("上班时间", self.settings_card)
        self.lbl_cfg_start.setFont(get_source_han_font(9))
        self.edit_work_start = QTimeEdit(self.settings_card)
        self.edit_work_start.setDisplayFormat("HH:mm")
        self.edit_work_start.setTime(QTime(9, 30))
        self.edit_work_start.setFixedHeight(34)
        self.edit_work_start.setFont(get_source_han_font(11, QFont.Weight.Bold))
        start_col.addWidget(self.lbl_cfg_start)
        start_col.addWidget(self.edit_work_start)

        end_col = QVBoxLayout()
        end_col.setSpacing(4)
        self.lbl_cfg_end = QLabel("下班时间", self.settings_card)
        self.lbl_cfg_end.setFont(get_source_han_font(9))
        self.edit_work_end = QTimeEdit(self.settings_card)
        self.edit_work_end.setDisplayFormat("HH:mm")
        self.edit_work_end.setTime(QTime(18, 30))
        self.edit_work_end.setFixedHeight(34)
        self.edit_work_end.setFont(get_source_han_font(11, QFont.Weight.Bold))
        end_col.addWidget(self.lbl_cfg_end)
        end_col.addWidget(self.edit_work_end)

        time_group.addLayout(start_col, 1)
        time_group.addLayout(end_col, 1)
        fs_layout.addLayout(time_group)

        # 1.5 午休开始 & 午休结束（与上下班时间/月薪发薪日保持统一两列对齐）
        lunch_group = QHBoxLayout()
        lunch_group.setSpacing(10)

        lunch_start_col = QVBoxLayout()
        lunch_start_col.setSpacing(4)
        self.lbl_cfg_lunch_start = QLabel("午休开始", self.settings_card)
        self.lbl_cfg_lunch_start.setFont(get_source_han_font(9))
        self.edit_lunch_start = QTimeEdit(self.settings_card)
        self.edit_lunch_start.setDisplayFormat("HH:mm")
        self.edit_lunch_start.setTime(QTime(12, 0))
        self.edit_lunch_start.setFixedHeight(34)
        self.edit_lunch_start.setFont(get_source_han_font(11, QFont.Weight.Bold))
        lunch_start_col.addWidget(self.lbl_cfg_lunch_start)
        lunch_start_col.addWidget(self.edit_lunch_start)

        lunch_end_col = QVBoxLayout()
        lunch_end_col.setSpacing(4)
        self.lbl_cfg_lunch_end = QLabel("午休结束", self.settings_card)
        self.lbl_cfg_lunch_end.setFont(get_source_han_font(9))
        self.edit_lunch_end = QTimeEdit(self.settings_card)
        self.edit_lunch_end.setDisplayFormat("HH:mm")
        self.edit_lunch_end.setTime(QTime(13, 0))
        self.edit_lunch_end.setFixedHeight(34)
        self.edit_lunch_end.setFont(get_source_han_font(11, QFont.Weight.Bold))
        lunch_end_col.addWidget(self.lbl_cfg_lunch_end)
        lunch_end_col.addWidget(self.edit_lunch_end)

        lunch_group.addLayout(lunch_start_col, 1)
        lunch_group.addLayout(lunch_end_col, 1)
        fs_layout.addLayout(lunch_group)

        # 2. 每月发薪日
        pay_col = QVBoxLayout()
        pay_col.setSpacing(4)
        self.lbl_cfg_pay = QLabel("每月发薪日", self.settings_card)
        self.lbl_cfg_pay.setFont(get_source_han_font(9))
        self.spin_payday = QSpinBox(self.settings_card)
        self.spin_payday.setRange(1, 31)
        self.spin_payday.setPrefix("每月 ")
        self.spin_payday.setSuffix(" 日")
        self.spin_payday.setFixedHeight(34)
        self.spin_payday.setFont(get_source_han_font(11, QFont.Weight.Bold))
        pay_col.addWidget(self.lbl_cfg_pay)
        pay_col.addWidget(self.spin_payday)
        fs_layout.addLayout(pay_col)

        # 3. 休息制度（双休 / 自定义休息日）—— 统一 2 列网格对齐
        mode_col = QVBoxLayout()
        mode_col.setSpacing(6)
        self.lbl_cfg_mode = QLabel("休息制度", self.settings_card)
        self.lbl_cfg_mode.setFont(get_source_han_font(9))

        mode_grid = QGridLayout()
        mode_grid.setContentsMargins(0, 0, 0, 0)
        mode_grid.setHorizontalSpacing(10)
        mode_grid.setColumnStretch(0, 1)
        mode_grid.setColumnStretch(1, 1)

        self.rb_double = QRadioButton("双休", self.settings_card)
        self.rb_custom = QRadioButton("自定义休息日", self.settings_card)
        self.rb_double.setFont(get_source_han_font(10))
        self.rb_custom.setFont(get_source_han_font(10))
        self.rb_custom.clicked.connect(self._open_custom_rest_dialog)

        self.mode_group = QButtonGroup(self.settings_card)
        self.mode_group.addButton(self.rb_double)
        self.mode_group.addButton(self.rb_custom)

        mode_grid.addWidget(self.rb_double, 0, 0)
        mode_grid.addWidget(self.rb_custom, 0, 1)
        mode_col.addWidget(self.lbl_cfg_mode)
        mode_col.addLayout(mode_grid)
        fs_layout.addLayout(mode_col)
        c_layout.addWidget(self.fish_settings_widget)

        # 4. 快捷开关（节假日与我无关 / 开机自启）—— 与上下选项框 2 列严格对齐
        sw_col = QVBoxLayout()
        sw_col.setSpacing(6)
        self.lbl_cfg_switches = QLabel("常规选项", self.settings_card)
        self.lbl_cfg_switches.setFont(get_source_han_font(9))

        self.sw_grid = QGridLayout()
        self.sw_grid.setContentsMargins(0, 0, 0, 0)
        self.sw_grid.setHorizontalSpacing(10)
        self.sw_grid.setColumnStretch(0, 1)
        self.sw_grid.setColumnStretch(1, 1)

        self.chk_holiday_irrelevant = QCheckBox("节假日与我无关", self.settings_card)
        self.chk_holiday_irrelevant.setFont(get_source_han_font(10))

        self.chk_auto_start = QCheckBox("开机自启", self.settings_card)
        self.chk_auto_start.setFont(get_source_han_font(10))

        self.chk_close_ask = QCheckBox("退出每次询问", self.settings_card)
        self.chk_close_ask.setFont(get_source_han_font(10))
        self.chk_close_ask.toggled.connect(self._on_close_ask_toggled)

        self.chk_close_to_tray = QCheckBox("退出缩小到任务栏", self.settings_card)
        self.chk_close_to_tray.setFont(get_source_han_font(10))
        self.chk_close_to_tray.toggled.connect(self._on_close_tray_toggled)

        self.chk_auto_update = QCheckBox("自动更新", self.settings_card)
        self.chk_auto_update.setFont(get_source_han_font(10))
        self.chk_auto_update.toggled.connect(self._on_auto_update_toggled)

        self.chk_clip_enabled = QCheckBox("启用粘贴板记录", self.settings_card)
        self.chk_clip_enabled.setFont(get_source_han_font(10))
        self.chk_clip_enabled.setChecked(True)

        self.chk_clip_keep_next_day = QCheckBox("粘贴板保留到第二天", self.settings_card)
        self.chk_clip_keep_next_day.setFont(get_source_han_font(10))
        self.chk_clip_keep_next_day.setChecked(False)

        self.chk_keep_window_on_capture = QCheckBox("截图不隐藏窗口", self.settings_card)
        self.chk_keep_window_on_capture.setFont(get_source_han_font(10))
        self.chk_keep_window_on_capture.setChecked(bool(getattr(self.config, "keep_window_on_capture", False)))
        self.chk_keep_window_on_capture.toggled.connect(self._on_keep_window_capture_toggled)

        self.chk_keep_children_on_hide = QCheckBox("最小化/关闭窗口保留子级", self.settings_card)
        self.chk_keep_children_on_hide.setFont(get_source_han_font(10))
        self.chk_keep_children_on_hide.setChecked(bool(getattr(self.config, "keep_children_on_hide", False)))
        self.chk_keep_children_on_hide.toggled.connect(self._on_keep_children_on_hide_toggled)

        self.sw_grid.setVerticalSpacing(6)
        self.sw_grid.addWidget(self.chk_holiday_irrelevant, 0, 0)
        self.sw_grid.addWidget(self.chk_auto_start, 0, 1)
        self.sw_grid.addWidget(self.chk_close_ask, 1, 0)
        self.sw_grid.addWidget(self.chk_close_to_tray, 1, 1)
        self.sw_grid.addWidget(self.chk_auto_update, 2, 0)
        self.sw_grid.addWidget(self.chk_clip_enabled, 2, 1)
        self.sw_grid.addWidget(self.chk_clip_keep_next_day, 3, 0)
        self.sw_grid.addWidget(self.chk_keep_window_on_capture, 3, 1)
        self.sw_grid.addWidget(self.chk_keep_children_on_hide, 4, 0)
        sw_col.addWidget(self.lbl_cfg_switches)
        sw_col.addLayout(self.sw_grid)
        c_layout.addLayout(sw_col)

        # 5. 界面主题风格（暗黑高级 / 白色简约）
        theme_col = QVBoxLayout()
        theme_col.setSpacing(6)
        self.lbl_cfg_theme = QLabel("界面主题风格", self.settings_card)
        self.lbl_cfg_theme.setFont(get_source_han_font(9))

        theme_grid = QGridLayout()
        theme_grid.setContentsMargins(0, 0, 0, 0)
        theme_grid.setHorizontalSpacing(10)
        theme_grid.setColumnStretch(0, 1)
        theme_grid.setColumnStretch(1, 1)

        self.rb_theme_dark = QRadioButton("暗黑高级", self.settings_card)
        self.rb_theme_light = QRadioButton("白色简约", self.settings_card)
        self.rb_theme_dark.setFont(get_source_han_font(10))
        self.rb_theme_light.setFont(get_source_han_font(10))

        self.theme_group = QButtonGroup(self.settings_card)
        self.theme_group.addButton(self.rb_theme_dark)
        self.theme_group.addButton(self.rb_theme_light)

        theme_grid.addWidget(self.rb_theme_dark, 0, 0)
        theme_grid.addWidget(self.rb_theme_light, 0, 1)
        theme_col.addWidget(self.lbl_cfg_theme)
        theme_col.addLayout(theme_grid)
        c_layout.addLayout(theme_col)

        # 6. 核心点缀色切换
        color_col = QVBoxLayout()
        color_col.setSpacing(6)
        self.lbl_cfg_color = QLabel("核心点缀色", self.settings_card)
        self.lbl_cfg_color.setFont(get_source_han_font(9))

        color_grid = QGridLayout()
        color_grid.setContentsMargins(0, 0, 0, 0)
        color_grid.setHorizontalSpacing(10)
        color_grid.setColumnStretch(0, 1)
        color_grid.setColumnStretch(1, 1)

        self.rb_orange = QRadioButton("琥珀橙", self.settings_card)
        self.rb_green = QRadioButton("翡翠绿", self.settings_card)
        self.rb_orange.setFont(get_source_han_font(10))
        self.rb_green.setFont(get_source_han_font(10))

        self.color_group = QButtonGroup(self.settings_card)
        self.color_group.addButton(self.rb_orange)
        self.color_group.addButton(self.rb_green)

        color_grid.addWidget(self.rb_orange, 0, 0)
        color_grid.addWidget(self.rb_green, 0, 1)
        color_col.addWidget(self.lbl_cfg_color)
        color_col.addLayout(color_grid)
        c_layout.addLayout(color_col)

        c_layout.addSpacing(4)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_cancel_cfg = QPushButton("取消返回", self.settings_card)
        self.btn_cancel_cfg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel_cfg.setFixedHeight(38)
        self.btn_cancel_cfg.setFont(get_source_han_font(10, QFont.Weight.Bold))
        self.btn_cancel_cfg.clicked.connect(self._close_settings_page)

        self.btn_save_cfg = QPushButton("保存并生效", self.settings_card)
        self.btn_save_cfg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_cfg.setFixedHeight(38)
        self.btn_save_cfg.setFont(get_source_han_font(10, QFont.Weight.Bold))
        self.btn_save_cfg.clicked.connect(self._save_settings)

        btn_row.addWidget(self.btn_cancel_cfg, 1)
        btn_row.addWidget(self.btn_save_cfg, 1)
        c_layout.addLayout(btn_row)

        layout.addWidget(self.settings_card)
        layout.addStretch(1)

        ver_row = QHBoxLayout()
        ver_row.setContentsMargins(2, 0, 2, 0)
        ver_row.setSpacing(4)
        self.lbl_version = QLabel(f"IdleMeter · v{CURRENT_VERSION}", page)
        self.lbl_version.setFont(get_source_han_font(9))

        self.btn_version_menu = HamburgerMenuButton(page, self.config.accent_color)
        self.btn_version_menu.setToolTip("菜单")
        self.btn_version_menu.clicked.connect(self._on_version_menu_clicked)

        ver_row.addStretch(1)
        ver_row.addWidget(self.lbl_version)
        ver_row.addWidget(self.btn_version_menu)
        ver_row.addStretch(1)
        layout.addLayout(ver_row)
        return page

    def _open_custom_rest_dialog(self) -> None:
        self.rb_custom.setChecked(True)
        temp_theme = "light" if self.rb_theme_light.isChecked() else "dark"
        temp_acc = GREEN_ACCENT if self.rb_green.isChecked() else ORANGE_ACCENT

        dlg = CustomRestCalendarDialog(
            parent=self,
            rest_dates=self._temp_custom_rest["custom_rest_dates"],
            fixed_weekdays=self._temp_custom_rest["custom_fixed_weekdays"],
            monthly_selected_days_enabled=self._temp_custom_rest["custom_monthly_selected_days_enabled"],
            theme_mode=temp_theme,
            accent_color=temp_acc,
        )
        dlg.adjustSize()
        self.position_beside_main(dlg, dlg.width(), dlg.height(), gap=10)
        if dlg.exec():
            self._temp_custom_rest = dlg.get_result()

    # ------------------------------------------------------------------
    # 主题与配色动态渲染
    # ------------------------------------------------------------------
    def _apply_theme(self) -> None:
        acc = self.config.accent_color
        is_light = self.config.theme_mode == "light"

        if is_light:
            card_bg = "#FFFFFF"
            card_border = "#E4E6EC"
            primary_text = "#18181C"
            secondary_text = "#5A5A66"
            muted_text = "#888894"
            track_color = "#EAECEF"
            pill_bg = "#F2F3F7"
            pill_border = "#E0E2EA"
            pill_text = "#484854"
            pill_hover_bg = "#E8EAF0"
            input_bg = "#F7F8FA"
            input_border = "#D6D8E0"
            cancel_bg = "#EFF0F4"
            cancel_text = "#50505C"
            cancel_border = "#DCDFE6"
            scroll_handle = "#D0D3DC"
            scroll_handle_hover = "#B4B8C4"
        else:
            card_bg = "#17171B"
            card_border = "#232329"
            primary_text = "#FFFFFF"
            secondary_text = "#EAEAEF"
            muted_text = "#7D7D87"
            track_color = "#232329"
            pill_bg = "#1F1F25"
            pill_border = "#2C2C34"
            pill_text = "#C8C8D2"
            pill_hover_bg = "#282830"
            input_bg = "#1F1F25"
            input_border = "#2E2E38"
            cancel_bg = "#23232A"
            cancel_text = "#B0B0BA"
            cancel_border = "#30303A"
            scroll_handle = "#2E2E38"
            scroll_handle_hover = "#444452"

        self.update()
        self._tooltip_manager.set_light_mode(is_light)
        if hasattr(self, "_clip_hover_popup"):
            self._clip_hover_popup.set_light_mode(is_light)

        self._refresh_app_icons()
        self.date_label.setStyleSheet(f"color: {secondary_text};")
        for btn in (
            self.btn_pin,
            self.btn_gear,
            self.btn_mini,
            self.btn_min,
            self.btn_close,
            self.btn_mini_restore,
            self.btn_progress_cfg,
            self.btn_slacking_cfg,
        ):
            btn.set_accent_color(acc)
            btn.set_light_mode(is_light)

        for card in (
            self.clock_card,
            self.progress_card,
            self.slacking_card,
            self.holiday_card,
            self.comp_card,
            self.work_card,
            self.share_card,
            self.clip_card,
            self.lan_card,
            self.alarm_card,
            self.tool_card,
            self.settings_card,
        ):
            card.set_colors(card_bg, card_border)

        # 迷你悬浮窗样式联动
        if hasattr(self, "lbl_mini_icon"):
            self.lbl_mini_icon.setPixmap(_build_app_qpixmap(acc, size=18, hidpi=True))
            self.lbl_mini_time.setStyleSheet(f"color: {primary_text};")
            self.lbl_mini_metric.setStyleSheet(f"color: {secondary_text};")
            self.mini_progress_bar.set_accent_color(acc)
            self.mini_progress_bar.set_track_color(track_color)

        # 带薪摸鱼卡片样式联动
        if hasattr(self, "slacking_card"):
            self.lbl_slacking_title.setStyleSheet(f"color: {muted_text}; border: none; background: transparent;")
            self.lbl_slacking_stats.setStyleSheet(f"color: {acc}; border: none; background: transparent;")
            self.btn_slacking_dash.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {muted_text}; border: none; text-align: right; padding: 0px; }}"
                f"QPushButton:hover {{ color: {acc}; }}"
                f"QPushButton:pressed {{ padding-top: 1px; }}"
            )
            self.slacking_mini_canvas.set_theme(is_light, acc)
            self._apply_slacking_btn_style()

        # 顶部双态胶囊切换控件样式
        self.mode_capsule.setStyleSheet(
            f"QFrame {{ background-color: {pill_bg}; border: 1px solid {pill_border}; border-radius: 11px; }}"
        )
        self._update_app_mode_capsule_styles()

        self.lbl_time_hm.setStyleSheet(f"color: {primary_text};")
        self.lbl_time_s.setStyleSheet(f"color: {acc};")
        self.status_ticker.set_text_color(pill_text)

        # 三合一进度板块（无标题）样式同步
        if hasattr(self, "lbl_icon_work"):
            self.lbl_icon_work.setPixmap(_make_tool_vector_icon("clock_off", acc).pixmap(13, 13))
            self.lbl_icon_weekend.setPixmap(_make_tool_vector_icon("weekend_sun", acc).pixmap(13, 13))
            self.lbl_icon_payday.setPixmap(_make_tool_vector_icon("payday_coin", acc).pixmap(13, 13))
            for lbl_tag in (self.lbl_tag_work, self.lbl_tag_weekend, self.lbl_tag_payday):
                lbl_tag.setStyleSheet(f"color: {primary_text}; border: none; background: transparent;")

        for lbl_cd in (self.lbl_countdown, self.lbl_weekend_countdown, self.lbl_payday_countdown):
            lbl_cd.setStyleSheet(f"color: {secondary_text}; border: none; background: transparent;")

        for lbl_pct in (self.lbl_progress_pct, self.lbl_weekend_pct, self.lbl_payday_pct):
            lbl_pct.setStyleSheet(f"color: {acc}; border: none; background: transparent;")

        for bar in (self.progress_bar, self.weekend_bar, self.payday_bar, self.work_progress_bar):
            bar.set_accent_color(acc)
            bar.set_track_color(track_color)

        # 工作模式极速下载板块样式同步
        self.lbl_progress_title.setStyleSheet(f"color: {muted_text}; border: none; background: transparent;")
        self.lbl_work_title.setStyleSheet(f"color: {muted_text};")
        self.lbl_work_sub.setStyleSheet(f"color: {muted_text};")
        if self.lbl_dl_status.text().startswith("✓"):
            self.lbl_dl_status.setStyleSheet(f"color: {GREEN_ACCENT};")
        elif self.lbl_dl_status.text().startswith("下载失败"):
            self.lbl_dl_status.setStyleSheet(f"color: {INVALID_RED};")
        else:
            self.lbl_dl_status.setStyleSheet(f"color: {secondary_text};")
        self.lbl_dl_pct.setStyleSheet(f"color: {acc};")
        self.edit_dl_url.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {input_bg};
                color: {primary_text};
                border: 1px solid {input_border};
                border-radius: 8px;
                padding: 4px 10px;
            }}
            QLineEdit:focus {{
                border-color: {acc};
            }}
            """
        )
        pill_press_bg = "#DCE0EA" if is_light else "#32323E"
        acc_hover = QColor(acc).lighter(110).name()
        acc_press = QColor(acc).darker(118).name()
        work_sub_btn_qss = f"""
            QPushButton {{
                background-color: {pill_bg};
                color: {primary_text};
                border: 1px solid {pill_border};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {pill_hover_bg};
                border-color: {acc};
                color: {acc};
            }}
            QPushButton:pressed {{
                background-color: {pill_press_bg};
                border-color: {acc};
                color: {acc};
                padding-top: 2px;
                padding-left: 1px;
            }}
        """
        dl_inline_btn_qss = f"""
            QPushButton {{
                background-color: {pill_bg};
                color: {primary_text};
                border: 1px solid {pill_border};
                border-radius: 6px;
                padding: 0px 4px;
            }}
            QPushButton:hover {{
                background-color: {pill_hover_bg};
                border-color: {acc};
                color: {acc};
            }}
            QPushButton:pressed {{
                background-color: {pill_press_bg};
                border-color: {acc};
                color: {acc};
                padding-top: 1px;
            }}
        """
        self.btn_dl_pause.setStyleSheet(dl_inline_btn_qss)
        self.btn_dl_open_dir.setStyleSheet(dl_inline_btn_qss)
        self._apply_dl_main_btn_style()

        # 文件快传卡片主题色联动样式
        if hasattr(self, "lbl_share_title"):
            self.lbl_share_title.setStyleSheet(f"color: {muted_text}; border: none; background: transparent;")
        if hasattr(self, "share_drop_zone"):
            self.share_drop_zone.set_theme(is_light, acc)
            self.lbl_share_drop_hint.setStyleSheet(f"color: {muted_text}; border: none; background: transparent;")
            share_pick_qss = f"""
                QPushButton {{
                    background-color: {pill_bg};
                    color: {primary_text};
                    border: 1px solid {pill_border};
                    border-radius: 6px;
                    padding: 0px 8px;
                }}
                QPushButton:hover {{
                    background-color: {pill_hover_bg};
                    border-color: {acc};
                    color: {acc};
                }}
                QPushButton:pressed {{
                    background-color: {pill_press_bg};
                    border-color: {acc};
                    color: {acc};
                    padding-top: 2px;
                    padding-left: 1px;
                }}
            """
            self.btn_share_pick_file.setStyleSheet(share_pick_qss)
            self.btn_share_pick_dir.setStyleSheet(share_pick_qss)
            self.lbl_share_file_info.setStyleSheet(f"color: {primary_text}; border: none; background: transparent;")
            st_txt = self.lbl_share_tunnel_state.text()
            if "就绪" in st_txt or "完成" in st_txt:
                self.lbl_share_tunnel_state.setStyleSheet(f"color: {GREEN_ACCENT}; border: none; background: transparent;")
            elif "失败" in st_txt or "超时" in st_txt:
                self.lbl_share_tunnel_state.setStyleSheet(f"color: {INVALID_RED}; border: none; background: transparent;")
            else:
                self.lbl_share_tunnel_state.setStyleSheet(f"color: {acc}; border: none; background: transparent;")
            self.lbl_share_link.setStyleSheet(f"color: {acc}; border: none; background: transparent;")
            self.btn_share_copy.setStyleSheet(
                f"QPushButton {{ background-color: {acc}; color: #FFFFFF; border: none; border-radius: 6px; padding: 0px 9px; }}"
                f"QPushButton:hover {{ background-color: {acc_hover}; }}"
                f"QPushButton:pressed {{ background-color: {acc_press}; padding-top: 2px; padding-left: 1px; }}"
                f"QPushButton:disabled {{ background-color: {pill_bg}; color: {muted_text}; border: 1px solid {pill_border}; }}"
            )
            warn_bg = "#FFFBEB" if is_light else "#292112"
            warn_bd = "#FDE68A" if is_light else "#52401B"
            warn_fg = "#B45309" if is_light else "#FBBF24"
            self.lbl_share_proxy_warn.setStyleSheet(
                f"background-color: {warn_bg}; color: {warn_fg}; border: 1px solid {warn_bd}; border-radius: 6px; padding: 3px 7px;"
            )
            self._apply_share_badge_style()
            self.btn_share_stop.setStyleSheet(
                f"QPushButton {{ background-color: {pill_bg}; color: {INVALID_RED}; border: 1px solid {pill_border}; border-radius: 6px; padding: 0px 7px; }}"
                f"QPushButton:hover {{ border-color: {INVALID_RED}; background-color: {pill_hover_bg}; }}"
                f"QPushButton:pressed {{ border-color: {INVALID_RED}; background-color: {pill_press_bg}; padding-top: 2px; }}"
            )

        # 复制历史模块样式同步
        self.lbl_clip_title.setStyleSheet(f"color: {muted_text};")
        self.btn_clip_clear.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {muted_text};
                border: none;
                border-radius: 6px;
                padding: 0px 6px;
            }}
            QPushButton:hover {{
                color: {INVALID_RED};
                background-color: {pill_hover_bg};
            }}
            QPushButton:pressed {{
                color: {INVALID_RED};
                background-color: {pill_press_bg};
                padding-top: 1px;
            }}
            """
        )
        self.clip_list_container.setStyleSheet("background: transparent;")
        self.clip_scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 5px;
                margin: 2px 0px 2px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {scroll_handle};
                min-height: 24px;
                border-radius: 2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            """
        )
        self._update_clip_tab_styles()
        self._rebuild_clipboard_list()

        # 连接手机卡片样式同步
        self.lbl_lan_title.setStyleSheet(f"color: {muted_text};")
        self.lbl_lan_status.setStyleSheet(
            f"color: {GREEN_ACCENT if self._lan_server.is_running() else muted_text};"
        )
        self.btn_lan_manage.setStyleSheet(work_sub_btn_qss)
        self.lan_toggle_switch.set_accent_color(acc)
        self.lan_toggle_switch.set_light_mode(is_light)
        tool_icon_color = "#6E7180" if is_light else "#9E9EA8"
        self.btn_tool_ocr.setStyleSheet(work_sub_btn_qss)
        self.btn_tool_ocr.setIcon(_make_tool_vector_icon("ocr", tool_icon_color))
        self.btn_tool_picker.setStyleSheet(work_sub_btn_qss)
        self.btn_tool_picker.setIcon(_make_tool_vector_icon("picker", tool_icon_color))

        # 闹钟提醒卡片样式同步
        if hasattr(self, "lbl_alarm_title"):
            self.lbl_alarm_title.setStyleSheet(f"color: {muted_text};")
            self.btn_alarm_edit.setStyleSheet(work_sub_btn_qss)
            self.alarm_empty_lbl.setStyleSheet(f"color: {muted_text};")
            self.lbl_alarm_time.setStyleSheet(f"color: {primary_text};")
            acc_bg = QColor(acc)
            acc_bg.setAlpha(36 if is_light else 45)
            self.lbl_alarm_mode.setStyleSheet(
                f"color: {acc}; background-color: rgba({acc_bg.red()}, {acc_bg.green()}, {acc_bg.blue()}, {acc_bg.alpha()});"
                " border-radius: 5px; padding: 2px 6px;"
            )
            self.lbl_alarm_note.setStyleSheet(f"color: {secondary_text};")

        self.lbl_holiday_title.setStyleSheet(f"color: {muted_text};")
        self._update_year_toggle_styles()
        self.holiday_list_container.setStyleSheet("background: transparent;")
        self.holiday_scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 5px;
                margin: 2px 0px 2px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {scroll_handle};
                min-height: 24px;
                border-radius: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {scroll_handle_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            """
        )

        # 调休余额卡片样式
        self.lbl_comp_title.setStyleSheet(f"color: {muted_text};")
        self.lbl_comp_bal_cap.setStyleSheet(f"color: {muted_text};")
        self.lbl_comp_ot_cap.setStyleSheet(f"color: {muted_text};")
        self.lbl_comp_bal_val.setStyleSheet(f"color: {acc};")
        self.lbl_comp_ot_val.setStyleSheet(f"color: {primary_text};")

        self.btn_manage_comp.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {pill_bg};
                color: {primary_text};
                border: 1px solid {pill_border};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: {pill_hover_bg};
                border-color: {acc};
                color: {acc};
            }}
            QPushButton:pressed {{
                background-color: {pill_press_bg};
                border-color: {acc};
                color: {acc};
                padding-top: 2px;
                padding-left: 1px;
            }}
            """
        )

        # 设置面板样式
        self.lbl_cfg_title.setStyleSheet(f"color: {primary_text};")
        for lbl in (
            self.lbl_cfg_start,
            self.lbl_cfg_end,
            self.lbl_cfg_lunch_start,
            self.lbl_cfg_lunch_end,
            self.lbl_cfg_pay,
            self.lbl_cfg_mode,
            self.lbl_cfg_switches,
            self.lbl_cfg_theme,
            self.lbl_cfg_color,
            self.lbl_version,
        ):
            lbl.setStyleSheet(f"color: {muted_text};")

        chk_qss = f"""
            QCheckBox {{
                color: {secondary_text};
                font-family: 'Source Han Sans CN', '思源黑体 CN', 'SimHei';
                font-size: 12px;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 7px;
                border: 1.5px solid {muted_text};
                background-color: {input_bg};
            }}
            QCheckBox::indicator:checked {{
                border-color: {acc};
                background-color: {acc};
            }}
        """
        self.chk_holiday_irrelevant.setStyleSheet(chk_qss)
        self.chk_auto_start.setStyleSheet(chk_qss)
        self.chk_close_ask.setStyleSheet(chk_qss)
        self.chk_close_to_tray.setStyleSheet(chk_qss)
        self.chk_auto_update.setStyleSheet(chk_qss)
        self.chk_clip_enabled.setStyleSheet(chk_qss)
        self.chk_clip_keep_next_day.setStyleSheet(chk_qss)
        self.chk_keep_window_on_capture.setStyleSheet(chk_qss)
        if hasattr(self, "chk_keep_children_on_hide"):
            self.chk_keep_children_on_hide.setStyleSheet(chk_qss)

        for dlg in (
            getattr(self, "_active_lan_dlg", None),
            getattr(self, "_active_feedback_dlg", None),
            getattr(self, "_active_update_dlg", None),
            getattr(self, "_active_cache_dlg", None),
            getattr(self, "_active_about_dlg", None),
            getattr(self, "_active_slacking_dlg", None),
            getattr(self, "_active_progress_cfg_dlg", None),
            getattr(self, "_active_slacking_cfg_dlg", None),
            getattr(self, "_active_alarm_editor_dlg", None),
            *list(getattr(self, "_active_alarm_alerts", [])),
        ):
            if dlg is not None and dlg.isVisible() and hasattr(dlg, "apply_theme"):
                dlg.apply_theme(self.config.theme_mode, self.config.accent_color)
        if hasattr(self, "_lan_server"):
            self._lan_server.set_theme(self.config.theme_mode, self.config.accent_color)
        if getattr(self, "_holiday_popout_dlg", None) is not None and self._holiday_popout_dlg.isVisible():
            self._holiday_popout_dlg.apply_theme(self.config.theme_mode == "light", self.config.accent_color)
        if getattr(self, "_active_comp_dlg", None) is not None and self._active_comp_dlg.isVisible():
            self._active_comp_dlg.apply_theme(self.config.theme_mode, self.config.accent_color)

        if hasattr(self, "tray_menu"):
            self.tray_menu.setStyleSheet(
                f"""
                QMenu {{
                    background-color: {card_bg};
                    color: {primary_text};
                    border: 1px solid {card_border};
                    border-radius: 6px;
                    padding: 4px;
                }}
                QMenu::item {{
                    padding: 5px 18px;
                    border-radius: 4px;
                }}
                QMenu::item:selected {{
                    background-color: {pill_hover_bg};
                    color: {acc};
                }}
                QMenu::separator {{
                    height: 1px;
                    background: {card_border};
                    margin: 3px 6px;
                }}
                """
            )

        up_url, down_url = _ensure_spin_arrow_icons(secondary_text)
        input_qss = f"""
            QTimeEdit, QDoubleSpinBox, QSpinBox {{
                background-color: {input_bg};
                color: {primary_text};
                border: 1px solid {input_border};
                border-radius: 8px;
                padding: 4px 24px 4px 10px;
                font-family: 'Source Han Sans CN', '思源黑体 CN', 'SimHei';
                font-size: 13px;
                font-weight: bold;
            }}
            QTimeEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
                border-color: {acc};
            }}
            QTimeEdit::up-button, QDoubleSpinBox::up-button, QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid {input_border};
                border-top-right-radius: 7px;
                background: transparent;
            }}
            QTimeEdit::down-button, QDoubleSpinBox::down-button, QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 20px;
                border-left: 1px solid {input_border};
                border-top: 1px solid {input_border};
                border-bottom-right-radius: 7px;
                background: transparent;
            }}
            QTimeEdit::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
            QTimeEdit::down-button:hover, QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
                background-color: {pill_hover_bg};
            }}
            QTimeEdit::up-arrow, QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
                image: url({up_url});
                width: 9px;
                height: 7px;
            }}
            QTimeEdit::down-arrow, QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
                image: url({down_url});
                width: 9px;
                height: 7px;
            }}
        """
        for w in (
            self.edit_work_start,
            self.edit_work_end,
            self.edit_lunch_start,
            self.edit_lunch_end,
            self.spin_payday,
        ):
            w.setStyleSheet(input_qss)

        radio_qss = f"""
            QRadioButton {{
                color: {secondary_text};
                font-family: 'Source Han Sans CN', '思源黑体 CN', 'SimHei';
                font-size: 12px;
                spacing: 6px;
            }}
            QRadioButton::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 7px;
                border: 1.5px solid {muted_text};
                background-color: {input_bg};
            }}
            QRadioButton::indicator:checked {{
                border-color: {acc};
                background-color: {acc};
            }}
        """
        for rb in (
            self.rb_double,
            self.rb_custom,
            self.rb_theme_dark,
            self.rb_theme_light,
            self.rb_orange,
            self.rb_green,
        ):
            rb.setStyleSheet(radio_qss)

        secondary_cfg_btn_qss = f"""
            QPushButton {{
                background-color: {cancel_bg};
                color: {cancel_text};
                border: 1px solid {cancel_border};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: {pill_hover_bg};
                color: {primary_text};
                border-color: {acc};
            }}
            QPushButton:pressed {{
                background-color: {pill_press_bg};
                color: {acc};
                border-color: {acc};
                padding-top: 2px;
                padding-left: 1px;
            }}
        """
        self.btn_cancel_cfg.setStyleSheet(secondary_cfg_btn_qss)
        self._apply_save_cfg_btn_style()
        if hasattr(self, "btn_version_menu"):
            self.btn_version_menu.set_theme_colors(muted_text, acc, pill_hover_bg)

    def _apply_save_cfg_btn_style(self) -> None:
        if not hasattr(self, "btn_save_cfg"):
            return
        acc = self.config.accent_color
        acc_hover = QColor(acc).lighter(110).name()
        acc_press = QColor(acc).darker(118).name()
        self.btn_save_cfg.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {acc};
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: {acc_hover};
                color: #FFFFFF;
            }}
            QPushButton:pressed {{
                background-color: {acc_press};
                color: #FFFFFF;
                padding-top: 2px;
                padding-left: 1px;
            }}
            """
        )

    def _restore_save_cfg_btn_state(self) -> None:
        self._save_btn_confirming = False
        if hasattr(self, "btn_save_cfg"):
            self._apply_save_cfg_btn_style()

    # ------------------------------------------------------------------
    # 在线检测更新、后台静默检测与原地静默替换
    # ------------------------------------------------------------------
    def _on_auto_update_toggled(self, checked: bool) -> None:
        self.config.auto_update = bool(checked)
        self.config.save()

    def _on_keep_window_capture_toggled(self, checked: bool) -> None:
        self.config.keep_window_on_capture = bool(checked)
        self.config.save()

    def _refresh_version_menu_badge(self) -> None:
        if hasattr(self, "btn_version_menu"):
            has_any = bool(self._has_new_update or self._has_unread_feedback)
            self.btn_version_menu.set_badge(has_any)
            tips: list[str] = []
            if self._has_new_update and self._pending_update_info:
                tips.append(f"发现新版本 v{self._pending_update_info.get('latest_version', '')}")
            if self._has_unread_feedback:
                tips.append("收到开发者回复")
            self.btn_version_menu.setToolTip("；".join(tips) if tips else "菜单")

    def _position_all_red_dots(self) -> None:
        self._refresh_version_menu_badge()

    def _set_update_red_dot(self, visible: bool) -> None:
        self._has_new_update = bool(visible)
        self._refresh_version_menu_badge()

    def _on_version_menu_clicked(self) -> None:
        ver = CURRENT_VERSION
        log_text = ""
        if self._pending_update_info:
            ver = str(self._pending_update_info.get("latest_version") or CURRENT_VERSION)
            log_text = str(self._pending_update_info.get("changelog") or "")
        popup = VersionMenuPopup(
            theme_mode=self.config.theme_mode,
            accent_color=self.config.accent_color,
            changelog_ver=ver,
            changelog_text=log_text,
            parent=self,
        )
        popup.action_triggered.connect(self._on_version_menu_action)
        btn_global = self.btn_version_menu.mapToGlobal(QPoint(0, self.btn_version_menu.height() + 4))
        x = min(
            btn_global.x(),
            self.x() + self.width() - popup.width() - 8,
        )
        x = max(self.x() + 8, x)
        popup.move(x, btn_global.y())
        popup.show()

    def _on_version_menu_action(self, key: str) -> None:
        if key == "feedback":
            self._on_feedback_clicked()
        elif key == "update":
            self._on_check_update_clicked()
        elif key == "download_link":
            self._on_copy_download_link_clicked()
        elif key == "cache":
            self._open_cache_manager_dialog()
        elif key == "about":
            self._open_about_dialog()

    def _open_about_dialog(self) -> None:
        ver = CURRENT_VERSION
        log_text = ""
        if self._pending_update_info:
            ver = str(self._pending_update_info.get("latest_version") or CURRENT_VERSION)
            log_text = str(self._pending_update_info.get("changelog") or "")
        if self._active_about_dlg is not None and self._active_about_dlg.isVisible():
            self._active_about_dlg.set_changelog_info(ver, log_text)
            self._active_about_dlg.apply_theme(self.config.theme_mode, self.config.accent_color)
            self._active_about_dlg.showNormal()
            self._active_about_dlg.raise_()
            self._active_about_dlg.activateWindow()
            return
        dlg = AboutDialog(
            config=self.config,
            changelog_ver=ver,
            changelog_text=log_text,
            parent=self,
        )
        dlg.setModal(False)
        dlg.finished.connect(lambda _res: setattr(self, "_active_about_dlg", None))
        self._active_about_dlg = dlg
        dlg.adjustSize()
        self.position_beside_main(dlg, dlg.width(), dlg.height(), gap=10)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _is_internet_mode_active(self) -> bool:
        """实时检测【连接手机】是否处于互联网模式或后台 cloudflared 穿透进程仍在运行。"""
        if hasattr(self, "_tunnel_mgr") and self._tunnel_mgr.is_prewarm_only():
            # 仅为局域网静默预热、用户尚未切换至互联网模式时，自动释放后台预热进程以免误拦缓存迁移
            self._tunnel_mgr.stop_all()
        if _has_active_cloudflared_proc():
            return True
        if hasattr(self, "_tunnel_mgr") and self._tunnel_mgr.is_active():
            return True
        if hasattr(self, "_lan_server") and self._lan_server.is_running() and bool(self._lan_server.get_internet_token()):
            return True
        dlg = getattr(self, "_active_lan_dlg", None)
        if dlg is not None:
            try:
                if (
                    getattr(dlg, "_mode", "lan") == "internet"
                    and getattr(self, "_tunnel_mgr", None) is not None
                    and self._tunnel_mgr.get_snapshot().get("state") != "error"
                ):
                    return True
            except RuntimeError:
                pass
        return False

    def _open_cache_manager_dialog(self) -> None:
        if self._active_cache_dlg is not None and self._active_cache_dlg.isVisible():
            self._active_cache_dlg.refresh_info()
            self._active_cache_dlg.showNormal()
            self._active_cache_dlg.raise_()
            self._active_cache_dlg.activateWindow()
            return
        dlg = CacheManagerDialog(
            config=self.config,
            on_migrated=self._on_cache_migrated,
            is_internet_active_fn=self._is_internet_mode_active,
            parent=self,
        )
        dlg.setModal(False)
        dlg.finished.connect(lambda _res: setattr(self, "_active_cache_dlg", None))
        self._active_cache_dlg = dlg
        dlg.adjustSize()
        self.position_beside_main(dlg, dlg.width(), dlg.height(), gap=10)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_cache_migrated(self, new_root: str) -> None:
        ClipboardHistoryStore.set_root_dir(new_root)
        self._clip_items = ClipboardHistoryStore.load(
            bool(getattr(self.config, "clipboard_keep_next_day", False))
        )
        self._rebuild_clipboard_list()
        if hasattr(self, "_lan_server"):
            self._lan_server.set_receive_dir(os.path.join(new_root, "手机互传接收"))

    def _on_copy_download_link_clicked(self) -> None:
        exe_name = "IdleMeter.exe"
        accel_url = (
            f"https://ghfast.top/https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
            f"/releases/latest/download/{exe_name}"
        )
        cb = QApplication.clipboard()
        if cb is not None:
            if hasattr(self, "_clip_watcher"):
                self._clip_watcher.mark_self_write()
            try:
                cb.setText(accel_url)
            finally:
                if hasattr(self, "_clip_watcher"):
                    self._clip_watcher.sync_sequence()
        self._toast.show_message(
            "✓ 已复制下载链接",
            is_light=(self.config.theme_mode == "light"),
            duration_ms=1500,
        )

    def _on_silent_update_found(self, info: dict) -> None:
        self._pending_update_info = info
        if self.config.auto_update:
            self._start_silent_auto_update(info)
        else:
            self._set_update_red_dot(True)

    def _start_silent_auto_update(self, info: dict) -> None:
        if self._update_download_worker is not None and self._update_download_worker.isRunning():
            return
        exe_dir = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else BASE_DIR
        dest_path = os.path.join(exe_dir, "update_temp.exe")
        latest_ver = info["latest_version"]

        worker = UpdateDownloadWorker(info["download_url"], dest_path, self)

        def _on_silent_dl_done(_path: str) -> None:
            is_light = self.config.theme_mode == "light"
            if not getattr(sys, "frozen", False):
                self._toast.show_message(f"已自动下载新版本 v{latest_ver}（源码模式跳过自动替换）", is_light=is_light)
                return
            self._toast.show_message(f"已自动下载新版本 v{latest_ver}，即将重启完成升级", is_light=is_light)
            QTimer.singleShot(1500, self._execute_bat_update_restart)

        worker.finished_signal.connect(_on_silent_dl_done)
        self._update_download_worker = worker
        worker.start()

    def _open_update_dialog(self, info: dict) -> None:
        if self._active_update_dlg is not None and self._active_update_dlg.isVisible():
            self._active_update_dlg.showNormal()
            self._active_update_dlg.raise_()
            self._active_update_dlg.activateWindow()
            return
        dlg = UpdateDialog(
            current_version=CURRENT_VERSION,
            latest_version=info["latest_version"],
            changelog=info["changelog"],
            theme_mode=self.config.theme_mode,
            accent_color=self.config.accent_color,
            parent=self,
        )
        dlg.setModal(False)
        dlg.download_requested.connect(lambda: self._start_update_download(dlg, info["download_url"]))
        dlg.install_requested.connect(lambda: self._install_update_and_restart(dlg))
        dlg.finished.connect(lambda _res: setattr(self, "_active_update_dlg", None))
        self._active_update_dlg = dlg
        dlg.adjustSize()
        self.position_beside_main(dlg, dlg.width(), dlg.height(), gap=10)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_check_update_clicked(self) -> None:
        self._set_update_red_dot(False)
        if (
            self._pending_update_info is not None
            and _parse_version_tuple(self._pending_update_info.get("latest_version", ""))
            > _parse_version_tuple(CURRENT_VERSION)
        ):
            self._open_update_dialog(self._pending_update_info)
            return

        if self._update_check_worker is not None and self._update_check_worker.isRunning():
            return

        worker = UpdateCheckWorker(self)
        worker.finished_signal.connect(self._on_update_check_done)
        worker.error_signal.connect(self._on_update_check_error)
        self._update_check_worker = worker
        worker.start()

    def _on_update_check_done(self, info: dict) -> None:
        is_light = self.config.theme_mode == "light"

        latest_ver = info["latest_version"]
        if _parse_version_tuple(latest_ver) <= _parse_version_tuple(CURRENT_VERSION):
            self._pending_update_info = None
            self._set_update_red_dot(False)
            self._toast.show_message(f"当前已是最新版本 (v{CURRENT_VERSION})", is_light=is_light)
            return

        self._pending_update_info = info
        self._open_update_dialog(info)

    def _on_update_check_error(self, msg: str) -> None:
        self._toast.show_message(msg, is_light=(self.config.theme_mode == "light"))

    def _start_update_download(self, dlg: UpdateDialog, url: str) -> None:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else BASE_DIR
        dest_path = os.path.join(exe_dir, "update_temp.exe")

        worker = UpdateDownloadWorker(url, dest_path, self)
        worker.progress_signal.connect(dlg.set_progress)
        worker.finished_signal.connect(lambda _path: dlg.set_download_finished())
        worker.error_signal.connect(dlg.set_error)
        self._update_download_worker = worker
        worker.start()

    def _execute_bat_update_restart(self) -> bool:
        exe_path = os.path.abspath(sys.executable)
        exe_dir = os.path.dirname(exe_path)
        exe_name = os.path.basename(exe_path)
        temp_exe = os.path.join(exe_dir, "update_temp.exe")
        bat_path = os.path.join(exe_dir, "install_update.bat")

        if not os.path.exists(temp_exe):
            return False

        bat_content = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            'pushd "%~dp0"\r\n'
            "timeout /t 2 /nobreak >nul\r\n"
            f'move /y "update_temp.exe" "{exe_name}" >nul\r\n'
            "ie4uinit.exe -show >nul 2>&1\r\n"
            "set _MEIPASS=\r\n"
            "set _MEIPASS2=\r\n"
            "set TCL_LIBRARY=\r\n"
            "set TK_LIBRARY=\r\n"
            f'explorer.exe "{exe_path}"\r\n'
            'del "%~f0"\r\n'
        )
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)

        clean_env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("_MEI") and k not in ("TCL_LIBRARY", "TK_LIBRARY")
        }
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            env=clean_env,
            creationflags=subprocess.CREATE_NO_WINDOW,
            close_fds=True,
        )
        if hasattr(self, "_clip_hover_popup"):
            self._clip_hover_popup.cancel_and_hide()
        if getattr(self, "_slacking_active", False):
            self._stop_slacking()
        if hasattr(self, "_cloud_bridge"):
            self._cloud_bridge.stop()
        if hasattr(self, "_clip_watcher"):
            self._clip_watcher.stop()
        if hasattr(self, "_active_lan_dlg") and self._active_lan_dlg is not None:
            try:
                self._active_lan_dlg.cleanup_tunnel()
                self._active_lan_dlg.close()
            except Exception:
                pass
        if hasattr(self, "_tunnel_mgr"):
            self._tunnel_mgr.stop_all()
        AlarmAudioPlayer.stop()
        for dlg in list(getattr(self, "_active_alarm_alerts", [])):
            try:
                dlg.close()
            except Exception:
                pass
        if getattr(self, "_active_alarm_editor_dlg", None) is not None:
            try:
                self._active_alarm_editor_dlg.close()
            except Exception:
                pass
        _cleanup_all_cloudflared_procs()
        LanTransferServer.cleanup_all_share_cache()
        if hasattr(self, "_lan_server"):
            self._lan_server.stop()
        if hasattr(self, "cloud_fetch_timer"):
            self.cloud_fetch_timer.stop()
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
        os._exit(0)

    def _install_update_and_restart(self, dlg: UpdateDialog) -> None:
        if not getattr(sys, "frozen", False):
            dlg.set_error("当前为源码模式，打包为 exe 后可测试替换")
            self._toast.show_message(
                "当前为源码模式，打包为 exe 后可测试替换",
                is_light=(self.config.theme_mode == "light"),
            )
            return

        if not self._execute_bat_update_restart():
            dlg.set_error("未找到更新包 update_temp.exe，请重新下载")

    # ------------------------------------------------------------------
    # 意见反馈弹窗与云端配置处理
    # ------------------------------------------------------------------
    @staticmethod
    def _reply_key(item: dict) -> str:
        return f"{item.get('id', '')}_{item.get('reply_time', '')}"

    def _update_feedback_badge(self) -> None:
        read_set = set(str(x) for x in (self.config.read_reply_keys or []))
        self._has_unread_feedback = any(
            isinstance(item, dict)
            and str(item.get("reply") or "").strip()
            and self._reply_key(item) not in read_set
            for item in self._my_feedbacks
        )
        self._refresh_version_menu_badge()

    def _mark_feedback_replies_read(self) -> None:
        read_list = list(self.config.read_reply_keys or [])
        read_set = set(str(x) for x in read_list)
        changed = False
        for item in self._my_feedbacks:
            if not isinstance(item, dict):
                continue
            if str(item.get("reply") or "").strip():
                rkey = self._reply_key(item)
                if rkey not in read_set:
                    read_list.append(rkey)
                    read_set.add(rkey)
                    changed = True
        if changed:
            self.config.read_reply_keys = read_list
            self.config.save()
        self._has_unread_feedback = False
        self._refresh_version_menu_badge()

    def _on_feedback_clicked(self) -> None:
        self._mark_feedback_replies_read()
        if self._active_feedback_dlg is not None and self._active_feedback_dlg.isVisible():
            self._active_feedback_dlg.showNormal()
            self._active_feedback_dlg.raise_()
            self._active_feedback_dlg.activateWindow()
            return
        dlg = FeedbackDialog(
            theme_mode=self.config.theme_mode,
            accent_color=self.config.accent_color,
            history_items=self._my_feedbacks,
            parent=self,
        )
        dlg.setModal(False)
        dlg.submit_requested.connect(lambda content, contact: self._submit_feedback(dlg, content, contact))
        dlg.finished.connect(lambda _res: setattr(self, "_active_feedback_dlg", None))
        self._active_feedback_dlg = dlg
        self._cloud_bridge.fetch_async()
        dlg.adjustSize()
        self.position_beside_main(dlg, dlg.width(), dlg.height(), gap=10)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _submit_feedback(self, dlg: FeedbackDialog, content: str, contact: str) -> None:
        remain = int(FEEDBACK_COOLDOWN_SEC - (time.monotonic() - self._last_feedback_success_ts))
        if self._last_feedback_success_ts > 0 and remain > 0:
            dlg.set_error(f"提交过于频繁，请等待 {remain} 秒后再试")
            return

        dlg.set_submitting(True)
        worker = FeedbackSubmitWorker(content, contact, self.config.device_id, self)

        def _on_ok() -> None:
            self._last_feedback_success_ts = time.monotonic()
            dlg.accept()
            self._toast.show_message(
                "感谢反馈，已发送至开发者！",
                is_light=(self.config.theme_mode == "light"),
            )

        worker.success_signal.connect(_on_ok)
        worker.error_signal.connect(dlg.set_error)
        self._feedback_worker = worker
        worker.start()

    def _get_status_quote_interval_ms(self) -> int:
        if self._cloud_cfg.get("top_enabled") is True:
            msgs = self._cloud_cfg.get("top_messages")
            if isinstance(msgs, list) and any(str(m).strip() for m in msgs):
                try:
                    raw = self._cloud_cfg.get("top_interval", self._cloud_cfg.get("interval", 5))
                    sec = int(raw)
                    if sec >= 1:
                        return sec * 1000
                except Exception:
                    pass
        return STATUS_QUOTE_INTERVAL_MS

    def _get_salary_quote_interval_ms(self) -> int:
        if self._cloud_cfg.get("salary_enabled") is True:
            tiers = self._cloud_cfg.get("salary_tiers")
            if isinstance(tiers, list) and tiers:
                has_msgs = any(
                    isinstance(t, dict) and any(str(m).strip() for m in (t.get("messages") or []))
                    for t in tiers
                )
                if has_msgs:
                    try:
                        sec = int(self._cloud_cfg.get("salary_interval", 8))
                        if sec >= 1:
                            return sec * 1000
                    except Exception:
                        pass
        return SALARY_QUOTE_INTERVAL_MS

    def _sync_feedback_ui(self) -> None:
        if self._active_feedback_dlg is not None:
            if self._my_feedbacks != self._active_feedback_dlg._history_items:
                self._active_feedback_dlg.update_history(self._my_feedbacks)
            self._mark_feedback_replies_read()
        else:
            self._update_feedback_badge()

    def _on_cloud_config_ready(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        raw_fb = data.get("my_feedbacks")
        self._my_feedbacks = [item for item in raw_fb if isinstance(item, dict)] if isinstance(raw_fb, list) else []
        self._sync_feedback_ui()

        if data == self._cloud_cfg:
            return
        self._cloud_cfg = data

        # 立即应用最新底部状态栏文案与轮播间隔
        top_interval = self._get_status_quote_interval_ms()
        if hasattr(self, "quote_timer"):
            self.quote_timer.start(top_interval)
        top_key, top_pool = self._get_current_quote_pool()
        self._active_quote_pool_key = top_key
        self._quote_idx = 0
        self._last_status_quote_ms = self._now_ms()
        self.status_ticker.slide_to(top_pool[0])

    # ------------------------------------------------------------------
    # 摸鱼模式 / 工作模式切换 & 极速下载板块
    # ------------------------------------------------------------------
    def _update_app_mode_capsule_styles(self) -> None:
        is_light = self.config.theme_mode == "light"
        is_work = getattr(self.config, "app_mode", "fish") == "work"

        # 纯灰阶单色图标：未选中浅灰，选中深灰/炭黑高对比度
        idle_icon_hex = "#9ca3af" if is_light else "#71717a"
        active_icon_hex = "#18181b" if is_light else "#f4f4f5"
        active_bg = "#e4e4e7" if is_light else "#3f3f46"
        active_press_bg = "#d4d4d8" if is_light else "#52525b"
        hover_bg = "#f4f4f5" if is_light else "#27272a"
        idle_press_bg = "#e4e4e7" if is_light else "#323238"

        self.btn_app_fish.setToolTip(
            "当前：摸鱼模式 / 点击切换工作模式" if not is_work else "点击切换摸鱼模式"
        )
        self.btn_app_work.setToolTip(
            "当前：工作模式 / 点击切换摸鱼模式" if is_work else "点击切换工作模式"
        )

        for btn, kind, active in (
            (self.btn_app_fish, "fish", not is_work),
            (self.btn_app_work, "work", is_work),
        ):
            icon_hex = active_icon_hex if active else idle_icon_hex
            btn.setIcon(_make_grayscale_mode_icon(kind, icon_hex))
            if active:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {active_bg};
                        border: none;
                        border-radius: 9px;
                        padding: 0px;
                    }}
                    QPushButton:pressed {{
                        background-color: {active_press_bg};
                        padding-top: 1px;
                    }}
                    """
                )
            else:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background: transparent;
                        border: none;
                        border-radius: 9px;
                        padding: 0px;
                    }}
                    QPushButton:hover {{
                        background-color: {hover_bg};
                    }}
                    QPushButton:pressed {{
                        background-color: {idle_press_bg};
                        padding-top: 1px;
                    }}
                    """
                )

    def _switch_app_mode(self, mode: str) -> None:
        if getattr(self.config, "app_mode", "fish") == mode:
            return
        if mode == "work" and getattr(self, "_slacking_active", False):
            self._stop_slacking()
        self.config.app_mode = mode
        self.config.save()
        self._apply_app_mode(save=False)

    def _apply_app_mode(self, save: bool = False) -> None:
        is_work = getattr(self.config, "app_mode", "fish") == "work"
        if hasattr(self, "mode_stack"):
            self.mode_stack.setCurrentIndex(1 if is_work else 0)
        if hasattr(self, "fish_settings_widget"):
            self.fish_settings_widget.setVisible(not is_work)
        if hasattr(self, "chk_holiday_irrelevant"):
            self.chk_holiday_irrelevant.setVisible(not is_work)
        if hasattr(self, "chk_clip_enabled"):
            self.chk_clip_enabled.setVisible(is_work)
        if hasattr(self, "chk_clip_keep_next_day"):
            self.chk_clip_keep_next_day.setVisible(is_work)
        if hasattr(self, "chk_keep_window_on_capture"):
            if is_work:
                self.chk_keep_window_on_capture.blockSignals(True)
                self.chk_keep_window_on_capture.setChecked(
                    bool(getattr(self.config, "keep_window_on_capture", False))
                )
                self.chk_keep_window_on_capture.blockSignals(False)
            self.chk_keep_window_on_capture.setVisible(is_work)
        if hasattr(self, "chk_keep_children_on_hide"):
            self.chk_keep_children_on_hide.blockSignals(True)
            self.chk_keep_children_on_hide.setChecked(
                bool(getattr(self.config, "keep_children_on_hide", False))
            )
            self.chk_keep_children_on_hide.blockSignals(False)
            self.chk_keep_children_on_hide.setVisible(True)
        if hasattr(self, "sw_grid"):
            all_chks = [
                self.chk_holiday_irrelevant,
                self.chk_auto_start,
                self.chk_close_ask,
                self.chk_close_to_tray,
                self.chk_auto_update,
                self.chk_clip_enabled,
                self.chk_clip_keep_next_day,
                self.chk_keep_window_on_capture,
                self.chk_keep_children_on_hide,
            ]
            for chk in all_chks:
                self.sw_grid.removeWidget(chk)
            if is_work:
                visible_chks = [
                    self.chk_clip_enabled,
                    self.chk_clip_keep_next_day,
                    self.chk_auto_start,
                    self.chk_close_ask,
                    self.chk_close_to_tray,
                    self.chk_auto_update,
                    self.chk_keep_window_on_capture,
                    self.chk_keep_children_on_hide,
                ]
            else:
                visible_chks = [
                    self.chk_holiday_irrelevant,
                    self.chk_auto_start,
                    self.chk_close_ask,
                    self.chk_close_to_tray,
                    self.chk_auto_update,
                    self.chk_keep_children_on_hide,
                ]
            for idx, chk in enumerate(visible_chks):
                self.sw_grid.addWidget(chk, idx // 2, idx % 2)
        if hasattr(self, "settings_card"):
            self.settings_card.adjustSize()
        if hasattr(self, "settings_page"):
            self.settings_page.updateGeometry()
        self._update_app_mode_capsule_styles()

    @staticmethod
    def _truncate_dl_name(name: str, max_chars: int = 18) -> str:
        text = str(name or "").strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."

    def _set_dl_status_elided(self, text: str) -> None:
        fm = QFontMetrics(self.lbl_dl_status.font())
        max_w = max(180, self.lbl_dl_status.width() if self.lbl_dl_status.width() > 40 else 245)
        self.lbl_dl_status.setText(fm.elidedText(str(text or ""), Qt.TextElideMode.ElideRight, max_w))

    def _apply_dl_main_btn_style(self) -> None:
        if not hasattr(self, "btn_dl_start"):
            return
        acc = self.config.accent_color
        is_light = self.config.theme_mode == "light"
        pill_border = "#E2E4EB" if is_light else "#2B2B33"
        muted_text = "#8B8C98" if is_light else "#71717A"
        if self._dl_bridge.is_downloading():
            cancel_bg = "#FEF2F2" if is_light else "#331C1E"
            cancel_hover = "#FEE2E2" if is_light else "#472226"
            cancel_press = "#FECACA" if is_light else "#5B262B"
            cancel_border = "#FCA5A5" if is_light else "#7F2D33"
            self.btn_dl_start.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {cancel_bg};
                    color: {INVALID_RED};
                    border: 1px solid {cancel_border};
                    border-radius: 10px;
                }}
                QPushButton:hover {{
                    background-color: {cancel_hover};
                    border-color: {INVALID_RED};
                }}
                QPushButton:pressed {{
                    background-color: {cancel_press};
                    border-color: {INVALID_RED};
                    padding-top: 2px;
                    padding-left: 1px;
                }}
                """
            )
        else:
            acc_hover = QColor(acc).lighter(110).name()
            acc_press = QColor(acc).darker(118).name()
            self.btn_dl_start.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {acc};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 10px;
                }}
                QPushButton:hover {{
                    background-color: {acc_hover};
                }}
                QPushButton:pressed {{
                    background-color: {acc_press};
                    padding-top: 2px;
                    padding-left: 1px;
                }}
                QPushButton:disabled {{
                    background-color: {pill_border};
                    color: {muted_text};
                }}
                """
            )

    def _on_dl_start_clicked(self) -> None:
        # 下载进行中时主按钮为“取消”，点击立即中断下载并清理 .part 临时文件
        if self._dl_bridge.is_downloading():
            self._dl_bridge.cancel()
            return
        url = self.edit_dl_url.text().strip()
        if not url.lower().startswith(("http://", "https://")):
            self._toast.show_message(
                "请输入有效的 HTTP / HTTPS 下载链接",
                is_light=(self.config.theme_mode == "light"),
            )
            return

        default_dir = (self.config.last_download_dir or "").strip() or FastDownloader.default_download_dir()
        default_fname = FastDownloader._extract_filename({}, url)
        default_path = os.path.join(default_dir, default_fname)
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择保存位置",
            default_path,
            "所有文件 (*.*)",
        )
        if not save_path:
            return

        save_dir = os.path.dirname(save_path) or default_dir
        fname = os.path.basename(save_path) or default_fname
        self.config.last_download_dir = save_dir
        self.config.save()

        dest_path = save_path
        self._last_completed_file = ""
        self._last_dl_size_str = ""
        self.btn_dl_start.setEnabled(True)
        self.btn_dl_start.setText("取消")
        self.btn_dl_pause.setText("⏸")
        self.btn_dl_pause.setToolTip("暂停下载")
        self.btn_dl_pause.setVisible(True)
        self.btn_dl_open_dir.setVisible(False)
        self.work_progress_bar.set_value(0.0)
        self.lbl_dl_pct.setText("0%")
        sec_text = "#5A5A66" if self.config.theme_mode == "light" else "#EAEAEF"
        self.lbl_dl_status.setStyleSheet(f"color: {sec_text};")
        self._set_dl_status_elided(f"正在连接 {self._truncate_dl_name(fname)}...")

        self._dl_bridge.start_download(url, dest_path, 0, False)
        self._apply_dl_main_btn_style()

    def _on_dl_pause_clicked(self) -> None:
        if not self._dl_bridge.is_downloading():
            return
        paused = self._dl_bridge.toggle_pause()
        if paused:
            self.btn_dl_pause.setText("▶")
            self.btn_dl_pause.setToolTip("继续下载")
            sz = getattr(self, "_last_dl_size_str", "")
            self._set_dl_status_elided(f"已暂停 · {sz}" if sz else "已暂停")
        else:
            self.btn_dl_pause.setText("⏸")
            self.btn_dl_pause.setToolTip("暂停下载")
            sz = getattr(self, "_last_dl_size_str", "")
            self._set_dl_status_elided(f"继续下载... · {sz}" if sz else "继续下载...")

    def _on_dl_progress(self, pct: float, speed_str: str, size_str: str, thread_desc: str) -> None:
        self._last_dl_size_str = size_str
        self.work_progress_bar.set_value(float(pct))
        self.lbl_dl_pct.setText("100%" if pct >= 100.0 else f"{pct:.1f}%")
        if self._dl_bridge.is_paused():
            self._set_dl_status_elided(f"已暂停 · {size_str}" if size_str else "已暂停")
        else:
            self._set_dl_status_elided(f"下载中... {speed_str} · {size_str}")

    def _on_dl_finished(self, final_path: str) -> None:
        self._last_completed_file = final_path
        self.btn_dl_start.setEnabled(True)
        self.btn_dl_start.setText("下载")
        self.btn_dl_pause.setVisible(False)
        self.btn_dl_open_dir.setVisible(True)
        self._apply_dl_main_btn_style()
        self.work_progress_bar.set_value(100.0)
        self.lbl_dl_pct.setText("100%")
        self.lbl_dl_status.setStyleSheet(f"color: {GREEN_ACCENT};")
        self._set_dl_status_elided(f"✓ 下载完成 · {self._truncate_dl_name(os.path.basename(final_path))}")

    def _on_dl_error(self, msg: str) -> None:
        self.btn_dl_start.setEnabled(True)
        self.btn_dl_start.setText("下载")
        self.btn_dl_pause.setVisible(False)
        self._apply_dl_main_btn_style()
        self.lbl_dl_status.setStyleSheet(f"color: {INVALID_RED};")
        short_msg = str(msg or "未知错误").strip()
        if len(short_msg) > 42:
            short_msg = short_msg[:39] + "..."
        self._set_dl_status_elided(f"下载失败：{short_msg}")

    def _on_dl_cancelled(self) -> None:
        self.btn_dl_start.setEnabled(True)
        self.btn_dl_start.setText("下载")
        self.btn_dl_pause.setVisible(False)
        self._apply_dl_main_btn_style()
        sec_text = "#5A5A66" if self.config.theme_mode == "light" else "#EAEAEF"
        self.lbl_dl_status.setStyleSheet(f"color: {sec_text};")
        self._set_dl_status_elided("已取消 · 临时文件已清理")
        self.work_progress_bar.set_value(0.0)
        self.lbl_dl_pct.setText("0%")

    def _on_dl_cancel_clicked(self) -> None:
        self._dl_bridge.cancel()

    def _on_dl_open_dir_clicked(self) -> None:
        target = self._last_completed_file
        folder = os.path.dirname(target) if target else (self.config.last_download_dir or FastDownloader.default_download_dir())
        if os.path.isdir(folder):
            try:
                os.startfile(folder)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 工作模式：复制历史记录
    # ------------------------------------------------------------------
    def _update_clip_tab_styles(self) -> None:
        if not hasattr(self, "_clip_tab_btns"):
            return
        acc = self.config.accent_color
        is_light = self.config.theme_mode == "light"
        muted = "#8B8C98" if is_light else "#71717A"
        hover_bg = "#ECEDF2" if is_light else "#232329"
        for key, btn in self._clip_tab_btns.items():
            active = key == self._clip_filter
            if active:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {acc};
                        color: #FFFFFF;
                        border: none;
                        border-radius: 6px;
                        padding: 0px 6px;
                    }}
                    """
                )
            else:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background: transparent;
                        color: {muted};
                        border: none;
                        border-radius: 6px;
                        padding: 0px 6px;
                    }}
                    QPushButton:hover {{
                        color: {acc};
                        background-color: {hover_bg};
                    }}
                    """
                )

    def _set_clip_filter(self, filter_key: str) -> None:
        self._clip_filter = filter_key
        self._update_clip_tab_styles()
        self._rebuild_clipboard_list()

    def _on_clip_clear_clicked(self) -> None:
        self._clip_items = ClipboardHistoryStore.clear_all(self._clip_items)
        self._rebuild_clipboard_list()

    def _check_clip_day_rollover(self) -> None:
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str != self._clip_last_date:
            self._clip_last_date = today_str
            if not getattr(self.config, "clipboard_keep_next_day", False):
                self._clip_items, changed = ClipboardHistoryStore.prune_non_today(self._clip_items)
                if changed:
                    ClipboardHistoryStore.save(self._clip_items)
                    self._rebuild_clipboard_list()

    def _on_system_clipboard_changed(self) -> None:
        if not getattr(self.config, "clipboard_history_enabled", True):
            return
        self._check_clip_day_rollover()
        cb = QApplication.clipboard()
        if cb is None:
            return
        mime = cb.mimeData()
        if mime is None:
            return

        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")
        entry: dict | None = None

        if mime.hasUrls():
            paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            paths = [p for p in paths if p]
            if paths:
                first_name = os.path.basename(paths[0]) or paths[0]
                preview = first_name if len(paths) == 1 else f"{first_name} 等 {len(paths)} 个文件"
                entry = {
                    "id": uuid.uuid4().hex[:12],
                    "type": "file",
                    "preview": preview,
                    "content": "",
                    "image_path": "",
                    "image_hash": "",
                    "file_paths": paths,
                    "time_str": time_str,
                    "date_str": date_str,
                    "ts": time.time(),
                }

        if entry is None and mime.hasImage():
            img = cb.image()
            if not img.isNull():
                ClipboardHistoryStore.ensure_cache_dir()
                fname = f"clip_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.png"
                img_path = os.path.join(ClipboardHistoryStore.CACHE_DIR, fname)
                if img.save(img_path, "PNG"):
                    try:
                        with open(img_path, "rb") as f:
                            img_hash = hashlib.md5(f.read()).hexdigest()
                    except Exception:
                        img_hash = uuid.uuid4().hex
                    entry = {
                        "id": uuid.uuid4().hex[:12],
                        "type": "file",
                        "preview": f"截图 {fname} ({img.width()}×{img.height()})",
                        "content": "",
                        "image_path": img_path,
                        "image_hash": img_hash,
                        "file_paths": [img_path],
                        "time_str": time_str,
                        "date_str": date_str,
                        "ts": time.time(),
                    }

        if entry is None and mime.hasText():
            raw_text = mime.text()
            if raw_text and raw_text.strip():
                trimmed = raw_text.strip()
                is_link = trimmed.lower().startswith(("http://", "https://"))
                single_line = " ".join(trimmed.splitlines()).strip()
                entry = {
                    "id": uuid.uuid4().hex[:12],
                    "type": "link" if is_link else "text",
                    "preview": single_line,
                    "content": trimmed if is_link else raw_text,
                    "image_path": "",
                    "image_hash": "",
                    "file_paths": [],
                    "time_str": time_str,
                    "date_str": date_str,
                    "ts": time.time(),
                }

        if entry is None:
            return
        self._clip_items = ClipboardHistoryStore.add_or_bump(self._clip_items, entry)
        self._rebuild_clipboard_list()

    def _copy_clip_entry(self, entry: dict, btn: QPushButton) -> None:
        cb = QApplication.clipboard()
        if cb is None:
            return
        etype = entry.get("type")
        self._clip_watcher.mark_self_write()
        try:
            if etype in ("text", "link"):
                cb.setText(str(entry.get("content") or ""))
            elif etype == "image":
                img_path = str(entry.get("image_path") or "")
                if os.path.isfile(img_path):
                    img = QImage(img_path)
                    if not img.isNull():
                        cb.setImage(img)
            elif etype == "file":
                paths = [p for p in (entry.get("file_paths") or []) if p]
                if paths:
                    md = QMimeData()
                    md.setUrls([QUrl.fromLocalFile(p) for p in paths])
                    cb.setMimeData(md)
        finally:
            self._clip_watcher.sync_sequence()

        btn.setText("✓ 已复制")
        QTimer.singleShot(1200, lambda b=btn: b.setText("复制") if b is not None else None)

    def _send_clip_link_to_downloader(self, url: str) -> None:
        if hasattr(self, "edit_dl_url"):
            self.edit_dl_url.setText(url.strip())
            self.edit_dl_url.setFocus()
            self._toast.show_message(
                "已填入上方多线程下载器",
                is_light=(self.config.theme_mode == "light"),
            )

    def _rebuild_clipboard_list(self) -> None:
        if not hasattr(self, "clip_list_layout"):
            return
        if hasattr(self, "_clip_hover_popup"):
            self._clip_hover_popup.cancel_and_hide()
        while self.clip_list_layout.count() > 0:
            item = self.clip_list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        is_light = self.config.theme_mode == "light"
        acc = self.config.accent_color
        row_bg = "#F7F8FA" if is_light else "#1E1E24"
        row_border = "#E6E8EF" if is_light else "#2B2B33"
        primary_fg = "#1D1E22" if is_light else "#F5F5F7"
        muted_fg = "#8B8C98" if is_light else "#71717A"
        btn_bg = "#FFFFFF" if is_light else "#26262E"
        btn_hover = "#ECEDF2" if is_light else "#30303A"

        visible_items = [
            it for it in self._clip_items
            if self._clip_filter == "all" or it.get("type") == self._clip_filter
        ]

        if not visible_items:
            empty_lbl = QLabel("暂无粘贴板记录", self.clip_list_container)
            empty_lbl.setFont(get_source_han_font(9))
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setFixedHeight(80)
            empty_lbl.setStyleSheet(f"color: {muted_fg}; background: transparent;")
            self.clip_list_layout.addWidget(empty_lbl)
            self.clip_list_layout.addStretch(1)
            return

        vp_w = self.clip_scroll.viewport().width() if hasattr(self, "clip_scroll") else 0
        row_avail_w = vp_w - 4 if vp_w > 120 else 286

        for entry in visible_items:
            row = QFrame(self.clip_list_container)
            row.setFixedHeight(32)
            row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.setStyleSheet(
                f"QFrame {{ background-color: {row_bg}; border: 1px solid {row_border}; border-radius: 8px; }}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(6, 3, 6, 3)
            rl.setSpacing(5)

            etype = str(entry.get("type") or "text")

            # 1. 优先构建右侧固定宽度操作按钮容器，确保“下载 / 传手机 / 复制”永远贴右完整显示、绝不被左侧文本挤出
            act_box = QWidget(row)
            act_box.setStyleSheet("background: transparent; border: none;")
            act_box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            act_l = QHBoxLayout(act_box)
            act_l.setContentsMargins(4, 0, 0, 0)
            act_l.setSpacing(4)

            if etype != "link":
                raw_time = str(entry.get("time_str") or "")
                short_time = raw_time[:5] if len(raw_time) >= 5 else raw_time
                time_lbl = QLabel(short_time, act_box)
                time_lbl.setFont(get_source_han_font(7))
                time_lbl.setStyleSheet(f"color: {muted_fg}; border: none; background: transparent;")
                time_lbl.setFixedWidth(28)
                time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                act_l.addWidget(time_lbl)

            if etype == "link":
                btn_dl = QPushButton("下载", act_box)
                btn_dl.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_dl.setFixedSize(32, 22)
                btn_dl.setFont(get_source_han_font(7, QFont.Weight.Bold))
                btn_dl.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {btn_bg};
                        color: {acc};
                        border: 1px solid {row_border};
                        border-radius: 5px;
                    }}
                    QPushButton:hover {{
                        background-color: {btn_hover};
                        border-color: {acc};
                    }}
                    """
                )
                btn_dl.clicked.connect(
                    lambda checked=False, u=str(entry.get("content") or ""): self._send_clip_link_to_downloader(u)
                )
                act_l.addWidget(btn_dl)

            btn_send = QPushButton("传手机", act_box)
            btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_send.setFixedSize(42, 22)
            btn_send.setFont(get_source_han_font(7))
            btn_send.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {btn_bg};
                    color: {muted_fg};
                    border: 1px solid {row_border};
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    background-color: {btn_hover};
                    border-color: {acc};
                    color: {acc};
                }}
                """
            )
            btn_send.clicked.connect(lambda checked=False, e=entry: self._send_clip_entry_to_phone(e))
            act_l.addWidget(btn_send)

            btn_cp = QPushButton("复制", act_box)
            btn_cp.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_cp.setFixedSize(36, 22)
            btn_cp.setFont(get_source_han_font(7, QFont.Weight.Bold))
            btn_cp.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {btn_bg};
                    color: {primary_fg};
                    border: 1px solid {row_border};
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    background-color: {btn_hover};
                    border-color: {acc};
                    color: {acc};
                }}
                """
            )
            btn_cp.clicked.connect(
                lambda checked=False, e=entry, b=btn_cp: self._copy_clip_entry(e, b)
            )
            act_l.addWidget(btn_cp)
            act_box.adjustSize()

            # 2. 左侧类型图标 + 动态单行省略预览文本（Ignored 水平策略只占右侧按钮剩余宽度，悬停 250ms 显示完整内容）
            icon_lbl = QLabel(row)
            icon_lbl.setFixedSize(18, 18)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setStyleSheet("border: none; background: transparent;")
            img_path = str(entry.get("image_path") or "")
            if img_path and os.path.isfile(img_path):
                pm = QPixmap(img_path)
                if not pm.isNull():
                    icon_lbl.setPixmap(
                        pm.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    )
            else:
                icon_lbl.setPixmap(_make_clip_type_icon(etype, muted_fg).pixmap(13, 13))

            raw_content = str(entry.get("content") or "")
            raw_preview = str(entry.get("preview") or raw_content)
            is_textual = etype in ("text", "link")
            full_hover_text = raw_content if (is_textual and raw_content.strip()) else raw_preview
            est_text_w = max(48, row_avail_w - 12 - 18 - 10 - act_box.sizeHint().width())

            preview_lbl = _ClipPreviewLabel(
                raw_preview=raw_preview,
                full_text=full_hover_text,
                enable_hover=is_textual,
                hover_popup=getattr(self, "_clip_hover_popup", None),
                fallback_width=est_text_w,
                parent=row,
            )
            preview_lbl.setFont(get_source_han_font(8))
            preview_lbl.setStyleSheet(f"color: {primary_fg}; border: none; background: transparent;")
            preview_lbl.update_elided_text(est_text_w)

            rl.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            rl.addWidget(preview_lbl, 1)
            rl.addWidget(act_box, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self.clip_list_layout.addWidget(row)

        self.clip_list_layout.addStretch(1)

    # ------------------------------------------------------------------
    # 工作模式：文件快传（拖入生成公网高速下载直链，支持零拷贝/ZIP_STORED/阅后即焚/代理检测）
    # ------------------------------------------------------------------
    def _apply_share_badge_style(self) -> None:
        if not hasattr(self, "lbl_share_badge"):
            return
        is_light = self.config.theme_mode == "light"
        acc = self.config.accent_color
        st = getattr(self, "_share_badge_state", "ready")
        if st == "completed":
            bg = "#ECFDF5" if is_light else "#132920"
            bd = "#A7F3D0" if is_light else "#1F4D3A"
            fg = GREEN_ACCENT
        elif st == "downloading":
            ac = QColor(acc)
            bg = f"rgba({ac.red()}, {ac.green()}, {ac.blue()}, {'0.12' if is_light else '0.18'})"
            bd = f"rgba({ac.red()}, {ac.green()}, {ac.blue()}, {'0.36' if is_light else '0.44'})"
            fg = acc
        else:
            bg = "#F1F5F9" if is_light else "#23232C"
            bd = "#CBD5E1" if is_light else "#323240"
            fg = "#475569" if is_light else "#B4B4C2"
        self.lbl_share_badge.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border: 1px solid {bd}; border-radius: 6px; padding: 2px 7px;"
        )

    def _set_share_badge(self, state: str, text: str) -> None:
        self._share_badge_state = state
        self.lbl_share_badge.setText(text)
        self._apply_share_badge_style()

    def _refresh_share_proxy_warning(self) -> None:
        if not hasattr(self, "lbl_share_proxy_warn"):
            return
        if self.share_active_box.isHidden():
            self.lbl_share_proxy_warn.setVisible(False)
            self.lbl_share_proxy_warn.setText("")
            return
        warn_text = format_proxy_tun_warning(detect_proxy_or_tun())
        self.lbl_share_proxy_warn.setText(warn_text)
        self.lbl_share_proxy_warn.setVisible(bool(warn_text))

    def _on_share_pick_file_clicked(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择要分享的文件（支持多选）", os.path.expanduser("~"))
        if files:
            self._on_share_paths_selected(files)

    def _on_share_pick_dir_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择要分享的文件夹", os.path.expanduser("~"))
        if folder:
            self._on_share_paths_selected([folder])

    def _on_share_paths_selected(self, paths: list[str]) -> None:
        valid = [os.path.abspath(p) for p in (paths or []) if p and os.path.exists(p)]
        if not valid:
            return
        self._share_reset_timer.stop()
        if self._share_active_id:
            LanTransferServer.unregister_share(self._share_active_id)
            self._share_active_id = ""

        self._share_seq += 1
        seq = self._share_seq
        self._share_public_url = ""
        self._share_auto_copied = False
        self._share_tunnel_pending = True

        self.share_idle_box.setVisible(False)
        self.share_active_box.setVisible(True)
        self._set_share_badge("ready", "一次性有效 · 仅限首人下载（15分钟内有效）")
        self.btn_share_copy.setEnabled(False)
        self.lbl_share_link.setText("正在连接公网隧道...")
        self.lbl_share_link.setToolTip("")
        self.lbl_share_tunnel_state.setText("连接中...")
        self.lbl_share_tunnel_state.setStyleSheet(
            f"color: {self.config.accent_color}; border: none; background: transparent;"
        )

        is_single_file = len(valid) == 1 and os.path.isfile(valid[0])
        if is_single_file:
            sz_txt = LanTransferServer._format_size(os.path.getsize(valid[0]))
            fm = QFontMetrics(self.lbl_share_file_info.font())
            self.lbl_share_file_info.setText(fm.elidedText(f"{os.path.basename(valid[0])} · {sz_txt}", Qt.TextElideMode.ElideMiddle, 210))
            self.lbl_share_file_info.setToolTip(valid[0])
        else:
            self.lbl_share_file_info.setText("正在快速打包...")
            self.lbl_share_file_info.setToolTip("")

        self._refresh_share_proxy_warning()

        def _bg_prepare() -> None:
            try:
                if not self._lan_server.is_running():
                    self._lan_server.start()
                serve_path, disp_name, total_bytes, is_temp = LanTransferServer.package_share_paths(
                    valid, share_cache_dir=SHARE_CACHE_DIR
                )
                self._lan_async_bridge.share_packed.emit(seq, serve_path, disp_name, total_bytes, is_temp)
            except Exception as exc:
                self._lan_async_bridge.share_pack_failed.emit(seq, str(exc))

        threading.Thread(target=_bg_prepare, daemon=True).start()

    def _on_share_packed(self, seq: int, serve_path: str, disp_name: str, total_bytes: int, is_temp: bool) -> None:
        if seq != self._share_seq:
            if is_temp and serve_path and os.path.isfile(serve_path):
                try:
                    os.remove(serve_path)
                except Exception:
                    pass
            return

        ent = LanTransferServer.register_share(
            file_path=serve_path,
            display_name=disp_name,
            is_temp=is_temp,
            burn_after_read=True,
            on_download_cb=self._lan_async_bridge.share_downloaded.emit,
            on_state_cb=self._lan_async_bridge.share_state_changed.emit,
        )
        self._share_active_id = ent["id"]
        fm = QFontMetrics(self.lbl_share_file_info.font())
        info_txt = f"{disp_name} · {ent['size_str']}"
        self.lbl_share_file_info.setText(fm.elidedText(info_txt, Qt.TextElideMode.ElideMiddle, 210))
        self.lbl_share_file_info.setToolTip(info_txt)

        # 复用现有 cloudflared 后台隧道管线（已就绪则 0 延迟秒出直链；连接中则复用同一进程）
        snap = self._tunnel_mgr.get_snapshot()
        if snap.get("state") == "ready" and snap.get("alive") and snap.get("public_base_url"):
            if snap.get("prewarm_only"):
                self._tunnel_mgr.promote_prewarm(on_prepare_token=None)
            self._finalize_share_link(str(snap["public_base_url"]), edge_ready=bool(snap.get("edge_ready")))
            return

        if snap.get("state") in ("connecting", "downloading"):
            if snap.get("prewarm_only"):
                self._tunnel_mgr.promote_prewarm(on_prepare_token=None)
            self.lbl_share_link.setText("正在连接公网隧道...")
            self.lbl_share_tunnel_state.setText("连接中...")
            return

        ready, cf_path = CloudflaredTunnelManager.is_component_ready(self.config)
        if not ready:
            dlg = _CloudflaredDownloadConfirmDialog(
                target_path=cf_path,
                is_light=(self.config.theme_mode == "light"),
                accent_color=self.config.accent_color,
                parent=self,
            )
            if dlg.exec() != QDialog.DialogCode.Accepted:
                self._finalize_share_link(self._lan_server.get_url(with_token=False), edge_ready=True, is_lan_fallback=True)
                return
            self.lbl_share_link.setText("正在下载跨网穿透组件...")
            self._tunnel_mgr.start_download(cf_path)
            return

        self._tunnel_mgr.start_tunnel(
            cf_path,
            self._lan_server.port,
            on_prepare_token=None,
            cf_tunnel_token=str(getattr(self.config, "cf_tunnel_token", "") or "").strip(),
            cf_custom_domain=str(getattr(self.config, "cf_custom_domain", "") or "").strip(),
            silent_prewarm=False,
            origin_ip=str(getattr(self._lan_server, "ip", "") or ""),
        )

    def _on_share_pack_failed(self, seq: int, err_msg: str) -> None:
        if seq != self._share_seq:
            return
        self._on_share_stop_clicked(silent=True)
        self._toast.show_message(f"文件快传准备失败：{err_msg[:36]}", is_light=(self.config.theme_mode == "light"))

    def _finalize_share_link(self, base_url: str, edge_ready: bool = False, is_lan_fallback: bool = False) -> None:
        if not self._share_active_id:
            return
        self._share_tunnel_pending = False
        clean_base = str(base_url or "").split("?", 1)[0].rstrip("/")
        url = f"{clean_base}/s/{self._share_active_id}"
        self._share_public_url = url
        fm = QFontMetrics(self.lbl_share_link.font())
        self.lbl_share_link.setText(fm.elidedText(url, Qt.TextElideMode.ElideMiddle, 215))
        self.lbl_share_link.setToolTip(url)
        self.btn_share_copy.setEnabled(True)
        if is_lan_fallback:
            self.lbl_share_tunnel_state.setText("局域网直链")
            self.lbl_share_tunnel_state.setStyleSheet(f"color: {GREEN_ACCENT}; border: none; background: transparent;")
        elif edge_ready:
            self.lbl_share_tunnel_state.setText("直链已就绪")
            self.lbl_share_tunnel_state.setStyleSheet(f"color: {GREEN_ACCENT}; border: none; background: transparent;")
        else:
            self.lbl_share_tunnel_state.setText("激活边缘中...")
            self.lbl_share_tunnel_state.setStyleSheet(
                f"color: {self.config.accent_color}; border: none; background: transparent;"
            )
        if self._share_badge_state == "ready":
            self._set_share_badge("ready", "一次性有效 · 仅限首人下载（15分钟内有效）")
        if not self._share_auto_copied:
            self._share_auto_copied = True
            self._copy_text_to_clipboard_quiet(url)
            self._toast.show_message("已复制下载链接", is_light=(self.config.theme_mode == "light"), duration_ms=1600)

    def _copy_text_to_clipboard_quiet(self, text: str) -> None:
        cb = QApplication.clipboard()
        if cb is not None:
            self._clip_watcher.mark_self_write()
            try:
                cb.setText(text)
            finally:
                self._clip_watcher.sync_sequence()

    def _on_share_copy_clicked(self) -> None:
        if not self._share_public_url:
            return
        self._copy_text_to_clipboard_quiet(self._share_public_url)
        self._toast.show_message("已复制下载链接", is_light=(self.config.theme_mode == "light"), duration_ms=1500)

    def _on_share_downloaded(self, _share_id: str, _count: int, _burned: bool) -> None:
        # 实际状态流转与 2 秒自动复位由 _on_share_state_changed 统一接管
        return

    def _on_share_state_changed(self, share_id: str, state: str, _detail: str = "") -> None:
        if share_id != self._share_active_id:
            return
        if state == "DOWNLOADING":
            self._set_share_badge("downloading", "接收方正在下载（链接已锁定）...")
            self.lbl_share_tunnel_state.setText("下载中...")
            self.lbl_share_tunnel_state.setStyleSheet(
                f"color: {self.config.accent_color}; border: none; background: transparent;"
            )
            self.btn_share_copy.setEnabled(False)
        elif state == "COMPLETED":
            self._set_share_badge("completed", "对方已成功接收，链接已自动销毁")
            self.lbl_share_tunnel_state.setText("传输完成")
            self.lbl_share_tunnel_state.setStyleSheet(f"color: {GREEN_ACCENT}; border: none; background: transparent;")
            self.btn_share_copy.setEnabled(False)
            # 无其他活跃分享且未开连接手机时，自动关闭临时公网隧道
            if not self._phone_switch_on and not LanTransferServer.has_active_shares():
                if hasattr(self, "_tunnel_mgr"):
                    self._tunnel_mgr.stop_all()
            self._share_reset_timer.start(2000)
        elif state == "EXPIRED":
            self._toast.show_message("分享链接已超过 15 分钟自动过期销毁", is_light=(self.config.theme_mode == "light"), duration_ms=2200)
            self._on_share_stop_clicked(silent=True)

    def _on_share_stop_clicked(self, silent: bool = False) -> None:
        self._share_reset_timer.stop()
        self._share_seq += 1
        if self._share_active_id:
            LanTransferServer.unregister_share(self._share_active_id)
            self._share_active_id = ""
        self._share_public_url = ""
        self._share_auto_copied = False
        self._share_tunnel_pending = False
        self._share_badge_state = "ready"

        self.share_active_box.setVisible(False)
        self.lbl_share_proxy_warn.setVisible(False)
        self.lbl_share_proxy_warn.setText("")
        self.share_idle_box.setVisible(True)
        self.btn_share_copy.setEnabled(False)

        # 若【连接手机】未开启且无其他活跃分享，则同步关闭临时公网隧道与本地服务释放资源
        if not self._phone_switch_on and not LanTransferServer.has_active_shares():
            if hasattr(self, "_tunnel_mgr"):
                self._tunnel_mgr.stop_all()
            if hasattr(self, "_lan_server") and self._lan_server.is_running():
                self._lan_server.stop()
        if not silent:
            self._toast.show_message("已停止文件分享并清理缓存", is_light=(self.config.theme_mode == "light"), duration_ms=1500)

    # ------------------------------------------------------------------
    # 工作模式：连接手机（局域网 / 互联网跨网双向收发）
    # ------------------------------------------------------------------
    def _update_lan_card_state(self) -> None:
        running = self._phone_switch_on and self._lan_server.is_running()
        starting = self._phone_switch_on and bool(getattr(self, "_lan_starting", False)) and not self._lan_server.is_running()
        active = running or starting
        is_light = self.config.theme_mode == "light"
        muted = "#8B8C98" if is_light else "#71717A"
        if running:
            net_tok = self._lan_server.get_internet_token()
            if net_tok:
                self.lbl_lan_status.setText("互联网运行中")
            else:
                self.lbl_lan_status.setText(f"运行中 · {self._lan_server.get_base_url()}")
            self.lbl_lan_status.setStyleSheet(f"color: {GREEN_ACCENT};")
        elif starting:
            self.lbl_lan_status.setText("正在获取局域网地址...")
            self.lbl_lan_status.setStyleSheet(f"color: {self.config.accent_color};")
        else:
            self.lbl_lan_status.setText("苹果、安卓无需安装扫码直连")
            self.lbl_lan_status.setStyleSheet(f"color: {muted};")
        self.btn_lan_manage.setVisible(active)
        if hasattr(self, "lan_toggle_switch"):
            self.lan_toggle_switch.set_checked(active, animate=True)

    def _on_lan_mode_changed(self, mode: str, _url: str, _token: str) -> None:
        self._update_lan_card_state()
        if mode != "internet" and not self._is_internet_mode_active():
            if getattr(self, "_active_cache_dlg", None) is not None:
                try:
                    self._active_cache_dlg.clear_internet_blocked_tip()
                except RuntimeError:
                    pass

    def _on_lan_toggled(self, checked: bool) -> None:
        if checked:
            self._on_lan_start_clicked()
        else:
            self._on_lan_stop_clicked()

    def _maybe_prewarm_tunnel(self) -> None:
        """开启连接手机后在后台守护线程静默预热 cloudflared 隧道（仅组件已就绪、未开代理/TUN且无活跃隧道时触发），切换互联网时 0.1 秒瞬开。"""
        if not self._lan_server.is_running():
            return
        if self._tunnel_mgr.is_active():
            return
        if detect_proxy_or_tun():
            return
        ready, cf_path = CloudflaredTunnelManager.is_component_ready(self.config)
        if not ready:
            return
        self._tunnel_mgr.start_tunnel(
            cf_path,
            self._lan_server.port,
            on_prepare_token=None,
            cf_tunnel_token=str(getattr(self.config, "cf_tunnel_token", "") or "").strip(),
            cf_custom_domain=str(getattr(self.config, "cf_custom_domain", "") or "").strip(),
            silent_prewarm=True,
            origin_ip=str(getattr(self._lan_server, "ip", "") or ""),
        )

    def _on_lan_start_clicked(self) -> None:
        self._phone_switch_on = True
        if self._lan_server.is_running():
            self._lan_starting = False
            self._update_lan_card_state()
            self._on_lan_manage_clicked()
            self._maybe_prewarm_tunnel()
            return

        if self._lan_starting:
            self._open_lan_manage_dialog(initial_loading=True)
            return

        # 零延迟秒开管理窗口：立即弹出并显示旋转加载圈，网卡 IP 枚举 + 0.0.0.0 服务启动 + 二维码 PIL 渲染全部异步化
        self._lan_starting = True
        self._lan_start_seq += 1
        seq = self._lan_start_seq
        self._update_lan_card_state()
        self._open_lan_manage_dialog(initial_loading=True)

        def _bg_start_lan() -> None:
            try:
                self._lan_server.start()
                lan_url = self._lan_server.get_url()
                qr_pil = LanTransferDialog._make_qr_pil_image(lan_url)
                self._lan_async_bridge.lan_ready.emit(seq, lan_url, qr_pil)
            except Exception as exc:
                self._lan_async_bridge.lan_failed.emit(seq, str(exc))

        threading.Thread(target=_bg_start_lan, daemon=True).start()

    def _on_lan_async_ready(self, seq: int, lan_url: str, qr_pil) -> None:
        if seq != self._lan_start_seq:
            # 启动期间用户已手动关闭开关，若无活跃文件快传则清理刚起的后台服务
            if not self._share_active_id:
                self._lan_server.stop()
            return
        self._lan_starting = False
        self._update_lan_card_state()
        if self._active_lan_dlg is not None:
            try:
                self._active_lan_dlg.on_lan_server_ready(lan_url, qr_pil)
            except RuntimeError:
                pass
        # 局域网就绪后立即后台静默预热互联网隧道
        self._maybe_prewarm_tunnel()

    def _on_lan_async_failed(self, seq: int, err_msg: str) -> None:
        if seq != self._lan_start_seq:
            return
        self._lan_starting = False
        self._phone_switch_on = False
        if self._active_lan_dlg is not None:
            try:
                if self._active_lan_dlg.isVisible():
                    self._active_lan_dlg.close()
            except Exception:
                pass
        self._update_lan_card_state()
        self._toast.show_message(f"连接手机启动失败：{err_msg}", is_light=(self.config.theme_mode == "light"))

    def _on_global_cf_download_finished(self, exe_path: str) -> None:
        if self._active_lan_dlg is None and self._lan_server.is_running():
            prep_cb = self._lan_server.set_internet_token if self._phone_switch_on else None
            self._tunnel_mgr.start_tunnel(
                exe_path,
                self._lan_server.port,
                on_prepare_token=prep_cb,
                cf_tunnel_token=str(getattr(self.config, "cf_tunnel_token", "") or "").strip(),
                cf_custom_domain=str(getattr(self.config, "cf_custom_domain", "") or "").strip(),
                silent_prewarm=False,
                origin_ip=str(getattr(self._lan_server, "ip", "") or ""),
            )

    def _on_global_tunnel_ready(self, public_base_url: str, token: str, ready_tip: str = "") -> None:
        if self._share_active_id:
            edge_ok = ready_tip == CloudflaredTunnelManager.EDGE_READY_TIP or bool(
                self._tunnel_mgr.get_snapshot().get("edge_ready")
            )
            self._finalize_share_link(public_base_url, edge_ready=edge_ok)
        if self._tunnel_mgr.is_prewarm_only():
            return
        if self._phone_switch_on and (
            self._active_lan_dlg is None or getattr(self._active_lan_dlg, "_mode", "lan") == "internet"
        ):
            self._lan_server.set_internet_token(token)
        self._update_lan_card_state()

    def _on_global_edge_state_changed(self, state_kind: str, _text: str) -> None:
        if self._share_active_id and state_kind == "ready" and hasattr(self, "lbl_share_tunnel_state"):
            self.lbl_share_tunnel_state.setText("直链已就绪")
            self.lbl_share_tunnel_state.setStyleSheet(f"color: {GREEN_ACCENT}; border: none; background: transparent;")

    def _on_global_tunnel_failed(self, err_msg: str) -> None:
        if self._share_active_id:
            self._share_tunnel_pending = False
            self.lbl_share_tunnel_state.setText("连接超时")
            self.lbl_share_tunnel_state.setStyleSheet(f"color: {INVALID_RED}; border: none; background: transparent;")
            fm = QFontMetrics(self.lbl_share_link.font())
            self.lbl_share_link.setText(fm.elidedText(err_msg, Qt.TextElideMode.ElideRight, 215))
            self.lbl_share_link.setToolTip(err_msg)
        self._lan_server.set_internet_token("")
        self._update_lan_card_state()
        if getattr(self, "_active_cache_dlg", None) is not None and not self._is_internet_mode_active():
            try:
                self._active_cache_dlg.clear_internet_blocked_tip()
            except RuntimeError:
                pass

    def _open_lan_manage_dialog(self, initial_loading: bool = False) -> None:
        if self._active_lan_dlg is not None and self._active_lan_dlg.isVisible():
            self._active_lan_dlg.showNormal()
            self._active_lan_dlg.raise_()
            self._active_lan_dlg.activateWindow()
            return
        dlg = LanTransferDialog(
            server=self._lan_server,
            config=self.config,
            theme_mode=self.config.theme_mode,
            accent_color=self.config.accent_color,
            on_copy_url=self._copy_lan_url,
            on_share_clipboard=self._share_current_clipboard_to_lan,
            on_mode_changed=self._on_lan_mode_changed,
            on_toast=lambda msg: self._toast.show_message(msg, is_light=(self.config.theme_mode == "light")),
            on_request_screenshot=self._on_lan_screenshot_clicked,
            tunnel_mgr=self._tunnel_mgr,
            initial_loading=initial_loading,
            parent=self,
        )
        dlg.setModal(False)
        dlg.finished.connect(lambda _res: setattr(self, "_active_lan_dlg", None))
        self._active_lan_dlg = dlg
        dlg.adjustSize()
        self.position_beside_main(dlg, dlg.width(), dlg.height(), gap=10)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_lan_manage_clicked(self) -> None:
        if not self._phone_switch_on:
            return
        if not self._lan_server.is_running() and not self._lan_starting:
            return
        self._open_lan_manage_dialog(initial_loading=not self._lan_server.is_running())

    def _on_lan_stop_clicked(self) -> None:
        self._lan_start_seq += 1
        self._lan_starting = False
        self._phone_switch_on = False
        if self._active_lan_dlg is not None:
            try:
                if self._share_active_id:
                    # 存在活跃的文件快传时仅关闭管理弹窗并清空互传校验码，不中断分享直链
                    self._active_lan_dlg._detach_tunnel_signals()
                else:
                    self._active_lan_dlg.cleanup_tunnel()
                if self._active_lan_dlg.isVisible():
                    self._active_lan_dlg.close()
            except Exception:
                pass
        self._lan_server.set_internet_token("")
        if not self._share_active_id:
            if hasattr(self, "_tunnel_mgr"):
                self._tunnel_mgr.stop_all()
            _cleanup_all_cloudflared_procs()
            self._lan_server.stop()
        self._update_lan_card_state()
        if getattr(self, "_active_cache_dlg", None) is not None and not self._is_internet_mode_active():
            try:
                self._active_cache_dlg.clear_internet_blocked_tip()
            except RuntimeError:
                pass
        self._toast.show_message("已关闭连接手机", is_light=(self.config.theme_mode == "light"), duration_ms=1500)

    def _copy_lan_url(self, url: str) -> None:
        cb = QApplication.clipboard()
        if cb is not None:
            self._clip_watcher.mark_self_write()
            try:
                cb.setText(url)
            finally:
                self._clip_watcher.sync_sequence()
        self._toast.show_message("✓ 已复制互传网址", is_light=(self.config.theme_mode == "light"), duration_ms=1500)

    def _share_current_clipboard_to_lan(self) -> None:
        cb = QApplication.clipboard()
        if cb is None:
            return
        mime = cb.mimeData()
        if mime is None:
            return
        if mime.hasUrls():
            paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            for p in paths:
                self._lan_server.add_shared_file(p)
        elif mime.hasText() and mime.text().strip():
            self._lan_server.add_shared_text(mime.text())

    def _send_clip_entry_to_phone(self, entry: dict) -> None:
        etype = str(entry.get("type") or "text")
        if etype in ("text", "link"):
            self._lan_server.add_shared_text(str(entry.get("content") or ""))
        elif etype == "image":
            img_p = str(entry.get("image_path") or "")
            if img_p and os.path.isfile(img_p):
                self._lan_server.add_shared_file(img_p)
        elif etype == "file":
            for fp in (entry.get("file_paths") or []):
                self._lan_server.add_shared_file(str(fp))
        if not self._lan_server.is_running():
            self._on_lan_start_clicked()
        else:
            if self._active_lan_dlg is not None:
                self._active_lan_dlg.refresh_shared_list()
            self._toast.show_message("✓ 已共享到手机", is_light=(self.config.theme_mode == "light"), duration_ms=1500)

    def _on_lan_text_received(self, text: str) -> None:
        cb = QApplication.clipboard()
        if cb is not None:
            self._clip_watcher.mark_self_write()
            try:
                cb.setText(text)
            finally:
                self._clip_watcher.sync_sequence()
        now = datetime.now()
        trimmed = text.strip()
        is_link = trimmed.lower().startswith(("http://", "https://"))
        entry = {
            "id": uuid.uuid4().hex[:12],
            "type": "link" if is_link else "text",
            "preview": " ".join(trimmed.splitlines()).strip(),
            "content": trimmed if is_link else text,
            "image_path": "",
            "image_hash": "",
            "file_paths": [],
            "time_str": now.strftime("%H:%M:%S"),
            "date_str": now.strftime("%Y-%m-%d"),
            "ts": time.time(),
        }
        self._clip_items = ClipboardHistoryStore.add_or_bump(self._clip_items, entry)
        self._rebuild_clipboard_list()
        if self._active_lan_dlg is not None and self._active_lan_dlg.isVisible():
            self._active_lan_dlg.refresh_chat_messages(force=True)
        self._toast.show_message("📱 已接收手机发送的文本", is_light=(self.config.theme_mode == "light"), duration_ms=2000)

    def _on_lan_file_received(self, saved_path: str) -> None:
        """异步后台生成聊天缩略图并回推主线程更新剪贴板与 UI，绝不阻塞手机上传 HTTP 响应。"""
        def _bg_post() -> None:
            ext = os.path.splitext(saved_path)[1].lower()
            is_img = ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
            pil_thumb = None
            if is_img and os.path.isfile(saved_path):
                try:
                    from PIL import Image, ImageOps
                    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                    with Image.open(saved_path) as im:
                        im = ImageOps.exif_transpose(im)
                        im.thumbnail((162, 136), resample)
                        pil_thumb = im.convert("RGBA").copy()
                except Exception:
                    pil_thumb = None
            self._lan_async_bridge.file_post_ready.emit(saved_path, pil_thumb, is_img)

        threading.Thread(target=_bg_post, daemon=True).start()

    def _on_lan_file_post_ready(self, saved_path: str, pil_thumb, is_img: bool) -> None:
        now = datetime.now()
        if is_img and os.path.isfile(saved_path):
            # 异步收到图片后自动写入 Windows 系统剪贴板（防剪贴板监听器回环重复记录）
            try:
                cb = QApplication.clipboard()
                if cb is not None:
                    qimg = QImage(saved_path)
                    if not qimg.isNull():
                        self._clip_watcher.mark_self_write()
                        try:
                            cb.setImage(qimg)
                        finally:
                            self._clip_watcher.sync_sequence()
            except Exception:
                pass

        entry = {
            "id": uuid.uuid4().hex[:12],
            "type": "image" if is_img else "file",
            "preview": f"[手机图片] {os.path.basename(saved_path)}" if is_img else os.path.basename(saved_path),
            "content": "",
            "image_path": saved_path if is_img else "",
            "image_hash": "",
            "file_paths": [saved_path],
            "time_str": now.strftime("%H:%M:%S"),
            "date_str": now.strftime("%Y-%m-%d"),
            "ts": time.time(),
        }
        self._clip_items = ClipboardHistoryStore.add_or_bump(self._clip_items, entry)
        self._rebuild_clipboard_list()
        if self._active_lan_dlg is not None and self._active_lan_dlg.isVisible():
            if pil_thumb is not None:
                self._active_lan_dlg.cache_image_thumbnail(saved_path, pil_thumb)
            self._active_lan_dlg.refresh_chat_messages(force=True)
        self._toast.show_message(
            f"📱 已接收手机{'图片' if is_img else '文件'}：{os.path.basename(saved_path)}",
            is_light=(self.config.theme_mode == "light"),
            duration_ms=2000,
        )

    # ------------------------------------------------------------------
    # 工作模式：全屏截图识字 (Windows 原生 OCR) / 截图传手机 & 实时放大镜屏幕取色
    # ------------------------------------------------------------------
    def prepare_windows_for_capture(self, wait: bool = True) -> list[QWidget]:
        """截图/OCR/取色统一窗口隐藏调度器。
        - keep_window_on_capture == True：直接跳过任何隐藏操作，保留主窗口及日历、连接手机等全部子窗口原始显示状态；
        - keep_window_on_capture == False：记录并统一隐藏主窗口及所有可见 Toplevel 子窗口（日历、管理窗、关于、缓存等）。
        """
        self._capture_hidden_windows: list[QWidget] = []
        if bool(getattr(self.config, "keep_window_on_capture", False)):
            return []

        skip_types = (ToastPopup, _ClipHoverPreviewPopup, VersionMenuPopup, ScreenCaptureOverlay, QMenu)
        hidden_list: list[QWidget] = []
        if self.isVisible() and not self.isMinimized():
            hidden_list.append(self)

        for w in QApplication.topLevelWidgets():
            if w is self or isinstance(w, skip_types):
                continue
            try:
                if w.isVisible() and not w.isMinimized() and w.width() > 2 and w.height() > 2:
                    hidden_list.append(w)
            except RuntimeError:
                continue

        for w in hidden_list:
            try:
                w.hide()
                w.update()
            except RuntimeError:
                pass

        self._capture_hidden_windows = hidden_list
        if hidden_list:
            QApplication.processEvents()
            if wait:
                time.sleep(0.15)
        return list(hidden_list)

    def restore_windows_after_capture(self, hidden_list: list[QWidget] | None = None) -> None:
        """截图/OCR/取色完成或 ESC 取消后按记录精确恢复先前隐藏的窗口；若未隐藏任何窗口则零闪烁直接返回。"""
        targets = list(self._capture_hidden_windows) if hidden_list is None else list(hidden_list)
        self._capture_hidden_windows = []
        if not targets:
            return
        for w in targets:
            try:
                w.showNormal()
                w.raise_()
            except RuntimeError:
                pass
        try:
            last_w = targets[-1]
            last_w.activateWindow()
        except RuntimeError:
            pass

    def _restore_windows_after_capture(self) -> None:
        self.restore_windows_after_capture()

    @staticmethod
    def _capture_virtual_desktop_gdi(vx: int, vy: int, vw: int, vh: int):
        """使用原生 Win32 GDI BitBlt 抓取全虚拟桌面物理像素位图，彻底规避多屏混合 DPI 缩放错位。"""
        from PIL import Image
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, vw, vh)
        old_bmp = gdi32.SelectObject(hdc_mem, hbmp)
        SRCCOPY = 0x00CC0020
        CAPTUREBLT = 0x40000000
        ok_blt = gdi32.BitBlt(hdc_mem, 0, 0, vw, vh, hdc_screen, vx, vy, SRCCOPY | CAPTUREBLT)

        class _BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32),
                ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]

        bmi = _BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.biWidth = vw
        bmi.biHeight = -vh
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf = ctypes.create_string_buffer(vw * vh * 4)
        scanlines = gdi32.GetDIBits(hdc_mem, hbmp, 0, vh, buf, ctypes.byref(bmi), 0)

        gdi32.SelectObject(hdc_mem, old_bmp)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)
        if not ok_blt or scanlines <= 0:
            from PIL import ImageGrab
            return ImageGrab.grab(all_screens=True)
        return Image.frombuffer("RGB", (vw, vh), buf, "raw", "BGRX", 0, 1)

    @staticmethod
    def _capture_monitors_mss() -> list[tuple[tuple[int, int, int, int], object]]:
        """使用 mss 逐物理显示器截取独立高清原图，避免跨屏混合 DPI DWM 拉伸。"""
        import mss
        from PIL import Image

        captures: list[tuple[tuple[int, int, int, int], object]] = []
        with mss.mss() as sct:
            monitors = sct.monitors[1:] if len(sct.monitors) > 1 else sct.monitors[:1]
            for mon in monitors:
                left = int(mon["left"])
                top = int(mon["top"])
                width = int(mon["width"])
                height = int(mon["height"])
                if width <= 0 or height <= 0:
                    continue
                sct_img = sct.grab(mon)
                pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                captures.append(((left, top, width, height), pil_img))
        return captures

    def _close_all_overlays(self) -> None:
        overlays = list(getattr(self, "_active_overlays", []))
        self._active_overlays = []
        for ov in overlays:
            try:
                ov.blockSignals(True)
                ov.close()
            except RuntimeError:
                pass

    def _launch_screen_overlay(self, mode: str) -> None:
        if getattr(self, "_active_overlays", []) or getattr(self, "_capture_pending", False):
            return
        hidden = self.prepare_windows_for_capture(wait=False)
        if hidden:
            self._capture_pending = True
            QTimer.singleShot(150, lambda m=mode: self._finish_launch_screen_overlay(m))
        else:
            self._finish_launch_screen_overlay(mode)

    def _finish_launch_screen_overlay(self, mode: str) -> None:
        self._capture_pending = False
        if getattr(self, "_active_overlays", []):
            return
        try:
            captures = self._capture_monitors_mss()
            if not captures:
                vx, vy, vw, vh = _get_virtual_screen_rect()
                if sys.platform == "win32" and vw > 0 and vh > 0:
                    captures = [((vx, vy, vw, vh), self._capture_virtual_desktop_gdi(vx, vy, vw, vh))]
                else:
                    from PIL import ImageGrab
                    img = ImageGrab.grab(all_screens=True)
                    captures = [((0, 0, img.width, img.height), img)]
        except Exception as exc:
            self.restore_windows_after_capture()
            self._toast.show_message(f"截屏失败：{exc}", is_light=(self.config.theme_mode == "light"))
            return

        cache_dir = CacheManager.get_effective_cache_dir(self.config)
        target_dir = os.path.join(cache_dir, "clipboard_cache") if mode == "transfer" else cache_dir
        cur_pos = _get_physical_cursor_pos()
        focus_ov: ScreenCaptureOverlay | None = None

        for mon_rect, pil_img in captures:
            ov = ScreenCaptureOverlay(
                mode=mode,
                pil_img=pil_img,
                cache_dir=target_dir,
                accent_color=self.config.accent_color,
                virt_rect=mon_rect,
            )
            ov.ocr_captured.connect(self._on_ocr_captured)
            ov.transfer_captured.connect(self._on_transfer_screenshot_captured)
            ov.color_picked.connect(self._on_color_picked)
            ov.cancelled.connect(self._on_overlay_cancelled)

            def _on_ov_destroyed(_obj=None, ref=ov) -> None:
                if ref in self._active_overlays:
                    self._active_overlays.remove(ref)
                if not self._active_overlays:
                    self.restore_windows_after_capture()

            ov.destroyed.connect(_on_ov_destroyed)
            self._active_overlays.append(ov)
            if cur_pos is not None:
                vx, vy, vw, vh = mon_rect
                if vx <= cur_pos[0] < vx + vw and vy <= cur_pos[1] < vy + vh:
                    focus_ov = ov

        for ov in self._active_overlays:
            ov.show()
            ov.raise_()
        target_focus = focus_ov or (self._active_overlays[0] if self._active_overlays else None)
        if target_focus is not None:
            target_focus.activateWindow()

    def _on_lan_screenshot_clicked(self) -> None:
        self._launch_screen_overlay("transfer")

    def _on_transfer_screenshot_captured(self, shot_path: str) -> None:
        self._close_all_overlays()
        self.restore_windows_after_capture()
        if os.path.isfile(shot_path):
            self._lan_server.add_shared_file(shot_path)
            if self._active_lan_dlg is not None:
                self._active_lan_dlg.refresh_chat_messages(force=True)
            self._toast.show_message("✓ 已发送截图到手机", is_light=(self.config.theme_mode == "light"), duration_ms=1600)

    def _on_ocr_clicked(self) -> None:
        self._launch_screen_overlay("ocr")

    def _on_picker_clicked(self) -> None:
        self._launch_screen_overlay("picker")

    def _on_overlay_cancelled(self) -> None:
        self._close_all_overlays()
        self.restore_windows_after_capture()

    def _on_ocr_captured(self, temp_path: str) -> None:
        self._close_all_overlays()
        self.restore_windows_after_capture()
        self._toast.show_message("正在识别文字...", is_light=(self.config.theme_mode == "light"), duration_ms=1500)

        def _worker() -> None:
            text = ""
            try:
                text = _run_windows_ocr(temp_path)
            except Exception:
                text = ""
            finally:
                if os.path.isfile(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
            self._ocr_bridge.finished.emit(text, temp_path)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_ocr_done(self, text: str, _temp_path: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned:
            self._toast.show_message("未识别到有效文字", is_light=(self.config.theme_mode == "light"), duration_ms=1800)
            return
        self._write_text_to_clipboard_and_history(cleaned)
        self._toast.show_message("✓ 已识别并复制文字", is_light=(self.config.theme_mode == "light"), duration_ms=1800)

    def _on_color_picked(self, hex_color: str) -> None:
        self._close_all_overlays()
        self.restore_windows_after_capture()
        self._write_text_to_clipboard_and_history(hex_color)
        self._toast.show_message(f"✓ 已复制色值 {hex_color}", is_light=(self.config.theme_mode == "light"), duration_ms=1800)

    def _write_text_to_clipboard_and_history(self, text: str) -> None:
        cb = QApplication.clipboard()
        if cb is not None:
            self._clip_watcher.mark_self_write()
            try:
                cb.setText(text)
            finally:
                self._clip_watcher.sync_sequence()
        now = datetime.now()
        trimmed = text.strip()
        is_link = trimmed.lower().startswith(("http://", "https://"))
        entry = {
            "id": uuid.uuid4().hex[:12],
            "type": "link" if is_link else "text",
            "preview": " ".join(trimmed.splitlines()).strip(),
            "content": trimmed if is_link else text,
            "image_path": "",
            "image_hash": "",
            "file_paths": [],
            "time_str": now.strftime("%H:%M:%S"),
            "date_str": now.strftime("%Y-%m-%d"),
            "ts": time.time(),
        }
        self._clip_items = ClipboardHistoryStore.add_or_bump(self._clip_items, entry)
        self._rebuild_clipboard_list()

    def _toggle_always_on_top(self) -> None:
        self.config.always_on_top = not self.config.always_on_top
        self.config.save()
        self.btn_pin.set_active(self.config.always_on_top)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.config.always_on_top)
        self.show()

    def _get_current_quote_pool(self, now: datetime = None) -> tuple[str, list[str]]:
        if self._cloud_cfg.get("top_enabled") is True:
            raw_msgs = self._cloud_cfg.get("top_messages")
            if isinstance(raw_msgs, list):
                clean_msgs = [str(m).strip() for m in raw_msgs if str(m).strip()]
                if clean_msgs:
                    return "cloud_top", clean_msgs

        if now is None:
            now = datetime.now()
        _, end_dt = TimeCalculator.get_work_datetimes(now, self.config)
        remain_sec = (end_dt - now).total_seconds()

        if 0 < remain_sec <= 300:
            return "last_5m", LAST_5M_QUOTES
        if 300 < remain_sec <= 1800:
            return "last_30m", LAST_30M_QUOTES
        if now.hour < 12:
            return "morning", MORNING_QUOTES
        return "afternoon", AFTERNOON_QUOTES

    def _sync_initial_quote(self) -> None:
        pool_key, pool = self._get_current_quote_pool()
        self._active_quote_pool_key = pool_key
        self._quote_idx = 0
        self.status_ticker.set_text_immediate(pool[0])

    def _advance_status_quote(self, animate: bool = True) -> None:
        pool_key, pool = self._get_current_quote_pool()
        if pool_key != self._active_quote_pool_key:
            self._active_quote_pool_key = pool_key
            self._quote_idx = 0
        else:
            self._quote_idx = (self._quote_idx + 1) % len(pool)
        text = pool[self._quote_idx]
        if animate:
            self.status_ticker.slide_to(text)
        else:
            self.status_ticker.set_text_immediate(text)

    @staticmethod
    def _now_ms() -> int:
        return int(time.monotonic() * 1000)

    def _try_staggered_refresh(
        self,
        timer: QTimer,
        interval_ms: int,
        other_last_ms: int,
        advance_fn,
    ) -> int | None:
        """若距离另一状态栏上次刷新不足 QUOTE_MIN_GAP_MS，则延后本次刷新，避免同时滚动。"""
        now = self._now_ms()
        elapsed = now - other_last_ms
        if other_last_ms > 0 and elapsed < QUOTE_MIN_GAP_MS:
            timer.start(QUOTE_MIN_GAP_MS - elapsed)
            return None
        advance_fn()
        if timer.interval() != interval_ms:
            timer.start(interval_ms)
        return now

    def _on_quote_timer(self) -> None:
        self._last_status_quote_ms = self._now_ms()
        self._advance_status_quote(animate=True)
        interval_ms = self._get_status_quote_interval_ms()
        if self.quote_timer.interval() != interval_ms:
            self.quote_timer.start(interval_ms)

    def _on_quote_clicked(self) -> None:
        self._last_status_quote_ms = self._now_ms()
        self.quote_timer.start(self._get_status_quote_interval_ms())
        self._advance_status_quote(animate=True)

    def _toggle_settings_page(self) -> None:
        if self.stack.currentIndex() == 0:
            self._load_config_into_form()
            self.stack.setCurrentIndex(1)
            self.btn_gear.set_active(True)
            QTimer.singleShot(0, self._position_all_red_dots)
        else:
            self._close_settings_page()

    def _close_settings_page(self) -> None:
        self.stack.setCurrentIndex(0)
        self.btn_gear.set_active(False)

    def _on_close_ask_toggled(self, checked: bool) -> None:
        if checked and self.chk_close_to_tray.isChecked():
            self.chk_close_to_tray.setChecked(False)

    def _on_close_tray_toggled(self, checked: bool) -> None:
        if checked and self.chk_close_ask.isChecked():
            self.chk_close_ask.setChecked(False)

    def _load_config_into_form(self) -> None:
        sh, sm = TimeCalculator.parse_hm(self.config.work_start, (9, 30))
        eh, em = TimeCalculator.parse_hm(self.config.work_end, (18, 30))
        lsh, lsm = TimeCalculator.parse_hm(self.config.lunch_start, (12, 0))
        leh, lem = TimeCalculator.parse_hm(self.config.lunch_end, (13, 0))
        self.edit_work_start.setTime(QTime(sh, sm))
        self.edit_work_end.setTime(QTime(eh, em))
        self.edit_lunch_start.setTime(QTime(lsh, lsm))
        self.edit_lunch_end.setTime(QTime(leh, lem))
        self.spin_payday.setValue(self.config.payday)

        if self.config.work_mode == "custom":
            self.rb_custom.setChecked(True)
        else:
            self.rb_double.setChecked(True)

        self._temp_custom_rest = {
            "custom_rest_dates": list(self.config.custom_rest_dates),
            "custom_fixed_weekdays": list(self.config.custom_fixed_weekdays),
            "custom_monthly_selected_days_enabled": self.config.custom_monthly_selected_days_enabled,
        }

        self.chk_holiday_irrelevant.setChecked(self.config.holiday_irrelevant)
        self.chk_auto_start.setChecked(self.config.auto_start)
        behavior = getattr(self.config, "close_behavior", "ask")
        self.chk_close_ask.setChecked(behavior == "ask")
        self.chk_close_to_tray.setChecked(behavior == "tray")
        self.chk_auto_update.blockSignals(True)
        self.chk_auto_update.setChecked(bool(getattr(self.config, "auto_update", False)))
        self.chk_auto_update.blockSignals(False)
        self.chk_clip_enabled.setChecked(bool(getattr(self.config, "clipboard_history_enabled", True)))
        self.chk_clip_keep_next_day.setChecked(bool(getattr(self.config, "clipboard_keep_next_day", False)))
        self.chk_keep_window_on_capture.blockSignals(True)
        self.chk_keep_window_on_capture.setChecked(bool(getattr(self.config, "keep_window_on_capture", False)))
        self.chk_keep_window_on_capture.blockSignals(False)
        self.chk_keep_children_on_hide.blockSignals(True)
        self.chk_keep_children_on_hide.setChecked(bool(getattr(self.config, "keep_children_on_hide", False)))
        self.chk_keep_children_on_hide.blockSignals(False)

        if self.config.theme_mode == "light":
            self.rb_theme_light.setChecked(True)
        else:
            self.rb_theme_dark.setChecked(True)

        if self.config.accent_color.upper() in (GREEN_ACCENT, "#00E676"):
            self.rb_green.setChecked(True)
        else:
            self.rb_orange.setChecked(True)

    def _save_settings(self) -> None:
        self.config.work_start = self.edit_work_start.time().toString("HH:mm")
        self.config.work_end = self.edit_work_end.time().toString("HH:mm")
        self.config.lunch_start = self.edit_lunch_start.time().toString("HH:mm")
        self.config.lunch_end = self.edit_lunch_end.time().toString("HH:mm")
        self.config.payday = int(self.spin_payday.value())

        self.config.work_mode = "custom" if self.rb_custom.isChecked() else "double"
        self.config.custom_rest_dates = list(self._temp_custom_rest["custom_rest_dates"])
        self.config.custom_fixed_weekdays = list(self._temp_custom_rest["custom_fixed_weekdays"])
        self.config.custom_monthly_selected_days_enabled = bool(
            self._temp_custom_rest["custom_monthly_selected_days_enabled"]
        )

        self.config.holiday_irrelevant = self.chk_holiday_irrelevant.isChecked()
        self.config.auto_start = self.chk_auto_start.isChecked()
        self.config.clipboard_history_enabled = self.chk_clip_enabled.isChecked()
        self.config.clipboard_keep_next_day = self.chk_clip_keep_next_day.isChecked()
        if getattr(self.config, "app_mode", "fish") == "work":
            self.config.keep_window_on_capture = self.chk_keep_window_on_capture.isChecked()
        self.config.keep_children_on_hide = self.chk_keep_children_on_hide.isChecked()
        self._sync_children_win32_ownership()
        if not self.config.clipboard_keep_next_day:
            self._clip_items, changed = ClipboardHistoryStore.prune_non_today(self._clip_items)
            if changed:
                ClipboardHistoryStore.save(self._clip_items)
                self._rebuild_clipboard_list()
        if self.chk_close_to_tray.isChecked():
            self.config.close_behavior = "tray"
        elif self.chk_close_ask.isChecked():
            self.config.close_behavior = "ask"
        else:
            self.config.close_behavior = "exit"
        self.config.theme_mode = "light" if self.rb_theme_light.isChecked() else "dark"
        self.config.accent_color = GREEN_ACCENT if self.rb_green.isChecked() else ORANGE_ACCENT

        self.config.save()
        set_windows_autostart(self.config.auto_start)
        self._apply_theme()
        self._rebuild_holiday_rows()
        self._refresh_metrics()

        self._toast.show_message(
            "设置已保存并生效",
            is_light=(self.config.theme_mode == "light"),
        )

    @staticmethod
    def _format_compact_pct(pct: float) -> str:
        if pct >= 99.95:
            return "100%"
        return f"{pct:.1f}%"

    @staticmethod
    def _format_compact_work_cd(metrics) -> tuple[str, str]:
        txt = str(metrics.countdown_text or "")
        if "今日休息" in txt:
            return "下班", "今日休息"
        if "已下班" in txt:
            return "下班", "已下班"
        if "距离上班" in txt:
            return "上班", metrics.remain_hms
        return "下班", metrics.remain_hms

    @staticmethod
    def _format_compact_weekend_cd(text: str, is_custom: bool) -> tuple[str, str]:
        tag = "休假" if is_custom else "周末"
        s = str(text or "")
        if "假期中" in s or "休假中" in s:
            return tag, "休假中"
        if "已下班" in s:
            return tag, "已开启"
        if "暂未设置" in s:
            return tag, "未设置"
        m = re.search(r"(\d+)天\s*(\d{2}:\d{2})", s)
        if m:
            return tag, f"{m.group(1)}天{m.group(2)}"
        m2 = re.search(r"(\d{2}:\d{2}:\d{2})", s)
        if m2:
            return tag, m2.group(1)
        return tag, s[:10]

    @staticmethod
    def _format_compact_payday_cd(text: str) -> str:
        s = str(text or "")
        if "今日发薪" in s:
            return "今日发薪"
        m = re.search(r"(\d+)天\s*\((\d+月\d+日)\)", s)
        if m:
            return f"{m.group(1)}天 · {m.group(2).replace('月', '/').replace('日', '')}"
        m2 = re.search(r"(\d+)天", s)
        if m2:
            return f"{m2.group(1)}天"
        return s[:10]

    # ------------------------------------------------------------------
    # 定时刷新逻辑
    # ------------------------------------------------------------------
    def _toggle_mini_mode(self) -> None:
        self._mini_mode = not self._mini_mode
        if self._mini_mode:
            self.top_bar_widget.setVisible(False)
            self.stack.setVisible(False)
            self.mini_bar_widget.setVisible(True)
            self._root_layout.setContentsMargins(10, 6, 10, 6)
            self.setFixedSize(244, 50)
        else:
            self.mini_bar_widget.setVisible(False)
            self.top_bar_widget.setVisible(True)
            self.stack.setVisible(True)
            self._root_layout.setContentsMargins(18, 15, 18, 16)
            self.setFixedSize(MAIN_WIDTH, 720)
        self._refresh_metrics()

    def _on_custom_target_toggled(self, checked: bool) -> None:
        self.custom_target_panel.setVisible(bool(checked))
        if hasattr(self, "settings_card"):
            self.settings_card.adjustSize()
        if hasattr(self, "settings_page"):
            self.settings_page.updateGeometry()

    def _apply_slacking_btn_style(self) -> None:
        if not hasattr(self, "btn_slacking_toggle"):
            return
        acc = self.config.accent_color
        active = bool(getattr(self, "is_slacking_active", False) or getattr(self, "_slacking_active", False))
        self.is_slacking_active = active
        self._slacking_active = active
        if active:
            bg = "#E53935"
            hover = "#F44336"
            press = "#C62828"
            self.btn_slacking_toggle.setText("结束摸鱼")
        else:
            bg = acc
            hover = QColor(acc).lighter(110).name()
            press = QColor(acc).darker(118).name()
            self.btn_slacking_toggle.setText("开始摸鱼")
        self.btn_slacking_toggle.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {bg};
                color: #FFFFFF;
                border: none;
                border-radius: 7px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:pressed {{
                background-color: {press};
                padding-top: 2px;
                padding-left: 1px;
            }}
            """
        )

    def _on_slacking_toggle_clicked(self) -> None:
        if self.is_slacking_active:
            self._stop_slacking()
        else:
            self._start_slacking(auto=False)

    def _start_slacking(self, auto: bool = False) -> None:
        if self.is_slacking_active:
            return
        self.is_slacking_active = True
        self._slacking_active = True
        self._slacking_start_ts = time.time()
        self._visible_fish_seconds = 0.0
        self._apply_slacking_btn_style()
        self._refresh_slacking_display()
        if auto:
            self._toast.show_message("🐟 已连续摸鱼满10分钟，开始带薪计时", is_light=(self.config.theme_mode == "light"))

    def _stop_slacking(self) -> None:
        if not self.is_slacking_active:
            return
        end_ts = time.time()
        start_ts = self._slacking_start_ts
        self.is_slacking_active = False
        self._slacking_active = False
        self._slacking_start_ts = 0.0
        self._visible_fish_seconds = 0.0
        if end_ts > start_ts:
            self._slacking_stats.record_session(start_ts, end_ts, self.config)
        self._apply_slacking_btn_style()
        self._refresh_slacking_display()

    def _get_live_slacking(self) -> tuple[float, float]:
        if not self._slacking_active or self._slacking_start_ts <= 0.0:
            return 0.0, 0.0
        secs = max(0.0, time.time() - self._slacking_start_ts)
        rate = SlackingStatsManager.calc_rate_per_second(self.config)
        return secs, secs * rate

    def _refresh_slacking_display(self) -> None:
        if not hasattr(self, "lbl_slacking_stats"):
            return
        live_secs, live_earned = self._get_live_slacking()
        has_salary = float(getattr(self.config, "monthly_salary", 0.0) or 0.0) > 0.0
        summary = self._slacking_stats.get_summary(live_secs, live_earned)
        today_secs = int(summary["today"]["seconds"])
        today_earned = summary["today"]["earned"]
        mm, ss = divmod(today_secs, 60)
        hh, mm = divmod(mm, 60)
        dur_str = f"{hh:02d}:{mm:02d}:{ss:02d}" if hh > 0 else f"{mm:02d}:{ss:02d}"
        amt_str = f"¥{today_earned:.2f}" if has_salary else "--"
        prefix = "摸鱼中 " if self._slacking_active else "今日 "
        self.lbl_slacking_stats.setText(f"{prefix}{dur_str}  ·  所得 {amt_str}")

        online_enabled = bool(getattr(self.config, "slacking_online_enabled", False))
        online_cnt = self._cloud_cfg.get("online_count") if (online_enabled and isinstance(self._cloud_cfg, dict)) else None
        online_txt = str(online_cnt) if online_cnt is not None else "--"
        self.btn_slacking_dash.setText("数据看板 >")

        if hasattr(self, "slacking_mini_canvas"):
            labels, vals, pk = self._slacking_stats.get_progressive_workday_curve(self.config, live_secs)
            self.slacking_mini_canvas.set_data(labels, vals, pk)

        if self._active_slacking_dlg is not None and self._active_slacking_dlg.isVisible():
            self._active_slacking_dlg.refresh_stats(live_secs, live_earned, has_salary, online_txt)

    def _send_slacking_anon_heartbeat(self) -> None:
        if not bool(getattr(self.config, "slacking_online_enabled", False)):
            return
        if not getattr(self, "_slacking_active", False):
            return
        anon_id = (getattr(self.config, "slacking_anon_uuid", "") or "").strip()
        if not anon_id:
            anon_id = uuid.uuid4().hex
            self.config.slacking_anon_uuid = anon_id
            self.config.save()

        def _worker() -> None:
            try:
                requests.post(
                    f"{CLOUD_API_DOMAIN}/api/slacking/heartbeat",
                    json={"uuid": anon_id},
                    timeout=5,
                )
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _open_progress_target_dialog(self) -> None:
        if self._active_progress_cfg_dlg is not None and self._active_progress_cfg_dlg.isVisible():
            self._active_progress_cfg_dlg.showNormal()
            self._active_progress_cfg_dlg.raise_()
            self._active_progress_cfg_dlg.activateWindow()
            return
        dlg = ProgressTargetConfigDialog(
            config=self.config,
            on_saved=self._refresh_metrics,
            parent=self,
        )
        dlg.finished.connect(lambda _res: setattr(self, "_active_progress_cfg_dlg", None))
        self._active_progress_cfg_dlg = dlg
        self._sync_children_win32_ownership()
        self.position_beside_main(dlg)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _open_slacking_settings_dialog(self) -> None:
        if self._active_slacking_cfg_dlg is not None and self._active_slacking_cfg_dlg.isVisible():
            self._active_slacking_cfg_dlg.showNormal()
            self._active_slacking_cfg_dlg.raise_()
            self._active_slacking_cfg_dlg.activateWindow()
            return
        dlg = SlackingSettingsDialog(
            config=self.config,
            on_saved=self._refresh_slacking_display,
            parent=self,
        )
        dlg.finished.connect(lambda _res: setattr(self, "_active_slacking_cfg_dlg", None))
        self._active_slacking_cfg_dlg = dlg
        self._sync_children_win32_ownership()
        self.position_beside_main(dlg)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _open_slacking_dashboard(self) -> None:
        if self._active_slacking_dlg is not None and self._active_slacking_dlg.isVisible():
            self._active_slacking_dlg.showNormal()
            self._active_slacking_dlg.raise_()
            self._active_slacking_dlg.activateWindow()
            return
        live_secs, live_earned = self._get_live_slacking()
        has_salary = float(getattr(self.config, "monthly_salary", 0.0) or 0.0) > 0.0
        online_enabled = bool(getattr(self.config, "slacking_online_enabled", False))
        online_cnt = self._cloud_cfg.get("online_count") if (online_enabled and isinstance(self._cloud_cfg, dict)) else None
        online_txt = str(online_cnt) if online_cnt is not None else "--"
        dlg = SlackingDashboardDialog(
            stats_mgr=self._slacking_stats,
            theme_mode=self.config.theme_mode,
            accent_color=self.config.accent_color,
            online_count_text=online_txt,
            live_secs=live_secs,
            live_earned=live_earned,
            has_salary=has_salary,
            parent=self,
        )
        dlg.finished.connect(lambda _res: setattr(self, "_active_slacking_dlg", None))
        self._active_slacking_dlg = dlg
        self._sync_children_win32_ownership()
        self.position_beside_main(dlg)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_tick(self) -> None:
        now_mono = time.monotonic()
        dt = max(0.0, min(5.0, now_mono - getattr(self, "_last_tick_ts", now_mono)))
        self._last_tick_ts = now_mono

        is_fish = getattr(self.config, "app_mode", "fish") == "fish"
        win_visible = self.isVisible() and not self.isMinimized()
        if is_fish and win_visible:
            if not self._slacking_active:
                self._visible_fish_seconds += dt
                if self._visible_fish_seconds >= 600.0:
                    self._start_slacking(auto=True)
        else:
            self._visible_fish_seconds = 0.0
            if self._slacking_active:
                self._stop_slacking()

        self._refresh_metrics()
        self._check_due_alarms()

    def _refresh_metrics(self) -> None:
        metrics = TimeCalculator.calculate(self.config)
        daily_salary = self.config.monthly_salary / 21.75
        self._latest_today_earned = 0.0 if metrics.is_weekend_rest else daily_salary * (metrics.progress_pct / 100.0)

        today = date.today()
        if self._last_holiday_render_date != today:
            self._rebuild_holiday_rows()

        self.date_label.setText(metrics.date_str)
        self.lbl_time_hm.setText(metrics.time_hm)
        self.lbl_time_s.setText(f":{metrics.time_s}")

        # 若进入新的时间段（如进入下班前30分/前5分），立即无缝切换至新时段文案
        pool_key, pool = self._get_current_quote_pool()
        if pool_key != self._active_quote_pool_key:
            self._active_quote_pool_key = pool_key
            self._quote_idx = 0
            self._last_status_quote_ms = self._now_ms()
            self.quote_timer.start(self._get_status_quote_interval_ms())
            self.status_ticker.slide_to(pool[0])

        work_tag, work_cd = self._format_compact_work_cd(metrics)
        work_pct, work_tip = metrics.progress_pct, metrics.countdown_text

        wk_tag, wk_cd = self._format_compact_weekend_cd(
            metrics.weekend_countdown_text,
            getattr(self.config, "work_mode", "double") == "custom",
        )
        wk_pct, wk_tip = metrics.weekend_progress_pct, metrics.weekend_countdown_text

        pd_tag = "发薪"
        pd_cd = self._format_compact_payday_cd(metrics.payday_countdown_text)
        pd_pct, pd_tip = metrics.payday_progress_pct, metrics.payday_countdown_text

        # 三个进度条槽位独立自定义目标覆盖
        fm_tag = QFontMetrics(self.lbl_tag_work.font())
        if getattr(self.config, "slot1_custom_enabled", False):
            ok, t_name, t_cd, t_tip, t_pct = TimeCalculator.calculate_slot_target(
                getattr(self.config, "slot1_custom_name", ""),
                getattr(self.config, "slot1_custom_date", ""),
                getattr(self.config, "slot1_custom_start", ""),
            )
            if ok:
                work_tag = fm_tag.elidedText(t_name, Qt.TextElideMode.ElideRight, 46)
                work_cd, work_pct, work_tip = t_cd, t_pct, t_tip
        if getattr(self.config, "slot2_custom_enabled", False):
            ok, t_name, t_cd, t_tip, t_pct = TimeCalculator.calculate_slot_target(
                getattr(self.config, "slot2_custom_name", ""),
                getattr(self.config, "slot2_custom_date", ""),
                getattr(self.config, "slot2_custom_start", ""),
            )
            if ok:
                wk_tag = fm_tag.elidedText(t_name, Qt.TextElideMode.ElideRight, 46)
                wk_cd, wk_pct, wk_tip = t_cd, t_pct, t_tip
        if getattr(self.config, "slot3_custom_enabled", False):
            ok, t_name, t_cd, t_tip, t_pct = TimeCalculator.calculate_slot_target(
                getattr(self.config, "slot3_custom_name", ""),
                getattr(self.config, "slot3_custom_date", ""),
                getattr(self.config, "slot3_custom_start", ""),
            )
            if ok:
                pd_tag = fm_tag.elidedText(t_name, Qt.TextElideMode.ElideRight, 46)
                pd_cd, pd_pct, pd_tip = t_cd, t_pct, t_tip

        self.lbl_tag_work.setText(work_tag)
        self.lbl_countdown.setText(work_cd)
        self.lbl_countdown.setToolTip(work_tip)
        self.lbl_progress_pct.setText(self._format_compact_pct(work_pct))
        self.lbl_progress_pct.setToolTip(work_tip)
        self.progress_bar.set_value(work_pct)

        self.lbl_tag_weekend.setText(wk_tag)
        self.lbl_weekend_countdown.setText(wk_cd)
        self.lbl_weekend_countdown.setToolTip(wk_tip)
        self.lbl_weekend_pct.setText(self._format_compact_pct(wk_pct))
        self.lbl_weekend_pct.setToolTip(wk_tip)
        self.weekend_bar.set_value(wk_pct)

        self.lbl_tag_payday.setText(pd_tag)
        self.lbl_payday_countdown.setText(pd_cd)
        self.lbl_payday_countdown.setToolTip(pd_tip)
        self.lbl_payday_pct.setText(self._format_compact_pct(pd_pct))
        self.lbl_payday_pct.setToolTip(pd_tip)
        self.payday_bar.set_value(pd_pct)

        self._refresh_slacking_display()

        if self._mini_mode and hasattr(self, "lbl_mini_time"):
            self.lbl_mini_time.setText(metrics.time_hm)
            if self._slacking_active:
                l_sec, l_earn = self._get_live_slacking()
                mm, ss = divmod(int(l_sec), 60)
                has_sal = float(getattr(self.config, "monthly_salary", 0.0) or 0.0) > 0.0
                amt = f"¥{l_earn:.2f}" if has_sal else "--"
                self.lbl_mini_metric.setText(f"摸鱼 {mm:02d}:{ss:02d} · {amt}")
            else:
                self.lbl_mini_metric.setText(f"{work_tag} {work_cd}")
            self.mini_progress_bar.set_value(work_pct)

    # ------------------------------------------------------------------
    # 闹钟提醒模块交互与后台轮询触发
    # ------------------------------------------------------------------
    def _refresh_alarm_card(self) -> None:
        if not hasattr(self, "alarm_card"):
            return
        primary = self._alarm_mgr.get_primary_alarm(self.config)
        has_alarm = primary is not None
        self.alarm_empty_lbl.setVisible(not has_alarm)
        self.alarm_row_widget.setVisible(has_alarm)
        if not has_alarm:
            return
        self._primary_alarm_id = primary.get("id", "")
        hr = int(primary.get("hour", 9))
        mn = int(primary.get("minute", 0))
        self.lbl_alarm_time.setText(f"{hr:02d}:{mn:02d}")
        mode_text = AlarmManager.MODE_LABELS.get(primary.get("mode", "daily"), "每日提醒")
        if primary.get("pinned"):
            mode_text = f"置顶 · {mode_text}"
        self.lbl_alarm_mode.setText(mode_text)
        note_raw = (primary.get("note") or "").strip() or "无备注"
        self.lbl_alarm_note.set_note_text(note_raw, 190)

    def _open_alarm_editor_dialog(self) -> None:
        if self._active_alarm_editor_dlg is not None and self._active_alarm_editor_dlg.isVisible():
            self._active_alarm_editor_dlg.showNormal()
            self._active_alarm_editor_dlg.raise_()
            self._active_alarm_editor_dlg.activateWindow()
            return
        dlg = AlarmEditorDialog(
            alarm_mgr=self._alarm_mgr,
            config=self.config,
            on_changed=self._refresh_alarm_card,
            parent=self,
        )
        dlg.finished.connect(lambda _res: setattr(self, "_active_alarm_editor_dlg", None))
        self._active_alarm_editor_dlg = dlg
        self._sync_children_win32_ownership()
        self.position_beside_main(dlg)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _check_due_alarms(self) -> None:
        if not hasattr(self, "_alarm_mgr"):
            return
        due_list = self._alarm_mgr.check_due_alarms(self.config)
        if not due_list:
            return
        self._refresh_alarm_card()
        if self._active_alarm_editor_dlg is not None and self._active_alarm_editor_dlg.isVisible():
            self._active_alarm_editor_dlg.refresh_list()
        for alarm in due_list:
            self._trigger_alarm_alert(alarm)

    def _trigger_alarm_alert(self, alarm: dict) -> None:
        def _on_alert_closed(dlg_ref: AlarmAlertDialog | None = None) -> None:
            if dlg_ref is not None and dlg_ref in self._active_alarm_alerts:
                self._active_alarm_alerts.remove(dlg_ref)
            self._refresh_alarm_card()
            if self._active_alarm_editor_dlg is not None and self._active_alarm_editor_dlg.isVisible():
                self._active_alarm_editor_dlg.refresh_list()

        dlg = AlarmAlertDialog(
            alarm=alarm,
            alarm_mgr=self._alarm_mgr,
            theme_mode=self.config.theme_mode,
            accent_color=self.config.accent_color,
            on_closed=lambda: _on_alert_closed(dlg),
            parent=None,
        )
        dlg.finished.connect(lambda _res, d=dlg: _on_alert_closed(d))
        self._active_alarm_alerts.append(dlg)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()


SINGLE_INSTANCE_KEY = "IdleMeter_SingleInstance_Lock"


def main():
    _cleanup_update_artifacts()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)

    # 单实例锁：若已有实例在运行，通知其唤醒并立即退出
    probe = QLocalSocket()
    probe.connectToServer(SINGLE_INSTANCE_KEY)
    if probe.waitForConnected(250):
        probe.write(b"SHOW")
        probe.waitForBytesWritten(250)
        probe.disconnectFromServer()
        sys.exit(0)

    QLocalServer.removeServer(SINGLE_INSTANCE_KEY)
    instance_server = QLocalServer(app)
    instance_server.listen(SINGLE_INSTANCE_KEY)

    # IdleMeter 启动自检：初始化主窗口并保持与既有统一缓存/配置目录（C:\Users\<用户名>\.摸鱼小工具）完全兼容
    window = MainWindow()
    window._refresh_app_icons()

    def _on_new_instance() -> None:
        conn = instance_server.nextPendingConnection()
        if conn is not None:
            conn.waitForReadyRead(100)
            conn.readAll()
            conn.close()
            conn.deleteLater()
        window._restore_from_tray()

    instance_server.newConnection.connect(_on_new_instance)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
