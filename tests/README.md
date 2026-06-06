# tests/ — verification addendum (not part of the original notebook)

Everything in this folder was **added during the June 2026 refresh**, not part
of the original summer-2025 notebook. It exists to prove the strategy code in
`src/` behaves correctly — it does not change any of the strategy logic.

| File | What it does | Needs network? |
| --- | --- | --- |
| `test_strategies.py` | Unit tests on tiny hand-made inputs that assert exact PnL / exit prices. Pins down the two bug fixes. | No |
| `smoke_real_data.py` | Runs both strategies once on live Yahoo Finance data to confirm they execute end-to-end. | Yes |

Run the unit tests (fast, offline):

```bash
pytest tests/test_strategies.py -v
```

Run the live smoke test:

```bash
python tests/smoke_real_data.py
```
