# Research route: memory changes and reliable handoffs

The selected question is whether explicit links from memory versions to work reduce stale decisions and incomplete handoffs after requirements change. This follows the user's chosen research direction. Database choice, fuzzy scores, persistent text, or the existence of a graph are not themselves novelty claims.

## Falsifiable primary hypothesis

With the same agents, input events, tools and evidence budget, validating current memory versions and prerequisites before work completion reduces obsolete-constraint completion and missed-review handoffs, while preserving unrelated completed work. Reject or narrow this claim if a fair comparison achieves the same reliability, if useful work is blocked excessively, or if extraction errors erase the benefit.

Compare the complete system with (1) the same memories and agent logic with current-state/dependency checks disabled, and (2) a strong flat versioned ledger that has the same source, scope, identity, time and dependency information. The first comparison isolates the checks; the second tests whether the implementation offers practical benefits beyond representing equivalent information differently. Do not substitute a deliberately weak raw-vector wrapper for a full named memory product.

Keep FalkorDB plus Qdrant fixed. Separately compare fuzzy scoring enabled versus neutral ordinary confidence, retaining protection and change rules in both. Report zero or negative effects. The first controlled retrieval results show no added source-recall benefit from fuzzy ranking after subject/state checks; this does not establish that the fuzzy controller is calibrated or useless in every setting.

## Protocol

Freeze the scenario generator, field schemas, intended changes, scopes and gold evidence before the final evaluation. Include direct corrections, later changes, logical retractions, agent disagreement, same-author repetition, independent corroboration, partial confirmation, alias ambiguity, missing facts, expiry, task prerequisites, concurrent ownership and restart/interruption.

Use development cases to fix failures. Then evaluate untouched paraphrases and multi-session dialogues. Keep raw-message interpretation, retrieval, field answerability, agent decisions and final generated answers as separate stages. A correct answer with wrong evidence and a correct retrieval followed by a wrong agent action are different failures.

Record stale completions, omitted review reasons, duplicated work, unsupported answers, missing-answer handling, relevant/current evidence, task and tenant violations, unnecessary blocking, receipt-to-ready delay, median/p95 retrieval latency, throughput, workload size and resource cost. Use paired runs with identical model settings and evidence budgets. Preserve per-case outcomes, exceptions, configuration, fixture hashes and code hashes; use scenario-level confidence intervals rather than treating repeated versions of one scenario as independent people.

## Evidence available now

The [first local study](../report/memory_evaluation_20261014/results.json) exposed weak replacement relevance and limited grammar coverage. Those cases were used to improve the implementation. The [revised study](../report/memory_evaluation_20261014_final/results.json) is a regression result, not an untouched blind test: graph and combined discovery retrieved the required current source in 24/24 answerable probes; field-aware recall handled all 36 supported/disputed/missing probes; raw vector discovery without state checks exposed old sources in 16/24 answerable probes. The local grammar extracted 14/16 explicit facts and avoided invented claims on six negative inputs. Two unsupported authoritative phrasings remain a reason to use structured input or a tested interpreter; the service now marks unclear confirmed requirements for review and blocks stale actions.

The [shared-service demo](../report/shared_memory_20261014_final/results.json) and regression tests provide real-storage evidence for private user spaces, task ownership, procedural memory, changes, handoffs, restart and bounded concurrent submission. Killed-process tests exercise receipt, vector, graph-publication and missing-vector boundaries. The [paired read check](../report/lifecycle_implementation_20261014_final/batching_check.json) isolates within-request batching and confirms identical ranked evidence.

## What remains before a paper claim

Run the strong ledger comparison, a larger untouched workload, and actual model-driven agents/final answers with a configured provider. Validate the automatic interpreter independently. No hosted-language provider credentials were available in this run. Do not call the current prepared probes blind data or general agent accuracy, and do not infer scientific novelty or statistical superiority from their perfect counts. Preserve failures and organizer/event data as exploratory material, not as a post-hoc sealed test set.
