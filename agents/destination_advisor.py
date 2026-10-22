"""Fast destination advice from the current draft and actual catalog evidence."""
import re


def recommendation_intent(text):
    return bool(re.search(r"\b(?:suggest|recommend|somewhere|some places|other (?:places|options)|see more|show more|none of these|don't like (?:any|these)|start destination list again|anywhere|choose a destination|not sure where|don't know where)\b", text, re.I))


def more_requested(text):
    return bool(re.search(r"\b(?:other|else|different|more|none of these|don't like (?:any|these)|not these)\b", text, re.I))


class DestinationAdvisor:
    def explain(self, item, draft):
        evidence = (" ".join(item.get("tags", [])) + " " + item.get("description", "")).lower()
        reasons = []
        if draft.get("pace") == "relaxed" and any(token in evidence for token in ("relax", "quiet", "unhurried", "slow", "wellness", "gentle")):
            quote = item.get("description", "").split(". ")[0].rstrip(".")
            reasons.append("For your relaxed pace: " + quote + ".")
        for interest in draft.get("interests", []):
            if interest.lower() in evidence:
                reasons.append(f"Matches your {interest} interest in the destination's catalog description or tags.")
        if not reasons:
            reasons.append("An alternative to explore from the catalog; a closer preference match is not yet established.")
        if draft.get("budget"):
            reasons.append(f"Your ₹{draft['budget']:,} spending limit is saved; the guide price alone does not confirm a whole-trip fit.")
        if draft.get("traveller_count") == 1:
            reasons.append("For your solo budget: displayed travel fares are calculated for one traveler.")
        return dict(item, match_reasons=reasons, why_fit=" ".join(reasons[:2]))

    def suggest(self, catalog, draft, text="", *, previous=()):
        context = " ".join([text, draft.get("pace") or "", *draft.get("interests", []), *draft.get("soft_preferences", [])]).casefold()
        relaxing = bool(re.search(r"\b(?:relax\w*|unwind|peace\w*|quiet|chill|slow\w*|unhurried)\b", context))
        beach = bool(re.search(r"\b(?:beach\w*|sea|seaside|coast\w*)\b", context, re.I))
        mountain = bool(re.search(r"\b(?:mountain\w*|hills?|forest\w*)\b", context, re.I))
        other = more_requested(text)
        budget = draft.get("budget")

        def score(item):
            tags = " ".join(item.get("tags", [])).lower()
            evidence = (tags + " " + item.get("description", "")).lower()
            result = 0
            if relaxing:
                result += sum(weight for word, weight in [("relax", 8), ("wellness", 6), ("slow travel", 6),
                    ("quiet", 4), ("unhurried", 4), ("gentle", 3), ("slower", 3), ("yoga", 2)] if word in evidence)
            if beach:
                result += 16 if any(word in tags for word in ("beach", "coastal", "island")) else -8
            if mountain:
                result += 16 if any(word in tags for word in ("mountain", "nature")) else -8
            result += sum(3 for tag in item.get("tags", []) if tag.lower() in context)
            # A catalog guide price is a ranking hint, never a verified trip total.
            if budget and item.get("price_inr", 0) > budget:
                result -= 12
            if draft.get("origin"):
                result += 2 if item.get("transport", {}).get("costs_complete") else -2
            return result

        candidates = [item for item in catalog if not (other and item["name"] in previous)]
        ranked = sorted(candidates, key=lambda item: (-score(item), item.get("price_inr", 0), item["name"]))[:3]
        # Explain the actual source rather than inventing a claim about safety,
        # supplier availability or a guaranteed within-budget trip.
        return [dict(self.explain(item, draft), recommendation_score=score(item)) for item in ranked]

    def reply(self, ranked, draft, *, followup=False):
        solo = draft.get("traveller_count") == 1
        relaxed = draft.get("pace") == "relaxed"
        budget = draft.get("budget")
        if followup:
            lead = "For the kind of break you described, these are the places I'd look at first."
        elif relaxed:
            lead = "A little time to unwind" + (" on your own" if solo else "") + " sounds like the direction to take."
        else:
            lead = "Let's find a place that fits the kind of trip you have in mind."
        if budget:
            lead += f" I'll keep your ₹{budget:,}" + (" solo" if solo else "") + " budget in mind."
        lines = [f"{item['name']} — {item['why_fit']}" for item in ranked]
        tail = "My first pick would be " + ranked[0]["name"] + ". " if ranked else ""
        tail += ("Which city will you be starting from? That will let me check travel fares for you."
                 if not draft.get("origin") else "Which of these feels more like your kind of escape?")
        if budget:
            tail = "The card prices are sample guides; dates and travel from your city will determine the full cost.\n\n" + tail
        return lead + "\n\n" + "\n\n".join(lines) + "\n\n" + tail
