# -*- coding: utf-8 -*-
import json, html, re

import sys
PUBLIC = "--public" in sys.argv
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv \
      else "/mnt/user-data/outputs/Taiwan_LDTs_Labs_v4_2026-08-26.html"

D = json.load(open('/home/claude/v4dump.json', encoding='utf-8'))
ITEMS = D['認證項目明細'][1:]
LABS = D['實驗室總表v4'][1:]
PLAT = [r for r in D['平台分布'][2:] if r[0]]
AUDIT = D['名單稽核'][1:]
RULES = [r for r in D['平台序號推論規則'][2:] if r[0]]

BC = {}
for r in json.load(open('/home/claude/brandcat.json', encoding='utf-8')):
    BC[(r['code'], r['name'])] = (r['cat'], r['vendor'])

CATNAME = {"A": "原廠指名", "B": "自有品牌", "C": "泛稱描述"}


def bcat(code, name):
    c, v = BC.get((code, name), ("C 泛稱描述", ""))
    return c[0], v


items = [{
    "code": r[0], "lab": r[1], "org": r[2], "idx": r[3], "name": r[4],
    "spec": r[5], "target": r[6], "tech": r[7], "use": r[8], "instr": r[9],
    "plat": r[10], "platWhy": r[11], "platLvl": r[12], "brand": r[13],
    "brandLvl": r[14], "doc": r[15], "s": r[16], "e": r[17], "st": r[18],
    "xv": r[19], "url": r[20],
    "bc": bcat(r[0], r[4])[0], "vendor": bcat(r[0], r[4])[1],
} for r in ITEMS]

labs = [{
    "code": r[0], "lab": r[1], "org": r[2], "loc": r[3], "orgHead": r[4],
    "labHead": r[5], "qa": r[6], "s": r[7], "e": r[8], "pub": r[9], "st": r[10],
    "n": r[11], "doc": r[12], "plat": r[13], "field": r[14], "tech": r[15],
    "brand": r[16], "brandLvl": r[17], "xv": r[18], "url": r[19],
} for r in LABS]

plats = [{"name": r[0], "labs": int(r[1]), "items": int(r[2]), "codes": r[3]} for r in PLAT]
audit = [{"k": r[0], "v": r[1], "res": r[2], "note": r[3]} for r in AUDIT]
rules = [{"pat": r[0], "plat": r[1], "conf": r[2], "seen": r[3]} for r in RULES]

expired = sum(1 for l in labs if "屆滿" in str(l["st"]))
autopass = sum(1 for i in items if str(i["xv"]).startswith("通過"))
manual = sum(1 for i in items if str(i["xv"]).startswith("人工核對補齊"))
passn = autopass + manual

import collections
bcount = collections.Counter(i["bc"] for i in items)
blabs = collections.defaultdict(set)
for i in items:
    blabs[i["bc"]].add(i["code"])
vend = collections.Counter(i["vendor"] for i in items if i["vendor"])
vlab = collections.defaultdict(set)
for i in items:
    if i["vendor"]:
        vlab[i["vendor"]].add(i["code"])
vtests = collections.defaultdict(list)
for i in items:
    if i["vendor"]:
        vtests[i["vendor"]].append(f"{i['code']} {i['name']}")

# platform x brand-type cross tab
cross = collections.defaultdict(lambda: collections.Counter())
for i in items:
    ps = [p.strip() for p in str(i["plat"]).replace("非定序平台：", "").split("；")]
    for p in ps:
        if not p or "無法" in p:
            p = "無法由序號判定"
        cross[p][i["bc"]] += 1
crossrows = sorted(cross.items(), key=lambda kv: -sum(kv[1].values()))

BDESC = {
 "A": "官方檢測名稱直接寫出第三方廠牌，等同公開宣告該項目綁定特定商品化試劑或平台。",
 "B": "官方檢測名稱使用實驗室自訂產品名，代表已產品化、以自有品牌競爭；試劑來源不對外揭露。",
 "C": "官方檢測名稱為純描述性，未含任何品名，無法由名稱判斷試劑或產品定位。",
}

LABNAME = {l["code"]: l["lab"] for l in labs}


def plats_of(it):
    return [x.strip() for x in str(it["plat"]).replace("非定序平台：", "").split("；") if x.strip()]


platDetail = []
for p in plats:
    per = collections.Counter()
    for i in items:
        if p["name"] in plats_of(i):
            per[i["code"]] += 1
    bd = collections.Counter()
    for i in items:
        if p["name"] in plats_of(i):
            bd[i["bc"]] += 1
    platDetail.append({
        "name": p["name"], "labs": p["labs"], "items": p["items"],
        "A": bd["A"], "B": bd["B"], "C": bd["C"],
        "rows": [{"code": c, "lab": LABNAME.get(c, c), "n": n}
                 for c, n in sorted(per.items(), key=lambda kv: (-kv[1], kv[0]))],
    })

unkC = collections.Counter()
unkLabs = collections.Counter()
for i in items:
    if not plats_of(i) or all("無法" in x for x in plats_of(i)):
        unkC[i["bc"]] += 1
        unkLabs[i["code"]] += 1
UNK = {"name": "無法由序號判定", "labs": len(unkLabs), "items": sum(unkC.values()),
       "A": unkC["A"], "B": unkC["B"], "C": unkC["C"],
       "rows": [{"code": c, "lab": LABNAME.get(c, c), "n": n}
                for c, n in sorted(unkLabs.items(), key=lambda kv: (-kv[1], kv[0]))]}

vendorDetail = []
for v, n in vend.most_common():
    per = collections.defaultdict(list)
    for i in items:
        if i["vendor"] == v:
            per[i["code"]].append(i["name"])
    vendorDetail.append({
        "name": v, "labs": len(vlab[v]), "items": n,
        "rows": [{"code": c, "lab": LABNAME.get(c, c), "n": len(t), "tests": t}
                 for c, t in sorted(per.items(), key=lambda kv: (-len(kv[1]), kv[0]))],
    })

brandDetail = []
for k in "ABC":
    per = collections.Counter(i["code"] for i in items if i["bc"] == k)
    brandDetail.append({
        "key": k, "name": CATNAME[k], "labs": len(blabs[k]), "items": bcount[k],
        "rows": [{"code": c, "lab": LABNAME.get(c, c), "n": n}
                 for c, n in sorted(per.items(), key=lambda kv: (-kv[1], kv[0]))],
    })

PAYLOAD = json.dumps({"items": items, "labs": labs, "plats": plats,
                      "audit": audit, "rules": rules,
                      "platDetail": platDetail, "brandDetail": brandDetail, "unk": UNK,
                      "vendorDetail": vendorDetail,
                      "brandDesc": BDESC},
                     ensure_ascii=False)

