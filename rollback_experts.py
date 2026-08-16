# -*- coding: utf-8 -*-
"""
Qoder 专家团配置回滚脚本
用法：1) 完全退出 Qoder
      2) 双击运行 rollback_experts.bat（或 python rollback_experts.py）
从最近一次 enable_experts 备份恢复 state.vscdb
路径探测（可移植）：--user-dir <Qoder用户目录> 或环境变量 QODER_USER_DIR 优先，
      否则自动使用 %APPDATA%/Qoder。
"""
import shutil
import glob
import os
import sys

def detect_db():
    if "--user-dir" in sys.argv:
        return os.path.join(sys.argv[sys.argv.index("--user-dir") + 1], "User", "globalStorage", "state.vscdb")
    env = os.environ.get("QODER_USER_DIR")
    if env:
        return os.path.join(env, "User", "globalStorage", "state.vscdb")
    return os.path.join(os.path.expandvars(r"%APPDATA%\Qoder"), "User", "globalStorage", "state.vscdb")

DB = detect_db()

# 0) 进程检查
tasklist = os.popen('tasklist /FO CSV /NH 2>nul').read().lower()
if "qoder" in tasklist or "code" in tasklist:
    print("[!] 检测到 Qoder 仍在运行，请先完全退出再回滚。")
    sys.exit(1)

# 1) 找最新备份
baks = sorted(glob.glob(DB + ".bak_experts_*"))
if not baks:
    print("[!] 未找到 enable_experts 备份，无法回滚。")
    sys.exit(2)
latest = baks[-1]
print("[1/2] 使用备份:", os.path.basename(latest))

# 2) 恢复
shutil.copy2(latest, DB)
print("[2/2] 已恢复。重新启动 Qoder 即可回到修改前状态。")
