import json, random, sys
sys.path.insert(0,"repo/scripts/v3"); sys.path.insert(0,".")
import indirect_payloads as P, business_docs as B
from build_docsets_lib import inject
random.seed(7)
for split, docs, pays in [("dev",B.DEV,P.DEV),("test",B.TEST,P.TEST)]:
    path=f"repo/data/indirect_docs/docs_{split}.jsonl"
    rows=[json.loads(l) for l in open(path,encoding="utf-8")]
    for i,t in enumerate(docs):
        base={"repo":"handwritten/business","url":None,"pair_id":f"{split}-biz-{i}"}
        rows.append({"text":t,"label":0,"source":f"docs_{split}","attack_type":"benign_document",**base})
        cat,pay=random.choice(pays); txt,pos=inject(t,pay,random.choice(P.WRAP_EVAL))
        rows.append({"text":txt,"label":1,"source":f"docs_{split}","attack_type":f"indirect_{cat}","position":pos,**base})
    with open(path,"w",encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
    print(split,len(rows))
