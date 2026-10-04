"""A small vector store over the project's own documentation, for retrieval-augmented answers.

Documents are the docs folder, the data product contracts and the semantic model (one chunk per
measure, so "how is average basket calculated?" finds the definition). Chunks are split on
markdown headings, embedded with TF-IDF over words and word pairs (deterministic, no model
download) and searched by cosine similarity.

Each chunk carries a sensitivity label from the governance catalog. `search` drops chunks above
the caller's clearance before ranking, so a restricted document can never reach a prompt.

In Fabric the same role is played by an Eventhouse vector table or Azure AI Search over OneLake,
with Foundry embeddings; `embed` is the single function to swap."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer

from fabricbi.governance.labels import LABELS, at_most
from fabricbi.paths import CONTRACTS_DIR, DOCS_DIR, ROOT, SEMANTIC_DIR


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    heading: str
    text: str
    label: str = "General"


def chunk_markdown(path: Path, label: str = "General") -> list[Chunk]:
    """Split a markdown file on headings. A `#` line inside a code fence is not a heading, and a
    fenced block under an `<!-- example: ... -->` marker is pasted command output, not prose, so
    it is left out of the index."""
    rel = path.relative_to(ROOT).as_posix()
    out, heading, buf = [], path.stem, []
    in_fence = skip_fence = after_example = False
    for line in path.read_text().splitlines():
        if line.startswith("```"):
            if not in_fence:
                in_fence, skip_fence = True, after_example
            else:
                in_fence = skip_fence = False
                continue
            after_example = False
            if skip_fence:
                continue
            buf.append(line)
            continue
        if in_fence:
            if not skip_fence:
                buf.append(line)
            continue
        after_example = line.startswith("<!-- example:")
        if line.startswith("#"):
            if "".join(buf).strip():
                out.append(Chunk(f"{rel}#{len(out)}", rel, heading, "\n".join(buf).strip(), label))
            heading, buf = line.lstrip("#").strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        out.append(Chunk(f"{rel}#{len(out)}", rel, heading, "\n".join(buf).strip(), label))
    return out


def corpus(doc_labels: dict[str, str] | None = None) -> list[Chunk]:
    doc_labels = doc_labels or {}
    chunks: list[Chunk] = []
    for p in sorted(DOCS_DIR.rglob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        chunks += chunk_markdown(p, doc_labels.get(rel, "General"))
    for p in sorted((CONTRACTS_DIR / "products").glob("*.yaml")):
        spec = yaml.safe_load(p.read_text())
        rel = p.relative_to(ROOT).as_posix()
        text = f"{spec['description']} Owner: {spec['owner']}. Tables: {', '.join(spec['output_ports'])}. Freshness SLO: {spec['slo']['freshness_hours']} hours."
        chunks.append(
            Chunk(f"{rel}#0", rel, f"Data product {spec['name']}", text, spec.get("sensitivity", "General"))
        )
    sem = yaml.safe_load((SEMANTIC_DIR / "retail_sales.yaml").read_text())
    for i, m in enumerate(sem["measures"]):
        text = f"Measure {m['name']}: {m['description']} DAX: {m['dax']}. Also called {', '.join(m['synonyms'])}."
        chunks.append(
            Chunk(
                f"semantic-model/retail_sales.yaml#{i}",
                "semantic-model/retail_sales.yaml",
                f"Measure {m['name']}",
                text,
                "General",
            )
        )
    return chunks


class VectorStore:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), sublinear_tf=True, stop_words="english", min_df=1
        )
        self.matrix = self.vectorizer.fit_transform([f"{c.heading}. {c.text}" for c in chunks])

    @classmethod
    def build(cls, doc_labels: dict[str, str] | None = None) -> VectorStore:
        return cls(corpus(doc_labels))

    def embed(self, text: str):
        return self.vectorizer.transform([text])

    def search(self, query: str, k: int = 3, clearance: str = "General") -> list[tuple[Chunk, float]]:
        if clearance not in LABELS:
            raise ValueError(f"unknown clearance {clearance!r}")
        q = self.embed(re.sub(r"\s+", " ", query))
        scores = (self.matrix @ q.T).toarray().ravel()
        allowed = np.array([at_most(c.label, clearance) for c in self.chunks])
        scores = np.where(allowed, scores, -1.0)
        order = np.argsort(-scores, kind="stable")[:k]
        return [(self.chunks[i], round(float(scores[i]), 4)) for i in order if scores[i] > 0]
