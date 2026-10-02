"""Free preview: can Qwen's keep/unsure/drop labels order the shortlist?

Three blocks (keep > unsure > drop), ties broken by the original fused rank.
No new run, no GPU, no API. Reads only files already on disk.
The baseline row is a calibration row, not a result: a plateau in the
baseline recall curve makes every arm look worse than it is, so read every
equivalent depth against baseline, never against N.
Write-up: docs/trec_qwen_preview.md
"""
import json
from pathlib import Path
D = Path(r"C:\dev\clinical_trials_rag_agent\data\trec")

def qrels(p):
    out={}
    for line in open(p,encoding="utf-8"):
        q=line.split()
        if len(q)>=4: out.setdefault(q[0],{})[q[2]]=int(q[3])
    return out
QR={"2021":qrels(D/"qrels2021.txt"),"2022":qrels(D/"qrels2022.txt")}
short=json.load(open(D/"rerank_shortlists.json",encoding="utf-8"))["years"]
gpu=json.load(open(D/"cheap_pass_gpu.json",encoding="utf-8"))
ce=json.load(open(D/"rerank_ce_scores.json",encoding="utf-8"))["truncate"]
llm=json.load(open(D/"rerank_llm_scores.json",encoding="utf-8"))["scores"]
BUCKET={"keep":2,"unsure":1,"drop":0}

def curve(order, rel):
    c=[0]; h=0
    for n in order:
        if rel.get(n)==2: h+=1
        c.append(h)
    return c

def depth_for(c, target):
    for i,v in enumerate(c):
        if v>=target: return i
    return len(c)-1

res={}
for y in ("2021","2022"):
    for tid in sorted(gpu["qwen"]["title_cond"][y].keys()):
        base=short[y]["topics"][tid]["shortlist"]; rel=QR[y].get(tid,{})
        ne=sum(1 for v in rel.values() if v==2)
        if not ne: continue
        rk={n:i for i,n in enumerate(base)}
        bc=curve(base,rel)
        cand={"baseline":base}
        for var,tag in (("title_cond","qwen_bucket"),("title_cond_slice","qwen_bucket_slice")):
            lab=gpu["qwen"][var][y].get(tid)
            if lab: cand[tag]=sorted(base,key=lambda n:(-BUCKET.get(lab.get(n,"unsure"),1),rk[n]))
        for qn in ("keywords","raw"):
            sc=ce.get("medcpt_ce",{}).get(qn,{}).get(y,{}).get(tid)
            if sc: cand[f"medcpt_ce_{qn}"]=sorted(base,key=lambda n:(-sc.get(n,-1e9),rk[n]))
        if y=="2021" and tid in llm:
            sc=llm[tid]
            cand["llm_mini_top200"]=sorted(base[:200],key=lambda n:(-sc.get(n,-1),rk[n]))+base[200:]
        for tag,order in cand.items():
            cc=curve(order,rel)
            for d in (100,200,500):
                res.setdefault((y,tag,d),[]).append((d, depth_for(bc, cc[d])))

print("Reading N trials in the reordered list finds as many eligible trials")
print("as reading E trials in the original search order. Same 30-patient sample.\n")
for y in ("2021","2022"):
    print(f"--- {y} ---")
    print("arm".ljust(22)+"".join(f"N={d}".rjust(22) for d in (100,200,500)))
    tags=sorted({t for (yy,t,d) in res if yy==y})
    for tag in tags:
        cells=""
        for d in (100,200,500):
            v=res.get((y,tag,d))
            if not v: cells+="".rjust(22); continue
            e=sum(x[1] for x in v)/len(v)
            cells+=f"= {e:6.0f}  ({1-d/e:+5.0%})".rjust(22)
        print(tag.ljust(22)+cells)
    print()