CSS = """
:root{
  --ink:#101a1f; --ink-2:#3d5158; --ink-3:#6b8189;
  --paper:#f3f6f6; --card:#ffffff; --line:#dbe4e4;
  --l1:#0f6d63;      /* 第一層 原文抄錄 */
  --l2:#b4661a;      /* 第二層 本表推論 */
  --l3:#7a6f95;      /* 第三層 沿用未驗證 */
  --flag:#a8342f;
  --sans:"Noto Sans TC","PingFang TC","Microsoft JhengHei","Hiragino Sans",system-ui,sans-serif;
  --mono:"SFMono-Regular",Menlo,Consolas,"Noto Sans Mono",monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.65;font-feature-settings:"tnum" 1}
.wrap{max-width:1280px;margin:0 auto;padding:0 22px}
a{color:var(--l1)}

/* ---------- masthead ---------- */
.mast{border-bottom:1px solid var(--line);background:var(--card)}
.mast .wrap{padding-top:38px;padding-bottom:26px}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.22em;text-transform:uppercase;
  color:var(--ink-3);margin:0 0 14px}
h1{font-size:clamp(27px,4.2vw,42px);line-height:1.16;letter-spacing:-.02em;margin:0 0 6px;font-weight:800}
.sub{color:var(--ink-2);margin:0;max-width:62ch}
.figs{display:flex;flex-wrap:wrap;gap:0;margin:26px 0 0;border-top:1px solid var(--line)}
.fig{padding:14px 26px 12px 0;margin-right:26px;border-right:1px solid var(--line)}
.fig:last-child{border-right:0}
.fig b{display:block;font-size:26px;font-weight:800;letter-spacing:-.01em;line-height:1.1}
.fig span{font-size:12px;color:var(--ink-3);font-family:var(--mono);letter-spacing:.06em}

/* ---------- strata (signature) ---------- */
.strata{margin:34px 0 0}
.stratum{display:grid;grid-template-columns:6px 148px 1fr;gap:0;background:var(--card);
  border:1px solid var(--line);border-bottom:0}
.strata .stratum:last-child{border-bottom:1px solid var(--line)}
.stratum i{display:block}
.s1 i{background:var(--l1)} .s2 i{background:var(--l2)} .s3 i{background:var(--l3)}
.stratum .tag{padding:15px 16px;font-family:var(--mono);font-size:11px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--ink-3);border-right:1px solid var(--line)}
.stratum .tag b{display:block;font-family:var(--sans);font-size:14px;letter-spacing:0;
  text-transform:none;color:var(--ink);margin-top:3px;font-weight:700}
.stratum .body{padding:15px 18px;color:var(--ink-2);font-size:14px}
.stratum .body em{font-style:normal;color:var(--ink);font-weight:600}

/* ---------- sections ---------- */
section{padding:44px 0 8px}
h2{font-size:20px;letter-spacing:-.01em;margin:0 0 4px;font-weight:800}
h2 .n{font-family:var(--mono);font-size:12px;color:var(--ink-3);letter-spacing:.1em;
  font-weight:400;margin-left:10px}
.lede{color:var(--ink-2);margin:0 0 18px;max-width:74ch;font-size:14px}

/* ---------- controls ---------- */
.controls{position:sticky;top:0;z-index:20;background:var(--paper);
  padding:10px 0 12px;border-bottom:1px solid var(--line);margin-bottom:0}
.crow{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=search],select{font:inherit;font-size:13px;padding:8px 11px;border:1px solid var(--line);
  background:var(--card);color:var(--ink);border-radius:2px;min-width:0}
input[type=search]{flex:1 1 260px}
select{flex:0 1 auto;max-width:100%}
.toggle{display:inline-flex;align-items:center;gap:7px;font-size:13px;padding:8px 12px;
  border:1px solid var(--l1);background:var(--card);color:var(--l1);border-radius:2px;cursor:pointer}
.toggle[aria-pressed=true]{background:var(--l1);color:#fff}
.count{font-family:var(--mono);font-size:12px;color:var(--ink-3);margin-left:auto;white-space:nowrap}

/* ---------- item list ---------- */
.list{margin:0;padding:0;list-style:none}
.it{background:var(--card);border:1px solid var(--line);border-top:0;position:relative}
.list .it:first-child{border-top:1px solid var(--line)}
.it>button{all:unset;display:grid;grid-template-columns:6px 92px 1fr auto;gap:0;
  width:100%;cursor:pointer;box-sizing:border-box}
.it>button:focus-visible{outline:2px solid var(--l1);outline-offset:-2px}
.it .rail{background:var(--l1)}
.it .code{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);padding:13px 10px 13px 14px;
  letter-spacing:.04em;line-height:1.5}
.it .code b{display:block;color:var(--ink-2);font-weight:600}
.it .main{padding:12px 14px 13px 4px;min-width:0}
.it .nm{font-weight:650;font-size:14.5px;line-height:1.45;word-break:break-word}
.it .meta{font-size:12.5px;color:var(--ink-3);margin-top:3px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.it .chev{padding:13px 14px;color:var(--ink-3);font-family:var(--mono);font-size:12px;align-self:start}
.it[open-row] .chev{transform:rotate(90deg)}
.det{display:none;border-top:1px dashed var(--line);padding:4px 14px 16px 100px;background:#fbfcfc}
.it[open-row] .det{display:block}
.det dl{display:grid;grid-template-columns:118px 1fr;gap:0;margin:0}
.det dt{font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--ink-3);
  padding:9px 12px 9px 0;border-bottom:1px solid var(--line);text-transform:uppercase}
.det dd{margin:0;padding:9px 0;border-bottom:1px solid var(--line);font-size:13.5px;
  color:var(--ink-2);word-break:break-word}
.det dd.raw{font-family:var(--mono);font-size:11.5px;line-height:1.7;color:var(--ink-2)}
.layer{display:inline-block;font-family:var(--mono);font-size:9.5px;letter-spacing:.1em;
  padding:1px 5px;border-radius:2px;vertical-align:2px;margin-right:6px;color:#fff}
.layer.a{background:var(--l1)} .layer.b{background:var(--l2)} .layer.c{background:var(--l3)}
.pill{display:inline-block;font-size:11.5px;font-family:var(--mono);padding:1px 7px;
  border:1px solid var(--line);border-radius:2px;color:var(--ink-2);background:var(--card)}
.pill.ok{border-color:#b6d8c9;background:#eef7f3;color:#175f4c}
.pill.warn{border-color:#e7cfa0;background:#fbf4e6;color:#8a5a12}
/* brand-type marks: filled = vendor-named, outlined = self-named, plain = generic */
.bc{display:inline-block;font-style:normal;font-family:var(--mono);font-size:9.5px;letter-spacing:.09em;
  padding:1px 6px;border-radius:2px;margin-right:7px;vertical-align:1px;white-space:nowrap}
.bc.A{background:#1c4f7c;color:#fff;border:1px solid #1c4f7c}
.bc.B{background:transparent;color:#1c4f7c;border:1px solid #9cb8ce}
.bc.C{background:transparent;color:var(--ink-3);border:1px solid var(--line)}
/* platform x brand composition */
.compwrap{background:var(--card);border:1px solid var(--line)}
.comp{display:grid;grid-template-columns:minmax(0,1fr) minmax(140px,300px) 108px 56px;
  gap:16px;align-items:center;padding:9px 16px;border-bottom:1px solid var(--line)}
.compwrap .comp:last-child{border-bottom:0}
.comp-unk{background:#fafbfb}
.comp-unk .cnm{color:var(--ink-3)}
.cnm{font-size:13.5px;min-width:0;overflow-wrap:anywhere}
.cnm small{font-size:11.5px;color:var(--ink-3)}
.stack{display:flex;height:10px;background:#eef2f2;overflow:hidden}
.stack span{display:block;height:100%}
.cnum{display:grid;grid-template-columns:36px 36px 36px;font-family:var(--mono);font-size:11.5px}
.cnum i{font-style:normal;text-align:right}
.cnum .nA{color:#1c4f7c;font-weight:700}
.cnum .nB{color:#4a6f8a}
.cnum .nC{color:var(--ink-3)}
.cn{font-family:var(--mono);font-size:11px;color:var(--ink-3);text-align:right}
.compkey{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 14px;font-size:12.5px;color:var(--ink-2)}
.compkey span{display:inline-flex;align-items:center;gap:6px}
.compkey em{width:22px;height:10px;display:inline-block;font-style:normal}
.howto{background:#fff;border:1px solid var(--line);border-left:3px solid var(--l1);
  padding:11px 14px;margin:0 0 16px;font-size:13px;color:var(--ink-2)}
.howto b{color:var(--ink)}
@media (max-width:760px){
  .comp{grid-template-columns:minmax(0,1fr) auto;gap:6px}
  .comp .stack{grid-column:1/-1}
}
.xtab td.v{font-family:var(--mono);text-align:right;font-size:12.5px}
.xtab td.z{color:#c3ced1}
/* numeric columns: header and cell share one right edge, fixed width so they sit together */
.xtab{min-width:660px}
.xtab th:not(:first-child),.xtab td:not(:first-child){text-align:right;width:104px}
.xtab th:last-child,.xtab td:last-child{width:88px;background:#f7f9f9}
.xtab th:last-child{border-left:1px solid var(--line)}
.xtab td:last-child{border-left:1px solid var(--line)}
.xtab th:first-child,.xtab td:first-child{width:auto}
/* vendor roster: counts align with their headers too */
.numt th:nth-child(2),.numt th:nth-child(3),
.numt td:nth-child(2),.numt td:nth-child(3){text-align:right;width:92px}
/* lab table: 項目數 column */
.labt th:nth-child(4),.labt td:nth-child(4){text-align:right;width:74px}
.legend{display:flex;flex-wrap:wrap;gap:16px;margin:0 0 16px;font-size:12.5px;color:var(--ink-2)}
.legend span{display:inline-flex;align-items:center;gap:7px;min-width:0}
.legend .bc{flex:0 0 auto}
body.official .infer{display:none}
.notice{background:#fffaf0;border:1px solid #e7cfa0;border-left:3px solid #b4661a;
  padding:12px 15px;margin:22px 0 0;font-size:13.5px;color:#6b4a12;line-height:1.6}
.notice b{color:#4a3208}
.notice button{font:inherit;font-size:12.5px;margin-left:6px;padding:3px 10px;
  border:1px solid #b4661a;background:#fff;color:#b4661a;border-radius:2px;cursor:pointer}
.notice button:hover{background:#b4661a;color:#fff}

/* ---------- lab table ---------- */
.tw{overflow-x:auto;border:1px solid var(--line);background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:900px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-family:var(--mono);font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--ink-3);font-weight:400;background:#f7f9f9;position:sticky;top:0;z-index:2}
tbody tr:hover{background:#f7fafa}
td.c{font-family:var(--mono);font-size:11.5px;color:var(--ink-2);white-space:nowrap}
.expired{color:var(--flag);font-weight:600}

/* ---------- platform bars ---------- */
.bars{background:var(--card);border:1px solid var(--line)}
.brow{border-bottom:1px solid var(--line)}
.bars .brow:last-child{border-bottom:0}
.bar{display:grid;grid-template-columns:minmax(0,1fr) minmax(150px,300px) 46px 108px 52px 24px;
  gap:16px;align-items:center;padding:10px 16px;width:100%;
  background:none;border:0;font:inherit;color:inherit;text-align:left;cursor:pointer}
.bar:hover{background:#f7fafa}
.bar:focus-visible{outline:2px solid var(--l1);outline-offset:-2px}
.bchev{font-family:var(--mono);font-size:12px;color:var(--ink-3);justify-self:end}
.brow[open-row] .bchev{transform:rotate(90deg)}
.bdet{display:none;padding:2px 16px 14px 16px;background:#fbfcfc;border-top:1px dashed var(--line)}
.brow[open-row] .bdet{display:block}
.bdet .lrow{display:grid;grid-template-columns:78px minmax(0,1fr) 58px;gap:10px;
  padding:6px 0;border-bottom:1px solid var(--line);align-items:baseline}
.bdet .lrow:last-child{border-bottom:0}
.bdet .lc{font-family:var(--mono);font-size:11.5px;color:var(--ink-3)}
.bdet .ln{font-size:13px}
.bdet .lq{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);text-align:right}
.bdet .hint{font-size:12px;color:var(--ink-3);margin:8px 0 4px}

.bar .nm{font-size:13.5px;min-width:0;overflow-wrap:anywhere}
.bar .track{height:9px;background:#eef2f2;position:relative}
.bar .fill{height:100%;background:var(--l2)}
.bar .qty{display:grid;grid-template-columns:46px 12px 54px;align-items:baseline;
  font-family:var(--mono);font-size:11.5px;color:var(--ink-3);white-space:nowrap;width:112px}
.bar .qty i{font-style:normal;text-align:right}
.bar .qty s{text-decoration:none;text-align:center;color:#c3ced1}
.bar .track{width:100%}
@media (max-width:1024px){.bar{grid-template-columns:minmax(0,1fr) minmax(110px,200px) 44px 100px 48px 22px;gap:10px}}
.seg{display:flex;height:10px;background:#eef2f2;overflow:hidden}
.seg span{display:block;height:100%}
.segwrap{display:flex;align-items:center;width:100%}
.labq{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);text-align:right}
.brk{display:grid;grid-template-columns:34px 34px 34px;font-family:var(--mono);font-size:11.5px}
.brk i{font-style:normal;text-align:right}
.brk .nA{color:#1c4f7c;font-weight:700}
.brk .nB{color:#4a6f8a}
.brk .nC{color:var(--ink-3)}
.ntot{font-family:var(--mono);font-size:11px;color:var(--ink-3);text-align:right}
.vbar{display:grid;grid-template-columns:minmax(0,1fr) 66px 74px 24px;gap:16px;
  align-items:center;padding:11px 16px;width:100%;background:none;border:0;font:inherit;
  color:inherit;text-align:left;cursor:pointer}
.vbar:hover{background:#f7fafa}
.vbar:focus-visible{outline:2px solid var(--l1);outline-offset:-2px}
.vbar .vn{font-size:14px;font-weight:650;min-width:0;overflow-wrap:anywhere}
.vbar .vq{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);text-align:right}
.tlist{margin:2px 0 8px 0;padding:0 0 0 78px;list-style:none}
.tlist li{font-size:12.5px;color:var(--ink-2);padding:3px 0;position:relative}
.tlist li:before{content:"–";position:absolute;left:-12px;color:var(--ink-3)}
.unkrow{background:#fafbfb;border-top:2px solid var(--line)}
.unkrow .nm{color:var(--ink-3)}
.unkrow .nm small{display:block;font-size:11.5px;margin-top:1px}
.nobar{font-family:var(--mono);font-size:10.5px;color:#c3ced1}
.compkey{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 14px;font-size:12.5px;color:var(--ink-2)}
.compkey span{display:inline-flex;align-items:center;gap:6px}
.compkey em{width:22px;height:10px;display:inline-block;font-style:normal}
.howto{background:#fff;border:1px solid var(--line);border-left:3px solid var(--l1);
  padding:11px 14px;margin:0 0 16px;font-size:13px;color:var(--ink-2)}
.howto b{color:var(--ink)}

/* ---------- audit ---------- */
.aud{background:var(--card);border:1px solid var(--line)}
.arow{display:grid;grid-template-columns:170px 130px 1fr;gap:0;border-bottom:1px solid var(--line)}
.aud .arow:last-child{border-bottom:0}
.arow>div{padding:11px 14px}
.arow .k{font-weight:650;font-size:13.5px;border-right:1px solid var(--line)}
.arow .k small{display:block;font-weight:400;color:var(--ink-3);font-size:12px;margin-top:2px}
.arow .r{border-right:1px solid var(--line);font-size:12px}
.arow .nt{font-size:13px;color:var(--ink-2)}
.res{font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;padding:2px 7px;
  border-radius:2px;display:inline-block;background:#eef2f2;color:var(--ink-2)}
.res.g{background:#eef7f3;color:#175f4c}
.res.w{background:#fbf4e6;color:#8a5a12}
.res.r{background:#fbeeed;color:#8e2f2a}

footer{margin-top:52px;border-top:1px solid var(--line);background:var(--card)}
footer .wrap{padding:26px 22px 46px;color:var(--ink-3);font-size:12.5px}
footer b{color:var(--ink-2)}
/* pagination */
.pager{display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:12px 14px;
  background:var(--card);border:1px solid var(--line);border-top:0}
.pager .pinfo{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);margin-right:auto}
.pager button{font:inherit;font-family:var(--mono);font-size:12px;min-width:32px;padding:5px 9px;
  border:1px solid var(--line);background:var(--card);color:var(--ink-2);border-radius:2px;cursor:pointer}
.pager button:hover:not(:disabled){border-color:var(--l1);color:var(--l1)}
.pager button[aria-current=page]{background:var(--l1);border-color:var(--l1);color:#fff;font-weight:700}
.pager button:disabled{opacity:.35;cursor:default}
.pager .gap{font-family:var(--mono);font-size:12px;color:var(--ink-3);padding:0 2px}
.pager button:focus-visible{outline:2px solid var(--l1);outline-offset:1px}
@media (max-width:760px){.pager .pinfo{width:100%;margin-bottom:4px}}
.empty{padding:36px 16px;text-align:center;color:var(--ink-3);font-size:14px;
  background:var(--card);border:1px solid var(--line);border-top:0}

@media (max-width:760px){
  .stratum{grid-template-columns:6px 1fr}
  .stratum .tag{border-right:0;border-bottom:1px solid var(--line);padding-bottom:8px}
  .it>button{grid-template-columns:6px 1fr auto}
  .it .code{padding:11px 10px 0 14px}
  .it .main{padding:4px 14px 12px 14px}
  .det{padding-left:20px}
  .det dl{grid-template-columns:1fr}
  .det dt{border-bottom:0;padding-bottom:0}
  .arow{grid-template-columns:1fr}
  .arow .k,.arow .r{border-right:0}
  .bar{grid-template-columns:minmax(0,1fr) auto;gap:6px}
  .bar .track,.bar .segwrap{grid-column:1/-1}
  .bdet .lrow{grid-template-columns:70px minmax(0,1fr) 50px;gap:8px}
  .bar .qty{justify-self:start}
  .count{margin-left:0;width:100%}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
@media print{
  .controls,.chev,.pager,.bchev{display:none}
  .bdet{display:block!important}
  tbody tr{display:table-row!important}
  body{background:#fff}
  .det{display:block!important}
}
"""

