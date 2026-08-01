#!/usr/bin/env python3
import argparse, datetime, os, shutil, subprocess, sys, tempfile
from pathlib import Path

EXCLUDES = {".git", "__pycache__", ".DS_Store"}
SECRET_NAMES = {".env", "credentials", "credentials.json", "secrets", "secrets.json", "hosts.yml"}
SECRET_SUFFIXES = {".pyc", ".pyo", ".log", ".pem", ".key", ".p12"}

def version_tuple(v):
    """将版本字符串转为可比较的元组，如 '1.2.0' -> (1,2,0)"""
    try: return tuple(int(x) for x in v.split("."))
    except: return (0,)

def get_version(skill_path):
    """从 SKILL.md 提取 version 字段，返回字符串或 None"""
    f = skill_path / "SKILL.md"
    if not f.exists(): return None
    for line in f.read_text(errors="ignore").splitlines()[:20]:
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    return None

def run(cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and p.returncode:
        print(p.stdout, file=sys.stderr); raise SystemExit(p.returncode)
    return p.stdout.strip()

def excluded(path):
    return any(x in EXCLUDES for x in path.parts) or path.name in SECRET_NAMES or path.suffix.lower() in SECRET_SUFFIXES or path.name.startswith(".env.")

def copy_tree(src, dst):
    if dst.exists(): shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if excluded(rel): continue
        out = dst / rel
        if p.is_dir(): out.mkdir(parents=True, exist_ok=True)
        elif p.is_file(): out.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, out)

def require_tools():
    for tool in ("git", "gh"):
        if not shutil.which(tool): raise SystemExit(f"缺少 {tool}，请先安装。")
    run(["gh", "auth", "status"])

def repo_slug(value):
    value = value.strip().rstrip("/")
    if value.endswith(".git"): value = value[:-4]
    if "github.com/" in value: value = value.split("github.com/", 1)[1]
    if value.count("/") != 1: raise SystemExit("仓库应为 owner/repo 或 GitHub 仓库 URL。")
    return value

def clone(repo, target):
    run(["gh", "repo", "clone", repo, str(target)])

def push(args):
    source = Path(args.skills_dir).expanduser().resolve()
    if not source.is_dir(): raise SystemExit(f"技能目录不存在：{source}")
    with tempfile.TemporaryDirectory(prefix="minis-skill-sync-") as td:
        work = Path(td) / "repo"; clone(args.repo, work)
        target = work / "skills"; target.mkdir(exist_ok=True)
        local_names = {p.name for p in source.iterdir() if p.is_dir() and not excluded(Path(p.name))}
        if args.delete_remote:
            for p in target.iterdir():
                if p.is_dir() and p.name not in local_names: shutil.rmtree(p)
        for name in sorted(local_names): copy_tree(source / name, target / name)
        run(["git", "add", "-A"], cwd=work)
        if not run(["git", "status", "--porcelain"], cwd=work): print("没有需要上传的变更。"); return
        run(["git", "config", "user.name", run(["gh", "api", "user", "--jq", ".login"])], cwd=work)
        run(["git", "config", "user.email", run(["gh", "api", "user", "--jq", ".login"]) + "@users.noreply.github.com"], cwd=work)
        msg = args.message or "Sync OpenMinis skills " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        run(["git", "commit", "-m", msg], cwd=work); print(run(["git", "push"], cwd=work)); print(f"已上传 {len(local_names)} 个技能到 {args.repo}。")

def pull(args):
    dest = Path(args.skills_dir).expanduser().resolve(); dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="minis-skill-sync-") as td:
        work = Path(td) / "repo"; clone(args.repo, work); source = work / "skills"
        if not source.is_dir(): raise SystemExit("仓库中没有 skills/ 目录。")
        incoming = [p for p in source.iterdir() if p.is_dir()]
        new = [p for p in incoming if not (dest / p.name).exists()]
        # 同名技能：检查版本差异，区分"升级"和"冲突"
        upgrades = []  # (路径, 旧版本, 新版本)
        conflicts = []  # 同名同版本或无法判断版本
        for p in incoming:
            if not (dest / p.name).exists(): continue
            local_ver = get_version(dest / p.name)
            remote_ver = get_version(p)
            if local_ver and remote_ver and version_tuple(remote_ver) > version_tuple(local_ver):
                upgrades.append((p, local_ver, remote_ver))
            else:
                conflicts.append(p.name)
        # 新技能始终直接安装
        for p in new: copy_tree(p, dest / p.name)
        if new: print(f"已安装 {len(new)} 个新技能：" + ", ".join(p.name for p in new))
        # 版本升级：--upgrade 或 --force 时执行
        to_upgrade = []
        if upgrades and (args.upgrade or args.force):
            backup = dest.parent / ("skills-backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")); backup.mkdir()
            for p, old_ver, new_ver in upgrades:
                shutil.copytree(dest / p.name, backup / p.name)
                copy_tree(p, dest / p.name)
                to_upgrade.append(f"{p.name} ({old_ver}→{new_ver})")
            print(f"已升级 {len(upgrades)} 个技能：" + ", ".join(to_upgrade))
            print(f"旧版本已备份到：{backup}")
        elif upgrades:
            print("以下技能有新版本：" + ", ".join(f"{p.name} ({old}→{new})" for p, old, new in upgrades) + "。加 --upgrade 升级，或加 --force 强制覆盖所有同名技能。")
        # 纯冲突（同名同版本）：仅 --force 覆盖
        if conflicts and args.force:
            backup = dest.parent / ("skills-backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")); backup.mkdir(exist_ok=True)
            for name in conflicts: shutil.copytree(dest / name, backup / name)
            for p in incoming:
                if p.name in conflicts: copy_tree(p, dest / p.name)
            print(f"已强制覆盖 {len(conflicts)} 个技能：" + ", ".join(conflicts))
        elif conflicts and not args.force:
            print("以下技能已存在且版本相同：" + ", ".join(conflicts) + "。加 --force 强制覆盖。")
        if not new and not upgrades and not conflicts: print("本机已是最新，无新技能。")

def main():
    ap = argparse.ArgumentParser(description="通过 GitHub 双向同步 OpenMinis Skills")
    ap.add_argument("action", choices=["push", "pull"]); ap.add_argument("--repo", default="SoftwarePianist/MyMinisSkill", type=repo_slug)
    ap.add_argument("--skills-dir", default="/var/minis/skills"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--upgrade", action="store_true", help="仅升级版本号不同的同名技能，不强制覆盖所有")
    ap.add_argument("--delete-remote", action="store_true"); ap.add_argument("--message")
    args = ap.parse_args(); require_tools(); push(args) if args.action == "push" else pull(args)

if __name__ == "__main__": main()
