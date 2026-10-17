# Event-grounded dashboard feature choices

Six candidates from the capability audit:

1. **Context provenance X-ray:** click an observed agent context, then a field to
   inspect its actual claim/source links. **Built** in Resources and Inspector.
2. **Cache reuse microscope:** inspect measured hit/miss counts for the selected
   event window and actual cache payload/entry quotas. **Built** in Resources.
3. **Freshness checkpoint:** select a validation event and inspect its real
   valid/changed outcome. Supported by the event inspector and conflict markers.
4. **Without-memory counterfactual:** useful once an equivalent baseline prompt
   and tokenizer are captured. Currently N/A; no saving percentage is invented.
5. **Why retrieved / why excluded:** existing context field support and provenance
   are shown; semantic-score explanations await traces from a real hybrid search.
6. **Maintenance impact ribbon:** would show actual dedupe/consolidation/eviction
   outcomes, only after capture is instrumented and those operations actually run.

The first two give the strongest immediate explanation of bounded context and
reuse using available evidence. Each Resources subview has one main visual and
at most one secondary block; raw payloads and provenance expand on demand.
No promotion, eviction, GPU-utilization or cost event was fabricated to make a
screen animate. Agent cursors, rings and wiring pulses use observed event IDs.