JS = r"""
const DATA = __PAYLOAD__;
const $ = s => document.querySelector(s);
const esc = s => (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function xvClass(v){ return String(v).startsWith('通過') ? 'ok' : 'warn'; }

function row(it,i){
  const meta = [it.tech, it.spec].filter(x=>x && x!=='（見原文）').join(' · ');
  const CN={A:'原廠指名',B:'自有品牌',C:'泛稱'};
  const chip = `<span class="bc ${it.bc}">${CN[it.bc]}${it.vendor?'　'+esc(it.vendor):''}</span>`;
  return `<li class="it" data-i="${i}">
    <button type="button" aria-expanded="false">
      <span class="rail"></span>
      <span class="code">${esc(it.code)}<b>#${esc(it.idx)}</b></span>
      <span class="main">
        <span class="nm">${chip}${esc(it.name)}</span>
        <span class="meta">${esc(it.lab)}${meta?' — '+esc(meta):''}</span>
      </span>
      <span class="chev">▸</span>
    </button>
    <div class="det">
      <dl>
        <dt>檢體型態</dt><dd>${esc(it.spec)}</dd>
        <dt>分析標的</dt><dd>${esc(it.target)}</dd>
        <dt>檢測項目</dt><dd>${esc(it.use)}</dd>
        <dt>關鍵儀器</dt><dd class="raw">${esc(it.instr)}</dd>
        <dt>序號驗證</dt><dd><span class="pill ${xvClass(it.xv)}">${esc(it.xv)}</span></dd>
        <dt class="infer">平台推論</dt><dd class="infer"><span class="layer b">第二層 推論</span>${esc(it.plat)}
          <br><small style="color:var(--ink-3)">${esc(it.platWhy)}｜信心 ${esc(it.platLvl)}</small></dd>
        <dt>品牌型態</dt><dd><span class="bc ${it.bc}">${CN[it.bc]}</span>
          ${it.vendor?esc(it.vendor)+'　<small style="color:var(--ink-3)">（廠牌名稱直接出現在官方檢測名稱中）</small>'
            :(it.bc==='B'?'實驗室自有產品命名　<small style="color:var(--ink-3)">（品名見官方檢測名稱，非試劑廠牌）</small>'
                        :'官方檢測名稱為泛稱描述，未含任何品名')}</dd>
        <dt>試劑貨號</dt><dd>未公開　<small style="color:var(--ink-3)">認證附件體例不列試劑品牌與 kit 貨號</small></dd>
        <dt>附件文號</dt><dd>${esc(it.doc)} · 效期 ${esc(it.s)} ～ ${esc(it.e)}
          ${String(it.st).includes('屆滿')?' <span class="pill warn">'+esc(it.st)+'</span>':''}
          <br><a href="${esc(it.url)}" target="_blank" rel="noopener">開啟食藥署認證附件 ↗</a></dd>
      </dl>
    </div>
  </li>`;
}

const PER = 20;
let view = DATA.items.slice();
let page = 1, labPage = 1;

function pagerHTML(cur, total, from, to, n, unit){
  if(total <= 1) return `<div class="pager"><span class="pinfo">共 ${n} ${unit}</span></div>`;
  const nums = [];
  const push = p => nums.push(
    `<button type="button" data-p="${p}"${p===cur?' aria-current="page"':''} aria-label="第 ${p} 頁">${p}</button>`);
  const gap = () => nums.push('<span class="gap">…</span>');
  push(1);
  let lo = Math.max(2, cur-1), hi = Math.min(total-1, cur+1);
  if(lo > 2) gap();
  for(let p=lo; p<=hi; p++) push(p);
  if(hi < total-1) gap();
  if(total > 1) push(total);
  return `<div class="pager">
    <span class="pinfo">第 ${from}–${to} ${unit}，共 ${n} ${unit}　·　${cur} / ${total} 頁</span>
    <button type="button" data-p="${cur-1}" ${cur===1?'disabled':''} aria-label="上一頁">‹ 上一頁</button>
    ${nums.join('')}
    <button type="button" data-p="${cur+1}" ${cur===total?'disabled':''} aria-label="下一頁">下一頁 ›</button>
  </div>`;
}

function render(){
  const q = $('#q').value.trim().toLowerCase();
  const lab = $('#fLab').value, tech = $('#fTech').value, plat = $('#fPlat').value,
        bc = $('#fBc').value;
  view = DATA.items.filter(it=>{
    if(lab && it.code!==lab) return false;
    if(tech && it.tech!==tech) return false;
    if(plat && !String(it.plat).includes(plat)) return false;
    if(bc && it.bc!==bc) return false;
    if(q){
      const hay = [it.code,it.lab,it.org,it.name,it.spec,it.target,it.tech,it.use,it.brand,it.plat,it.doc]
        .join(' ').toLowerCase();
      if(!hay.includes(q)) return false;
    }
    return true;
  });
  const total = Math.max(1, Math.ceil(view.length / PER));
  if(page > total) page = total;
  if(page < 1) page = 1;
  const from = (page-1)*PER, slice = view.slice(from, from+PER);
  $('#list').innerHTML = slice.map(row).join('');
  $('#empty').hidden = view.length>0;
  $('#pager').innerHTML = view.length
    ? pagerHTML(page, total, from+1, from+slice.length, view.length, '項') : '';
  const labN = new Set(view.map(v=>v.code)).size;
  $('#count').textContent = `顯示 ${view.length} / ${DATA.items.length} 項　·　${labN} 家實驗室`;
}

function bind(){
  $('#list').addEventListener('click', e=>{
    const b = e.target.closest('button'); if(!b) return;
    const li = b.parentElement;
    const open = li.hasAttribute('open-row');
    if(open){ li.removeAttribute('open-row'); b.setAttribute('aria-expanded','false'); }
    else { li.setAttribute('open-row',''); b.setAttribute('aria-expanded','true'); }
  });
  const refilter = () => { page = 1; render(); };
  ['#q','#fLab','#fTech','#fPlat','#fBc'].forEach(s=>{
    $(s).addEventListener('input', refilter);
    $(s).addEventListener('change', refilter);
  });
  $('#pager').addEventListener('click', e=>{
    const b = e.target.closest('button[data-p]'); if(!b || b.disabled) return;
    page = +b.dataset.p; render();
    $('#items').scrollIntoView({behavior:'smooth', block:'start'});
  });
  $('#labPager').addEventListener('click', e=>{
    const b = e.target.closest('button[data-p]'); if(!b || b.disabled) return;
    labPage = +b.dataset.p; renderLabs();
    $('#labs').scrollIntoView({behavior:'smooth', block:'start'});
  });
  $('#reset').addEventListener('click', ()=>{
    $('#q').value=''; $('#fLab').value=''; $('#fTech').value=''; $('#fPlat').value=''; $('#fBc').value=''; page=1; render();
  });
  const t = $('#official');
  const setMode = hide => {
    t.setAttribute('aria-pressed', String(hide));
    document.body.classList.toggle('official', hide);
    t.querySelector('span').textContent = hide ? '顯示推論欄位' : '隱去推論欄位';
    if(hide && $('#fPlat').value){ $('#fPlat').value=''; page=1; render(); }
  };
  t.addEventListener('click', ()=> setMode(t.getAttribute('aria-pressed')!=='true'));
  const rv = document.querySelector('#reveal');
  if(rv) rv.addEventListener('click', ()=> setMode(false));
  setMode(document.body.classList.contains('official'));
}

const CATN = {A:'原廠指名', B:'自有品牌', C:'泛稱描述'};

function barBlock(id, rows, maxv, colorOf){
  document.querySelector(id).innerHTML = rows.map((r,i)=>{
    const w = (r.labs/maxv*100).toFixed(1);
    const label = r.key
      ? `<span class="bc ${r.key}">${esc(r.name)}</span>${esc(DATA.brandDesc[r.key])}`
      : esc(r.name);
    return `<div class="brow" data-i="${i}">
      <button type="button" class="bar" aria-expanded="false">
        <span class="nm">${label}</span>
        <span class="track"><span class="fill" style="width:${w}%;background:${colorOf(r)}"></span></span>
        <span class="qty"><i>${r.labs} 家</i><s>/</s><i>${r.items} 項</i></span>
        <span class="bchev">▸</span>
      </button>
      <div class="bdet">
        <p class="hint">推論使用此${r.key?'品牌型態':'平台'}的實驗室，依認證項目數排序：</p>
        ${r.rows.map(x=>`<div class="lrow"><span class="lc">${esc(x.code)}</span>
          <span class="ln">${esc(x.lab)}</span><span class="lq">${x.n} 項</span></div>`).join('')}
      </div>
    </div>`;
  }).join('');
  document.querySelector(id).addEventListener('click', e=>{
    const b = e.target.closest('button.bar'); if(!b) return;
    const row = b.parentElement, on = row.hasAttribute('open-row');
    if(on){ row.removeAttribute('open-row'); b.setAttribute('aria-expanded','false'); }
    else { row.setAttribute('open-row',''); b.setAttribute('aria-expanded','true'); }
  });
}

const BCOL = {A:'#1c4f7c', B:'#7ba0bd', C:'#d5dcdf'};

function platBlock(){
  const max = Math.max(...DATA.platDetail.map(p=>p.items));
  const draw = (r, isUnk) => {
    const seg = isUnk ? `<span class="nobar">不列入比較</span>`
      : `<span class="segwrap"><span class="seg" style="width:${(r.items/max*100).toFixed(2)}%">`
        + ['A','B','C'].filter(k=>r[k]).map(k=>
            `<span style="width:${(r[k]/r.items*100).toFixed(2)}%;background:${BCOL[k]}"
             title="${CATN[k]} ${r[k]} 項"></span>`).join('')
        + `</span></span>`;
    const nm = isUnk
      ? `${esc(r.name)}<small>非平台，僅表示序號不符合任何已知編碼慣例</small>`
      : esc(r.name);
    return `<div class="brow${isUnk?' unkrow':''}">
      <button type="button" class="bar" aria-expanded="false">
        <span class="nm">${nm}</span>
        ${seg}
        <span class="labq">${r.labs} 家</span>
        <span class="brk"><i class="nA">${r.A||'·'}</i><i class="nB">${r.B||'·'}</i><i class="nC">${r.C||'·'}</i></span>
        <span class="ntot">n=${r.items}</span>
        <span class="bchev">▸</span>
      </button>
      <div class="bdet">
        <p class="hint">${isUnk?'序號無法辨識平台的項目分布':'推論使用此平台的實驗室'}，依認證項目數排序：</p>
        ${r.rows.map(x=>`<div class="lrow"><span class="lc">${esc(x.code)}</span>
          <span class="ln">${esc(x.lab)}</span><span class="lq">${x.n} 項</span></div>`).join('')}
      </div></div>`;
  };
  document.querySelector('#platBars').innerHTML =
    DATA.platDetail.map(r=>draw(r,false)).join('') + draw(DATA.unk, true);
  document.querySelector('#platBars').addEventListener('click', e=>{
    const b = e.target.closest('button.bar'); if(!b) return;
    const row = b.parentElement, on = row.hasAttribute('open-row');
    if(on){ row.removeAttribute('open-row'); b.setAttribute('aria-expanded','false'); }
    else { row.setAttribute('open-row',''); b.setAttribute('aria-expanded','true'); }
  });
}

function vendBlock(){
  document.querySelector('#vendBars').innerHTML = DATA.vendorDetail.map(v=>`
    <div class="brow">
      <button type="button" class="vbar" aria-expanded="false">
        <span class="vn">${esc(v.name)}</span>
        <span class="vq">${v.labs} 家</span>
        <span class="vq">${v.items} 項</span>
        <span class="bchev">▸</span>
      </button>
      <div class="bdet">
        <p class="hint">在官方檢測名稱中指名此廠牌的實驗室：</p>
        ${v.rows.map(x=>`<div class="lrow"><span class="lc">${esc(x.code)}</span>
            <span class="ln">${esc(x.lab)}</span><span class="lq">${x.n} 項</span></div>
          <ul class="tlist">${x.tests.map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`).join('')}
      </div>
    </div>`).join('');
  document.querySelector('#vendBars').addEventListener('click', e=>{
    const b = e.target.closest('button.vbar'); if(!b) return;
    const row = b.parentElement, on = row.hasAttribute('open-row');
    if(on){ row.removeAttribute('open-row'); b.setAttribute('aria-expanded','false'); }
    else { row.setAttribute('open-row',''); b.setAttribute('aria-expanded','true'); }
  });
}

function bars(){
  platBlock();
  vendBlock();
  const bmax = Math.max(...DATA.brandDetail.map(b=>b.labs));
  barBlock('#brandBars', DATA.brandDetail, bmax,
    r => r.key==='A' ? '#1c4f7c' : (r.key==='B' ? '#7ba0bd' : '#c3ced1'));
}

function fill(){
  const labs = [...new Map(DATA.items.map(i=>[i.code, i.lab])).entries()]
    .sort((a,b)=>a[0]<b[0]?-1:1);
  $('#fLab').insertAdjacentHTML('beforeend',
    labs.map(([c,n])=>`<option value="${esc(c)}">${esc(c)}　${esc(n)}</option>`).join(''));
  const techs=[...new Set(DATA.items.map(i=>i.tech))].filter(Boolean).sort();
  $('#fTech').insertAdjacentHTML('beforeend',
    techs.map(t=>`<option value="${esc(t)}">${esc(t)}</option>`).join(''));
  $('#fPlat').insertAdjacentHTML('beforeend',
    DATA.plats.map(p=>`<option value="${esc(p.name)}">${esc(p.name)}（${p.labs} 家）</option>`).join(''));
}

function renderLabs(){
  const rows = [...document.querySelectorAll('#labBody tr')];
  const total = Math.max(1, Math.ceil(rows.length / PER));
  if(labPage > total) labPage = total;
  const from = (labPage-1)*PER;
  rows.forEach((tr,i)=>{ tr.style.display = (i>=from && i<from+PER) ? '' : 'none'; });
  $('#labPager').innerHTML =
    pagerHTML(labPage, total, from+1, Math.min(from+PER, rows.length), rows.length, '家');
}

fill(); bind(); bars(); render(); renderLabs();
"""


