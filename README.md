# FIIO ECHO STUDIO
### 飞傲便携无损播放器专用乐库规范化工作台

<div align="center">

[![Platform](https://img.shields.io/badge/PLATFORM-macOS%20ARM64-000000.svg?style=flat-square&logo=apple)](https://github.com/KaiTeeDreamChai/fiio-echo-studio)
[![UI Design](https://img.shields.io/badge/UI-SWISS%20INTERNATIONAL-FF3300.svg?style=flat-square)](https://github.com/KaiTeeDreamChai/fiio-echo-studio)
[![Codec Compliance](https://img.shields.io/badge/FLAC-BLOCKSIZE%20%E2%89%A4%204096-000000.svg?style=flat-square)](https://github.com/KaiTeeDreamChai/fiio-echo-studio)
[![Tests](https://img.shields.io/badge/TESTS-19%20PASSED-000000.svg?style=flat-square)](engine/tests/test_core.py)
[![License](https://img.shields.io/badge/LICENSE-WTFPL-FF3300.svg?style=flat-square)](LICENSE)

</div>

---

<div align="center">
  <img src="assets/screenshots/workbench-preview.png" alt="FiiO Echo Studio Workbench" width="960" />
</div>

---

## 01 // OVERVIEW

这是一套专为 **飞傲（FiiO）/ SNOWSKY 便携无损音乐播放器**（如 FiiO Echo 及同架构硬件）深度定制的乐库管理工作台。

便携硬件播放器受限于嵌入式解码芯片算力、DMA 缓冲区大小与 FAT32 文件系统寻址机制，直接拷入未经处理的现代流媒体音频或高规格曲目常导致 **切歌爆音、死机卡顿、封面无法渲染、乱码及按物理扇区乱序播放**。

本工作台遵循 **Swiss International Typographic Style** 设计构建。

### 核心设计原则
* **严谨硬件合规 (Hardware Exactness)**：所有重构均面向硬件解码器的物理约束，绝不进行劣质重采样。
* **无损与元数据完整 (Bit-Exact Integrity)**：仅规整 FLAC 元数据容器与 Frame BlockSize，100% 保持 16/24-bit PCM 音频无损。
* **只显示实测值 (No Invented Numbers)**：界面上的帧大小、位深、采样率、封面尺寸全部由后端 `mutagen` 读取真实字节得出；读不到就显示 `—`，绝不猜。
* **信息高密度与纯粹排版 (Swiss Typographic UI)**：无浮夸装饰，采用严谨的网格系统、非对称信息排布与等宽数据检视。

---

## 02 // HARDWARE SPECIFICATION (硬件解码与存储规格)

工作台流水线自动执行以下五维硬件合规校验与物理重整：

| # | 检视维度 (DIMENSION) | 硬件严苛指标 (HARDWARE TARGET) | 自动化流水线处理机制 (AUTO-PIPELINE) | 状态 |
|---|---|---|---|---|
| **01** | **FLAC 帧块大小** | `BlockSize ≤ 4096` (4KB DMA 限制) | 读取 `STREAMINFO.max_blocksize`；超标时用 `ffmpeg -c:a flac -frame_size 4096` 重封装并复核 | `ENFORCED` |
| **02** | **内嵌封面渲染** | `500 × 500` Baseline JPEG (`YUV 4:2:0`)、Type 3 | 解析封面真实像素（含 `0×0` 元数据的网易云封面），等比缩放+黑边填充，清除多余 Picture 块；**源文件无封面时优先读取网易云客户端本地 `meta/track-<id>.jpg`，缺失才用 `picUrl` 联网补全** | `ENFORCED` |
| **03** | **同名同步歌词** | 严格同名 `.lrc`，`[mm:ss.xx]`，UTF-8、CRLF | 清洗网易云 `{"t":...}` 脏词、毫秒三位截断、NFC 归一；默认**不写 BOM**（可用 `FIIO_LRC_BOM=1` 开启） | `ENFORCED` |
| **04** | **网易加密解密** | 原生 `16/24-bit` 无损还原 | 原生 `ncmdump` 解密 `.ncm`，并**按真实容器决定输出扩展名**（FLAC 保持 `.flac`，MP3 保持 `.mp3`） | `ENFORCED` |
| **05** | **FAT32 物理槽位** | 目录项按 `01..N` 连续排列 | 将目录内文件移出再按序移回以重建目录项顺序，并执行 `dot_clean` 与 `._*`/`.DS_Store` 清理 | `BEST-EFFORT` |

> **关于第 05 项**：FAT32 目录项由文件系统驱动分配，重建后仍可能被驱动重排，因此这里提供的是"尽力而为"的物理顺序重建，而不是硬件级保证。此前版本该按钮只做统计却回报成功，现已改为真实搬移并回报处理数量。

### 额外保障
* **原生 macOS 菜单栏**：文件（⌘R 重新探测、⌘B 构建、⌘O 选择输出目录）、编辑、视图（⌘T 切换主题、⌘⇧R 重载）、窗口、帮助；菜单项通过事件与界面联动，不是摆设。
* **本机数据源自动识别**：启动时扫描网易云客户端的多个可能位置（Application Support / Containers），按数据库大小与表结构选出真实库；下载目录不写死，而是用 `offlineTrack` 里的真实文件名去候选目录命中打分，命中率最高的即真实下载目录。可用 `NETEASE_DB_PATH`、`NETEASE_DOWNLOAD_DIR` 环境变量覆盖。
* **FAT32 文件名净化**：`\ / : * ? " < > |` 与 DOS 保留名、超长名称都会被安全替换/截断，避免"在 Mac 上能生成、拷进 SD 卡就报错"。
* **构建任务化**：大库构建在后台线程执行，界面实时显示 `已完成/总数`、当前曲目，并支持中途取消。
* **本地接口防越权**：仅允许 `127.0.0.1` / `localhost` 的 `Host` 与 `Origin` 访问，任意网页无法调用写文件接口。

---

## 03 // WORKBENCH ARCHITECTURE (工作台架构)

### 三栏工作台功能设计
* **来源侧栏**：网易云本地专辑/歌单双模态、**模糊搜索**（专辑名/歌手、歌单名/作者）、**我创建 / 我收藏**切换、作者/歌手模糊筛选、重新探测、导入、手动创建分类。
* **COL 01: 乐库与队列检视**：已下载感知、真实帧大小/封面列、自定义目标目录归档与物理上下排序。
* **COL 02: 硬件规范深度透视**：真实 PCM 参数、帧大小合规判定、封面真实分辨率/色度抽样与不合规原因、LRC 清洗前后对照。
* **COL 03: 规范构建与输出**：目标路径挂载、后台任务进度与取消、构建统计、FAT32 目录项重建与 macOS 幽灵文件净化。

### 技术栈构成 (Tech Stack)
* **GUI 工作台**：React 19 + TypeScript + Tailwind CSS（瑞士国际设计系统，深浅双主题即时切换）
* **桌面原生桥接**：Python 3 + Cocoa `pywebview`（原生 macOS WKWebView）
* **音频与元数据引擎**：`mutagen` + 静态 `ffmpeg` + 原生 `ncmdump`
* **独立桌面打包**：PyInstaller 6.x + Apple Developer Command Line Tools + `hdiutil` 自动化 DMG 构建

---

## 04 // INSTALLATION & DOWNLOAD

### 方式 A: 预编译安装包（推荐）

1. 前往 [Releases](../../releases) 下载最新版：
   * `FiiO_Echo_Studio_v1.2.0_arm64.dmg`（macOS Apple Silicon）
2. 双击打开 DMG，将 **FiiO Echo Studio** 拖入 **Applications**。
3. 首次启动无需安装任何依赖（`ffmpeg`、`ncmdump` 与 Python 运行时均已内置）。
4. 应用为 ad-hoc 签名、未做 Apple 公证；若 Gatekeeper 拦截，请右键 App → **打开**。

### 方式 B: 从源码运行与开发构建

```bash
# 0. 依赖：Node 20+ / Python 3.10+ / ffmpeg / ncmdump
brew install ffmpeg ncmdump

# 1. 克隆本仓库
git clone https://github.com/KaiTeeDreamChai/fiio-echo-studio.git
cd fiio-echo-studio

# 2. 安装前端依赖
npm install

# 3. 开发模式（两个终端）
python3 -m engine.server --port 57123   # 后端 API
npm run dev                              # 前端 http://localhost:5173

# 4. 一键打包 macOS 独立桌面 App 及 DMG
chmod +x build_app.sh
./build_app.sh
```

构建产物：
* `dist_app/FiiO Echo Studio.app`
* `dist_app/FiiO_Echo_Studio_v1.2.0_arm64.dmg`

> `engine/bin/` 中的 `ffmpeg`、`ncmdump` 不入库。`build_app.sh` 会自动尝试从 `node_modules/ffmpeg-static`、`PATH` 或 Homebrew 补齐，缺失时给出明确指引。

---

## 05 // USAGE WORKFLOW

```text
[ 网易云音乐本地下载 ]
        │
        ▼
[ 1. 扫描与检索 ] ──► 读取本地 SQLite 专辑/歌单，标注已下载与未下载
        │
        ▼
[ 2. 真实参数探测 ] ──► mutagen 读取帧大小 / 位深 / 采样率 / 封面真实像素
        │                （加密 .ncm 显示"待解密"，不猜测）
        ▼
[ 3. 分类与排序 ] ──► 调整目标目录（Albums / Playlists）与播放物理顺次
        │
        ▼
[ 4. 后台规范化构建 ] ──► NCM 解密 ➔ FLAC 重封装 ➔ 封面归一化 ➔ 歌词生成
        │                 （逐首进度、可取消、可单曲执行）
        ▼
[ 5. 存储介质净化 ] ──► FAT32 目录项按序重建 ➔ macOS 幽灵文件清除
        │
        ▼
[ 插入 FiiO 播放器开机即播，无卡顿爆音 ]
```

### 输出结构

```text
<library_root>/
├── echo_library.json
└── Albums/
    └── Hurry Up Tomorrow/
        ├── 01 The Weeknd - São Paulo.flac   # 或 .mp3（按真实容器）
        └── 01 The Weeknd - São Paulo.lrc
```

---

## 06 // TESTING

```bash
# 后端单元测试（文件名净化 / LRC / 探测 / 流水线 / 构建器 / provider）
python3 -m unittest discover -s engine/tests -v

# 无界面探测单曲
python3 -m engine.bridge inspect --file "/path/to/track.flac"

# 命令行构建（与 App 共用同一套代码）
python3 -m engine.bridge build-library --config build.json
```

---

## 07 // KNOWN LIMITATIONS (已知限制)

* 加密 `.ncm` 在构建前无法读取内部参数，界面会明确显示"待解密"，而不是编造数值。
* 封面来源优先级：音频内嵌图 → 网易云客户端本地缓存 `~/Music/网易云音乐/meta/track-<id>.jpg`（离线可用，实测覆盖 457/457 首）→ 数据库 `picUrl` 联网补全。三处都没有时才会保留无封面并在报告中注明。
* 仅处理 `FLAC` / `MP3` 容器；其他格式会以 `UNSUPPORTED_CONTAINER` 明确失败。
* 打包与 `dot_clean` 相关能力仅面向 macOS。
* FAT32 目录项顺序属于尽力而为，最终顺序仍取决于文件系统驱动。

---

## 08 // PROJECT ROADMAP (项目演进路线)

- [x] 瑞士国际主义风格高对比 UI 与深浅色自适应模式
- [x] 网易云音乐本地 SQLite 库只读检索与多专辑/歌单聚合
- [x] FLAC BlockSize 探测与降级至 4096 物理帧（构建后复核）
- [x] 封面真实像素解析与 Baseline JPEG 500x500 / YUV 4:2:0 归一化
- [x] 无内嵌封面时优先使用网易云本地 `meta/track-<id>.jpg` 缓存，离线可用
- [x] 本地缓存缺失时再从 `picUrl` 联网补全
- [x] 同名 LRC 同步清洗（UTF-8 无 BOM + CRLF，可选 BOM）
- [x] FAT32 目录项重建与 macOS `dot_clean` 净化
- [x] 后台构建任务、实时进度、取消与单曲执行
- [x] 本地 API 的 Host/Origin 校验
- [x] macOS 单文件 App 与 DMG 打包流水线
- [ ] 添加 Windows / Android / Linux 等平台支持
- [ ] 添加多配置文件支持，以适配更多播放器（Shanling、HiBy、Sony Walkman 等）

---

## 09 // CONTRIBUTING & LICENSE (开源协议)

欢迎提交 Issue 与 Pull Request 共同完善对更多硬件播放器（如 Shanling、HiBy、Sony Walkman 等）的特殊音频与文件系统适配。

本项目采用 [WTFPL](LICENSE) 开源许可证，因使用本软件所造成的任何数据丢失、硬件损坏或异常损失概不负责。

---

<div align="center">
  <sub>CRAFTED WITH PRECISION FOR AUDIOPHILES & PORTABLE DAPS</sub><br>
  <sub>DESIGNED IN SWISS INTERNATIONAL TYPOGRAPHIC STYLE</sub>
</div>
