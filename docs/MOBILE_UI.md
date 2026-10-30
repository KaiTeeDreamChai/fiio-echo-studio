# 移动端 UI 适配方案（Android 优先）

> 目标：在保留桌面工作台的前提下，为 Android 手机做一套真正可用的界面，而不是"把三栏压成一栏"。
> 本文覆盖：现状诊断、目标信息架构、交互与版式规范、组件改造映射、Android 运行时前置决策、分阶段计划。

---

## 1. 现状诊断：现在这版只是"桌面缩小"

在 412×915（Pixel 7 尺寸）下实测三屏（截图见 `docs/assets/mobile-current-queue.png` / `-detail.png`），问题按严重度排列：

### P0 · 结构性
1. **顶部占用过高**：品牌区 + 目录输入 + 三个页签共约 330px，占屏幕 36%；真正的内容区只剩一半。
2. **页签在顶部**：单手够不到；文案换行（`03 LOCAL LIBRARY` 两行），页签高度 90px。
3. **曲目仍用桌面表格**：`TARGET FOLDER` 重复占位、`STATE` 列被裁切（`构建`/`FIX` 只露出半个）、需要横向滑动才能看全。
4. **"三栏 = 三页签"是错误映射**：桌面第 02 栏是"选中曲目的详情"，在手机上它应该由"点列表项进入"产生，而不是一个并列页签。

### P1 · 可用性
5. **触控目标过小**：复选框 14px、`↑/↓` 约 28px、`BROWSE` 约 34px，低于 Android 建议的 48dp。
6. **字号过密**：正文 12px 等宽字体，长曲名/长路径全部靠截断。
7. **行内编辑目录路径**：手机上不该出现可编辑的绝对路径输入框，应改为"当前目录 + 更改"。
8. **无安全区处理**：没有 `viewport-fit=cover` / `env(safe-area-inset-*)`，`100vh` 在移动浏览器里会随地址栏抖动。
9. **LRC 预览横向溢出**：长句直接被裁断，没有换行或"点击展开"。

### P2 · 平台差异
10. `BROWSE` 走 `osascript`（macOS 专属）；Android 必须换成 SAF 文件选择。
11. `dot_clean` / FAT32 物理排序是桌面 + 外接卡的能力；手机上要么隐藏，要么明确"需连接电脑"。
12. 导入歌单时一次性对全部已下载曲目做探测（最多数千首），手机端会明显卡顿，需要懒加载/分页。

---

## 2. 目标信息架构

```
┌ 底部三 Tab ─────────────────────────────┐
│  乐库 (Library)   曲目 (Queue)   构建 (Build)  │
└────────────────────────────────────────┘
        │                │                 │
        ▼                ▼                 ▼
 专辑/歌单浏览      当前队列(卡片)      指标/目录/进度
 搜索 + 作者筛选    筛选 chips          开始/取消
 导入按钮           多选 + 排序         TF 工具(桌面专属项隐藏)
        │                │
        │                └──▶ 曲目详情（全屏页，返回手势回列表）
        │
        └──▶ 设置抽屉（主题、目标播放器配置、关于、源目录）

全局：顶部 56dp App Bar（标题 + 当前集合 + 溢出菜单），不再放输入框。
```

### 关键取舍
- **详情不是 Tab**：列表 → 详情是层级关系，用系统返回手势/返回键即可退出。
- **构建是 Tab**：它是"一次长任务的入口 + 进度 + 结果"，需要独立空间和常驻状态。
- **设置进抽屉**：目录、主题、目标配置属于低频操作，不该占据首屏。
- **保留瑞士风**：黑/白/灰 + 国际橙、细线分隔、等宽数据；但**中文优先**做标签，英文等宽只做副标题/数值，减少 `TARGET FOLDER` 这类占宽的说明文字。

---

## 3. 版式与交互规范

### 断点（按 Android 窗口尺寸类别）
| 类别 | 宽度 | 布局 |
|---|---|---|
| Compact | < 600dp | 单栏 + 底部导航 + 详情全屏 |
| Medium | 600–1023dp | 列表 + 详情双栏（列表 40%），导航改侧边 rail |
| Expanded | ≥ 1024dp | 现有桌面三栏（≥1180 保持现状） |

> 现在 `useAdaptiveLayout` 的 768/1180 两个阈值建议改为 600/1024，并与 Material 3 的 window size class 对齐。

### 尺寸与触控
- 最小触控目标 **48×48dp**；复选框视觉 18dp、命中区 48dp。
- 列表项高度 ≥ 72dp；底部导航 56dp + 安全区。
- 正文 14sp、次要 12sp、等宽数据 11–12sp；行高 ≥1.5。
- 圆角保持 0（瑞士风），用 1px 实线和留白建立层次。

### 移动端不适用的东西
- 悬停态（hover）→ 改为按下态（active）。
- 三列表格 → 卡片；参数列不再平铺，收进详情页或折叠区。
- 横向滚动容器（除 chips 行）。

### 安全区与滚动
```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
```
```css
.shell { height: 100dvh; }
.bottom-nav { padding-bottom: calc(10px + env(safe-area-inset-bottom)); }
.appbar { padding-top: env(safe-area-inset-top); }
```
- 列表用 `overscroll-behavior: contain`，避免整页回弹。
- 长列表必须虚拟化（`2738` 首的歌单是真实场景）。

