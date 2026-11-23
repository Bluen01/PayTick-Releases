import json
import mimetypes
import os
import queue
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import uuid
import zipfile
import calendar
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import requests
try:
    import winreg
except ImportError:
    winreg = None
from dataclasses import dataclass, asdict, field
from datetime import datetime, date, timedelta
from typing import Tuple, List, Dict, Any


APP_VERSION = "2.1.0"

BASE_DIR = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.expanduser("~"), ".摸鱼小工具")
os.makedirs(DATA_DIR, exist_ok=True)
PATH_CONFIG_FILE = os.path.join(DATA_DIR, "path_config.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
HOLIDAY_CACHE_FILE = os.path.join(DATA_DIR, "holidays_cache.json")
COMP_TIME_FILE = os.path.join(DATA_DIR, "comp_time.json")
SLACKING_STATS_FILE = os.path.join(DATA_DIR, "slacking_stats.json")
ALARMS_FILE = os.path.join(DATA_DIR, "alarms.json")
MESSAGES_CACHE_FILE = os.path.join(DATA_DIR, "messages_cache.json")
SHARE_CACHE_DIR = os.path.join(DATA_DIR, "share_cache")
SHARE_REGISTRY: Dict[str, Dict[str, Any]] = {}
_SHARE_REGISTRY_LOCK = threading.Lock()


def _ensure_parent_dir(filepath: str) -> None:
    parent = os.path.dirname(filepath)
    if parent:
        os.makedirs(parent, exist_ok=True)


@dataclass
class AppConfig:
    work_start: str = "09:30"          # 上班时间 HH:MM
    work_end: str = "18:30"            # 下班时间 HH:MM
    lunch_start: str = "12:00"         # 午休开始时间 HH:MM
    lunch_end: str = "13:00"           # 午休结束时间 HH:MM
    monthly_salary: float = 3000.0     # 税后月薪 (元)
    payday: int = 15                   # 每月发薪日 (1-31)
    work_mode: str = "double"          # 工作制度: "double" (双休) / "custom" (自定义休息日)
    always_on_top: bool = False        # 默认是否置顶
    accent_color: str = "#FF6B00"      # 主题点缀色: "#FF6B00" (琥珀橙) 或 "#10B981" (翡翠绿)
    theme_mode: str = "dark"           # 主题模式: "dark" (暗黑系) / "light" (白色简约模式)
    status_index: int = 0              # 当前选中的状态文案索引
    holiday_irrelevant: bool = False   # 节假日与我无关
    auto_start: bool = False           # 开机自启 (默认不选择)
    auto_update: bool = False          # 自动更新 (默认关闭)
    close_behavior: str = "ask"        # 关闭行为: "ask" (每次询问) / "tray" (缩小到任务栏) / "exit" (直接退出)

    # 自定义休息模式配置
    custom_rest_dates: List[str] = field(default_factory=list)       # 日历点选日期 ["YYYY-MM-DD", ...]
    custom_fixed_weekdays: List[int] = field(default_factory=list)   # 固定每周几休息 [0..6]
    custom_monthly_selected_days_enabled: bool = False               # 每月固定休（已选择日期的号数）

    # 设备持久标识与已读反馈回复键列表
    device_id: str = ""
    read_reply_ids: List[str] = field(default_factory=list)
    read_reply_keys: List[str] = field(default_factory=list)
    holiday_view_mode: str = "list"    # 法定节假日展示模式: "list" / "calendar"
    app_mode: str = "fish"             # 应用模式: "fish" (摸鱼模式) / "work" (工作模式)
    last_download_dir: str = ""        # 工作模式极速下载上次保存目录
    clipboard_history_enabled: bool = True   # 启用复制历史记录
    clipboard_keep_next_day: bool = False    # 复制历史保留到第二天
    cache_dir: str = ""                      # 自定义缓存根目录（空则使用默认 DATA_DIR）
    cf_tunnel_token: str = ""                # 可选：Cloudflare Zero Trust 永久隧道 Token（留空则走免费 Quick Tunnel）
    cf_custom_domain: str = ""               # 可选：自定义固定 HTTPS 访问域名（如 https://im.ccwu.cc）
    keep_window_on_capture: bool = False     # 截图/识字/取色时不隐藏主窗口与子窗口（默认自动隐藏）
    keep_children_on_hide: bool = False      # 主窗口最小化或关闭隐藏到托盘时保留已打开的子窗口显示
    custom_target_enabled: bool = False
    custom_target_name: str = ""
    custom_target_date: str = ""
    custom_target_start_date: str = ""
    custom_target_slot: str = "work"
    slot1_custom_enabled: bool = False
    slot1_custom_name: str = ""
    slot1_custom_date: str = ""
    slot1_custom_start: str = ""
    slot1_exact_time: bool = False
    slot2_custom_enabled: bool = False
    slot2_custom_name: str = ""
    slot2_custom_date: str = ""
    slot2_custom_start: str = ""
    slot2_exact_time: bool = False
    slot3_custom_enabled: bool = False
    slot3_custom_name: str = ""
    slot3_custom_date: str = ""
    slot3_custom_start: str = ""
    slot3_exact_time: bool = False
    slacking_online_enabled: bool = False
    slacking_anon_uuid: str = ""

    @classmethod
    def load(cls, filepath: str = CONFIG_FILE) -> "AppConfig":
        cfg = None
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                valid_keys = cls.__dataclass_fields__.keys()
                filtered = {k: v for k, v in data.items() if k in valid_keys}
                if str(filtered.get("accent_color", "")).upper() == "#00E676":
                    filtered["accent_color"] = "#10B981"
                if filtered.get("work_mode") == "single":
                    filtered["work_mode"] = "double"
                for t_key, t_def in (
                    ("work_start", "09:30"),
                    ("work_end", "18:30"),
                    ("lunch_start", "12:00"),
                    ("lunch_end", "13:00"),
                ):
                    if not str(filtered.get(t_key, "") or "").strip():
                        filtered[t_key] = t_def
                cfg = cls(**filtered)
            except Exception:
                cfg = None
        if cfg is None:
            cfg = cls()
        if not cfg.device_id:
            cfg.device_id = f"DEV-{uuid.uuid4().hex[:8].upper()}"
            cfg.save(filepath)
        elif not os.path.exists(filepath):
            cfg.save(filepath)
        return cfg

    def save(self, filepath: str = CONFIG_FILE) -> None:
        try:
            _ensure_parent_dir(filepath)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        except Exception:
            pass


@dataclass
class OvertimeRecord:
    id: str
    date_str: str           # YYYY-MM-DD
    start_time_str: str     # 开始时间 HH:MM
    end_time_str: str       # 结束时间 HH:MM
    overtime_hours: float   # 实际加班时长 (小时)
    comp_hours: float       # 计入调休时长 (小时)
    note: str = ""          # 保留字段兼容旧数据


def set_windows_autostart(enabled: bool, app_name: str = "IdleMeter") -> bool:
    """
    通过 Windows 注册表 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run 设置/取消开机自启
    """
    if winreg is None:
        return False
    run_key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key_path, 0, winreg.KEY_SET_VALUE)
        try:
            if enabled:
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    main_py = os.path.join(BASE_DIR, "main.py")
                    py_dir = os.path.dirname(sys.executable)
                    pythonw_exe = os.path.join(py_dir, "pythonw.exe")
                    exe_path = pythonw_exe if os.path.exists(pythonw_exe) else sys.executable
                    cmd = f'"{exe_path}" "{main_py}"'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
        return True
    except Exception:
        return False


class CompTimeManager:
    """
    调休余额与加班记录管理器（持久化至 comp_time.json）
    规则：以设定下班时间（如 18:30）为基准，超过 2 小时（如 20:30 及以后）才计入调休，不超过 2 小时不计调休。
    """
    def __init__(self, filepath: str = COMP_TIME_FILE):
        self.filepath = filepath
        self.records: List[OvertimeRecord] = []
        self.manual_adjustment_hours: float = 0.0
        self.load()

    def load(self) -> None:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.manual_adjustment_hours = float(data.get("manual_adjustment_hours", 0.0))
                raw_recs = data.get("records", [])
                self.records = []
                for item in raw_recs:
                    self.records.append(
                        OvertimeRecord(
                            id=str(item.get("id", "")),
                            date_str=str(item.get("date_str", "")),
                            start_time_str=str(item.get("start_time_str", "18:30")),
                            end_time_str=str(item.get("end_time_str", "")),
                            overtime_hours=float(item.get("overtime_hours", 0.0)),
                            comp_hours=float(item.get("comp_hours", 0.0)),
                            note=str(item.get("note", "")),
                        )
                    )
                self._sort_records()
            except Exception:
                self.records = []
                self.manual_adjustment_hours = 0.0

    def save(self) -> None:
        self._sort_records()
        payload = {
            "manual_adjustment_hours": round(self.manual_adjustment_hours, 2),
            "records": [asdict(r) for r in self.records],
        }
        try:
            _ensure_parent_dir(self.filepath)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _sort_records(self) -> None:
        self.records.sort(key=lambda r: (r.date_str, r.id), reverse=True)

    @staticmethod
    def calc_overtime_and_comp(
        start_str: str,
        end_str: str,
        deduct_lunch: bool = False,
        lunch_start_str: str = "12:00",
        lunch_end_str: str = "13:00",
    ) -> Tuple[float, float]:
        """
        根据加班开始时间与结束时间，计算加班时长与可调休时长。
        超过 2.0 小时（例如 18:30 到 20:30 及以后）才算有效调休。
        当 deduct_lunch 为 True 时，自动扣除与午休时间段重叠的分钟数。
        """
        sh, sm = TimeCalculator.parse_hm(start_str, (18, 30))
        eh, em = TimeCalculator.parse_hm(end_str, (20, 30))

        start_mins = sh * 60 + sm
        end_mins = eh * 60 + em
        if end_mins < start_mins and end_mins < 12 * 60:
            end_mins += 24 * 60

        diff_mins = max(0, end_mins - start_mins)
        if deduct_lunch and diff_mins > 0:
            lsh, lsm = TimeCalculator.parse_hm(lunch_start_str, (12, 0))
            leh, lem = TimeCalculator.parse_hm(lunch_end_str, (13, 0))
            lunch_s = lsh * 60 + lsm
            lunch_e = leh * 60 + lem
            if lunch_e > lunch_s:
                overlap = max(0, min(end_mins, lunch_e) - max(start_mins, lunch_s))
                diff_mins = max(0, diff_mins - overlap)

        overtime_hours = round(diff_mins / 60.0, 2)
        comp_hours = overtime_hours if overtime_hours >= 2.0 else 0.0
        return overtime_hours, comp_hours

    def add_record(
        self,
        date_str: str,
        start_time_str: str,
        end_time_str: str,
        note: str = "",
        deduct_lunch: bool = False,
        lunch_start_str: str = "12:00",
        lunch_end_str: str = "13:00",
    ) -> OvertimeRecord:
        ot_h, comp_h = self.calc_overtime_and_comp(
            start_time_str,
            end_time_str,
            deduct_lunch=deduct_lunch,
            lunch_start_str=lunch_start_str,
            lunch_end_str=lunch_end_str,
        )
        rec = OvertimeRecord(
            id=str(int(datetime.now().timestamp() * 1000)),
            date_str=date_str,
            start_time_str=start_time_str,
            end_time_str=end_time_str,
            overtime_hours=ot_h,
            comp_hours=comp_h,
            note=note.strip(),
        )
        self.records.append(rec)
        self.save()
        return rec

    def update_record(
        self,
        rec_id: str,
        date_str: str,
        start_time_str: str,
        end_time_str: str,
        overtime_hours: float,
        comp_hours: float,
        note: str = "",
    ) -> None:
        for r in self.records:
            if r.id == rec_id:
                r.date_str = date_str
                r.start_time_str = start_time_str
                r.end_time_str = end_time_str
                r.overtime_hours = round(max(0.0, overtime_hours), 2)
                r.comp_hours = round(max(0.0, comp_hours), 2)
                r.note = note.strip()
                break
        self.save()

    def delete_record(self, rec_id: str) -> None:
        self.records = [r for r in self.records if r.id != rec_id]
        self.save()

    def add_manual_adjustment(self, delta_hours: float) -> None:
        self.manual_adjustment_hours = round(self.manual_adjustment_hours + delta_hours, 2)
        self.save()

    def set_total_balance(self, target_balance: float) -> None:
        rec_sum = sum(r.comp_hours for r in self.records)
        self.manual_adjustment_hours = round(target_balance - rec_sum, 2)
        self.save()

    def get_balance_hours(self) -> float:
        rec_sum = sum(r.comp_hours for r in self.records)
        return round(rec_sum + self.manual_adjustment_hours, 2)

    def get_last_overtime_hours(self) -> float:
        if not self.records:
            return 0.0
        self._sort_records()
        return round(self.records[0].overtime_hours, 2)


@dataclass
class HolidayEntry:
    name: str
    start_date: date
    end_date: date
    holiday_days: int
    makeup_days: int
    makeup_dates: List[str]
    is_expired: bool
    is_ongoing: bool
    days_until: int
    status_col_text: str
    rest_col_text: str
    makeup_col_text: str
    hover_countdown_tip: str


@dataclass
class WorkMetrics:
    date_str: str
    time_hm: str
    time_s: str
    is_off_work: bool
    is_before_work: bool
    is_weekend_rest: bool
    countdown_text: str
    remain_hms: str
    progress_pct: float
    weekend_countdown_text: str
    weekend_progress_pct: float
    payday_countdown_text: str
    payday_progress_pct: float


