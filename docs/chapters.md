# Chapter tags

Each **Chapter** is an annotated git tag on a linear `main`. `uv run demo chapter N` checks it out and resets the
warehouse and the Context layer to it (see the README).

## Naming

`chapter-N`, where N is 0 to 7. One tag per Chapter. `demo chapter N` accepts only annotated tags.

## Annotation convention

The tag message is what a follower reads instead of watching the video. `demo chapter N` prints it after the jump,
and `git tag -n99 chapter-N` or `git show chapter-N` shows it at any time. Use this shape:

```
Chapter N: <title>

What this chapter adds:
- <the context files, code or data introduced, in one line each>
- <the point the chapter makes>

Accuracy matrix (Working set, correct on all 3 runs):

| Tier       | Ch2 | Ch3 | ... | ChN |
|------------|-----|-----|-----|-----|
| Lookup     |  x% |  x% |     |  x% |
| Definition |  x% |  x% |     |  x% |
| Judgment   |  x% |  x% |     |  x% |

Held-out set: <x% overall, or "not run in this chapter">
Benchmark: <date>, <model>, <cost reported by nao test>
```

- The title matches the chapter table in the README.
- The matrix comes from `uv run demo report` for that chapter (Chapters 0 and 1 have no agent, so no matrix).
- Each chapter's matrix includes all earlier chapters' columns, so the latest tag carries the full story.

Create a tag with the message in a file, so the table stays intact:

```sh
git tag -a chapter-3 -F chapter-3.txt          # first cut
git tag -a -f chapter-3 -F chapter-3.txt <sha> # re-cut (before publishing only)
```

## Tag policy

- **Until recording, tags are re-cut freely.** Fixing an earlier chapter means rewriting `main` from that point and
  re-cutting that chapter's tag and every later one, so each chapter stays clean on camera.
- **Once a chapter is recorded and published, its tag is frozen.** It is never moved or deleted, and `main` is no
  longer rewritten before it. Later fixes are new commits on `main`; if a fix matters to followers, say so in the
  README rather than moving the tag. This keeps followers' clones and links working.
- Pushing a re-cut tag needs `git push --force origin chapter-N`. After publishing, never do that.
