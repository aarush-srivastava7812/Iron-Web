# Publish and submit the blog yourself

The draft is complete apart from your public video link and image uploads. Nothing has been published or submitted.

## 1. Prepare the video and images

- Finish your current YouTube upload using the [YouTube upload package](../youtube-upload/README.md). Use the corrected `ironweb-voyara-2m58-final.mp4`: it retains the supplied voice and already has burned-in captions. Enable viewing without sign-in.
- Copy its viewer URL. Replace `TODO-demo-video` in the post with it, then remove the `[NORTH: ...]` line near the end.
- The screenshot files to upload are [before](../docs/screenshots/demo-2026-10-18/context-budget-before.png) and [after](../docs/screenshots/demo-2026-10-18/context-budget-after.png). These are the canonical recorded demonstration screenshots.

## 2. Publish on DEV

1. Sign in at [DEV](https://dev.to) and choose **Write a Post**.
2. Open [the DEV-ready draft](graph-hacks-post-devto.md). In the rich + Markdown editor, put the front-matter title in the title field and paste only the body below the closing `---`. Add the four tags `falkordb`, `ai`, `agents`, `hackathon` using the tags field.
3. If you use DEV's Basic Markdown editor instead, paste the entire DEV-ready file, including its front matter. Leave `published: false` while reviewing.
4. Upload both screenshots through the editor. Replace `TODO-screenshot-before` and `TODO-screenshot-after` with the returned image URLs, or replace those complete Markdown image lines with the editor-generated lines. Remove the italic upload instruction below them; retain a short factual caption if useful.
5. Replace `TODO-demo-video`, remove the NORTH line, and read the first-person wording once to ensure it reflects your experience. Retain the AI-assistance disclosure.
6. Preview the post. Check the diagram, both Cypher blocks, images, and links. Search for `TODO-` and `[NORTH:`; neither should remain. You can publish without a cover image; optionally use an existing dashboard screenshot.
7. Click **Publish**. In the Basic Markdown editor, change `published: false` to `published: true` and save. Open the resulting article URL in a signed-out/private window and verify access.

DEV accepts a maximum of four tags. The [master draft](graph-hacks-post.md) retains the five tags you requested; the DEV copy omits `graphdb`. Source: [DEV editor guide](https://dev.to/p/editor_guide). The publishing flow follows [DEV's help page](https://dev.to/help/writing-editing-scheduling). The disclosure follows [DEV's AI-assisted article guidance](https://dev.to/guidelines-for-ai-assisted-articles-on-dev).

For Hashnode instead, create an article in your blog dashboard, enter the master draft's title, paste its body without YAML front matter, and apply the requested tags through its editor. Upload the same images, fix the video link, preview, and publish. Exact Hashnode controls were not checked in this session.

## 3. Submit the public article link

1. Open [Graph Hacks submission](https://www.wemakedevs.org/hackathons/falkordb/submit) and sign in using your registration account.
2. Open your project submission and retain **Track 02: Agent Memory and Coordination**, as you confirmed.
3. Add the public article URL in the blog field if the panel provides one. Include the public repository and demo-video URLs in their corresponding fields.
4. If no blog field appears, add the article URL to the project description/additional links where supported. Follow the panel's instructions or organizer guidance for the side-prize entry. The authenticated form and its field names were not accessible during this check.
5. Save/submit, reopen the submission, and confirm the article and demo URLs were retained. Follow any event-specific Discord instruction shown there.
6. Complete this before **October 18, 2026, 11:59 PM IST**. The organizer confirms the deadline and that team/submission management uses the registration panel: [official event page](https://www.wemakedevs.org/hackathons/falkordb).

Read [verification notes](verification-notes.md) for the remaining public-access and event-eligibility questions. No upload, publication, deployment, or submission was performed by the assistant.
