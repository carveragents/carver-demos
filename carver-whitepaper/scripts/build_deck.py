#!/usr/bin/env python3
"""
Render INTERNAL-DECK.md into a self-contained HTML slide deck.

    python3 scripts/build_deck.py experiments/INTERNAL-DECK.md experiments/INTERNAL-DECK.html

Splits the markdown on `---` slide breaks, renders each chunk with pandoc, and wraps the
result in one file with inline CSS/JS — no CDN, no build step, no server. Same doctrine as
the whitepaper itself: open the file and it works.

Navigation: arrow keys / space / PageUp-Down, click the edges, or press `o` for an overview
grid. `p` toggles a print layout that puts one slide per page, so browser "Print to PDF"
produces a deck rather than a wall of text.

Long appendix tables are allowed to scroll inside their slide on screen and to flow across
pages in print, rather than being clipped.
"""
import html
import re
import subprocess
import sys
from pathlib import Path

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#0f1115; --fg:#e8eaed; --muted:#9aa3ad; --line:#2a2f3a;
  --accent:#6ea8fe; --warn:#f0b429; --good:#5fd08a; --surface:#171a21;
}
@media (prefers-color-scheme:light){
  :root{--bg:#ffffff;--fg:#15181d;--muted:#5b6570;--line:#dfe3e8;
        --accent:#1a5fd0;--warn:#9a6700;--good:#1a7f4b;--surface:#f6f8fa}
}
html,body{margin:0;padding:0;background:var(--bg);color:var(--fg);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif}
#deck{position:relative}
.slide{
  display:none; min-height:100vh; padding:4.5vh 6vw 8vh;
  max-width:1180px; margin:0 auto; flex-direction:column; justify-content:flex-start;
}
.slide.active{display:flex}
.slide>*:first-child{margin-top:0}
h1{font-size:2.5rem;line-height:1.15;margin:.2em 0 .3em;letter-spacing:-.02em}
h2{font-size:1.9rem;line-height:1.2;margin:0 0 .6em;letter-spacing:-.015em}
h3{font-size:1.25rem;margin:1.1em 0 .4em;color:var(--accent)}
p,li{font-size:1.05rem}
li{margin:.3em 0}
strong{color:var(--fg);font-weight:650}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.9em;
  background:var(--surface);border:1px solid var(--line);border-radius:4px;padding:.08em .35em}
hr{border:0;border-top:1px solid var(--line);margin:1.2em 0}
blockquote{margin:.6em 0;padding:.3em 0 .3em 1em;border-left:3px solid var(--line);color:var(--muted)}
table{border-collapse:collapse;width:100%;margin:.7em 0;font-size:.92rem;
  display:block;overflow-x:auto;max-height:64vh}
th,td{border:1px solid var(--line);padding:.4em .6em;text-align:left;vertical-align:top}
th{background:var(--surface);font-weight:650;white-space:nowrap;position:sticky;top:0}
tbody tr:nth-child(even){background:color-mix(in srgb,var(--surface) 55%,transparent)}
td:first-child,th:first-child{white-space:nowrap}
.slide table code{background:none;border:0;padding:0}
/* chrome */
#bar{position:fixed;left:0;right:0;bottom:0;height:3px;background:var(--line);z-index:20}
#bar>i{display:block;height:100%;background:var(--accent);transition:width .18s}
#num{position:fixed;right:14px;bottom:10px;font-size:.8rem;color:var(--muted);z-index:21;
  font-variant-numeric:tabular-nums}
#hint{position:fixed;left:14px;bottom:10px;font-size:.8rem;color:var(--muted);z-index:21}
.edge{position:fixed;top:0;bottom:0;width:9vw;z-index:10;cursor:pointer}
.edge.l{left:0} .edge.r{right:0}
/* overview */
body.overview .slide{display:block;min-height:0;padding:14px 16px;border:1px solid var(--line);
  border-radius:8px;background:var(--surface);zoom:.42;cursor:pointer;margin:0}
