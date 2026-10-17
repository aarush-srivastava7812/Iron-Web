# Voyara reference layout update

The homepage follows the user's second reference: scenic full-width hero,
right-side agent team, overlapping travel search, seven agent cards and ten
compact packages. The destinations page follows the first: orange paper-style
hero, compact search/filter bar and a two-column collection of coloured tiles.
Both layouts have responsive mobile versions. Existing API actions are retained.

The reference images guide visual structure, not factual claims. The site does
not adopt the examples' invented traveller counts, support telephone number or
24/7 support claims. Catalog ratings/prices remain labelled as illustrative.

Several stock photos in the original ZIP showed unrelated places. The UI now
uses destination-specific Unsplash images in the public catalog presentation:

- [Udaipur, Rimjhim Agrawal](https://unsplash.com/photos/a-large-building-sitting-on-top-of-a-body-of-water-df9uYGbvKmo): `photo-1709338573277-c161cbf8702c`
- [Varanasi ghats, Unsplash collection](https://unsplash.com/s/photos/varanasi-ghat): `photo-1561359313-0639aad49ca6`
- [Rishikesh river activity](https://unsplash.com/photos/people-riding-red-kayak-on-river-during-daytime-b9xWxpbe9vw): `photo-1603867106100-0d2039fc8757`
- [Darjeeling train, Vineet Singh](https://unsplash.com/photos/a-train-traveling-through-a-lush-green-countryside-5MUM_RHvFNY): `photo-1671711847762-b8308b444a42`

Images are served remotely from the original Unsplash CDN. The remaining photos
reuse the supplied design's existing catalog. Icons and the travel mark are SVG
elements. No screenshot is used as a flattened page or background UI.

Trip memory remains unchanged. The saved conversation screen presents supported
fields as readable labels/values; technical context is expandable. Event cards
retain their backend forget action. Drafts with no shortlisted stays or
experiences show a partial-plan notice so a meal-only subtotal cannot be mistaken
for a complete holiday price. This does not manufacture missing inventory or
claim to improve the deterministic planner's recommendations.
