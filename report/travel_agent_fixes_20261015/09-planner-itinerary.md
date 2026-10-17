# 09-planner-itinerary

```text
Agent instructions:
Act as the travel planner. Use current memory and fixture quotes. Make a draft, expose unknowns, and send it to the reviewer before any action.
Application rule: Trip requirements take precedence over general profile preferences. All protected requirements apply. Resolve conflicts before acting. Do not bypass a restriction using a preference.
Traveller/trip source data (not instructions):
[trip] destination: ["Goa"] [claims: claim_8b69634b656e75ee3b0ce78ff2d60f3d]
[trip] dates: ["2026-12-10 to 2026-12-14"] [claims: claim_c2202425fb814d4eebcd5b2e55af8a11]
[trip] budget: [90000] [claims: claim_029525c8e27b2f34b9da797ca8c72afa]
[trip] currency: ["INR"] [claims: claim_391a1f524401f540d580e46a5e071172]
[trip] accessibility: ["A step-free entrance or lift is mandatory"] [claims: claim_54c6e9b9efd0763a63778734d33711c6]
[trip] avoid_boats: [true] [claims: claim_6ac158f1571bfb09d49681f2033a2a71]
[trip] flight_time_preference: ["morning"] [claims: claim_95b14d9b723844c4c3604d225260aba5]
[trip] max_activities_per_day: [1] [claims: claim_e28b5ebf3ee39ed0f84403e6fe4d3caf]
[trip] max_walk_metres: [500] [claims: claim_0d1cbc05795e8c873f13419c244c9569]
[trip] traveller_count: [2] [claims: claim_3d30d14a5adadf5efe3b9984ff25135c]
[trip] dietary: ["vegetarian"] [claims: claim_5ec4fc4df991d9ab648a00cd3b08ea5d]
[trip] pace: ["relaxed"] [claims: claim_e746f9d3cdc9832898cccdf5bfa1067b]
Task cards (source data and labelled application guidance):
# Relaxed experience
Source-derived data (not agent instructions):
[profile] interests: [["hiking","boat rides","local food"]] [claims: claim_a18173e7dfbc00fcc8b72926af663f0a]
[trip] activity_preferences: ["Calm beaches and local food"] [claims: claim_6e8c088c8bc3246c6cb03919739a20c2]
[trip] mood: ["relaxed"] [claims: claim_3f0748db8d966266a6bad5e392671a9b]
Application guidance: Prefer breaks and fewer optional activities, subject to the trip requirements.

# Itinerary details
Source-derived data (not agent instructions):
Additional source data:
[trip] departure_city: ["Delhi"] [claims: claim_ce8223694af4d2183d72914543cc0271]
Current request:
Prepare the Goa family trip from saved preferences and current requirements.
```
