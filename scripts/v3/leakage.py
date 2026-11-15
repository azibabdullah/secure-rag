"""Shared leakage checks: normalised exact-hash match plus word 6-gram containment.
An evaluation item counts as leaked into a training row when the normalised
texts match, or when the training row contains >= 50% of the evaluation item's
6-grams AND the two texts share >= 60% of their distinct words (Jaccard). The
second condition stops short questions that merely share an opening phrase
from being counted as copies."""
import hashlib
import re
from collections import defaultdict

N = 6
THRESHOLD = 0.5
JACCARD = 0.6


def norm(text):
    return re.sub(r"\W+", " ", str(text).lower()).strip()


def text_hash(text):
    return hashlib.sha256(norm(text).encode("utf-8")).hexdigest()


def grams(text, n=N):
    words = norm(text).split()
    if len(words) < n:
        return set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


class EvalIndex:
    """Index of evaluation items, used to scan large training pools."""

    def __init__(self, items):
        self.items = list(items)               # dicts with 'text' and 'set'
        self.hashes = {}
        self.gram_to_ids = defaultdict(list)
        self.gram_counts = []
        self.wordsets = []
        for i, it in enumerate(self.items):
            self.wordsets.append(set(norm(it["text"]).split()))
            self.hashes.setdefault(text_hash(it["text"]), i)
            g = grams(it["text"])
            self.gram_counts.append(len(g))
            for x in g:
                self.gram_to_ids[x].append(i)

    def leaks(self, text):
        """Return indices of evaluation items that this training text leaks."""
        hits = set()
        h = text_hash(text)
        if h in self.hashes:
            hits.add(self.hashes[h])
        counts = defaultdict(int)
        for x in grams(text):
            for i in self.gram_to_ids.get(x, ()):
                counts[i] += 1
        if counts:
            words = set(norm(text).split())
            for i, c in counts.items():
                if self.gram_counts[i] and c / self.gram_counts[i] >= THRESHOLD:
                    ws = self.wordsets[i]
                    if len(words & ws) / max(len(words | ws), 1) >= JACCARD:
                        hits.add(i)
        return hits
