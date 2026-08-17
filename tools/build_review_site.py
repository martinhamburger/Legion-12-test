#!/usr/bin/env python3
"""Build the static GitHub Pages review site for cards, rules, and S1 content."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>十二军团资料库</title>
  <link rel="stylesheet" href="assets/site.css?v=__CACHE_KEY__">
</head>
<body>
  <header class="hero">
    <div class="topbar">
      <button class="brand" type="button" data-route="cards">十二军团<span>资料库</span></button>
      <nav aria-label="主导航">
        <button type="button" data-route="cards">卡池</button>
        <button type="button" data-route="rules">规则</button>
        <button type="button" data-route="disasters">天灾</button>
        <button type="button" data-route="factions">阵营资源</button>
        <button type="button" data-route="decks">参考构筑</button>
        <button type="button" data-route="lab">学习实验室</button>
      </nav>
    </div>
    <div class="hero-copy">
      <p class="eyebrow">SEASON 01 · REVIEW ARCHIVE</p>
      <h1>十二军团<br><em>资料库</em></h1>
      <p>面向审校的结构化资料：卡池、规则、天灾、阵营资源与首测构筑。</p>
    </div>
  </header>
  <main>
    <section class="summary" id="summary"></section>
    <section class="view is-active" id="cards" data-view="cards">
      <div class="section-heading"><div><p class="eyebrow">CARD LIBRARY</p><h2>卡池</h2></div><p>按名称、阵营、类型、费用和审校状态检索。</p></div>
      <section class="filters" aria-label="卡池筛选">
        <label>搜索<input id="search" placeholder="编号、名称、效果"></label>
        <label>阵营<select id="faction"><option value="">全部</option></select></label>
        <label>卡类<select id="type"><option value="">全部</option></select></label>
        <label>费用<select id="cost"><option value="">全部</option></select></label>
        <label>状态<select id="status"><option value="">全部</option></select></label>
      </section>
      <p class="count" id="count"></p><section class="card-grid" id="grid"></section>
    </section>
    <section class="view" id="rules" data-view="rules">
      <div class="section-heading"><div><p class="eyebrow">RULEBOOKS</p><h2>规则</h2></div><p>规则手册 2.0 是首测真值；Ver1.0 仅供历史差异追溯。</p></div>
      <section class="tabs"><button class="tab is-active" data-rulebook="current">规则手册 2.0</button><button class="tab" data-rulebook="historical">历史 Ver1.0</button></section>
      <section class="rulebook" id="rulebook"></section>
    </section>
    <section class="view" id="disasters" data-view="disasters">
      <div class="section-heading"><div><p class="eyebrow">S01 DISASTER CATALOGUE</p><h2>天灾</h2></div><p>仅 S01-DS01 至 S01-DS10 属于首测天灾池；《湮灭》固定置底。</p></div>
      <section class="entity-grid" id="disaster-grid"></section>
    </section>
    <section class="view" id="factions" data-view="factions">
      <div class="section-heading"><div><p class="eyebrow">FACTION MORALE</p><h2>阵营资源</h2></div><p>士气牌是阵营资源，不混入普通主牌库。</p></div>
      <section class="entity-grid" id="faction-grid"></section>
    </section>
    <section class="view" id="decks" data-view="decks">
      <div class="section-heading"><div><p class="eyebrow">FIRST MATCH BASELINES</p><h2>参考构筑</h2></div><p>用于规则正确性与首轮单卡替换；不代表环境强度结论。</p></div>
      <section class="deck-grid" id="deck-grid"></section>
    </section>
    <section class="view" id="lab" data-view="lab">
      <div class="section-heading"><div><p class="eyebrow">APPROXIMATE LEARNING LAB</p><h2>学习实验室</h2></div><p>固定构筑的近似对局结果，用于学习与复盘，不代表正式规则胜率。</p></div>
      <section id="lab-view"></section>
    </section>
  </main>
  <dialog id="detail"><button class="close" aria-label="关闭">×</button><div id="detail-body"></div></dialog>
  <script src="assets/app.js?v=__CACHE_KEY__"></script>
</body>
</html>"""

