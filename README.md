# Signal 模拟器轮转版：恢复源码包

本包从 `Signal模拟器轮转版.exe`（SHA-256: `91375d695b1f49e37e21652c89d18c4da59ec971cff3d310671e4f18b8b0f4ff`）中恢复。

## 包含内容

- `bytecode_project/`：从最终 EXE 提取的完整入口和 22 个 `console` 模块的 Python 3.12 字节码。
- `disassembly/`：每个模块的 Python 3.12 指令反汇编，可据此改写为普通 `.py`。
- `module_manifest.json`：模块、字节码与反汇编文件的对应关系。

## 后期修改方式

1. 使用 Python 3.12。
2. 在 `bytecode_project/console/` 下新建同名 `.py` 文件，例如 `engine.py`。Python 会优先加载 `.py`，从而覆盖同名 `.pyc`。
3. 以 `disassembly/console/engine.txt` 为逻辑参考，将需修改的模块逐步还原为普通 Python 代码。
4. 修改完成后再使用 PyInstaller 重新打包。

## 限制

PyInstaller 只在最终 EXE 中保留字节码，原始注释、排版和部分局部变量命名无法无损还原。因此本包保留原始 `.pyc` 作为可运行的准确逻辑备份，同时提供反汇编供后续改写。

## 2Captcha 修复

本修复包新增两个同名源码覆盖层：

- `bytecode_project/console/captcha_solver.py`：补齐 2Captcha token → Signal deep link 提交。
- `bytecode_project/console/signal_support/registration.py`：补齐注册页面的自动验证分支，并防止同一挑战重复付费提交。

原始 `.pyc` 均保留不变。运行测试：

```powershell
py -3.12 tests/test_captcha_repair.py
py -3.12 tests/test_full_system.py
```

`test_full_system.py` 覆盖模块导入、SQLite 数据结构、账号统计、任务队列、五类业务 dry-run、
分类型并发限制、接码客户端夹具、手机号与素材文件、CSV/XLSX 导出、DPAPI、代理/计划任务辅助逻辑。

## 启动源码版

```powershell
py -3.12 bytecode_project/launcher.py
```

自检启动：

```powershell
py -3.12 bytecode_project/launcher.py --data-home smoke_data --smoke-test
```

## 2026.10 全面优化层

- 启动时自动执行 SQLite 完整性检查，并启用 WAL、8 秒忙等待、500 页自动 checkpoint。
- 为任务队列、日志、结果、账号、计划任务增加 8 个查询索引。
- 每 24 小时生成一次 SQLite 一致性备份，滚动保留最近 7 份。
- 每次启动生成脱敏的 `health-latest.json`，包含环境、磁盘、ADB、MuMu、数据库和队列状态。
- 标题栏显示“优化版”和当前健康分。
- 提供指数退避重试工具，为后续外部 API 适配器统一复用。
- PyInstaller 自检会真实导入 2Captcha 和注册修复层，不再固定返回成功。

### 界面优化

- 统一深色主题、按钮、输入框、表格标题、选中状态和隔行底色。
- 左侧导航显示当前页面高亮。
- 新增“文件 / 运行 / 视图 / 工具 / 帮助”菜单。
- `Ctrl+K` 打开页面快速切换器，支持输入筛选 13 个页面。
- `Ctrl+1～9` 页面直达，`F5` 刷新，`F9/F10` 开始与暂停，`Ctrl+H` 打开健康中心。
- 表格支持多选、右键复制、全选和 `Ctrl+C` 复制。
- 支持 `Ctrl++ / Ctrl+- / Ctrl+0` 调整界面比例。
- 自动记忆窗口大小、位置、上次页面和缩放比例。
- 工具菜单提供健康中心、立即数据库备份、模拟器窗口刷新和系统设置入口。

独立健康检查：

```powershell
py -3.12 bytecode_project/launcher.py --data-home runtime --health-check
```
