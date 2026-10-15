# GPU-resident persona and task cards: feasibility evidence

Research date: 2026-10-14 (Asia/Calcutta). Scope: read-only repository inspection and primary documentation; no model initialization, download, hosted request, or application/configuration change.

## Answer

The proposed second tier is feasible as a logical card catalog whose bounded embeddings and card handles reside in VRAM for local matching. A `persona.md` file does not become model memory merely because its bytes reside in VRAM. The missing interface is a reader that selects cards and supplies their contents to inference. Use GPU tensors to match cards, then resolve their authoritative text and supply normal text context to hosted models. A model-owned KV prefix cache is a separate future optimization for a local generator. Keep the authoritative cards and source references in durable storage so eviction or a restart cannot lose preferences.

**The concrete problem today:** this repository has GPU-capable retrieval models, but no demonstrated GPU card cache or local generative model that consumes one. Turning on `USE_GPU` would accelerate embedding/reranking; it would not implement Tier 2.

## Observed repository and hardware facts

| Observation | Evidence | Consequence |
| --- | --- | --- |
| Effective configuration selects CPU and no hosted extraction; reranking is disabled. | [config.yaml](D:/Opencode_/reserchpaper/config.yaml:2), [settings](D:/Opencode_/reserchpaper/memory/config.py:64) | GPU functionality is optional, not active by configuration. Environment overrides remain possible; running application state was not inspected. |
| Local models are `BAAI/bge-small-en-v1.5` and `BAAI/bge-reranker-base`; engine initialization is lazy. | [models](D:/Opencode_/reserchpaper/config.yaml:15), [lazy embedder](D:/Opencode_/reserchpaper/memory/engine.py:226) | These provide retrieval features and scores, not travel-agent response generation. |
| The embedder can select CUDA/DirectML, fall back to CPU, and returns a host `numpy.float32` array. | [providers](D:/Opencode_/reserchpaper/memory/embeddings/embedder.py:70), [output](D:/Opencode_/reserchpaper/memory/embeddings/embedder.py:130) | GPU execution does not imply a persistent GPU-resident card index. |
| Current vectors use a local Qdrant client. | [Qdrant client](D:/Opencode_/reserchpaper/memory/vector_store/qdrant_store.py:61) | The source examined has no GPU vector-index allocation interface. |
| NIM extraction uses the OpenAI client against `https://integrate.api.nvidia.com/v1` and sends text `messages`. | [endpoint/client](D:/Opencode_/reserchpaper/memory/ingestion/nim_extractor.py:45), [request](D:/Opencode_/reserchpaper/memory/ingestion/nim_extractor.py:83) | This request path transmits selected text, not local VRAM tensors or a local KV cache. |
| No matches for `vllm`, `AutoModelForCausalLM`, `past_key_values`, `prefix_cach`, `DynamicCache`, or `KVCache` under `memory`, `requirements`, `server.py`, or `shared_server.py`. | Read-only `rg` search, 2026-10-14 | This establishes absence in the inspected application sources, not absence of every tool installed on the machine. |
| NVIDIA telemetry reports RTX 4050 Laptop GPU, **6141 MiB total**, **4068 MiB free**, driver **592.82**. | `nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv,noheader`, 2026-10-14 | Free VRAM is a transient snapshot; no card capacity or inference performance was benchmarked. |
| Repository profile defines 1024 MiB reserved and 5117 MiB operational VRAM targets explicitly as informational. | [device profile](D:/Opencode_/reserchpaper/memory/device.py:80) | These are not an enforced allocator quota and do not prove that 5117 MiB is available now. |

## Four representations must remain distinct

| Representation | Meaning and useful interface | Limitation |
| --- | --- | --- |
| Markdown / UTF-8 bytes | Human-readable authoritative card content; selected text enters the prompt. | Storing bytes on a device provides no implicit connection to a model. |
| Token IDs | Tokenizer output for a particular generator/chat template; useful to avoid repeating tokenization. | IDs still require model computation; they are not attention state and must match the tokenizer and template. |
| Retrieval embeddings | Vectors used to choose matching cards, then fetch their original text. | A BGE retrieval vector is not the generative model's input embedding or KV state. It cannot replace the selected textual evidence. |
| KV prefix cache | Keys and values produced by a particular causal model while processing a prompt; can reuse compatible preceding context. | Large, runtime-specific, context-dependent, volatile; suitable as a derivative optimization. |

