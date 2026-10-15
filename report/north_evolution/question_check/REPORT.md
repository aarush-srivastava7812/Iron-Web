# Retrieval question demo: what worked and what still needs improvement

The graph is useful, but it should be paired with meaning-based search and a check that the requested answer actually exists. This demonstration tested finding evidence, not writing final answers.

## What we tried

We wrote 30 questions before creating the prototype retrieval helper. They covered direct facts, different wording, connected facts, conditions, changes and missing information. Twenty-eight had reference evidence in the supplied data. Two requested facts that were absent.

Both systems received the same 91 manually prepared notes and the user-confirmed organization alias. The current application used its real, locally cached meaning-search model. Its existing code ran in separate test stores. The prototype used wording lookup on graph-stored notes and actual graph connections, with no meaning-search model. Reading words to find a graph entry point is included in “KG-only” here; graph connections alone do not understand a natural-language question.

The first five selections and the complete evidence within a budget of ten items were recorded. Some questions require two notes: finding only one does not count as complete. A required answer fact may have several acceptable supporting notes. Reference answers were written for evaluation; the system did not generate them.

## Original results

| Search method | Complete evidence in first five | Complete evidence within ten |
| --- | --- | --- |
| Our first KG lookup | 24 / 28 | 25 / 28 |
| Our improved KG lookup | 25 / 28 | 27 / 28 |
| Current normal combined search, default ingestion | 24 / 28 | 26 / 28 |
| Current combined search, given prepared graph links | 23 / 28 | 26 / 28 |
| Current graph search, given prepared links | 6 / 28 | 6 / 28 |
| Current graph search, fresh data under default settings | 0 / 28 | 0 / 28 |

The zero result is explained by the current default: saving new text does not automatically extract entity links. It does not mean all existing application graphs are empty. The current combined search still finds text through its meaning-based search.

Prepared graph links were supplied manually to give the current graph search a fairer chance. Its graph-only path starts from names mentioned in the question and then collects connected memories. A question without a matching name can have no starting point. A broad name such as North can also bring back many unrelated notes, with recency and importance affecting their order. Adding those prepared links did not improve the ten-item combined-search total in this sample. More connections require selective retrieval, not just more traversal.

## Two improvements were tried in the demo

The first lookup searched the wording of whole records but did not include their field labels. Consequently, “employment” could fail to find “Works at Inditech.” The revised helper includes field labels in its entry-point search.

The first lookup could also find a game feature list without bringing back the note identifying the local multiplayer project, or find the internship without the employment report. The revision follows specific project, episode and organization connections to collect related records. It deliberately excludes broad person/persona/technology hubs from this added expansion so that it does not pull in every memory.

These generic changes repaired two original failures. They did not introduce question-ID routes, expected-answer lookups, embeddings or a generative model into KG retrieval. They also did not change the application itself.

## Additional questions, without further tuning

We froze ten additional questions before writing that improvement, then ran them without making a second round of changes based on their outcomes. Nine had reference evidence; one asked for an unspecified installed software version.

| Search method | Complete evidence within ten |
| --- | --- |
| First KG | 8 / 9 |
| Improved KG | 8 / 9 |
| Current normal search | 6 / 9 |

The graph missed “What qualification label and discipline does the earlier profile contain?” despite storing the BTech record. The current normal search also missed that wording, along with a tone-baseline question and a question needing both anime escape preferences. Ten questions are too few to establish which method is generally better. The improvement benefited the original examples but showed no increase on this additional set.

## Examples worth inspecting

