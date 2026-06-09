#!/usr/bin/env python3
"""
Inject huntr_scored.json into the Huntr tool (template.html) and write index.html,
defaulting the hosted page to the Live view. No manual editing of the HTML required.

template.html = your existing huntr-prototype.html, copied into the repo and renamed.
"""
import json, re

data = json.load(open("huntr_scored.json", encoding="utf-8"))

def num(x):
    return "null" if x is None else repr(round(x, 4))

lines = []
for c in data["companies"]:
    f, rr = c["factors"], c["raw"]
    F = [f.get("f_val", 50), f.get("f_own", 50), f.get("f_bs", 50), f.get("f_sz", 50)]
    R = [rr.get("mktcap_eur"), rr.get("ev_ebitda"), rr.get("ev_rev"), rr.get("nd_ebitda"), rr.get("float_pct")]
    name = c["name"].replace("\\", "\\\\").replace('"', '\\"')
    lines.append('  {n:"%s",t:"%s",r:"%s",s:"%s",F:[%s],R:[%s],c:"%s"},' % (
        name, c["ticker"], c["region"], c["subsector"],
        ",".join(str(x) for x in F), ",".join(num(x) for x in R), c["coverage"]))
block = "const LIVE_RAW = [\n" + "\n".join(lines) + "\n];"

html = open("template.html", encoding="utf-8").read()

# 1) swap in the fresh dataset
html = re.sub(r"const LIVE_RAW = \[[\s\S]*?\];", block, html, count=1)
# 2) update the retrieved timestamp shown in audit panels
html = re.sub(r'retrieved:"[^"]*"', 'retrieved:"%s"' % data["meta"]["retrieved"], html, count=1)
# 3) default the hosted page to Live
html = html.replace('dataset:"demo" };', 'dataset:"live" };')
html = html.replace('<button data-ds="demo" class="on">Demo</button><button data-ds="live">Live</button>',
                    '<button data-ds="demo">Demo</button><button data-ds="live" class="on">Live</button>')
# 4) make init use the Live dataset (and update the source pill)
html = html.replace(
    "buildFilters();\nsyncSlider();\nsyncDSlider();\nrender();",
    'if(state.dataset==="live" && typeof DATASETS!=="undefined"){ companies=DATASETS.live; reassignDeciles();'
    ' var _sp=document.getElementById("srcPill"); if(_sp){_sp.className="pill"; _sp.innerHTML=\'<span class="dot"></span> Live \\u00b7 Yahoo (Stage 1)\';} }\n'
    "buildFilters();\nsyncSlider();\nsyncDSlider();\nrender();")

open("index.html", "w", encoding="utf-8").write(html)
print("Built index.html (Live default) with", len(data["companies"]), "companies.")
