# Qoder 专家团第三方 API 启用工具

让 Qoder 专家团（Experts）在**第三方 API（BYOK）模式**下使用自定义模型
（如 DeepSeek），突破客户端对 experts 通道的代码级限制。
实测通过：模型可选、可对话、上下文可配置（默认注入 1M）。

## 项目背景

Qoder 的专家团功能仅支持官方模型编排（`experts-auto` 等），第三方 API 模式下：
模型选择器不显示自定义模型、全部禁用、自动回退 `experts-auto`。
经反混淆分析客户端 bundle（`agents-window.desktop.main.js`），定位到**五层拦截**：

| 层 | 拦截点 | 后果 |
|---|---|---|
| 校验层 | `_isCustomModelExists` 初始化时序竞态（自定义模型服务未加载完） | 校验失败 → 回退官方编排 |
| 数据层 | `getAvailableModelConfigs` 不合并 custom 模型 | UI 列表无自定义模型 |
| UI 门控 | `re = !uG(...) \|\| c`（experts 模式强制） | BYOK gate closed |
| UI 列表 | `$e = c ? [] : ...`、`on = !c && ...`、`Wr` 强制 experts-auto | 无 custom 标签页、显示名伪装 |
| UI 占位 | 当前模型不在列表时插入 id 占位项 | 触发器显示原始引用 id |

另发现：Qoder **自动更新会还原 Program Files 中的 patch**（已实证），
故附带自动更新禁用脚本。

## 核心功能

- **P1-P6 客户端 patch**（`agents-window.desktop.main.js` 单文件 6 处，幂等可重跑）
  - P1：消除自定义模型校验时序竞态
  - P2：`getAvailableModelConfigs` 运行时合并 custom 模型（含 displayName，服务端刷新无法覆盖）
  - P4：解除 experts 模式 BYOK 门控
  - P5a/b/c：experts 模式启用 custom 标签页、列表、真实模型名
  - P6：触发器显示 displayName（不再显示 `custom:model_xxx` 原始 id）
- **配置写入**（`state.vscdb`）：注入 cache.experts、设置默认模型、上下文 1M、清理旧会话模型记忆
- **自动更新禁用**：`settings.json` + `app.json` 两处开关
- **完整回滚**：JS 与配置独立回滚脚本（自动备份）
- **路径/模型自动探测**：无需硬编码本机路径与模型 ID

## 技术栈

- Python 3（标准库：SQLite `state.vscdb` 读写、字符串 patch、dry-run 测试）
- Webpack 混淆 JS 逆向分析（单行 bundle、反混淆定位）
- BAT 入口（管理员运行）

## 快速开始

前置条件：

1. Qoder 桌面版（Windows），已在"自定义模型"中配置第三方 API 模型
   （`aicoding.customModels`，如 DeepSeek / OpenAI 兼容端点）
2. 完全退出 Qoder（含系统托盘）

```bat
:: 1. JS patch（管理员：写入 Program Files）
patch_qoder_experts.bat

:: 2. 配置写入（无需管理员：写用户配置库）
::    --list 查看可用模型，--model 指定 id/displayName/model，缺省取第一个
python enable_experts.py --list
python enable_experts.py --model <模型id或名称>

:: 3. 重启 Qoder -> 专家团 -> Custom 标签页 -> 自定义模型可选
```

每次运行自动备份 + 读回验证，输出 `[3/3]` / `[6/6]` 通过即成功。

## 使用方法

### 路径探测（可移植，无需配置）

**安装目录**（JS patch / 回滚）：`--js <bundle路径>` > 环境变量 `QODER_INSTALL_DIR` > 常见安装位置
（Program Files / Program Files (x86) / %LOCALAPPDATA%\Programs）

**用户数据目录**（配置写入 / 回滚 / 自动更新）：
`--user-dir <Qoder用户目录>` > 环境变量 `QODER_USER_DIR` > `%APPDATA%\Qoder`

```bat
:: 非标准安装示例
python patch_qoder_experts.py --js "D:\Apps\Qoder\resources\app\out\lingma\agents-window\agents-window.desktop.main.js"
python enable_experts.py --user-dir "D:\QoderData" --model DeepSeek-V4-Pro
```

### 模型选择

```bat
python enable_experts.py --list                          :: 列出全部自定义模型
python enable_experts.py --model <id>                    :: 按模型 id
python enable_experts.py --model "DeepSeek-V4-Pro"       :: 按显示名/model 名
python enable_experts.py                                 :: 缺省：第一个模型
```

默认注入上下文档位 `1m`（100 万 token）；模型未配置该档位时自动回退其默认档。

### 回滚

```bat
:: JS patch 回滚（管理员）
rollback_qoder_experts.bat
:: 配置回滚
rollback_experts.bat
```

### 维护

- **Qoder 更新会还原 JS patch**：更新后重跑 `patch_qoder_experts.bat`；
  如需彻底禁用自动更新：`disable_autoupdate.bat`
- **验证**：专家团模型选择器出现 Custom 标签页、自定义模型可选、
  上下文显示 1M；日志出现 `initialModel=custom:model_...`
  与 `custom model resolved, provider=...`

## 目录结构

```
experts/
├── patch_qoder_experts.py/.bat    # JS patch（P1-P6，幂等，管理员）
├── enable_experts.py/.bat         # 配置写入：注入模型/上下文/清理会话记忆
├── rollback_qoder_experts.py/.bat # JS patch 回滚
├── rollback_experts.py/.bat       # 配置回滚
├── disable_autoupdate.py/.bat     # 关闭 Qoder 自动更新
└── README.md
```

## 注意事项

- 本工具修改 Qoder 客户端文件（Program Files）与配置库（state.vscdb），仅适用于个人环境
- 所有脚本自动备份，回滚脚本可从最近备份恢复
- 不包含任何 API 密钥；模型凭据由 Qoder 客户端管理
- 若 Qoder 升级重构 experts 逻辑，patch 可能失效——需重新反混淆定位对应代码段
