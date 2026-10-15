# Repository working instructions

- Use subagents for independent research, implementation, or review when practical.
- Write for an experienced software engineer using clear, active English; define unfamiliar specialist terms.
- Use primary ACFE sources for fraud-examination methods and the specified IBM paper for dataset claims. Distinguish sourced guidance from our configurable engineering heuristics.
- Treat outputs as review leads. Never infer shell status, guilt, employment, or losses from IBM laundering labels.
- Keep source data, local databases, credentials, and generated case reports out of Git. Only authored non-sensitive fixtures belong in examples/.
- Preserve exact account IDs, bank/account composite identity, decimal amounts, currencies, source hashes, and original record references.
- Keep target labels and pattern membership out of detection inputs. Keep missing data explicit.
- Add regression tests for changed behavior. Run `python3 -m unittest discover -s tests -v` before claiming completion.
- Keep v0 local and dependency-light. Changes requiring new source data or business evidence must document their assumptions and evaluation limits.
