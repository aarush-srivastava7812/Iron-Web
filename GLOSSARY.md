# Shared Agent Memory

Language for the reusable memory system and the applications and evidence built around it.

## Language

**Travel specialist**:
A member of the travel team with a distinct planning responsibility, working style and evidence-backed contribution to the current trip.
_Avoid_: Several names for the same chatbot

**Indicative trip estimate**:
The calculated cost of the listed draft selections and stated allowances, with omissions made explicit. It is neither a supplier quotation nor a confirmed reservation.

**Plan version**:
A saved state of one trip's schedule and selected stay that can be compared with or restored from an earlier state.

**Memory core**:
The reusable system that preserves knowledge across sessions, manages changes, and supports shared work between agents.
_Avoid_: Travel application, chatbot

**Hackathon entry**:
The focused travel application and memory demonstration submitted to the Agent Memory and Coordination track.
_Avoid_: Finished commercial product

**Research outcome**:
The paper and reproducible evidence investigating whether graph-based memory changes and agent handoffs improve reliability.
_Avoid_: Winning demo as proof of research novelty

**Commercial offering**:
A validated, supported way for other organizations to use the memory core in their own applications.
_Avoid_: Hackathon prototype as a sale-ready system

**Event receipt**:
Acknowledgment that an original message or observation was saved. It does not by itself mean its meaning is understood or ready for an agent to use.

**Ready memory**:
A saved event whose supported interpretation has been applied. Its claims may still be proposals, disputed statements or missing required facts.

**Unclear requirement**:
A confirmed requirement whose meaning has not been established. It needs clarification before an agent relies on potentially outdated requirements.

**Belief score**:
A changing indicator of the strength and freshness of evidence for a revisable memory.
_Avoid_: Truth probability, permission, task ownership

**Protected memory**:
An explicitly approved instruction or rule that time alone does not weaken. A deliberate accepted change can end its current applicability.

**Logical retraction**:
An approved withdrawal from current use that preserves the earlier statement and the reason for withdrawing it.
_Avoid_: Erasing history

**Evidence deletion**:
An explicit request to remove retained source content, rather than merely change which statement is current.

**Execution attempt**:
One agent's currently authorized attempt to perform a task. An expired or replaced attempt cannot claim completion for the new owner.

**Handoff**:
The requirements, evidence, work state and review reasons another agent needs to continue appropriately.

**Agent profile**:
The role, specialties and working style assigned to an agent.
_Avoid_: Traveller persona

**Traveller profile**:
A person's stated enduring travel preferences, kept separate from requirements for one trip.
_Avoid_: Guessed personality, current mood

**Trip brief**:
The current requirements and goals for one identified trip.
_Avoid_: Permanent traveller profile

**Mood state**:
A person's explicitly stated temporary preference for the experience or interaction in a particular session or trip.
_Avoid_: Psychological diagnosis, permanent personality

**Task card**:
A focused description of the preferences, requirements and guidance relevant to one task or stated mood, with the evidence supporting it.
_Avoid_: Independent source of truth
