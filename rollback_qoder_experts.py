# -*- coding: utf-8 -*-
"""
Qoder 专家团 Patch 回滚脚本：从最近备份恢复 agents-window.desktop.main.js
用法：退出 Qoder 后，右键本 bat -> 以管理员身份运行
路径探测（可移植）：--js <bundle路径> 或环境变量 QODER_INSTALL_DIR 优先，
      否则自动探测常见安装位置。
"""
import glob
import os
import sys
import shutil

def detect_js():
    if "--js" in sys.argv:
        return sys.argv[sys.argv.index("--js") + 1]
    env = os.environ.get("QODER_INSTALL_DIR")
    rel = os.path.join("resources", "app", "out", "lingma", "agents-window", "agents-window.desktop.main.js")
    if env:
        return os.path.join(env, rel)
    for root in (r"C:\Program Files\Qoder", r"C:\Program Files (x86)\Qoder",
                 os.path.expandvars(r"%LOCALAPPDATA%\Programs\Qoder")):
        p = os.path.join(root, rel)
        if os.path.exists(p):
            return p
    return os.path.join(r"C:\Program Files\Qoder", rel)

JS = detect_js()

tasklist = os.popen('tasklist /FO CSV /NH 2>nul').read().lower()
if "qoder" in tasklist:
    print("[!] Qoder 仍在运行，请先完全退出再回滚。")
    sys.exit(1)

baks = sorted(glob.glob(JS + ".bak_experts_*"))
if not baks:
    print("[!] 未找到 patch 备份，无法回滚。")
    sys.exit(2)
latest = baks[-1]
shutil.copy2(latest, JS)
print("[ok] 已从", os.path.basename(latest), "恢复。可正常启动 Qoder。")
