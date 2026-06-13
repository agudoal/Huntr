#!/usr/bin/env python3
"""
Inject huntr_scored.json into template.html -> index.html.
Workstream A: F[6]=[f_val,f_own,f_bs,f_sz,f_sc,f_si], R[7]=[...,sc_deals,si_flags]
"""
import json, re

data = json.load(open("huntr_scored.json", encoding="utf-8"))

def num(x):
    return "null" if x is None else repr(round(float(x), 4))

def js_str(x):
    if x is None or x == "":
        return "null"
    return '"' + str(x).replace("\\","\\\\").replace('"','\\"') + '"'

lines = []
for c in data["companies"]:
    f, rr, ed = c["factors"], c["raw"], c.get("edgar", {})
    F = [f.get("f_val",50), f.get("f_own",50), f.get("f_bs",50), f.get("f_sz",50),
         f.get("f_sc",50), f.get("f_si",50)]
    R_nums = [rr.get("mktcap_eur"), rr.get("ev_ebitda"), rr.get("ev_rev"),
              rr.get("nd_ebitda"), rr.get("float_pct")]
    r_serial = (",".join(num(x) for x in R_nums) + "," + num(ed.get("sc_deals"))
                + "," + js_str(ed.get("si_flag_str")))
    name = c["name"].replace("\\","\\\\").replace('"','\\"')
    lines.append('  {n:"%s",t:"%s",r:"%s",co:"%s",s:"%s",F:[%s],R:[%s],c:"%s"},' % (
        name, c["ticker"], c["region"], c.get("country",""), c["subsector"],
        ",".join(str(x) for x in F), r_serial, c["coverage"]))

block = "const LIVE_RAW = [\n" + "\n".join(lines) + "\n];"
html  = open("template.html", encoding="utf-8").read()
html  = re.sub(r"const LIVE_RAW = \[[\s\S]*?\];", block, html, count=1)
html  = re.sub(r'retrieved:"[^"]*"', 'retrieved:"%s"' % data["meta"]["retrieved"], html, count=1)
html  = html.replace('dataset:"demo" };', 'dataset:"live" };')
html  = html.replace(
    '<button data-ds="demo" class="on">Demo</button><button data-ds="live">Live</button>',
    '<button data-ds="demo">Demo</button><button data-ds="live" class="on">Live</button>')
html  = html.replace(
    "buildFilters();\nsyncSlider();\nsyncDSlider();\nrender();",
    'if(state.dataset==="live" && typeof DATASETS!=="undefined"){companies=DATASETS.live;'
    ' reassignDeciles(); var _sp=document.getElementById("srcPill");'
    ' if(_sp){_sp.className="pill";_sp.innerHTML=liveBanner();} }'
    "\nbuildFilters();\nsyncSlider();\nsyncDSlider();\nrender();")
# Inject named-buyer lists + structured theses (insights.py output), keyed by full ticker.
buyers_map = {c["ticker"]: c.get("buyers", []) for c in data["companies"]}
thesis_map = {c["ticker"]: c.get("thesis", {}) for c in data["companies"]}
html = html.replace("const LIVE_BUYERS = {};",
                    "const LIVE_BUYERS = " + json.dumps(buyers_map, ensure_ascii=False) + ";", 1)
html = html.replace("const LIVE_THESIS = {};",
                    "const LIVE_THESIS = " + json.dumps(thesis_map, ensure_ascii=False) + ";", 1)

open("index.html","w",encoding="utf-8").write(html)
nb = sum(1 for v in buyers_map.values() if v)
print("Built index.html with", len(data["companies"]), "companies;", nb, "with named buyers + thesis.")
