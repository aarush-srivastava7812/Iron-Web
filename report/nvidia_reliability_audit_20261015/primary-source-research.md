# Research: reliability of the NVIDIA travel-agent evaluation

Researched 15 October 2026. This note uses six primary sources, the captured evaluation, and the application client. It makes no new model calls and changes no memory code. External studies concern different models and tasks; their findings suggest checks and design choices, not a proven explanation for this particular run.

## What the local evidence already establishes

The [verified evaluation](../nvidia_multi_agent_20261015_verified/README.md) contains direct failures, so unreliability does not rest on a paper or an opinion:

- The planner selected offers costing INR 72,600 but wrote 76,600; its later output used the correct INR 65,000 cap yet selected the same over-budget offers. The fixture contains a feasible INR 58,600 alternative.
- The first reviewer returned 76,600 as the budget instead of the current 90,000. Later explanations repeated an incorrect fixed-cost subtotal and an invented rule that a morning flight must leave before 09:00.
- The memory supplied the updated limits in these cases. Remembering a requirement and obeying it are separate operations.
- Planner and reviewer are separate roles calling the same model. The reviewer receives the candidate draft. Their answers must not be counted as independent confirmations. The observed repetition is evidence of shared errors; whether it arises from candidate anchoring, shared model weaknesses, prompt wording, or several causes requires an intervention.
- `NvidiaModel.json()` requests temperature zero and `enable_thinking=False`, parses an object, and rejects length truncation. It does not supply a server-enforced response schema. `TravelAgent.respond()` validates memory freshness after generation; that is not validation of travel arithmetic or feasibility.
- The runner's independent checks score answers, but its work-lifecycle probes register/complete work even when a plan fails. A completed memory work record therefore cannot be read as approval of the itinerary.

## 1. The model configuration differs from NVIDIA's example recipe