BAAI documents its embeddings as retrieval representations and its reranker as a query/document similarity scorer. The distinction between retrieval vectors and generator state follows from those interfaces and the generator cache interface below. [BAAI model card](https://huggingface.co/BAAI/bge-small-en-v1.5).

Hugging Face describes KV state as per-layer attention keys and values produced from processed tokens. Each cache tensor has batch, head, sequence, and head-dimension axes; generation must supply compatible attention context. Consequently, independently prefilled card caches cannot simply be concatenated under arbitrary preceding prompts: the preceding context contributes to those states. This is an architectural inference from causal attention, not a benchmark result. [How caching works](https://huggingface.co/docs/transformers/main/en/cache_explanation).

ONNX Runtime explicitly distinguishes GPU execution from device-resident outputs: absent device output binding, outputs are copied back to CPU. A persistent VRAM card index needs an explicit allocator/device-tensor interface; existing FastEmbed calls returning NumPy are insufficient. [ONNX Runtime I/O binding](https://onnxruntime.ai/docs/performance/tune-performance/iobinding.html).

## Concrete proposed GPU card-matching interface

Implement a bounded matrix of normalized card embeddings on CUDA, accompanied by row-to-card/version handles. Compute matching scores against a query tensor, resolve selected handles to canonical card text on the host, and serialize that text for the hosted consumer. PyTorch documents explicit CUDA-memory copies and matrix/vector products; these provide one supported building block for this proposal. [Tensor.cuda](https://docs.pytorch.org/docs/2.14/generated/torch.Tensor.cuda.html), [torch.matmul](https://docs.pytorch.org/docs/2.14/generated/torch.matmul.html). Copy only the selected scores/row identifiers to CPU as needed; PyTorch distinguishes this as a CPU-memory copy. [Tensor.cpu](https://docs.pytorch.org/docs/2.14/generated/torch.Tensor.cpu.html).

The GPU backend is a required implementation capability for the requested VRAM tier, with a CPU fallback when disabled, unavailable, or over budget. This is a proposed interface, not an installed or verified implementation. Filter authorized owner/trip/task/mood scope before similarity selection; keep handles and matching rows synchronized through updates, deletion and eviction; expose actual residency, allocation bytes and fallback reason. Normalized dot-product matching is a design choice; semantic retrieval is not proof that a fact applies to the traveler. No latency benefit is claimed for a small catalog: upload, score transfer, synchronization, model inference and contention must be measured.

## Prefix reuse conditions and update behavior

vLLM hashes each full cache block using its tokens, preceding block hash, and applicable adapter/multimodal/isolation identifiers. Reuse therefore needs the same compatible prefix, not merely a semantically similar card. It also provides a per-request cache salt to isolate reuse; cached blocks can be evicted when their storage is needed. [vLLM prefix-cache design](https://docs.vllm.ai/en/latest/design/prefix_caching/).

Proposed policy: build the stable agent instructions first, then the scoped stable user/trip facts, then selected cards, and finally changing request/evidence. Key any future cache by model revision, tokenizer/chat-template revision, adapter, owner/trip scope, card versions, exact ordered prefix and runtime format. A changed card invalidates the prefix from that change onward. Never key by mood alone: two travelers may both request a quiet trip yet have different facts. Deletion must remove authoritative content and invalidate all derived card/token/vector/prefix entries. TTL/LRU eviction can discard derivatives and recompile from authorized source data.

## VRAM budgeting: illustrative arithmetic, not measured capacity

For a conventional decoder with equally shaped key/value tensors at every layer:

`KV_bytes = 2 × layers × KV_heads × head_dim × stored_tokens × concurrent_copies × bytes_per_element`

This formula is derived from the per-layer key/value tensor shapes in [Hugging Face's cache explanation](https://huggingface.co/docs/transformers/main/en/cache_explanation). Use KV heads rather than query heads for grouped-query attention. Sliding-window or hybrid architectures require a per-layer calculation; quantized formats add scales/metadata; blocks, alignment, and allocator overhead add cost.

**Illustration only:** 32 layers, 8 KV heads, head dimension 128, FP16 (2 bytes), and 2048 tokens consume `2 × 32 × 8 × 128 × 2048 × 2 = 268435456` bytes = **256 MiB** per independent prefix. Sixteen independent such prefixes consume **4 GiB**, before model weights, retrieval models, inference workspace, live suffix/generation caches, display/other processes, and fragmentation. Shared compatible blocks may reduce duplication. By contrast, 10,000 retrieval vectors of 384 float32 values contain about **14.65 MiB** of raw vector payload, excluding index and metadata. Small embeddings and large KV state are different budgets.

Proposed admission rule: require `weights + retrieval_models + card_derivatives + active_requests + workspace + safety_margin <= currently_available_VRAM`, with measured peak allocations and explicit eviction/fallback. Do not equate total device capacity with currently available capacity. Offloaded caches trade GPU residency for CPU transfers; quantized caches lower memory but can hurt latency, so either requires runtime-specific measurement. [Hugging Face cache strategies](https://huggingface.co/docs/transformers/main/en/kv_cache).

## Decision before travel-site integration

Proceed with durable versioned cards, deterministic task/user/trip selection, and the bounded CUDA card-matching interface above, always producing bounded selected text for the consumer. The current CPU profile must remain valid. Treat GPU embedding/reranking and a GPU card index as separately observable capabilities. Claim actual VRAM residency only after device allocations and CPU fallback are implemented and measured. A local generator/KV adapter is additional optional work; a hosted travel generator needs prompt composition, and receives selected text through its documented API. No evidence gathered here establishes NIM hosted prompt-cache support or residency guarantees.

Required proof for a future GPU implementation: scoped isolation; source-update/deletion invalidation; exact-prefix hit/miss correctness; equivalent selected evidence under CPU fallback; OOM/eviction behavior; and peak VRAM/latency measured with the intended generator plus retrieval models. The hardware observation alone does not resolve these checks.