### 状态与无障碍
- 状态色保持：合规=绿 `#0F8A5F`、待规范=橙 `#FF3300`、未下载=灰、加密=深灰。
- 所有图标按钮补 `aria-label`；状态不只靠颜色，配文字（`OK`/`待解密`）。
- 暗色主题跟随 `prefers-color-scheme`，手动切换作为覆盖项记住。

---

## 4. 组件改造映射

| 现在 | 移动端目标 | 处理方式 |
|---|---|---|
| `SwissHeader` | `MobileAppBar` + `SettingsSheet` | 拆分：标题/副标题/溢出菜单；目录、主题、重置进抽屉 |
| `QueuePanel`（含表格） | `LibraryTab` + `QueueTab` | 提取筛选/选择逻辑为 hook；表格保留给桌面，新增 `TrackCardList` |
| `InspectorPanel` | `TrackDetailScreen` | 手机端全屏页（路由或全屏 sheet），桌面仍作为第 02 栏 |
| `LocalLibraryPanel` | `BuildTab` | 指标、输出目录、构建按钮、进度、日志、TF 工具分区 |
| `TelemetryFooter` | 构建页内日志 + 底部 Snackbar | 手机端不再常驻整条页脚 |
| `useAdaptiveLayout` | `useWindowSizeClass` | 改 3 档：compact/medium/expanded，监听 `matchMedia` 与旋转 |

新增目录建议：

```
src/components/mobile/
├── MobileShell.tsx        # 安全区 + 布局骨架
├── MobileAppBar.tsx
├── BottomNav.tsx
├── TrackCard.tsx
├── FilterChips.tsx
├── TrackDetailScreen.tsx
├── BuildTab.tsx
└── SettingsSheet.tsx
```

---

## 5. Android 运行时的三个前置决策（会影响 UI 取舍）

1. **外壳形态**
   - 方案 A（推荐先做）：`Capacitor` + 现有 React UI，WebView 复用 95% 界面；先跑通"手机能看能用"。
   - 方案 B：Kotlin + Compose 原生重写，体验最好但工作量大，UI 需要重做一遍。
2. **引擎怎么跑**（真正的难点，不是 UI）
   - `Chaquopy` 在 App 内跑 CPython + 现有 `engine/`，HTTP 服务监听 `127.0.0.1`，WebView 指向它 —— 代码复用最高，但包体 +40–60MB、启动变慢，且 Chaquopy 对 Python 版本有限制。
   - 或把引擎移植到 Kotlin（FLAC 解析、封面处理、ffmpeg 调用、ncmdump 移植），长期更轻，但工作量最大。
   - **建议并行做一次技术验证**：在 Android 上跑通"`.ncm` → 解密 → 4096 重封装 → 写回"，再决定是否投入原生重写。
3. **存储与目录**
   - 桌面是"绝对路径"；Android 是 scoped storage，需要 SAF 目录授权（`content://`），Python 侧不能直接按路径读写。
   - 需要抽象一层 `StorageTarget`（桌面=路径，Android=SAF 树 URI + 本地镜像），并明确"写入 TF 卡"在 Android 上的可行路径（SAF 或 `MANAGE_EXTERNAL_STORAGE`）。
   - `dot_clean`、FAT32 物理排序在 Android 上没有直接等价物 → 手机上隐藏这两项，或标注"请连接电脑执行"。

---

## 6. 分阶段计划

### P0 · 技术验证（0.5–1 天）
- 用 Capacitor 建一个 Android 壳，加载现有构建产物，真机跑一遍触控/滚动/返回键。
- 产出一句话结论：WebView 方案的手感能否接受。

**验收**：手机上能打开现有界面、切页签、列表可滚动，无明显掉帧。

### P1 · 移动端骨架（2–3 天）
- 新断点体系 + `MobileShell`（安全区、100dvh）。
- 底部三 Tab + 56dp App Bar。
- 曲目列表卡片化，筛选 chips，48dp 触控目标。
- 桌面布局保持不变（回归测试）。

**验收**：390×844 与 360×740 下无横向滚动、无裁切；触控目标达标；桌面截图与现在一致。

### P2 · 详情页与构建页（3–4 天）
- 详情全屏页（返回手势）。
- 构建页：目录选择（改为动作）、进度/取消/日志、TF 工具条件展示。
- 长列表虚拟化 + 探测结果懒加载/分页。

**验收**：2738 首歌单可流畅滚动；构建过程可见进度、可取消。

### P3 · 平板与打磨（2–3 天）
- Medium 宽度的双栏布局、Expanded 回归三栏。
- 无障碍标签、暗色跟随系统、动效克制。
- Android 返回键语义：详情 → 列表 → Tab 根 → 退出。

---

## 7. 待确认

1. 外壳先走 **Capacitor（WebView）** 还是直接 **Compose 原生**？（建议先 Capacitor 验证手感）
2. 底部导航用 **乐库 / 曲目 / 构建** 三分法，还是保留 **导入 / 检视 / 输出** 的旧命名？
3. 手机端是否需要"编辑目标目录"这种手动分类能力？（桌面有，手机上可能只保留"整张专辑/歌单"级别）
4. 构建输出在 Android 上先写"应用私有目录"还是直接要求 SAF 选 TF 卡？

---

*草图：`docs/assets/mobile-wireframe.png`（曲目队列 / 曲目详情 / 构建页）*