CSS = """
:root{--ink:#17191e;--paper:#f4efe5;--panel:#fffdf8;--line:#d9cfbb;--gold:#a46c23;--wine:#702d32;--muted:#6f695e}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 ui-serif,Georgia,"Noto Serif SC",serif}.hero{min-height:330px;color:#fff;background:radial-gradient(circle at 78% 28%,#85612d 0,transparent 27%),linear-gradient(115deg,#171818,#302819 55%,#614625);padding:0 max(24px,calc((100vw - 1200px)/2))}.topbar{height:76px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #ffffff2b}.brand,.topbar nav button{border:0;background:none;color:inherit;cursor:pointer}.brand{font-weight:700;font-size:1.05rem;letter-spacing:.06em;padding:0}.brand span{color:#e9c77f;margin-left:.35em}.topbar nav{display:flex;gap:20px;flex-wrap:wrap}.topbar nav button{padding:8px 0;border-bottom:2px solid transparent;color:#eae4d9;font:inherit}.topbar nav button.is-active{color:#f4d797;border-color:#f4d797}.hero-copy{max-width:620px;padding:54px 0 50px}.eyebrow{margin:0;color:var(--gold);font:700 .72rem/1.2 system-ui,sans-serif;letter-spacing:.16em}.hero .eyebrow{color:#e9c77f}.hero h1{font-size:clamp(2.8rem,7vw,5rem);line-height:.95;letter-spacing:-.05em;margin:.22em 0}.hero h1 em{color:#e9c77f;font-weight:400}.hero-copy>p:last-child{max-width:500px;color:#e3ddd2;margin:1rem 0 0}main{max-width:1200px;margin:auto;padding:26px 24px 72px}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:-48px;position:relative}.summary article,.deck,.entity{background:var(--panel);border:1px solid var(--line);box-shadow:0 6px 20px #35271512;padding:15px 18px}.summary strong{display:block;color:var(--gold);font-size:1.75rem}.view{display:none;padding-top:54px}.view.is-active{display:block}.section-heading{display:flex;justify-content:space-between;gap:24px;align-items:end;border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:22px}.section-heading h2{font-size:2.1rem;margin:.1em 0 0}.section-heading>p{max-width:430px;color:var(--muted);margin:0}.filters{display:grid;grid-template-columns:1.8fr repeat(4,1fr);gap:10px}.filters label{display:grid;gap:4px;color:var(--muted);font:700 .75rem/1.2 system-ui,sans-serif}input,select{border:1px solid var(--line);border-radius:4px;background:#fffdf7;color:var(--ink);padding:10px;font:inherit}.count{color:var(--muted);font-size:.9rem}.card-grid,.entity-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.card,.entity{padding:7px;cursor:pointer;text-align:left;color:inherit;font:inherit;transition:transform .16s,box-shadow .16s}.card:hover,.entity:hover{transform:translateY(-3px);box-shadow:0 10px 24px #382b1a1c}.card img,.entity img{display:block;width:100%;aspect-ratio:5/7;object-fit:cover;background:#e3dacb}.card h3,.entity h3{font-size:.94rem;margin:7px 0 2px}.meta{color:var(--muted);font:.72rem/1.35 system-ui,sans-serif}.state{display:inline-block;margin-top:6px;background:#eee0be;color:#68430f;border-radius:99px;padding:2px 6px;font:700 .64rem system-ui,sans-serif}.state.final{background:#eed1d1;color:var(--wine)}.tabs{display:flex;gap:8px;margin-bottom:16px}.tab{border:1px solid var(--line);background:var(--panel);padding:9px 14px;cursor:pointer;font:inherit}.tab.is-active{background:var(--ink);color:#fff;border-color:var(--ink)}.rulebook{background:var(--panel);border:1px solid var(--line);box-shadow:0 8px 24px #3527150d;padding:clamp(20px,4vw,52px)}.rule-notice{border-left:4px solid var(--gold);background:#faf4e8;padding:12px 15px;margin-bottom:22px}.rule-chapter{max-width:900px;margin:auto;padding:28px 0;border-bottom:1px solid var(--line)}.rule-chapter:first-child{padding-top:0}.rule-chapter h3{margin:0;color:var(--gold);font-size:clamp(1.35rem,3vw,1.9rem);font-weight:800;letter-spacing:.02em}.rule-meta{margin:5px 0 18px;color:var(--muted);font:.76rem system-ui,sans-serif}.rule-text{color:#302b22;font-size:1rem;line-height:1.9}.rule-text p{margin:.45em 0}.rule-text h4{margin:1.55em 0 .5em;padding-left:.72em;border-left:3px solid var(--gold);color:#76501c;font-size:1.16rem}.rule-images{max-width:980px;margin:34px auto 0;padding-top:20px;border-top:1px solid var(--line)}.rule-images summary{cursor:pointer;color:var(--gold);font-weight:800;font-size:1.05rem}.rule-image-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:18px}.rule-image-list figure{margin:0;padding:8px;background:#faf6ed;border:1px solid var(--line)}.rule-image-list img{display:block;width:100%}.rule-image-list figcaption{margin-top:6px;color:var(--muted);font:.75rem system-ui,sans-serif}.deck-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.deck h3{margin:.2em 0}.deck dl,.properties{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.deck dt,.property dt{font:700 .68rem system-ui,sans-serif;color:var(--muted);letter-spacing:.06em}.deck dd,.property dd{margin:4px 0 0;white-space:pre-wrap;word-break:break-word}.deck .list{grid-column:1/-1;border-top:1px solid var(--line);padding-top:10px}.entity-grid{grid-template-columns:repeat(3,minmax(0,1fr))}dialog{max-width:min(1000px,96vw);max-height:94vh;background:var(--panel);color:var(--ink);border:1px solid var(--line);box-shadow:0 22px 70px #21170666;padding:24px}dialog::backdrop{background:#16110bae}.close{float:right;border:0;background:none;color:var(--ink);font-size:2rem;cursor:pointer}.detail-grid{display:grid;grid-template-columns:minmax(240px,42%) 1fr;gap:24px}.detail-grid img{width:100%;border:1px solid var(--line)}.properties{margin-top:1rem}.property{background:#faf6ed;border:1px solid var(--line);padding:9px}.property.wide{grid-column:1/-1}.empty{color:#948b7b}details{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}details summary{cursor:pointer;color:var(--gold);font-weight:700}details p{white-space:pre-wrap;word-break:break-word;color:var(--muted)}a{color:var(--gold);font-weight:700}@media(max-width:980px){.card-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.summary{grid-template-columns:repeat(2,1fr)}}@media(max-width:720px){.hero{padding:0 18px}.topbar{height:auto;min-height:76px;padding:14px 0}.topbar nav{gap:12px}.summary{grid-template-columns:1fr;margin-top:-24px}.section-heading{display:block}.section-heading>p{margin-top:10px}.filters{grid-template-columns:1fr 1fr}.filters label:first-child{grid-column:1/-1}.card-grid,.entity-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.deck-grid{grid-template-columns:1fr}.properties,.deck dl{grid-template-columns:1fr}.rulebook{padding:20px}.rule-image-list{grid-template-columns:1fr}.detail-grid{grid-template-columns:1fr}}
"""

