# -*- coding: utf-8 -*-
import glob, re, json, warnings, os, unicodedata
import pdfplumber


def nk(x):
    return unicodedata.normalize('NFKC', x) if isinstance(x, str) else x
warnings.filterwarnings("ignore")

FILES = sorted(glob.glob('/home/claude/pdfs_all/*.pdf'))

CJK_NUM = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}


def roc_to_ad(s):
    m = re.search(r'(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日\s*至\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日', s)
    if not m:
        return "", ""
    y1, m1, d1, y2, m2, d2 = map(int, m.groups())
    return f"{y1+1911:04d}-{m1:02d}-{d1:02d}", f"{y2+1911:04d}-{m2:02d}-{d2:02d}"


def lines_of(page):
    """y-sorted logical lines, restoring visual reading order."""
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    buckets = {}
    for w in words:
        key = round(w['top'] / 1.2)
        buckets.setdefault(key, []).append(w)
    out = []
    for key in sorted(buckets):
        ws = sorted(buckets[key], key=lambda w: w['x0'])
        txt = ""
        prev = None
        for w in ws:
            if prev is not None and w['x0'] - prev > 1.6:
                txt += " "
            txt += w['text']
            prev = w['x1']
        out.append(txt.strip())
    return out


GENE_LINE = re.compile(r'^[A-Z0-9\-\+\_ \.]+$')


INSTR_KW = re.compile(
    r'System|Instrument|Sequencer|Cycler|Fluorometer|Spectrophotometer|Analyzer|'
    r'Analysis|Scanner|Platform|PCR|NGS|Electrophoresis|Machine|Reader|Oven|'
    r'Automation|Purification|Extraction|Chef|Station|Microarray|Droplet|'
    r'Mass\s*Spec|Capillary|Fragment|Thermal|Template|Slide|Multi-mode|'
    r'Temperature|Workstation|Hybridi|Centrifuge|Array|Bioanalyzer|Chip',
    re.I)


def is_instrument_line(s):
    """儀器行必須同時具備：儀器關鍵字 + 序號樣式（括號或數字）。
    如此可排除全大寫基因列與含數字的菌株/病毒名稱列。"""
    if not s or '儀器' in s or re.match(r'^附.{0,4}?表', s.replace(' ', '')):
        return False
    if not INSTR_KW.search(s):
        return False
    return bool(re.search(r'[\(（]', s) or re.search(r'\d{3,}', s))


def collapse(row):
    return [c for c in row if c not in (None, '')]


def parse(path):
    rec = {"file": os.path.basename(path)}
    with pdfplumber.open(path) as pdf:
        pages_text = []
        pages_lines = []
        tables = []
        for p in pdf.pages:
            pages_text.append(nk(p.extract_text() or ""))
            pages_lines.append([nk(x) for x in lines_of(p)])
            for t in (p.extract_tables() or []):
                tables.append([[nk(c) if c else c for c in row] for row in t])
        rec["n_pages"] = len(pdf.pages)

    full = "\n".join(pages_text)
    flat = full.replace(' ', '')
    flat1 = flat.replace('\n', '')

    m = re.search(r'機構名稱[：:]\s*([^（(\n]+)', full)
    rec["org"] = m.group(1).strip() if m else ""
    m = re.search(r'機構負責人[：:]\s*([^\s（(\n]+)', full)
    rec["org_head"] = m.group(1).strip() if m else ""
    m = re.search(r'實驗室名稱[：:]\s*([^（(\n]+)', full)
    rec["lab"] = m.group(1).strip() if m else ""
    m = re.search(r'實驗室負責人[：:]\s*([^\s（(\n]+)', full)
    rec["lab_head"] = m.group(1).strip() if m else ""
    m = re.search(r'實驗室品質主管[：:]\s*([^\s）)\n]+)', full)
    rec["qa_head"] = m.group(1).strip() if m else ""
    m = re.search(r'認證編號[：:]+\s*([A-Z]{3}\d+)', flat)
    rec["code"] = m.group(1) if m else ""
    m = re.search(r'認證有效期間[：:](.{6,80}?)止', flat1)
    period = m.group(1) if m else ""
    rec["start"], rec["end"] = roc_to_ad(period)
    m = re.search(r'FDA品字?第(\d+)號', flat1)
    rec["doc_no"] = ("FDA 品字第 " + m.group(1) + " 號") if m else ""

    # ---- 認證範圍 items
    items = []
    for t in tables:
        for row in t:
            cells = collapse(row)
            if not cells:
                continue
            if not re.fullmatch(r'\d+', (cells[0] or '').strip()):
                continue
            if len(cells) < 4:
                continue
            idx = cells[0].strip()
            rest = [re.sub(r'\s*\n\s*', '', c).strip() for c in cells[1:]]
            rest = [c for c in rest if c]
            if len(rest) < 3:
                continue
            name = rest[0]
            target = rest[1]
            tech = rest[2]
            use = rest[3] if len(rest) > 3 else ""
            if any(it["idx"] == idx and it["name"] == name for it in items):
                continue
            spec = ""
            genes = target
            mm = re.search(r'檢體型態[：:](.*?)(?:2\s*[\.、]|基因數|分析標的|$)', target)
            if mm:
                spec = mm.group(1).strip(' 。;；,')
            mm = re.search(r'(?:基因數|分析標的)[：:](.*)$', target)
            if mm:
                genes = mm.group(1).strip()
            items.append({"idx": idx, "name": name, "spec": spec,
                          "genes": genes, "raw_target": target,
                          "tech": tech, "use": use})
    items.sort(key=lambda x: int(x["idx"]))
    rec["items"] = items

    # ---- 關鍵儀器設備 per 附表
    # 附表標籤與其儀器清單在版面上是上下關係；標記字串常被逐字排版打散，
    # 因此改以「最近的上方附表編號」歸屬，並用儀器關鍵字白名單過濾基因/菌種列。
    instr = {}
    cur_tab = None
    for lines in pages_lines:
        for i, L in enumerate(lines):
            LC = L.replace(' ', '')
            mtab = re.match(r'^附.{0,4}?表\s*(\d+)', LC)
            if mtab:
                cur_tab = mtab.group(1)
                continue
            if re.match(r'^附.{0,4}?表', LC):
                m3 = re.search(r'(\d+)', LC[:10])
                if m3:
                    cur_tab = m3.group(1)
                else:
                    for k in range(i + 1, min(i + 4, len(lines))):
                        m3 = re.match(r'^(\d+)', lines[k].replace(' ', ''))
                        if m3:
                            cur_tab = m3.group(1)
                            break
                continue
            if cur_tab and is_instrument_line(L):
                instr.setdefault(cur_tab, [])
                v = L.strip('、 :：')
                if v and v not in instr[cur_tab]:
                    instr[cur_tab].append(v)
    rec["instruments"] = {k: " ".join(v) for k, v in instr.items()}
    return rec


out = []
for f in FILES:
    try:
        out.append(parse(f))
    except Exception as e:
        out.append({"file": os.path.basename(f), "error": str(e)})

json.dump(out, open('/home/claude/parsed_all.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print(f"{'code':9}{'items':>6}{'instr':>6}  lab")
tot = 0
for r in out:
    if 'error' in r:
        print("ERR", r['file'], r['error']); continue
    tot += len(r['items'])
    print(f"{r['code']:9}{len(r['items']):>6}{len(r['instruments']):>6}  {r['lab'][:24]}  {r['start']}~{r['end']}  {r['doc_no'] or 'NO-DOC'}")
print("total items:", tot)
