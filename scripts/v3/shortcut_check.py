"""Shortcut check: TF-IDF + logistic regression on the training pool.
If this simple model scores near DeBERTa in-distribution but much lower on
Agentic-5K, the training data carries surface shortcuts.
Usage (from E:\\SecureRAG): python scripts\\v3\\shortcut_check.py"""
import json, sys, time, collections
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, accuracy_score, roc_auc_score
D="data/"  # run from E:\\SecureRAG
def rows(p): return [json.loads(l) for l in open(p,encoding="utf-8") if l.strip()]
tr=rows(D+"processed/train.jsonl"); va=rows(D+"processed/validation.jsonl")
# de-duplicate oversampled copies
seen=set(); tr2=[]
for r in tr:
    if r["text"] not in seen: seen.add(r["text"]); tr2.append(r)
print("train rows",len(tr),"distinct",len(tr2))
print("label by source:",{s:dict(collections.Counter(r["label"] for r in tr2 if r["source"]==s)) for s in sorted({r["source"] for r in tr2})})
ag=rows(D+"held_out_eval/agentic_5k.jsonl"); ni=rows(D+"held_out_eval/notinject.jsonl")
t=time.time()
vec=TfidfVectorizer(ngram_range=(1,2),min_df=3,max_features=300000,sublinear_tf=True,lowercase=True)
X=vec.fit_transform([r["text"] for r in tr2]); y=np.array([r["label"] for r in tr2])
clf=LogisticRegression(max_iter=2000,C=4.0,solver="liblinear").fit(X,y)
def ev(name,rs):
    p=clf.predict_proba(vec.transform([r["text"] for r in rs]))[:,1]; yy=np.array([r["label"] for r in rs]); pr=(p>=.5).astype(int)
    out={"acc":round(accuracy_score(yy,pr),4)}
    if len(set(yy))>1: out|={"f1":round(f1_score(yy,pr),4),"macro_f1":round(f1_score(yy,pr,average="macro"),4),"roc_auc":round(roc_auc_score(yy,p),4)}
    else: out["fpr"]=round(pr.mean(),4)
    print(f"{name:22s}",out)
ev("validation (in-dist)",va)
for s in sorted({r["source"] for r in va}): ev("  val/"+s,[r for r in va if r["source"]==s])
ev("Agentic-5K",ag); ev("NotInject (benign)",ni)
# top features
names=np.array(vec.get_feature_names_out()); co=clf.coef_[0]
print("top MALICIOUS features:",list(names[np.argsort(co)[-30:]][::-1]))
print("top SAFE features:",list(names[np.argsort(co)[:30]]))
print("secs",round(time.time()-t))