LAB_CSS = """
.lab-notice{border-left:4px solid var(--wine);background:#f9eeee;padding:14px 17px;margin-bottom:18px}.lab-notice p{margin:.25em 0}.lab-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:18px 0}.lab-card{background:var(--panel);border:1px solid var(--line);box-shadow:0 6px 20px #35271512;padding:16px}.lab-card h3{margin:.1em 0 .55em;font-size:1rem}.lab-card strong{display:block;color:var(--gold);font-size:1.8rem}.lab-card p,.lab-card li{color:var(--muted);font-size:.88rem}.lab-card ul{padding-left:1.2em;margin:.4em 0}.lab-chart{grid-column:span 2}.lab-chart svg{width:100%;height:160px;background:#faf6ed;border:1px solid var(--line)}.lab-chart polyline{fill:none;stroke:var(--wine);stroke-width:3}.lab-table{width:100%;border-collapse:collapse;font-size:.9rem}.lab-table th,.lab-table td{text-align:left;border-bottom:1px solid var(--line);padding:8px;vertical-align:top}.lab-table th{color:var(--muted);font:.7rem system-ui,sans-serif}.replay-list details{background:var(--panel);border:1px solid var(--line);padding:12px 15px}.replay-list summary{color:var(--ink)}.replay-list ol{padding-left:1.3em;color:var(--muted);font-size:.87rem}.replay-list li{margin:.4em 0}@media(max-width:980px){.lab-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.lab-chart{grid-column:span 2}}@media(max-width:720px){.lab-grid{grid-template-columns:1fr}.lab-chart{grid-column:auto}.lab-table{font-size:.78rem}}
"""

LAB_SUMMARY_CSS = """
.learning-guide{margin:10px 0 16px;color:var(--muted)}.learning-card-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.learning-card{background:var(--panel);border:1px solid var(--line);padding:14px}.learning-card h4{margin:0 0 6px;font-size:1rem}.learning-card p{margin:0;color:var(--muted);font-size:.88rem}.learning-card .meta{display:block;margin-top:9px}@media(max-width:980px){.learning-card-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:720px){.learning-card-grid{grid-template-columns:1fr}}
"""

