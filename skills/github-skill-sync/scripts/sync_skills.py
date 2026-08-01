#!/usr/bin/env python3
import argparse, datetime, os, shutil, subprocess, sys, tempfile
from pathlib import Path

EXCLUDES = {".git", "__pycache__", ".DS_Store"}
SECRET_NAMES = {".env", "credentials", "credentials.json", "secrets", "secrets.json", "hosts.yml"}
SECRET_SUFFIXES = {".pyc", ".pyo", ".log", ".pem", ".key", ".p12"}

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
        conflicts = [p.name for p in incoming if (dest / p.name).exists()]
        new = [p for p in incoming if not (dest / p.name).exists()]
        # 新技能始终直接安装；仅当存在同名覆盖冲突且未确认时才拦截
        for p in new: copy_tree(p, dest / p.name)
        if new: print(f"已安装 {len(new)} 个新技能：" + ", ".join(p.name for p in new))
        if conflicts and not args.force:
            if new: print("以下同名技能未更新：" + ", ".join(conflicts) + "。确认覆盖时加 --force。")
            else: raise SystemExit("以下技能已存在：" + ", ".join(conflicts) + "。确认覆盖时加 --force。")
            return
        backup = None
        if conflicts:
            backup = dest.parent / ("skills-backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")); backup.mkdir()
            for name in conflicts: shutil.copytree(dest / name, backup / name)
            for p in incoming:
                if p.name in conflicts: copy_tree(p, dest / p.name)
            print(f"已覆盖更新 {len(conflicts)} 个技能：" + ", ".join(conflicts))
        if not new and not conflicts: print("本机已是最新，无新技能。")
        if backup: print(f"被覆盖技能已备份到：{backup}")

def main():
    ap = argparse.ArgumentParser(description="通过 GitHub 双向同步 OpenMinis Skills")
    ap.add_argument("action", choices=["push", "pull"]); ap.add_argument("--repo", default="SoftwarePianist/MyMinisSkill", type=repo_slug)
    ap.add_argument("--skills-dir", default="/var/minis/skills"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--delete-remote", action="store_true"); ap.add_argument("--message")
    args = ap.parse_args(); require_tools(); push(args) if args.action == "push" else pull(args)

if __name__ == "__main__": main()
