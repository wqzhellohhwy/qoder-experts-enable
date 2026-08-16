# -*- coding: utf-8 -*-
"""
Qoder 专家团自定义模型 Patch 脚本 v2（两处 patch，幂等）
P1: _isCustomModelExists -> 消除初始化时序竞态（custom 模型校验恒通过）
P2: getAvailableModelConfigs -> EXPERTS 通道返回列表时合并 custom 模型条目
    （运行时计算合并，服务端缓存刷新无法覆盖；UI 模型列表即显示 DeepSeek 模型）
用法：1) 完全退出 Qoder
      2) 右键本 bat -> 以管理员身份运行
      3) 重启 Qoder -> 打开专家团 -> 模型选择器应出现自定义模型
回滚：rollback_qoder_experts.bat（管理员运行）

路径探测（可移植）：
  --js <bundle路径> 或环境变量 QODER_INSTALL_DIR（安装目录）优先，
  否则自动探测 Program Files / Program Files (x86) / %LOCALAPPDATA%/Programs。
"""
import os
import sys
import shutil
import datetime

def detect_js():
    """探测 agents-window.desktop.main.js 路径：--js > QODER_INSTALL_DIR > 常见安装位置"""
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

PATCHES = [
    # P1: 时序竞态
    (
        "_isCustomModelExists(e){const r=uie(e);return r?this.customModelService.getModels().records.some(i=>i.id===r&&i.visible):!1}",
        "_isCustomModelExists(e){return!!uie(e)}",
    ),
    # P4: 解除 experts 模式 BYOK gate（re 恒 false）
    (
        "re=(0,yl.useMemo)(()=>!uG(Q.userPlan?.user_type,Q.userInfo,Q.userPlan?.is_personal_version)||c,[Q.userPlan,Q.userInfo,c])",
        "re=(0,yl.useMemo)(()=>!1,[Q.userPlan,Q.userInfo,c])",
    ),
    # P5a: experts 模式 custom 列表不再置空
    (
        "$e=(0,yl.useMemo)(()=>c?[]:de.filter(nxp),[c,de])",
        "$e=(0,yl.useMemo)(()=>de.filter(nxp),[c,de])",
    ),
    # P5b: experts 模式显示 custom 标签页
    (
        "on=!c&&(!re||qr)",
        "on=!re||qr",
    ),
    # P5c: experts 模式当前模型显示真实名称（不再强制 experts-auto）
    (
        "Wr=(0,yl.useMemo)(()=>$t?\"experts-auto\":ve,[ve,$t])",
        "Wr=(0,yl.useMemo)(()=>ve,[ve,$t])",
    ),
    # P6: custom 当前模型不再产生 id 占位项（触发器显示走 displayName）
    (
        "qt=!c&&$f(Ht);!v.some(Nr=>Nr.name===Ht&&!Nr.enabled)&&!bn&&!Ye&&!qt&&At.unshift({label:p(pin(Ht,\"label\",l),Ht),value:Ht,disabled:!0})",
        "qt=$f(Ht);!v.some(Nr=>Nr.name===Ht&&!Nr.enabled)&&!bn&&!Ye&&!qt&&At.unshift({label:p(pin(Ht,\"label\",l),Ht),value:Ht,disabled:!0})",
    ),
]

# P2 升级链：原版 -> P2a(无 displayName) -> P2b(带 displayName)
P2_OLD_ORIG = "async getAvailableModelConfigs(e){const r=e||pn.ASSISTANT,n=this._availableModelConfigs.get(r)||[];return!this._initialized&&n.length===0&&await this.refreshModelConfigs(r),this._availableModelConfigs.get(r)||[]}"
P2_OLD_A = "async getAvailableModelConfigs(e){const r=e||pn.ASSISTANT,n=this._availableModelConfigs.get(r)||[];return!this._initialized&&n.length===0&&await this.refreshModelConfigs(r),r===pn.EXPERTS?(this._availableModelConfigs.get(r)||[]).concat(this.customModelService.getModels().records.filter(i=>i.visible).map(i=>this._findCustomModelConfig(\"custom:\"+i.id)).filter(Boolean)):this._availableModelConfigs.get(r)||[]}"
P2_NEW_B = "async getAvailableModelConfigs(e){const r=e||pn.ASSISTANT,n=this._availableModelConfigs.get(r)||[];return!this._initialized&&n.length===0&&await this.refreshModelConfigs(r),r===pn.EXPERTS?(this._availableModelConfigs.get(r)||[]).concat(this.customModelService.getModels().records.filter(i=>i.visible).map(i=>{const c=this._findCustomModelConfig(\"custom:\"+i.id);return c?Object.assign(c,{displayName:i.displayName||i.alias||i.model}):null}).filter(Boolean)):this._availableModelConfigs.get(r)||[]}"

TEST_MODE = "--test" in sys.argv
if TEST_MODE:
    JS = sys.argv[sys.argv.index("--test") + 1]


def main():
    if not TEST_MODE:
        tasklist = os.popen('tasklist /FO CSV /NH 2>nul').read().lower()
        if "qoder" in tasklist:
            print("[!] Qoder 仍在运行，请先完全退出（含托盘）再执行。")
            sys.exit(1)

    if not os.path.exists(JS):
        print("[!] 找不到目标文件（版本可能已更新）：", JS)
        sys.exit(2)

    with open(JS, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    todo = []
    for old, new in PATCHES:
        if new in content:
            print("[*] 已 patch 跳过:", old[:50], "...")
        elif old in content:
            todo.append((old, new))
        else:
            print("[!] 版本不匹配，未找到目标代码段:", old[:60], "...")
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_js_version.txt"), "w", encoding="utf-8") as f:
                f.write("size=%d\n" % len(content))
            sys.exit(3)

    # P2 升级链处理
    if P2_NEW_B in content:
        print("[*] P2 已是最新版（带 displayName），跳过")
    elif P2_OLD_A in content:
        todo.append((P2_OLD_A, P2_NEW_B))
        print("[*] P2 升级: 旧合并 -> 带 displayName 版本")
    elif P2_OLD_ORIG in content:
        todo.append((P2_OLD_ORIG, P2_NEW_B))
        print("[*] P2 写入: 原版 -> 带 displayName 合并版本")
    else:
        print("[!] 未找到 getAvailableModelConfigs 任何已知版本，中止。")
        sys.exit(3)

    if not todo:
        print("[*] 全部 patch 已生效，无需操作。")
        return

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = JS + ".bak_experts_v2_" + ts
    shutil.copy2(JS, bak)
    print("[1/3] 已备份:", os.path.basename(bak))

    for old, new in todo:
        content = content.replace(old, new, 1)
    with open(JS, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print("[2/3] 已写入 %d 处 patch" % len(todo))

    with open(JS, "r", encoding="utf-8", errors="replace") as f:
        check = f.read()
    ok = all(new in check for _, new in PATCHES) and P2_NEW_B in check
    if ok:
        print("[3/3] 读回验证通过。重启 Qoder 后打开专家团，模型选择器应出现 DeepSeek 模型。")
        print("      失败可回滚：rollback_qoder_experts.bat")
    else:
        print("[3/3] 读回验证失败！请勿启动 Qoder，立即运行 rollback_qoder_experts.bat 恢复。")


if __name__ == "__main__":
    main()