def res_class(t):
    t = str(t)
    if any(k in t for k in ("相符", "全數", "全對", "完成", "通過", "已修正", "已處理", "正確")):
        return "g"
    if any(k in t for k in ("誤植", "未擷取", "需追蹤", "續證中")):
        return "r"
    return "w"


maxlabs = max(p["labs"] for p in plats)

BLABEL = {"A": "A　原廠指名", "B": "B　自有品牌", "C": "C　泛稱描述"}


vend_rows = "".join(
    f"<tr><td><b>{html.escape(v)}</b></td><td class='c'>{len(vlab[v])}</td><td class='c'>{n}</td>"
    f"<td>{html.escape('；'.join(vtests[v]))}</td></tr>"
    for v, n in vend.most_common())


lab_rows = "".join(
    f"<tr><td class='c'>{html.escape(str(l['code']))}</td>"
    f"<td>{html.escape(str(l['lab']))}<br><small style='color:var(--ink-3)'>{html.escape(str(l['org']))}</small></td>"
    f"<td class='c'>{html.escape(str(l['loc']))}</td>"
    f"<td class='c'>{l['n']}</td>"
    f"<td class='c'>{html.escape(str(l['s']))}<br>{html.escape(str(l['e']))}"
    + ("<br><span class='expired'>已屆滿</span>" if "屆滿" in str(l['st']) else "") + "</td>"
    f"<td class='c'>{html.escape(str(l['doc']))}</td>"
    f"<td class='infer'>{html.escape(str(l['plat']))}</td>"
    f"<td class='c'>{html.escape(str(l['xv']))}</td>"
    f"<td class='c'><a href='{html.escape(str(l['url']))}' target='_blank' rel='noopener'>附件 ↗</a></td></tr>"
    for l in labs)



