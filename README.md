# IdleMeter（摸鱼小工具）

一款基于 **Python + PySide6** 打造的 Windows 极简桌面效率与摸鱼双模式桌面工具，支持深色/浅色主题与强调色实时切换、迷你悬浮窗以及本地化数据存储。

---

## 核心功能亮点

### 摸鱼模式
- **实时时钟与进度追踪**：自定义上下班时间与发薪日，提供下班、周末（支持自定义休息日）及发薪日三合一倒计时进度条，支持三个槽位独立自定义目标倒计时。
- **摸鱼计时与统计**：支持一键开始/结束带薪摸鱼计时，查看今日与历史摸鱼统计图表及估算收益。
- **法定节假日与调休**：内置节假日日历与调休识别，支持联网同步最新节假日安排与弹窗全览。
- **加班/调休记录**：便捷记录加班与调休时长，自动统计剩余可调休时间。
- **迷你悬浮窗**：顶部一键切换为桌面紧凑悬浮条，实时显示时间、核心倒计时与进度条。

### 工作模式
- **多线程分片下载器**：支持 6 线程 16MB 分片并发下载与断点续传，适配大文件稳定下载。
- **局域网手机互传**：内置 HTTP 服务与二维码直连，手机扫码即可与电脑互传文字和文件，网页端配色实时同步桌面主题；支持临时公网分享。
- **本地剪贴板历史**：自动监听并保存文本与图片剪贴板记录，支持分类筛选、悬停预览与一键复制。
- **闹钟提醒**：支持只提醒一次、次日、每日、工作日、每月及每月工作日（遇周末/节假日支持提前或延后至最近工作日）6 种模式，支持置顶互斥、自定义铃声/静音、5 分钟稍后提醒。
- **桌面小工具**：集成多屏 DPI 自适应的截图识字（OCR）与屏幕取色器。

---

## 下载与运行（Windows）

### 方式一：直接下载 Release 可执行文件（推荐）
1. 前往本仓库的 [Releases](https://github.com/Bluen01/PayTick-Releases/releases) 页面，下载最新版本的 `IdleMeter.exe`。
2. 双击 `IdleMeter.exe` 即可直接运行，无需安装 Python 环境。
3. 程序默认将个人配置、闹钟、剪贴板历史及接收文件存放在 `C:\Users\<用户名>\.摸鱼小工具`，不会污染程序所在目录。

---

## 本地源码运行与打包

### 环境要求
- Windows 10 / 11
- Python 3.10+（推荐 Python 3.12 / 3.13）

### 1. 克隆仓库并安装依赖
```bash
git clone https://github.com/Bluen01/PayTick-Releases.git
cd PayTick-Releases
pip install -r requirements.txt
```

### 2. 从源码启动
```bash
python main.py
```
也可双击项目根目录的 `启动摸鱼小工具.bat` 或 `静默启动.vbs` 快速启动。

### 3. 使用 PyInstaller 打包为单文件 `.exe`
先安装 PyInstaller：
```bash
pip install pyinstaller
```
使用项目提供的 spec 文件打包：
```bash
pyinstaller --clean --noconfirm IdleMeter.spec
```
或直接通过命令行参数打包：
```bash
pyinstaller --clean --noconfirm --onefile --windowed --icon=app_icon.ico --add-data "app_icon.ico;." --name IdleMeter main.py
```
打包完成后，可执行文件位于 `dist/IdleMeter.exe`。

---

## 开源协议

本项目基于 [MIT License](LICENSE) 开源。
