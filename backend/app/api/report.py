"""诊疗报告生成 接口

从会话的最近一次辨证结果渲染 A4 版式 HTML，并优先用「无头 Chrome / WeasyPrint」
打成矢量 PDF（与页面预览同引擎，版式一致）；二者皆不可用时降级返回 HTML
（页面内置「下载 PDF」按钮走浏览器打印另存）。报告经 /reports 静态目录提供下载。
"""

from __future__ import annotations

import asyncio
import html as _html
import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.models.schemas import ReportRequest, ReportResponse, DISCLAIMER
from app.services.session import session_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/report", tags=["报告"])

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

ROLE_LABELS = {"doctor": "医生", "patient": "患者", "researcher": "研究者"}


def _find_chrome() -> Optional[str]:
    """定位可用于 --print-to-pdf 的 Chrome/Chromium/Edge 可执行文件。"""
    env = os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    mac_apps = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for c in mac_apps:
        if Path(c).exists():
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "microsoft-edge"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _html_to_pdf(html_path: Path, pdf_path: Path) -> bool:
    """把 A4 HTML 打成矢量 PDF。优先 WeasyPrint，其次无头 Chrome；均失败返回 False。"""
    html_path = html_path.resolve()
    pdf_path = pdf_path.resolve()
    # ① WeasyPrint（纯 Python，但依赖系统库，常缺）
    try:
        from weasyprint import HTML  # type: ignore

        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            return True
    except Exception as e:
        logger.info("WeasyPrint 不可用：%s", e)

    # ② 无头 Chrome --print-to-pdf（与浏览器预览同引擎，版式最稳）
    chrome = _find_chrome()
    if chrome:
        try:
            # Chrome 无头打印常写完 PDF 却不自退（本机即如此）。故不等它退出：
            # 启动后轮询输出文件，写好且大小稳定即主动结束进程，延迟≈写盘耗时。
            if pdf_path.exists():
                pdf_path.unlink()
            with tempfile.TemporaryDirectory() as udir:
                proc = subprocess.Popen(
                    [
                        chrome, "--headless", "--disable-gpu", "--no-sandbox",
                        f"--user-data-dir={udir}",
                        "--no-pdf-header-footer",
                        "--virtual-time-budget=6000",
                        f"--print-to-pdf={pdf_path}",
                        html_path.as_uri(),
                    ],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                deadline, last_size, stable = time.time() + 20, -1, 0
                try:
                    while time.time() < deadline:
                        if proc.poll() is not None:
                            break  # 自己退出了
                        if pdf_path.exists():
                            sz = pdf_path.stat().st_size
                            if sz > 0 and sz == last_size:
                                stable += 1
                                if stable >= 2:  # 连续两次大小不变 → 写盘完成
                                    break
                            else:
                                stable = 0
                            last_size = sz
                        time.sleep(0.4)
                finally:
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except Exception:
                            proc.kill()
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                return True
        except Exception as e:
            logger.info("Chrome 导出 PDF 失败：%s", e)
    else:
        logger.info("未找到 Chrome，PDF 降级为 HTML")
    return False


def _esc(v) -> str:
    return _html.escape(str(v)) if v is not None else ""


def _render_html(result: dict, sources: list[dict], report_id: str, role: str, date_str: str) -> str:
    s2 = result.get("step2_location_nature", {}) or {}
    s3 = result.get("step3_syndrome", {}) or {}
    s6 = result.get("step6_formula", {}) or {}
    s7 = result.get("step7_care", {}) or {}

    role_label = ROLE_LABELS.get(role, "医生")

    def _tags(items) -> str:
        items = [x for x in (items or []) if x]
        return "".join(f"<span>{_esc(x)}</span>" for x in items) or '<span class="muted">—</span>'

    conf = s3.get("confidence", "")
    try:
        cf = float(conf)
        conf_pct = f"{round(cf * 100) if cf <= 1 else round(cf)}%"
    except (TypeError, ValueError):
        conf_pct = _esc(conf) or "—"

    herb_rows = "".join(
        f"<tr><td class='hb-name'>{_esc(h.get('herb',''))}</td>"
        f"<td class='hb-dose'>{_esc(h.get('dosage','')) or '—'}</td>"
        f"<td><span class='hb-role'>{_esc(h.get('role','')) or '—'}</span></td>"
        f"<td class='hb-reason'>{_esc(h.get('reason','')) or '—'}</td></tr>"
        for h in (s6.get("composition") or [])
    ) or "<tr><td colspan='4' class='muted'>—</td></tr>"

    care_defs = [
        ("忌", "用药禁忌", s7.get("contraindication")),
        ("食", "食疗建议", s7.get("diet")),
        ("居", "起居调护", s7.get("lifestyle")),
        ("功", "简易功法", s7.get("exercise")),
    ]
    care_items = "".join(
        f"<div class='care-item'><div class='care-head'><span class='care-seal'>{seal}</span>{label}</div>"
        f"<p>{_esc(text)}</p></div>"
        for seal, label, text in care_defs if text
    ) or "<p class='muted'>—</p>"

    evidence = "".join(
        f"<li><span class='ev-text'>{_esc(ev.get('text',''))}</span>"
        f"<em class='ev-src'>{_esc(ev.get('source',''))}</em></li>"
        for ev in (result.get("step4_classic_evidence") or [])
    ) or "<li class='muted'>本次辨证未匹配到知识库引证条目。</li>"

    formula_meta = ""
    if s6.get("name") or s6.get("modification"):
        formula_meta = (
            f"<p class='formula-meta'>方名：<b>{_esc(s6.get('name','')) or '—'}</b>"
            f"　随症加减：{_esc(s6.get('modification','')) or '—'}</p>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>李时珍智能医师·诊疗报告 {report_id}</title>
<style>
  :root {{
    --navy:#1F3A5F; --gold:#C8A45C; --gold-deep:#9A6A1F; --cinnabar:#9A2D2D;
    --ink:#1F1B16; --ink2:#5C5345; --ink3:#8A8170; --line:#E5DCC9; --paper:#FBF7EE;
  }}
  * {{ box-sizing:border-box; }}
  html, body {{ margin:0; padding:0; }}
  body {{
    background:#5b5f66;
    font-family:"Songti SC","STSong","Noto Serif SC","Source Han Serif SC",serif;
    color:var(--ink); -webkit-print-color-adjust:exact; print-color-adjust:exact;
  }}

  /* 顶部工具条（打印/PDF 中隐藏） */
  .toolbar {{
    position:sticky; top:0; z-index:20;
    display:flex; align-items:center; justify-content:center; gap:12px;
    padding:12px 16px; background:rgba(22,41,63,0.97);
    box-shadow:0 2px 12px rgba(0,0,0,0.35);
  }}
  .toolbar button {{
    font-family:inherit; font-size:15px; font-weight:600; cursor:pointer;
    padding:9px 22px; border-radius:22px; border:1px solid transparent; transition:all .18s;
  }}
  .btn-pdf {{ background:var(--cinnabar); color:#FBF7EE; }}
  .btn-pdf:hover {{ background:#b5413f; }}
  .btn-print {{ background:transparent; color:#EAF0F6; border-color:rgba(234,240,246,.5); }}
  .btn-print:hover {{ border-color:var(--gold); color:var(--gold); }}
  .toolbar .hint {{ color:#aeb8c4; font-size:13px; margin-left:6px; }}

  /* A4 纸张 */
  .a4-wrap {{ display:flex; justify-content:center; padding:26px 14px 40px; }}
  .a4-sheet {{
    width:210mm; min-height:297mm; background:#fff;
    padding:18mm 18mm 16mm; box-shadow:0 8px 36px rgba(0,0,0,0.4);
  }}

  /* 抬头 */
  .r-header {{ display:flex; align-items:center; gap:16px; border-bottom:3px double var(--gold); padding-bottom:16px; }}
  .r-seal {{
    width:58px; height:58px; border-radius:10px; flex-shrink:0;
    background:var(--cinnabar); color:#FBF7EE; display:flex; align-items:center; justify-content:center;
    font-size:34px; font-weight:700; box-shadow:inset 0 0 0 2px rgba(251,247,238,.35);
  }}
  .r-title {{ font-size:27px; font-weight:700; color:var(--navy); letter-spacing:3px; margin:0; }}
  .r-sub {{ font-size:14px; color:var(--ink2); margin-top:5px; letter-spacing:2px; }}
  .r-meta {{ display:flex; flex-wrap:wrap; gap:10px 26px; margin:14px 0 4px; font-size:13.5px; color:var(--ink2); }}
  .r-meta b {{ color:var(--navy); font-weight:600; }}

  /* 区块 */
  section.block {{ margin-top:22px; page-break-inside:avoid; }}
  .block h2 {{
    font-size:18px; color:var(--navy); margin:0 0 11px; padding-left:12px;
    border-left:5px solid var(--gold); line-height:1.5; letter-spacing:1px;
  }}
  .block p, .block li {{ font-size:15px; line-height:1.9; color:var(--ink); margin:0 0 6px; }}
  .muted {{ color:var(--ink3); }}

  .kv {{ font-size:15.5px; line-height:2.1; }}
  .kv .lead {{ color:var(--cinnabar); font-weight:700; font-size:19px; letter-spacing:1px; }}
  .kv .conf {{ display:inline-block; margin-left:8px; padding:1px 12px; border-radius:12px;
    background:rgba(95,179,161,.16); color:#2f7d5b; font-size:13px; font-variant-numeric:tabular-nums; }}
  .nature {{ margin-top:8px; }}
  .nature .nlabel {{ display:inline-block; width:64px; color:var(--ink2); font-size:14px; }}
  .tags span {{ display:inline-block; border:1px solid var(--line); background:var(--paper); color:var(--ink2);
    padding:2px 13px; border-radius:14px; margin:0 6px 7px 0; font-size:13.5px; }}

  /* 方药表 */
  table.herbs {{ width:100%; border-collapse:collapse; margin-top:4px; }}
  table.herbs th {{ background:var(--navy); color:#fff; font-size:13.5px; font-weight:600; padding:10px 12px; text-align:left; letter-spacing:1px; }}
  table.herbs td {{ border-bottom:1px solid var(--line); padding:9px 12px; font-size:14.5px; vertical-align:top; }}
  table.herbs tr:nth-child(even) td {{ background:#FAF7EF; }}
  .hb-name {{ font-weight:700; color:var(--navy); white-space:nowrap; }}
  .hb-dose {{ white-space:nowrap; font-variant-numeric:tabular-nums; }}
  .hb-role {{ display:inline-block; min-width:24px; text-align:center; padding:1px 8px; border-radius:10px;
    background:var(--paper); border:1px solid var(--gold); color:var(--gold-deep); font-size:13px; }}
  .hb-reason {{ color:var(--ink2); }}
  .formula-meta {{ margin-top:10px; font-size:14.5px; }}

  /* 调护 */
  .care-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px 22px; }}
  .care-item {{ border:1px solid var(--line); border-radius:8px; padding:11px 14px; background:#FCFAF4; }}
  .care-head {{ display:flex; align-items:center; gap:8px; font-size:15px; font-weight:700; color:var(--navy); margin-bottom:5px; }}
  .care-seal {{ width:24px; height:24px; border-radius:5px; background:var(--cinnabar); color:#FBF7EE;
    display:flex; align-items:center; justify-content:center; font-size:14px; }}
  .care-item p {{ margin:0; font-size:14px; line-height:1.8; color:var(--ink); }}

  /* 文献 */
  .evidence {{ list-style:none; padding:0; margin:0; }}
  .evidence li {{ padding:8px 0 8px 18px; border-bottom:1px dashed var(--line); position:relative; font-size:14.5px; line-height:1.8; }}
  .evidence li::before {{ content:"❝"; position:absolute; left:0; top:6px; color:var(--gold); }}
  .ev-src {{ display:block; margin-top:3px; color:var(--gold-deep); font-style:normal; font-size:13px; }}

  /* 免责 + 落款 */
  .disclaimer {{ margin-top:26px; padding:14px 16px; background:#F5F3EC; border:1px dashed var(--line);
    border-radius:8px; font-size:13px; color:var(--ink2); line-height:1.75; }}
  .sign {{ margin-top:30px; display:flex; justify-content:space-between; align-items:flex-end; }}
  .sign .org {{ font-size:14px; color:var(--ink2); }}
  .sign .stamp {{ border:2px solid var(--cinnabar); color:var(--cinnabar); padding:10px 16px; border-radius:8px;
    transform:rotate(-5deg); font-size:15px; font-weight:700; letter-spacing:2px; }}

  @page {{ size:A4; margin:0; }}
  @media print {{
    body {{ background:#fff; }}
    .toolbar {{ display:none; }}
    .a4-wrap {{ display:block; padding:0; }}
    .a4-sheet {{ box-shadow:none; }}
  }}
</style></head>
<body>
  <div class="toolbar">
    <button class="btn-pdf" onclick="window.print()">⬇ 下载 / 打印 PDF</button>
    <span class="hint">打印窗口中将「目标」选为「另存为 PDF」即可下载　·　编号 {report_id}</span>
  </div>

  <div class="a4-wrap">
    <article class="a4-sheet" id="sheet">
      <header class="r-header">
        <div class="r-seal">李</div>
        <div>
          <h1 class="r-title">李时珍智能医师 · 中医辨证调护报告</h1>
          <div class="r-sub">四诊合参 · 八步辨证 · 文献溯源</div>
        </div>
      </header>
      <div class="r-meta">
        <span>报告编号：<b>{report_id}</b></span>
        <span>出具日期：<b>{date_str}</b></span>
        <span>呈现视角：<b>{role_label}</b></span>
        <span>湖北时珍实验室</span>
      </div>

      <section class="block">
        <h2>一、主诉与四诊概要</h2>
        <p>{_esc(result.get('step1_symptom_summary','')) or '—'}</p>
      </section>

      <section class="block">
        <h2>二、辨证结论</h2>
        <div class="kv">主证：<span class="lead">{_esc(s3.get('主证','')) or '待辨证'}</span>
          <span class="conf">置信度 {conf_pct}</span></div>
        <div class="kv">兼证：{('、'.join(_esc(x) for x in (s3.get('兼证') or []))) or '—'}</div>
        <div class="nature tags">病位：{_tags(s2.get('病位'))}</div>
        <div class="nature tags">病性：{_tags(s2.get('病性'))}</div>
        {f'<div class="kv">气血津液：{_esc(s2.get("气血津液",""))}</div>' if s2.get('气血津液') else ''}
      </section>

      <section class="block">
        <h2>三、治法</h2>
        <p>{_esc(result.get('step5_treatment','')) or '—'}</p>
      </section>

      <section class="block">
        <h2>四、推荐方药</h2>
        <table class="herbs">
          <tr><th style="width:22%">药材</th><th style="width:16%">剂量</th><th style="width:14%">配伍</th><th>功用说明</th></tr>
          {herb_rows}
        </table>
        {formula_meta}
      </section>

      <section class="block">
        <h2>五、调护建议</h2>
        <div class="care-grid">{care_items}</div>
      </section>

      <section class="block">
        <h2>六、文献依据</h2>
        <ul class="evidence">{evidence}</ul>
      </section>

      <div class="disclaimer">{_esc(result.get('step8_disclaimer') or DISCLAIMER)}</div>

      <div class="sign">
        <span class="org">李时珍智能医师系统 · 基于检索增强生成技术</span>
        <span class="stamp">李时珍智能医师</span>
      </div>
    </article>
  </div>
</body></html>"""


@router.post("/generate", response_model=ReportResponse)
async def generate(req: ReportRequest) -> ReportResponse:
    sess = session_store.get(req.session_id)
    if not sess or not sess.last_result:
        raise HTTPException(status_code=404, detail="会话不存在或尚无辨证结果")

    report_id = f"LSZ-RPT-{uuid.uuid4().hex[:8].upper()}"
    date_str = datetime.now().strftime("%Y年%m月%d日")
    html = _render_html(sess.last_result, sess.sources, report_id, sess.role, date_str)

    html_path = REPORTS_DIR / f"{report_id}.html"
    html_path.write_text(html, encoding="utf-8")
    download_name = html_path.name

    # 优先产出矢量 PDF（无头 Chrome / WeasyPrint）；阻塞操作放线程池，避免卡事件循环
    pdf_path = REPORTS_DIR / f"{report_id}.pdf"
    if await asyncio.to_thread(_html_to_pdf, html_path, pdf_path):
        download_name = pdf_path.name

    return ReportResponse(
        report_id=report_id,
        download_url=f"/reports/{download_name}",
    )
