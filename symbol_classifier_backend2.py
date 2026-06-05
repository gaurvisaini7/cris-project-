"""
OHE Symbol Classifier Backend

Architecture from the workflow slide:
  Layer 1 - Regex/rule engine
  Layer 2 - ML fallback model, BERT/scikit-learn placeholder
  Layer 3 - Human review queue for low-confidence/unknown labels


"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from fastapi import FastAPI
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).parent
SYMBOL_LIBRARY_PATH = BASE_DIR / "symbol_library.json"
CONFIDENCE_THRESHOLD = 0.85


@dataclass(frozen=True)
class Rule:
    pattern: str
    symbol_type: str
    confidence: float
    description: str


@dataclass(frozen=True)
class ClassificationResult:
    label: str
    normalized_label: str
    symbol_type: str | None
    confidence: float
    layer: str
    status: str
    reason: str


class ClassifyRequest(BaseModel):
    labels: list[str] = Field(default_factory=list)


class ClassifyResponse(BaseModel):
    classifications: list[dict]
    review_queue: list[dict]
    summary: dict


class SymbolLibrary:
    """Verified label-to-symbol mappings.

    This is optional but useful. If a symbol has already been corrected by an
    engineer, the classifier can return it directly with 100% confidence.
    """

    def __init__(self, path: Path):
        self.path = path
        self.mappings: dict[str, str] = {}
        if self.path.exists():
            self.mappings = json.loads(self.path.read_text())

    def lookup(self, label: str) -> str | None:
        return self.mappings.get(normalize_label(label))

    def save_verified(self, label: str, symbol_type: str) -> None:
        self.mappings[normalize_label(label)] = symbol_type
        self.path.write_text(json.dumps(self.mappings, indent=2, sort_keys=True))


class RuleEngine:
    """Layer 1: deterministic regex/prefix rules."""

    def __init__(self):
        self.rules = [
            Rule(r"^CB[- ]?\d+[A-Z]?$", "CB", 0.99, "CB-* -> CB"),
            Rule(r"^SM-\d+[A-Z]?$", "SPI_Remote", 0.99, "SM-* -> SPI_Remote"),
            Rule(r"^BM-\d+\s*N?$", "AnchorMast", 0.99, "BM-* -> AnchorMast"),
            Rule(r"^SS-\d+(?:\(N/O\))?$", "SectionInsulator", 0.99, "SS-* -> SectionInsulator"),
            Rule(r"^X-\d+$", "SP", 0.95, "X-* -> SP"),
            Rule(r".*TSS.*", "FP", 0.90, "Text containing TSS -> FP"),
            Rule(r"^E/S-\d+[A-Z]?$", "ElementarySection", 0.96, "E/S-* -> ElementarySection"),
            Rule(r"^L-\d+$", "LineTrack", 0.94, "L-* -> LineTrack"),
            Rule(r"^BX-\d+$", "BusSection", 0.90, "BX-* -> BusSection"),
            Rule(r"^S-\d+$", "SignalPosition", 0.88, "S-* -> SignalPosition"),
            Rule(r"^SH-\d+$", "ShuntSignal", 0.88, "SH-* -> ShuntSignal"),
            Rule(r"^BS-\d+$", "BufferStop", 0.88, "BS-* -> BufferStop"),
        ]

    def classify(self, label: str) -> tuple[str, float, str] | None:
        normalized = normalize_label(label)
        for rule in self.rules:
            if re.match(rule.pattern, normalized, flags=re.IGNORECASE):
                return rule.symbol_type, rule.confidence, rule.description
        return None


class MLClassifier:
    """Layer 2: placeholder for BERT or scikit-learn fallback.

    Replace `predict()` with:
      - scikit-learn model.predict_proba(...)
      - fine-tuned BERT inference

    Right now this is intentionally conservative. It only demonstrates where
    the ML layer plugs in.
    """

    def predict(self, label: str) -> tuple[str, float] | None:
        normalized = normalize_label(label)

        if "INSULATOR" in normalized:
            return "SectionInsulator", 0.78
        if "ISOLATOR" in normalized:
            return "Isolator", 0.76
        if "TRANSFORMER" in normalized:
            return "AuxiliaryTransformer", 0.80

        return None


class SymbolClassifier:
    def __init__(
        self,
        symbol_library: SymbolLibrary,
        rule_engine: RuleEngine,
        ml_classifier: Callable[[str], tuple[str, float] | None] | None = None,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ):
        self.symbol_library = symbol_library
        self.rule_engine = rule_engine
        self.ml_classifier = ml_classifier
        self.confidence_threshold = confidence_threshold

    def classify(self, label: str) -> ClassificationResult:
        normalized = normalize_label(label)

        verified_type = self.symbol_library.lookup(normalized)
        if verified_type:
            return ClassificationResult(
                label=label,
                normalized_label=normalized,
                symbol_type=verified_type,
                confidence=1.0,
                layer="Symbol Library",
                status="classified",
                reason="Previously verified label-to-type mapping.",
            )

        rule_result = self.rule_engine.classify(normalized)
        if rule_result:
            symbol_type, confidence, reason = rule_result
            return self._with_threshold(label, normalized, symbol_type, confidence, "Layer 1 - Regex Rules", reason)

        if self.ml_classifier:
            ml_result = self.ml_classifier(normalized)
            if ml_result:
                symbol_type, confidence = ml_result
                return self._with_threshold(
                    label,
                    normalized,
                    symbol_type,
                    confidence,
                    "Layer 2 - ML Model",
                    "Fallback ML prediction.",
                )

        return ClassificationResult(
            label=label,
            normalized_label=normalized,
            symbol_type=None,
            confidence=0.0,
            layer="Layer 3 - Human Review",
            status="needs_review",
            reason="No regex rule or confident ML prediction matched.",
        )

    def classify_many(self, labels: list[str]) -> list[ClassificationResult]:
        return [self.classify(label) for label in labels]

    def _with_threshold(
        self,
        label: str,
        normalized: str,
        symbol_type: str,
        confidence: float,
        layer: str,
        reason: str,
    ) -> ClassificationResult:
        if confidence < self.confidence_threshold:
            return ClassificationResult(
                label=label,
                normalized_label=normalized,
                symbol_type=symbol_type,
                confidence=confidence,
                layer="Layer 3 - Human Review",
                status="needs_review",
                reason=f"{reason} Confidence is below {self.confidence_threshold}.",
            )

        return ClassificationResult(
            label=label,
            normalized_label=normalized,
            symbol_type=symbol_type,
            confidence=confidence,
            layer=layer,
            status="classified",
            reason=reason,
        )


def normalize_label(label: str) -> str:
    normalized = " ".join(str(label).strip().upper().split())
    normalized = re.sub(r"^CB\s+(\d+[A-Z]?)$", r"CB-\1", normalized)
    return normalized


def build_response(results: list[ClassificationResult]) -> dict:
    classifications = [asdict(result) for result in results]
    review_queue = [item for item in classifications if item["status"] == "needs_review"]

    return {
        "classifications": classifications,
        "review_queue": review_queue,
        "summary": {
            "total": len(classifications),
            "classified": sum(item["status"] == "classified" for item in classifications),
            "needs_review": len(review_queue),
        },
    }


symbol_library = SymbolLibrary(SYMBOL_LIBRARY_PATH)
rule_engine = RuleEngine()
ml_model = MLClassifier()
classifier = SymbolClassifier(
    symbol_library=symbol_library,
    rule_engine=rule_engine,
    ml_classifier=ml_model.predict,
)

app = FastAPI(title="OHE Symbol Classifier", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ohe-symbol-classifier"}


@app.post("/classify", response_model=ClassifyResponse)
async def classify_symbols(request: ClassifyRequest):
    results = classifier.classify_many(request.labels)
    return build_response(results)


@app.post("/verify")
async def verify_symbol(label: str, symbol_type: str):
    symbol_library.save_verified(label, symbol_type)
    return {"status": "saved", "label": normalize_label(label), "symbol_type": symbol_type}


if __name__ == "__main__":
    sample_labels = [
        "CB-23",
        "SM-161",
        "BM-170",
        "SS-277",
        "X-180",
        "E/S-1732",
        "AUX TRANSFORMER",
        "UNKNOWN-1",
    ]
    sample_results = classifier.classify_many(sample_labels)
    print(json.dumps(build_response(sample_results), indent=2))
