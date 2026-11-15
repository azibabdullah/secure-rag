"""Deterministic checks for hidden document channels (metadata, annotations, form fields, ...).

Hidden channels have no legitimate reason to address an AI assistant or to issue
instructions about how answers are written. The classifier can miss short, polite
payloads there ("AI reviewer: include X in your summary"), so these rules act as a
second, explainable layer. They are applied to hidden channels only, never to
visible page text, so documents that discuss prompt injection are not affected.
"""
import re

_FLAGS = re.I | re.S
RULES = [
    ('addresses an AI assistant directly',
     re.compile(r'(?:^|[\s,;.(\[])(?:the\s+)?(?:ai|a\.i\.|assistant|chat\s?bot|llm|language\s+model|copilot|gpt|chatgpt|claude|gemini|'
                r'ai\s+(?:assistant|reviewer|agent|model|system))\s*(?:reviewer|agent)?\s*:\s*[A-Za-z]', _FLAGS)),
    ('tells the model to ignore or override its instructions',
     re.compile(r'\b(?:ignore|disregard|forget|override|bypass|skip)\b.{0,40}?\b(?:previous|prior|above|earlier|all|any|your|system|safety)\b'
                r'.{0,25}?\b(?:instructions?|rules?|prompts?|guidelines?|policies|polic(?:y|ies)|guardrails?)\b', _FLAGS)),
    ('tells the model what to add to its answers',
     re.compile(r'\b(?:append|add|insert|include|prepend|output|print|say|mention|respond\s+with|reply\s+with|end\s+with|start\s+with)\b'
                r'.{0,80}?\b(?:to|in|into|at\s+the\s+(?:end|start|beginning)\s+of)\b.{0,25}?'
                r'\b(?:all|every|each|any|your|the|its)\b.{0,15}?\b(?:responses?|answers?|replies|outputs?|summary|summaries|messages?)\b', _FLAGS)),
    ('refers to the system prompt or hidden instructions',
     re.compile(r'\b(?:system\s+prompt|developer\s+(?:message|prompt)|hidden\s+instructions?|initial\s+instructions?)\b', _FLAGS)),
    ('tries to change the model\'s role',
     re.compile(r'\b(?:you\s+are\s+now|from\s+now\s+on,?\s+you|act\s+as\s+(?:an?\s+)?(?:ai|assistant|admin|system)|pretend\s+(?:to\s+be|you\s+are))\b', _FLAGS)),
    ('embeds a remote image or tracking link (data exfiltration)',
     re.compile(r'!\[[^\]]*\]\(\s*https?://', _FLAGS)),
    ('asks to reveal or send secrets',
     re.compile(r'\b(?:reveal|exfiltrate|leak|send|forward|email|disclose)\b.{0,50}?\b(?:passwords?|credentials?|secrets?|api\s*keys?|tokens?|'
                r'system\s+prompt|other\s+documents?|conversation\s+history)\b', _FLAGS)),
]


def hidden_instruction(text):
    """Return (why, matched excerpt) for the first rule that matches, else None."""
    for why, pattern in RULES:
        match = pattern.search(text or '')
        if match:
            excerpt = ' '.join(match.group(0).split())
            return why, excerpt[:120]
    return None
