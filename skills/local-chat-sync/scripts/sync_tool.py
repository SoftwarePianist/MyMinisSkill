import sys
import os
import json
import subprocess
import urllib.request
import datetime

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except:
        return None

def export_chats(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    list_data = run_cmd("minis-sessions-cli list --limit 20 --compact")
    if not list_data or not list_data.get("ok"):
        print("Failed to list sessions.")
        return
    
    sessions = list_data.get("data", {}).get("sessions", [])
    export_data = []
    
    for sess in sessions:
        sess_id = sess.get("session_id")
        title = sess.get("title", "未命名会话")
        print(f"Exporting: {title} ({sess_id})")
        msg_data = run_cmd(f"minis-sessions-cli messages --id {sess_id} --full --compact")
        if msg_data and msg_data.get("ok"):
            sess["messages"] = msg_data.get("data", {}).get("messages", [])
        else:
            sess["messages"] = []
        export_data.append(sess)
        
    out_file = os.path.join(output_dir, "chats_export.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    print(f"Export complete: {out_file}")

def import_chats(url, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    print(f"Downloading from {url} ...")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Download failed: {e}")
        return
        
    for sess in data:
        title = sess.get("title", "未命名会话")
        # sanitize title for filename
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-")
        started_at = sess.get("started_at", "").replace(":", "-").replace(" ", "_")
        filename = f"{started_at}_{safe_title}.md"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(f"**开始时间:** {sess.get('started_at')}\n")
            f.write(f"**消息数:** {sess.get('message_count')}\n\n")
            f.write("---\n\n")
            
            for msg in sess.get("messages", []):
                role = "👤 **User**" if msg.get("role") == "user" else "🤖 **Minis**"
                time = msg.get("created_at")
                text = msg.get("text", "")
                f.write(f"{role} _{time}_\n\n{text}\n\n---\n\n")
        print(f"Generated: {filepath}")
        
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 sync_tool.py [export|import] [args]")
        sys.exit(1)
        
    mode = sys.argv[1]
    if mode == "export":
        export_chats(sys.argv[2])
    elif mode == "import":
        import_chats(sys.argv[2], sys.argv[3])
    else:
        print("Unknown mode.")
