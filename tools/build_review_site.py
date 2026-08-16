#!/usr/bin/env python3
"""Build the static GitHub Pages card and rulebook reference site."""

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
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>十二军团资料库</title>
  <link rel="stylesheet" href="assets/site.css">
</head>
<body>
  <header class="hero">
    <div class="topbar">
      <a class="brand" href="#cards">十二军团<span>资料库</span></a>
      <nav aria-label="主导航">
        <a href="#cards" data-route="cards">卡池</a>
        <a href="#rules" data-route="rules">规则</a>
      </nav>
    </div>
    <div class="hero-copy">
      <p class="eyebrow">SEASON 01 · REFERENCE ARCHIVE</p>
      <h1>十二军团<br><em>资料库</em></h1>
      <p>浏览卡池、核对字段，并从每个条目回到官方 PDF 原页。</p>
    </div>
  </header>
  <main>
    <section class="summary" id="summary"></section>
    <section class="view is-active" id="cards" data-view="cards">
      <div class="section-heading">
        <div><p class="eyebrow">CARD LIBRARY</p><h2>卡池</h2></div>
        <p>按名称、阵营、类型、费用和审校状态检索。</p>
      </div>
      <section class="filters" aria-label="卡池筛选">
        <label>搜索<input id="search" placeholder="编号、名称、效果"></label>
        <label>阵营<select id="faction"><option value="">全部</option></select></label>
        <label>卡类<select id="type"><option value="">全部</option></select></label>
        <label>费用<select id="cost"><option value="">全部</option></select></label>
        <label>状态<select id="status"><option value="">全部</option></select></label>
      </section>
      <p class="count" id="count"></p>
      <section class="card-grid" id="grid"></section>
    </section>
    <section class="view" id="rules" data-view="rules">
      <div class="section-heading">
        <div><p class="eyebrow">RULEBOOK 2.0</p><h2>规则</h2></div>
        <p>每一页规则手册都是一个独立条目，保留原始页码与来源。</p>
      </div>
      <section class="rule-grid" id="rule-grid"></section>
    </section>
  </main>
  <dialog id="detail"><button class="close" aria-label="关闭">×</button><div id="detail-body"></div></dialog>
  <script src="assets/app.js"></script>