class HolidayService:
    SPRING_SUB_NAMES = {"除夕", "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "春节"}
    DISPLAY_NAME_MAP = {
        "元旦": "元旦",
        "春节": "春节",
        "清明节": "清明节",
        "劳动节": "劳动节",
        "端午节": "端午节",
        "中秋节": "中秋节",
        "国庆节": "国庆节",
    }

    FALLBACK_2026 = {
        "01-01": {"holiday": True, "name": "元旦", "date": "2026-01-01"},
        "01-02": {"holiday": True, "name": "元旦", "date": "2026-01-02"},
        "01-03": {"holiday": True, "name": "元旦", "date": "2026-01-03"},
        "01-04": {"holiday": False, "name": "元旦后补班", "target": "元旦", "date": "2026-01-04"},
        "02-14": {"holiday": False, "name": "春节前补班", "target": "春节", "date": "2026-02-14"},
        "02-15": {"holiday": True, "name": "春节", "date": "2026-02-15"},
        "02-16": {"holiday": True, "name": "除夕", "date": "2026-02-16"},
        "02-17": {"holiday": True, "name": "初一", "date": "2026-02-17"},
        "02-18": {"holiday": True, "name": "初二", "date": "2026-02-18"},
        "02-19": {"holiday": True, "name": "初三", "date": "2026-02-19"},
        "02-20": {"holiday": True, "name": "初四", "date": "2026-02-20"},
        "02-21": {"holiday": True, "name": "初五", "date": "2026-02-21"},
        "02-22": {"holiday": True, "name": "初六", "date": "2026-02-22"},
        "02-23": {"holiday": True, "name": "初七", "date": "2026-02-23"},
        "02-28": {"holiday": False, "name": "春节后补班", "target": "春节", "date": "2026-02-28"},
        "04-04": {"holiday": True, "name": "清明节", "date": "2026-04-04"},
        "04-05": {"holiday": True, "name": "清明节", "date": "2026-04-05"},
        "04-06": {"holiday": True, "name": "清明节", "date": "2026-04-06"},
        "05-01": {"holiday": True, "name": "劳动节", "date": "2026-05-01"},
        "05-02": {"holiday": True, "name": "劳动节", "date": "2026-05-02"},
        "05-03": {"holiday": True, "name": "劳动节", "date": "2026-05-03"},
        "05-04": {"holiday": True, "name": "劳动节", "date": "2026-05-04"},
        "05-05": {"holiday": True, "name": "劳动节", "date": "2026-05-05"},
        "05-09": {"holiday": False, "name": "劳动节后补班", "target": "劳动节", "date": "2026-05-09"},
        "06-19": {"holiday": True, "name": "端午节", "date": "2026-06-19"},
        "06-20": {"holiday": True, "name": "端午节", "date": "2026-06-20"},
        "06-21": {"holiday": True, "name": "端午节", "date": "2026-06-21"},
        "09-20": {"holiday": False, "name": "国庆节前补班", "target": "国庆节", "date": "2026-09-20"},
        "09-25": {"holiday": True, "name": "中秋节", "date": "2026-09-25"},
        "09-26": {"holiday": True, "name": "中秋节", "date": "2026-09-26"},
        "09-27": {"holiday": True, "name": "中秋节", "date": "2026-09-27"},
        "10-01": {"holiday": True, "name": "国庆节", "date": "2026-10-01"},
        "10-02": {"holiday": True, "name": "国庆节", "date": "2026-10-02"},
        "10-03": {"holiday": True, "name": "国庆节", "date": "2026-10-03"},
        "10-04": {"holiday": True, "name": "国庆节", "date": "2026-10-04"},
        "10-05": {"holiday": True, "name": "国庆节", "date": "2026-10-05"},
        "10-06": {"holiday": True, "name": "国庆节", "date": "2026-10-06"},
        "10-07": {"holiday": True, "name": "国庆节", "date": "2026-10-07"},
        "10-10": {"holiday": False, "name": "国庆节后补班", "target": "国庆节", "date": "2026-10-10"},
    }

    FALLBACK_2027 = {
        "01-01": {"holiday": True, "name": "元旦", "date": "2027-01-01"},
        "01-02": {"holiday": True, "name": "元旦", "date": "2027-01-02"},
        "01-03": {"holiday": True, "name": "元旦", "date": "2027-01-03"},
        "01-31": {"holiday": False, "name": "春节前补班", "target": "春节", "date": "2027-01-31"},
        "02-05": {"holiday": True, "name": "除夕", "date": "2027-02-05"},
        "02-06": {"holiday": True, "name": "初一", "date": "2027-02-06"},
        "02-07": {"holiday": True, "name": "初二", "date": "2027-02-07"},
        "02-08": {"holiday": True, "name": "初三", "date": "2027-02-08"},
        "02-09": {"holiday": True, "name": "初四", "date": "2027-02-09"},
        "02-10": {"holiday": True, "name": "初五", "date": "2027-02-10"},
        "02-11": {"holiday": True, "name": "初六", "date": "2027-02-11"},
        "02-12": {"holiday": True, "name": "初七", "date": "2027-02-12"},
        "02-13": {"holiday": True, "name": "初八", "date": "2027-02-13"},
        "02-14": {"holiday": False, "name": "春节后补班", "target": "春节", "date": "2027-02-14"},
        "04-03": {"holiday": True, "name": "清明节", "date": "2027-04-03"},
        "04-04": {"holiday": True, "name": "清明节", "date": "2027-04-04"},
        "04-05": {"holiday": True, "name": "清明节", "date": "2027-04-05"},
        "05-01": {"holiday": True, "name": "劳动节", "date": "2027-05-01"},
        "05-02": {"holiday": True, "name": "劳动节", "date": "2027-05-02"},
        "05-03": {"holiday": True, "name": "劳动节", "date": "2027-05-03"},
        "05-04": {"holiday": True, "name": "劳动节", "date": "2027-05-04"},
        "05-05": {"holiday": True, "name": "劳动节", "date": "2027-05-05"},
        "05-08": {"holiday": False, "name": "劳动节后补班", "target": "劳动节", "date": "2027-05-08"},
        "06-09": {"holiday": True, "name": "端午节", "date": "2027-06-09"},
        "09-15": {"holiday": True, "name": "中秋节", "date": "2027-09-15"},
        "09-26": {"holiday": False, "name": "国庆节前补班", "target": "国庆节", "date": "2027-09-26"},
        "10-01": {"holiday": True, "name": "国庆节", "date": "2027-10-01"},
        "10-02": {"holiday": True, "name": "国庆节", "date": "2027-10-02"},
        "10-03": {"holiday": True, "name": "国庆节", "date": "2027-10-03"},
        "10-04": {"holiday": True, "name": "国庆节", "date": "2027-10-04"},
        "10-05": {"holiday": True, "name": "国庆节", "date": "2027-10-05"},
        "10-06": {"holiday": True, "name": "国庆节", "date": "2027-10-06"},
        "10-07": {"holiday": True, "name": "国庆节", "date": "2027-10-07"},
        "10-09": {"holiday": False, "name": "国庆节后补班", "target": "国庆节", "date": "2027-10-09"},
    }

    @classmethod
    def normalize_festival_key(cls, raw_name: str, target_name: str = "") -> str:
        name = target_name.strip() if target_name else raw_name.strip()
        if name in cls.SPRING_SUB_NAMES or "春节" in name:
            return "春节"
        for k in ("元旦", "清明节", "劳动节", "端午节", "中秋节", "国庆节"):
            if k in name:
                return k
        return name

    @classmethod
    def fetch_year_raw_online(cls, year: int) -> Tuple[Dict[str, Any], bool]:
        url = f"https://timor.tech/api/holiday/year/{year}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw_bytes = resp.read()
                payload = json.loads(raw_bytes.decode("utf-8"))
                if payload.get("code") == 0 and isinstance(payload.get("holiday"), dict) and payload["holiday"]:
                    cls._save_cache(year, payload["holiday"])
                    return payload["holiday"], True
        except Exception:
            pass

        cached = cls._load_cache(year)
        if cached:
            return cached, False
        if year == 2026:
            return cls.FALLBACK_2026, False
        if year == 2027:
            return cls.FALLBACK_2027, False
        return {}, False

    @classmethod
    def _load_cache(cls, year: int) -> Dict[str, Any]:
        if os.path.exists(HOLIDAY_CACHE_FILE):
            try:
                with open(HOLIDAY_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                yr_data = data.get(str(year))
                if isinstance(yr_data, dict) and yr_data:
                    return yr_data
            except Exception:
                pass
        return {}

    @classmethod
    def _save_cache(cls, year: int, holiday_dict: Dict[str, Any]) -> None:
        data = {}
        if os.path.exists(HOLIDAY_CACHE_FILE):
            try:
                with open(HOLIDAY_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[str(year)] = holiday_dict
        try:
            _ensure_parent_dir(HOLIDAY_CACHE_FILE)
            with open(HOLIDAY_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def get_initial_raw_data(cls, year: int) -> Dict[str, Any]:
        cached = cls._load_cache(year)
        if cached:
            return cached
        if year == 2026:
            return cls.FALLBACK_2026
        if year == 2027:
            return cls.FALLBACK_2027
        return {}

    @classmethod
    def parse_holidays(cls, raw_dict: Dict[str, Any], today: date = None) -> List[HolidayEntry]:
        if today is None:
            today = date.today()

        groups: Dict[str, Dict[str, List[date]]] = {}
        order_keys: List[str] = []

        for _, item in sorted(raw_dict.items(), key=lambda x: x[0]):
            date_str = item.get("date", "")
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                continue

            is_hol = bool(item.get("holiday", True))
            raw_name = str(item.get("name", ""))
            target_name = str(item.get("target", ""))
            fest_key = cls.normalize_festival_key(raw_name, target_name if not is_hol else "")

            if fest_key not in groups:
                groups[fest_key] = {"rest_dates": [], "makeup_dates": []}
                order_keys.append(fest_key)

            if is_hol:
                groups[fest_key]["rest_dates"].append(d)
            else:
                groups[fest_key]["makeup_dates"].append(d)

        entries: List[HolidayEntry] = []
        for fest_key in order_keys:
            rest_dates = sorted(groups[fest_key]["rest_dates"])
            makeup_dates = sorted(groups[fest_key]["makeup_dates"])
            if not rest_dates:
                continue

            start_d = rest_dates[0]
            end_d = rest_dates[-1]
            holiday_days = len(rest_dates)
            makeup_days = len(makeup_dates)
            makeup_str_list = [f"{md.month:02d}.{md.day:02d}" for md in makeup_dates]

            display_name = cls.DISPLAY_NAME_MAP.get(fest_key, fest_key[:3])

            if today > end_d:
                is_expired = True
                is_ongoing = False
                days_until = 0
                status_col_text = "已失效"
                hover_countdown_tip = "该节日今年已过"
            elif start_d <= today <= end_d:
                is_expired = False
                is_ongoing = True
                days_until = 0
                status_col_text = "休假中"
                hover_countdown_tip = "当前正在享受假期中"
            else:
                is_expired = False
                is_ongoing = False
                days_until = (start_d - today).days
                status_col_text = "待生效"
                hover_countdown_tip = f"距离生效还有 {days_until} 天"

            entries.append(
                HolidayEntry(
                    name=display_name,
                    start_date=start_d,
                    end_date=end_d,
                    holiday_days=holiday_days,
                    makeup_days=makeup_days,
                    makeup_dates=makeup_str_list,
                    is_expired=is_expired,
                    is_ongoing=is_ongoing,
                    days_until=days_until,
                    status_col_text=status_col_text,
                    rest_col_text=f"休{holiday_days}天",
                    makeup_col_text=f"补班{makeup_days}天",
                    hover_countdown_tip=hover_countdown_tip,
                )
            )

        entries.sort(key=lambda e: e.start_date)
        return entries


class TimeCalculator:
    WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    @staticmethod
    def parse_hm(hm_str: str, default: Tuple[int, int] = (9, 30)) -> Tuple[int, int]:
        try:
            parts = hm_str.strip().split(":")
            h = max(0, min(23, int(parts[0])))
            m = max(0, min(59, int(parts[1])))
            return h, m
        except Exception:
            return default

    @classmethod
    def get_work_datetimes(cls, now: datetime, config: AppConfig) -> Tuple[datetime, datetime]:
        sh, sm = cls.parse_hm(config.work_start, (9, 30))
        eh, em = cls.parse_hm(config.work_end, (18, 30))

        start_dt = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end_dt = now.replace(hour=eh, minute=em, second=0, microsecond=0)

        if end_dt <= start_dt:
            if now < start_dt and now.hour < eh + 2:
                start_dt -= timedelta(days=1)
            else:
                end_dt += timedelta(days=1)
        return start_dt, end_dt

    @classmethod
    def is_custom_rest_day(cls, d: date, config: AppConfig) -> bool:
        d_str = d.strftime("%Y-%m-%d")
        if d_str in config.custom_rest_dates:
            return True
        if d.weekday() in config.custom_fixed_weekdays:
            return True
        if config.custom_monthly_selected_days_enabled and config.custom_rest_dates:
            selected_day_nums = set()
            for item in config.custom_rest_dates:
                try:
                    selected_day_nums.add(int(item.split("-")[2]))
                except Exception:
                    pass
            if d.day in selected_day_nums:
                return True
        return False

    @classmethod
    def is_rest_day(cls, d: date, config: AppConfig) -> bool:
        if config.work_mode == "custom":
            return cls.is_custom_rest_day(d, config)
        return d.weekday() in (5, 6)

    @classmethod
    def _get_adjusted_payday(cls, yr: int, mo: int, payday_day: int, config: AppConfig) -> Tuple[date, bool]:
        max_d = calendar.monthrange(yr, mo)[1]
        actual_d = min(max(1, min(31, payday_day)), max_d)
        target = date(yr, mo, actual_d)
        adjusted = False
        guard = 0
        while cls.is_rest_day(target, config) and guard < 15:
            target -= timedelta(days=1)
            adjusted = True
            guard += 1
        return target, adjusted

    @classmethod
    def calc_payday(cls, now: datetime, payday_day: int, config: AppConfig) -> Tuple[str, float]:
        today = now.date()
        cur_payday, _ = cls._get_adjusted_payday(today.year, today.month, payday_day, config)

        if cur_payday >= today:
            next_payday = cur_payday
            if today.month == 1:
                prev_payday, _ = cls._get_adjusted_payday(today.year - 1, 12, payday_day, config)
            else:
                prev_payday, _ = cls._get_adjusted_payday(today.year, today.month - 1, payday_day, config)
        else:
            prev_payday = cur_payday
            if today.month == 12:
                next_payday, _ = cls._get_adjusted_payday(today.year + 1, 1, payday_day, config)
            else:
                next_payday, _ = cls._get_adjusted_payday(today.year, today.month + 1, payday_day, config)

        days_left = (next_payday - today).days
        if days_left == 0:
            text = f"🎉 今日发薪日 ({next_payday.month:02d}月{next_payday.day:02d}日)，注意查收"
            pct = 100.0
        else:
            text = f"距离发薪日还有 {days_left}天 ({next_payday.month:02d}月{next_payday.day:02d}日)"
            prev_dt = datetime(prev_payday.year, prev_payday.month, prev_payday.day, 0, 0, 0)
            next_dt = datetime(next_payday.year, next_payday.month, next_payday.day, 0, 0, 0)
            total_sec = max(1.0, (next_dt - prev_dt).total_seconds())
            elapsed_sec = max(0.0, (now - prev_dt).total_seconds())
            pct = min(100.0, max(0.0, (elapsed_sec / total_sec) * 100.0))

        return text, pct

    @classmethod
    def calc_weekend_countdown(cls, now: datetime, config: AppConfig) -> Tuple[str, float]:
        today = now.date()
        sh, sm = cls.parse_hm(config.work_start, (9, 30))
        eh, em = cls.parse_hm(config.work_end, (18, 30))

        if config.work_mode == "custom":
            if cls.is_rest_day(today, config):
                return "🎉 今日自定义休假中，享受生活", 100.0

            next_rest = None
            for offset in range(1, 62):
                cand = today + timedelta(days=offset)
                if cls.is_rest_day(cand, config):
                    next_rest = cand
                    break

            if next_rest is None:
                return "暂未设置后续休息日 (可在设置中勾选)", 0.0

            prev_work_start_d = today
            for back in range(1, 32):
                cand = today - timedelta(days=back)
                if cls.is_rest_day(cand, config):
                    break
                prev_work_start_d = cand

            cycle_start_dt = datetime(prev_work_start_d.year, prev_work_start_d.month, prev_work_start_d.day, sh, sm, 0)
            last_work_d = next_rest - timedelta(days=1)
            target_dt = datetime(last_work_d.year, last_work_d.month, last_work_d.day, eh, em, 0)

            if now >= target_dt:
                return "🎉 本轮工作已下班，即将开启休假", 100.0

            total_sec = max(1.0, (target_dt - cycle_start_dt).total_seconds())
            elapsed_sec = max(0.0, (now - cycle_start_dt).total_seconds())
            pct = min(100.0, max(0.0, (elapsed_sec / total_sec) * 100.0))

            diff_sec = int((target_dt - now).total_seconds())
            days = diff_sec // 86400
            rem = diff_sec % 86400
            hours, rem = divmod(rem, 3600)
            minutes, seconds = divmod(rem, 60)
            if days > 0:
                text = f"距离休假还有 {days}天 {hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                text = f"距离休假还有 {hours:02d}:{minutes:02d}:{seconds:02d}"
            return text, pct

        wd = now.weekday()
        last_work_weekday = 4

        if wd > last_work_weekday:
            return "🎉 周末假期中，尽情享受生活", 100.0

        monday_dt = (now - timedelta(days=wd)).replace(hour=sh, minute=sm, second=0, microsecond=0)
        days_until_last = last_work_weekday - wd
        target_dt = (now + timedelta(days=days_until_last)).replace(
            hour=eh, minute=em, second=0, microsecond=0
        )

        if target_dt <= monday_dt:
            target_dt += timedelta(days=1)

        if now >= target_dt:
            return "🎉 本周已下班，周末愉快", 100.0

        total_week_sec = max(1.0, (target_dt - monday_dt).total_seconds())
        elapsed_week_sec = max(0.0, (now - monday_dt).total_seconds())
        pct = min(100.0, max(0.0, (elapsed_week_sec / total_week_sec) * 100.0))

        diff_sec = int((target_dt - now).total_seconds())
        days = diff_sec // 86400
        rem = diff_sec % 86400
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)

        if days > 0:
            text = f"距离周末还有 {days}天 {hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            text = f"距离周末还有 {hours:02d}:{minutes:02d}:{seconds:02d}"

        return text, pct

    @classmethod
    def calculate(cls, config: AppConfig, now: datetime = None) -> WorkMetrics:
        if now is None:
            now = datetime.now()

        today = now.date()
        full_weekdays = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
        wd_name = full_weekdays[today.weekday()]
        date_str = f"{today.year}年{today.month:02d}月{today.day:02d}日 {wd_name}"
        time_hm = now.strftime("%H:%M")
        time_s = now.strftime("%S")

        start_dt, end_dt = cls.get_work_datetimes(now, config)
        total_work_seconds = max(1.0, (end_dt - start_dt).total_seconds())

        is_weekend_rest = cls.is_rest_day(today, config)
        is_before_work = False
        is_off_work = False

        if is_weekend_rest:
            is_off_work = True
            progress_pct = 100.0
            remain_hms = "00:00:00"
            countdown_text = "🎉 今日休息，享受生活"
        elif now < start_dt:
            is_before_work = True
            progress_pct = 0.0
            diff_sec = int((start_dt - now).total_seconds())
            h, rem = divmod(diff_sec, 3600)
            m, s = divmod(rem, 60)
            remain_hms = f"{h:02d}:{m:02d}:{s:02d}"
            countdown_text = f"距离上班还有 {remain_hms}"
        elif now >= end_dt:
            is_off_work = True
            progress_pct = 100.0
            remain_hms = "00:00:00"
            countdown_text = "🎉 今日已下班，享受生活"
        else:
            elapsed = (now - start_dt).total_seconds()
            remain = max(0.0, (end_dt - now).total_seconds())
            progress_pct = min(100.0, max(0.0, (elapsed / total_work_seconds) * 100.0))

            rem_int = int(remain)
            h, r = divmod(rem_int, 3600)
            m, s = divmod(r, 60)
            remain_hms = f"{h:02d}:{m:02d}:{s:02d}"
            countdown_text = f"距离下班还有 {remain_hms}"

        weekend_text, weekend_pct = cls.calc_weekend_countdown(now, config)
        payday_text, payday_pct = cls.calc_payday(now, config.payday, config)

        return WorkMetrics(
            date_str=date_str,
            time_hm=time_hm,
            time_s=time_s,
            is_off_work=is_off_work,
            is_before_work=is_before_work,
            is_weekend_rest=is_weekend_rest,
            countdown_text=countdown_text,
            remain_hms=remain_hms,
            progress_pct=progress_pct,
            weekend_countdown_text=weekend_text,
            weekend_progress_pct=weekend_pct,
            payday_countdown_text=payday_text,
            payday_progress_pct=payday_pct,
        )

    @staticmethod
    def parse_target_datetime(raw: str) -> datetime | None:
        text = str(raw or "").strip()
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    @classmethod
    def calculate_slot_target(
        cls, name: str, target_date_str: str, start_date_str: str = "", now: datetime | None = None
    ) -> Tuple[bool, str, str, str, float]:
        if now is None:
            now = datetime.now()
        target_dt = cls.parse_target_datetime(target_date_str)
        if target_dt is None:
            return False, "", "--", "", 0.0
        clean_name = (name or "").strip() or "目标"
        start_dt = cls.parse_target_datetime(start_date_str) or now
        if start_dt >= target_dt:
            start_dt = target_dt - timedelta(days=1)

        if now >= target_dt:
            return True, clean_name, "已到期", f"{clean_name} 已到期", 100.0

        total_span = max(1.0, (target_dt - start_dt).total_seconds())
        elapsed = max(0.0, (now - start_dt).total_seconds())
        pct = min(100.0, max(0.0, (elapsed / total_span) * 100.0))

        rem_sec = int(max(0.0, (target_dt - now).total_seconds()))
        days, rem = divmod(rem_sec, 86400)
        hours, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        compact = f"{days}天{hours:02d}时" if days > 0 else f"{hours:02d}:{mins:02d}:{secs:02d}"
        tip = f"距离 {clean_name} 还有 {days} 天 {hours:02d}:{mins:02d}:{secs:02d}"
        return True, clean_name, compact, tip, pct

    @classmethod
    def calculate_custom_target(
        cls, config: AppConfig, now: datetime | None = None
    ) -> Tuple[bool, str, str, str, float]:
        return cls.calculate_slot_target(
            getattr(config, "custom_target_name", ""),
            getattr(config, "custom_target_date", ""),
            getattr(config, "custom_target_start_date", ""),
            now=now,
        )


class LunarCalendar:
    """1900-2100 公历转农历及常见中西方节日查询。"""

    LUNAR_INFO = [
        0x04BD8, 0x04AE0, 0x0A570, 0x054D5, 0x0D260, 0x0D950, 0x16554, 0x056A0, 0x09AD0, 0x055D2,
        0x04AE0, 0x0A5B6, 0x0A4D0, 0x0D250, 0x1D255, 0x0B540, 0x0D6A0, 0x0ADA2, 0x095B0, 0x14977,
        0x04970, 0x0A4B0, 0x0B4B5, 0x06A50, 0x06D40, 0x1AB54, 0x02B60, 0x09570, 0x052F2, 0x04970,
        0x06566, 0x0D4A0, 0x0EA50, 0x06E95, 0x05AD0, 0x02B60, 0x186E3, 0x092E0, 0x1C8D7, 0x0C950,
        0x0D4A0, 0x1D8A6, 0x0B550, 0x056A0, 0x1A5B4, 0x025D0, 0x092D0, 0x0D2B2, 0x0A950, 0x0B557,
        0x06CA0, 0x0B550, 0x15355, 0x04DA0, 0x0A5B0, 0x14573, 0x052B0, 0x0A9A8, 0x0E950, 0x06AA0,
        0x0AEA6, 0x0AB50, 0x04B60, 0x0AAE4, 0x0A570, 0x05260, 0x0F263, 0x0D950, 0x05B57, 0x056A0,
        0x096D0, 0x04DD5, 0x04AD0, 0x0A4D0, 0x0D4D4, 0x0D250, 0x0D558, 0x0B540, 0x0B6A0, 0x195A6,
        0x095B0, 0x049B0, 0x0A974, 0x0A4B0, 0x0B27A, 0x06A50, 0x06D40, 0x0AF46, 0x0AB60, 0x09570,
        0x04AF5, 0x04970, 0x064B0, 0x074A3, 0x0EA50, 0x06B58, 0x055C0, 0x0AB60, 0x096D5, 0x092E0,
        0x0C960, 0x0D954, 0x0D4A0, 0x0DA50, 0x07552, 0x056A0, 0x0ABB7, 0x025D0, 0x092D0, 0x0CAB5,
        0x0A950, 0x0B4A0, 0x0BAA4, 0x0AD50, 0x055D9, 0x04BA0, 0x0A5B0, 0x15176, 0x052B0, 0x0A930,
        0x07954, 0x06AA0, 0x0AD50, 0x05B52, 0x04B60, 0x0A6E6, 0x0A4E0, 0x0D260, 0x0EA65, 0x0D530,
        0x05AA0, 0x076A3, 0x096D0, 0x04AFB, 0x04AD0, 0x0A4D0, 0x1D0B6, 0x0D250, 0x0D520, 0x0DD45,
        0x0B5A0, 0x056D0, 0x055B2, 0x049B0, 0x0A577, 0x0A4B0, 0x0AA50, 0x1B255, 0x06D20, 0x0ADA0,
        0x14B63, 0x09370, 0x049F8, 0x04970, 0x064B0, 0x168A6, 0x0EA50, 0x06B20, 0x1A6C4, 0x0AAE0,
        0x0A2E0, 0x0D2E3, 0x0C960, 0x0D557, 0x0D4A0, 0x0DA50, 0x05D55, 0x056A0, 0x0A6D0, 0x055D4,
        0x052D0, 0x0A9B8, 0x0A950, 0x0B4A0, 0x0B6A6, 0x0AD50, 0x055A0, 0x0ABA4, 0x0A5B0, 0x052B0,
        0x0B273, 0x06930, 0x07337, 0x06AA0, 0x0AD50, 0x14B55, 0x04B60, 0x0A570, 0x054E4, 0x0D160,
        0x0E968, 0x0D520, 0x0DAA0, 0x16AA6, 0x056D0, 0x04AE0, 0x0A9D4, 0x0A2D0, 0x0D150, 0x0F252,
        0x0D520,
    ]
    BASE_DATE = date(1900, 1, 31)
    CN_MONTHS = ["", "正月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "冬月", "腊月"]
    CN_DAYS = [
        "", "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
        "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
        "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十",
    ]
    SOLAR_FESTIVALS = {
        (1, 1): "元旦",
        (2, 14): "情人节",
        (3, 8): "妇女节",
        (3, 12): "植树节",
        (4, 1): "愚人节",
        (5, 1): "劳动节",
        (5, 4): "青年节",
        (6, 1): "儿童节",
        (7, 1): "建党节",
        (8, 1): "建军节",
        (9, 10): "教师节",
        (10, 1): "国庆节",
        (10, 31): "万圣夜",
        (11, 11): "双十一",
        (12, 24): "平安夜",
        (12, 25): "圣诞节",
    }
    LUNAR_FESTIVALS = {
        (1, 1): "春节",
        (1, 15): "元宵",
        (2, 2): "龙抬头",
        (5, 5): "端午",
        (7, 7): "七夕",
        (7, 15): "中元",
        (8, 15): "中秋",
        (9, 9): "重阳",
        (12, 8): "腊八",
        (12, 23): "小年",
    }

    @classmethod
    def _leap_month(cls, year: int) -> int:
        return cls.LUNAR_INFO[year - 1900] & 0xF

    @classmethod
    def _leap_days(cls, year: int) -> int:
        if cls._leap_month(year):
            return 30 if (cls.LUNAR_INFO[year - 1900] & 0x10000) else 29
        return 0

    @classmethod
    def _month_days(cls, year: int, month: int) -> int:
        return 30 if (cls.LUNAR_INFO[year - 1900] & (0x10000 >> month)) else 29

    @classmethod
    def _year_days(cls, year: int) -> int:
        total = 348
        info = cls.LUNAR_INFO[year - 1900]
        mask = 0x8000
        while mask > 0x8:
            if info & mask:
                total += 1
            mask >>= 1
        return total + cls._leap_days(year)

    @classmethod
    def solar_to_lunar(cls, d: date) -> Tuple[int, int, int, bool]:
        if d < cls.BASE_DATE or d.year > 2100:
            return d.year, d.month, d.day, False
        offset = (d - cls.BASE_DATE).days
        year = 1900
        while year <= 2100:
            ydays = cls._year_days(year)
            if offset < ydays:
                break
            offset -= ydays
            year += 1

        leap = cls._leap_month(year)
        is_leap = False
        month = 1
        while month <= 12:
            if leap > 0 and month == leap + 1 and not is_leap:
                month -= 1
                is_leap = True
                mdays = cls._leap_days(year)
            else:
                mdays = cls._month_days(year, month)
            if offset < mdays:
                break
            offset -= mdays
            if is_leap and month == leap:
                is_leap = False
            month += 1
        day = offset + 1
        return year, month, day, is_leap

    @classmethod
    def get_day_info(cls, d: date) -> Tuple[str, str, bool]:
        """返回 (格子底部短文本, 完整农历与节日说明, 是否节日高亮)。"""
        _, l_month, l_day, is_leap = cls.solar_to_lunar(d)
        m_prefix = "闰" if is_leap else ""
        lunar_str = f"{m_prefix}{cls.CN_MONTHS[l_month]}{cls.CN_DAYS[l_day]}"

        festivals: List[str] = []
        if not is_leap:
            lf = cls.LUNAR_FESTIVALS.get((l_month, l_day))
            if lf:
                festivals.append(lf)
            # 除夕判断：下一天是正月初一
            _, nm, nd, nl = cls.solar_to_lunar(d + timedelta(days=1))
            if not nl and nm == 1 and nd == 1:
                festivals.append("除夕")
        sf = cls.SOLAR_FESTIVALS.get((d.month, d.day))
        if sf:
            festivals.append(sf)

        if festivals:
            sub_text = festivals[0]
            return sub_text, f"农历{lunar_str} · {' / '.join(festivals)}", True
        if l_day == 1:
            return f"{m_prefix}{cls.CN_MONTHS[l_month]}", f"农历{lunar_str}", False
        return cls.CN_DAYS[l_day], f"农历{lunar_str}", False


class FastDownloader:
    """类 IDM 多线程高速下载引擎：基于 urllib 统一代理与 SSL 兼容，支持 8 线程 Range 并发分段与单线程流式无缝兜底。"""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    MAX_WORKERS = 6
    RANGE_THRESHOLD_BYTES = 5 * 1024 * 1024  # 5 MB
    CHUNK_BLOCK_BYTES = 16 * 1024 * 1024  # 16 MB
    MAX_BLOCK_RETRIES = 15
    READ_CHUNK_BYTES = 131072  # 128 KB
    WRITE_BUFFER_BYTES = 1024 * 1024  # 1 MB
    CN_MIRROR_HOSTS = (
        "mirrors.aliyun.com",
        "mirrors.tuna.tsinghua.edu.cn",
        "mirrors.ustc.edu.cn",
        "mirrors.163.com",
        "mirrors.cloud.tencent.com",
    )

    @classmethod
    def _is_cn_mirror_url(cls, url: str) -> bool:
        try:
            host = (urllib.parse.urlparse(url).hostname or "").lower()
            return any(host == m or host.endswith("." + m) for m in cls.CN_MIRROR_HOSTS)
        except Exception:
            return False

    @staticmethod
    def default_download_dir() -> str:
        d = os.path.join(os.path.expanduser("~"), "Downloads")
        if os.path.isdir(d):
            return d
        return os.path.expanduser("~")

    @staticmethod
    def _get_proxies() -> Dict[str, str]:
        raw = urllib.request.getproxies()
        cleaned: Dict[str, str] = {}
        for k, v in raw.items():
            if isinstance(v, str) and v.startswith("socks5h://"):
                cleaned[k] = "socks5://" + v[len("socks5h://"):]
            else:
                cleaned[k] = v
        return cleaned

    @staticmethod
    def _build_opener(bypass_proxy: bool = False) -> urllib.request.OpenerDirector:
        proxies = {} if bypass_proxy else urllib.request.getproxies()
        proxy_handler = urllib.request.ProxyHandler(proxies)
        https_handler = urllib.request.HTTPSHandler(context=ssl._create_unverified_context())
        return urllib.request.build_opener(proxy_handler, https_handler)

    @staticmethod
    def sanitize_filename(name: str) -> str:
        base = str(name or "").split("?")[0].split("#")[0]
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base).strip().strip(".")
        if not cleaned or "." not in cleaned:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"download_{ts}.bin" if not cleaned else f"{cleaned}.bin"
        return cleaned

    @staticmethod
    def format_size(num_bytes: int) -> str:
        if num_bytes < 1024:
            return f"{num_bytes} B"
        if num_bytes < 1024 * 1024:
            return f"{num_bytes / 1024:.1f} KB"
        if num_bytes < 1024 * 1024 * 1024:
            return f"{num_bytes / (1024 * 1024):.1f} MB"
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"

    @staticmethod
    def format_speed(bps: float) -> str:
        if bps < 1024 * 1024:
            return f"{bps / 1024:.1f} KB/s"
        return f"{bps / (1024 * 1024):.2f} MB/s"

    @classmethod
    def _extract_filename(cls, headers: Dict[str, Any], final_url: str) -> str:
        cd = ""
        for k, v in headers.items():
            if k.lower() == "content-disposition":
                cd = str(v)
                break
        if cd:
            m_star = re.search(r"filename\*\s*=\s*(?:UTF-8''|utf-8'')?([^;\r\n]+)", cd)
            if m_star:
                raw = urllib.parse.unquote(m_star.group(1).strip().strip('"').strip("'"))
                if raw:
                    return cls.sanitize_filename(raw)
            m_plain = re.search(r'filename\s*=\s*"?([^";\r\n]+)"?', cd)
            if m_plain:
                raw = urllib.parse.unquote(m_plain.group(1).strip().strip('"').strip("'"))
                if raw:
                    return cls.sanitize_filename(raw)

        parsed = urllib.parse.urlparse(final_url)
        tail = urllib.parse.unquote(os.path.basename(parsed.path)).split("?")[0].split("#")[0]
        if tail and "." in tail:
            return cls.sanitize_filename(tail)
        return cls.sanitize_filename("")

    @classmethod
    def _build_headers(
        cls,
        url: str,
        extra: Dict[str, str] | None = None,
        with_referer: bool = False,
    ) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "User-Agent": cls.USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if with_referer:
            try:
                parsed = urllib.parse.urlparse(url)
                if parsed.scheme and parsed.netloc:
                    headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
            except Exception:
                pass
        if extra:
            headers.update(extra)
        return headers

    @classmethod
    def _open_with_403_retry(
        cls,
        opener: urllib.request.OpenerDirector,
        url: str,
        extra_headers: Dict[str, str] | None = None,
        timeout: int = 15,
    ):
        req = urllib.request.Request(
            url,
            headers=cls._build_headers(url, extra_headers, with_referer=False),
            method="GET",
        )
        try:
            return opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                try:
                    exc.close()
                except Exception:
                    pass
                retry_req = urllib.request.Request(
                    url,
                    headers=cls._build_headers(url, extra_headers, with_referer=True),
                    method="GET",
                )
                return opener.open(retry_req, timeout=timeout)
            raise

    @classmethod
    def probe(cls, url: str, timeout: int = 15) -> Tuple[str, str, int, bool]:
        """使用不带 Range 的 GET 请求探测真实重定向地址、建议文件名、Content-Length 及 Accept-Ranges。"""
        opener = cls._build_opener()
        final_url = url
        total_bytes = 0
        supports_range = False
        resp_headers: Dict[str, Any] = {}

        try:
            with cls._open_with_403_retry(opener, url, timeout=timeout) as resp:
                final_url = resp.geturl() or url
                resp_headers = {k: v for k, v in resp.headers.items()}
                supports_range = "bytes" in str(resp.headers.get("Accept-Ranges") or "").lower()
                try:
                    total_bytes = int(resp.headers.get("Content-Length") or 0)
                except Exception:
                    total_bytes = 0
        except Exception:
            pass

        filename = cls._extract_filename(resp_headers, final_url)
        return final_url, filename, max(0, total_bytes), supports_range

    @classmethod
    def download_file(
        cls,
        url: str,
        dest_path: str,
        total_bytes: int,
        supports_range: bool,
        cancel_event: threading.Event,
        on_progress,
        pause_event: threading.Event | None = None,
        extra_headers: Dict[str, str] | None = None,
    ) -> str:
        """
        探测与下载一体化：
        1. 发起首个不带 Range 的 GET 请求获取重定向地址、Content-Length 与 Accept-Ranges；
        2. 仅当明确支持 Accept-Ranges: bytes 且 Content-Length > 5MB 时启用 6 线程队列并发分段（每片失败自动断点续传重试）；
        3. 支持 pause_event 线程安全暂停/继续与 cancel_event 即时中断清理；
        4. 每读取网络流即实时累加字节并按 80ms 高频回调进度。
        """
        is_cn_mirror = cls._is_cn_mirror_url(url)
        opener = cls._build_opener(bypass_proxy=is_cn_mirror)
        part_path = dest_path + ".part"
        _ensure_parent_dir(dest_path)

        downloaded_lock = threading.Lock()
        write_lock = threading.Lock()
        downloaded = 0
        errors: List[str] = []

        def _wait_if_paused() -> bool:
            """若处于暂停态则阻塞等待恢复或取消；返回 True 表示已取消。"""
            if pause_event is None:
                return cancel_event.is_set()
            while pause_event.is_set():
                if cancel_event.is_set():
                    return True
                time.sleep(0.05)
            return cancel_event.is_set()

        def _cleanup_part() -> None:
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except Exception:
                    pass

        def _stream_from_resp(resp, stream_total: int, desc: str) -> None:
            nonlocal downloaded
            downloaded = 0
            last_t = time.monotonic()
            last_b = 0
            with open(part_path, "wb", buffering=cls.WRITE_BUFFER_BYTES) as fh:
                while True:
                    if cancel_event.is_set():
                        break
                    if pause_event is not None and pause_event.is_set():
                        fh.flush()
                        if _wait_if_paused():
                            break
                        last_t = time.monotonic()
                        last_b = downloaded
                    piece = resp.read(cls.READ_CHUNK_BYTES)
                    if not piece:
                        break
                    fh.write(piece)
                    downloaded += len(piece)
                    if pause_event is not None and pause_event.is_set():
                        continue
                    now_t = time.monotonic()
                    if now_t - last_t >= 0.08:
                        dt = max(0.02, now_t - last_t)
                        speed = max(0.0, (downloaded - last_b) / dt)
                        last_t, last_b = now_t, downloaded
                        pct = min(100.0, (downloaded * 100.0) / max(1, stream_total)) if stream_total > 0 else 0.0
                        size_str = (
                            f"{cls.format_size(downloaded)} / {cls.format_size(stream_total)}"
                            if stream_total > 0
                            else f"{cls.format_size(downloaded)} / 未知大小"
                        )
                        on_progress(pct, cls.format_speed(speed), size_str, desc)

        def _download_single_fresh(target_url: str, stream_total: int, desc: str) -> None:
            errors.clear()
            _cleanup_part()
            try:
                with cls._open_with_403_retry(opener, target_url, extra_headers=extra_headers, timeout=20) as resp:
                    cl = stream_total
                    try:
                        hdr_cl = int(resp.headers.get("Content-Length") or 0)
                        if hdr_cl > 0:
                            cl = hdr_cl
                    except Exception:
                        pass
                    _stream_from_resp(resp, cl, desc)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")

        first_resp = None
        final_url = url
        cl = 0
        accept_ranges = False
        try:
            first_resp = cls._open_with_403_retry(opener, url, extra_headers=extra_headers, timeout=15)
        except Exception as first_exc:
            if is_cn_mirror:
                # 若国内镜像直连异常，回退系统代理再试一次
                opener = cls._build_opener(bypass_proxy=False)
                try:
                    first_resp = cls._open_with_403_retry(opener, url, extra_headers=extra_headers, timeout=15)
                except Exception as exc:
                    _cleanup_part()
                    raise RuntimeError(f"{type(exc).__name__}: {exc}")
            else:
                _cleanup_part()
                raise RuntimeError(f"{type(first_exc).__name__}: {first_exc}")

        try:
            final_url = first_resp.geturl() or url
            accept_ranges = "bytes" in str(first_resp.headers.get("Accept-Ranges") or "").lower()
            try:
                cl = int(first_resp.headers.get("Content-Length") or 0)
            except Exception:
                cl = 0
        except Exception as exc:
            if first_resp is not None:
                try:
                    first_resp.close()
                except Exception:
                    pass
            _cleanup_part()
            raise RuntimeError(f"{type(exc).__name__}: {exc}")

        use_multi = accept_ranges and cl > cls.RANGE_THRESHOLD_BYTES
        thread_desc = f"{cls.MAX_WORKERS} 线程并发" if use_multi else "单线程流式"

        if use_multi:
            try:
                first_resp.close()
            except Exception:
                pass

            with open(part_path, "wb") as f:
                f.seek(cl - 1)
                f.write(b"\0")

            # 将大文件切分为固定 16MB 小块放入线程安全队列，由 6 个工作线程并发消费
            task_queue: queue.Queue[Tuple[int, int]] = queue.Queue()
            block_size = cls.CHUNK_BLOCK_BYTES
            pos = 0
            while pos < cl:
                end_b = min(cl - 1, pos + block_size - 1)
                task_queue.put((pos, end_b))
                pos = end_b + 1

            workers_count = min(cls.MAX_WORKERS, max(1, task_queue.qsize()))
            thread_desc = f"{workers_count} 线程队列"

            def _download_block(start_b: int, end_b: int) -> None:
                nonlocal downloaded
                current_pos = start_b
                retries = 0

                while current_pos <= end_b:
                    if _wait_if_paused() or errors:
                        return
                    rng_extra = dict(extra_headers or {})
                    rng_extra["Range"] = f"bytes={current_pos}-{end_b}"
                    buf = bytearray()
                    write_offset = current_pos
                    try:
                        with cls._open_with_403_retry(opener, final_url, extra_headers=rng_extra, timeout=25) as resp:
                            status_code = getattr(resp, "status", None) or resp.getcode()
                            if status_code not in (200, 206):
                                raise RuntimeError(f"HTTP {status_code}")
                            with open(part_path, "r+b", buffering=cls.WRITE_BUFFER_BYTES) as fh:
                                try:
                                    while current_pos <= end_b:
                                        if cancel_event.is_set() or errors:
                                            return
                                        if pause_event is not None and pause_event.is_set():
                                            if buf:
                                                with write_lock:
                                                    fh.seek(write_offset)
                                                    fh.write(buf)
                                                write_offset += len(buf)
                                                buf.clear()
                                            fh.flush()
                                            if _wait_if_paused() or errors:
                                                return
                                        need = end_b - current_pos + 1
                                        piece = resp.read(min(cls.READ_CHUNK_BYTES, need))
                                        if not piece:
                                            break
                                        buf.extend(piece)
                                        current_pos += len(piece)
                                        with downloaded_lock:
                                            downloaded += len(piece)
                                        if len(buf) >= cls.WRITE_BUFFER_BYTES:
                                            with write_lock:
                                                fh.seek(write_offset)
                                                fh.write(buf)
                                            write_offset += len(buf)
                                            buf.clear()
                                finally:
                                    if buf and not cancel_event.is_set():
                                        with write_lock:
                                            fh.seek(write_offset)
                                            fh.write(buf)
                                        write_offset += len(buf)
                                        buf.clear()

                        if current_pos <= end_b:
                            if retries < cls.MAX_BLOCK_RETRIES:
                                retries += 1
                                time.sleep(min(1.5, 0.5 + (retries - 1) * 0.1))
                                continue
                            raise RuntimeError(f"分片断流({current_pos}/{end_b})")
                        return
                    except Exception as exc:
                        if retries < cls.MAX_BLOCK_RETRIES and not cancel_event.is_set() and not errors:
                            retries += 1
                            time.sleep(min(1.5, 0.5 + (retries - 1) * 0.1))
                            continue
                        with downloaded_lock:
                            errors.append(f"{type(exc).__name__}: {exc}")
                        return

            def _worker_loop() -> None:
                while not cancel_event.is_set() and not errors:
                    if _wait_if_paused() or errors:
                        return
                    try:
                        s_b, e_b = task_queue.get_nowait()
                    except queue.Empty:
                        return
                    try:
                        _download_block(s_b, e_b)
                    finally:
                        task_queue.task_done()

            executor = ThreadPoolExecutor(max_workers=workers_count)
            futures = [executor.submit(_worker_loop) for _ in range(workers_count)]
            try:
                last_t = time.monotonic()
                last_b = 0
                while not all(fut.done() for fut in futures):
                    if cancel_event.is_set() or errors:
                        break
                    if pause_event is not None and pause_event.is_set():
                        time.sleep(0.08)
                        last_t = time.monotonic()
                        with downloaded_lock:
                            last_b = downloaded
                        continue
                    time.sleep(0.08)
                    if pause_event is not None and pause_event.is_set():
                        continue
                    now_t = time.monotonic()
                    dt = max(0.02, now_t - last_t)
                    with downloaded_lock:
                        cur_b = downloaded
                    speed = max(0.0, (cur_b - last_b) / dt)
                    last_t, last_b = now_t, cur_b
                    pct = min(100.0, (cur_b * 100.0) / max(1, cl))
                    on_progress(
                        pct,
                        cls.format_speed(speed),
                        f"{cls.format_size(cur_b)} / {cls.format_size(cl)}",
                        thread_desc,
                    )
            finally:
                executor.shutdown(wait=True)
        else:
            try:
                with first_resp as resp:
                    _stream_from_resp(resp, cl, thread_desc)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")

        if cancel_event.is_set():
            _cleanup_part()
            raise InterruptedError("下载已取消")
        if errors:
            _cleanup_part()
            raise RuntimeError(errors[0])

        # 严格完整性与二进制包大小校验，杜绝“假完成”
        actual_size = os.path.getsize(part_path) if os.path.exists(part_path) else 0
        if cl > 0 and actual_size != cl:
            _cleanup_part()
            raise RuntimeError(f"传输中断({actual_size}/{cl})")
        bin_exts = (".exe", ".msi", ".iso", ".zip", ".7z", ".rar", ".tar", ".gz")
        if dest_path.lower().endswith(bin_exts) and actual_size < 10 * 1024:
            _cleanup_part()
            raise RuntimeError(f"文件异常过小({actual_size}B)")

        os.replace(part_path, dest_path)
        on_progress(100.0, "0.0 KB/s", f"{cls.format_size(actual_size)} / {cls.format_size(actual_size)}", thread_desc)
        return dest_path


class LanTransferServer:
    """局域网手机电脑双向互传 HTTP 服务（ThreadingHTTPServer + 免装 App H5 页面）。"""

    DEFAULT_PORT = 8989

    def __init__(
        self,
        receive_dir: str | None = None,
        on_receive_text=None,
        on_receive_file=None,
        theme_mode: str = "dark",
        accent_color: str = "#FF6B00",
    ):
        exe_root = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else BASE_DIR
        self.receive_dir = receive_dir or os.path.join(exe_root, "手机互传接收")
        self._on_receive_text = on_receive_text
        self._on_receive_file = on_receive_file
        self._lock = threading.Lock()
        self._shared_items_by_mode: Dict[str, List[Dict[str, Any]]] = {"lan": [], "internet": []}
        self._chat_messages_by_mode: Dict[str, List[Dict[str, Any]]] = {"lan": [], "internet": []}
        self._active_chat_mode: str = "lan"
        self._media_files: Dict[str, str] = {}
        self._device_labels: Dict[str, str] = {}
        self._device_avatars: Dict[str, int] = {}
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port: int = self.DEFAULT_PORT
        self.ip: str = self.get_lan_ip()
        self._firewall_checked: bool = False
        self._theme: Dict[str, str] = self.get_theme_palette(theme_mode, accent_color)
        self._access_token: str = ""
        self._internet_token: str = ""
        self._load_chat_messages_cache()

    ACCESS_TOKEN_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"

    def generate_access_token(self, length: int = 6) -> str:
        n = max(4, min(6, int(length or 6)))
        tok = "".join(secrets.choice(self.ACCESS_TOKEN_ALPHABET) for _ in range(n))
        with self._lock:
            self._access_token = tok
        return tok

    def set_access_token(self, token: str) -> None:
        with self._lock:
            self._access_token = str(token or "").strip()

    def get_access_token(self) -> str:
        with self._lock:
            return self._access_token

    def set_internet_token(self, token: str) -> None:
        with self._lock:
            self._internet_token = str(token or "").strip()

    def get_internet_token(self) -> str:
        with self._lock:
            return self._internet_token

    def get_active_token(self) -> str:
        with self._lock:
            return self._internet_token or self._access_token

    @staticmethod
    def get_theme_palette(theme_mode: str, accent_color: str) -> Dict[str, str]:
        if theme_mode == "light":
            return {
                "mode": "light",
                "bg": "#ededed",
                "nav_bg": "#f7f7f7",
                "chat_bg": "#ededed",
                "card_bg": "#ffffff",
                "bubble_pc": "#ffffff",
                "input_bar_bg": "#f7f7f7",
                "panel_bg": "#f2f2f2",
                "input_bg": "#ffffff",
                "fg": "#18181c",
                "sub_fg": "#7a7d87",
                "border": "#e2e4ea",
                "accent": accent_color,
            }
        return {
            "mode": "dark",
            "bg": "#111114",
            "nav_bg": "#18181d",
            "chat_bg": "#111114",
            "card_bg": "#1e1e25",
            "bubble_pc": "#22222a",
            "input_bar_bg": "#18181d",
            "panel_bg": "#15151a",
            "input_bg": "#24242d",
            "fg": "#f5f5f7",
            "sub_fg": "#8c8c9a",
            "border": "#2a2a34",
            "accent": accent_color,
        }

    def set_theme(self, theme_mode: str, accent_color: str) -> None:
        pal = self.get_theme_palette(theme_mode, accent_color)
        with self._lock:
            self._theme = pal

    def get_theme(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._theme)

    def set_receive_dir(self, receive_dir: str) -> None:
        with self._lock:
            self.receive_dir = receive_dir

    @staticmethod
    def _is_valid_lan_ip(ip: str) -> bool:
        if not ip:
            return False
        bad_prefixes = ("127.", "169.254.", "198.18.", "198.19.", "192.168.56.", "192.168.137.", "0.")
        return not any(ip.startswith(p) for p in bad_prefixes)

    @classmethod
    def get_lan_ip(cls) -> str:
        candidates: List[str] = []
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("223.5.5.5", 80))
            udp_ip = s.getsockname()[0]
            if cls._is_valid_lan_ip(udp_ip):
                candidates.append(udp_ip)
        except Exception:
            pass
        finally:
            s.close()

        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                addr = str(info[4][0])
                if cls._is_valid_lan_ip(addr) and addr not in candidates:
                    candidates.append(addr)
        except Exception:
            pass

        for prefix in ("192.168.", "10."):
            for addr in candidates:
                if addr.startswith(prefix):
                    return addr
        for addr in candidates:
            if addr.startswith("172."):
                try:
                    second = int(addr.split(".")[1])
                    if 16 <= second <= 31:
                        return addr
                except Exception:
                    pass
        return candidates[0] if candidates else "127.0.0.1"

    def _ensure_firewall_rule_async(self) -> None:
        if self._firewall_checked:
            return
        self._firewall_checked = True

        def _worker() -> None:
            if os.name != "nt":
                return
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            rule_name = "IdleMeterLAN"
            try:
                chk = subprocess.run(
                    ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
                    capture_output=True,
                    creationflags=flags,
                    timeout=5,
                )
                if chk.returncode != 0:
                    subprocess.run(
                        [
                            "netsh",
                            "advfirewall",
                            "firewall",
                            "add",
                            "rule",
                            f"name={rule_name}",
                            "dir=in",
                            "action=allow",
                            f"program={sys.executable}",
                            "enable=yes",
                            "profile=private,domain,public",
                        ],
                        capture_output=True,
                        creationflags=flags,
                        timeout=5,
                    )
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def is_running(self) -> bool:
        return self._server is not None

    def get_base_url(self) -> str:
        return f"http://{self.ip}:{self.port}"

    def get_url(self, with_token: bool = True) -> str:
        base = f"http://{self.ip}:{self.port}"
        if not with_token:
            return base
        tok = self.get_active_token()
        return f"{base}/?token={tok}" if tok else base

    IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic", ".svg", ".ico")
    AUDIO_EXTS = (".webm", ".m4a", ".mp3", ".wav", ".ogg", ".aac", ".opus", ".amr")

    @classmethod
    def _classify_file_kind(cls, filename: str) -> str:
        low = os.path.basename(str(filename or "")).lower()
        ext = os.path.splitext(low)[1]
        if ext in cls.IMAGE_EXTS:
            return "image"
        if ext in cls.AUDIO_EXTS or (ext == ".mp4" and low.startswith("voice_")):
            return "audio"
        return "file"

    @staticmethod
    def _guess_mime_type(file_path: str) -> str:
        low = os.path.basename(str(file_path or "")).lower()
        ext = os.path.splitext(low)[1]
        explicit = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".svg": "image/svg+xml",
            ".webm": "audio/webm",
            ".m4a": "audio/mp4",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".aac": "audio/aac",
            ".opus": "audio/opus",
            ".mp4": "audio/mp4" if low.startswith("voice_") else "video/mp4",
        }
        if ext in explicit:
            return explicit[ext]
        guessed, _ = mimetypes.guess_type(file_path)
        return guessed or "application/octet-stream"

    @staticmethod
    def _public_chat_msg(m: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": m["id"],
            "direction": m["direction"],
            "msg_type": m["msg_type"],
            "device_id": m.get("device_id", ""),
            "sender_name": m.get("sender_name", "电脑端" if m["direction"] == "pc" else "手机端-1"),
            "avatar_idx": int(m.get("avatar_idx", 0 if m["direction"] == "pc" else 1)),
            "name": m.get("name", ""),
            "text": m.get("text", ""),
            "size": m.get("size", 0),
            "size_str": m.get("size_str", ""),
            "duration": m.get("duration", 0),
            "time_str": m.get("time_str", ""),
            "ts": m.get("ts", 0.0),
        }

    def resolve_phone_device(self, device_id: str) -> Tuple[str, str, int]:
        """根据手机 device_id 分配持久化的设备名（手机端-1 / 手机端-2 ...）与专属头像索引（1..5）。"""
        did = str(device_id or "").strip() or "PHONE-DEFAULT"
        with self._lock:
            if did not in self._device_labels:
                seq = len(self._device_labels) + 1
                self._device_labels[did] = f"手机端-{seq}"
                # 按设备 ID 哈希确定性分配 1..5 专属头像风格（前 5 台优先不撞色）
                if seq <= 5:
                    av_idx = seq
                else:
                    h = sum((i + 1) * ord(ch) for i, ch in enumerate(did))
                    av_idx = (h % 5) + 1
                self._device_avatars[did] = av_idx
            return did, self._device_labels[did], self._device_avatars[did]

    def _normalize_mode_locked(self, mode: str | None = None) -> str:
        raw = str(mode or "").strip().lower()
        if raw in ("lan", "internet"):
            return raw
        return self._active_chat_mode if self._active_chat_mode in ("lan", "internet") else "lan"

    def set_active_mode(self, mode: str) -> str:
        norm = "internet" if str(mode or "").strip().lower() == "internet" else "lan"
        with self._lock:
            self._active_chat_mode = norm
        return norm

    def get_active_mode(self) -> str:
        with self._lock:
            return self._active_chat_mode

    def _load_chat_messages_cache(self) -> None:
        """从 messages_cache.json 独立加载局域网 (lan) 与互联网 (internet) 聊天记录，互不串读。"""
        if not os.path.exists(MESSAGES_CACHE_FILE):
            return
        try:
            with open(MESSAGES_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            cm = data.get("chat_messages")
            if not isinstance(cm, dict):
                return
            with self._lock:
                for mkey in ("lan", "internet"):
                    raw_list = cm.get(mkey)
                    if isinstance(raw_list, list):
                        cleaned = [dict(x) for x in raw_list if isinstance(x, dict) and x.get("id")][-120:]
                        self._chat_messages_by_mode[mkey] = cleaned
                        for item in cleaned:
                            fp = str(item.get("file_path") or "")
                            if fp and os.path.isfile(fp):
                                self._media_files[str(item["id"])] = fp
        except Exception:
            pass

    def _save_chat_messages_cache_locked(self) -> None:
        """将局域网 (lan) 与互联网 (internet) 两个独立聊天队列持久化至 messages_cache.json，保留其他缓存键。"""
        try:
            data: Dict[str, Any] = {}
            if os.path.exists(MESSAGES_CACHE_FILE):
                try:
                    with open(MESSAGES_CACHE_FILE, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data = loaded
                except Exception:
                    data = {}
            data["chat_messages"] = {
                "lan": [dict(m) for m in self._chat_messages_by_mode["lan"][-120:]],
                "internet": [dict(m) for m in self._chat_messages_by_mode["internet"][-120:]],
            }
            _ensure_parent_dir(MESSAGES_CACHE_FILE)
            with open(MESSAGES_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def clear_chat_messages(self, mode: str | None = None) -> None:
        """清空内存中及 messages_cache.json 中的聊天记录与会话列表；严格保留本地已接收的图片和文件，不删除任何磁盘文件。"""
        with self._lock:
            targets = [self._normalize_mode_locked(mode)] if mode else ["lan", "internet"]
            removed_ids = set()
            for mkey in targets:
                for m in self._chat_messages_by_mode[mkey]:
                    mid = m.get("id")
                    if mid:
                        removed_ids.add(mid)
                for x in self._shared_items_by_mode[mkey]:
                    xid = x.get("id")
                    if xid:
                        removed_ids.add(xid)
                self._chat_messages_by_mode[mkey] = []
                self._shared_items_by_mode[mkey] = []
            for rid in removed_ids:
                self._media_files.pop(rid, None)
            self._save_chat_messages_cache_locked()

    def add_shared_text(self, text: str, mode: str | None = None) -> Dict[str, Any]:
        raw = str(text or "")
        single = " ".join(raw.strip().splitlines())
        now_t = datetime.now().strftime("%H:%M:%S")
        ts = time.time()
        item_id = uuid.uuid4().hex[:10]
        item = {
            "id": item_id,
            "kind": "text",
            "name": single[:60] + ("..." if len(single) > 60 else ""),
            "text": raw,
            "file_path": "",
            "size": len(raw.encode("utf-8")),
            "size_str": f"{len(raw)} 字",
            "time_str": now_t,
        }
        chat_msg = {
            "id": item_id,
            "direction": "pc",
            "msg_type": "text",
            "device_id": "PC",
            "sender_name": "电脑端",
            "avatar_idx": 0,
            "name": item["name"],
            "text": raw,
            "size": item["size"],
            "size_str": item["size_str"],
            "duration": 0,
            "time_str": now_t[:5],
            "ts": ts,
        }
        with self._lock:
            mkey = self._normalize_mode_locked(mode)
            shared = self._shared_items_by_mode[mkey]
            shared[:] = [x for x in shared if not (x["kind"] == "text" and x["text"] == raw)]
            shared.insert(0, item)
            msgs = self._chat_messages_by_mode[mkey]
            msgs.append(chat_msg)
            self._chat_messages_by_mode[mkey] = msgs[-120:]
            self._save_chat_messages_cache_locked()
        return item

    def add_shared_file(self, file_path: str, mode: str | None = None) -> Dict[str, Any] | None:
        if not file_path or not os.path.isfile(file_path):
            return None
        size = os.path.getsize(file_path)
        now_t = datetime.now().strftime("%H:%M:%S")
        ts = time.time()
        item_id = uuid.uuid4().hex[:10]
        fname = os.path.basename(file_path)
        msg_type = self._classify_file_kind(fname)
        item = {
            "id": item_id,
            "kind": "file",
            "name": fname,
            "text": "",
            "file_path": file_path,
            "size": size,
            "size_str": FastDownloader.format_size(size),
            "time_str": now_t,
        }
        chat_msg = {
            "id": item_id,
            "direction": "pc",
            "msg_type": msg_type,
            "device_id": "PC",
            "sender_name": "电脑端",
            "avatar_idx": 0,
            "name": fname,
            "text": "",
            "file_path": file_path,
            "size": size,
            "size_str": item["size_str"],
            "duration": 0,
            "time_str": now_t[:5],
            "ts": ts,
        }
        with self._lock:
            mkey = self._normalize_mode_locked(mode)
            shared = self._shared_items_by_mode[mkey]
            shared[:] = [x for x in shared if not (x["kind"] == "file" and x["file_path"] == file_path)]
            shared.insert(0, item)
            self._media_files[item_id] = file_path
            msgs = self._chat_messages_by_mode[mkey]
            msgs.append(chat_msg)
            self._chat_messages_by_mode[mkey] = msgs[-120:]
            self._save_chat_messages_cache_locked()
        return item

    def record_phone_text(self, text: str, device_id: str = "", mode: str | None = None) -> Dict[str, Any]:
        raw = str(text or "")
        did, sname, av_idx = self.resolve_phone_device(device_id)
        now_t = datetime.now().strftime("%H:%M")
        msg = {
            "id": uuid.uuid4().hex[:10],
            "direction": "phone",
            "msg_type": "text",
            "device_id": did,
            "sender_name": sname,
            "avatar_idx": av_idx,
            "name": "",
            "text": raw,
            "size": len(raw.encode("utf-8")),
            "size_str": f"{len(raw)} 字",
            "duration": 0,
            "time_str": now_t,
            "ts": time.time(),
        }
        with self._lock:
            mkey = self._normalize_mode_locked(mode)
            msgs = self._chat_messages_by_mode[mkey]
            msgs.append(msg)
            self._chat_messages_by_mode[mkey] = msgs[-120:]
            self._save_chat_messages_cache_locked()
        return self._public_chat_msg(msg)

    def record_phone_file(
        self,
        file_path: str,
        duration: int = 0,
        device_id: str = "",
        mode: str | None = None,
    ) -> Dict[str, Any]:
        fname = os.path.basename(file_path)
        size = os.path.getsize(file_path) if os.path.isfile(file_path) else 0
        msg_type = self._classify_file_kind(fname)
        did, sname, av_idx = self.resolve_phone_device(device_id)
        msg_id = uuid.uuid4().hex[:10]
        msg = {
            "id": msg_id,
            "direction": "phone",
            "msg_type": msg_type,
            "device_id": did,
            "sender_name": sname,
            "avatar_idx": av_idx,
            "name": fname,
            "text": "",
            "file_path": file_path,
            "size": size,
            "size_str": FastDownloader.format_size(size),
            "duration": max(0, int(duration or 0)),
            "time_str": datetime.now().strftime("%H:%M"),
            "ts": time.time(),
        }
        with self._lock:
            mkey = self._normalize_mode_locked(mode)
            self._media_files[msg_id] = file_path
            msgs = self._chat_messages_by_mode[mkey]
            msgs.append(msg)
            self._chat_messages_by_mode[mkey] = msgs[-120:]
            self._save_chat_messages_cache_locked()
        return self._public_chat_msg(msg)

    def remove_shared_item(self, item_id: str, mode: str | None = None) -> None:
        with self._lock:
            targets = [self._normalize_mode_locked(mode)] if mode else ["lan", "internet"]
            for mkey in targets:
                self._shared_items_by_mode[mkey] = [
                    x for x in self._shared_items_by_mode[mkey] if x["id"] != item_id
                ]
                self._chat_messages_by_mode[mkey] = [
                    m for m in self._chat_messages_by_mode[mkey] if m["id"] != item_id
                ]
            self._media_files.pop(item_id, None)
            self._save_chat_messages_cache_locked()

    def list_shared_items(self, mode: str | None = None) -> List[Dict[str, Any]]:
        with self._lock:
            mkey = self._normalize_mode_locked(mode)
            return [dict(x) for x in self._shared_items_by_mode[mkey]]

    def list_chat_messages(self, mode: str | None = None) -> List[Dict[str, Any]]:
        with self._lock:
            mkey = self._normalize_mode_locked(mode)
            return [self._public_chat_msg(m) for m in self._chat_messages_by_mode[mkey]]

    def resolve_media_path(self, item_id: str) -> str | None:
        with self._lock:
            fp = self._media_files.get(item_id)
            if fp and os.path.isfile(fp):
                return fp
            for mkey in ("lan", "internet"):
                for x in self._shared_items_by_mode[mkey]:
                    if x["id"] == item_id and x["kind"] == "file" and os.path.isfile(x["file_path"]):
                        return x["file_path"]
        return None

    def _unique_receive_path(self, filename: str) -> str:
        os.makedirs(self.receive_dir, exist_ok=True)
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", os.path.basename(filename or "upload.bin")).strip() or "upload.bin"
        stem, ext = os.path.splitext(safe)
        candidate = os.path.join(self.receive_dir, safe)
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(self.receive_dir, f"{stem} ({idx}){ext}")
            idx += 1
        return candidate

    def _build_h5_html(self) -> bytes:
        t = self.get_theme()
        is_internet = bool(self.get_internet_token())
        init_conn_text = "公网加密隧道已连接" if is_internet else "局域网直连"
        template = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover, interactive-widget=resizes-content">
<title>文件传输助手</title>
<style>
  :root {
    --bg: __BG__;
    --nav-bg: __NAV_BG__;
    --chat-bg: __CHAT_BG__;
    --card: __CARD_BG__;
    --bubble-pc: __BUBBLE_PC__;
    --input-bar-bg: __INPUT_BAR_BG__;
    --panel-bg: __PANEL_BG__;
    --input-bg: __INPUT_BG__;
    --fg: __FG__;
    --sub-fg: __SUB_FG__;
    --border: __BORDER__;
    --accent: __ACCENT__;
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body {
    margin: 0; padding: 0; width: 100%; height: 100%;
    overflow: hidden; overscroll-behavior: none;
    position: fixed; left: 0; top: 0;
    background: var(--chat-bg);
    color: var(--fg);
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", "Microsoft YaHei", sans-serif;
    transition: background 0.22s, color 0.22s;
  }
  input, textarea {
    font-size: 16px;
  }
  #app, .app {
    display: flex; flex-direction: column;
    width: 100%; height: 100vh; height: 100dvh;
    overflow: hidden;
    background: var(--chat-bg);
    will-change: height, transform;
  }

  /* 顶部仿微信吸顶导航栏 */
  .navbar {
    flex-shrink: 0;
    position: sticky; top: 0; z-index: 20;
    background: var(--nav-bg);
    border-bottom: 1px solid var(--border);
    padding: calc(10px + env(safe-area-inset-top, 0px)) 16px 10px 16px;
    display: flex; align-items: center; justify-content: space-between;
    transition: background 0.22s, border-color 0.22s;
  }
  .nav-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .nav-avatar {
    width: 34px; height: 34px; border-radius: 9px;
    background: var(--accent); color: #fff;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }
  .nav-meta { display: flex; flex-direction: column; min-width: 0; }
  .nav-title { font-size: 16px; font-weight: 600; line-height: 1.25; color: var(--fg); }
  .nav-status {
    display: flex; align-items: center; gap: 5px;
    font-size: 11px; color: var(--sub-fg); margin-top: 2px;
  }
  .status-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: #10b981; flex-shrink: 0;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.22);
  }

  /* 中间聊天气泡流 */
  .chat-scroll {
    flex: 1; min-height: 0;
    overflow-y: auto; -webkit-overflow-scrolling: touch;
    padding: 14px 12px 18px 12px;
    display: flex; flex-direction: column; gap: 12px;
  }
  .empty-hint {
    margin: auto; text-align: center; padding: 28px 20px;
    color: var(--sub-fg); font-size: 13px; line-height: 1.7;
  }
  .empty-hint .badge {
    display: inline-flex; align-items: center; justify-content: center;
    width: 48px; height: 48px; border-radius: 14px;
    background: var(--card); border: 1px solid var(--border);
    color: var(--accent); margin-bottom: 10px;
  }
  .time-divider {
    align-self: center;
    font-size: 11px; color: var(--sub-fg);
    background: rgba(128, 128, 140, 0.12);
    padding: 2px 10px; border-radius: 10px;
    margin: 2px 0;
  }

  .msg-row {
    display: flex; align-items: flex-start; gap: 8px;
    max-width: 100%;
  }
  .msg-row.me { flex-direction: row-reverse; }
  .msg-avatar {
    width: 34px; height: 34px; border-radius: 9px;
    flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700;
    overflow: hidden;
  }
  .msg-sender {
    font-size: 10px; color: var(--sub-fg);
    margin-bottom: 3px; padding: 0 2px;
  }
  .msg-col {
    display: flex; flex-direction: column;
    max-width: calc(100% - 86px);
    align-items: flex-start;
  }
  .msg-row.me .msg-col { align-items: flex-end; }
  .msg-sub {
    font-size: 10px; color: var(--sub-fg);
    margin-top: 4px; padding: 0 2px;
  }
  .msg-sub.ok { color: #10b981; }
  .msg-sub.err { color: #ef4444; }

  /* 文本气泡 */
  .bubble-text {
    position: relative;
    padding: 10px 13px;
    border-radius: 12px;
    font-size: 15px; line-height: 1.5;
    word-break: break-word; white-space: pre-wrap;
    user-select: text;
    transition: opacity 0.15s, background 0.22s;
  }
  .msg-row.pc .bubble-text {
    background: var(--bubble-pc); color: var(--fg);
    border: 1px solid var(--border);
    border-top-left-radius: 4px;
    cursor: pointer;
  }
  .msg-row.pc .bubble-text:active { opacity: 0.78; }
  .msg-row.me .bubble-text {
    background: var(--accent); color: #ffffff;
    border-top-right-radius: 4px;
  }

  /* 图片气泡 */
  .bubble-img-wrap {
    position: relative;
    border-radius: 10px; overflow: hidden;
    background: var(--card); border: 1px solid var(--border);
    max-width: 210px; min-width: 80px; min-height: 80px;
    cursor: pointer;
  }
  .bubble-img-wrap img {
    display: block; max-width: 210px; max-height: 240px;
    width: auto; height: auto; object-fit: cover;
  }
  .img-progress-mask {
    position: absolute; inset: 0;
    background: rgba(0, 0, 0, 0.48);
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    color: #fff; font-size: 13px; font-weight: 600; gap: 6px;
  }
  .img-progress-mask.hidden { display: none; }

  /* 文件卡片气泡 */
  .bubble-file {
    width: 236px; max-width: 100%;
    background: var(--card); color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 11px; padding: 11px 12px;
    display: flex; flex-direction: column; gap: 8px;
    cursor: pointer; text-decoration: none;
    transition: background 0.22s, border-color 0.22s;
  }
  .bubble-file:active { opacity: 0.82; }
  .file-top { display: flex; align-items: center; gap: 10px; }
  .file-info { flex: 1; min-width: 0; }
  .file-name {
    font-size: 14px; font-weight: 500; color: var(--fg);
    line-height: 1.35;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; word-break: break-all;
  }
  .file-meta { font-size: 11px; color: var(--sub-fg); margin-top: 4px; }
  .file-badge {
    width: 40px; height: 44px; border-radius: 7px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 700; color: #fff; letter-spacing: 0.3px;
  }
  .file-prog-track {
    width: 100%; height: 4px; border-radius: 2px;
    background: rgba(128, 128, 140, 0.2); overflow: hidden;
  }
  .file-prog-track.hidden { display: none; }
  .file-prog-fill {
    height: 100%; width: 0%; background: var(--accent);
    border-radius: 2px; transition: width 0.12s linear;
  }

  /* 语音条气泡 */
  .bubble-voice {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 9px 13px; border-radius: 12px;
    min-width: 88px; max-width: 210px;
    cursor: pointer; user-select: none;
    font-size: 14px; font-weight: 500;
  }
  .msg-row.pc .bubble-voice {
    background: var(--bubble-pc); color: var(--fg);
    border: 1px solid var(--border);
    border-top-left-radius: 4px;
  }
  .msg-row.me .bubble-voice {
    background: var(--accent); color: #fff;
    border-top-right-radius: 4px;
    flex-direction: row-reverse;
  }
  .voice-wave-svg { width: 18px; height: 18px; flex-shrink: 0; }
  .msg-row.me .voice-wave-svg { transform: scaleX(-1); }
  .bubble-voice.playing .vw-arc2 { animation: vwBlink 0.9s infinite 0.15s; }
  .bubble-voice.playing .vw-arc3 { animation: vwBlink 0.9s infinite 0.35s; }
  @keyframes vwBlink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.2; }
  }

  /* 底部仿微信输入栏（Flex 自然沉底，杜绝 iOS fixed 悬浮错位） */
  .bottom-dock {
    flex-shrink: 0;
    background: var(--input-bar-bg);
    border-top: 1px solid var(--border);
    padding-bottom: max(8px, env(safe-area-inset-bottom, 0px));
    transition: background 0.22s, border-color 0.22s;
  }
  #app.keyboard-open .bottom-dock {
    padding-bottom: 8px;
  }
  .input-bar {
    display: flex; align-items: flex-end; gap: 8px;
    padding: 8px 10px 0 10px;
  }
  .icon-btn {
    width: 34px; height: 34px; flex-shrink: 0;
    border-radius: 50%; border: none; background: transparent;
    color: var(--fg); cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    padding: 0;
  }
  .icon-btn:active { opacity: 0.6; }
  .input-wrap {
    flex: 1; min-width: 0;
    display: flex; align-items: center;
  }
  .msg-input {
    width: 100%; min-height: 36px; max-height: 104px;
    border-radius: 8px; border: 1px solid var(--border);
    background: var(--input-bg); color: var(--fg);
    padding: 7px 11px; font-size: 16px; line-height: 21px;
    resize: none; outline: none; overflow-y: auto;
    font-family: inherit;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .msg-input:focus { border-color: var(--accent); }
  .msg-input.pulse-highlight {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(255, 107, 0, 0.22);
  }
  .voice-hold-btn {
    width: 100%; height: 36px;
    border-radius: 8px; border: 1px solid var(--border);
    background: var(--input-bg); color: var(--fg);
    font-size: 14px; font-weight: 600;
    display: none; align-items: center; justify-content: center;
    cursor: pointer; user-select: none; -webkit-user-select: none;
    -webkit-touch-callout: none; touch-action: none;
  }
  .voice-hold-btn.show { display: flex; }
  .voice-hold-btn.recording {
    background: rgba(128, 128, 140, 0.24);
    border-color: var(--accent);
    color: var(--accent);
  }
  .send-btn {
    height: 34px; padding: 0 13px; flex-shrink: 0;
    border-radius: 8px; border: none;
    background: var(--accent); color: #fff;
    font-size: 14px; font-weight: 600; cursor: pointer;
    display: none; align-items: center; justify-content: center;
  }
  .send-btn.show { display: inline-flex; }
  .send-btn:active { opacity: 0.82; }

  /* 底部互斥展开面板：表情面板 & 加号宫格抽屉 */
  .drawer-container {
    background: var(--panel-bg);
    border-top: 1px solid var(--border);
    overflow: hidden;
    max-height: 0;
    transition: max-height 0.24s cubic-bezier(0.22, 1, 0.36, 1);
  }
  .drawer-container.open { max-height: 260px; }

  .emoji-panel {
    display: none; position: relative;
    height: 230px; padding: 10px 10px 44px 10px;
    overflow-y: auto; -webkit-overflow-scrolling: touch;
  }
  .emoji-panel.active { display: block; }
  .emoji-grid {
    display: grid; grid-template-columns: repeat(8, 1fr);
    gap: 4px;
  }
  .emoji-item {
    height: 38px; border: none; background: transparent;
    font-size: 23px; border-radius: 8px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    padding: 0;
  }
  .emoji-item:active { background: rgba(128, 128, 140, 0.18); transform: scale(1.1); }
  .emoji-backspace {
    position: sticky; bottom: 0; float: right;
    margin-top: -34px; margin-right: 4px;
    width: 48px; height: 34px; border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--card); color: var(--fg);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  }
  .emoji-backspace:active { opacity: 0.72; }

  .plus-panel {
    display: none; padding: 18px 16px 20px 16px;
  }
  .plus-panel.active { display: block; }
  .plus-grid {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
  }
  .plus-card {
    display: flex; flex-direction: column; align-items: center; gap: 7px;
    background: transparent; border: none; cursor: pointer; padding: 0;
    color: var(--sub-fg); font-size: 12px;
  }
  .plus-icon-box {
    width: 56px; height: 56px; border-radius: 14px;
    background: var(--card); border: 1px solid var(--border);
    color: var(--fg);
    display: flex; align-items: center; justify-content: center;
    transition: transform 0.12s, border-color 0.15s;
  }
  .plus-card:active .plus-icon-box { transform: scale(0.94); border-color: var(--accent); color: var(--accent); }

  /* 屏幕中央录音动态声波悬浮 HUD */
  .rec-hud {
    position: fixed; left: 50%; top: 44%; transform: translate(-50%, -50%);
    width: 158px; padding: 18px 14px 14px 14px;
    border-radius: 16px;
    background: rgba(20, 20, 26, 0.86); color: #fff;
    backdrop-filter: blur(8px);
    display: none; flex-direction: column; align-items: center; gap: 10px;
    z-index: 60; pointer-events: none;
  }
  .rec-hud.show { display: flex; }
  .rec-waves {
    display: flex; align-items: center; justify-content: center;
    gap: 4px; height: 34px;
  }
  .rec-bar {
    width: 4px; border-radius: 2px; background: var(--accent);
    animation: recBounce 0.65s ease-in-out infinite alternate;
  }
  .rec-bar:nth-child(1) { height: 12px; animation-delay: 0.00s; }
  .rec-bar:nth-child(2) { height: 24px; animation-delay: 0.12s; }
  .rec-bar:nth-child(3) { height: 32px; animation-delay: 0.24s; }
  .rec-bar:nth-child(4) { height: 22px; animation-delay: 0.16s; }
  .rec-bar:nth-child(5) { height: 30px; animation-delay: 0.08s; }
  .rec-bar:nth-child(6) { height: 16px; animation-delay: 0.28s; }
  @keyframes recBounce {
    from { transform: scaleY(0.35); opacity: 0.65; }
    to { transform: scaleY(1.0); opacity: 1; }
  }
  .rec-sec { font-size: 16px; font-weight: 700; letter-spacing: 0.5px; }
  .rec-tip { font-size: 11px; color: rgba(255, 255, 255, 0.78); }

  /* 图片全屏放大预览灯箱 */
  .lightbox {
    position: fixed; inset: 0; z-index: 80;
    background: rgba(0, 0, 0, 0.92);
    display: none; flex-direction: column; align-items: center; justify-content: center;
    padding: 20px;
  }
  .lightbox.show { display: flex; }
  .lightbox img {
    max-width: 100%; max-height: 82vh; object-fit: contain; border-radius: 6px;
  }
  .lightbox-actions {
    margin-top: 16px; display: flex; gap: 12px;
  }
  .lb-btn {
    padding: 8px 18px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.28);
    background: rgba(255,255,255,0.14); color: #fff; font-size: 13px;
    text-decoration: none; cursor: pointer;
  }

  /* 轻量 Toast */
  .toast {
    position: fixed; left: 50%; top: 68px; transform: translateX(-50%) translateY(-8px);
    max-width: 84vw; padding: 9px 16px; border-radius: 10px;
    background: rgba(22, 22, 28, 0.90); color: #fff;
    font-size: 13px; text-align: center; line-height: 1.4;
    z-index: 90; opacity: 0; pointer-events: none;
    transition: opacity 0.2s, transform 0.2s;
  }
  .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
</style>
</head>
<body>
<div id="app" class="app">
  <!-- 顶部导航栏 -->
  <header class="navbar">
    <div class="nav-left">
      <div class="nav-avatar" aria-hidden="true">
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/>
        </svg>
      </div>
      <div class="nav-meta">
        <div class="nav-title">文件传输助手</div>
        <div class="nav-status">
          <span class="status-dot"></span>
          <span id="connStatus">__INIT_CONN_TEXT__</span>
        </div>
      </div>
    </div>
  </header>

  <!-- 中间聊天气泡流 -->
  <main id="chatList" class="chat-scroll">
    <div id="emptyHint" class="empty-hint">
      <div class="badge">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>
        </svg>
      </div>
      <div>已与电脑建立安全连接<br>发送文字、照片、文件或语音，即刻双向同步</div>
    </div>
  </main>

  <!-- 底部微信式输入栏与扩展抽屉 -->
  <footer id="bottomDock" class="bottom-dock">
    <div class="input-bar">
      <!-- 左侧：语音 / 键盘切换 -->
      <button id="btnVoiceToggle" class="icon-btn" type="button" aria-label="语音切换">
        <svg id="icoVoice" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="9.5"/>
          <path d="M9.5 9.8a3.2 3.2 0 0 1 0 4.4"/>
          <path d="M12.2 7.8a6 6 0 0 1 0 8.4"/>
          <circle cx="7.4" cy="12" r="0.9" fill="currentColor" stroke="none"/>
        </svg>
        <svg id="icoKeyboard" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="display:none;">
          <rect x="2.5" y="5.5" width="19" height="13" rx="2.5"/>
          <line x1="6" y1="9.5" x2="6.01" y2="9.5"/><line x1="9.5" y1="9.5" x2="9.51" y2="9.5"/><line x1="13" y1="9.5" x2="13.01" y2="9.5"/><line x1="16.5" y1="9.5" x2="16.51" y2="9.5"/>
          <line x1="7.5" y1="14.5" x2="16.5" y2="14.5"/>
        </svg>
      </button>

      <!-- 中间：自适应文本输入框 / 按住说话 -->
      <div class="input-wrap">
        <textarea id="msgInput" class="msg-input" rows="1"></textarea>
        <button id="btnVoiceHold" class="voice-hold-btn" type="button">按住 说话</button>
      </div>

      <!-- 右侧：表情图标 -->
      <button id="btnEmoji" class="icon-btn" type="button" aria-label="表情">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="9.5"/>
          <circle cx="9" cy="10" r="1" fill="currentColor" stroke="none"/>
          <circle cx="15" cy="10" r="1" fill="currentColor" stroke="none"/>
          <path d="M8.5 14.5a4.5 4.5 0 0 0 7 0"/>
        </svg>
      </button>

      <!-- 右侧：加号图标 / 发送按钮 -->
      <button id="btnPlus" class="icon-btn" type="button" aria-label="更多功能">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="9.5"/>
          <line x1="12" y1="7.8" x2="12" y2="16.2"/>
          <line x1="7.8" y1="12" x2="16.2" y2="12"/>
        </svg>
      </button>
      <button id="btnSend" class="send-btn" type="button">发送</button>
    </div>

    <!-- 互斥展开抽屉容器 -->
    <div id="drawerBox" class="drawer-container">
      <!-- 表情面板 -->
      <div id="emojiPanel" class="emoji-panel">
        <div id="emojiGrid" class="emoji-grid"></div>
        <button id="btnEmojiDel" class="emoji-backspace" type="button" aria-label="退格删除">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 4H8l-7 8 7 8h13a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/>
            <line x1="18" y1="9" x2="12" y2="15"/>
            <line x1="12" y1="9" x2="18" y2="15"/>
          </svg>
        </button>
      </div>

      <!-- 加号功能宫格 -->
      <div id="plusPanel" class="plus-panel">
        <div class="plus-grid">
          <button id="actPhoto" class="plus-card" type="button">
            <div class="plus-icon-box">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="4" width="18" height="16" rx="2.5"/>
                <circle cx="8.5" cy="9.5" r="1.5"/>
                <path d="M21 15l-4.5-4.5L7 20"/>
              </svg>
            </div>
            <span>照片</span>
          </button>

          <button id="actCamera" class="plus-card" type="button">
            <div class="plus-icon-box">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                <circle cx="12" cy="13" r="4"/>
              </svg>
            </div>
            <span>拍照</span>
          </button>

          <button id="actFile" class="plus-card" type="button">
            <div class="plus-icon-box">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
            </div>
            <span>文件</span>
          </button>

          <button id="actClip" class="plus-card" type="button">
            <div class="plus-icon-box">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                <rect x="8" y="2" width="8" height="4" rx="1"/>
                <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
                <line x1="9" y1="12" x2="15" y2="12"/>
                <line x1="9" y1="16" x2="13" y2="16"/>
              </svg>
            </div>
            <span>粘贴剪贴板</span>
          </button>
        </div>
      </div>
    </div>
  </footer>
</div>

<!-- 隐藏文件选择器 -->
<input id="inpPhoto" type="file" accept="image/*,video/*" multiple style="display:none;">
<input id="inpCamera" type="file" accept="image/*" capture="environment" style="display:none;">
<input id="inpFile" type="file" multiple style="display:none;">

<!-- 录音中央声波悬浮提示 -->
<div id="recHud" class="rec-hud">
  <div class="rec-waves">
    <div class="rec-bar"></div><div class="rec-bar"></div><div class="rec-bar"></div>
    <div class="rec-bar"></div><div class="rec-bar"></div><div class="rec-bar"></div>
  </div>
  <div id="recSec" class="rec-sec">0"</div>
  <div class="rec-tip">松开发送（最长 60 秒）</div>
</div>

<!-- 图片全屏预览灯箱 -->
<div id="lightbox" class="lightbox">
  <img id="lbImg" src="" alt="预览图片">
  <div class="lightbox-actions">
    <a id="lbDownload" class="lb-btn" href="#" download>保存原图</a>
    <button id="lbClose" class="lb-btn" type="button">关闭</button>
  </div>
</div>

<div id="toast" class="toast"></div>

<script>
(function() {
  const PAGE_TOKEN = new URLSearchParams(window.location.search).get('token') || '';
  function withToken(url) {
    if (!PAGE_TOKEN) return url;
    return url + (url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(PAGE_TOKEN);
  }

  function getOrCreateDeviceId() {
    const key = 'idlemeter_phone_device_id';
    try {
      let id = localStorage.getItem(key);
      if (id && id.length >= 6) return id;
      id = 'PH-' + Math.random().toString(16).slice(2, 10).toUpperCase();
      localStorage.setItem(key, id);
      return id;
    } catch (_) {
      return 'PH-' + Math.random().toString(16).slice(2, 10).toUpperCase();
    }
  }
  const MY_DEVICE_ID = getOrCreateDeviceId();
  let mySenderName = '本机手机';
  let myAvatarIdx = 1;

  const AVATAR_PALETTES = [
    { bg: '#2B3345', fg: '#F8FAFC', accent: '#60A5FA' }, // 0: PC 电脑端
    { bg: '#10B981', fg: '#FFFFFF', accent: '#A7F3D0' }, // 1: 手机端-1
    { bg: '#3B82F6', fg: '#FFFFFF', accent: '#BFDBFE' }, // 2: 手机端-2
    { bg: '#8B5CF6', fg: '#FFFFFF', accent: '#DDD6FE' }, // 3: 手机端-3
    { bg: '#F59E0B', fg: '#FFFFFF', accent: '#FEF3C7' }, // 4: 手机端-4
    { bg: '#EC4899', fg: '#FFFFFF', accent: '#FBCFE8' }, // 5: 手机端-5
  ];

  function makeDeviceAvatarSvg(avIdx) {
    const idx = Math.max(0, Math.min(5, Number(avIdx || 0)));
    const p = AVATAR_PALETTES[idx];
    if (idx === 0) {
      return '<svg width="34" height="34" viewBox="0 0 34 34">' +
        '<rect width="34" height="34" rx="9" fill="' + p.bg + '"/>' +
        '<rect x="7" y="8" width="20" height="13" rx="2" fill="none" stroke="' + p.fg + '" stroke-width="1.8"/>' +
        '<line x1="17" y1="21" x2="17" y2="25" stroke="' + p.fg + '" stroke-width="1.8"/>' +
        '<line x1="12" y1="25.5" x2="22" y2="25.5" stroke="' + p.fg + '" stroke-width="1.8" stroke-linecap="round"/>' +
        '<circle cx="17" cy="14.5" r="2" fill="' + p.accent + '"/>' +
        '</svg>';
    }
    return '<svg width="34" height="34" viewBox="0 0 34 34">' +
      '<rect width="34" height="34" rx="9" fill="' + p.bg + '"/>' +
      '<rect x="10.5" y="6.5" width="13" height="21" rx="2.6" fill="none" stroke="' + p.fg + '" stroke-width="1.8"/>' +
      '<line x1="14.5" y1="9.5" x2="19.5" y2="9.5" stroke="' + p.accent + '" stroke-width="1.6" stroke-linecap="round"/>' +
      '<circle cx="17" cy="23.8" r="1.2" fill="' + p.fg + '"/>' +
      '</svg>';
  }

  const chatList = document.getElementById('chatList');
  const emptyHint = document.getElementById('emptyHint');
  const connStatus = document.getElementById('connStatus');
  const msgInput = document.getElementById('msgInput');
  const btnVoiceToggle = document.getElementById('btnVoiceToggle');
  const icoVoice = document.getElementById('icoVoice');
  const icoKeyboard = document.getElementById('icoKeyboard');
  const btnVoiceHold = document.getElementById('btnVoiceHold');
  const btnEmoji = document.getElementById('btnEmoji');
  const btnPlus = document.getElementById('btnPlus');
  const btnSend = document.getElementById('btnSend');
  const drawerBox = document.getElementById('drawerBox');
  const emojiPanel = document.getElementById('emojiPanel');
  const emojiGrid = document.getElementById('emojiGrid');
  const btnEmojiDel = document.getElementById('btnEmojiDel');
  const plusPanel = document.getElementById('plusPanel');
  const inpPhoto = document.getElementById('inpPhoto');
  const inpCamera = document.getElementById('inpCamera');
  const inpFile = document.getElementById('inpFile');
  const recHud = document.getElementById('recHud');
  const recSecEl = document.getElementById('recSec');
  const lightbox = document.getElementById('lightbox');
  const lbImg = document.getElementById('lbImg');
  const lbDownload = document.getElementById('lbDownload');
  const lbClose = document.getElementById('lbClose');
  const toastEl = document.getElementById('toast');

  const EMOJIS = [
    '😀','😁','😂','🤣','😃','😄','😅','😆',
    '😉','😊','😋','😎','😍','🥰','😘','🤗',
    '🤔','😐','😑','😶','🙄','😏','😣','😥',
    '😮','🤐','😯','😪','😫','🥱','😴','😌',
    '😛','😜','😝','🤤','😒','😓','😔','😕',
    '🙃','🤑','😲','😭','😤','😠','😡','🤯',
    '😳','🥺','😱','😨','😰','🥳','😇','🤠',
    '👍','👎','👌','✌️','🤞','🤝','👏','🙏',
    '💪','🎉','🔥','💯','❤️','🧡','💛','💚',
    '✨','⚡','📌','📎','📁','💻','📱','☕'
  ];

  let toastTimer = null;
  function showToast(msg, ms) {
    toastEl.textContent = msg;
    toastEl.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove('show'), ms || 2000);
  }

  function applyTheme(th) {
    if (!th) return;
    const root = document.documentElement.style;
    const map = {
      bg: '--bg', nav_bg: '--nav-bg', chat_bg: '--chat-bg',
      card_bg: '--card', bubble_pc: '--bubble-pc',
      input_bar_bg: '--input-bar-bg', panel_bg: '--panel-bg',
      input_bg: '--input-bg', fg: '--fg', sub_fg: '--sub-fg',
      border: '--border', accent: '--accent'
    };
    for (const k in map) {
      if (th[k]) root.setProperty(map[k], th[k]);
    }
  }

  function formatSize(bytes) {
    const n = Number(bytes || 0);
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    if (n < 1073741824) return (n / 1048576).toFixed(1) + ' MB';
    return (n / 1073741824).toFixed(2) + ' GB';
  }

  function getFileExtInfo(name) {
    const m = String(name || '').match(/\.([a-zA-Z0-9]{1,6})$/);
    const ext = m ? m[1].toUpperCase() : 'FILE';
    const colors = {
      PDF: '#e11d48', DOC: '#2563eb', DOCX: '#2563eb',
      XLS: '#16a34a', XLSX: '#16a34a', PPT: '#ea580c', PPTX: '#ea580c',
      ZIP: '#d97706', RAR: '#d97706', '7Z': '#d97706',
      MP4: '#7c3aed', MOV: '#7c3aed', MP3: '#0891b2', WAV: '#0891b2',
      TXT: '#64748b', MD: '#64748b', EXE: '#4f46e5', APK: '#10b981'
    };
    return { label: ext.slice(0, 4), color: colors[ext] || '#6366f1' };
  }

  function scrollToBottom() {
    requestAnimationFrame(() => { chatList.scrollTop = chatList.scrollHeight; });
  }

  // ------------------------------------------------------------------
  // 面板切换与输入框自适应
  // ------------------------------------------------------------------
  let voiceMode = false;
  let activeDrawer = ''; // '' | 'emoji' | 'plus'

  function updateSendOrPlus() {
    const hasText = !voiceMode && msgInput.value.trim().length > 0;
    btnSend.classList.toggle('show', hasText);
    btnPlus.style.display = hasText ? 'none' : 'flex';
  }

  function autoResizeInput() {
    msgInput.style.height = 'auto';
    msgInput.style.height = Math.min(104, Math.max(36, msgInput.scrollHeight)) + 'px';
    updateSendOrPlus();
  }

  function closeDrawers() {
    activeDrawer = '';
    drawerBox.classList.remove('open');
    emojiPanel.classList.remove('active');
    plusPanel.classList.remove('active');
  }

  function toggleDrawer(kind) {
    if (activeDrawer === kind) {
      closeDrawers();
      return;
    }
    if (voiceMode) setVoiceMode(false);
    activeDrawer = kind;
    emojiPanel.classList.toggle('active', kind === 'emoji');
    plusPanel.classList.toggle('active', kind === 'plus');
    drawerBox.classList.add('open');
    msgInput.blur();
    scrollToBottom();
  }

  function setVoiceMode(enable) {
    voiceMode = !!enable;
    if (voiceMode) {
      closeDrawers();
      msgInput.blur();
      msgInput.style.display = 'none';
      btnVoiceHold.classList.add('show');
      icoVoice.style.display = 'none';
      icoKeyboard.style.display = 'block';
    } else {
      msgInput.style.display = 'block';
      btnVoiceHold.classList.remove('show');
      icoVoice.style.display = 'block';
      icoKeyboard.style.display = 'none';
    }
    updateSendOrPlus();
  }

  function isVoiceSupported() {
    return !!(navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function' && typeof MediaRecorder !== 'undefined');
  }

  btnVoiceToggle.addEventListener('click', () => {
    if (!voiceMode && !isVoiceSupported()) {
      showToast('语音功能需在【互联网】安全连接下使用', 2600);
      return;
    }
    setVoiceMode(!voiceMode);
  });

  btnEmoji.addEventListener('click', () => toggleDrawer('emoji'));
  btnPlus.addEventListener('click', () => toggleDrawer('plus'));
  msgInput.addEventListener('focus', () => closeDrawers());
  msgInput.addEventListener('input', autoResizeInput);
  msgInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      sendCurrentText();
    }
  });
  chatList.addEventListener('click', (e) => {
    if (e.target === chatList || e.target === emptyHint) closeDrawers();
  });

  // 渲染表情网格
  EMOJIS.forEach((em) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'emoji-item';
    b.textContent = em;
    b.addEventListener('click', () => {
      const start = msgInput.selectionStart ?? msgInput.value.length;
      const end = msgInput.selectionEnd ?? msgInput.value.length;
      msgInput.value = msgInput.value.slice(0, start) + em + msgInput.value.slice(end);
      const nextPos = start + em.length;
      try { msgInput.setSelectionRange(nextPos, nextPos); } catch (_) {}
      autoResizeInput();
    });
    emojiGrid.appendChild(b);
  });

  btnEmojiDel.addEventListener('click', () => {
    const val = msgInput.value;
    if (!val) return;
    const chars = Array.from(val);
    chars.pop();
    msgInput.value = chars.join('');
    autoResizeInput();
  });

  // ------------------------------------------------------------------
  // 语音播放器（全局互斥，支持动态声波动画）
  // ------------------------------------------------------------------
  let activeAudio = null;
  let activeVoiceBtn = null;

  function stopVoicePlayback() {
    if (activeAudio) {
      try { activeAudio.pause(); activeAudio.currentTime = 0; } catch (_) {}
      activeAudio = null;
    }
    if (activeVoiceBtn) {
      activeVoiceBtn.classList.remove('playing');
      activeVoiceBtn = null;
    }
  }

  function toggleVoicePlay(btn, srcUrl) {
    if (activeVoiceBtn === btn) {
      stopVoicePlayback();
      return;
    }
    stopVoicePlayback();
    const audio = new Audio(srcUrl);
    activeAudio = audio;
    activeVoiceBtn = btn;
    btn.classList.add('playing');
    audio.onended = () => stopVoicePlayback();
    audio.onerror = () => { stopVoicePlayback(); showToast('音频播放失败'); };
    audio.play().catch(() => { stopVoicePlayback(); showToast('无法播放该语音'); });
  }

  // ------------------------------------------------------------------
  // 图片全屏预览灯箱
  // ------------------------------------------------------------------
  function openLightbox(srcUrl, filename) {
    lbImg.src = srcUrl;
    lbDownload.href = srcUrl;
    lbDownload.setAttribute('download', filename || 'image.png');
    lightbox.classList.add('show');
  }
  lbClose.addEventListener('click', () => lightbox.classList.remove('show'));
  lightbox.addEventListener('click', (e) => {
    if (e.target === lightbox) lightbox.classList.remove('show');
  });

  // ------------------------------------------------------------------
  // 聊天气泡渲染引擎
  // ------------------------------------------------------------------
  const renderedIds = new Set();
  let lastTimeStampLabel = '';

  function ensureTimeDivider(timeStr) {
    if (!timeStr) return;
    if (timeStr !== lastTimeStampLabel) {
      lastTimeStampLabel = timeStr;
      const div = document.createElement('div');
      div.className = 'time-divider';
      div.textContent = timeStr;
      chatList.appendChild(div);
    }
  }

  async function copyTextToPhone(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        showToast('✓ 已复制到手机剪贴板', 1500);
        return;
      }
    } catch (_) {}
    try {
      const ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      showToast('✓ 已复制到手机剪贴板', 1500);
    } catch (_) {
      showToast('请长按气泡手动复制');
    }
  }

  function makeVoiceWaveSvg() {
    return '<svg class="voice-wave-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">' +
      '<circle cx="5.5" cy="12" r="1.4" fill="currentColor" stroke="none"/>' +
      '<path class="vw-arc2" d="M9.5 8.5a5 5 0 0 1 0 7"/>' +
      '<path class="vw-arc3" d="M13.5 5.5a9.2 9.2 0 0 1 0 13"/>' +
      '</svg>';
  }

  function createBubbleRow(msg, opts) {
    opts = opts || {};
    if (emptyHint) emptyHint.style.display = 'none';
    ensureTimeDivider(msg.time_str || new Date().toTimeString().slice(0, 5));

    const isMe = msg.direction === 'phone' && (!msg.device_id || msg.device_id === MY_DEVICE_ID);
    const avIdx = (msg.avatar_idx !== undefined && msg.avatar_idx !== null)
      ? Number(msg.avatar_idx)
      : (isMe ? myAvatarIdx : (msg.direction === 'pc' ? 0 : 1));
    const senderName = msg.sender_name || (msg.direction === 'pc' ? '电脑端' : mySenderName);

    const row = document.createElement('div');
    row.className = 'msg-row ' + (isMe ? 'me' : 'pc');
    if (msg.id) row.dataset.msgId = msg.id;

    const av = document.createElement('div');
    av.className = 'msg-avatar';
    av.innerHTML = makeDeviceAvatarSvg(avIdx);
    row.appendChild(av);

    const col = document.createElement('div');
    col.className = 'msg-col';
    row.appendChild(col);

    const senderEl = document.createElement('div');
    senderEl.className = 'msg-sender';
    senderEl.textContent = senderName;
    col.appendChild(senderEl);

    const sub = document.createElement('div');
    sub.className = 'msg-sub';

    const mtype = msg.msg_type || 'text';
    const mediaUrl = opts.localUrl || (msg.id ? withToken('/api/media?id=' + encodeURIComponent(msg.id)) : '');
    const dlUrl = msg.id ? withToken('/api/download?id=' + encodeURIComponent(msg.id)) : mediaUrl;

    let refs = { row, col, sub, av, senderEl };

    if (mtype === 'text') {
      const b = document.createElement('div');
      b.className = 'bubble-text';
      b.textContent = msg.text || '';
      if (!isMe) {
        b.title = '点击复制全文';
        b.addEventListener('click', () => copyTextToPhone(msg.text || ''));
        sub.textContent = '点击气泡复制全文';
      } else {
        sub.textContent = opts.pending ? '发送中...' : '✓ 已同步电脑剪贴板';
        if (!opts.pending) sub.classList.add('ok');
      }
      col.appendChild(b);
      col.appendChild(sub);
    } else if (mtype === 'image') {
      const wrap = document.createElement('div');
      wrap.className = 'bubble-img-wrap';
      const img = document.createElement('img');
      img.src = mediaUrl;
      img.alt = msg.name || '图片';
      img.loading = 'lazy';
      wrap.appendChild(img);

      const mask = document.createElement('div');
      mask.className = 'img-progress-mask' + (opts.pending ? '' : ' hidden');
      mask.textContent = opts.pending ? '0%' : '';
      wrap.appendChild(mask);

      wrap.addEventListener('click', () => {
        const curSrc = img.dataset.serverSrc || img.src;
        openLightbox(curSrc, msg.name || 'image.png');
      });

      sub.textContent = opts.pending ? '正在上传图片...' : (isMe ? '✓ 已保存到电脑' : '点击查看大图');
      if (!opts.pending && isMe) sub.classList.add('ok');
      col.appendChild(wrap);
      col.appendChild(sub);
      refs.img = img;
      refs.mask = mask;
    } else if (mtype === 'audio') {
      const dur = Math.max(1, Number(msg.duration || 1));
      const b = document.createElement('div');
      b.className = 'bubble-voice';
      b.style.width = Math.min(210, Math.max(88, 72 + dur * 5)) + 'px';
      b.innerHTML = makeVoiceWaveSvg() + '<span>' + dur + '"</span>';
      b.dataset.audioSrc = mediaUrl;
      b.addEventListener('click', () => {
        if (b.dataset.audioSrc) toggleVoicePlay(b, b.dataset.audioSrc);
      });
      sub.textContent = opts.pending ? '语音上传中...' : (isMe ? '✓ 语音已发送到电脑' : '点击播放语音');
      if (!opts.pending && isMe) sub.classList.add('ok');
      col.appendChild(b);
      col.appendChild(sub);
      refs.voiceBtn = b;
    } else {
      const card = document.createElement('a');
      card.className = 'bubble-file';
      if (dlUrl) {
        card.href = dlUrl;
        card.setAttribute('download', msg.name || 'file');
      } else {
        card.href = 'javascript:void(0)';
      }
      const extInfo = getFileExtInfo(msg.name);
      const top = document.createElement('div');
      top.className = 'file-top';

      const info = document.createElement('div');
      info.className = 'file-info';
      const nm = document.createElement('div');
      nm.className = 'file-name';
      nm.textContent = msg.name || '文件';
      const meta = document.createElement('div');
      meta.className = 'file-meta';
      meta.textContent = (msg.size_str || formatSize(msg.size)) + (opts.pending ? ' · 0%' : (isMe ? ' · 已发送' : ' · 点击下载'));
      info.appendChild(nm);
      info.appendChild(meta);

      const badge = document.createElement('div');
      badge.className = 'file-badge';
      badge.style.background = extInfo.color;
      badge.textContent = extInfo.label;

      top.appendChild(info);
      top.appendChild(badge);
      card.appendChild(top);

      const track = document.createElement('div');
      track.className = 'file-prog-track' + (opts.pending ? '' : ' hidden');
      const fill = document.createElement('div');
      fill.className = 'file-prog-fill';
      track.appendChild(fill);
      card.appendChild(track);

      col.appendChild(card);
      refs.fileCard = card;
      refs.fileMeta = meta;
      refs.progTrack = track;
      refs.progFill = fill;
    }

    chatList.appendChild(row);
    scrollToBottom();
    return refs;
  }

  // ------------------------------------------------------------------
  // 发送文字 & XHR 带实时进度上传文件/图片/语音
  // ------------------------------------------------------------------
  async function sendTextString(raw) {
    const v = String(raw || '');
    if (!v.trim()) return;
    const refs = createBubbleRow({
      direction: 'phone', msg_type: 'text', text: v,
      device_id: MY_DEVICE_ID, sender_name: mySenderName, avatar_idx: myAvatarIdx,
      time_str: new Date().toTimeString().slice(0, 5)
    }, { pending: true });

    try {
      const r = await fetch(withToken('/api/text'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-Id': MY_DEVICE_ID },
        body: JSON.stringify({ text: v, device_id: MY_DEVICE_ID })
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const j = await r.json();
      if (j && j.message && j.message.id) {
        renderedIds.add(j.message.id);
        refs.row.dataset.msgId = j.message.id;
        if (j.message.sender_name) { mySenderName = j.message.sender_name; refs.senderEl.textContent = mySenderName; }
        if (j.message.avatar_idx) { myAvatarIdx = j.message.avatar_idx; refs.av.innerHTML = makeDeviceAvatarSvg(myAvatarIdx); }
      }
      refs.sub.textContent = '✓ 已同步电脑剪贴板';
      refs.sub.classList.add('ok');
    } catch (e) {
      refs.sub.textContent = '发送失败';
      refs.sub.classList.add('err');
      showToast('发送失败，请检查连接');
    }
  }

  function sendCurrentText() {
    const v = msgInput.value;
    if (!v.trim()) return;
    msgInput.value = '';
    autoResizeInput();
    sendTextString(v);
  }
  btnSend.addEventListener('click', sendCurrentText);

  function classifyLocalFile(file, forceType) {
    if (forceType) return forceType;
    const mime = String(file.type || '').toLowerCase();
    const name = String(file.name || '').toLowerCase();
    if (mime.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp|heic|svg)$/.test(name)) return 'image';
    if (mime.startsWith('audio/') || /\.(webm|m4a|mp3|wav|ogg|aac|opus|amr)$/.test(name)) return 'audio';
    return 'file';
  }

  function uploadSingleFile(file, opts) {
    opts = opts || {};
    const mtype = classifyLocalFile(file, opts.forceType);
    const localUrl = (mtype === 'image' || mtype === 'audio') ? URL.createObjectURL(file) : '';
    const sizeStr = formatSize(file.size);
    const refs = createBubbleRow({
      direction: 'phone',
      msg_type: mtype,
      device_id: MY_DEVICE_ID,
      sender_name: mySenderName,
      avatar_idx: myAvatarIdx,
      name: file.name || 'upload.bin',
      size: file.size,
      size_str: sizeStr,
      duration: opts.duration || 0,
      time_str: new Date().toTimeString().slice(0, 5)
    }, { pending: true, localUrl: localUrl });

    const fd = new FormData();
    fd.append('device_id', MY_DEVICE_ID);
    if (opts.duration) fd.append('duration', String(opts.duration));
    fd.append('file', file, file.name || 'upload.bin');

    const xhr = new XMLHttpRequest();
    xhr.open('POST', withToken('/api/upload'), true);
    xhr.setRequestHeader('X-Device-Id', MY_DEVICE_ID);
    xhr.upload.onprogress = (ev) => {
      if (!ev.lengthComputable) return;
      const pct = Math.min(99, Math.round((ev.loaded * 100) / Math.max(1, ev.total)));
      if (refs.mask) refs.mask.textContent = pct + '%';
      if (refs.progFill) refs.progFill.style.width = pct + '%';
      if (refs.fileMeta) refs.fileMeta.textContent = sizeStr + ' · 上传中 ' + pct + '%';
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        let srvMsg = null;
        try {
          const j = JSON.parse(xhr.responseText || '{}');
          if (j.messages && j.messages.length) srvMsg = j.messages[0];
        } catch (_) {}
        if (srvMsg && srvMsg.id) {
          renderedIds.add(srvMsg.id);
          refs.row.dataset.msgId = srvMsg.id;
          if (srvMsg.sender_name) { mySenderName = srvMsg.sender_name; refs.senderEl.textContent = mySenderName; }
          if (srvMsg.avatar_idx) { myAvatarIdx = srvMsg.avatar_idx; refs.av.innerHTML = makeDeviceAvatarSvg(myAvatarIdx); }
          const mUrl = withToken('/api/media?id=' + encodeURIComponent(srvMsg.id));
          const dUrl = withToken('/api/download?id=' + encodeURIComponent(srvMsg.id));
          if (refs.img) refs.img.dataset.serverSrc = mUrl;
          if (refs.voiceBtn) refs.voiceBtn.dataset.audioSrc = mUrl;
          if (refs.fileCard) refs.fileCard.href = dUrl;
        }
        if (refs.mask) refs.mask.classList.add('hidden');
        if (refs.progFill) refs.progFill.style.width = '100%';
        if (refs.progTrack) setTimeout(() => refs.progTrack.classList.add('hidden'), 350);
        if (refs.fileMeta) refs.fileMeta.textContent = sizeStr + ' · ✓ 已发送到电脑';
        if (refs.sub) {
          refs.sub.textContent = mtype === 'audio' ? '✓ 语音已发送到电脑' : '✓ 已保存到电脑';
          refs.sub.classList.add('ok');
        }
      } else {
        if (refs.mask) refs.mask.textContent = '上传失败';
        if (refs.fileMeta) refs.fileMeta.textContent = sizeStr + ' · 上传失败';
        if (refs.sub) { refs.sub.textContent = '上传失败'; refs.sub.classList.add('err'); }
      }
    };
    xhr.onerror = () => {
      if (refs.mask) refs.mask.textContent = '网络错误';
      if (refs.fileMeta) refs.fileMeta.textContent = sizeStr + ' · 网络错误';
      if (refs.sub) { refs.sub.textContent = '网络错误'; refs.sub.classList.add('err'); }
    };
    xhr.send(fd);
  }

  function handleFileSelection(inputEl) {
    const files = Array.from(inputEl.files || []);
    inputEl.value = '';
    if (!files.length) return;
    closeDrawers();
    for (const f of files) {
      uploadSingleFile(f);
    }
  }

  document.getElementById('actPhoto').addEventListener('click', () => inpPhoto.click());
  document.getElementById('actCamera').addEventListener('click', () => inpCamera.click());
  document.getElementById('actFile').addEventListener('click', () => inpFile.click());
  inpPhoto.addEventListener('change', () => handleFileSelection(inpPhoto));
  inpCamera.addEventListener('change', () => handleFileSelection(inpCamera));
  inpFile.addEventListener('change', () => handleFileSelection(inpFile));

  document.getElementById('actClip').addEventListener('click', async () => {
    closeDrawers();
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const txt = await navigator.clipboard.readText();
        if (txt && txt.trim()) {
          sendTextString(txt);
          return;
        }
        showToast('手机剪贴板暂无文字内容');
        return;
      }
    } catch (_) {}
    setVoiceMode(false);
    msgInput.focus();
    msgInput.classList.add('pulse-highlight');
    setTimeout(() => msgInput.classList.remove('pulse-highlight'), 1800);
    showToast('当前环境限制自动读取，请长按输入框直接粘贴', 2400);
  });

  // ------------------------------------------------------------------
  // 按住说话录音逻辑（iOS audio/mp4 + Android audio/webm + 60s 自动停 + <1s 提示）
  // ------------------------------------------------------------------
  let isHoldingVoice = false;
  let mediaRecorder = null;
  let audioStream = null;
  let audioChunks = [];
  let recStartTs = 0;
  let recTimer = null;
  let recMime = 'audio/webm';

  function pickRecorderMime() {
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
    for (const c of candidates) {
      try {
        if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c)) return c;
      } catch (_) {}
    }
    return '';
  }

  function cleanupAudioStream() {
    clearInterval(recTimer);
    recTimer = null;
    if (audioStream) {
      try { audioStream.getTracks().forEach((tr) => tr.stop()); } catch (_) {}
      audioStream = null;
    }
  }

  async function startVoiceRecord(e) {
    if (e) e.preventDefault();
    if (isHoldingVoice) return;
    if (!isVoiceSupported()) {
      showToast('语音功能需在【互联网】安全连接下使用', 2600);
      return;
    }
    isHoldingVoice = true;
    btnVoiceHold.classList.add('recording');
    btnVoiceHold.textContent = '松开 结束';

    try {
      audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!isHoldingVoice) { cleanupAudioStream(); return; }
      audioChunks = [];
      const chosen = pickRecorderMime();
      recMime = chosen || 'audio/webm';
      mediaRecorder = chosen ? new MediaRecorder(audioStream, { mimeType: chosen }) : new MediaRecorder(audioStream);
      mediaRecorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) audioChunks.push(ev.data);
      };
      mediaRecorder.onstop = () => {
        const elapsedMs = Date.now() - recStartTs;
        const sec = Math.max(1, Math.min(60, Math.round(elapsedMs / 1000)));
        const chunks = audioChunks.slice();
        cleanupAudioStream();
        if (elapsedMs < 1000 || !chunks.length) {
          showToast('说话时间太短', 1600);
          return;
        }
        const finalMime = (mediaRecorder && mediaRecorder.mimeType) || recMime || 'audio/webm';
        const ext = finalMime.includes('mp4') ? 'm4a' : (finalMime.includes('ogg') ? 'ogg' : 'webm');
        const blob = new Blob(chunks, { type: finalMime });
        const file = new File([blob], 'voice_' + Date.now() + '.' + ext, { type: finalMime });
        uploadSingleFile(file, { forceType: 'audio', duration: sec });
      };
      recStartTs = Date.now();
      recSecEl.textContent = '0"';
      recHud.classList.add('show');
      mediaRecorder.start(200);
      recTimer = setInterval(() => {
        const s = Math.floor((Date.now() - recStartTs) / 1000);
        recSecEl.textContent = s + '"';
        if (s >= 60) stopVoiceRecord();
      }, 250);
    } catch (err) {
      isHoldingVoice = false;
      btnVoiceHold.classList.remove('recording');
      btnVoiceHold.textContent = '按住 说话';
      recHud.classList.remove('show');
      cleanupAudioStream();
      showToast('无法访问麦克风，请检查浏览器录音权限', 2400);
    }
  }

  function stopVoiceRecord(e) {
    if (e) e.preventDefault();
    if (!isHoldingVoice) return;
    isHoldingVoice = false;
    btnVoiceHold.classList.remove('recording');
    btnVoiceHold.textContent = '按住 说话';
    recHud.classList.remove('show');
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      try { mediaRecorder.stop(); } catch (_) { cleanupAudioStream(); }
    } else {
      cleanupAudioStream();
    }
  }

  btnVoiceHold.addEventListener('contextmenu', (e) => e.preventDefault());
  btnVoiceHold.addEventListener('touchstart', startVoiceRecord, { passive: false });
  btnVoiceHold.addEventListener('touchend', stopVoiceRecord, { passive: false });
  btnVoiceHold.addEventListener('touchcancel', stopVoiceRecord, { passive: false });
  btnVoiceHold.addEventListener('mousedown', startVoiceRecord);
  window.addEventListener('mouseup', () => { if (isHoldingVoice) stopVoiceRecord(); });

  // ------------------------------------------------------------------
  // 定时轮询 /api/state：实时同步主题 + 增量渲染电脑/手机消息流
  // ------------------------------------------------------------------
  async function syncState() {
    try {
      const r = await fetch(withToken('/api/state'));
      if (!r.ok) return;
      const data = await r.json();
      if (data && data.theme) applyTheme(data.theme);
      if (data && typeof data.is_internet === 'boolean') {
        connStatus.textContent = (data.is_internet || window.location.protocol === 'https:')
          ? '公网加密隧道已连接'
          : '局域网直连';
      }
      const msgs = Array.isArray(data.messages) ? data.messages : [];
      for (const m of msgs) {
        if (!m || !m.id || renderedIds.has(m.id)) continue;
        renderedIds.add(m.id);
        createBubbleRow(m, { pending: false });
      }
    } catch (_) {}
  }

  // ------------------------------------------------------------------
  // window.visualViewport 实时贴合引擎（兼容 iOS Safari/微信/第三方输入法 & 安卓全系）
  // ------------------------------------------------------------------
  const appEl = document.getElementById('app');
  let baseViewportHeight = Math.max(
    window.innerHeight || 0,
    (window.visualViewport && window.visualViewport.height) || 0
  );
  let lastKbOpen = false;
  let vpRafId = 0;

  function applyViewportLayout() {
    vpRafId = 0;
    if (!appEl) return;

    const vv = window.visualViewport;
    if (vv) {
      const vh = Math.max(120, Math.round(vv.height));
      const offsetTop = Math.max(0, Math.round(vv.offsetTop || 0));
      if (vh > baseViewportHeight) {
        baseViewportHeight = vh;
      }
      const shrinkDelta = Math.max(baseViewportHeight - vh, (window.innerHeight || vh) - vh);
      const isFocusedInput = (document.activeElement === msgInput);
      const kbOpen = shrinkDelta > 100 || (isFocusedInput && shrinkDelta > 60);

      appEl.style.height = vh + 'px';
      appEl.style.transform = offsetTop > 0 ? ('translateY(' + offsetTop + 'px)') : 'translateY(0px)';
      appEl.classList.toggle('keyboard-open', kbOpen);

      if (window.scrollY !== 0 || document.documentElement.scrollTop !== 0 || document.body.scrollTop !== 0) {
        window.scrollTo(0, 0);
      }
      if (kbOpen) {
        requestAnimationFrame(() => {
          chatList.scrollTop = chatList.scrollHeight;
        });
      }
      lastKbOpen = kbOpen;
    } else {
      const vh = Math.max(120, Math.round(window.innerHeight || 0));
      if (vh > baseViewportHeight) baseViewportHeight = vh;
      const kbOpen = (baseViewportHeight - vh) > 100;
      appEl.style.height = vh + 'px';
      appEl.style.transform = 'translateY(0px)';
      appEl.classList.toggle('keyboard-open', kbOpen);
      if (kbOpen && !lastKbOpen) {
        requestAnimationFrame(() => {
          chatList.scrollTop = chatList.scrollHeight;
        });
      }
      lastKbOpen = kbOpen;
    }
  }

  function scheduleViewportSync() {
    if (vpRafId) return;
    vpRafId = requestAnimationFrame(applyViewportLayout);
  }

  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', scheduleViewportSync);
    window.visualViewport.addEventListener('scroll', scheduleViewportSync);
  }
  window.addEventListener('resize', scheduleViewportSync);
  window.addEventListener('orientationchange', () => {
    setTimeout(() => {
      baseViewportHeight = Math.max(
        window.innerHeight || 0,
        (window.visualViewport && window.visualViewport.height) || 0
      );
      applyViewportLayout();
    }, 260);
  });
  msgInput.addEventListener('focus', () => {
    scheduleViewportSync();
    setTimeout(applyViewportLayout, 120);
    setTimeout(applyViewportLayout, 320);
  });
  msgInput.addEventListener('blur', () => {
    setTimeout(() => {
      window.scrollTo(0, 0);
      applyViewportLayout();
    }, 90);
  });
  applyViewportLayout();

  syncState();
  setInterval(syncState, 2000);
})();
</script>
</body>
</html>"""
        replacements = {
            "__BG__": t["bg"],
            "__NAV_BG__": t["nav_bg"],
            "__CHAT_BG__": t["chat_bg"],
            "__CARD_BG__": t["card_bg"],
            "__BUBBLE_PC__": t["bubble_pc"],
            "__INPUT_BAR_BG__": t["input_bar_bg"],
            "__PANEL_BG__": t["panel_bg"],
            "__INPUT_BG__": t["input_bg"],
            "__FG__": t["fg"],
            "__SUB_FG__": t["sub_fg"],
            "__BORDER__": t["border"],
            "__ACCENT__": t["accent"],
            "__INIT_CONN_TEXT__": init_conn_text,
        }
        html = template
        for k, v in replacements.items():
            html = html.replace(k, v)
        return html.encode("utf-8")

    def _stream_parse_multipart(
        self,
        rfile,
        content_length: int,
        boundary: bytes,
        chunk_size: int = 65536,
    ) -> Tuple[List[str], int, str]:
        """64KB 分块流式解析 multipart/form-data 并直接落盘，彻底避免大文件一次性撑爆内存。"""
        dash_boundary = b"--" + boundary
        crlf_boundary = b"\r\n--" + boundary
        keep_tail = len(crlf_boundary) + 2

        remaining = max(0, int(content_length))
        buf = bytearray()
        state = "preamble"  # "preamble" | "headers" | "file_body" | "field_body" | "done"
        saved_paths: List[str] = []
        duration_sec = 0
        form_dev_id = ""
        cur_fh = None
        cur_field_name = ""
        cur_field_buf = bytearray()

        def _read_more() -> bool:
            nonlocal remaining
            if remaining <= 0:
                return False
            data = rfile.read(min(chunk_size, remaining))
            if not data:
                remaining = 0
                return False
            remaining -= len(data)
            buf.extend(data)
            return True

        try:
            while state != "done":
                if state == "preamble":
                    idx = buf.find(dash_boundary)
                    if idx == -1:
                        if len(buf) > len(dash_boundary):
                            del buf[:-len(dash_boundary)]
                        if not _read_more():
                            break
                        continue
                    del buf[: idx + len(dash_boundary)]
                    while len(buf) < 2 and _read_more():
                        pass
                    if buf[:2] == b"--":
                        state = "done"
                        break
                    if buf[:2] == b"\r\n":
                        del buf[:2]
                    state = "headers"

                elif state == "headers":
                    sep = buf.find(b"\r\n\r\n")
                    if sep == -1:
                        if len(buf) > 65536 or not _read_more():
                            break
                        continue
                    hdr_bytes = bytes(buf[:sep])
                    del buf[: sep + 4]
                    hdr_text = hdr_bytes.decode("utf-8", errors="replace")

                    fname = ""
                    fn_m = re.search(r'filename="([^"]*)"', hdr_text)
                    if fn_m and fn_m.group(1):
                        fname = fn_m.group(1)
                    else:
                        fn_star = re.search(r"filename\*=UTF-8''([^\r\n;]+)", hdr_text, flags=re.IGNORECASE)
                        if fn_star:
                            try:
                                fname = urllib.parse.unquote(fn_star.group(1).strip())
                            except Exception:
                                fname = fn_star.group(1).strip()

                    if fname:
                        dest = self._unique_receive_path(fname)
                        cur_fh = open(dest, "wb")
                        saved_paths.append(dest)
                        state = "file_body"
                    else:
                        nm = re.search(r'name="([^"]*)"', hdr_text)
                        cur_field_name = nm.group(1) if nm else ""
                        cur_field_buf.clear()
                        state = "field_body"

                elif state in ("file_body", "field_body"):
                    idx = buf.find(crlf_boundary)
                    if idx != -1:
                        if state == "file_body" and cur_fh is not None:
                            if idx > 0:
                                cur_fh.write(memoryview(buf)[:idx])
                            cur_fh.flush()
                            cur_fh.close()
                            cur_fh = None
                        elif state == "field_body":
                            if idx > 0 and len(cur_field_buf) < 65536:
                                cur_field_buf.extend(buf[:idx])
                            val = bytes(cur_field_buf).decode("utf-8", errors="ignore").strip()
                            if cur_field_name == "duration":
                                try:
                                    duration_sec = max(0, int(val))
                                except Exception:
                                    duration_sec = 0
                            elif cur_field_name == "device_id" and val:
                                form_dev_id = val

                        del buf[: idx + len(crlf_boundary)]
                        while len(buf) < 2 and _read_more():
                            pass
                        if buf[:2] == b"--":
                            state = "done"
                            break
                        if buf[:2] == b"\r\n":
                            del buf[:2]
                        state = "headers"
                    else:
                        if len(buf) > keep_tail:
                            flush_n = len(buf) - keep_tail
                            if state == "file_body" and cur_fh is not None:
                                cur_fh.write(memoryview(buf)[:flush_n])
                            elif state == "field_body" and len(cur_field_buf) < 65536:
                                cur_field_buf.extend(buf[:flush_n])
                            del buf[:flush_n]
                        if not _read_more():
                            if state == "file_body" and cur_fh is not None and buf:
                                cur_fh.write(buf)
                                buf.clear()
                            break
        finally:
            if cur_fh is not None:
                try:
                    cur_fh.flush()
                    cur_fh.close()
                except Exception:
                    pass
            # 若仍有剩余字节未读完，快速排空以防连接复位
            while remaining > 0:
                skipped = rfile.read(min(chunk_size, remaining))
                if not skipped:
                    break
                remaining -= len(skipped)

        return saved_paths, duration_sec, form_dev_id

    SHARE_ID_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    SHARE_SKIP_NAMES = frozenset({"desktop.ini", "thumbs.db", ".ds_store"})

    @staticmethod
    def _format_size(num_bytes: int) -> str:
        return FastDownloader.format_size(int(num_bytes or 0))

    @classmethod
    def _should_skip_share_file(cls, filename: str) -> bool:
        low = str(filename or "").strip().lower()
        return (not low) or (low in cls.SHARE_SKIP_NAMES) or low.startswith("~$")

    @classmethod
    def package_share_paths(
        cls,
        paths: List[str],
        share_cache_dir: str = SHARE_CACHE_DIR,
    ) -> Tuple[str, str, int, bool]:
        """单文件零拷贝直接映射；多文件或嵌套文件夹使用 ZIP_STORED 极速防报错打包至 share_cache。
        返回 (serve_path, display_name, total_bytes, is_temp_zip)。
        """
        valid_paths = [os.path.abspath(p) for p in paths if p and os.path.exists(p)]
        if not valid_paths:
            raise FileNotFoundError("未选择有效的文件或文件夹")

        # 单个普通文件：0 拷贝直接引用原路径，不占用额外磁盘空间
        if len(valid_paths) == 1 and os.path.isfile(valid_paths[0]):
            fpath = valid_paths[0]
            return fpath, os.path.basename(fpath), int(os.path.getsize(fpath)), False

        # 多文件或任意嵌套文件夹：后台 ZIP_STORED 极速归档（跳过系统垃圾与锁死文件，保留空目录，容错 PermissionError）
        os.makedirs(share_cache_dir, exist_ok=True)
        if len(valid_paths) == 1 and os.path.isdir(valid_paths[0]):
            base_name = os.path.basename(valid_paths[0].rstrip("\\/")) or "folder"
            display_name = f"{base_name}.zip"
        else:
            first_name = os.path.basename(valid_paths[0].rstrip("\\/")) or "files"
            stem = os.path.splitext(first_name)[0] or first_name
            display_name = f"{stem}_等{len(valid_paths)}项.zip"

        safe_stem = re.sub(r'[\\/:*?"<>|]+', "_", os.path.splitext(display_name)[0])[:48] or "share"
        zip_path = os.path.join(share_cache_dir, f"{safe_stem}_{uuid.uuid4().hex[:8]}.zip")
        used_arcnames: set[str] = set()

        def _unique_arc(arc: str) -> str:
            norm = arc.replace("\\", "/").lstrip("/")
            if norm not in used_arcnames:
                used_arcnames.add(norm)
                return norm
            stem_p, ext_p = os.path.splitext(norm)
            idx = 1
            while True:
                cand = f"{stem_p}_{idx}{ext_p}"
                if cand not in used_arcnames:
                    used_arcnames.add(cand)
                    return cand
                idx += 1

        try:
            with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
                for p in valid_paths:
                    if os.path.isfile(p):
                        fname = os.path.basename(p)
                        if cls._should_skip_share_file(fname):
                            continue
                        try:
                            zf.write(p, arcname=_unique_arc(fname))
                        except (PermissionError, OSError):
                            continue
                    elif os.path.isdir(p):
                        root_folder = os.path.basename(p.rstrip("\\/")) or "folder"
                        for cur_dir, sub_dirs, file_names in os.walk(p, onerror=lambda _e: None):
                            rel_dir = os.path.relpath(cur_dir, p)
                            arc_dir = root_folder if rel_dir in (".", "") else f"{root_folder}/{rel_dir.replace(os.sep, '/')}"
                            written_here = False
                            for fn in file_names:
                                if cls._should_skip_share_file(fn):
                                    continue
                                full_f = os.path.join(cur_dir, fn)
                                try:
                                    zf.write(full_f, arcname=_unique_arc(f"{arc_dir}/{fn}"))
                                    written_here = True
                                except (PermissionError, OSError):
                                    continue
                            # 保留空目录层级
                            if not sub_dirs and not written_here:
                                dir_entry = arc_dir.rstrip("/") + "/"
                                if dir_entry not in used_arcnames:
                                    used_arcnames.add(dir_entry)
                                    zf.writestr(zipfile.ZipInfo(dir_entry), b"")
        except Exception:
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            except Exception:
                pass
            raise

        return zip_path, display_name, int(os.path.getsize(zip_path)), True

    SHARE_TTL_SECONDS = 15 * 60
    SHARE_REAPER_INTERVAL_SEC = 15.0
    _SHARE_REAPER_STARTED = False
    _SHARE_REAPER_LOCK = threading.Lock()

    @classmethod
    def _delete_temp_file_async(cls, path: str) -> None:
        if not path:
            return

        def _rm() -> None:
            for _ in range(3):
                if not os.path.exists(path):
                    return
                try:
                    os.remove(path)
                    return
                except Exception:
                    time.sleep(0.25)

        threading.Thread(target=_rm, daemon=True).start()

    @classmethod
    def _ensure_share_reaper_started(cls) -> None:
        with cls._SHARE_REAPER_LOCK:
            if cls._SHARE_REAPER_STARTED:
                return
            cls._SHARE_REAPER_STARTED = True

        def _reaper_loop() -> None:
            while True:
                time.sleep(cls.SHARE_REAPER_INTERVAL_SEC)
                try:
                    cls.reap_expired_shares()
                except Exception:
                    pass

        threading.Thread(target=_reaper_loop, daemon=True).start()

    @classmethod
    def reap_expired_shares(cls, now_ts: float | None = None) -> List[str]:
        """巡检 SHARE_REGISTRY，自动销毁超过 15 分钟未被领取或下载中断滞留的分享链接并清理临时缓存。"""
        now = time.time() if now_ts is None else float(now_ts)
        expired_items: List[Tuple[str, str, Any]] = []
        with _SHARE_REGISTRY_LOCK:
            for sid in list(SHARE_REGISTRY.keys()):
                ent = SHARE_REGISTRY.get(sid)
                if ent is None:
                    continue
                st = str(ent.get("status") or "READY")
                expires_at = float(ent.get("expires_at") or 0.0)
                active_streams = int(ent.get("active_streams") or 0)
                last_io_ts = float(ent.get("last_io_ts") or ent.get("created_at") or 0.0)
                should_expire = False
                if st == "EXPIRED":
                    should_expire = True
                elif st == "READY" and expires_at > 0 and now >= expires_at:
                    should_expire = True
                elif st == "DOWNLOADING" and active_streams <= 0 and (now - last_io_ts) >= 20.0:
                    # 传输结束/中断后无后续分片拉取的延迟清理兜底
                    should_expire = True
                if should_expire:
                    ent["status"] = "EXPIRED"
                    SHARE_REGISTRY.pop(sid, None)
                    temp_p = str(ent.get("path") or "") if ent.get("is_temp") else ""
                    cb = ent.get("on_state_cb")
                    expired_items.append((sid, temp_p, cb))

        expired_ids: List[str] = []
        for sid, temp_p, cb in expired_items:
            expired_ids.append(sid)
            if temp_p:
                cls._delete_temp_file_async(temp_p)
            if cb is not None:
                try:
                    cb(sid, "EXPIRED", "链接已自动过期销毁")
                except Exception:
                    pass
        return expired_ids

    @classmethod
    def register_share(
        cls,
        file_path: str,
        display_name: str,
        is_temp: bool = False,
        burn_after_read: bool = True,
        on_download_cb=None,
        on_state_cb=None,
        ttl_seconds: float | None = None,
    ) -> Dict[str, Any]:
        abs_path = os.path.abspath(file_path)
        size = int(os.path.getsize(abs_path)) if os.path.isfile(abs_path) else 0
        now = time.time()
        ttl = cls.SHARE_TTL_SECONDS if ttl_seconds is None else max(1.0, float(ttl_seconds))
        with _SHARE_REGISTRY_LOCK:
            share_id = "".join(secrets.choice(cls.SHARE_ID_ALPHABET) for _ in range(8))
            while share_id in SHARE_REGISTRY:
                share_id = "".join(secrets.choice(cls.SHARE_ID_ALPHABET) for _ in range(8))
            entry = {
                "id": share_id,
                "path": abs_path,
                "filename": str(display_name or os.path.basename(abs_path) or "download.bin"),
                "size": size,
                "size_str": cls._format_size(size),
                "is_temp": bool(is_temp),
                "burn_after_read": True,
                "status": "READY",       # READY -> DOWNLOADING -> EXPIRED
                "owner_fp": "",          # 首次下载者指纹 (client_ip|user_agent)
                "active_streams": 0,
                "final_chunk_done": False,
                "downloads": 0,
                "on_download_cb": on_download_cb,
                "on_state_cb": on_state_cb,
                "created_at": now,
                "created_ts": now,
                "expires_at": now + ttl,
                "last_io_ts": now,
            }
            SHARE_REGISTRY[share_id] = entry
        cls._ensure_share_reaper_started()
        return dict(entry)

    @classmethod
    def has_active_shares(cls) -> bool:
        with _SHARE_REGISTRY_LOCK:
            return any(str(v.get("status") or "") in ("READY", "DOWNLOADING") for v in SHARE_REGISTRY.values())

    @classmethod
    def set_share_burn_after_read(cls, share_id: str, enabled: bool) -> None:
        with _SHARE_REGISTRY_LOCK:
            ent = SHARE_REGISTRY.get(share_id)
            if ent is not None:
                ent["burn_after_read"] = bool(enabled)

    @classmethod
    def unregister_share(cls, share_id: str) -> None:
        if not share_id:
            return
        with _SHARE_REGISTRY_LOCK:
            ent = SHARE_REGISTRY.pop(share_id, None)
            if ent is not None:
                ent["status"] = "EXPIRED"
        if ent and ent.get("is_temp"):
            p = str(ent.get("path") or "")
            if p and os.path.isfile(p):
                cls._delete_temp_file_async(p)

    @classmethod
    def cleanup_all_share_cache(cls, share_cache_dir: str = SHARE_CACHE_DIR) -> None:
        with _SHARE_REGISTRY_LOCK:
            entries = list(SHARE_REGISTRY.values())
            for ent in entries:
                ent["status"] = "EXPIRED"
            SHARE_REGISTRY.clear()
        for ent in entries:
            if ent.get("is_temp"):
                p = ent.get("path", "")
                if p and os.path.isfile(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        if share_cache_dir and os.path.isdir(share_cache_dir):
            try:
                for fn in os.listdir(share_cache_dir):
                    fp = os.path.join(share_cache_dir, fn)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                        except Exception:
                            pass
            except Exception:
                pass

    def _build_share_expired_html(self) -> bytes:
        t = self.get_theme()
        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>链接已失效 · IdleMeter 文件快传</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;
background:{t["bg"]};color:{t["fg"]};font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;}}
.card{{width:100%;max-width:360px;background:{t["card_bg"]};border:1px solid {t["border"]};
border-radius:18px;padding:30px 24px;text-align:center;box-shadow:0 12px 32px rgba(0,0,0,.14);}}
.code{{font-size:44px;font-weight:800;color:{t["accent"]};letter-spacing:2px;margin-bottom:8px;}}
.title{{font-size:17px;font-weight:700;margin-bottom:8px;}}
.sub{{font-size:13px;color:{t["sub_fg"]};line-height:1.65;}}
</style>
</head>
<body>
<div class="card">
  <div class="code">410</div>
  <div class="title">链接已失效</div>
  <div class="sub">该一次性文件链接已被领取或已过期销毁</div>
</div>
</body>
</html>"""
        return html.encode("utf-8")

    def _build_wechat_guide_html(self, filename: str, size_str: str) -> bytes:
        t = self.get_theme()
        safe_name = (
            str(filename or "文件")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>在浏览器中打开下载 · IdleMeter</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:28px 22px;
background:{t["bg"]};color:{t["fg"]};font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;}}
.arrow{{position:fixed;top:14px;right:20px;display:flex;flex-direction:column;align-items:flex-end;gap:4px;color:{t["accent"]};font-weight:700;font-size:13px;}}
.card{{width:100%;max-width:360px;background:{t["card_bg"]};border:1px solid {t["border"]};
border-radius:18px;padding:28px 22px;text-align:center;box-shadow:0 12px 32px rgba(0,0,0,.14);}}
.badge{{display:inline-block;padding:4px 12px;border-radius:999px;font-size:12px;font-weight:600;
background:{t["accent"]}20;color:{t["accent"]};margin-bottom:14px;}}
.fname{{font-size:15px;font-weight:700;word-break:break-all;margin-bottom:6px;}}
.fsize{{font-size:12px;color:{t["sub_fg"]};margin-bottom:18px;}}
.tip{{font-size:14px;line-height:1.7;color:{t["fg"]};background:{t["input_bg"]};border:1px solid {t["border"]};
border-radius:12px;padding:14px 12px;}}
.tip b{{color:{t["accent"]};}}
</style>
</head>
<body>
<div class="arrow">
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
    <path d="M7 17L17 7"/><path d="M8 7h9v9"/>
  </svg>
  <span>点这里「···」</span>
