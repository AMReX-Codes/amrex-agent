# REMORA Demo

## Basic smoke test (override_static)

Use a baseline override with a simple prompt so the run focuses on inputs reuse.

```bash
python amrex_agent.py \
  --baseline-override "REMORA/Exec/Upwelling" \
  --indexing-strategy override_static \
  --prompt "Run the REMORA Upwelling case to demonstrate wind-driven upwelling over a periodic channel."
```