</body>
</html>"""

CSS = """:root{--ink:#151618;--paper:#f4efe5;--panel:#fffdf8;--line:#d9cfbb;--gold:#a46c23;--muted:#6f695e}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 ui-serif,Georgia,"Noto Serif SC",serif}.hero{min-height:330px;color:#fff;background:radial-gradient(circle at 78% 28%,#85612d 0,transparent 27%),linear-gradient(115deg,#171818,#302819 55%,#614625);padding:0 max(24px,calc((100vw - 1200px)/2))}.topbar{height:76px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #ffffff2b}.brand{font-weight:700;color:inherit;text-decoration:none;font-size:1.05rem;letter-spacing:.06em}.brand span{color:#e9c77f;margin-left:.35em}.topbar nav{display:flex;gap:24px}.topbar nav a{color:#eae4d9;text-decoration:none;padding:8px 0;border-bottom:2px solid transparent}.topbar nav a.is-active{color:#f4d797;border-color:#f4d797}.hero-copy{max-width:620px;padding:54px 0 50px}.eyebrow{margin:0;color:var(--gold);font:700 .72rem/1.2 system-ui,sans-serif;letter-spacing:.16em}.hero .eyebrow{color:#e9c77f}.hero h1{font-size:clamp(2.8rem,7vw,5rem);line-height:.95;letter-spacing:-.05em;margin:.22em 0}.hero h1 em{color:#e9c77f;font-weight:400}.hero-copy>p:last-child{max-width:450px;color:#e3ddd2;margin:1rem 0 0}main{max-width:1200px;margin:auto;padding:26px 24px 72px}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:-48px;position:relative}.summary article{background:var(--panel);border:1px solid var(--line);box-shadow:0 6px 20px #35271512;padding:15px 18px}.summary strong{display:block;color:var(--gold);font-size:1.75rem}.view{display:none;padding-top:54px}.view.is-active{display:block}.section-heading{display:flex;justify-content:space-between;gap:24px;align-items:end;border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:22px}.section-heading h2{font-size:2.1rem;margin:.1em 0 0}.section-heading>p{max-width:400px;color:var(--muted);margin:0}.filters{display:grid;grid-template-columns:1.8fr repeat(4,1fr);gap:10px}.filters label{display:grid;gap:4px;color:var(--muted);font:700 .75rem/1.2 system-ui,sans-serif}input,select{border:1px solid var(--line);border-radius:4px;background:#fffdf7;color:var(--ink);padding:10px;font:inherit}.count{color:var(--muted);font-size:.9rem}.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(185px,1fr));gap:16px}.card{background:var(--panel);border:1px solid var(--line);padding:8px;cursor:pointer;text-align:left;color:inherit;font:inherit;transition:transform .16s,box-shadow .16s}.card:hover{transform:translateY(-3px);box-shadow:0 10px 24px #382b1a1c}.card img{display:block;width:100%;aspect-ratio:5/7;object-fit:cover;background:#e3dacb}.card h3{font-size:1rem;margin:9px 0 2px}.meta{color:var(--muted);font: .77rem/1.4 system-ui,sans-serif}.state{display:inline-block;margin-top:7px;background:#eee0be;color:#68430f;border-radius:99px;padding:2px 7px;font:700 .68rem system-ui,sans-serif}.rule-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px}.rule{background:var(--panel);border:1px solid var(--line);padding:10px}.rule img{width:100%;display:block;aspect-ratio:1/.72;object-fit:cover;object-position:top;border:1px solid #e7dece}.rule h3{margin:12px 0 3px;font-size:1.05rem}.rule p{margin:0;color:var(--muted);font:.82rem system-ui,sans-serif}.rule a,.property a{color:var(--gold);font-weight:700}dialog{max-width:min(1000px,96vw);max-height:94vh;background:var(--panel);color:var(--ink);border:1px solid var(--line);box-shadow:0 22px 70px #21170666;padding:24px}dialog::backdrop{background:#16110bae}.close{float:right;border:0;background:none;color:var(--ink);font-size:2rem;cursor:pointer}.detail-grid{display:grid;grid-template-columns:minmax(240px,42%) 1fr;gap:24px}.detail-grid img{width:100%;border:1px solid var(--line)}.properties{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.property{background:#faf6ed;border:1px solid var(--line);padding:9px}.property.wide{grid-column:1/-1}.property dt{font:700 .68rem system-ui,sans-serif;color:var(--muted);letter-spacing:.06em}.property dd{margin:4px 0 0;white-space:pre-wrap;word-break:break-word}.empty{color:#948b7b}details{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}details summary{cursor:pointer;color:var(--gold);font-weight:700}details p{white-space:pre-wrap;word-break:break-word;color:var(--muted)}@media(max-width:720px){.hero{padding:0 18px}.summary{grid-template-columns:1fr;margin-top:-24px}.section-heading{display:block}.section-heading>p{margin-top:10px}.filters{grid-template-columns:1fr 1fr}.filters label:first-child{grid-column:1/-1}.detail-grid{grid-template-columns:1fr}.properties{grid-template-columns:1fr}}"""

JS = """const q=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>\\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\\"':'&quot;',"'":'&#39;'}[c]));
let cards=[],rules=[];const field=id=>q(id).value;
function options(id,values){const s=q(id);[...values].filter(Boolean).sort().forEach(v=>s.insertAdjacentHTML('beforeend',`<option value="${esc(v)}">${esc(v)}</option>`))}
function route(){const name=location.hash==='#rules'?'rules':'cards';document.querySelectorAll('[data-view]').forEach(v=>v.classList.toggle('is-active',v.dataset.view===name));document.querySelectorAll('[data-route]').forEach(v=>v.classList.toggle('is-active',v.dataset.route===name))}
function filtered(){const term=field('#search').toLowerCase();return cards.filter(c=>{const text=[c.card_id,c.official_card_id,c.name,c.text,c.ocr?.raw_text].join(' ').toLowerCase();return(!term||text.includes(term))&&(!field('#faction')||c.faction.id===field('#faction'))&&(!field('#type')||c.card_type===field('#type'))&&(!field('#cost')||String(c.cost)===field('#cost'))&&(!field('#status')||c.review.status===field('#status'))})}
function renderCards(){const visible=filtered();q('#count').textContent=`显示 ${visible.length} / ${cards.length} 张卡`;q('#grid').innerHTML=visible.map(c=>`<button class="card" data-id="${esc(c.card_id)}"><img loading="lazy" src="cards/${encodeURIComponent(c.card_id)}.webp" alt="${esc(c.name||c.card_id)} 卡面"><h3>${esc(c.name||c.card_id)}</h3><div class="meta">${esc(c.faction.label)} · ${esc(c.card_type||'待识别')} · 费用 ${esc(c.cost??'待识别')}</div><span class="state">${esc(c.review.status)}</span></button>`).join('');q('#grid').querySelectorAll('.card').forEach(n=>n.onclick=()=>detail(cards.find(c=>c.card_id===n.dataset.id)))}
const value=v=>v===null||v===undefined||v===''?'<span class="empty">待核对</span>':esc(v);const prop=(label,content,wide=false)=>`<div class="property${wide?' wide':''}"><dt>${label}</dt><dd>${content}</dd></div>`;
function detail(c){const feedback=`${c.card_id}｜字段｜将“当前值”改为“建议值”｜依据：${c.source.pdf_path} 第 ${c.source.page} 页`;const stats=Object.keys(c.stats||{}).length?Object.entries(c.stats).map(([k,v])=>`${k}：${v}`).join(' · '):null;const tags=(c.tags||[]).join('、')||null;const props=[prop('卡牌编号',value(c.official_card_id||c.card_id)),prop('阵营',value(c.faction.label)),prop('卡牌类型',value(c.card_type)),prop('费用',value(c.cost)),prop('数值',value(stats)),prop('标签',value(tags)),prop('效果',value(c.text),true),prop('效果实现',value(c.effect.implementation_status)),prop('审校状态',value(c.review.status)),prop('备注',value(c.review.notes),true),prop('来源',`<a target="_blank" rel="noreferrer" href="${esc(c.source.github_url)}">${esc(c.source.pdf_path)} · 第 ${c.source.page} 页</a>`,true),prop('反馈模板',esc(feedback),true)].join('');q('#detail-body').innerHTML=`<div class="detail-grid"><img src="cards/${encodeURIComponent(c.card_id)}.webp" alt="${esc(c.card_id)} 卡面"><div><p class="eyebrow">${esc(c.faction.label)} · ${esc(c.review.status)}</p><h2>${esc(c.name||c.card_id)}</h2><section class="properties">${props}</section><details><summary>展开机器识别原文（未核验）</summary><p>${esc(c.ocr.raw_text||'未执行 OCR')}</p></details></div></div>`;q('#detail').showModal()}
function renderRules(){q('#rule-grid').innerHTML=rules.map(r=>`<article class="rule"><img loading="lazy" src="rules/${encodeURIComponent(r.rule_id)}.webp" alt="${esc(r.title)}"><h3>${esc(r.title)}</h3><p>原 PDF 第 ${esc(r.source.page)} 页 · ${esc(r.review.status)}</p><p><a target="_blank" rel="noreferrer" href="${esc(r.source.github_url)}">查看原 PDF</a></p></article>`).join('')}
Promise.all([fetch('data/card_pool.json').then(r=>r.json()),fetch('data/rules.json').then(r=>r.json())]).then(([pool,rulebook])=>{cards=pool.cards;rules=rulebook.rules.map(r=>({...r,title:r.title||`规则手册 2.0 · 第 ${r.source.page} 页`}));const faction=new Map(cards.map(c=>[c.faction.id,c.faction.label]));options('#faction',faction.keys());options('#type',new Set(cards.map(c=>c.card_type)));options('#cost',new Set(cards.map(c=>c.cost).filter(v=>v!==null)));options('#status',new Set(cards.map(c=>c.review.status)));const needs=cards.filter(c=>c.review.status==='needs_review').length;q('#summary').innerHTML=`<article><strong>${cards.length}</strong>卡池条目</article><article><strong>${rules.length}</strong>规则条目</article><article><strong>${needs}</strong>待复核卡牌</article>`;renderCards();renderRules();route()});
document.querySelectorAll('input,select').forEach(n=>n.oninput=renderCards);addEventListener('hashchange',route);q('.close').onclick=()=>q('#detail').close();q('#detail').onclick=e=>{if(e.target===q('#detail'))q('#detail').close()};"""


def source_url(repo_url: str, pdf_path: str, page: int) -> str:
    return f"{repo_url.rstrip('/')}/{quote(pdf_path)}#page={page}"


def render_pdf_page(pdf: Path, page: int, target: Path, crop: dict[str, float] | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix="legion12-preview-") as temp_dir:
        temp = Path(temp_dir)
        prefix = temp / "page"
        subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-r", "150", "-png", str(pdf), str(prefix)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        page_image = next(temp.glob("page-*.png"))
        image = page_image
        if crop:
            cropped = temp / "crop.png"
            if shutil.which("sips"):
                metadata = subprocess.check_output(
                    ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(page_image)], text=True
                )
                dimensions = [int(value) for value in metadata.split() if value.isdigit()]
                width, height = dimensions[-2:]
            else:
                metadata = subprocess.check_output(
                    ["identify", "-format", "%w %h", str(page_image)], text=True
                )
                width, height = (int(value) for value in metadata.split())
            crop_width, crop_height = round(width * crop["width"]), round(height * crop["height"])
            offset_x, offset_y = round(width * crop["x"]), round(height * crop["y"])
            if shutil.which("sips"):
                command = [
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
                ]
            else:
                command = [
                    "convert",
                    str(page_image),
                    "-crop",
                    f"{crop_width}x{crop_height}+{offset_x}+{offset_y}",
                    "+repage",
                    str(cropped),
                ]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            image = cropped
        subprocess.run(["cwebp", "-quiet", "-q", "80", str(image), "-o", str(target)], check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("data/card_pools/s01/card_pool.json"))
    parser.add_argument("--rules", type=Path, default=Path("data/card_pools/s01/rules.json"))
    parser.add_argument("--output", type=Path, default=Path("build/review-site"))
    parser.add_argument("--repo-url", default="https://github.com/martinhamburger/Legion-12-test/blob/main")
    parser.add_argument("--no-previews", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    cropper = "sips" if shutil.which("sips") else "convert"
    required = ("pdftoppm", "cwebp", cropper)
    missing = [command for command in required if not shutil.which(command)]
    if missing and not args.no_previews:
        raise SystemExit(f"missing preview tools: {', '.join(missing)}")
    pool = json.loads(args.catalog.read_text(encoding="utf-8"))
    rulebook = json.loads(args.rules.read_text(encoding="utf-8"))
    if args.output.exists():
        shutil.rmtree(args.output)
    for folder in ("assets", "cards", "rules", "data"):
        (args.output / folder).mkdir(parents=True, exist_ok=True)
    (args.output / "index.html").write_text(HTML, encoding="utf-8")
    (args.output / "assets" / "site.css").write_text(CSS, encoding="utf-8")
    (args.output / "assets" / "app.js").write_text(JS, encoding="utf-8")
    preview_jobs: list[tuple[Path, int, Path, dict[str, float] | None]] = []
    for card in pool["cards"]:
        card["source"]["github_url"] = source_url(args.repo_url, card["source"]["pdf_path"], card["source"]["page"])
        preview_jobs.append((Path(card["source"]["pdf_path"]), card["source"]["page"], args.output / "cards" / f"{card['card_id']}.webp", card["source"]["crop"]))
    for rule in rulebook["rules"]:
        rule["source"]["github_url"] = source_url(args.repo_url, rule["source"]["pdf_path"], rule["source"]["page"])
        preview_jobs.append((Path(rule["source"]["pdf_path"]), rule["source"]["page"], args.output / "rules" / f"{rule['rule_id']}.webp", None))
    if not args.no_previews:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            list(executor.map(lambda job: render_pdf_page(*job), preview_jobs))
    (args.output / "data" / "card_pool.json").write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
    (args.output / "data" / "rules.json").write_text(json.dumps(rulebook, ensure_ascii=False), encoding="utf-8")
    print(f"site={args.output} cards={len(pool['cards'])} rules={len(rulebook['rules'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
