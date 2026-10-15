# How GPU-Resident Persona Cards Reach the Model

Labels: wayfinder:research
Type: research
Mode: AFK
Status: resolved
Assignee: Codex
Parent: ../map.md
Blocked by: none

## Question

What representations of persona/task cards can use GPU VRAM, how do they reach a local or hosted model, and what hardware/runtime constraints must the design respect?

## Context

Research evidence belongs at ../gpu-card-research.md. The workspace has existing GPU embedding/reranking support, but config.yaml defaults to CPU. Preserve application settings and user data. Use primary sources and clearly separate observed repository facts from proposals.

## Answer

Use structured, evidence-backed cards with a readable Markdown rendering. Store recoverable card definitions/derivatives with tier 3; keep the active card catalog in host RAM. For the requested VRAM tier, add a bounded GPU matrix of card retrieval embeddings and opaque card handles. The matrix selects cards; their selected text still enters model context through a context assembler. Demonstrating real GPU residency is an implementation gate before site integration, while CPU fallback remains supported.

This is an agent design decision, not a measured speed improvement. It satisfies the GPU representation requirement without requiring a new local language model. Merely writing card text to a CUDA allocation or enabling the existing GPU embedder is insufficient.

The current embedder returns CPU NumPy arrays, and no local generative model/prefix-cache adapter was found in the inspected application sources. Optional future local generation can reuse exact compatible model-owned KV prefixes; retrieval vectors are not generator KV memory. Do not concatenate independently computed KV cards or claim a hosted model can read local VRAM.

The RTX 4050 telemetry reported 6141 MiB total and 4068 MiB free during inspection. This snapshot is not an allocation promise. Start with a **64 MiB maximum** for card-owned GPU allocations, disabled when admission cannot preserve measured inference/retrieval peaks and a **512 MiB safety reserve**. These are proposed conservative caps; deployment admission must use live availability and enforce accounting, including duplicate buffers. Small catalogs may run faster on CPU; benchmark before selecting a performance default.

[GPU-resident persona and task cards: feasibility evidence](../gpu-card-research.md) records primary documentation, source locations, observed hardware and illustrative KV/vector memory arithmetic. [ONNX Runtime I/O binding](https://onnxruntime.ai/docs/performance/tune-performance/iobinding.html) provides a device-output route; exact backend selection belongs to the adapter implementation and must preserve the current host-returning embedder contract.

The required accelerated adapter and proof are in scope before integration. Local generator adoption, KV-prefix optimization and hosted-provider caching selection are out of scope for this first core contract.