audit_rows = "".join(
    f"<div class='arow'><div class='k'>{html.escape(str(a['k']))}<small>{html.escape(str(a['v']))}</small></div>"
    f"<div class='r'><span class='res {res_class(a['res'])}'>{html.escape(str(a['res']))}</span></div>"
    f"<div class='nt'>{html.escape(str(a['note']))}</div></div>"
    for a in audit)

rule_rows = "".join(
    f"<tr><td class='c'>{html.escape(str(r['pat']))}</td><td>{html.escape(str(r['plat']))}</td>"
    f"<td class='c'>{html.escape(str(r['conf']))}</td><td class='c'>{html.escape(str(r['seen']))}</td></tr>"
    for r in rules)

brand_a = bcount["A"]
multi_n = sum(1 for i in items if len([p for p in plats_of(i) if "無法" not in p]) > 1)
unk_n, unk_c = UNK["items"], UNK["C"]

NOTICE = ("""<div class="notice"><b>此版本預設隱藏「平台推論」相關內容。</b>
  平台是由認證附件的儀器序號反推得出，屬本表推論、非食藥署官方標示，也未經原廠或各實驗室確認。
  為避免被誤讀為官方事實，公開版預設不顯示；如需檢視，可
  <button type="button" id="reveal">顯示推論欄位</button>
  （或使用下方「認證項目明細」的同名按鈕隨時切換）。
  隱藏不影響第一層原文資料，198 個認證項目與全部官方欄位皆完整呈現。</div>"""
          if PUBLIC else "")

