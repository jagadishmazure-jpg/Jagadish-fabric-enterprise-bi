# Enrichment: demand forecast and ticket classification

**Purpose.** Two pieces of machine learning add columns that the business asks for but the source
systems do not have: a seven-day sales forecast per store and category, and a category for every
customer-support ticket. Both write gold tables that sit in data products, and both have an eval
gate that blocks a release if quality drops.

## Architecture

```mermaid
flowchart LR
  subgraph Forecast
    A[(gold.agg_daily_sales)] --> F[features: lag7, lag14, lag21,<br/>mean7_lag7, dow, store, category, size]
    F --> M[GradientBoostingRegressor]
    M --> BT{beats same weekday<br/>last week on 14 days?}
    BT --> FS[(gold.forecast_sales)]
  end
  subgraph Tickets
    T[(silver.support_tickets<br/>redacted)] --> P[prompt: system rules + few-shot<br/>ticket fenced as data]
    P --> C[Foundry chat model<br/>JSON schema response]
    C --> V{valid?}
    V -->|yes, confidence >= 0.6| FT[(gold.fact_ticket)]
    V -->|yes, low confidence| R[needs_review]
    V -->|malformed| RT[retry once] --> V
    V -->|steered: extra field or unknown label| R
    R --> FT
  end
```

## How it works: demand forecast

1. `features()` builds a complete store x category x day grid from the daily aggregate (missing
   days become zero sales) and adds the features. Every feature is known seven days before the
   target day: lags of 7, 14 and 21 days, a 7-day mean that ends a week earlier, the weekday, the
   store key and size, and a category code.
2. Rows without 21 days of history are dropped.
3. The last 14 days are the hold-out; everything before is training data.
4. A gradient-boosted regressor is trained; negative predictions are clipped to zero.
5. WAPE (total absolute error divided by total actual sales) is computed for the model and for
   the seasonal naive baseline, which is "same weekday last week" (`lag7`).
6. `ForecastResult.passed` is true only if the model beats the baseline. Hold-out predictions
   are written to `gold.forecast_sales`, the output port of the `demand-forecast` product.
7. [`scripts/model_card.py`](../scripts/model_card.py) regenerates the
   [model card](model-card-demand-forecast.md) from a real run.

## How it works: ticket classification

1. Silver has already removed emails and phone numbers from the ticket text.
2. `build_messages()` puts the rules in the system message, adds two worked examples, and wraps
   the ticket in `<ticket>` tags as data. The system prompt says text inside a ticket is never
   an instruction.
3. The client is called with a JSON schema response format: label from a closed set of five,
   confidence 0 to 1, an optional short rationale, no other fields.
4. `validate()` parses and checks the reply. A valid reply with confidence below 0.6 is kept but
   flagged for review.
5. Malformed JSON is retried once, then routed to review.
6. A reply with an extra field (such as `action`) or a label outside the set means the ticket text
   steered the model. It goes straight to a person and is **not** retried, because the same input
   would steer it again.
7. Results land in `gold.fact_ticket` with `category`, `confidence` and `needs_review`.

## Key files

| File | What it does |
|---|---|
| [`enrich/forecast.py`](../src/fabricbi/enrich/forecast.py) | Features, training, backtest, WAPE, `ForecastResult` |
| [`enrich/tickets.py`](../src/fabricbi/enrich/tickets.py) | Prompt, schema, validation, retry and review routing |
| [`enrich/foundry_mock.py`](../src/fabricbi/enrich/foundry_mock.py) | Deterministic stand-in for a Foundry chat deployment, with an injection and a failure mode |
| [`scripts/model_card.py`](../scripts/model_card.py) | Writes the model card from a run; `--check` fails if it is stale |
| [`docs/model-card-demand-forecast.md`](model-card-demand-forecast.md) | Generated model card |

## Code excerpts

The model's parameters and the gate:

<!-- excerpt: src/fabricbi/enrich/forecast.py -->
```python
HORIZON_DAYS = 7
HOLDOUT_DAYS = 14
FEATURES = ["lag7", "lag14", "lag21", "mean7_lag7", "dow", "store_key", "cat_code", "square_meters"]
```

<!-- excerpt: src/fabricbi/enrich/forecast.py -->
```python
    @property
    def passed(self) -> bool:
        return self.wape_model < self.wape_naive
```

A steered answer is not retried:

<!-- excerpt: src/fabricbi/enrich/tickets.py -->
```python
        if reason.startswith("unexpected_fields") or reason == "label_not_allowed":
            break  # a steered answer is not retried; it goes straight to a person
    return Classification(ticket_id, "needs_review", 0.0, True, attempt, reason)
```

## Configuration and parameters

| Parameter | Value | Where |
|---|---|---|
| Horizon / hold-out | 7 days / 14 days | `HORIZON_DAYS`, `HOLDOUT_DAYS` |
| Model | `n_estimators=250`, `max_depth=3`, `learning_rate=0.05`, `subsample=0.9`, `random_state=0` | `MODEL_PARAMS` |
| Ticket labels | billing, product_quality, delivery, store_experience, loyalty | `LABELS` |
| Review threshold | confidence below 0.6 | `REVIEW_BELOW` |
| Attempts | 2 (one retry) | `classify(max_attempts=2)` |
| Mock failure injection | `MockFoundryChatClient(fail_every=n)` | malformed reply on every n-th call |

