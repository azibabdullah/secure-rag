"""Builds the indirect-injection document sets (train / dev / test) from real
GitHub documentation passages. Each passage appears once as benign (label 0)
and once with an injected payload (label 1): minimal pairs. Projects, payloads
and wrappers are disjoint between splits."""
import json, random, re, sys
sys.path.insert(0, "repo/scripts/v3")
import indirect_payloads as P
random.seed(20261111)
d = json.load(open("gh/passages.json"))
def linky(t):
    urls = sum(len(m) for m in re.findall(r"https?://\S+", t))
    refs = len(re.findall(r"^\s*\[[^\]]+\]:\s*\S+", t, flags=re.M))
    return urls / max(len(t), 1) > 0.25 or refs >= 5
def inject(text, payload, wrapper):
    sents = [m.end() for m in re.finditer(r"(?<=[.!?])\s+|\n\n", text)]
    w = wrapper.format(p=payload)
    r = random.random()
    if r < 0.2 or not sents: return w + "\n\n" + text, "start"
    if r < 0.7:
        cut = random.choice(sents)
        return text[:cut] + w + "\n\n" + text[cut:], "middle"
    return text.rstrip() + "\n\n" + w, "end"
pools = {"train": (P.TRAIN, P.WRAP_TRAIN), "dev": (P.DEV, P.WRAP_EVAL), "test": (P.TEST, P.WRAP_EVAL)}
for split, rows in d["passages"].items():
    pays, wraps = pools[split]
    out = []
    for i, r in enumerate(x for x in rows if not linky(x["text"])):
        base = {"repo": r["repo"], "url": r["url"], "pair_id": f"{split}-{i}"}
        out.append({"text": r["text"], "label": 0, "source": f"docs_{split}", "attack_type": "benign_document", **base})
        cat, pay = random.choice(pays)
        txt, pos = inject(r["text"], pay, random.choice(wraps))
        out.append({"text": txt, "label": 1, "source": f"docs_{split}", "attack_type": f"indirect_{cat}", "position": pos, **base})
    path = f"repo/data/indirect_docs/docs_{split}.jsonl"
    import os; os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for o in out: f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(split, len(out), "rows ->", path)