L2NOTE = ("　<em>本版本預設隱藏此層。</em>" if PUBLIC else "")

HTML = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>台灣 LDTs 精準醫療分子檢測實驗室認證總覽｜2026-08-26</title>
<style>{CSS}</style>
</head>
<body{{BODYCLASS}}>

<header class="mast">
  <div class="wrap">
    <p class="eyebrow">衛福部食藥署　特管辦法　實驗室開發檢測認證</p>
    <h1>台灣 LDTs 認證實驗室總覽</h1>
    <p class="sub">32 家經認證實驗室、{len(items)} 個認證檢測項目，逐項展開。全數取自食藥署認證附件原檔，
    並以第二套 PDF 引擎交叉驗證序號：{autopass} 列自動驗證通過，{manual} 列因附表逐字錯位改以原檔人工核對補齊。
    資料基準日 2026-08-26。</p>
    <div class="figs">
      <div class="fig"><b>32</b><span>認證實驗室</span></div>
      <div class="fig"><b>{len(items)}</b><span>認證檢測項目</span></div>
      <div class="fig"><b>{passn}/{len(items)}</b><span>序號驗證完成（{manual} 列人工補齊）</span></div>
      <div class="fig"><b>{expired}</b><span>效期已屆滿仍列名</span></div>
    </div>
    {{NOTICE}}
  </div>