## Run it locally

```bash
python -m fabricbi.examples forecast
python -m fabricbi.examples tickets
python scripts/model_card.py --check     # fails if the model card no longer matches a fresh run
```

<!-- example: forecast -->
```text
hold-out WAPE: model 0.3125, naive (same weekday last week) 0.3933
improvement: 20.5%, gate passed: True
predictions written to gold.forecast_sales: 1,176 rows, columns ['store_key', 'category', 'date', 'net_sales', 'lag7', 'forecast']
```

<!-- example: tickets -->
```text
classified 120 tickets: {'billing': 24, 'delivery': 24, 'loyalty': 24, 'product_quality': 24, 'store_experience': 24}
sent to review: 0
normal ticket     -> label=billing review=False attempts=1 reason=-
injection         -> label=needs_review review=True attempts=1 reason=unexpected_fields:action
one bad reply     -> label=billing review=False attempts=2 reason=-
always malformed  -> label=needs_review review=True attempts=2 reason=invalid_json
```

1,176 forecast rows are 12 stores x 7 categories x 14 hold-out days.

## Tests and eval gates

[`tests/test_06_lambda_forecast_tickets.py`](../tests/test_06_lambda_forecast_tickets.py):

| Test | Checks |
|---|---|
| `test_forecast_beats_naive` | the gate passes and the improvement is above 10% |
| `test_forecast_predictions_cover_holdout` | the gold table has the expected columns and no missing forecasts |
| `test_wape_definition` | WAPE on two hand-worked cases; horizon is 7 |
| `test_ticket_classifier_matches_labels` | at least 90% agree with the generator's labels |
| `test_prompt_fences_ticket_as_data` | ticket text is in the last user message, never in the system prompt |
| `test_injection_is_routed_to_review_not_retried` | an injection ends in review |
| `test_malformed_output_is_retried_then_reviewed` | one bad reply is retried and succeeds; always-bad replies end in review |
| `test_validate_rejects_extra_fields_and_unknown_labels` | extra field, unknown label, confidence above 1, broken JSON |

Eval gates ([`evals/thresholds.yaml`](../evals/thresholds.yaml)): `forecast_beats_naive: true`,
`ticket_accuracy` at least 0.85, `ticket_injection_routed_to_review` 1.0.

## Guardrails, security and governance

- Personal data is removed before the text reaches the model.
- The model's answer can only be a label and a confidence; anything that looks like an action
  fails validation. The model never triggers a refund, an email or any other side effect.
- Low-confidence and rejected answers are kept in the table with `needs_review = true`, so
  reviewers can find them, and they are not silently dropped.
- The forecast and the ticket classifier are recorded in lineage as `ml.demand_forecast` and
  `ml.ticket_classifier`, so a model change shows up in impact analysis.

## Observability

Spans `enrich.tickets` (attribute `gen_ai.system=foundry-mock`) and `enrich.forecast`
(`ml.framework=scikit-learn`). The share of tickets with `needs_review` is a column in gold and
can be charted in the semantic model.

## Failure modes

| Failure | Handling |
|---|---|
| Model returns broken or truncated JSON | Retried once, then review (`invalid_json`) |
| Ticket text tries to steer the model | Rejected by validation, not retried, review (`unexpected_fields:action`) |
| Model is unsure | Kept with `needs_review` when confidence is below 0.6 |
| Forecast gets worse than the naive baseline | `forecast_beats_naive` gate fails and CI stops |
| New store or category with little history | Rows without 21 days of history are not scored |
| Model card drifts from the code | `model_card.py --check` fails in CI |

## On real Fabric

| Here | In Fabric / Azure |
|---|---|
| `forecast.py` | A Fabric Data Science notebook that trains with scikit-learn and logs to an ML experiment and model in the workspace, or an Azure ML job reading gold through a OneLake shortcut |
| `gold.forecast_sales` | Batch scoring with the PREDICT function or a notebook into the Lakehouse |
| `MockFoundryChatClient` | A chat model deployment in a Microsoft Foundry project, called with Entra ID through a managed identity, never an API key. The Foundry project is not in the IaC yet (see Limitations) |
| Prompt and schema | Same messages and `response_format`, sent with the OpenAI or `azure-ai-inference` SDK |
| Ticket accuracy gate | Foundry evaluations on a labelled set before a prompt or model change is promoted |

## Limitations

- The ticket classifier is a keyword scorer that imitates a chat model. Its accuracy measures the
  harness on templated synthetic text, not a real model.
- The forecast is a single global model over 56 days of synthetic sales, with no holidays,
  promotions or weather. It forecasts the hold-out window only and is not retrained on a schedule.
- No drift monitoring on inputs or predictions yet.
- The Bicep and Terraform do not provision a Foundry project or model deployment; that is planned work.
