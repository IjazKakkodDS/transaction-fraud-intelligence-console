#!/usr/bin/env python3
"""
Architecture diagram generator — Real-Time Transaction Fraud Intelligence Console.
Produces 6 production SVG diagrams in docs/architecture/.
Run from the repository root: python docs/architecture/source/generate_svgs.py
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
    W,H = 1400,668
    o = hdr(W,H,"System at a Glance",
            "Complete product architecture: analyst console, FastAPI, hybrid scoring, case store, analyst operations, and portfolio scan.")

    # ── zone backgrounds ──────────────────────────────────────────────────────
    zones = [
        (10,52,1380,78,"#EFF6FF","EXPERIENCE LAYER","#1D4ED8"),
        (10,146,1380,78,"#F5F3FF","SERVICE LAYER","#6D28D9"),
        (10,240,1380,178,"#FFF1F2","DECISION INTELLIGENCE","#BE123C"),
        (10,434,1380,78,"#F0FDF4","DATA & PERSISTENCE LAYER","#15803D"),
        (10,528,1380,124,"#FFFBEB","ANALYST OPERATIONS","#B45309"),
    ]
    for zx,zy,zw,zh,zc,zl_,zcol in zones:
        o += f'  <rect x="{zx}" y="{zy}" width="{zw}" height="{zh}" rx="4" fill="{zc}"/>\n'
        o += zl(zx+10,zy+13,zl_,zcol)

    # ── nodes ─────────────────────────────────────────────────────────────────
    # Experience
    o += nd(480,62,440,58,"Analyst Console","Next.js 16 · 8 routes","experience")

    # Service
    o += nd(430,156,540,58,"FastAPI REST API","27 endpoints · scoring · cases · scan · workflow","service")

    # Intelligence — 4 nodes spread across x=10..1380
    # widths 290 each, gaps ~113px: x = 10,313,616,919  right=209,502,805,1108... actually:
    # 4×290=1160, space=1380-1160=220, 3 gaps=73 each
    # x: 10, 10+290+73=373, 373+290+73=736, 736+290+73=1099  right: 300,663,1026,1389 ✓
    intel = [
        (10, "Model Risk","XGBoost · weight 0.6","model"),
        (373,"Rule Controls","Deterministic · weight 0.4","rule"),
        (736,"Behavioural Intelligence","Entity deviation signals","behav"),
        (1099,"Graph Intelligence","Mule-network topology","graph"),
    ]
    iw,ih,iy = 290,58,250
    for ix,il,is_,isty in intel:
        o += nd(ix,iy,iw,ih,il,is_,isty)

    # Fusion
    o += nd(10,344,1380,62,"Risk Score   ·   Decision Tier   ·   Reason Codes",
            "APPROVE  < 0.30          REVIEW  0.30 – 0.70          BLOCK  ≥ 0.70","fusion")

    # Data
    o += nd(160,444,440,58,"PostgreSQL Case Store","Cases · investigations · verdicts · events","data")
    # Portfolio (right side in data zone)
    o += nd(760,444,440,58,"Portfolio Scan Results","Indexed results · tier counters · export","portfolio")

    # Ops — 5 nodes
    ow_,oh_,oy = 248,54,538
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
    o += nd(796,608,248,46,"Reliability Metrics","SLO monitoring · health verdict","audit")

    # ── arrows ────────────────────────────────────────────────────────────────
    # Experience → Service
    o += ln(700,120,700,156)
    # Service → each intel node
    sx,sy = 700,214
    for ix,*_ in intel:
        tx = ix+iw//2
        o += cbez(sx,sy, sx,sy+14, tx,iy-14, tx,iy)
    # Intel → Fusion
    for ix,*_ in intel:
        tx = ix+iw//2
        fx = min(max(tx,50),1340)
        o += ln(tx,iy+ih,fx,344)
    # Fusion → PostgreSQL
    o += cbez(380,406, 380,425, 380,434, 380,444)
    # Fusion → Portfolio (dashed async)
    o += cbez(980,406, 980,425, 980,434, 980,444, dash=True)
    # FastAPI → Portfolio Scan (dashed)  — show Portfolio as parallel path from API
    o += cbez(970,185, 1200,185, 1200,214, 1200,244, dash=True)
    # PostgreSQL → Ops (fan)
    pc = 380
    for ox_,*_ in ops:
        tc = ox_+ow_//2
        o += cbez(pc,502, pc,520, tc,528, tc,538)
    # Ops flow (horizontal)
    o += ln(10+ow_,oy+oh_//2, 272,oy+oh_//2)
    o += ln(272+ow_,oy+oh_//2, 534,oy+oh_//2)
    # Verdict → Reliability
    o += ln(796+ow_//2,oy+oh_,796+ow_//2,608)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 2 — Transaction Intake and Scoring
# ─────────────────────────────────────────────────────────────────────────────
def d2():
    W,H = 1400,618
    o = hdr(W,H,"Transaction Intake and Scoring",
            "Scoring pipeline: transaction submission, feature extraction, four-layer intelligence, score composition, decision tier, case record.")

    # Vertical flow + fan + converge
    # Row y positions:
    r = [60,136,212,302,390,466,542]  # node top-y per row (heights vary)
    nh = 58  # standard node height

    # Zones
    o += f'  <rect x="10" y="52" width="1380" height="74" rx="4" fill="#EFF6FF"/>\n'
    o += zl(20,65,"Intake","#1D4ED8")
    o += f'  <rect x="10" y="132" width="1380" height="74" rx="4" fill="#FFF1F2"/>\n'
    o += zl(20,145,"Feature Processing","#BE123C")
    o += f'  <rect x="10" y="212" width="1380" height="172" rx="4" fill="#FFF7ED"/>\n'
    o += zl(20,225,"Four-Layer Scoring","#B45309")
    o += f'  <rect x="10" y="390" width="1380" height="74" rx="4" fill="#F0FDF4"/>\n'
    o += zl(20,403,"Score Composition","#15803D")
    o += f'  <rect x="10" y="470" width="1380" height="136" rx="4" fill="#EEF2FF"/>\n'
    o += zl(20,483,"Decision & Persistence","#3730A3")

    # Row 1: Transaction Submitted
    o += nd(480,60,440,58,"Transaction Submitted","POST /predict · POST /risk-scan · Kafka event","input")
    # Row 2: API Validation + Feature Extraction side by side
    o += nd(120,136,500,58,"API Validation","Schema check · field normalisation","service")
    o += nd(780,136,500,58,"Feature Extraction","9-feature vector · device · geo · velocity","service")
    # Row 3: Four intelligence nodes
    intel2 = [
        (10, "Model Risk","XGBoost inference","model"),
        (362,"Rule Controls","Deterministic flags","rule"),
        (714,"Behavioural Profile","Entity deviation","behav"),
        (1066,"Graph Intelligence","Mule topology","graph"),
    ]
    iw2,ih2,iy2 = 310,62,222
    for ix,il,is_,isty in intel2:
        o += nd(ix,iy2,iw2,ih2,il,is_,isty)
    # Row 4: Score Composition
    o += nd(10,400,1380,58,"Score Composition  ·  Risk Score 0.0 – 1.0  ·  Layer Boosts Applied","base = (model × 0.6) + (rule × 0.4)   +   behavioural boost   +   graph boost","fusion")
    # Row 5: Risk Tier + Reason Codes
    o += nd(120,478,500,58,"Risk Tier Decision","APPROVE < 0.30   REVIEW 0.30–0.70   BLOCK ≥ 0.70","ops")
    o += nd(780,478,500,58,"Reason Codes","Per-layer evidence codes for Case Dossier","audit")
    # Row 6: Case Record
    o += nd(350,552,700,52,"Case Record (PostgreSQL)","risk_score · decision · features · reason codes persisted","data")

    # ── arrows ────────────────────────────────────────────────────────────────
    # Intake → Validation + Features
    o += cbez(700,118, 700,127, 370,127, 370,136)
    o += cbez(700,118, 700,127, 1030,127, 1030,136)
    # Validation + Features → intel nodes
    for ix,*_ in intel2:
        tx = ix+iw2//2
        o += cbez(370,194, 370,208, tx,212, tx,222)
        o += cbez(1030,194, 1030,208, tx,212, tx,222)
    # Intel → Score Composition
    for ix,*_ in intel2:
        tx = ix+iw2//2
        o += ln(tx,iy2+ih2,tx,400)
    # Score → Risk Tier + Reason Codes
    o += cbez(700,458, 700,468, 370,468, 370,478)
    o += cbez(700,458, 700,468, 1030,468, 1030,478)
    # Risk Tier + Reasons → Case Record
    o += cbez(370,536, 370,545, 700,545, 700,552)
    o += cbez(1030,536, 1030,545, 700,545, 700,552)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 3 — Analyst Case Dossier and Verdict
# ─────────────────────────────────────────────────────────────────────────────
def d3():
    W,H = 1400,608
    o = hdr(W,H,"Analyst Case Intelligence Pipeline",
            "Intelligence-driven case review: queue, evidence groups, analyst review, verdict capture, workflow dispatch, audit trail.")

    # Zones
    o += f'  <rect x="10" y="52" width="440" height="68" rx="4" fill="#F5F3FF"/>\n'
    o += zl(20,65,"Queue","#6D28D9")
    o += f'  <rect x="10" y="130" width="1380" height="74" rx="4" fill="#EFF6FF"/>\n'
    o += zl(20,143,"Case Dossier 2.0","#1D4ED8")
    o += f'  <rect x="10" y="214" width="1380" height="130" rx="4" fill="#FFF7ED"/>\n'
    o += zl(20,227,"Evidence Groups","#B45309")
    o += f'  <rect x="10" y="354" width="440" height="68" rx="4" fill="#FFFBEB"/>\n'
    o += zl(20,367,"Analyst Review","#B45309")
    o += f'  <rect x="10" y="432" width="1380" height="160" rx="4" fill="#F0FDF4"/>\n'
    o += zl(20,445,"Decision & Audit","#15803D")

    # Row 1: Queue
    o += nd(10,58,420,56,"Review Queue","Cases sorted by risk · P0–P3 priority tiers","ops")
    # Row 2: Case Dossier
    o += nd(10,136,1380,66,"Case Dossier 2.0","Structured lifecycle view: evidence groups · timeline · model attribution · AI brief · verdict panel","service")
    # Row 3: Evidence groups (6 nodes)
    ev_nodes = [
        (10,"Base Signals","ML score · rule flag · 9 features","model"),
        (248,"Enriched Signals","Rich risk indicators","rule"),
        (486,"Behavioural","Amount · velocity · profile deviation","behav"),
        (724,"Graph Evidence","Fan-in · fan-out · device clusters","graph"),
        (962,"TreeSHAP Attribution","Per-feature XGBoost contributions","audit"),
        (1200,"Investigation Brief","AI advisory · AGENT_VERSION","ai"),
    ]
    ew,eh,ey = 192,64,224
    for ex_,el,es_,esty in ev_nodes:
        o += nd(ex_,ey,ew,eh,el,es_,esty)
    # Row 4: Analyst Review
    o += nd(10,360,420,56,"Analyst Review","Evidence evaluated · decision formed","ops")
    # Row 5: Verdict + Workflow + Audit
    o += nd(10,444,400,56,"Verdict Capture","CONFIRMED_FRAUD · FALSE_POSITIVE · APPROVED","ops")
    o += nd(490,444,400,56,"Workflow Dispatch","POST /workflow/notify-case/{id}","workflow")
    o += nd(970,444,420,56,"Workflow Event","n8n callback · status persisted","audit")
    # Row 6: Audit Trail
    o += nd(10,516,840,56,"Automation Audit Trail","Workflow events · case-scoped · filterable · append-only","data")
    o += nd(970,516,420,56,"Reliability Metrics","SLO health · dispatch success rate","audit")

    # ── arrows ────────────────────────────────────────────────────────────────
    # Queue → Dossier
    o += ln(220,114,220,136)
    # Dossier → each evidence group
    for ex_,*_ in ev_nodes:
        tx = ex_+ew//2
        o += ln(tx,202,tx,224)
    # Evidence → Analyst Review (all converge)
    for ex_,*_ in ev_nodes:
        tx = ex_+ew//2
        o += cbez(tx,ey+eh, tx,ey+eh+14, 220,350, 220,360)
    # Analyst Review → Verdict
    o += ln(220,416,220,444)
    # Verdict → Workflow
    o += ln(410,472,490,472)
    # Workflow → Event
    o += ln(890,472,970,472)
    # Verdict → Audit
    o += cbez(210,500, 210,510, 210,516, 210,516)
    # Event → Audit + Reliability
    o += cbez(1180,500, 1180,510, 1180,516, 1180,516)
    o += cbez(420,500, 420,510, 500,510, 500,516)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 4 — Advisory Investigation Brief
# ─────────────────────────────────────────────────────────────────────────────
def d4():
    W,H = 1400,560
    o = hdr(W,H,"Case Investigation Lifecycle",
            "Case investigation lifecycle: evidence assembly, local LLM inference, schema validation, failure-bounded persistence, analyst review, and verdict.")

    # Zones
    o += f'  <rect x="10" y="52" width="1380" height="74" rx="4" fill="#FFF1F2"/>\n'
    o += zl(20,65,"Evidence Assembly","#BE123C")
    o += f'  <rect x="10" y="136" width="1380" height="74" rx="4" fill="#FEF3C7"/>\n'
    o += zl(20,149,"LLM Inference","#92400E")
    o += f'  <rect x="10" y="220" width="1380" height="146" rx="4" fill="#F0FDF4"/>\n'
    o += zl(20,233,"Validation & Persistence","#15803D")
    o += f'  <rect x="10" y="376" width="1380" height="168" rx="4" fill="#EFF6FF"/>\n'
    o += zl(20,389,"Analyst Control","#1D4ED8")

    # Row 1: Evidence assembly (3 nodes)
    o += nd(10,58,410,58,"Case Context","Transaction · features · decision · risk score","input")
    o += nd(500,58,400,58,"Evidence Payload","Base · enriched · behavioural · graph signals grouped","model")
    o += nd(980,58,410,58,"RAG Retrieval","Playbook and policy knowledge base queried","behav")
    # Row 2: LLM inference
    o += nd(200,144,460,58,"Local LLM Profile","Ollama inference (local runtime only)","ai")
    o += nd(740,144,460,58,"Prompt Assembly","Evidence groups + playbook context structured","fusion")
    # Row 3: Advisory Brief + Validation
    o += nd(200,228,460,58,"Advisory Brief","Recommendation · confidence · rationale · risk factors","audit")
    o += nd(740,228,460,58,"Schema Validation","Structured output contract enforced","fusion")
    # Row 4: Branch — persisted vs failed
    o += nd(80,318,440,62,"Persisted Brief (COMPLETE)","AGENT_VERSION tagged · durable record","data")
    o += nd(600,318,440,62,"Bounded Failure Record (FAILED)","Analyst-readable failure · durable FAILED state","disabled")
    # Row 5: Analyst review
    o += nd(200,400,460,62,"Analyst Review","Brief is advisory only — analyst retains decision control","experience")
    o += nd(740,400,460,62,"Human Verdict","CONFIRMED_FRAUD · FALSE_POSITIVE · APPROVED","ops")
    # NOTE box
    o += f'  <text x="700" y="488" text-anchor="middle" font-family="{F}" font-size="12" fill="#6B7280" font-style="italic">AI assists investigation briefing. Analyst decision is authoritative. Every brief carries AGENT_VERSION for traceability.</text>\n'

    # ── arrows ────────────────────────────────────────────────────────────────
    # Evidence assembly → LLM + Prompt
    o += cbez(215,116, 215,128, 430,128, 430,144)
    o += cbez(700,116, 700,128, 970,128, 970,144)
    o += cbez(1185,116, 1185,128, 970,128, 970,144)
    # LLM + Prompt → Brief
    o += cbez(430,202, 430,215, 430,228, 430,228)
    o += cbez(970,202, 970,215, 970,228, 970,228)
    # Brief → Validation
    o += ln(660,257,740,257)
    # Validation → branches
    o += cbez(970,286, 970,302, 300,302, 300,318)
    o += cbez(970,286, 970,302, 820,302, 820,318)
    # Persisted + Failed → Analyst
    o += cbez(300,380, 300,392, 430,392, 430,400)
    o += cbez(820,380, 820,392, 430,392, 430,400)
    # Analyst → Verdict
    o += ln(660,431,740,431)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 5 — Portfolio Risk Scan
# ─────────────────────────────────────────────────────────────────────────────
def d5():
    W,H = 1400,612
    o = hdr(W,H,"Portfolio Risk Scan Pipeline",
            "Async bulk scan: CSV upload, chunked scoring, tier counters, indexed results, pagination, streaming export, case promotion.")

    # Zones
    o += f'  <rect x="10" y="52" width="1380" height="74" rx="4" fill="#EFF6FF"/>\n'
    o += zl(20,65,"Upload & Validation","#1D4ED8")
    o += f'  <rect x="10" y="136" width="1380" height="74" rx="4" fill="#FEF3C7"/>\n'
    o += zl(20,149,"Async Processing","#92400E")
    o += f'  <rect x="10" y="220" width="1380" height="74" rx="4" fill="#FFF1F2"/>\n'
    o += zl(20,233,"Scoring","#BE123C")
    o += f'  <rect x="10" y="304" width="1380" height="74" rx="4" fill="#F0FDF4"/>\n'
    o += zl(20,317,"Persistence","#15803D")
    o += f'  <rect x="10" y="388" width="1380" height="74" rx="4" fill="#ECFEFF"/>\n'
    o += zl(20,401,"Results Access","#0E7490")
    o += f'  <rect x="10" y="472" width="1380" height="124" rx="4" fill="#FFFBEB"/>\n'
    o += zl(20,485,"Output Paths","#B45309")

    # Row 1: Upload + Validation
    o += nd(120,58,500,58,"CSV Upload","POST /risk-scan · HTTP 202 + scan_id returned","input")
    o += nd(780,58,500,58,"Schema Validation","Field types · required columns · row sanitisation","service")
    # Row 2: Async
    o += nd(120,144,500,58,"Async Scan Job","Background task · scan_id persisted · scan_id polling","ops")
    o += nd(780,144,500,58,"Chunked Processing","2,000-row chunks · memory-bounded per chunk","portfolio")
    # Row 3: Scoring
    o += nd(10,228,680,58,"4-Layer Scoring","Model + rules + behavioural + graph per row","model")
    o += nd(710,228,680,58,"Tier Assignment","P0 Critical · P1 High · P2 Medium · P3 Low","rule")
    # Row 4: Persistence
    o += nd(10,312,680,58,"Running Summary Counters","P0–P3 counts · exposure totals updated per chunk","data")
    o += nd(710,312,680,58,"Indexed Scan Results","Composite index (scan_id, risk_score, tier)","data")
    # Row 5: Polling
    o += nd(400,396,600,58,"Progress Polling","GET /risk-scan/{scan_id}/status · real-time incremental","portfolio")
    # Row 6: Outputs (3 nodes)
    o += nd(10,480,400,56,"Paginated Results","GET /risk-scan/{id}/results · P0/P1/P3 filter","portfolio")
    o += nd(490,480,400,56,"Streaming CSV Export","GET /risk-scan/{id}/export · server-side cursor","portfolio")
    o += nd(970,480,420,56,"Promote to Case","Individual row → Case Dossier · Review Queue","ops")

    # Hosted boundary note
    o += f'  <rect x="10" y="548" width="1380" height="50" rx="4" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>\n'
    o += f'  <text x="700" y="567" text-anchor="middle" font-family="{F}" font-size="12" fill="#64748B" font-weight="600">Hosted Profile B (Render) supports bounded inspection scans. 10M-row benchmark evidence is from controlled local environment benchmark runs.</text>\n'
    o += f'  <text x="700" y="585" text-anchor="middle" font-family="{F}" font-size="11" fill="#9CA3AF">The hosted environment validates async architecture, progress polling, pagination, and export. Full benchmark replication requires the local Docker Compose stack.</text>\n'

    # ── arrows ────────────────────────────────────────────────────────────────
    o += ln(370,116,370,144)   # Upload → Async
    o += ln(1030,116,1030,144) # Validation → Chunked
    o += cbez(370,202, 370,215, 350,228, 350,228)   # Async → Scoring
    o += cbez(1030,202, 1030,215, 1050,228, 1050,228) # Chunked → Tier
    o += ln(350,286,350,312)   # Scoring → Counters
    o += ln(1050,286,1050,312) # Tier → Indexed
    # Indexed → Polling
    o += cbez(1050,370, 1050,382, 700,388, 700,396)
    # Counters + Indexed → Outputs
    o += cbez(350,370, 350,382, 210,472, 210,480)
    o += cbez(1050,370, 1050,382, 690,472, 690,480)
    o += cbez(1050,370, 1050,382, 1180,472, 1180,480)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 6 — Workflow Automation and Audit
# ─────────────────────────────────────────────────────────────────────────────
def d6_workflow():
    W,H = 1400,560
    o = hdr(W,H,"Workflow Automation and Audit",
            "Analyst verdict triggers workflow dispatch, n8n callback automation, events table persistence, reliability metrics, and missing-callback visibility.")

    # Zones
    o += f'  <rect x="10" y="52" width="1380" height="74" rx="4" fill="#FFFBEB"/>\n'
    o += zl(20,65,"ANALYST DECISION","#B45309")
    o += f'  <rect x="10" y="136" width="1380" height="148" rx="4" fill="#FDF2F8"/>\n'
    o += zl(20,149,"WORKFLOW AUTOMATION","#9D174D")
    o += f'  <rect x="10" y="294" width="1380" height="74" rx="4" fill="#F5F3FF"/>\n'
    o += zl(20,307,"CALLBACK RECEIPT","#6D28D9")
    o += f'  <rect x="10" y="378" width="1380" height="166" rx="4" fill="#F0FDF4"/>\n'
    o += zl(20,391,"PERSISTENCE AND OBSERVABILITY","#15803D")

    cx,nw = 500,400
    mc = cx + nw//2  # 700

    # Vertical chain
    o += nd(cx,58,nw,58,"Analyst Verdict","CONFIRMED_FRAUD verdict triggers escalation","ops")
    o += nd(cx,142,nw,58,"Workflow Dispatch","POST /workflow/notify-case/{id}","workflow")
    o += nd(cx,216,nw,58,"n8n Local Workflow","Webhook trigger · escalation automation sequence","workflow")
    o += nd(cx,300,nw,58,"Callback Event","POST /workflow/callback · status persisted","service")

    # Bottom three nodes
    bw,bh,by = 380,56,398
    bx_list = [50, 510, 970]
    bot = [
        ("Workflow Events Table","case_id · dispatched_at · callback_received · latency","data"),
        ("Reliability Metrics","SLO health · dispatch success rate · health verdict","audit"),
        ("Missing Callback Visible","Stale detection · operator alert · audit trail","ops"),
    ]
    for i,(lbl,sub,sty) in enumerate(bot):
        o += nd(bx_list[i],by,bw,bh,lbl,sub,sty)

    # Arrows — vertical chain
    o += ln(mc,116,mc,142)
    o += ln(mc,200,mc,216)
    o += ln(mc,274,mc,300)
    # Callback fans to bottom three
    for bxi in bx_list:
        tc = bxi + bw//2
        o += cbez(mc,358, mc,370, tc,390, tc,398)

    o += ftr()
    return o

# ─────────────────────────────────────────────────────────────────────────────
# Diagram 7 — Deployment Profiles
# ─────────────────────────────────────────────────────────────────────────────
def d7():
    W,H = 1400,680
    o = hdr(W,H,"Deployment Profiles",
            "Side-by-side comparison of Profile A (local full runtime) and Profile B (hosted inspection runtime).")

    CW = 630  # column width
    CX_A = 40   # Profile A start x
    CX_B = 730  # Profile B start x
    divX = 700  # divider x

    # Column headers
    o += f'  <rect x="{CX_A}" y="52" width="{CW}" height="40" rx="4" fill="#1E293B"/>\n'
    o += f'  <text x="{CX_A+CW//2}" y="78" text-anchor="middle" font-family="{F}" font-size="16" font-weight="700" fill="#F1F5F9">Profile A — Local Full Runtime</text>\n'
    o += f'  <rect x="{CX_B}" y="52" width="{CW}" height="40" rx="4" fill="#0C4A6E"/>\n'
    o += f'  <text x="{CX_B+CW//2}" y="78" text-anchor="middle" font-family="{F}" font-size="16" font-weight="700" fill="#BAE6FD">Profile B — Hosted Inspection Runtime</text>\n'

    # Divider
    o += f'  <line x1="{divX}" y1="52" x2="{divX}" y2="{H-16}" stroke="#E2E8F0" stroke-width="2" stroke-dasharray="4,4"/>\n'

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
    start_y = 108
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
    ]
    for fname, fn in diagrams:
        path = OUT / fname
        svg = fn()
        path.write_text(svg, encoding="utf-8")
        size = len(svg.encode("utf-8"))
        print(f"  wrote {path}  ({size:,} bytes)")

if __name__ == "__main__":
    main()
