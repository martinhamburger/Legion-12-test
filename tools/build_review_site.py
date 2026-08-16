#!/usr/bin/env python3
"""Build the disposable static GitHub Pages card-pool review site."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote


HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>十二军团卡池审校</title><link rel="stylesheet" href="assets/site.css"></head>
<body><header><p class="eyebrow">S01 · 只读审校站</p><h1>十二军团卡池</h1><p>OCR 候选不是真值。请根据卡面反馈卡牌编号、字段与建议修改。</p></header>
<main><section class="summary" id="summary"></section><section class="filters"><label>搜索<input id="search" placeholder="编号、名称、卡文"></label><label>阵营<select id="faction"><option value="">全部</option></select></label><label>卡类<select id="type"><option value="">全部</option></select></label><label>费用<select id="cost"><option value="">全部</option></select></label><label>状态<select id="status"><option value="">全部</option></select></label></section><p id="count"></p><section class="grid" id="grid"></section></main>
<dialog id="detail"><button class="close" aria-label="关闭">×</button><div id="detail-body"></div></dialog><script src="assets/app.js"></script></body></html>"""

CSS = """*{box-sizing:border-box}body{margin:0;background:#101114;color:#e9e7e2;font:16px/1.55 system-ui,-apple-system,"PingFang SC",sans-serif}header,main{max-width:1280px;margin:auto;padding:24px}header{padding-top:48px}.eyebrow{color:#d4ad5c;letter-spacing:.12em;text-transform:uppercase;margin:0}h1{font-size:clamp(2rem,6vw,4.5rem);margin:.15em 0}.summary{display:flex;gap:12px;flex-wrap:wrap}.summary article{background:#1b1d20;border:1px solid #30343a;padding:14px 18px;border-radius:10px;min-width:150px}.summary strong{display:block;font-size:1.5rem;color:#f0c76e}.filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:28px 0 14px}.filters label{display:grid;gap:5px;color:#c4c7c9}input,select{background:#1b1d20;border:1px solid #444a50;border-radius:7px;padding:9px;color:inherit}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:16px}.card{border:1px solid #30343a;background:#191b1e;padding:9px;border-radius:10px;cursor:pointer;text-align:left;color:inherit}.card img{display:block;width:100%;aspect-ratio:5/7;object-fit:cover;border-radius:6px;background:#24272a}.card h2{font-size:1rem;margin:8px 0 2px}.meta{color:#b1b5ba;font-size:.82rem}.state{font-size:.75rem;color:#101114;background:#f0c76e;border-radius:99px;padding:2px 7px}dialog{max-width:min(960px,96vw);max-height:94vh;background:#17191d;color:inherit;border:1px solid #4b5057;border-radius:12px;padding:24px}dialog::backdrop{background:#000b}.close{float:right;border:0;background:none;color:#fff;font-size:2rem;cursor:pointer}.detail-grid{display:grid;grid-template-columns:minmax(240px,42%) 1fr;gap:24px}.detail-grid img{width:100%;border-radius:8px}.detail-grid pre{white-space:pre-wrap;word-break:break-word;background:#101114;padding:12px;border-radius:8px;font-size:.85rem}a{color:#f0c76e}@media(max-width:650px){header,main{padding:16px}.detail-grid{grid-template-columns:1fr}}"""

JS = """const q=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
let all=[];const field=id=>q(id).value;function options(id,values){const s=q(id);[...values].filter(Boolean).sort().forEach(v=>s.insertAdjacentHTML('beforeend',`<option value="${esc(v)}">${esc(v)}</option>`))}
function filtered(){const term=field('#search').toLowerCase();return all.filter(c=>{const text=[c.card_id,c.official_card_id,c.name,c.text,c.ocr?.raw_text].join(' ').toLowerCase();return(!term||text.includes(term))&&(!field('#faction')||c.faction.id===field('#faction'))&&(!field('#type')||c.card_type===field('#type'))&&(!field('#cost')||String(c.cost)===field('#cost'))&&(!field('#status')||c.review.status===field('#status'))})}
function render(){const cards=filtered();q('#count').textContent=`显示 ${cards.length} / ${all.length} 张卡`;q('#grid').innerHTML=cards.map(c=>`<button class="card" data-id="${esc(c.card_id)}"><img loading="lazy" src="cards/${encodeURIComponent(c.card_id)}.webp" alt="${esc(c.card_id)} 卡面"><h2>${esc(c.name||c.card_id)}</h2><div class="meta">${esc(c.faction.label)} · ${esc(c.card_type||'待识别')} · 费用 ${esc(c.cost??'待识别')}</div><span class="state">${esc(c.review.status)}</span></button>`).join('');q('#grid').querySelectorAll('.card').forEach(n=>n.onclick=()=>detail(all.find(c=>c.card_id===n.dataset.id)))}
function detail(c){const feedback=`${c.card_id}｜字段｜将“当前值”改为“建议值”｜依据：${c.source.pdf_path} 第 ${c.source.page} 页`;q('#detail-body').innerHTML=`<div class="detail-grid"><img src="cards/${encodeURIComponent(c.card_id)}.webp" alt="${esc(c.card_id)} 卡面"><div><p class="eyebrow">${esc(c.faction.label)} · ${esc(c.review.status)}</p><h2>${esc(c.name||c.card_id)}</h2><p><a target="_blank" rel="noreferrer" href="${esc(c.source.github_url)}">查看原 PDF 第 ${c.source.page} 页</a></p><h3>结构化字段</h3><pre>${esc(JSON.stringify({official_card_id:c.official_card_id,card_type:c.card_type,cost:c.cost,stats:c.stats,text:c.text,tags:c.tags,evidence:c.effect},null,2))}</pre><h3>OCR 原文（未核验）</h3><pre>${esc(c.ocr.raw_text||'未执行 OCR')}</pre><h3>反馈模板</h3><pre>${esc(feedback)}</pre></div></div>`;q('#detail').showModal()}
fetch('data/card_pool.json').then(r=>r.json()).then(pool=>{all=pool.cards;const faction=new Map(all.map(c=>[c.faction.id,c.faction.label]));options('#faction',faction.keys());options('#type',new Set(all.map(c=>c.card_type)));options('#cost',new Set(all.map(c=>c.cost).filter(v=>v!==null)));options('#status',new Set(all.map(c=>c.review.status)));const needs=all.filter(c=>c.review.status==='needs_review').length;q('#summary').innerHTML=`<article><strong>${all.length}</strong>候选卡</article><article><strong>${needs}</strong>待复核</article><article><strong>${faction.size}</strong>阵营/通用</article>`;document.querySelectorAll('input,select').forEach(n=>n.oninput=render);render()});q('.close').onclick=()=>q('#detail').close();q('#detail').onclick=e=>{if(e.target===q('#detail'))q('#detail').close()};"""