body.overview #deck{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
  gap:10px;padding:14px}
body.overview table{max-height:none}
body.overview .edge{display:none}
/* print: one slide per page */
@media print{
  @page{size:1280px 760px;margin:14mm}
  html,body{background:#fff;color:#000}
  .slide{display:block!important;min-height:0;page-break-after:always;break-after:page;
    padding:0;max-width:none}
  .slide:last-child{page-break-after:auto}
  table{display:table;max-height:none;overflow:visible;font-size:.8rem}
  th{position:static}
  #bar,#num,#hint,.edge{display:none!important}
  h1{font-size:2rem}h2{font-size:1.5rem}p,li{font-size:.95rem}
}
body.printmode .slide{display:block;min-height:0;page-break-after:always;
  border-bottom:1px dashed var(--line);margin-bottom:18px}
body.printmode table{max-height:none}
body.printmode .edge{display:none}
"""

JS = """
const slides=[...document.querySelectorAll('.slide')];
let i=0;
const bar=document.querySelector('#bar>i'), num=document.getElementById('num');
function show(n){
  i=Math.max(0,Math.min(slides.length-1,n));
  slides.forEach((s,k)=>s.classList.toggle('active',k===i));
  bar.style.width=((i+1)/slides.length*100)+'%';
  num.textContent=(i+1)+' / '+slides.length;
  if(!document.body.classList.contains('overview'))location.hash=i+1;
}
function overview(on){
  document.body.classList.toggle('overview',on);
  if(on) slides.forEach(s=>s.classList.add('active')); else show(i);
}
addEventListener('keydown',e=>{
  if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown'){e.preventDefault();
    document.body.classList.contains('overview')?overview(false):show(i+1);}
  else if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();show(i-1);}
  else if(e.key==='Home'){show(0);} else if(e.key==='End'){show(slides.length-1);}
  else if(e.key==='o'){overview(!document.body.classList.contains('overview'));}
  else if(e.key==='p'){document.body.classList.toggle('printmode');
    slides.forEach(s=>s.classList.add('active'));}
  else if(e.key==='Escape'){overview(false);document.body.classList.remove('printmode');}
});
slides.forEach((s,k)=>s.addEventListener('click',()=>{
  if(document.body.classList.contains('overview')){i=k;overview(false);}}));
document.querySelector('.edge.l').onclick=()=>show(i-1);
document.querySelector('.edge.r').onclick=()=>show(i+1);
show(parseInt(location.hash.slice(1)||'1',10)-1);
"""


def md_to_html(chunk: str) -> str:
    """Render one slide's markdown via pandoc (gfm gives us pipe tables)."""
    return subprocess.run(
        ["pandoc", "-f", "gfm", "-t", "html5"],
        input=chunk, text=True, capture_output=True, check=True,
    ).stdout


def build(src: Path, dst: Path) -> None:
    text = src.read_text()
    # Slide breaks are `---` alone on a line. Not `***`, and not a YAML fence.
    chunks = [c.strip() for c in re.split(r"^---[ \t]*$", text, flags=re.M)]
    chunks = [c for c in chunks if c]
    body = "\n".join(f'<section class="slide">\n{md_to_html(c)}</section>' for c in chunks)
    title = "Carver vs web search vs memory — internal results"
    page = (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        '<div class="edge l"></div><div class="edge r"></div>\n'
        f'<div id="deck">\n{body}\n</div>\n'
        '<div id="bar"><i></i></div><div id="num"></div>'
        '<div id="hint">← → navigate · o overview · p print layout</div>\n'
        f"<script>{JS}</script>\n</body>\n</html>\n"
    )
    dst.write_text(page)
    print(f"{dst}  ({len(chunks)} slides, {len(page)/1024:.0f} KB)")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent.parent
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "experiments/INTERNAL-DECK.md"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else here / "experiments/INTERNAL-DECK.html"
    build(src, dst)