JS = """
const q=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const VERSION='__CACHE_KEY__';let cards=[],currentRules=[],historicalRules=[],disasters=[],factions=[],decks=[],lab=null,labSweeps=null,activeRulebook='current';
const field=id=>q(id).value;const value=v=>v===null||v===undefined||v===''?'<span class="empty">待核对</span>':esc(v);
const prop=(label,content,wide=false)=>`<div class="property${wide?' wide':''}"><dt>${label}</dt><dd>${content}</dd></div>`;
function route(name=location.hash.slice(1)||'cards'){document.querySelectorAll('[data-view]').forEach(v=>v.classList.toggle('is-active',v.dataset.view===name));document.querySelectorAll('[data-route]').forEach(v=>v.classList.toggle('is-active',v.dataset.route===name));}
function go(name){history.replaceState(null,'',`#${name}`);route(name);window.scrollTo(0,0)}
function options(id,values){const select=q(id);[...values].filter(Boolean).sort().forEach(v=>select.insertAdjacentHTML('beforeend',`<option value="${esc(v)}">${esc(v)}</option>`));}
function filtered(){const term=field('#search').toLowerCase();return cards.filter(c=>{const text=[c.card_id,c.official_card_id,c.name,c.text,c.ocr?.raw_text].join(' ').toLowerCase();return(!term||text.includes(term))&&(!field('#faction')||c.faction.id===field('#faction'))&&(!field('#type')||c.card_type===field('#type'))&&(!field('#cost')||String(c.cost)===field('#cost'))&&(!field('#status')||c.review.status===field('#status'));});}
function renderCards(){const visible=filtered();q('#count').textContent=`显示 ${visible.length} / ${cards.length} 张卡`;q('#grid').innerHTML=visible.map(c=>`<button class="card" data-id="${esc(c.card_id)}"><img loading="lazy" src="${esc(c.preview)}" alt="${esc(c.name||c.card_id)} 卡面"><h3>${esc(c.name||c.card_id)}</h3><div class="meta">${esc(c.faction.label)} · ${esc(c.card_type||'待识别')} · 费用 ${esc(c.cost??'待识别')}</div><span class="state">${esc(c.review.status)}</span></button>`).join('');q('#grid').querySelectorAll('.card').forEach(n=>n.onclick=()=>cardDetail(cards.find(c=>c.card_id===n.dataset.id)));}
function sourceLink(source){return source.github_url?`<a target="_blank" rel="noreferrer" href="${esc(source.github_url)}">${esc(source.asset_path||source.pdf_path||source.image_path)}</a>`:value(source.asset_path||source.pdf_path||source.image_path);}
function learningInsight(cardId){return lab?.card_insights?.find(item=>item.card_id===cardId);}
function simpleLearningSummary(insight){const usage=insight.play_rate>=.5?'经常会被打出':insight.play_rate>=.2?'有条件地打出':'在当前样本中较少打出';const mulligan=insight.mulligan_retention_rate>=.8?'按当前固定调度会保留':insight.mulligan_retention_rate<=.2?'按当前固定调度会换掉':'固定调度下取舍不明显';return `${usage}（打出率 ${(insight.play_rate*100).toFixed(1)}%）；${mulligan}。当前只近似：${insight.approximated.join('、')}。`}
function learningCardSummary(card){const insight=learningInsight(card.official_card_id);return insight?`${simpleLearningSummary(insight)} 出场后的关联胜率 ${(insight.conditional_win_rate*100).toFixed(1)}%，但会受阵营与对局结构影响，不能理解为单卡强度。`:'当前两套固定构筑没有使用这张卡，因此没有近似对局样本；这不代表它弱。';}
function cardDetail(c){const stats=Object.entries(c.stats||{}).map(([k,v])=>`${k}：${v}`).join(' · ');const props=[prop('正式编号',value(c.official_card_id)),prop('阵营',value(c.faction.label)),prop('原始类型',value(c.card_type)),prop('引擎类型',value(c.engine_card_type)),prop('费用',value(c.cost)),prop('兵力',value(stats)),prop('近似实验总结',value(learningCardSummary(c)),true),prop('效果',value(c.text),true),prop('实现状态',value(c.effect?.implementation_status)),prop('审校状态',value(c.review?.status)),prop('备注',value(c.review?.notes),true),prop('来源',sourceLink(c.source),true)].join('');q('#detail-body').innerHTML=`<div class="detail-grid"><img src="${esc(c.preview)}" alt="${esc(c.name||c.card_id)} 卡面"><div><p class="eyebrow">${esc(c.faction.label)} · ${esc(c.review.status)}</p><h2>${esc(c.name||c.card_id)}</h2><section class="properties">${props}</section><details><summary>展开原始提取记录</summary><p>${esc(c.ocr?.raw_text||'无')}</p></details></div></div>`;q('#detail').showModal();}
function ruleText(text){return String(text||'等待多模态文字提取。').split(/\\n+/).map(line=>line.trim()).filter(Boolean).map(line=>{const content=esc(line);return line.length<=28&&!/[。；，：]/.test(line)&&!/^[·•—\\d-]/.test(line)?`<h4>${content}</h4>`:`<p>${content}</p>`;}).join('');}
function renderRules(){const isHistorical=activeRulebook==='historical';const rules=isHistorical?historicalRules:currentRules;const notice=isHistorical?'<aside class="rule-notice"><strong>历史参考</strong>：Ver1.0 不参与 standard-2.0-s01、训练或严格模拟。差异项会单独复核。</aside>':'<aside class="rule-notice"><strong>首测规则真值</strong>：规则手册 2.0 与正式卡面优先；未实现内容不会被静默使用。</aside>';const chapters=rules.map(r=>`<article class="rule-chapter" id="${esc(r.rule_id)}"><h3>${esc(r.title)}</h3><div class="rule-meta">第 ${esc(r.source.page)} 页 · ${esc(r.review.status)}</div><div class="rule-text">${ruleText(r.text)}</div></article>`).join('');const images=rules.map(r=>`<figure><img loading="lazy" src="${esc(r.preview)}" alt="${esc(r.title)} 原始截图"><figcaption>${esc(r.title)} · ${sourceLink(r.source)}</figcaption></figure>`).join('');q('#rulebook').innerHTML=`${notice}${chapters}<details class="rule-images"><summary>展开原始规则截图（${rules.length} 页）</summary><div class="rule-image-list">${images}</div></details>`;}
function entityDetail(entity,title){const properties=Object.entries(entity).filter(([key])=>!['source','preview','effect','effects','review'].includes(key)).map(([key,val])=>prop(key,typeof val==='object'?value(JSON.stringify(val,null,2)):value(val),key==='text')).join('');q('#detail-body').innerHTML=`<div><p class="eyebrow">${esc(entity.review?.status||'资料')}</p><h2>${esc(title)}</h2><section class="properties">${properties}${prop('效果文本',value(entity.text),true)}${prop('实现状态',value(entity.effect?.implementation_status),true)}${prop('审校备注',value(entity.review?.notes),true)}${prop('来源',sourceLink(entity.source),true)}</section></div>`;q('#detail').showModal();}
function renderDisasters(){q('#disaster-grid').innerHTML=disasters.map(d=>`<button class="entity" data-id="${esc(d.disaster_id)}"><img loading="lazy" src="${esc(d.preview)}" alt="${esc(d.name)} 卡面"><h3>${esc(d.name)}</h3><div class="meta">${esc(d.official_card_id)} · ${esc(d.timing)}</div><span class="state${d.is_final?' final':''}">${d.is_final?'最终天灾':'S1 天灾'}</span></button>`).join('');q('#disaster-grid').querySelectorAll('.entity').forEach(n=>n.onclick=()=>{const d=disasters.find(item=>item.disaster_id===n.dataset.id);entityDetail(d,d.name);});}
function renderFactions(){q('#faction-grid').innerHTML=factions.map(f=>`<button class="entity" data-id="${esc(f.faction_id)}"><img loading="lazy" src="${esc(f.preview)}" alt="${esc(f.label)} 士气卡"><h3>${esc(f.label)}</h3><div class="meta">${esc(f.resource_definition_id)} · ${esc(f.morale_deck_size)} 张士气</div><span class="state">阵营资源</span></button>`).join('');q('#faction-grid').querySelectorAll('.entity').forEach(n=>n.onclick=()=>{const f=factions.find(item=>item.faction_id===n.dataset.id);entityDetail(f,`${f.label}士气资源`);});}
function renderDecks(){q('#deck-grid').innerHTML=decks.map(d=>{const rows=Object.entries(d.cards).map(([id,count])=>{const card=cards.find(c=>c.official_card_id===id);return `${count} × ${esc(card?.name||id)}`;}).join('\\n');return `<article class="deck"><p class="eyebrow">${esc(d.faction_id)} · ${esc(d.ruleset_id)}</p><h3>${esc(d.name)}</h3><dl><div><dt>主宰者</dt><dd>${esc(cards.find(c=>c.official_card_id===d.ruler_official_card_id)?.name||d.ruler_official_card_id)}</dd></div><div><dt>主牌库</dt><dd>${Object.values(d.cards).reduce((a,b)=>a+b,0)} 张</dd></div><div class="list"><dt>卡表</dt><dd>${rows}</dd></div><div class="list"><dt>审校状态</dt><dd>${esc(d.review.status)} · ${esc(d.review.notes)}</dd></div></dl></article>`;}).join('');}
function renderLab(){if(!lab)return;const e=lab.evaluation,c=lab.coverage,d=lab.deck_insights,curve=lab.training_curve||[];const chart=(title,key,format=v=>v)=>{const values=curve.map(p=>p[key]);const low=Math.min(...values),high=Math.max(...values);const points=curve.map((p,i)=>`${Math.round(i*100/(Math.max(curve.length-1,1)))} ${Math.round(92-(p[key]-low)*84/(high-low||1))}`).join(' ');return `<article class="lab-card lab-chart"><h3>${title}</h3><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="${title}"><polyline points="${points}"></polyline></svg><p>第 ${esc(curve.at(-1)?.episode)} 局：${esc(format(curve.at(-1)?.[key]))}</p></article>`;};const insightRows=(lab.card_insights||[]).sort((a,b)=>b.play_count-a.play_count).slice(0,12).map(i=>`<tr><td>${esc(i.card_id)}<br>${esc(i.name)}</td><td>${esc(i.cost)}</td><td>${(i.play_rate*100).toFixed(1)}%</td><td>${(i.mulligan_retention_rate*100).toFixed(1)}%</td><td>${(i.conditional_win_rate*100).toFixed(1)}%</td><td>${esc(i.review_status)}</td><td>${esc(i.approximated.join('、')||'基础单位')}</td></tr>`).join('');const replays=(lab.representative_replays||[]).map((r,i)=>`<details><summary>回放 ${i+1} · seed ${esc(r.seed)} · ${esc(r.turns)} 回合 · ${esc(r.winner||'平局')}</summary><ol>${(r.steps||[]).map(s=>`<li><strong>回合 ${esc(s.turn)} · ${esc(s.player)}</strong><br>手牌：${esc(s.hand.join('、'))}<br>士气：活跃 ${esc(s.active_morale)} / 休整 ${esc(s.rested_morale)}；场面：${esc(s.board.join('、')||'空')}；对方血量：${esc(s.opponent_health)}<br>可选：${esc(s.legal_actions.join('、'))}<br>选择：${esc(s.chosen_action)}（${esc(s.reason)}）<br>结算：${esc(s.resolution)}</li>`).join('')}</ol></details>`).join('');q('#lab-view').innerHTML=`<aside class="lab-notice"><strong>${esc(lab.disclaimer)}</strong><p>严格规则加载器与本实验室隔离。未建模：${esc(c.unmodeled.join('、'))}。起手调度固定为：费用不低于 6 的卡替换；保留率不是模型学出的结论。</p></aside><section class="lab-grid"><article class="lab-card"><h3>学习策略对规则基线</h3><strong>${(e.learned_score*100).toFixed(1)}%</strong><p>${esc(e.learned_wins)} / ${esc(e.games)} 胜；95% 区间 ${(e.confidence_95[0]*100).toFixed(1)}%–${(e.confidence_95[1]*100).toFixed(1)}%。</p></article><article class="lab-card"><h3>本次固定配置</h3><p>seed ${esc(lab.config.seed)} · 训练 ${esc(lab.config.training_episodes)} 局 · 评估 ${esc(e.games)} 局 · 最多 ${esc(lab.config.max_turns)} 回合。</p><p>规则基线 ${esc(e.baseline_wins)} 胜；学习策略 ${esc(e.learned_wins)} 胜。</p></article><article class="lab-card"><h3>费用与资源</h3><p>费用曲线：${esc(Object.entries(d.cost_curve).map(([cost,count])=>`${cost}费 ${count}`).join(' · '))}。</p><p>平均未花完活跃士气：${esc(d.morale_waste_per_turn)}。</p></article>${chart('训练回报','mean_reward',v=>v.toFixed(3))}${chart('训练胜率','win_rate',v=>`${(v*100).toFixed(1)}%`)}${chart('探索率','epsilon',v=>v.toFixed(3))}${chart('平均对局长度','mean_turns',v=>`${v} 回合`)}</section><h3>卡牌洞察（按本次打出次数）</h3><p class="meta">${esc(d.metric_note)}</p><table class="lab-table"><thead><tr><th>卡牌</th><th>费用</th><th>打出率</th><th>固定调度保留</th><th>条件胜率</th><th>审校</th><th>已近似</th></tr></thead><tbody>${insightRows}</tbody></table><h3>代表性逐回合回放</h3><section class="replay-list">${replays}</section>`;}
function renderSimpleCardInsights(){if(!lab)return;const cards=(lab.card_insights||[]).slice().sort((a,b)=>a.card_id.localeCompare(b.card_id));const entries=cards.map(i=>`<article class="learning-card"><h4>${esc(i.name)} <span class="meta">${esc(i.card_id)}</span></h4><p>${esc(simpleLearningSummary(i))}</p><span class="meta">关联胜率 ${(i.conditional_win_rate*100).toFixed(1)}% · ${esc(i.review_status)} · 相关性非因果</span></article>`).join('');q('#lab-view').insertAdjacentHTML('beforeend',`<h3>每张相关卡的简单结论</h3><p class="learning-guide">读法：先看“常不常打、固定调度是否保留、近似了什么”。关联胜率只记录该卡出现时本方是否获胜，不能单独证明强度。</p><section class="learning-card-grid">${entries}</section>`);}
function renderLabSweeps(){if(!labSweeps)return;const rows=labSweeps.budget_comparison.map(r=>`<tr><td>${esc((r.training_episodes/1000).toFixed(0))}k</td><td>${esc(r.seeds)}</td><td>${esc(r.pooled_games.toLocaleString())}</td><td>${(r.mean_score*100).toFixed(2)}%</td><td>${(r.score_standard_deviation*100).toFixed(2)} pp</td></tr>`).join('');q('#lab-view').insertAdjacentHTML('beforeend',`<h3>多 seed 稳定性与训练预算</h3><aside class="lab-notice"><strong>推荐 ${esc((labSweeps.stability.recommended_training_episodes/1000).toFixed(0))}k 局训练</strong><p>${esc(labSweeps.stability.reason)}</p><p>${esc(labSweeps.evaluation_protocol)} 已累计 ${esc(labSweeps.stability.total_evaluation_games.toLocaleString())} 局评估。</p></aside><table class="lab-table"><thead><tr><th>训练预算</th><th>seed</th><th>评估局数</th><th>平均胜率</th><th>seed 标准差</th></tr></thead><tbody>${rows}</tbody></table>`);}
Promise.all([fetch(`data/card_pool.json?v=${VERSION}`).then(r=>r.json()),fetch(`data/rules-current.json?v=${VERSION}`).then(r=>r.json()),fetch(`data/rules-historical.json?v=${VERSION}`).then(r=>r.json()),fetch(`data/disasters.json?v=${VERSION}`).then(r=>r.json()),fetch(`data/factions.json?v=${VERSION}`).then(r=>r.json()),fetch(`data/decks.json?v=${VERSION}`).then(r=>r.json()),fetch(`data/lab.json?v=${VERSION}`).then(r=>r.json()),fetch(`data/lab-sweeps.json?v=${VERSION}`).then(r=>r.json())]).then(([pool,current,historical,disasterSet,factionSet,deckSet,labSet,sweepSet])=>{cards=pool.cards;currentRules=current.rules;historicalRules=historical.rules;disasters=disasterSet.cards;factions=factionSet.factions;decks=deckSet.decks;lab=labSet;labSweeps=sweepSet;const labels=new Map(cards.map(c=>[c.faction.id,c.faction.label]));options('#faction',labels.keys());options('#type',new Set(cards.map(c=>c.card_type)));options('#cost',new Set(cards.map(c=>c.cost).filter(v=>v!==null)));options('#status',new Set(cards.map(c=>c.review.status)));const verified=cards.filter(c=>c.review.status==='verified').length;q('#summary').innerHTML=`<article><strong>${cards.length}</strong>卡池条目</article><article><strong>${currentRules.length}</strong>规则 2.0 条目</article><article><strong>${disasters.length}</strong>S1 天灾</article><article><strong>${verified}</strong>已审校卡牌</article>`;renderCards();renderRules();renderDisasters();renderFactions();renderDecks();renderLab();renderSimpleCardInsights();renderLabSweeps();route();});
document.querySelectorAll('input,select').forEach(node=>node.oninput=renderCards);document.querySelectorAll('[data-route]').forEach(node=>node.onclick=()=>go(node.dataset.route));document.querySelectorAll('[data-rulebook]').forEach(node=>node.onclick=()=>{activeRulebook=node.dataset.rulebook;document.querySelectorAll('[data-rulebook]').forEach(tab=>tab.classList.toggle('is-active',tab===node));renderRules();});addEventListener('hashchange',()=>route());q('.close').onclick=()=>q('#detail').close();q('#detail').onclick=e=>{if(e.target===q('#detail'))q('#detail').close();};
"""