</header>

<div class="wrap">

<section>
  <h2>先讀這個：三層資料性質</h2>
  <p class="lede">這份表裡的欄位不是同一種東西。引用之前請先確認你看的是哪一層——
  這關係到能不能直接對外使用。</p>
  <div class="strata">
    <div class="stratum s1"><i></i>
      <div class="tag">Layer 01<b>原文抄錄</b></div>
      <div class="body">認證編號、效期、文號、檢測名稱、檢體型態、基因數、檢測技術、用途、儀器序號，以及由檢測名稱直接判定的品牌型態。
      <em>來自官方原檔，並經雙引擎交叉驗證，可直接引用。</em>
      但請注意：官方文件本身也有誤植（見稽核紀錄）。</div>
    </div>
    <div class="stratum s2"><i></i>
      <div class="tag">Layer 02<b>本表推論</b></div>
      <div class="body">定序平台推論與平台分布統計。
      <em>認證附件只列儀器序號、不列廠牌型號</em>，此欄由序號慣例反推，非官方資料，也未經原廠文件驗證。
      對外引用務必註明為推論，且不得再由平台往下推導試劑品牌。{{L2NOTE}}</div>
    </div>
    <div class="stratum s3"><i></i>
      <div class="tag">Layer 03<b>沿用未驗證</b></div>
      <div class="body">所在地、領域、主要技術，以及「中」等級的試劑品牌線索。
      <em>沿用第一版整理，未重新核對原檔。</em>用於分類與檢索足夠，不宜作為對外論述依據。</div>
    </div>
  </div>
</section>

