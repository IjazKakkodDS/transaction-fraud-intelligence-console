#!/usr/bin/env python3
"""
Architecture diagram generator — Real-Time Transaction Fraud Intelligence Console.
Produces 6 production SVG diagrams in docs/architecture/.
Run from the repository root: python docs/architecture/source/generate_svgs.py

Vertical layout contract (all diagrams):
  0–46      main title band
  58        first zone top (12px clearance under title band)
  zone top + 0–30    reserved heading band (label baseline at zone top + 19)
  zone top + 30      first node row
  zone bottom − 12   content bottom padding
  canvas H − 16      last content bottom margin
"""

import os, pathlib

OUT = pathlib.Path("docs/architecture")
F   = "'Segoe UI','Helvetica Neue',Arial,sans-serif"
ARR = "#475569"
BG  = "#F8FAFC"
BD  = "#CBD5E1"
TBG = "#0F172A"

P = {
    "experience": ("#BFDBFE","#2563EB","#1E3A8A"),
    "service":    ("#DDD6FE","#7C3AED","#3B0764"),
    "model":      ("#FECACA","#DC2626","#7F1D1D"),
    "rule":       ("#FED7AA","#EA580C","#7C2D12"),
    "behav":      ("#FEF9C3","#A16207","#713F12"),
    "graph":      ("#DCFCE7","#16A34A","#14532D"),
    "data":       ("#BBF7D0","#059669","#064E3B"),
    "ops":        ("#FDE68A","#D97706","#451A03"),
    "portfolio":  ("#A5F3FC","#0891B2","#083344"),
    "audit":      ("#E9D5FF","#9333EA","#3B0764"),
    "workflow":   ("#FBCFE8","#DB2777","#831843"),
    "fusion":     ("#E2E8F0","#475569","#0F172A"),
    "disabled":   ("#E5E7EB","#9CA3AF","#6B7280"),
    "ai":         ("#FEE2E2","#B91C1C","#7F1D1D"),
    "input":      ("#DBEAFE","#1D4ED8","#1E40AF"),
    "output":     ("#D1FAE5","#059669","#064E3B"),
}

def xe(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def hdr(w,h,title,desc):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">\n'
            f'  <title>{xe(title)}</title>\n'
            f'  <desc>{xe(desc)}</desc>\n'
            f'  <defs>\n'
            f'    <marker id="ah" viewBox="0 0 10 10" refX="9" refY="5"\n'
            f'            markerWidth="6" markerHeight="6" orient="auto">\n'
            f'      <polygon points="0,0 10,5 0,10" fill="{ARR}"/>\n'
            f'    </marker>\n'
            f'  </defs>\n'
            f'  <rect width="{w}" height="{h}" rx="8" fill="{BG}" stroke="{BD}" stroke-width="1.5"/>\n'
            f'  <rect x="0" y="0" width="{w}" height="46" rx="8" fill="{TBG}"/>\n'
            f'  <rect x="0" y="34" width="{w}" height="12" fill="{TBG}"/>\n'
            f'  <text x="{w//2}" y="30" text-anchor="middle" font-family="{F}" '
            f'font-size="20" font-weight="700" fill="#F1F5F9">{xe(title)}</text>\n')

def nd(x,y,w,h,label,sub="",sty="fusion",rx=6):
    f_,s_,t_ = P[sty]
    o = f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{f_}" stroke="{s_}" stroke-width="1.5"/>\n'
    if sub:
        o += (f'  <text x="{x+w//2}" y="{y+h//2-5}" text-anchor="middle" '
              f'font-family="{F}" font-size="14" font-weight="600" fill="{t_}">{xe(label)}</text>\n'
              f'  <text x="{x+w//2}" y="{y+h//2+11}" text-anchor="middle" '
              f'font-family="{F}" font-size="11" fill="{t_}" opacity="0.85">{xe(sub)}</text>\n')
    else:
        o += (f'  <text x="{x+w//2}" y="{y+h//2+5}" text-anchor="middle" '
              f'font-family="{F}" font-size="14" font-weight="600" fill="{t_}">{xe(label)}</text>\n')
    return o

def zl(x,y,label,col="#64748B"):
    return (f'  <text x="{x}" y="{y}" font-family="{F}" font-size="10" font-weight="700" '
            f'fill="{col}" letter-spacing="1.4">{xe(label.upper())}</text>\n')

