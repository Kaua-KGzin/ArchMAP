"""Task-scoped context retrieval: which files an agent should read for a task.

Given a free-text task ("fix the retry logic in the payment webhook"), rank
the project's files with BM25 over identifier-aware tokens (path segments
weigh more than body text), then spread part of each hit's score to its
direct imports and dependents in the dependency graph — the files an agent
would otherwise discover one ``Read`` at a time. The result is trimmed to a
token budget and each file comes with the reasons it was picked and its best
matching lines, so the agent can often skip reading it entirely.

Pure Python and deterministic: no embeddings, no network, no SQLite FTS5
(not compiled into every Python build, e.g. some Termux packages).
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 512 * 1024
PATH_WEIGHT = 3
NEIGHBOR_SHARE = 0.35
BYTES_PER_TOKEN = 4
_K1 = 1.5
_B = 0.75

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "when", "then", "else",
    "not", "are", "was", "but", "all", "any", "can", "has", "have", "will", "should",
    "fix", "add", "use", "make", "need", "want", "please", "there", "where", "which",
    "self", "return", "import", "def", "class", "const", "let", "var", "function", "true",
    "false", "none", "null", "new", "public", "private", "static", "void", "int", "str",
}


def tokenize(text: str) -> list[str]:
    """Split identifiers on camelCase/snake_case and lowercase them.

    ``parseHTTPResponse`` → parse, http, response, parsehttpresponse — the
    whole identifier is kept too, so exact-name queries still win.
    """
    tokens: list[str] = []
    for word in _WORD.findall(text):
        lower = word.lower()
        parts = [p.lower() for p in _CAMEL.findall(word)]
        if len(parts) > 1 and len(lower) >= 3 and lower not in _STOPWORDS:
            tokens.append(lower)
        for part in parts:
            if len(part) >= 3 and part not in _STOPWORDS:
                tokens.append(_stem(part))
    return tokens


def _stem(token: str) -> str:
    """Tiny suffix stripper so 'retries'/'retrying'/'retry' meet."""
    for suffix in ("ies", "ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            stem = token[: -len(suffix)]
            return stem + "y" if suffix == "ies" else stem
    return token


def _read(root: Path, file_id: str) -> str:
    try:
        with (root / file_id).open("rb") as handle:
            raw = handle.read(MAX_FILE_BYTES)
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace")


def rank_relevant_files(
    report: dict[str, Any],
    task: str,
    *,
    budget_tokens: int = 8000,
    max_files: int = 15,
    snippets_per_file: int = 3,
) -> dict[str, Any]:
    """Rank files for ``task`` and pack them into ``budget_tokens``."""
    root = Path(report["projectRoot"])
    file_nodes = {n["id"]: n for n in report.get("nodes", []) if n.get("type") == "file"}
    query_terms = list(dict.fromkeys(tokenize(task)))
    if not query_terms:
        return {
            "task": task,
            "queryTerms": [],
            "files": [],
            "budgetTokens": budget_tokens,
            "usedTokens": 0,
            "note": "The task text has no searchable terms; describe it with code identifiers.",
        }

    documents: dict[str, Counter[str]] = {}
    texts: dict[str, str] = {}
    for file_id in file_nodes:
        body = _read(root, file_id)
        texts[file_id] = body
        terms = Counter(tokenize(body))
        for term in tokenize(file_id.replace("/", " ").replace(".", " ")):
            terms[term] += PATH_WEIGHT
        documents[file_id] = terms

    total_docs = len(documents) or 1
    avg_len = sum(sum(d.values()) for d in documents.values()) / total_docs
    doc_freq = {t: sum(1 for d in documents.values() if t in d) for t in query_terms}

    lexical: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    for file_id, terms in documents.items():
        length = sum(terms.values()) or 1
        score = 0.0
        hits: list[str] = []
        for term in query_terms:
            tf = terms.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (total_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            score += idf * tf * (_K1 + 1) / (tf + _K1 * (1 - _B + _B * length / avg_len))
            hits.append(term)
        if score > 0:
            lexical[file_id] = score
            matched[file_id] = hits

    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    for edge in report.get("edges", []):
        source, target = edge["source"], edge["target"]
        if source in file_nodes and target in file_nodes:
            outgoing[source].add(target)
            incoming[target].add(source)

    scores: dict[str, float] = dict(lexical)
    via: dict[str, list[str]] = defaultdict(list)
    for file_id, score in lexical.items():
        neighbors = outgoing[file_id] | incoming[file_id]
        if not neighbors:
            continue
        share = score * NEIGHBOR_SHARE / math.sqrt(len(neighbors))
        for neighbor in neighbors:
            scores[neighbor] = scores.get(neighbor, 0.0) + share
            relation = "imported by" if neighbor in outgoing[file_id] else "imports"
            via[neighbor].append(f"{relation} {file_id}")

    risk = {item["file"]: item.get("riskScore", 0) for item in
            report.get("risks", {}).get("top_risk_files", [])}
    ranked = sorted(scores, key=lambda f: (-scores[f], -risk.get(f, 0), f))

    picked: list[dict[str, Any]] = []
    used = 0
    for file_id in ranked:
        if len(picked) >= max_files:
            break
        tokens = max(1, len(texts.get(file_id, "")) // BYTES_PER_TOKEN)
        if used + tokens > budget_tokens and picked:
            continue
        used += tokens
        node = file_nodes[file_id]
        reasons = []
        if file_id in matched:
            reasons.append("matches " + ", ".join(matched[file_id]))
        reasons.extend(sorted(set(via.get(file_id, [])))[:3])
        picked.append({
            "file": file_id,
            "score": round(scores[file_id], 3),
            "role": "match" if file_id in lexical else "neighbor",
            "estimatedTokens": tokens,
            "reasons": reasons,
            "dependents": int(node.get("incoming", 0)),
            "imports": int(node.get("outgoing", 0)),
            "riskScore": risk.get(file_id),
            "snippets": _snippets(texts.get(file_id, ""), query_terms, snippets_per_file),
        })

    return {
        "task": task,
        "queryTerms": query_terms,
        "budgetTokens": budget_tokens,
        "usedTokens": used,
        "candidates": len(scores),
        "files": picked,
        "note": (
            "Read files in order; 'neighbor' files did not match the task text but import "
            "or are imported by a match. Snippets show the best matching lines (1-based)."
        ),
    }


def _snippets(text: str, query_terms: list[str], limit: int) -> list[dict[str, Any]]:
    if not text or limit <= 0:
        return []
    wanted = set(query_terms)
    scored: list[tuple[int, int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        hits = len(wanted.intersection(tokenize(line)))
        if hits:
            scored.append((hits, number, line.strip()[:160]))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [{"line": number, "text": line} for _, number, line in sorted(
        scored[:limit], key=lambda item: item[1]
    )]
