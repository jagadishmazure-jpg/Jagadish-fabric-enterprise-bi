# Cold path: medallion Lakehouse, mirroring and quality

## Ingest

**Copy jobs (bronze.py).** Each source file is copied into `Files/landing/<source>/` and
recorded in a manifest by content hash. Landing the same file twice is a no-op, so a re-run
pipeline cannot double-load a day. Bronze reads every column as text and adds `_source_file`,
`_batch_id` and `_row_hash`; typing waits for silver, so a bad value never stops ingest.

**Mirroring (mirroring.py).** The operational database (stores and loyalty members) is
replicated, not copied in batches. Each insert, update and delete is written to a change log with
a log sequence number (LSN) in the same transaction as the change. The replica reads changes after
its checkpoint, applies them in LSN order (upsert by key, delete by key) and only then moves the
checkpoint. Because an upsert of the same row is harmless, a crash between applying and saving the
checkpoint just means the next sync applies the same changes again with the same result. The
replication lag (change-log entries not yet applied) is reported after each sync.

**Shortcuts.** Silver reads the mirrored tables through internal OneLake shortcuts rather than
copying them, so there is one physical copy of member data.

## Silver rules

| Table | Rule | On failure |
|---|---|---|
| pos_lines | exact duplicate line | dropped, counted as `dedupe:exact_duplicate` |
| pos_lines | quantity between 1 and 50 | quarantined (`range:qty`) |
| pos_lines | SKU exists in the catalog | quarantined (`fk:sku->products`) |
| pos_lines | store exists | quarantined (`fk:store_id->stores`) |
| products | price stored as text | coerced, counted as a warning |
| products | missing category | kept as `Unassigned`, counted as a warning (sales are not lost) |
| freezer_readings | temperature between -40 and 15 C | quarantined |
| support_tickets | emails and phone numbers | redacted before the row is written |

Quarantined rows keep the name of the rule they broke. The pipeline's quality gate fails if more
than 2% of a table's rows are quarantined (`DqReport.passed`).

## Schema contracts

Every gold table and the key silver tables have a YAML contract in
[`contracts/schemas`](../contracts/schemas): columns, logical types, nullability, uniqueness,
accepted values, ranges and the primary key. A write that breaks its contract raises before the
file is replaced. `contracts.compatibility(old, new)` classifies a contract change as breaking
(removed column, changed type, newly required column, changed key) or additive, which decides the
data product's next version (major or minor).

## Gold star schema

`gold.py` assigns dense surrogate keys in a stable order, so rebuilding from the same silver data
gives the same keys. Guest checkouts and members deleted at the source map to customer key -1.
Every fact row's keys resolve to a dimension row; `tests/test_gold.py` checks that.
