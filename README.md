# FiiO Echo Studio

给飞傲 / SNOWSKY 便携无损播放器整理乐库的本地工具。macOS Apple Silicon。

![工作台](assets/screenshots/workbench-preview.png)

播放器的嵌入式解码器只有 4 KB DMA 缓冲，又按 FAT32 目录项顺序播放。未处理的音频，或者网易云客户端下载回来的 `.ncm`，直接拷进 TF 卡通常就是切歌爆音、卡顿死机、封面不显示、顺序错乱。这个工具在拷贝之前把文件修到硬件能用的状态。

## 处理什么

| 约束 | 处理 |
|---|---|
| FLAC 帧 BlockSize ≤ 4096 | 超标的用 `ffmpeg -frame_size 4096` 重封装。PCM 位精确，不重采样 |
| 封面 500×500 baseline JPEG、YUV 4:2:0、Type 3 | 缩放加黑边补齐，清掉多余的 picture 块 |
| 同名 `.lrc`、`[mm:ss.xx]`、UTF-8 无 BOM + CRLF | 清掉网易云的 `{"t":...}` 逐字时间轴。要 BOM 就设 `FIIO_LRC_BOM=1` |
| `.ncm` 解密 | 走 `ncmdump`，输出扩展名按真实容器决定，MP3 不会被改成 `.flac` |
| FAT32 目录项顺序 | 文件搬出再按序搬回，然后跑 `dot_clean` 清 `._*` 和 `.DS_Store` |

封面来源依次是内嵌图 → 网易云本地缓存 `meta/track-<id>.jpg` → 数据库 `picUrl` 联网下载。都没有就保持无封面，在构建报告里注明。

网易云这边有个坑：封面在 FLAC 元数据里常写成 0×0，真实字节却是 1115×1115 的 4:4:4。所以合规判定读的是 JPEG 的 SOF 段，不信元数据。

界面上的帧大小、位深、采样率、封面尺寸都是 mutagen 实测值，读不到就显示 `—`，加密 `.ncm` 显示"待解密"，没有占位数字。

## 数据来源

直接读网易云客户端的本地 SQLite，只读打开。库文件和下载目录自动扫描，不用手填；要覆盖就设 `NETEASE_DB_PATH` 和 `NETEASE_DOWNLOAD_DIR`。

## 安装

预编译包在 [Releases](../../releases)，拖进 Applications 即可，依赖都在里面。没做 Apple 公证，被 Gatekeeper 拦就右键 → 打开。

从源码跑：

```bash
brew install ffmpeg ncmdump
npm install
python3 -m engine.server --port 57123    # 后端
npm run dev                               # 前端 http://localhost:5173
```

打包：

```bash
./build_app.sh    # → dist_app/FiiO Echo Studio.app 与同名 DMG
```

`engine/bin/` 里的 ffmpeg 和 ncmdump 不入库，`build_app.sh` 会从 `node_modules/ffmpeg-static`、`PATH` 或 Homebrew 补齐。

## 用法

左侧选专辑或歌单（支持模糊搜索），中间看实测参数和不合规原因，勾选后构建。构建完再对 TF 卡跑一次目录排序和幽灵文件清理。

输出：

```text
<乐库根目录>/
├── echo_library.json
└── Albums/
    └── Hurry Up Tomorrow/
        ├── 01 The Weeknd - São Paulo.flac    # 也可能是 .mp3，看真实容器
        └── 01 The Weeknd - São Paulo.lrc
```

## 测试

```bash
python3 -m unittest discover -s engine/tests -v    # 21 个
```

测试用的音频由 ffmpeg 现场生成，没有 ffmpeg 会跳过相关用例。

## 限制

- 加密 `.ncm` 解密前读不到内部参数，界面显示"待解密"。
- 只处理 FLAC 和 MP3，其他容器以 `UNSUPPORTED_CONTAINER` 失败。
- FAT32 目录项顺序尽力而为，最终由文件系统驱动决定。
- 打包和 `dot_clean` 只支持 macOS。
- 只在 macOS Apple Silicon 上验证过。

## 许可

[WTFPL](LICENSE)。数据丢失、硬件损坏之类的后果自负。想适配别的播放器（Shanling、HiBy、Walkman）欢迎提 PR。
