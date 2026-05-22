"""
Local QA review server — browse, preview, approve, and reject rendered posts.
Opens at http://localhost:8765
"""

import json
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import config

mimetypes.add_type("video/mp4", ".mp4")

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Content Pipeline QA</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  :root{--bg:#0d0d10;--surface:#17171f;--border:#252530;--yellow:#FFE01B;--green:#3ecf8e;--red:#e05c4b;--muted:#888;--text:#eee}
  body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:32px}
  h1{font-size:22px;font-weight:700;color:var(--yellow);margin-bottom:24px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:20px}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
  .card video{width:100%;max-height:280px;object-fit:cover;display:block}
  .card-body{padding:16px;display:flex;flex-direction:column;gap:10px}
  .job-id{font-size:12px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.5px}
  .caption{font-size:13px;line-height:1.5}
  .hashtags{font-size:12px;color:var(--muted)}
  .badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:600}
  .badge-pending{background:#2a2510;color:var(--yellow)}
  .badge-approved{background:#0f2a1f;color:var(--green)}
  .badge-rejected{background:#2a100f;color:var(--red)}
  .badge-scheduled{background:#1a1a35;color:#a78bfa}
  .actions{display:flex;gap:8px;flex-wrap:wrap}
  .btn{padding:8px 16px;border:none;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer}
  .btn-green{background:var(--green);color:#000}
  .btn-red{background:var(--red);color:#fff}
  .reject-form{display:none;flex-direction:column;gap:8px}
  .reject-form.open{display:flex}
  textarea{width:100%;background:#222;border:1px solid var(--border);color:var(--text);padding:8px;border-radius:6px;font-size:13px;resize:vertical;min-height:64px}
  .btn-sm{padding:6px 12px;font-size:12px}
  .empty{color:var(--muted);font-size:14px}
  .notes{font-size:12px;color:var(--muted);font-style:italic}
</style>
</head>
<body>
<h1>Content Pipeline QA</h1>
<div class="grid" id="grid">CONTENT</div>
<script>
function toggleReject(jobId){
  document.getElementById('rf-'+jobId).classList.toggle('open');
}
async function approve(jobId){
  await fetch('/action',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({job_id:jobId,action:'approve'})});
  location.reload();
}
async function reject(jobId){
  const reason=document.getElementById('rr-'+jobId).value.trim();
  if(!reason){alert('Enter a reason');return;}
  await fetch('/action',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({job_id:jobId,action:'reject',reason})});
  location.reload();
}
</script>
</body>
</html>"""

CARD_TEMPLATE = """
<div class="card">
  {video_tag}
  <div class="card-body">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span class="job-id">{job_id}</span>
      <span class="badge badge-{status}">{status}</span>
    </div>
    <div class="caption">{caption}</div>
    <div class="hashtags">{hashtags}</div>
    {notes_tag}
    {rejection_tag}
    <div class="actions">
      <button class="btn btn-green" onclick="approve('{job_id}')">✓ Approve</button>
      <button class="btn btn-red" onclick="toggleReject('{job_id}')">✗ Reject</button>
    </div>
    <div class="reject-form" id="rf-{job_id}">
      <textarea id="rr-{job_id}" placeholder="Rejection reason..."></textarea>
      <button class="btn btn-red btn-sm" onclick="reject('{job_id}')">Submit</button>
    </div>
  </div>
</div>
"""


def _load_jobs() -> list[dict]:
    jobs = []
    for meta_file in sorted(config.OUTPUT_DIR.rglob("post_meta.json")):
        try:
            meta = json.loads(meta_file.read_text())
            meta["_meta_path"] = str(meta_file)
            jobs.append(meta)
        except Exception:
            pass
    return jobs


def _render_page() -> str:
    jobs = _load_jobs()
    if not jobs:
        cards = '<p class="empty">No processed jobs yet. Drop clips into input/ and run the pipeline.</p>'
    else:
        cards = ""
        for j in jobs:
            vp = j.get("video_path", "")
            job_id = j.get("job_id", "unknown")
            if vp and Path(vp).exists():
                video_tag = f'<video controls preload="metadata" src="/video/{urllib.parse.quote(vp)}"></video>'
            else:
                video_tag = '<div style="height:120px;background:#111;display:flex;align-items:center;justify-content:center;color:var(--muted)">Video not found</div>'

            hashtags_str = " ".join(j.get("hashtags", []))
            notes = j.get("notes", "")
            notes_tag = f'<div class="notes">{notes}</div>' if notes else ""
            rej = j.get("rejection_reason", "")
            rejection_tag = f'<div style="color:var(--red);font-size:12px">✗ {rej}</div>' if rej else ""

            cards += CARD_TEMPLATE.format(
                video_tag=video_tag,
                job_id=job_id,
                status=j.get("status", "pending"),
                caption=j.get("caption", ""),
                hashtags=hashtags_str,
                notes_tag=notes_tag,
                rejection_tag=rejection_tag,
            )
    return HTML_PAGE.replace("CONTENT", cards)


class QAHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress default access log
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "":
            body = _render_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path.startswith("/video/"):
            video_path = urllib.parse.unquote(self.path[7:])
            p = Path(video_path)
            if p.exists():
                data = p.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", len(data))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/action":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            job_id = body.get("job_id")
            action = body.get("action")
            reason = body.get("reason", "")

            # Find meta file
            meta_file = config.OUTPUT_DIR / job_id / "post_meta.json"
            if not meta_file.exists():
                # fallback: search
                matches = list(config.OUTPUT_DIR.rglob(f"{job_id}/post_meta.json"))
                if matches:
                    meta_file = matches[0]

            if meta_file.exists():
                meta = json.loads(meta_file.read_text())
                meta["status"] = action + "d" if action in ("approve", "reject") else action
                if action == "reject":
                    meta["rejection_reason"] = reason
                meta_file.write_text(json.dumps(meta, indent=2))

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')


def run():
    server = HTTPServer((config.QA_HOST, config.QA_PORT), QAHandler)
    print(f"QA server running at http://{config.QA_HOST}:{config.QA_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nQA server stopped.")


if __name__ == "__main__":
    run()
