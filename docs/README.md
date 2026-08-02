# Garbleworks documentation

Start at the [project front page](../README.md). This folder and the design docs at
the repository root go deeper.

## For operators

- [Usage & API reference](USAGE-AND-API.md) - endpoints, target adapters, the detector
 pipeline, recipes/decks, history/analytics, troubleshooting.
- [Technique coverage](../COVERAGE.md) - every op, StegOFF parity, and the field-guide crosswalk.
- [The injection field guide](FIELD-GUIDE.md) - the 312-technique reference catalog, its ATLAS/OWASP/NIST/CWE crosswalk (attack techniques), and the `field_guide_ops` bridge from a catalogued technique to the op that runs it.

## For understanding the method

- [Optimizer & statistics, formally](../EVOLVE_MATH.md) - the EVOLVE genetic search,
 the confidence bounds, racing, and FDR.
- [Positioning vs the literature](../HARNESS-POSITIONING.md) - the honest delta against
 h4rm3l and composable-jailbreak work.
- [Research distillation](../RESEARCH-DISTILLATION.md) - the papers and repos the pipeline draws on.
- [Full harness spec](../SPEC-redteam-harness.md).

## Benchmarks

- [Garbleworks vs wallbreaker A/B](BENCH-VS-WALLBREAKER.md) - methodology and results.
- Offline math + plumbing audit: `backend/benchmarks/README.md`.

## Contributing & policy

- [How to contribute](../CONTRIBUTING.md)
- [Security & responsible use](../SECURITY.md)
- [Code of conduct](../CODE_OF_CONDUCT.md)