</div>
<div class="card">
  <div class="badge">IdleMeter 文件快传</div>
  <div class="fname">{safe_name}</div>
  <div class="fsize">文件大小：{size_str}</div>
  <div class="tip">点击右上角 <b>「···」</b> 选择 <b>「在默认浏览器中打开」</b> 即可自动开始下载</div>
</div>
</body>
</html>"""
        return html.encode("utf-8")

    def start(self) -> Tuple[str, int]:
        if self._server is not None:
            if not self.get_access_token():
                self.generate_access_token(6)
            return self.ip, self.port
        self.ip = self.get_lan_ip()
        self.generate_access_token(6)
        parent_srv = self

        class _Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format, *args) -> None:
                return

            def _send_bytes(self, code: int, body: bytes, content_type: str, extra_headers: Dict[str, str] | None = None) -> None:
                self.close_connection = True
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                if extra_headers:
                    for hk, hv in extra_headers.items():
                        self.send_header(hk, hv)
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()

            def _check_internet_token(self, parsed) -> bool:
                """局域网与公网临时传输统一校验一次性 4~6 位随机安全 Token；缺失或无效则返回 403 拒绝访问。"""
                required = parent_srv.get_active_token()
                if not required:
                    return True
                qs = urllib.parse.parse_qs(parsed.query)
                q_tok = (qs.get("token") or [""])[0].strip()
                if q_tok == required:
                    return True
                h_tok = str(self.headers.get("X-Access-Token") or "").strip()
                if h_tok == required:
                    return True
                cookie_hdr = str(self.headers.get("Cookie") or "")
                for part in cookie_hdr.split(";"):
                    k, sep, v = part.strip().partition("=")
                    if sep and k == "idlemeter_token" and v.strip() == required:
                        return True
                self._send_bytes(
                    403,
                    "403 Forbidden · 缺少或无效的安全访问码 (token)".encode("utf-8"),
                    "text/plain; charset=utf-8",
                )
                return False

            def _send_file_stream(self, fpath: str, inline: bool = False) -> None:
                fsize = os.path.getsize(fpath)
                ctype = parent_srv._guess_mime_type(fpath) if inline else "application/octet-stream"
                quoted = urllib.parse.quote(os.path.basename(fpath))
                disp = "inline" if inline else "attachment"

                start_b = 0
                end_b = max(0, fsize - 1)
                status = 200
                rng_hdr = str(self.headers.get("Range") or "").strip()
                if inline and rng_hdr.startswith("bytes=") and fsize > 0:
                    m_rng = re.match(r"bytes=(\d*)-(\d*)", rng_hdr)
                    if m_rng:
                        s_raw, e_raw = m_rng.group(1), m_rng.group(2)
                        if s_raw:
                            start_b = max(0, min(fsize - 1, int(s_raw)))
                            end_b = min(fsize - 1, int(e_raw)) if e_raw else (fsize - 1)
                        elif e_raw:
                            tail = int(e_raw)
                            start_b = max(0, fsize - tail)
                            end_b = fsize - 1
                        if start_b <= end_b:
                            status = 206

                send_len = (end_b - start_b + 1) if fsize > 0 else 0
                self.close_connection = True
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(send_len))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Disposition", f"{disp}; filename*=UTF-8''{quoted}")
                if status == 206:
                    self.send_header("Content-Range", f"bytes {start_b}-{end_b}/{fsize}")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                if send_len <= 0:
                    return
                with open(fpath, "rb") as fh:
                    if start_b > 0:
                        fh.seek(start_b)
                    remain = send_len
                    while remain > 0:
                        chunk = fh.read(min(65536, remain))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remain -= len(chunk)
                self.wfile.flush()

            def _send_share_gone(self, head_only: bool = False) -> None:
                body = parent_srv._build_share_expired_html()
                if head_only:
                    self.close_connection = True
                    self.send_response(410)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "close")
                    self.end_headers()
                else:
                    self._send_bytes(410, body, "text/html; charset=utf-8")

            def _handle_share_request(self, share_id: str, head_only: bool = False) -> None:
                ua = str(self.headers.get("User-Agent") or "")
                ua_low = ua.lower()
                is_wx_or_qq = ("micromessenger" in ua_low) or ("qq/" in ua_low)
                rng_hdr = str(self.headers.get("Range") or "").strip()
                has_range = rng_hdr.startswith("bytes=")

                # 提取真实客户端 IP（穿透场景优先读取 Cloudflare/代理透传头）+ UA 组成接收方指纹
                cf_ip = str(self.headers.get("CF-Connecting-IP") or "").strip()
                xff = str(self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
                peer_ip = str(self.client_address[0] if self.client_address else "").strip()
                client_ip = cf_ip or xff or peer_ip
                client_fp = f"{client_ip}|{ua}"
                now = time.time()

                # HEAD 探测与微信/QQ 引导页不消耗唯一下载名额
                if head_only or is_wx_or_qq:
                    with _SHARE_REGISTRY_LOCK:
                        ent = SHARE_REGISTRY.get(share_id)
                        if (
                            ent is None
                            or ent.get("status") == "EXPIRED"
                            or (float(ent.get("expires_at") or 0.0) > 0 and now >= float(ent.get("expires_at") or 0.0))
                            or not os.path.isfile(str(ent.get("path") or ""))
                        ):
                            snap = None
                        elif ent.get("status") == "DOWNLOADING" and ent.get("owner_fp") != client_fp:
                            snap = None
                        else:
                            snap = dict(ent)

                    if snap is None:
                        self._send_share_gone(head_only=head_only)
                        return

                    if is_wx_or_qq:
                        body = parent_srv._build_wechat_guide_html(snap["filename"], snap["size_str"])
                        if head_only:
                            self.close_connection = True
                            self.send_response(200)
                            self.send_header("Content-Type", "text/html; charset=utf-8")
                            self.send_header("Content-Length", str(len(body)))
                            self.send_header("Connection", "close")
                            self.end_headers()
                        else:
                            self._send_bytes(200, body, "text/html; charset=utf-8")
                        return

                    # HEAD 探测：返回文件头但不消耗名额
                    fpath = snap["path"]
                    fsize = os.path.getsize(fpath)
                    quoted = urllib.parse.quote(snap["filename"])
                    self.close_connection = True
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quoted}")
                    self.send_header("Content-Length", str(fsize))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    return

                # 正式 GET 文件流请求：在锁内原子完成 READY -> DOWNLOADING 锁定及指纹校验
                just_locked = False
                state_cb = None
                snap = None
                with _SHARE_REGISTRY_LOCK:
                    ent = SHARE_REGISTRY.get(share_id)
                    if ent is None or not os.path.isfile(str(ent.get("path") or "")):
                        snap = None
                    else:
                        st = str(ent.get("status") or "READY")
                        exp_at = float(ent.get("expires_at") or 0.0)
                        if st == "EXPIRED" or (st == "READY" and exp_at > 0 and now >= exp_at):
                            ent["status"] = "EXPIRED"
                            SHARE_REGISTRY.pop(share_id, None)
                            if ent.get("is_temp"):
                                parent_srv._delete_temp_file_async(str(ent.get("path") or ""))
                            snap = None
                        elif st == "READY":
                            ent["status"] = "DOWNLOADING"
                            ent["owner_fp"] = client_fp
                            ent["active_streams"] = int(ent.get("active_streams") or 0) + 1
                            ent["last_io_ts"] = now
                            just_locked = True
                            state_cb = ent.get("on_state_cb")
                            snap = dict(ent)
                        elif st == "DOWNLOADING" and has_range and ent.get("owner_fp") == client_fp:
                            # 仅允许首次下载者本人携带 Range 头进行断点续传或多线程分片下载
                            ent["active_streams"] = int(ent.get("active_streams") or 0) + 1
                            ent["last_io_ts"] = now
                            snap = dict(ent)
                        else:
                            # 第二人点开或非 Range 重复请求 -> 严格拒绝 410 Gone
                            snap = None

                if snap is None:
                    self._send_share_gone(head_only=False)
                    return

                if just_locked and state_cb is not None:
                    try:
                        state_cb(share_id, "DOWNLOADING", "接收方正在下载（链接已锁定）...")
                    except Exception:
                        pass

                fpath = snap["path"]
                fname = snap["filename"]
                fsize = os.path.getsize(fpath)
                quoted = urllib.parse.quote(fname)

                start_b = 0
                end_b = max(0, fsize - 1)
                status = 200
                if has_range and fsize > 0:
                    m_rng = re.match(r"bytes=(\d*)-(\d*)", rng_hdr)
                    if m_rng:
                        s_raw, e_raw = m_rng.group(1), m_rng.group(2)
                        if s_raw:
                            start_b = max(0, min(fsize - 1, int(s_raw)))
                            end_b = min(fsize - 1, int(e_raw)) if e_raw else (fsize - 1)
                        elif e_raw:
                            tail = int(e_raw)
                            start_b = max(0, fsize - tail)
                            end_b = fsize - 1
                        if start_b <= end_b:
                            status = 206

                send_len = (end_b - start_b + 1) if fsize > 0 else 0
                self.close_connection = True
                self.send_response(status)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quoted}")
                self.send_header("Content-Length", str(send_len))
                self.send_header("Accept-Ranges", "bytes")
                if status == 206:
                    self.send_header("Content-Range", f"bytes {start_b}-{end_b}/{fsize}")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()

                completed = False
                try:
                    if send_len > 0:
                        with open(fpath, "rb") as fh:
                            if start_b > 0:
                                fh.seek(start_b)
                            remain = send_len
                            while remain > 0:
                                chunk = fh.read(min(65536, remain))
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                                remain -= len(chunk)
                        self.wfile.flush()
                    completed = True
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                    completed = False
                finally:
                    # 更新并发流计数并在传输完成时立即原子销毁链接与临时缓存
                    should_finalize = False
                    temp_to_delete = ""
                    done_cb = None
                    dl_cb = None
                    new_count = 0
                    with _SHARE_REGISTRY_LOCK:
                        live_ent = SHARE_REGISTRY.get(share_id)
                        if live_ent is not None:
                            live_ent["active_streams"] = max(0, int(live_ent.get("active_streams") or 1) - 1)
                            live_ent["last_io_ts"] = time.time()
                            reached_end = completed and (status == 200 or end_b >= max(0, fsize - 1))
                            if reached_end:
                                live_ent["final_chunk_done"] = True
                            if live_ent.get("final_chunk_done") and live_ent["active_streams"] <= 0:
                                live_ent["status"] = "EXPIRED"
                                live_ent["downloads"] = int(live_ent.get("downloads") or 0) + 1
                                new_count = live_ent["downloads"]
                                done_cb = live_ent.get("on_state_cb")
                                dl_cb = live_ent.get("on_download_cb")
                                SHARE_REGISTRY.pop(share_id, None)
                                if live_ent.get("is_temp"):
                                    temp_to_delete = str(live_ent.get("path") or "")
                                should_finalize = True

                    if should_finalize:
                        if temp_to_delete:
                            parent_srv._delete_temp_file_async(temp_to_delete)
                        if dl_cb is not None:
                            try:
                                dl_cb(share_id, new_count, True)
                            except Exception:
                                pass
                        if done_cb is not None:
                            try:
                                done_cb(share_id, "COMPLETED", "对方已成功接收，链接已自动销毁")
                            except Exception:
                                pass

            def do_HEAD(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                m_share = re.match(r"^/s/([A-Za-z0-9]{4,32})$", parsed.path)
                if m_share:
                    self._handle_share_request(m_share.group(1), head_only=True)
                    return
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()

            def _detect_request_mode(self) -> str:
                host = str(self.headers.get("Host") or "").lower()
                if (
                    "trycloudflare.com" in host
                    or bool(self.headers.get("CF-Connecting-IP"))
                    or bool(self.headers.get("Cf-Ray"))
                ):
                    return "internet"
                if bool(parent_srv.get_internet_token()) and (
                    str(self.headers.get("X-Forwarded-Proto") or "").lower() == "https"
                    or parent_srv.get_active_mode() == "internet"
                ):
                    return "internet"
                return "lan"

            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                m_share = re.match(r"^/s/([A-Za-z0-9]{4,32})$", parsed.path)
                if m_share:
                    self._handle_share_request(m_share.group(1), head_only=False)
                    return
                if not self._check_internet_token(parsed):
                    return
                req_mode = self._detect_request_mode()
                if parsed.path == "/":
                    required = parent_srv.get_active_token()
                    extra = {"Set-Cookie": f"idlemeter_token={required}; Path=/; SameSite=Lax"} if required else None
                    self._send_bytes(200, parent_srv._build_h5_html(), "text/html; charset=utf-8", extra_headers=extra)
                    return
                if parsed.path in ("/api/state", "/api/shared"):
                    items = [
                        {
                            "id": x["id"],
                            "kind": x["kind"],
                            "name": x["name"],
                            "text": x["text"],
                            "size_str": x["size_str"],
                            "time_str": x["time_str"],
                        }
                        for x in parent_srv.list_shared_items(mode=req_mode)
                    ]
                    is_net = req_mode == "internet"
                    payload = {
                        "items": items,
                        "messages": parent_srv.list_chat_messages(mode=req_mode),
                        "theme": parent_srv.get_theme(),
                        "is_internet": is_net,
                        "mode": req_mode,
                    }
                    self._send_bytes(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                    return
                if parsed.path in ("/api/media", "/api/download"):
                    qs = urllib.parse.parse_qs(parsed.query)
                    item_id = (qs.get("id") or [""])[0]
                    fpath = parent_srv.resolve_media_path(item_id)
                    if not fpath or not os.path.isfile(fpath):
                        self._send_bytes(404, b"Not Found", "text/plain; charset=utf-8")
                        return
                    self._send_file_stream(fpath, inline=(parsed.path == "/api/media"))
                    return
                self._send_bytes(404, b"Not Found", "text/plain; charset=utf-8")

            def do_POST(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                if not self._check_internet_token(parsed):
                    return
                req_mode = self._detect_request_mode()
                cl = int(self.headers.get("Content-Length") or 0)
                if parsed.path == "/api/text":
                    raw = self.rfile.read(cl) if cl > 0 else b"{}"
                    try:
                        data = json.loads(raw.decode("utf-8"))
                        txt = str(data.get("text") or "")
                        dev_id = str(data.get("device_id") or self.headers.get("X-Device-Id") or "").strip()
                        msg_obj = None
                        if txt.strip():
                            msg_obj = parent_srv.record_phone_text(txt, device_id=dev_id, mode=req_mode)
                            if parent_srv._on_receive_text:
                                parent_srv._on_receive_text(txt)
                        self._send_bytes(
                            200,
                            json.dumps({"ok": True, "message": msg_obj}, ensure_ascii=False).encode("utf-8"),
                            "application/json; charset=utf-8",
                        )
                    except Exception as exc:
                        self._send_bytes(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                    return

                if parsed.path == "/api/upload":
                    ctype = str(self.headers.get("Content-Type") or "")
                    m = re.search(r'boundary=([^;]+)', ctype)
                    if not m or cl <= 0:
                        self._send_bytes(400, b"Bad Request", "text/plain; charset=utf-8")
                        return
                    boundary = m.group(1).strip().strip('"').encode("utf-8")
                    header_dev_id = str(self.headers.get("X-Device-Id") or "").strip()

                    # 64KB 分块流式直接落盘（不将整文件读入内存）
                    saved_paths, duration_sec, form_dev_id = parent_srv._stream_parse_multipart(
                        self.rfile, cl, boundary, chunk_size=65536
                    )
                    dev_id = form_dev_id or header_dev_id

                    created_msgs: List[Dict[str, Any]] = []
                    for dest in saved_paths:
                        created_msgs.append(
                            parent_srv.record_phone_file(dest, duration=duration_sec, device_id=dev_id, mode=req_mode)
                        )

                    # 落盘完毕立刻秒回 200 OK JSON，彻底消除手机端进度条卡 99% 等待
                    self._send_bytes(
                        200,
                        json.dumps({"ok": True, "count": len(saved_paths), "messages": created_msgs}, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8",
                    )

                    # 响应发出后再异步执行桌面端缩略图生成、剪贴板写入与聊天记录 UI 刷新
                    if saved_paths and parent_srv._on_receive_file:
                        cb_fn = parent_srv._on_receive_file
                        paths_copy = list(saved_paths)

                        def _dispatch_received() -> None:
                            for p in paths_copy:
                                try:
                                    cb_fn(p)
                                except Exception:
                                    pass

                        threading.Thread(target=_dispatch_received, daemon=True).start()
                    return
                self._send_bytes(404, b"Not Found", "text/plain; charset=utf-8")

        port = self.DEFAULT_PORT
        srv: ThreadingHTTPServer | None = None
        for offset in range(32):
            try:
                srv = ThreadingHTTPServer(("0.0.0.0", port + offset), _Handler)
                port = port + offset
                break
            except OSError:
                continue
        if srv is None:
            raise RuntimeError("无法绑定局域网互传端口")
        self.port = port
        self._server = srv
        self._thread = threading.Thread(target=srv.serve_forever, daemon=True)
        self._thread.start()
        self._ensure_firewall_rule_async()
        return self.ip, self.port

    def stop(self) -> None:
        self.set_internet_token("")
        self.set_access_token("")
        srv = self._server
        self._server = None
        if srv is not None:
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:
                pass


class CacheManager:
    """统一管理程序缓存目录统计与安全迁移（锚点文件 path_config.json 始终保留在用户主目录）。"""

    CACHE_SUBDIRS = ("clipboard_cache", "手机互传接收", "bin")

    @staticmethod
    def save_path_config(cache_dir: str) -> None:
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(PATH_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"cache_dir": cache_dir}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def get_effective_cache_dir(cfg: AppConfig | None = None) -> str:
        if os.path.isfile(PATH_CONFIG_FILE):
            try:
                with open(PATH_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                p = str(data.get("cache_dir") or "").strip()
                if p:
                    os.makedirs(p, exist_ok=True)
                    return p
            except Exception:
                pass
        custom = (getattr(cfg, "cache_dir", "") or "").strip() if cfg is not None else ""
        target = custom if custom else DATA_DIR
        os.makedirs(target, exist_ok=True)
        return target

    @classmethod
    def calc_cache_size_bytes(cls, cache_root: str) -> int:
        total = 0
        for sub in cls.CACHE_SUBDIRS:
            d = os.path.join(cache_root, sub)
            if os.path.isdir(d):
                for root_dir, _dirs, files in os.walk(d):
                    for fn in files:
                        fp = os.path.join(root_dir, fn)
                        try:
                            total += os.path.getsize(fp)
                        except Exception:
                            pass
        hist_file = os.path.join(cache_root, "clipboard_history.json")
        if os.path.isfile(hist_file):
            try:
                total += os.path.getsize(hist_file)
            except Exception:
                pass
        return total

    @classmethod
    def migrate_cache(cls, old_root: str, new_root: str) -> Tuple[bool, str]:
        old_abs = os.path.abspath(old_root)
        new_abs = os.path.abspath(new_root)
        if old_abs == new_abs:
            return False, "新目录与当前缓存目录相同"
        try:
            if os.path.commonpath([old_abs, new_abs]) == old_abs:
                return False, "不能迁移到原缓存目录的子目录"
        except Exception:
            pass

        os.makedirs(new_abs, exist_ok=True)
        for sub in cls.CACHE_SUBDIRS:
            src_sub = os.path.join(old_abs, sub)
            dst_sub = os.path.join(new_abs, sub)
            if not os.path.isdir(src_sub):
                continue
            os.makedirs(dst_sub, exist_ok=True)
            for root_dir, _dirs, files in os.walk(src_sub):
                rel = os.path.relpath(root_dir, src_sub)
                target_dir = dst_sub if rel == "." else os.path.join(dst_sub, rel)
                os.makedirs(target_dir, exist_ok=True)
                for fn in files:
                    src_f = os.path.join(root_dir, fn)
                    dst_f = os.path.join(target_dir, fn)
                    try:
                        if not os.path.exists(dst_f):
                            shutil.copy2(src_f, dst_f)
                        os.remove(src_f)
                    except Exception:
                        pass
            try:
                shutil.rmtree(src_sub, ignore_errors=True)
            except Exception:
                pass

        old_hist = os.path.join(old_abs, "clipboard_history.json")
        new_hist = os.path.join(new_abs, "clipboard_history.json")
        if os.path.isfile(old_hist):
            try:
                with open(old_hist, "r", encoding="utf-8") as f:
                    items = json.load(f)
                if isinstance(items, list):
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        ip = str(it.get("image_path") or "")
                        if ip.startswith(old_abs):
                            it["image_path"] = new_abs + ip[len(old_abs):]
                        fps = it.get("file_paths") or []
                        it["file_paths"] = [
                            (new_abs + p[len(old_abs):]) if isinstance(p, str) and p.startswith(old_abs) else p
                            for p in fps
                        ]
                with open(new_hist, "w", encoding="utf-8") as f:
                    json.dump(items, f, ensure_ascii=False, indent=2)
                os.remove(old_hist)
            except Exception:
                pass

        cls.save_path_config(new_abs)
        return True, new_abs


class SlackingStatsManager:
    """带薪摸鱼时长、薪资折算与按日/24小时时段本地持久化管理。"""

    def __init__(self, filepath: str = SLACKING_STATS_FILE):
        self.filepath = filepath
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.isfile(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict) and isinstance(raw.get("days"), dict):
                    return raw
            except Exception:
                pass
        return {"days": {}}

    def _save_locked(self) -> None:
        _ensure_parent_dir(self.filepath)
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def calc_rate_per_second(cfg: AppConfig, ref_date: date | None = None) -> float:
        salary = float(getattr(cfg, "monthly_salary", 0.0) or 0.0)
        if salary <= 0.0:
            return 0.0
        if ref_date is None:
            ref_date = date.today()
        ws_h, ws_m = TimeCalculator.parse_hm(getattr(cfg, "work_start", "09:30"), (9, 30))
        we_h, we_m = TimeCalculator.parse_hm(getattr(cfg, "work_end", "18:30"), (18, 30))
        ls_h, ls_m = TimeCalculator.parse_hm(getattr(cfg, "lunch_start", "12:00"), (12, 0))
        le_h, le_m = TimeCalculator.parse_hm(getattr(cfg, "lunch_end", "13:00"), (13, 0))
        work_mins = (we_h * 60 + we_m) - (ws_h * 60 + ws_m)
        lunch_mins = max(0, (le_h * 60 + le_m) - (ls_h * 60 + ls_m))
        daily_secs = max(3600.0, float(work_mins - lunch_mins) * 60.0)

        _, days_in_month = calendar.monthrange(ref_date.year, ref_date.month)
        workdays = 0
        for d in range(1, days_in_month + 1):
            cur = date(ref_date.year, ref_date.month, d)
            if not TimeCalculator.is_rest_day(cur, cfg):
                workdays += 1
        workdays = max(1, workdays)
        return salary / (float(workdays) * daily_secs)

    def record_session(self, start_ts: float, end_ts: float, cfg: AppConfig) -> float:
        if end_ts <= start_ts:
            return 0.0
        rate = self.calc_rate_per_second(cfg)
        earned_total = (end_ts - start_ts) * rate
        cur = start_ts
        with self._lock:
            days_map = self._data.setdefault("days", {})
            while cur < end_ts:
                dt_cur = datetime.fromtimestamp(cur)
                next_hour_dt = (dt_cur.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
                seg_end = min(end_ts, next_hour_dt.timestamp())
                seg_secs = max(0.0, seg_end - cur)
                day_key = dt_cur.strftime("%Y-%m-%d")
                entry = days_map.setdefault(day_key, {"seconds": 0.0, "earned": 0.0, "hours": [0.0] * 24})
                if not isinstance(entry.get("hours"), list) or len(entry["hours"]) != 24:
                    entry["hours"] = [0.0] * 24
                entry["seconds"] = float(entry.get("seconds", 0.0)) + seg_secs
                entry["earned"] = float(entry.get("earned", 0.0)) + seg_secs * rate
                entry["hours"][dt_cur.hour] = float(entry["hours"][dt_cur.hour]) + seg_secs
                cur = seg_end
            self._save_locked()
        return earned_total

    def get_summary(self, live_secs: float = 0.0, live_earned: float = 0.0) -> Dict[str, Dict[str, float]]:
        today = date.today()
        today_key = today.strftime("%Y-%m-%d")
        week_keys = {(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)}
        month_keys = {(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)}
        with self._lock:
            days_map = self._data.get("days", {})
            t_sec = float(days_map.get(today_key, {}).get("seconds", 0.0)) + live_secs
            t_earn = float(days_map.get(today_key, {}).get("earned", 0.0)) + live_earned
            w_sec = sum(float(days_map.get(k, {}).get("seconds", 0.0)) for k in week_keys) + live_secs
            w_earn = sum(float(days_map.get(k, {}).get("earned", 0.0)) for k in week_keys) + live_earned
            m_sec = sum(float(days_map.get(k, {}).get("seconds", 0.0)) for k in month_keys) + live_secs
            m_earn = sum(float(days_map.get(k, {}).get("earned", 0.0)) for k in month_keys) + live_earned
        return {
            "today": {"seconds": t_sec, "earned": t_earn},
            "week": {"seconds": w_sec, "earned": w_earn},
            "month": {"seconds": m_sec, "earned": m_earn},
        }

    def get_curve_data(
        self, mode: str = "today", live_secs: float = 0.0
    ) -> Tuple[List[str], List[float], int]:
        today = date.today()
        with self._lock:
            days_map = self._data.get("days", {})
            if mode == "today":
                today_key = today.strftime("%Y-%m-%d")
                hours = list(days_map.get(today_key, {}).get("hours", [0.0] * 24))
                if len(hours) != 24:
                    hours = [0.0] * 24
                cur_hr = datetime.now().hour
                hours[cur_hr] = float(hours[cur_hr]) + live_secs
                labels = [f"{h:02d}" for h in range(24)]
                vals = [round(float(x) / 60.0, 2) for x in hours]
            elif mode == "7d":
                labels, vals = [], []
                for i in range(6, -1, -1):
                    d = today - timedelta(days=i)
                    k = d.strftime("%Y-%m-%d")
                    s = float(days_map.get(k, {}).get("seconds", 0.0)) + (live_secs if i == 0 else 0.0)
                    labels.append(d.strftime("%m-%d"))
                    vals.append(round(s / 60.0, 2))
            else:
                labels, vals = [], []
                for i in range(29, -1, -1):
                    d = today - timedelta(days=i)
                    k = d.strftime("%Y-%m-%d")
                    s = float(days_map.get(k, {}).get("seconds", 0.0)) + (live_secs if i == 0 else 0.0)
                    labels.append(d.strftime("%m-%d"))
                    vals.append(round(s / 60.0, 2))
        peak_idx = max(range(len(vals)), key=lambda idx: vals[idx]) if vals else 0
        return labels, vals, peak_idx

    def get_progressive_workday_curve(
        self, cfg: AppConfig, live_secs: float = 0.0, now: datetime | None = None
    ) -> Tuple[List[str], List[float], int]:
        """严格按有效工作时段（剔除午休）生成渐进式放大生长曲线。"""
        if now is None:
            now = datetime.now()
        ws_h, ws_m = TimeCalculator.parse_hm(getattr(cfg, "work_start", "09:30"), (9, 30))
        we_h, we_m = TimeCalculator.parse_hm(getattr(cfg, "work_end", "18:30"), (18, 30))
        ls_h, ls_m = TimeCalculator.parse_hm(getattr(cfg, "lunch_start", "12:00"), (12, 0))
        le_h, le_m = TimeCalculator.parse_hm(getattr(cfg, "lunch_end", "13:00"), (13, 0))

        ws_min = ws_h * 60 + ws_m
        we_min = max(ws_min + 60, we_h * 60 + we_m)
        ls_min = ls_h * 60 + ls_m
        le_min = le_h * 60 + le_m

        # 按 30 分钟划分有效工作时段（自动剔除午休）
        buckets: List[Tuple[int, str]] = []
        cur = ws_min
        while cur < we_min:
            if not (ls_min <= cur < le_min):
                buckets.append((cur // 60, f"{cur // 60:02d}:{cur % 60:02d}"))
            cur += 30
        if not buckets:
            buckets = [(h, f"{h:02d}:00") for h in range(9, 19)]

        today_key = now.strftime("%Y-%m-%d")
        with self._lock:
            hours = list(self._data.get("days", {}).get(today_key, {}).get("hours", [0.0] * 24))
            if len(hours) != 24:
                hours = [0.0] * 24
        hours[now.hour] = float(hours[now.hour]) + max(0.0, live_secs)

        # 将小时数据映射到有效时段桶，并根据当前已积累的有效时间点做动态放大拉伸
        raw_vals = [round(float(hours[hr]) / 60.0, 2) for hr, _lbl in buckets]
        last_nonzero = 0
        for idx, v in enumerate(raw_vals):
            if v > 0.0:
                last_nonzero = idx
        now_min = now.hour * 60 + now.minute
        cur_idx = 0
        for idx, (hr, lbl) in enumerate(buckets):
            b_min = hr * 60 + int(lbl.split(":")[1])
            if b_min <= now_min:
                cur_idx = idx
        visible_count = max(4, min(len(buckets), max(last_nonzero, cur_idx) + 1))

        vis_labels = [buckets[i][1] for i in range(visible_count)]
        vis_vals = [raw_vals[i] for i in range(visible_count)]
        peak_idx = max(range(len(vis_vals)), key=lambda i: vis_vals[i]) if vis_vals else 0
        return vis_labels, vis_vals, peak_idx


class AlarmManager:
    """闹钟提醒持久化、6种提醒模式触发时间计算及法定节假日/周末顺延逻辑。"""

    MODES = (
        ("once", "只提醒一次"),
        ("next_day", "次日提醒"),
        ("daily", "每日提醒"),
        ("workday", "工作日提醒"),
        ("monthly", "每月提醒"),
        ("monthly_workday", "每月工作日提醒"),
    )
    MODE_LABELS = dict(MODES)
    BUILTIN_RINGTONES = (
        ("builtin_chime", "经典清脆"),
        ("builtin_bell", "柔和风铃"),
        ("builtin_pulse", "双音提示"),
        ("builtin_radar", "雷达脉冲"),
    )
    BUILTIN_RINGTONE_LABELS = dict(BUILTIN_RINGTONES)

    def __init__(self, filepath: str = ALARMS_FILE):
        self.filepath = filepath
        self._lock = threading.Lock()
        self._alarms: List[Dict[str, Any]] = []
        self._custom_ringtones: List[str] = []
        self._load()

    def _load(self) -> None:
        if os.path.isfile(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    self._alarms = [a for a in (raw.get("alarms") or []) if isinstance(a, dict)]
                    self._custom_ringtones = [str(p) for p in (raw.get("custom_ringtones") or []) if str(p).strip()]
            except Exception:
                self._alarms = []
                self._custom_ringtones = []

    def _save_locked(self) -> None:
        _ensure_parent_dir(self.filepath)
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {"alarms": self._alarms, "custom_ringtones": self._custom_ringtones},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass

    def list_alarms(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(a) for a in self._alarms]

    def list_custom_ringtones(self) -> List[str]:
        with self._lock:
            return [p for p in self._custom_ringtones if os.path.isfile(p)]

    def add_custom_ringtone(self, path: str) -> None:
        p = os.path.abspath(str(path or "").strip())
        if not p or not os.path.isfile(p):
            return
        with self._lock:
            if p not in self._custom_ringtones:
                self._custom_ringtones.append(p)
                self._save_locked()

    def upsert_alarm(self, alarm: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(alarm)
        if not item.get("id"):
            item["id"] = uuid.uuid4().hex[:10]
        item.setdefault("enabled", True)
        item.setdefault("pinned", False)
        item.setdefault("hour", 9)
        item.setdefault("minute", 30)
        item.setdefault("mode", "daily")
        item.setdefault("target_date", date.today().strftime("%Y-%m-%d"))
        item.setdefault("month_day", date.today().day)
        item.setdefault("workday_adjust", "next")
        item.setdefault("note", "")
        item.setdefault("ringtone", "none")
        item.setdefault("snooze_until", 0.0)
        item.setdefault("last_fired_key", "")
        with self._lock:
            if item.get("pinned"):
                for a in self._alarms:
                    a["pinned"] = False
            replaced = False
            for i, a in enumerate(self._alarms):
                if a.get("id") == item["id"]:
                    self._alarms[i] = item
                    replaced = True
                    break
            if not replaced:
                self._alarms.append(item)
            self._save_locked()
        return item

    def delete_alarm(self, alarm_id: str) -> None:
        with self._lock:
            self._alarms = [a for a in self._alarms if a.get("id") != alarm_id]
            self._save_locked()

    def set_enabled(self, alarm_id: str, enabled: bool) -> None:
        with self._lock:
            for a in self._alarms:
                if a.get("id") == alarm_id:
                    a["enabled"] = bool(enabled)
                    if not enabled:
                        a["snooze_until"] = 0.0
                    break
            self._save_locked()

    def set_pinned(self, alarm_id: str, pinned: bool) -> None:
        with self._lock:
            if pinned:
                for a in self._alarms:
                    a["pinned"] = (a.get("id") == alarm_id)
            else:
                for a in self._alarms:
                    if a.get("id") == alarm_id:
                        a["pinned"] = False
            self._save_locked()

    def snooze_alarm(self, alarm_id: str, seconds: int = 300) -> None:
        with self._lock:
            for a in self._alarms:
                if a.get("id") == alarm_id:
                    a["snooze_until"] = time.time() + seconds
                    break
            self._save_locked()

    @staticmethod
    def is_legal_workday(d: date, cfg: AppConfig) -> bool:
        raw = HolidayService.get_initial_raw_data(d.year)
        hol_map = raw.get("holiday") if isinstance(raw, dict) else None
        key = d.strftime("%Y-%m-%d")
        if isinstance(hol_map, dict) and key in hol_map:
            info = hol_map[key]
            if isinstance(info, dict) and "holiday" in info:
                return not bool(info["holiday"])
        return not TimeCalculator.is_rest_day(d, cfg)

    @classmethod
    def adjust_monthly_workday(
        cls, year: int, month: int, day_num: int, adjust: str, cfg: AppConfig
    ) -> Tuple[date, bool, date]:
        _, dim = calendar.monthrange(year, month)
        raw_d = date(year, month, min(max(1, day_num), dim))
        if cls.is_legal_workday(raw_d, cfg):
            return raw_d, False, raw_d
        step = -1 if adjust == "prev" else 1
        cur = raw_d
        for _ in range(31):
            cur = cur + timedelta(days=step)
            if cls.is_legal_workday(cur, cfg):
                return cur, True, raw_d
        return raw_d, True, raw_d

    @classmethod
    def compute_next_trigger(
        cls, alarm: Dict[str, Any], cfg: AppConfig, now: datetime | None = None
    ) -> Tuple[datetime | None, bool, date | None]:
        if now is None:
            now = datetime.now()
        snooze_ts = float(alarm.get("snooze_until") or 0.0)
        if snooze_ts > now.timestamp():
            return datetime.fromtimestamp(snooze_ts), False, None

        hr = int(alarm.get("hour", 9))
        mn = int(alarm.get("minute", 0))
        mode = str(alarm.get("mode") or "daily")

        if mode == "once":
            try:
                d = datetime.strptime(str(alarm.get("target_date") or ""), "%Y-%m-%d").date()
            except ValueError:
                d = now.date()
            dt = datetime(d.year, d.month, d.day, hr, mn)
            return (dt, False, d) if dt > now else (None, False, d)

        if mode == "next_day":
            try:
                d = datetime.strptime(str(alarm.get("target_date") or ""), "%Y-%m-%d").date()
            except ValueError:
                d = now.date() + timedelta(days=1)
            dt = datetime(d.year, d.month, d.day, hr, mn)
            return (dt, False, d) if dt > now else (None, False, d)

        if mode == "daily":
            dt = datetime(now.year, now.month, now.day, hr, mn)
            if dt <= now:
                dt += timedelta(days=1)
            return dt, False, dt.date()

        if mode == "workday":
            start_off = 0 if datetime(now.year, now.month, now.day, hr, mn) > now else 1
            for off in range(start_off, start_off + 45):
                cand = now.date() + timedelta(days=off)
                if cls.is_legal_workday(cand, cfg):
                    return datetime(cand.year, cand.month, cand.day, hr, mn), False, cand
            return None, False, None

        if mode == "monthly":
            m_day = int(alarm.get("month_day") or 1)
            y, m = now.year, now.month
            for _ in range(13):
                _, dim = calendar.monthrange(y, m)
                cand = date(y, m, min(max(1, m_day), dim))
                dt = datetime(cand.year, cand.month, cand.day, hr, mn)
                if dt > now:
                    return dt, False, cand
                m += 1
                if m > 12:
                    m = 1
                    y += 1
            return None, False, None

        if mode == "monthly_workday":
            m_day = int(alarm.get("month_day") or 1)
            adj = str(alarm.get("workday_adjust") or "next")
            y, m = now.year, now.month
            for _ in range(13):
                adj_d, was_adj, raw_d = cls.adjust_monthly_workday(y, m, m_day, adj, cfg)
                dt = datetime(adj_d.year, adj_d.month, adj_d.day, hr, mn)
                if dt > now:
                    return dt, was_adj, raw_d
                m += 1
                if m > 12:
                    m = 1
                    y += 1
            return None, False, None

        return None, False, None

    def get_primary_alarm(self, cfg: AppConfig, now: datetime | None = None) -> Dict[str, Any] | None:
        if now is None:
            now = datetime.now()
        alarms = self.list_alarms()
        if not alarms:
            return None
        pool = [a for a in alarms if a.get("enabled", True)] or alarms

        def _sort_key(a: Dict[str, Any]) -> Tuple[int, float]:
            pinned_rank = 0 if a.get("pinned", False) else 1
            nxt, _, _ = self.compute_next_trigger(a, cfg, now)
            ts = nxt.timestamp() if nxt is not None else float("inf")
            return (pinned_rank, ts)

        pool.sort(key=_sort_key)
        return pool[0]

    def check_due_alarms(self, cfg: AppConfig, now: datetime | None = None) -> List[Dict[str, Any]]:
        if now is None:
            now = datetime.now()
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        due: List[Dict[str, Any]] = []
        changed = False
        with self._lock:
            for a in self._alarms:
                if not a.get("enabled", True):
                    continue
                snooze_ts = float(a.get("snooze_until") or 0.0)
                if snooze_ts > 0.0 and now.timestamp() >= snooze_ts:
                    a["snooze_until"] = 0.0
                    a["last_fired_key"] = minute_key
                    due.append(dict(a))
                    changed = True
                    continue
                if a.get("last_fired_key") == minute_key:
                    continue
                # 检查当前分钟是否命中触发点（传入 now - 1s 以便精确匹配当前分钟）
                probe_now = now.replace(second=0, microsecond=0) - timedelta(seconds=1)
                nxt, _, _ = self.compute_next_trigger(a, cfg, probe_now)
                if nxt is not None and nxt.strftime("%Y-%m-%d %H:%M") == minute_key:
                    a["last_fired_key"] = minute_key
                    if a.get("mode") in ("once", "next_day"):
                        a["enabled"] = False
                    due.append(dict(a))
                    changed = True
            if changed:
                self._save_locked()
        return due
