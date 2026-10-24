# MLH submission package — Hacktoberfest Hack Day Barcelona 2026

Paste these fields into the MLH form (mlh.com/events/hacktoberfest-hack-day-barcelona) or feed them to DevRelay.

## Project name
A Judge That Learns from an Expert

## One-line pitch (short_description)
A rule-learning judge for bank-assistant conversations: it recomputes the numbers, learns the expert's criteria from labeled examples, discovers new rules with an LLM, and explains every verdict with a quote.

## Description
Plata's expert labeled 150 conversations between customers and a banking assistant as good or bad without stating the rules. Our judge learns them. During `adapt` it builds a fact sheet from each conversation's context (transactions, balances, holds, interest), instantiates rule families from the training set, and verifies every candidate against all labeled examples: one false "bad" on a good conversation demotes the rule to a documented boundary hypothesis. With an API key, a model proposes new rules for the bad conversations no rule explains; each proposal goes through the same verifier. During `eval` the first violated active rule gives the verdict, with the assistant's quote and the recomputed numbers. The explanation for the jury is generated from the same manifest that makes the predictions, with a SHA-256 link between them.

Measured with the organizers' scorer on the public test (80 conversations): rules alone 0.950 macro accuracy with zero false "bad"; bare Claude Sonnet 5.5 / gpt-oss-120b zero-shot 0.76–0.77; rules + Sonnet 5.5 0.950 with 2 newly induced rules and zero false "bad". Grouped cross-validation on train: 0.922. Hidden-rule test (we removed one rule family and asked the model to find it again): Sonnet 5.5 re-discovered it 4 of 4 with no false alarms; open-weight models did not. An independent black-box audit against the task contract found three robustness defects; all are fixed and covered by regression tests. Everything runs in two Docker containers (adapt, eval), standard-library Python, no key required for the deterministic mode.

## Technologies
Python (standard library only), Docker, OpenRouter API, Claude Sonnet 5.5 (anthropic/claude-sonnet-5.5, rule discovery and semantic checks), Qwen3.8-27B (open-weight fallback), Gemini 4 (team-member run), gpt-oss-120b and Gemma 4 31B (benchmarked), TF-IDF few-shot retrieval, SVG/HTML explainer.

## Links
- GitHub: https://github.com/orlanqur/metalearning-llmaaj (branch `orlanqur/plata-clean-work`)
- Commit SHA: see the last line of this file
- Visual explainer (EN/RU): https://github.com/orlanqur/metalearning-llmaaj/blob/orlanqur/plata-clean-work/docs/APPROACH.html (open locally: `docs/APPROACH.html`)
- extra_links: "Blind audit report" → docs/BLIND-EVAL.md; "Organizer task contract" → docs/ORGANIZER-README.md; "Docker instructions" → docs/DOCKER.md
- Live demo: command line, `python3 -S demo/judge_demo.py --id <conversation id>`; no video.

## ai_tools (our harness and models)
claude-code; coding:anthropic/claude-fable-5.1 (planning, review), coding:openai/gpt-6-astra via Codex CLI (implementation), coding:anthropic/claude-opus-5.5 (pitch and explainer), coding:google/gemini-4-argon (critique)

## Prize categories

### A Judge That Learns from an Expert (Plata Bank Challenge) — YES
sponsor_usage: Our pipeline implements the challenge contract end to end: `adapt` learns rule families from the labeled conversations, verifies each against all expert labels, lets Claude Sonnet 5.5 discover rules for the unexplained cases, and writes the jury explanation from the same manifest `eval` uses. Public test: 0.950 macro accuracy with zero false "bad"; hidden-rule test re-discovered 4 of 4.

### Best Open-Source AI Project — YES
sponsor_usage: MIT-licensed, standard-library Python, reproducible in two Docker containers without a key. Open-weight Qwen3.8-27B is the documented fallback model (hybrid run 0.950, zero false "bad"); gpt-oss-120b and Gemma 4 were benchmarked and the numbers are in the README. The black-box audit harness ships in the repo.

### Best Use of Gemma 4 — SKIP unless the form requires an entry
sponsor_usage (only if entered): Gemma 4 31B was benchmarked as a discovery model: it phrased the hidden rule almost verbatim; our verifier rejected it for three false alarms (0.938 on the public test). It is not the shipped default, so enter only if partial use counts.

### Best Use of ElevenLabs — SKIP
No voice component.

## Final commit SHA
See `git rev-parse HEAD` on branch `orlanqur/plata-clean-work`; recorded at submission time in TEAM/DIALOG.md.