def source_url(repo_url: str, source: dict[str, object]) -> str:
    path = source.get("asset_path") or source.get("pdf_path") or source.get("image_path")
    if not isinstance(path, str):
        return ""
    suffix = f"#page={source['page']}" if isinstance(source.get("page"), int) else ""
    return f"{repo_url.rstrip('/')}/{quote(path)}{suffix}"


def render_pdf_page(
    pdf: Path, page: int, target: Path, crop: dict[str, float] | None = None
) -> None:
    with tempfile.TemporaryDirectory(prefix="legion12-preview-") as temp_dir:
        temp = Path(temp_dir)
        prefix = temp / "page"
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                str(page),
                "-l",
                str(page),
                "-r",
                "150",
                "-png",
                str(pdf),
                str(prefix),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        image = next(temp.glob("page-*.png"))
        if crop:
            image = crop_image(image, crop, temp / "crop.png")
        subprocess.run(["cwebp", "-quiet", "-q", "80", str(image), "-o", str(target)], check=True)


def crop_image(image: Path, crop: dict[str, float], target: Path) -> Path:
    """Crop fractional source coordinates with ImageMagick or macOS sips."""

    if shutil.which("convert"):
        geometry = (
            f"{crop['width'] * 100}%x{crop['height'] * 100}%+{crop['x'] * 100}%+{crop['y'] * 100}%"
        )
        command = [
            "convert",
            str(image),
            "-gravity",
            "NorthWest",
            "-crop",
            geometry,
            "+repage",
            str(target),
        ]
    else:
        output = subprocess.check_output(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(image)], text=True
        )
        values = {
            line.split(":", 1)[0].strip(): float(line.split(":", 1)[1].strip())
            for line in output.splitlines()
            if ":" in line and line.split(":", 1)[0].strip() in {"pixelWidth", "pixelHeight"}
        }
        width = round(values["pixelWidth"] * crop["width"])
        height = round(values["pixelHeight"] * crop["height"])
        left = round(values["pixelWidth"] * crop["x"])
        top = round(values["pixelHeight"] * crop["y"])
        command = [
            "sips",
            "-c",
            str(height),
            str(width),
            "--cropOffset",
            str(top),
            str(left),
            str(image),
            "--out",
            str(target),
        ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return target


def render_image(image: Path, target: Path) -> None:
    subprocess.run(["cwebp", "-quiet", "-q", "80", str(image), "-o", str(target)], check=True)


def add_preview(
    item: dict[str, object],
    output: Path,
    folder: str,
    identifier: str,
    repo_url: str,
    jobs: list[tuple[str, Path, int | None, Path, dict[str, float] | None]],
) -> None:
    source = item["source"]
    if not isinstance(source, dict):
        raise ValueError(f"{identifier} has no source")
    source["github_url"] = source_url(repo_url, source)
    path = source.get("pdf_path") or source.get("image_path")
    if not isinstance(path, str):
        raise ValueError(f"{identifier} has no preview path")
    target = output / folder / f"{identifier}.webp"
    item["preview"] = f"{folder}/{identifier}.webp"
    jobs.append(
        (
            "pdf" if source.get("kind") != "image" else "image",
            Path(path),
            source.get("page"),
            target,
            source.get("crop"),
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("data/card_pools/s01/card_pool.json"))
    parser.add_argument("--rules", type=Path, default=Path("data/card_pools/s01/rules.json"))
    parser.add_argument(
        "--historical-rules", type=Path, default=Path("data/rulesets/handbook-v1-2025-04-26.json")
    )
    parser.add_argument("--disasters", type=Path, default=Path("data/s1/disasters.json"))
    parser.add_argument("--factions", type=Path, default=Path("data/s1/faction_resources.json"))
    parser.add_argument("--decks", type=Path, default=Path("data/s1/reference_decks.json"))
    parser.add_argument("--lab", type=Path, default=Path("data/labs/s1-approx-v0/latest.json"))
    parser.add_argument(
        "--lab-sweeps", type=Path, default=Path("data/labs/s1-approx-v0/sweeps/summary.json")
    )
    parser.add_argument("--output", type=Path, default=Path("build/review-site"))
    parser.add_argument(
        "--repo-url", default="https://github.com/martinhamburger/Legion-12-test/blob/main"
    )
    parser.add_argument("--no-previews", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not args.no_previews:
        missing = [tool for tool in ("pdftoppm", "cwebp") if not shutil.which(tool)]
        if not shutil.which("convert") and not shutil.which("sips"):
            missing.append("convert or sips")
        if missing:
            raise SystemExit(f"missing preview tools: {', '.join(missing)}")
    pool = json.loads(args.catalog.read_text(encoding="utf-8"))
    current_rules = json.loads(args.rules.read_text(encoding="utf-8"))
    historical_rules = json.loads(args.historical_rules.read_text(encoding="utf-8"))
    disasters = json.loads(args.disasters.read_text(encoding="utf-8"))
    factions = json.loads(args.factions.read_text(encoding="utf-8"))
    decks = json.loads(args.decks.read_text(encoding="utf-8"))
    lab = json.loads(args.lab.read_text(encoding="utf-8"))
    lab_sweeps = json.loads(args.lab_sweeps.read_text(encoding="utf-8"))
    if args.output.exists():
        shutil.rmtree(args.output)
    for folder in (
        "assets",
        "cards",
        "rules-current",
        "rules-historical",
        "disasters",
        "factions",
        "data",
    ):
        (args.output / folder).mkdir(parents=True, exist_ok=True)
    jobs: list[tuple[str, Path, int | None, Path, dict[str, float] | None]] = []
    for card in pool["cards"]:
        add_preview(card, args.output, "cards", str(card["card_id"]), args.repo_url, jobs)
    for rule in current_rules["rules"]:
        add_preview(rule, args.output, "rules-current", str(rule["rule_id"]), args.repo_url, jobs)
    for rule in historical_rules["rules"]:
        add_preview(
            rule, args.output, "rules-historical", str(rule["rule_id"]), args.repo_url, jobs
        )
    for disaster in disasters["cards"]:
        add_preview(
            disaster, args.output, "disasters", str(disaster["disaster_id"]), args.repo_url, jobs
        )
    for faction in factions["factions"]:
        add_preview(
            faction, args.output, "factions", str(faction["faction_id"]), args.repo_url, jobs
        )
    if not args.no_previews:

        def render(job: tuple[str, Path, int | None, Path, dict[str, float] | None]) -> None:
            kind, path, page, target, crop = job
            if kind == "image":
                render_image(path, target)
            else:
                render_pdf_page(path, int(page), target, crop)

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            list(executor.map(render, jobs))
    cache_key = str(time.time_ns())
    (args.output / "index.html").write_text(
        HTML.replace("__CACHE_KEY__", cache_key), encoding="utf-8"
    )
    (args.output / "assets/site.css").write_text(CSS + LAB_CSS + LAB_SUMMARY_CSS, encoding="utf-8")
    (args.output / "assets/app.js").write_text(
        JS.replace("__CACHE_KEY__", cache_key), encoding="utf-8"
    )
    payloads = {
        "card_pool.json": pool,
        "rules-current.json": current_rules,
        "rules-historical.json": historical_rules,
        "disasters.json": disasters,
        "factions.json": factions,
        "decks.json": decks,
        "lab.json": lab,
        "lab-sweeps.json": lab_sweeps,
    }
    for name, payload in payloads.items():
        (args.output / "data" / name).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    print(
        f"site={args.output} cards={len(pool['cards'])} rules={len(current_rules['rules'])}+{len(historical_rules['rules'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