def source_url(repo_url: str, pdf_path: str, page: int) -> str:
    return f"{repo_url.rstrip('/')}/{quote(pdf_path)}#page={page}"


def make_preview(pdf: Path, page: int, crop: dict[str, float], target: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="legion12-preview-") as temp_dir:
        temp = Path(temp_dir)
        prefix = temp / "page"
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "150", "-png", str(pdf), str(prefix)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        page_image = next(temp.glob("page-*.png"))
        if shutil.which("sips"):
            metadata = subprocess.check_output(
                ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(page_image)], text=True
            )
            numbers = [int(value) for value in metadata.split() if value.isdigit()]
            width, height = numbers[-2:]
        else:
            dimensions = subprocess.check_output(
                ["identify", "-format", "%w %h", str(page_image)], text=True
            )
            width, height = (int(value) for value in dimensions.split())
        crop_width, crop_height = round(width * crop["width"]), round(height * crop["height"])
        offset_x, offset_y = round(width * crop["x"]), round(height * crop["y"])
        cropped = temp / "card.png"
        if shutil.which("sips"):
            subprocess.run(
                [
                    "sips",
                    "-c",
                    str(crop_height),
                    str(crop_width),
                    "--cropOffset",
                    str(offset_y),
                    str(offset_x),
                    str(page_image),
                    "--out",
                    str(cropped),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        else:
            subprocess.run(
                [
                    "convert",
                    str(page_image),
                    "-crop",
                    f"{crop_width}x{crop_height}+{offset_x}+{offset_y}",
                    "+repage",
                    str(cropped),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        subprocess.run(["cwebp", "-quiet", "-q", "80", str(cropped), "-o", str(target)], check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("data/card_pools/s01/card_pool.json"))
    parser.add_argument("--output", type=Path, default=Path("build/review-site"))
    parser.add_argument("--repo-url", default="https://github.com/martinhamburger/Legion-12-test/blob/main")
    parser.add_argument("--no-previews", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    required = ("pdftoppm", "cwebp", "sips" if shutil.which("sips") else "convert")
    missing = [command for command in required if not shutil.which(command)]
    if missing and not args.no_previews:
        raise SystemExit(f"missing preview tools: {', '.join(missing)}")
    pool = json.loads(args.catalog.read_text(encoding="utf-8"))
    if args.output.exists():
        shutil.rmtree(args.output)
    (args.output / "assets").mkdir(parents=True)
    (args.output / "cards").mkdir()
    (args.output / "data").mkdir()
    (args.output / "index.html").write_text(HTML, encoding="utf-8")
    (args.output / "assets" / "site.css").write_text(CSS, encoding="utf-8")
    (args.output / "assets" / "app.js").write_text(JS, encoding="utf-8")
    preview_jobs = []
    for card in pool["cards"]:
        card["source"]["github_url"] = source_url(args.repo_url, card["source"]["pdf_path"], card["source"]["page"])
        if not args.no_previews:
            preview_jobs.append(
                (
                    Path(card["source"]["pdf_path"]),
                    card["source"]["page"],
                    card["source"]["crop"],
                    args.output / "cards" / f"{card['card_id']}.webp",
                )
            )
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(lambda job: make_preview(*job), preview_jobs))
    (args.output / "data" / "card_pool.json").write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
    print(f"site={args.output} cards={len(pool['cards'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