NVIDIA's own Lightning 3.5 model card recommends temperature 1.0 and `top_p=0.95`; thinking is enabled by default and can explicitly be disabled for direct answers. Both on/off examples are supported. Its reference snippets use a larger output allowance than this evaluation. These are model-family usage recommendations, not a guarantee of task accuracy or proof of the hosted endpoint's exact model revision/precision. [NVIDIA model card, API Client and Model Summary](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16#api-client).

**Implication for this run:** the results characterize the selected direct-answer configuration, not the best performance attainable with this model. Disabling thinking is a plausible contributor to difficult planning failures, but the existing run has no thinking-on comparison. Temperature zero is an intentional repeatability choice; simply raising temperature cannot be assumed to repair arithmetic or make responses safer. A controlled comparison should vary thinking separately from sampling, retain the same inputs and output schema, record completion/reasoning tokens, and score against the same independent checks. Larger thinking budgets can increase latency and create a new truncation risk.

## 2. JSON shape is different from correct content

NVIDIA NIM documents constrained generation using a JSON schema, grammar, regular expression, or a fixed set of choices. Its schema guidance distinguishes an explicit schema from JSON-object mode, which can still return an empty object. The documented examples use NIM serving configurations; support for each parameter on the actual hosted endpoint must be tested, not assumed. [NVIDIA NIM 1.15 structured generation](https://docs.nvidia.com/nim/large-language-models/1.15.0/structured-generation.html#json-schema).

**Implication for this run:** the application currently uses prompt instructions plus `json.loads()` and an object check, a weaker guarantee than schema-constrained generation. A schema could reject an unknown decision, missing field, wrong type, or invalid enum before downstream use. Structural validity alone cannot establish that 34,000 + 24,000 + 600 + 14,000 equals the supplied total, that a remembered number really came from the source, or that the chosen hotel fits the walking limit. Those relationships need application checks against trusted records. Neither valid JSON nor a valid claim ID establishes semantic correctness.

## 3. More agent roles do not automatically provide verification

The MAST study analyzed over 1,600 traces from seven multi-agent frameworks and identified failures in system design, inter-agent alignment, and verification. It reports missing/incomplete and incorrect verification even in some successful runs. Prompt and topology interventions helped in some tested configurations but did not improve all of them consistently. [Cemri et al., *Why Do Multi-Agent LLM Systems Fail?*, v3, sections 4–5 and appendices G–H](https://arxiv.org/html/2503.13657v3).

**Implication for this run:** a reviewer role is an additional attempt to detect errors, not a correctness certificate. The local mistaken subtotal and invented time cutoff are consistent with the study's verification categories, but MAST did not test this NVIDIA model or this travel system. A useful follow-up comparison is draft-visible review versus an independent calculation from the current memory and supplier catalog before showing the candidate; record both false approvals and false rejections. This tests an anchoring hypothesis rather than presuming that another role or a longer debate resolves it. A changed topology must be assessed on new scenarios rather than only the fixture used to design it.

## 4. Self-review has known limits, with important qualifications

Huang et al. studied intrinsic reasoning correction without external feedback and found that tested models often failed to repair answers and sometimes degraded them. This is bounded evidence about their evaluation setup and models, not a universal impossibility result. [*Large Language Models Cannot Self-Correct Reasoning Yet*, ICLR 2024](https://arxiv.org/abs/2310.01798).

Liu et al. subsequently demonstrated intrinsic correction under different conditions, emphasizing unbiased prompts and zero-temperature settings. These findings specifically caution against treating the earlier result as a blanket claim that self-correction never works. [*Large Language Models have Intrinsic Self-Correction Ability*, v2](https://arxiv.org/abs/2406.15673).

**Implication for this run:** it is reasonable to test better review prompts and sampling, but neither paper justifies using self-review as the sole acceptance gate. Our reviewer receives memory and offers as well as the draft, so it is not exactly either paper's intrinsic-correction setup. Its failures are established by the captured answers themselves. In particular, the second paper means temperature zero should not be blamed on intuition alone; the model-specific recipe and the local task must be tested.

## 5. Arithmetic can be verified outside the language model

PAL separates interpreting a problem from executing its calculations. Across the authors' tested arithmetic/symbolic tasks, offloading execution to a runtime improved results; it does not make the model's problem interpretation infallible. [Gao et al., *PAL: Program-aided Language Models*](https://arxiv.org/abs/2211.10435).

**Implication for this run:** known supplier IDs and current memory limits permit a direct application calculation. The calculator should read the trusted offer catalog, apply explicit units/party-size/night rules, compute totals, and test hard constraints. Asking the model to produce a number or a calculation string still leaves interpretation and source selection fallible. For this bounded catalog, fixed application rules are easier to audit than unrestricted model-generated code. A deterministic check proves only the conditions encoded in it; the evaluator itself needs adversarial cases and an explicit domain contract. No calculator, gate, or other fix was implemented in this research task.

## What cannot be concluded from the current evidence

- There is no measured causal attribution to thinking mode, temperature, model size, prompt position, or reviewer anchoring. These are possible explanations to distinguish with paired checks.
- The 46/50 result mixes correlated controls from one synthetic scenario. It is not a 92% success probability for travel planning, nor a reliability guarantee for every memory operation.
- A changing fuzzy score is not a calibrated probability that an extracted claim is true. In this application the score does not enforce itinerary feasibility, and a protected user rule's score of one expresses authority/currentness rather than proof that a model interpreted its text correctly.
- Two-card GPU timings do not establish an advantage at larger scale. The local card vectors are separate from NVIDIA's hosted generation and its provider cache.
- Existing checks establish that memory retrieval/state transitions worked in those cases. They do not establish that every possible ingestion, update, privacy boundary, metadata path, or work dependency has been tested.

## Six primary sources

1. [NVIDIA Lightning 3.5 model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16).
2. [NVIDIA NIM 1.15 structured generation](https://docs.nvidia.com/nim/large-language-models/1.15.0/structured-generation.html).
3. [Cemri et al., MAST, v3](https://arxiv.org/html/2503.13657v3).
4. [Huang et al., intrinsic self-correction limits](https://arxiv.org/abs/2310.01798).
5. [Liu et al., conditions enabling intrinsic self-correction, v2](https://arxiv.org/abs/2406.15673).
6. [Gao et al., PAL](https://arxiv.org/abs/2211.10435).
