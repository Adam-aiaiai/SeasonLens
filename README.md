# SeasonLens

SeasonLens is a formative research prototype investigating observation-first scaffolding for novice ecological noticing.

## Live Demo

The deployed prototype can be accessed directly in a web browser:

- **Participant interface:** https://seasonlens-production.up.railway.app/
- **Researcher/debug interface:** https://seasonlens-production.up.railway.app/?debug=1

No local installation is required for the online demo.

> Note: the deployed version is intended for prototype demonstration and formative testing. Persistent database storage and authenticated researcher access are not yet implemented.

SeasonLens is currently deterministic: ecological facts, accepted evidence regions, stage answers, and hints are frozen authored content. Rule-based diagnosis selects an appropriate hint from that library; the prototype does not use an LLM or vision model to generate botanical answers.

## Current research goal

SeasonLens studies whether asking novices to locate and describe visible plant evidence before receiving guidance can support more deliberate ecological noticing. Region selection is an explicit interaction proxy, not gaze measurement.

## Current prototype flow

```text
Select region
→ Describe visible evidence
→ Bounded stage judgement
→ Commit
→ Deterministic diagnostic
→ Conditional guidance
→ Reveal
→ Reflect
