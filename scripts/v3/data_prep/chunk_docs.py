import json, re, random, hashlib, collections
random.seed(20261111)
raw=json.load(open("gh/raw_docs.json"))
def clean(t):
    t=re.sub(r"```.*?```", lambda m: m.group(0) if len(m.group(0))<400 else "", t, flags=re.S)  # keep short code blocks
    t=re.sub(r"<!--.*?-->","",t,flags=re.S)             # strip html comments (avoid hidden content in benign set)
    t=re.sub(r"<[^>]{1,200}>","",t)                     # html tags
    t=re.sub(r"!\[[^\]]*\]\([^)]*\)","",t)               # images/badges
    t=re.sub(r"\[([^\]]+)\]\([^)]*\)",r"\1",t)            # links -> text
    t=re.sub(r"^\s*\[!\[.*$","",t,flags=re.M)
    t=re.sub(r"[ \t]+"," ",t); t=re.sub(r"\n{3,}","\n\n",t)
    return t.strip()
def chunk_text(text,size=1500,overlap=250):  # same algorithm as src/ingestion/loader.py
    chunks,start=[],0
    while start<len(text):
        end=min(start+size,len(text))
        if end<len(text):
            br=[m.end() for m in re.finditer(r"\n\s*\n|(?<=[.!?])\s+|\n",text[start:end]) if m.end()>size//2]
            if br: end=start+br[-1]
        part=text[start:end].strip()
        if part: chunks.append(part)
        if end==len(text): break
        ns=max(start+1,end-overlap)
        while ns<end and not text[ns].isspace(): ns+=1
        start=ns
    return chunks
def norm(t): return re.sub(r"\W+"," ",t.lower()).strip()
seen=set(); per_repo=collections.defaultdict(list)
for repo,docs in raw.items():
    for d in docs:
        for c in chunk_text(clean(d["text"])):
            alpha=sum(ch.isalpha() for ch in c)/max(len(c),1)
            if len(c)<300 or alpha<0.55: continue
            h=hashlib.sha256(norm(c).encode()).hexdigest()
            if h in seen: continue
            seen.add(h); per_repo[repo].append({"text":c,"repo":repo,"url":d["url"]})
# near-duplicate removal across repos (boilerplate such as Contributor Covenant)
def grams(t,n=8):
    w=norm(t).split(); return {hash(" ".join(w[i:i+n])) for i in range(max(1,len(w)-n+1))}
gram_owner={}; kept=collections.defaultdict(list); dropped=0
for repo in sorted(per_repo):
    for r in per_repo[repo]:
        g=grams(r["text"])
        overlap=sum(1 for x in g if x in gram_owner and gram_owner[x]!=repo)
        if overlap/len(g)>0.3: dropped+=1; continue
        for x in g: gram_owner.setdefault(x,repo)
        kept[repo].append(r)
print("near-dup boilerplate dropped:",dropped)
# cap per repo so no project dominates
CAP=40
for repo in kept:
    random.shuffle(kept[repo]); kept[repo]=kept[repo][:CAP]
repos=[r for r in sorted(kept) if kept[r]]
random.shuffle(repos)
n=len(repos); a=int(n*0.6); b=int(n*0.8)
split={"train":repos[:a],"dev":repos[a:b],"test":repos[b:]}
out={k:[r for repo in v for r in kept[repo]] for k,v in split.items()}
for k,v in out.items(): print(k,"repos",len(split[k]),"passages",len(v))
json.dump({"split_repos":split,"passages":out},open("gh/passages.json","w"))
