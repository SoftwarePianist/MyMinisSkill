---
name: github-skill-sync
description: 通过用户个人 GitHub 仓库备份、上传、下载、恢复和双向同步 OpenMinis 的全部 Skills。用户说“连接 GitHub 同步技能”“备份本机 skills”“把 skills 上传到仓库”“换手机恢复技能”“从相同 GitHub 账号同步所有技能到新手机”时使用。
version: 1.0.0
---
# GitHub Skill Sync

通过 GitHub 仓库的 `skills/` 目录同步 `/var/minis/skills/`。

## 安全规则

- 使用 `gh auth status` 判断登录状态；绝不读取、打印或索要 Token。
- 如果尚未登录，安装 `github-cli` 后让用户在交互终端运行 `gh auth login --hostname github.com --git-protocol https --web`。
- 推送前检查仓库可见性。公开仓库也不得上传 `.env`、密钥、凭据、Token、日志、缓存或证书。
- 默认不删除仓库中仅远端存在的技能；只有用户明确要求镜像删除时才使用 `--delete-remote`。
- 拉取发现同名技能时，不直接覆盖。说明冲突并取得用户确认；确认后使用 `--force`。脚本会先备份旧版本。
- 跨手机同步的是 Skill 文件，不包括 GitHub 登录状态、环境变量、API Key、系统权限和已安装依赖；新手机需另行配置这些项目。

## 上传或备份

1. 确认 `git`、`gh` 可用且 GitHub 已登录。
2. 默认使用固定仓库 `SoftwarePianist/MyMinisSkill`。
3. 执行：

```sh
python3 /var/minis/skills/github-skill-sync/scripts/sync_skills.py push
```

4. 核验远端提交和默认分支，报告上传数量、提交和仓库链接。

如需让远端严格镜像本机、删除远端多余技能，仅在用户明确同意后添加 `--delete-remote`。

## 新手机恢复

1. 在新手机安装并登录 GitHub CLI，登录同一个有仓库访问权的账号。
2. 先预判本机同名 Skill 冲突。首次拉取不加 `--force`：

```sh
python3 /var/minis/skills/github-skill-sync/scripts/sync_skills.py pull
```

3. 如果报告冲突，向用户列出同名技能。用户确认覆盖后执行：

```sh
python3 /var/minis/skills/github-skill-sync/scripts/sync_skills.py pull --force
```

4. 覆盖前的版本会备份到 `/var/minis/skills-backup-时间戳/`。
5. 核验各技能存在 `SKILL.md`。提示用户重开会话，使新安装技能被重新发现。

## 同步策略

- **上传（Push）**：当用户说“备份技能”“上传技能”“把我本机的技能推送到云端”时，执行 `push`。
- **下载/拉取（Pull）**：当用户说“下载技能”“从云端拉取”“恢复技能”“拉取更新”时，执行 `pull`。
- **注意**：如果用户只说“同步”，你需要反问明确方向，不要自行盲目猜测。
- 不自动合并同一个 Skill 内的差异；以用户选择的上传端或下载端版本为准。
- 对公共仓库，在每次推送前再次做敏感文件检查。