def ln(x1,y1,x2,y2,dash=False):
    d = ' stroke-dasharray="6,3"' if dash else ''
    return f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{ARR}" stroke-width="2"{d} marker-end="url(#ah)"/>\n'

def pa(d,dash=False):
    da = ' stroke-dasharray="6,3"' if dash else ''
    return f'  <path d="{d}" stroke="{ARR}" stroke-width="2" fill="none"{da} marker-end="url(#ah)"/>\n'

def qbez(x1,y1,cx,cy,x2,y2,dash=False):
    return pa(f"M{x1},{y1} Q{cx},{cy} {x2},{y2}",dash)

def cbez(x1,y1,cx1,cy1,cx2,cy2,x2,y2,dash=False):
    return pa(f"M{x1},{y1} C{cx1},{cy1} {cx2},{cy2} {x2},{y2}",dash)

def divline(y,w=1400):
    return f'  <line x1="20" y1="{y}" x2="{w-20}" y2="{y}" stroke="#E2E8F0" stroke-width="1" stroke-dasharray="3,4"/>\n'

def badge(x,y,w,h,label,col):
    return (f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{col}" opacity="0.18" stroke="{col}" stroke-width="1.2"/>\n'
            f'  <text x="{x+w//2}" y="{y+h//2+4}" text-anchor="middle" font-family="{F}" '
            f'font-size="11" font-weight="700" fill="{col}">{xe(label)}</text>\n')

def ftr(): return '</svg>\n'

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 1 — System at a Glance
# ─────────────────────────────────────────────────────────────────────────────
def d1():
    W,H = 1400,758
    o = hdr(W,H,"System at a Glance",
            "Complete product architecture: analyst console, FastAPI, hybrid scoring, case store, analyst operations, and portfolio scan.")

    # ── zone backgrounds ──────────────────────────────────────────────────────
    zones = [
        (10,58,1380,100,"#EFF6FF","EXPERIENCE LAYER","#1D4ED8"),
        (10,168,1380,100,"#F5F3FF","SERVICE LAYER","#6D28D9"),
        (10,278,1380,186,"#FFF1F2","DECISION INTELLIGENCE","#BE123C"),
        (10,474,1380,100,"#F0FDF4","DATA & PERSISTENCE LAYER","#15803D"),
        (10,584,1380,158,"#FFFBEB","ANALYST OPERATIONS","#B45309"),
    ]
    for zx,zy,zw,zh,zc,zl_,zcol in zones:
        o += f'  <rect x="{zx}" y="{zy}" width="{zw}" height="{zh}" rx="4" fill="{zc}"/>\n'
        o += zl(zx+10,zy+19,zl_,zcol)

    # ── nodes ─────────────────────────────────────────────────────────────────
    # Experience
    o += nd(480,88,440,58,"Analyst Console","Next.js 16 · 8 routes","experience")

    # Service
    o += nd(430,198,540,58,"FastAPI REST API","27 endpoints · scoring · cases · scan · workflow","service")

    # Intelligence — 4 nodes, width 290, x = 10 / 373 / 736 / 1099 (73px gaps)
    intel = [
        (10, "Model Risk","XGBoost · weight 0.6","model"),
        (373,"Rule Controls","Deterministic · weight 0.4","rule"),
        (736,"Behavioural Intelligence","Entity deviation signals","behav"),
        (1099,"Graph Intelligence","Mule-network topology","graph"),
    ]
    iw,ih,iy = 290,58,308
    for ix,il,is_,isty in intel:
        o += nd(ix,iy,iw,ih,il,is_,isty)

    # Fusion
    o += nd(10,390,1380,62,"Risk Score   ·   Decision Tier   ·   Reason Codes",
            "APPROVE  < 0.30          REVIEW  0.30 – 0.70          BLOCK  ≥ 0.70","fusion")

    # Data
    o += nd(160,504,440,58,"PostgreSQL Case Store","Cases · investigations · verdicts · events","data")
    # Portfolio (right side in data zone)
    o += nd(760,504,440,58,"Portfolio Scan Results","Indexed results · tier counters · export","portfolio")

    # Ops — 5 nodes
    ow_,oh_,oy = 248,54,614
    ops = [
        (10,"Review Queue","P0–P3 priority · sort by risk","ops"),
        (272,"Case Dossier 2.0","Evidence · attribution · AI brief","ops"),
        (534,"Investigation Brief","AI advisory · version-tracked","audit"),
        (796,"Verdict Capture","CONFIRMED · FALSE_POSITIVE · APPROVED","ops"),
        (1058,"Workflow Audit","Dispatch events · callback","workflow"),
    ]
    for ox_,ol,os_,osty in ops:
        o += nd(ox_,oy,ow_,oh_,ol,os_,osty)
    # Reliability Metrics below Verdict
    o += nd(796,684,248,46,"Reliability Metrics","SLO monitoring · health verdict","audit")

    # ── arrows ────────────────────────────────────────────────────────────────
    # Experience → Service
    o += ln(700,146,700,198)
    # Service → each intel node (entry x nudged right of the zone heading text)
    sx,sy = 700,256
    for ix,*_ in intel:
        tx = max(ix+iw//2,235)
        o += cbez(sx,sy, sx,sy+16, tx,iy-16, tx,iy)
    # Intel → Fusion
    for ix,*_ in intel:
        tx = ix+iw//2
        fx = min(max(tx,50),1340)
        o += ln(tx,iy+ih,fx,390)
    # Fusion → PostgreSQL
    o += cbez(380,452, 380,478, 380,494, 380,504)
    # Fusion → Portfolio (dashed async)
    o += cbez(980,452, 980,478, 980,494, 980,504, dash=True)
    # FastAPI → Portfolio Scan (dashed)  — show Portfolio as parallel path from API
    o += cbez(970,227, 1062,227, 1062,268, 1062,302, dash=True)
    # PostgreSQL → Ops (fan; entry x nudged right of the zone heading text)
    pc = 380
    for ox_,*_ in ops:
        tc = max(ox_+ow_//2,200)
        o += cbez(pc,562, pc,588, tc,600, tc,oy)
    # Ops flow (horizontal)
    o += ln(10+ow_,oy+oh_//2, 272,oy+oh_//2)
    o += ln(272+ow_,oy+oh_//2, 534,oy+oh_//2)
    # Verdict → Reliability
    o += ln(796+ow_//2,oy+oh_,796+ow_//2,684)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 2 — Transaction Intake and Scoring
# ─────────────────────────────────────────────────────────────────────────────
def d2():
    W,H = 1400,686
    o = hdr(W,H,"Transaction Intake and Scoring",
            "Scoring pipeline: transaction submission, feature extraction, four-layer intelligence, score composition, decision tier, case record.")

    # Zones
    o += f'  <rect x="10" y="58" width="1380" height="100" rx="4" fill="#EFF6FF"/>\n'
    o += zl(20,77,"Intake","#1D4ED8")
    o += f'  <rect x="10" y="168" width="1380" height="100" rx="4" fill="#FFF1F2"/>\n'
    o += zl(20,187,"Feature Processing","#BE123C")
    o += f'  <rect x="10" y="278" width="1380" height="104" rx="4" fill="#FFF7ED"/>\n'
    o += zl(20,297,"Four-Layer Scoring","#B45309")
    o += f'  <rect x="10" y="392" width="1380" height="100" rx="4" fill="#F0FDF4"/>\n'
    o += zl(20,411,"Score Composition","#15803D")
    o += f'  <rect x="10" y="502" width="1380" height="168" rx="4" fill="#EEF2FF"/>\n'
    o += zl(20,521,"Decision & Persistence","#3730A3")

    # Row 1: Transaction Submitted
    o += nd(480,88,440,58,"Transaction Submitted","POST /predict · POST /risk-scan · Kafka event","input")
    # Row 2: API Validation + Feature Extraction side by side
    o += nd(120,198,500,58,"API Validation","Schema check · field normalisation","service")
    o += nd(780,198,500,58,"Feature Extraction","9-feature vector · device · geo · velocity","service")
    # Row 3: Four intelligence nodes
    intel2 = [
        (10, "Model Risk","XGBoost inference","model"),
        (362,"Rule Controls","Deterministic flags","rule"),
        (714,"Behavioural Profile","Entity deviation","behav"),
        (1066,"Graph Intelligence","Mule topology","graph"),
    ]
    iw2,ih2,iy2 = 310,62,308
    for ix,il,is_,isty in intel2:
        o += nd(ix,iy2,iw2,ih2,il,is_,isty)
    # Row 4: Score Composition
    o += nd(10,422,1380,58,"Score Composition  ·  Risk Score 0.0 – 1.0  ·  Layer Boosts Applied","base = (model × 0.6) + (rule × 0.4)   +   behavioural boost   +   graph boost","fusion")
    # Row 5: Risk Tier + Reason Codes
    o += nd(120,532,500,58,"Risk Tier Decision","APPROVE < 0.30   REVIEW 0.30–0.70   BLOCK ≥ 0.70","ops")
    o += nd(780,532,500,58,"Reason Codes","Per-layer evidence codes for Case Dossier","audit")
    # Row 6: Case Record
    o += nd(350,606,700,52,"Case Record (PostgreSQL)","risk_score · decision · features · reason codes persisted","data")

    # ── arrows ────────────────────────────────────────────────────────────────
    # Intake → Validation + Features
    o += cbez(700,146, 700,172, 370,172, 370,198)
    o += cbez(700,146, 700,172, 1030,172, 1030,198)
    # Validation + Features → intel nodes (entry x nudged right of the zone heading text)
    for ix,*_ in intel2:
        tx = max(ix+iw2//2,210)
        o += cbez(370,256, 370,282, tx,294, tx,308)
        o += cbez(1030,256, 1030,282, tx,294, tx,308)
    # Intel → Score Composition (entry x nudged right of the zone heading text)
    for ix,*_ in intel2:
        tx = ix+iw2//2
        ex = max(tx,210)
        o += cbez(tx,370, tx,392, ex,408, ex,422)
    # Score → Risk Tier + Reason Codes
    o += cbez(700,480, 700,508, 370,508, 370,532)
    o += cbez(700,480, 700,508, 1030,508, 1030,532)
    # Risk Tier + Reasons → Case Record
    o += cbez(370,590, 370,599, 700,599, 700,606)
    o += cbez(1030,590, 1030,599, 700,599, 700,606)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 3 — Analyst Case Dossier and Verdict
# ─────────────────────────────────────────────────────────────────────────────
def d3():
    W,H = 1400,694
    o = hdr(W,H,"Analyst Case Intelligence Pipeline",
            "Intelligence-driven case review: queue, evidence groups, analyst review, verdict capture, workflow dispatch, audit trail.")

    # Zones
    o += f'  <rect x="10" y="58" width="440" height="98" rx="4" fill="#F5F3FF"/>\n'
    o += zl(20,77,"Queue","#6D28D9")
    o += f'  <rect x="10" y="166" width="1380" height="108" rx="4" fill="#EFF6FF"/>\n'
    o += zl(20,185,"Case Dossier 2.0","#1D4ED8")
    o += f'  <rect x="10" y="284" width="1380" height="106" rx="4" fill="#FFF7ED"/>\n'
    o += zl(20,303,"Evidence Groups","#B45309")
    o += f'  <rect x="10" y="400" width="440" height="98" rx="4" fill="#FFFBEB"/>\n'
    o += zl(20,419,"Analyst Review","#B45309")
    o += f'  <rect x="10" y="508" width="1380" height="170" rx="4" fill="#F0FDF4"/>\n'
    o += zl(20,527,"Decision & Audit","#15803D")

    # Row 1: Queue
    o += nd(10,88,420,56,"Review Queue","Cases sorted by risk · P0–P3 priority tiers","ops")
    # Row 2: Case Dossier
    o += nd(10,196,1380,66,"Case Dossier 2.0","Structured lifecycle view: evidence groups · timeline · model attribution · AI brief · verdict panel","service")
    # Row 3: Evidence groups (6 nodes)
    ev_nodes = [
        (10,"Base Signals","ML score · rule flag · 9 features","model"),
        (248,"Enriched Signals","Rich risk indicators","rule"),
        (486,"Behavioural","Amount · velocity · profile deviation","behav"),
        (724,"Graph Evidence","Fan-in · fan-out · device clusters","graph"),
        (962,"TreeSHAP Attribution","Per-feature XGBoost contributions","audit"),
        (1200,"Investigation Brief","AI advisory · AGENT_VERSION","ai"),
    ]
    ew,eh,ey = 192,64,314
    for ex_,el,es_,esty in ev_nodes:
        o += nd(ex_,ey,ew,eh,el,es_,esty)
    # Row 4: Analyst Review
    o += nd(10,430,420,56,"Analyst Review","Evidence evaluated · decision formed","ops")
    # Row 5: Verdict + Workflow + Audit
    o += nd(10,538,400,56,"Verdict Capture","CONFIRMED_FRAUD · FALSE_POSITIVE · APPROVED","ops")
    o += nd(490,538,400,56,"Workflow Dispatch","POST /workflow/notify-case/{id}","workflow")
    o += nd(970,538,420,56,"Workflow Event","n8n callback · status persisted","audit")
    # Row 6: Audit Trail
    o += nd(10,610,840,56,"Automation Audit Trail","Workflow events · case-scoped · filterable · append-only","data")
    o += nd(970,610,420,56,"Reliability Metrics","SLO health · dispatch success rate","audit")

    # ── arrows ────────────────────────────────────────────────────────────────
    # Queue → Dossier
    o += ln(220,144,220,196)
    # Dossier → each evidence group (entry x nudged right of the zone heading text)
    for ex_,*_ in ev_nodes:
        tx = max(ex_+ew//2,180)
        o += ln(tx,262,tx,314)
    # Evidence → Analyst Review (all converge)
    for ex_,*_ in ev_nodes:
        tx = ex_+ew//2
        o += cbez(tx,ey+eh, tx,ey+eh+18, 220,420, 220,430)
    # Analyst Review → Verdict
    o += ln(220,486,220,538)
    # Verdict → Workflow
    o += ln(410,566,490,566)
    # Workflow → Event
    o += ln(890,566,970,566)
    # Verdict → Audit
    o += ln(210,594,210,610)
    # Event → Audit + Reliability
    o += ln(1180,594,1180,610)
    o += cbez(420,594, 420,602, 500,602, 500,610)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 4 — Advisory Investigation Brief
# ─────────────────────────────────────────────────────────────────────────────
def d4():
    W,H = 1400,616
    o = hdr(W,H,"Case Investigation Lifecycle",
            "Case investigation lifecycle: evidence assembly, local LLM inference, schema validation, failure-bounded persistence, analyst review, and verdict.")

    # Zones
    o += f'  <rect x="10" y="58" width="1380" height="100" rx="4" fill="#FFF1F2"/>\n'
    o += zl(20,77,"Evidence Assembly","#BE123C")
    o += f'  <rect x="10" y="168" width="1380" height="100" rx="4" fill="#FEF3C7"/>\n'
    o += zl(20,187,"LLM Inference","#92400E")
    o += f'  <rect x="10" y="278" width="1380" height="186" rx="4" fill="#F0FDF4"/>\n'
    o += zl(20,297,"Validation & Persistence","#15803D")
    o += f'  <rect x="10" y="474" width="1380" height="126" rx="4" fill="#EFF6FF"/>\n'
    o += zl(20,493,"Analyst Control","#1D4ED8")

    # Row 1: Evidence assembly (3 nodes)
    o += nd(10,88,410,58,"Case Context","Transaction · features · decision · risk score","input")
    o += nd(500,88,400,58,"Evidence Payload","Base · enriched · behavioural · graph signals grouped","model")
    o += nd(980,88,410,58,"RAG Retrieval","Playbook and policy knowledge base queried","behav")
    # Row 2: LLM inference
    o += nd(200,198,460,58,"Local LLM Profile","Ollama inference (local runtime only)","ai")
    o += nd(740,198,460,58,"Prompt Assembly","Evidence groups + playbook context structured","fusion")
    # Row 3: Advisory Brief + Validation
    o += nd(200,308,460,58,"Advisory Brief","Recommendation · confidence · rationale · risk factors","audit")
    o += nd(740,308,460,58,"Schema Validation","Structured output contract enforced","fusion")
    # Row 4: Branch — persisted vs failed
    o += nd(80,390,440,62,"Persisted Brief (COMPLETE)","AGENT_VERSION tagged · durable record","data")
    o += nd(600,390,440,62,"Bounded Failure Record (FAILED)","Analyst-readable failure · durable FAILED state","disabled")
    # Row 5: Analyst review
    o += nd(200,504,460,62,"Analyst Review","Brief is advisory only — analyst retains decision control","experience")
    o += nd(740,504,460,62,"Human Verdict","CONFIRMED_FRAUD · FALSE_POSITIVE · APPROVED","ops")
    # NOTE box
    o += f'  <text x="700" y="590" text-anchor="middle" font-family="{F}" font-size="12" fill="#6B7280" font-style="italic">AI assists investigation briefing. Analyst decision is authoritative. Every brief carries AGENT_VERSION for traceability.</text>\n'

    # ── arrows ────────────────────────────────────────────────────────────────
    # Evidence assembly → LLM + Prompt
    o += cbez(215,146, 215,172, 430,172, 430,198)
    o += cbez(700,146, 700,172, 970,172, 970,198)
    o += cbez(1185,146, 1185,172, 970,172, 970,198)
    # LLM + Prompt → Brief
    o += cbez(430,256, 430,282, 430,296, 430,308)
    o += cbez(970,256, 970,282, 970,296, 970,308)
    # Brief → Validation
    o += ln(660,337,740,337)
    # Validation → branches
    o += cbez(970,366, 970,378, 300,378, 300,390)
    o += cbez(970,366, 970,378, 820,378, 820,390)
    # Persisted + Failed → Analyst
    o += cbez(300,452, 300,478, 430,478, 430,504)
    o += cbez(820,452, 820,478, 430,478, 430,504)
    # Analyst → Verdict
    o += ln(660,535,740,535)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 5 — Portfolio Risk Scan
# ─────────────────────────────────────────────────────────────────────────────
def d5():
    W,H = 1400,782
    o = hdr(W,H,"Portfolio Risk Scan Pipeline",
            "Async bulk scan: CSV upload, chunked scoring, tier counters, indexed results, pagination, streaming export, case promotion.")

    # Zones
    o += f'  <rect x="10" y="58" width="1380" height="100" rx="4" fill="#EFF6FF"/>\n'
    o += zl(20,77,"Upload & Validation","#1D4ED8")
    o += f'  <rect x="10" y="168" width="1380" height="100" rx="4" fill="#FEF3C7"/>\n'
    o += zl(20,187,"Async Processing","#92400E")
    o += f'  <rect x="10" y="278" width="1380" height="100" rx="4" fill="#FFF1F2"/>\n'
    o += zl(20,297,"Scoring","#BE123C")
    o += f'  <rect x="10" y="388" width="1380" height="100" rx="4" fill="#F0FDF4"/>\n'
    o += zl(20,407,"Persistence","#15803D")
    o += f'  <rect x="10" y="498" width="1380" height="100" rx="4" fill="#ECFEFF"/>\n'
    o += zl(20,517,"Results Access","#0E7490")
    o += f'  <rect x="10" y="608" width="1380" height="98" rx="4" fill="#FFFBEB"/>\n'
    o += zl(20,627,"Output Paths","#B45309")

    # Row 1: Upload + Validation
    o += nd(120,88,500,58,"CSV Upload","POST /risk-scan · HTTP 202 + scan_id returned","input")
    o += nd(780,88,500,58,"Schema Validation","Field types · required columns · row sanitisation","service")
    # Row 2: Async
    o += nd(120,198,500,58,"Async Scan Job","Background task · scan_id persisted · scan_id polling","ops")
    o += nd(780,198,500,58,"Chunked Processing","2,000-row chunks · memory-bounded per chunk","portfolio")
    # Row 3: Scoring
    o += nd(10,308,680,58,"4-Layer Scoring","Model + rules + behavioural + graph per row","model")
    o += nd(710,308,680,58,"Tier Assignment","P0 Critical · P1 High · P2 Medium · P3 Low","rule")
    # Row 4: Persistence
    o += nd(10,418,680,58,"Running Summary Counters","P0–P3 counts · exposure totals updated per chunk","data")
    o += nd(710,418,680,58,"Indexed Scan Results","Composite index (scan_id, risk_score, tier)","data")
    # Row 5: Polling
    o += nd(400,528,600,58,"Progress Polling","GET /risk-scan/{scan_id}/status · real-time incremental","portfolio")
    # Row 6: Outputs (3 nodes)
    o += nd(10,638,400,56,"Paginated Results","GET /risk-scan/{id}/results · P0/P1/P3 filter","portfolio")
    o += nd(490,638,400,56,"Streaming CSV Export","GET /risk-scan/{id}/export · server-side cursor","portfolio")
    o += nd(970,638,420,56,"Promote to Case","Individual row → Case Dossier · Review Queue","ops")

    # Hosted boundary note
    o += f'  <rect x="10" y="716" width="1380" height="50" rx="4" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>\n'
    o += f'  <text x="700" y="735" text-anchor="middle" font-family="{F}" font-size="12" fill="#64748B" font-weight="600">Hosted Profile B (Render) supports bounded inspection scans. 10M-row benchmark evidence is from controlled local environment benchmark runs.</text>\n'
    o += f'  <text x="700" y="753" text-anchor="middle" font-family="{F}" font-size="11" fill="#9CA3AF">The hosted environment validates async architecture, progress polling, pagination, and export. Full benchmark replication requires the local Docker Compose stack.</text>\n'

    # ── arrows ────────────────────────────────────────────────────────────────
    o += ln(370,146,370,198)   # Upload → Async
    o += ln(1030,146,1030,198) # Validation → Chunked
    o += cbez(370,256, 370,282, 350,294, 350,308)   # Async → Scoring
    o += cbez(1030,256, 1030,282, 1050,294, 1050,308) # Chunked → Tier
    o += ln(350,366,350,418)   # Scoring → Counters
    o += ln(1050,366,1050,418) # Tier → Indexed
    # Indexed → Polling
    o += cbez(1050,476, 1050,502, 700,502, 700,528)
    # Counters + Indexed → Outputs
    o += cbez(350,476, 350,540, 210,584, 210,638)
    o += pa("M1050,476 C1050,530 1050,580 1050,612 C1050,632 690,608 690,638")
    o += cbez(1050,476, 1180,530, 1180,590, 1180,638)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 7 — Workflow Automation and Audit
# ─────────────────────────────────────────────────────────────────────────────
def d6_workflow():
    W,H = 1400,576
    o = hdr(W,H,"Workflow Automation and Audit",
            "Analyst verdict triggers workflow dispatch, n8n callback automation, events table persistence, reliability metrics, and missing-callback visibility.")

    # Zones (reserved heading band: label baseline at zone top + 19)
    o += f'  <rect x="10" y="58" width="1380" height="100" rx="4" fill="#FFFBEB"/>\n'
    o += zl(20,77,"ANALYST DECISION","#B45309")
    o += f'  <rect x="10" y="168" width="1380" height="174" rx="4" fill="#FDF2F8"/>\n'
    o += zl(20,187,"WORKFLOW AUTOMATION","#9D174D")
    o += f'  <rect x="10" y="352" width="1380" height="100" rx="4" fill="#F5F3FF"/>\n'
    o += zl(20,371,"CALLBACK RECEIPT","#6D28D9")
    o += f'  <rect x="10" y="462" width="1380" height="98" rx="4" fill="#F0FDF4"/>\n'
    o += zl(20,481,"PERSISTENCE AND OBSERVABILITY","#15803D")

    cx,nw = 500,400
    mc = cx + nw//2  # 700

    # Vertical chain
    o += nd(cx,88,nw,58,"Analyst Verdict","CONFIRMED_FRAUD verdict triggers escalation","ops")
    o += nd(cx,198,nw,58,"Workflow Dispatch","POST /workflow/notify-case/{id}","workflow")
    o += nd(cx,272,nw,58,"n8n Local Workflow","Webhook trigger · escalation automation sequence","workflow")
    o += nd(cx,382,nw,58,"Callback Event","POST /workflow/callback · status persisted","service")

    # Bottom three nodes
    bw,bh,by = 380,56,492
    bx_list = [50, 510, 970]
    bot = [
        ("Workflow Events Table","case_id · dispatched_at · callback_received · latency","data"),
        ("Reliability Metrics","SLO health · dispatch success rate · health verdict","audit"),
        ("Missing Callback Visible","Stale detection · operator alert · audit trail","ops"),
    ]
    for i,(lbl,sub,sty) in enumerate(bot):
        o += nd(bx_list[i],by,bw,bh,lbl,sub,sty)

    # Arrows — vertical chain
    o += ln(mc,146,mc,198)
    o += ln(mc,256,mc,272)
    o += ln(mc,330,mc,382)
    # Callback fans to bottom three
    for bxi in bx_list:
        tc = bxi + bw//2
        o += cbez(mc,440, mc,452, tc,484, tc,492)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 7 — Deployment Profiles
# ─────────────────────────────────────────────────────────────────────────────
def d7():
    W,H = 1400,682
    o = hdr(W,H,"Deployment Profiles",
            "Side-by-side comparison of Profile A (local full runtime) and Profile B (hosted inspection runtime).")

    CW = 630  # column width
    CX_A = 40   # Profile A start x
    CX_B = 730  # Profile B start x
    divX = 700  # divider x

    # Column headers
    o += f'  <rect x="{CX_A}" y="62" width="{CW}" height="40" rx="4" fill="#1E293B"/>\n'
    o += f'  <text x="{CX_A+CW//2}" y="88" text-anchor="middle" font-family="{F}" font-size="16" font-weight="700" fill="#F1F5F9">Profile A — Local Full Runtime</text>\n'
    o += f'  <rect x="{CX_B}" y="62" width="{CW}" height="40" rx="4" fill="#0C4A6E"/>\n'
    o += f'  <text x="{CX_B+CW//2}" y="88" text-anchor="middle" font-family="{F}" font-size="16" font-weight="700" fill="#BAE6FD">Profile B — Hosted Inspection Runtime</text>\n'

    # Divider
    o += f'  <line x1="{divX}" y1="58" x2="{divX}" y2="{H-16}" stroke="#E2E8F0" stroke-width="2" stroke-dasharray="4,4"/>\n'

    # Status badges
    def sticker(x,y,label,col,fc):
        w_=108
        o  = f'  <rect x="{x}" y="{y}" width="{w_}" height="20" rx="10" fill="{col}"/>\n'
        o += f'  <text x="{x+w_//2}" y="{y+13}" text-anchor="middle" font-family="{F}" font-size="10" font-weight="700" fill="{fc}">{xe(label)}</text>\n'
        return o

    # Profile A components
    a_comps = [
        ("Next.js 16","Analyst frontend","experience","ACTIVE","#059669","#FFFFFF"),
        ("FastAPI + Scoring","REST API · 4-layer scoring","service","ACTIVE","#059669","#FFFFFF"),
        ("PostgreSQL 16","Cases · events · scan results","data","ACTIVE","#059669","#FFFFFF"),
        ("Redis","Cache layer","data","ACTIVE","#059669","#FFFFFF"),
        ("Redpanda (Kafka)","Scoring · investigation topics","portfolio","ACTIVE","#059669","#FFFFFF"),
        ("Scoring Consumer","4-layer scoring pipeline","model","ACTIVE","#059669","#FFFFFF"),
        ("Investigation Consumer","Ollama-backed AI briefs","ai","ACTIVE","#059669","#FFFFFF"),
        ("n8n Workflow","Fraud escalation automation","workflow","ACTIVE","#059669","#FFFFFF"),
        ("Ollama (Local LLM)","Mistral · investigation briefs","ai","ACTIVE","#059669","#FFFFFF"),
    ]
    # Profile B components
    b_comps = [
        ("Vercel","Next.js frontend · CDN-distributed","experience","ACTIVE","#059669","#FFFFFF"),
        ("Render (FastAPI)","REST API · synchronous scoring","service","ACTIVE","#059669","#FFFFFF"),
        ("Neon (PostgreSQL)","Managed cloud Postgres","data","ACTIVE","#059669","#FFFFFF"),
        ("Redis","Not hosted","disabled","HOSTED-DISABLED","#9CA3AF","#FFFFFF"),
        ("Kafka / Redpanda","Not hosted · sync-only path","disabled","HOSTED-DISABLED","#9CA3AF","#FFFFFF"),
        ("Scoring Consumer","Disabled · sync path active","disabled","HOSTED-DISABLED","#9CA3AF","#FFFFFF"),
        ("Investigation Consumer","Disabled · no Ollama","disabled","HOSTED-DISABLED","#9CA3AF","#FFFFFF"),
        ("n8n Workflow","Disabled · no hosted callbacks","disabled","HOSTED-DISABLED","#9CA3AF","#FFFFFF"),
        ("Ollama / LLM","Disabled · hosted-disabled","disabled","HOSTED-DISABLED","#9CA3AF","#FFFFFF"),
    ]

    NW,NH,gap = 590,48,8
    start_y = 118
    for i,(lbl,sub,sty,badge_t,bcol,btc) in enumerate(a_comps):
        ny = start_y + i*(NH+gap)
        o += nd(CX_A,ny,NW,NH,lbl,sub,sty)
        o += sticker(CX_A+NW-116,ny+14,badge_t,bcol,btc)
    for i,(lbl,sub,sty,badge_t,bcol,btc) in enumerate(b_comps):
        ny = start_y + i*(NH+gap)
        o += nd(CX_B,ny,NW,NH,lbl,sub,sty)
        o += sticker(CX_B+NW-116,ny+14,badge_t,bcol,btc)

    # Docker Compose label
    o += f'  <rect x="{CX_A}" y="{H-56}" width="{CW}" height="36" rx="4" fill="#F1F5F9" stroke="#CBD5E1" stroke-width="1"/>\n'
    o += f'  <text x="{CX_A+CW//2}" y="{H-33}" text-anchor="middle" font-family="{F}" font-size="12" fill="#374151" font-weight="600">docker compose up — 7 services · single command</text>\n'
    o += f'  <rect x="{CX_B}" y="{H-56}" width="{CW}" height="36" rx="4" fill="#F0F9FF" stroke="#BAE6FD" stroke-width="1"/>\n'
    o += f'  <text x="{CX_B+CW//2}" y="{H-33}" text-anchor="middle" font-family="{F}" font-size="12" fill="#0C4A6E" font-weight="600">Inspection runtime · Profile B · No production SLA</text>\n'

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Write all diagrams
# ─────────────────────────────────────────────────────────────────────────────
def main():
    diagrams = [
        ("01_system_at_a_glance.svg",   d1),
        ("02_scoring_architecture.svg", d2),
        ("03_intelligence_pipeline.svg", d3),
        ("04_case_lifecycle.svg",        d4),
        ("05_risk_scan_pipeline.svg",   d5),
        ("06_deployment_profiles.svg",  d7),
        ("07_workflow_automation_audit.svg", d6_workflow),
    ]
    for fname, fn in diagrams:
        path = OUT / fname
        svg = fn()
        path.write_text(svg, encoding="utf-8")
        size = len(svg.encode("utf-8"))
        print(f"  wrote {path}  ({size:,} bytes)")

if __name__ == "__main__":
    main()