- “What is the SIH validation accuracy?” Both the KG and current normal search found the 65.24% record.
- “Does the completed Inditech internship mean the employment ended?” The first KG missed the employment companion. The improved KG found both. The two records support keeping the episodes separate, not inventing a termination.
- “Which build is intended to let friends assemble teams and take turns fighting?” The first KG found the feature goals without the project-identifying companion. The revised graph paths brought back both. The current normal search already found both.
- “What makes him start acting when a competitor starts moving?” The improved KG and current normal search still missed the Friction Ignition record. Both need better handling of varied wording.
- “Why should the assistant challenge the no depth without ROI stance?” The KG retrieved both the policy and its attributed interpretation. Current default combined search did not retrieve both within ten; prepared graph links did.
- “Does the platform replace GDPE?” The prototype returned the relevant records and the explicit unresolved relationship. This is an uncertainty that should be visible in the eventual answer.
- “What is North's personal telephone number?” The first and improved KG returned unrelated character-sheet notes. The current normal search returned nearby profile memories. Neither returned the requested number, because it was not supplied.

## Recognizing missing answers remains unfinished

The KG returned no information for salary, but unrelated information for telephone and related information for the installed FastAPI version. The current normal search returned nearby information for all three.

These are retrieval observations, not fabricated-answer observations: no final answer generator was tested. Returning a related note is not itself a false answer, and returning nothing does not prove sophisticated uncertainty reasoning. The application still needs an explicit check that the requested detail exists before presenting an answer. “Uses FastAPI” cannot establish a version number. “Student in India” cannot establish nationality. A source saying “latest Pokedex” cannot establish a precise edition.

## Current versus old claims

Three separate synthetic probes tested the change behavior already demonstrated in the graph. The current system correctly labelled explicitly supplied supersession links, but with those links alone it still returned both old and new notes for a current question. A label and penalty are not the same as excluding a replaced claim from current use.

The existing application already supports explicit expiry. Supplying the expiry made its current search return the replacement and its historical search return the old note. That is an existing capability to build on, not a feature that must be rebuilt from scratch.

The proposed graph separates an old retained assertion from a currently eligible assertion. Accepted changes/corrections leave only the replacement eligible for current use. Unaccepted contradictions retain both as disputed. A correction's former acceptance score is an audit of a past belief; it does not establish that the earlier claim was historically true.

The existing age logic treats 1 as an ordinary importance value. It does not grant the proposed protection against decay. Importance, relevance, current acceptance, and protection should remain distinct: a strongly accepted anime preference still cannot answer a laptop-memory question.

## A practical improvement path

1. **Keep meaning search and use the graph to check what it found.** Meaning search finds varied wording. The graph adds relevant companions, conditions, source evidence, changes and disagreements. The first demo already showed each succeeding where the other failed.
2. **Create clearer memories when data arrives.** Preserve the original wording and separate independently changeable details. Keep compound instructions with their conditions. Mark goals, past activities, unknown dates and uncertain identities.
3. **Retrieve a complete explanation.** Bring back a tone policy with its baseline, an internship with the relevant work report, or a replacement with its previous claim and change reason. Favor specific connections over broad “everything about North” links.
4. **Check the requested detail before answering.** Distinguish a missing detail from an unrelated result. Add a wider test set containing unprovided values, ambiguous questions and paraphrases; passing three examples would not prove a reliable missing-answer detector.
5. **Make changes explicit.** Require accepted replacement/correction evidence before changing current eligibility or transferring score-one protection. Preserve both nodes. Surface unresolved contradictions rather than resolving them by highest score.
6. **Run the new view alongside the existing one first.** Rebuild a test graph from saved sources, compare searches without replacing current memories, and inspect misses. Then connect both methods and test the eventual answers as well as the retrieved evidence.
7. **Test larger and messier data.** Add irrelevant memories, repeated paraphrases, conflicting source authority, partial updates and event-date changes. Measure whether needed evidence stays near the top and whether unrelated information overwhelms the answer.

## What this demonstration does not prove

It does not establish general answer accuracy, information gain, production throughput, statistical superiority or large-scale retrieval quality. Both systems were given hand-prepared normalized notes, so it does not measure automatic ingestion. It does not test generated answers or a combined version of the new KG and meaning-search system. Single-pass local timings are recorded for inspection but are not presented as a fair speed comparison.

The original questions, additional questions, executed database results and retrieved evidence are available beside this report. The interactive page lets you select a question and method and see which required evidence was retrieved or missed. All changes for this work are contained in the isolated demonstration files.
