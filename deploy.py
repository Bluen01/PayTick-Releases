import ctypes
import os
import re
import shutil
import subprocess
import sys
import requests

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_local_env(env_path: str) -> None:
    """从同级 .env 文件读取 KEY=VALUE 并写入 os.environ。"""
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, val)


_load_local_env(os.path.join(PROJECT_DIR, ".env"))

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "") or "Bluen01"
GITHUB_REPO = os.environ.get("GITHUB_REPO", "") or "PayTick-Releases"

MAIN_PY_PATH = os.path.join(PROJECT_DIR, "main.py")
CORE_PY_PATH = os.path.join(PROJECT_DIR, "core.py")
DIST_EXE_PATH = os.path.join(PROJECT_DIR, "dist", "IdleMeter.exe")
APP_NAME = "IdleMeter"


def update_source_version(new_version: str) -> None:
    """更新 main.py 中的 CURRENT_VERSION 与 core.py 中的 APP_VERSION。"""
    with open(MAIN_PY_PATH, "r", encoding="utf-8") as f:
        main_src = f.read()
    updated_main, count = re.subn(
        r'^(CURRENT_VERSION\s*=\s*")[^"]*(")',
        rf"\g<1>{new_version}\2",
        main_src,
        flags=re.MULTILINE,
    )
    if count == 0:
        raise RuntimeError("未在 main.py 中找到 CURRENT_VERSION 常量")
    with open(MAIN_PY_PATH, "w", encoding="utf-8") as f:
        f.write(updated_main)

    if os.path.exists(CORE_PY_PATH):
        with open(CORE_PY_PATH, "r", encoding="utf-8") as f:
            core_src = f.read()
        updated_core, core_count = re.subn(
            r'^(APP_VERSION\s*=\s*")[^"]*(")',
            rf"\g<1>{new_version}\2",
            core_src,
            flags=re.MULTILINE,
        )
        if core_count > 0:
            with open(CORE_PY_PATH, "w", encoding="utf-8") as f:
                f.write(updated_core)


def refresh_windows_icon_cache() -> None:
    """刷新 Windows 资源管理器图标缓存，使新打包的同名 exe 立即显示最新图标。"""
    try:
        subprocess.run(
            ["ie4uinit.exe", "-show"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass


def build_exe() -> str:
    """调用 PyInstaller 打包为单文件无黑框 .exe（打包前清理 build 缓存并启用 --clean）。"""
    build_dir = os.path.join(PROJECT_DIR, "build")
    if os.path.isdir(build_dir):
        print(f"[2/3] 正在清理旧构建缓存目录: {build_dir}")
        shutil.rmtree(build_dir, ignore_errors=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--icon=app_icon.ico",
        "--add-data",
        "app_icon.ico;.",
        "--name",
        APP_NAME,
        "main.py",
    ]
    print(f"[2/3] 正在执行打包命令: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=PROJECT_DIR)
    if res.returncode != 0 or not os.path.exists(DIST_EXE_PATH):
        raise RuntimeError(f"PyInstaller 打包失败，退出码：{res.returncode}")
    refresh_windows_icon_cache()
    print(f"[2/3] 打包成功: {DIST_EXE_PATH}")
    return DIST_EXE_PATH


def publish_github_release(version: str, changelog: str, exe_path: str) -> None:
    """调用 GitHub Releases API 创建新 Release 并上传 exe 附件。"""
    if not GITHUB_TOKEN or GITHUB_TOKEN == "你的Token" or "【" in GITHUB_TOKEN or "【" in GITHUB_OWNER or "【" in GITHUB_REPO:
        raise RuntimeError("请先在同级 .env 文件或环境变量中填入真实的 GITHUB_TOKEN")

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    tag_name = f"v{version}"
    create_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
    payload = {
        "tag_name": tag_name,
        "name": f"{APP_NAME} {tag_name}",
        "body": changelog,
        "draft": False,
        "prerelease": False,
    }

    print(f"[3/3] 正在创建 GitHub Release ({tag_name})...")
    resp = requests.post(create_url, headers=headers, json=payload, timeout=20)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"创建 Release 失败 ({resp.status_code}): {resp.text}")

    release_data = resp.json()
    upload_url_tpl = release_data["upload_url"]
    upload_base = upload_url_tpl.split("{")[0]
    asset_name = os.path.basename(exe_path)
    upload_url = f"{upload_base}?name={asset_name}"

    print(f"[3/3] 正在上传附件 {asset_name}...")
    upload_headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/octet-stream",
    }
    with open(exe_path, "rb") as f:
        up_resp = requests.post(upload_url, headers=upload_headers, data=f, timeout=180)
    if up_resp.status_code not in (200, 201):
        raise RuntimeError(f"上传附件失败 ({up_resp.status_code}): {up_resp.text}")

    html_url = release_data.get("html_url", "")
    print(f"[3/3] 发布成功！Release 地址: {html_url}")


def main() -> None:
    print("=== IdleMeter 一键打包与 GitHub Release 发布工具 ===")
    raw_ver = input("请输入新版本号 (例如 1.0.14): ").strip()
    new_version = raw_ver.lstrip("vV")
    if not re.match(r"^\d+(\.\d+)*$", new_version):
        print("版本号格式无效，请输入如 1.0.14 的数字版本号。")
        sys.exit(1)

    print("请输入更新日志 (支持多行，输入空行结束):")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    changelog = "\n".join(lines).strip() or f"IdleMeter v{new_version} 更新"

    print(f"[1/3] 正在更新源码版本号为 {new_version}...")
    update_source_version(new_version)

    exe_path = build_exe()
    publish_github_release(new_version, changelog, exe_path)


if __name__ == "__main__":
    main()
