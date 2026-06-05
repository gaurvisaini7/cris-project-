# cris-project-
 OHE Symbol Classifier

This code follows the classifier shown in the workflow slide.

## Classifier Used

The main working classifier is:

```text
Layer 1 - Regex/rule-based classifier
```

It also includes:

```text
Layer 2 - ML fallback placeholder for BERT or scikit-learn
Layer 3 - Human review queue
```

The ML layer is only a placeholder until a labelled OHE dataset is available.

## Rules

```text
CB-*  -> CB
SM-*  -> SPI_Remote
BM-*  -> AnchorMast
SS-*  -> SectionInsulator
X-*   -> SP
TSS   -> FP
```

Extra GP diagram rules are also included:

```text
E/S-* -> ElementarySection
L-*   -> LineTrack
BX-*  -> BusSection
S-*   -> SignalPosition
SH-*  -> ShuntSignal
BS-*  -> BufferStop
```

## Run Demo

```bash
python3 symbol_classifier_backend.py
```

## Run API

```bash
pip install -r requirements.txt
uvicorn symbol_classifier_backend:app --reload
```

Then test:

```bash
curl -X POST http://127.0.0.1:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"labels":["CB-23","SM-161","BM-170","SS-277","UNKNOWN-1"]}'
```