<section id="items">
  <h2>認證項目明細<span class="n">{len(items)} 項</span></h2>
  <p class="lede">每頁 20 項。點任一列展開檢體、標的、關鍵儀器原文、平台推論與附件連結。</p>
  <div class="controls">
    <div class="crow">
      <input id="q" type="search" placeholder="搜尋檢測名稱、實驗室、基因、文號…" aria-label="搜尋">
      <select id="fLab" aria-label="篩選實驗室"><option value="">全部實驗室</option></select>
      <select id="fTech" aria-label="篩選檢測技術"><option value="">全部技術</option></select>
      <select id="fPlat" class="infer" aria-label="篩選平台"><option value="">全部平台（推論）</option></select>
      <select id="fBc" aria-label="篩選品牌型態"><option value="">全部品牌型態</option>
        <option value="A">A 原廠指名</option><option value="B">B 自有品牌</option>
        <option value="C">C 泛稱描述</option></select>
      <button class="toggle" id="official" type="button" aria-pressed="false">
        <span>只看官方原文</span></button>
      <button class="toggle" id="reset" type="button" style="border-color:var(--line);color:var(--ink-2)">清除</button>
      <span class="count" id="count"></span>
    </div>
  </div>
  <ul class="list" id="list"></ul>
  <div class="empty" id="empty" hidden>沒有符合的項目。調整關鍵字或清除篩選再試一次。</div>
  <div id="pager"></div>
</section>

<section id="labs">
  <h2>實驗室總表<span class="n">32 家</span></h2>
  <p class="lede">依認證起日新到舊排列，每頁 20 家。「序號驗證」為該家所有項目中通過交叉驗證的比例。</p>
  <div class="tw"><table class="labt">
    <thead><tr><th>編號</th><th>實驗室 / 機構</th><th>所在地</th><th>項目數</th><th>效期</th>
    <th>附件文號</th><th class="infer">定序平台（推論）</th><th>序號驗證</th><th>原檔</th></tr></thead>
    <tbody id="labBody">{lab_rows}</tbody>
  </table></div>
  <div id="labPager"></div>
</section>

<section class="infer">
  <h2>平台分布與品牌組成<span class="n">第二層　推論</span></h2>
  <p class="lede">平台由關鍵儀器設備序號反推，非食藥署官方標示。
  <b>橫條長度代表該平台的認證項目數，列與列之間可直接比較</b>；條內的深淺分段是品牌組成。
  點任一列展開實驗室名單與各自的項目數。</p>
  <div class="compkey">
    <span><em style="background:#1c4f7c"></em>A 原廠指名</span>
    <span><em style="background:#7ba0bd"></em>B 自有品牌</span>
    <span><em style="background:#d5dcdf"></em>C 泛稱描述</span>
    <span style="color:var(--ink-3)">家數 ｜ A / B / C 項數 ｜ n = 該平台項目數</span>
  </div>
  <div class="bars" id="platBars"></div>
  <p class="lede" style="margin-top:14px;font-size:13px">
  <b>兩個必須知道的限制。</b>其一，同一個認證項目若同時用到多個平台，會在多列各出現一次（共 {multi_n} 項如此），
  因此 n 值與家數縱向加總都會大於實際總數（{len(items)} 項、32 家）。橫列可讀，縱欄不可加總。
  其二，最後一列「無法由序號判定」不是平台，只表示儀器序號不符合任何已知編碼慣例，
  故不繪製橫條、不列入長度比較；該群共 {unk_n} 項，其中 {unk_c} 項同時也是泛稱描述——多為單基因 qPCR 或 Sanger 檢測，
  既無平台辨識度也無品牌辨識度。</p>
</section>

<section>
  <h2>檢測品牌結構<span class="n">第一層　原文</span></h2>
  <p class="lede">認證附件不列試劑廠牌與 kit 貨號，因此「用了什麼試劑」在官方文件裡幾乎不存在——
  198 個項目中只有 {brand_a} 項的官方檢測名稱直接寫出第三方廠牌。但檢測名稱本身 100% 可讀，
  據此可分出三種品牌揭露型態，這是唯一能與平台分析對等、且全數來自原文的品牌維度。</p>
  <div class="legend">
    <span><i class="bc A">原廠指名</i>廠牌寫在官方檢測名稱裡</span>
    <span><i class="bc B">自有品牌</i>實驗室自訂產品名</span>
    <span><i class="bc C">泛稱</i>純描述性名稱</span>
  </div>
  <div class="bars" id="brandBars"></div>
</section>

<section>
  <h2>原廠指名名冊<span class="n">{brand_a} 項　5 家</span></h2>
  <p class="lede">這是全台 LDTs 認證項目中，唯一能在官方文件層級確認商品化試劑或平台廠牌的清單。
  其餘 191 項的試劑來源在認證文件中不可考。點任一列展開，可看到是哪幾家實驗室、指名在哪些認證項目上。</p>
  <div class="bars" id="vendBars"></div>
</section>



<section>
  <h2>名單稽核紀錄<span class="n">{len(audit)} 項</span></h2>
  <p class="lede">包含核對結果、官方文件本身的瑕疵，以及本次未能取得的資料與原因。</p>
  <div class="aud">{audit_rows}</div>
</section>

<section class="infer">
  <h2>平台序號推論規則<span class="n">第二層　推論</span></h2>
  <p class="lede">這是第二層資料的推導依據，公開出來供你自行判斷可信度。規則來自各廠牌序號慣例，未經原廠文件驗證。</p>
  <div class="tw"><table>
    <thead><tr><th>序號 / 名稱樣式</th><th>推論平台或儀器</th><th>信心</th><th>出現於</th></tr></thead>
    <tbody>{rule_rows}</tbody>
  </table></div>
</section>

</div>

<footer><div class="wrap">
  <p><b>資料來源</b>　衛生福利部食品藥物管理署「精準醫療分子檢測實驗室認證名單」
  <a href="https://www.fda.gov.tw/TC/siteList.aspx?sid=12204" target="_blank" rel="noopener">sid=12204</a>
  ，以及各家認證附件 PDF 原檔。資料基準日 2026-08-26。</p>
  <p><b>法規依據</b>　《特定醫療技術檢查檢驗醫療儀器施行或使用管理辦法》。衛福部自 2022-01-17 委任食藥署辦理實驗室認證及查核。
  食藥署另有「列冊登錄（LDTS）」名單（sid=12206），係 2018 年指引下的自願性列冊，與本認證名單不同，請勿混用。</p>
  <p><b>維護</b>　每季重新比對官網名單；附件文號改變即代表認證範圍可能異動，需重新解析該家 PDF。
  目前追蹤中：LDT0001 行動基因續證狀態（文號仍為 1150017903）。</p>
</div></footer>

<script>{JS.replace('__PAYLOAD__', PAYLOAD)}</script>
</body>
</html>
"""

HTML = (HTML.replace("{BODYCLASS}", ' class="official"' if PUBLIC else "")
            .replace("{NOTICE}", NOTICE)
            .replace("{L2NOTE}", L2NOTE))
open(OUT, 'w', encoding='utf-8').write(HTML)
print(("public " if PUBLIC else "internal ") + OUT, "| bytes:", len(HTML),
      "items:", len(items), "labs:", len(labs), "plats:", len(plats))
