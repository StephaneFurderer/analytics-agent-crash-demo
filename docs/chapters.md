# Chapter tags

Each **Chapter** is an annotated git tag on a linear `main`. `uv run demo chapter N` checks it out and resets the
warehouse and the Context layer to it (see the README).

## Naming

`chN-<slug>`, exactly one annotated tag per Chapter. `demo chapter N` resolves the single annotated tag matching
`chN-*` and refuses if there are none or several (lightweight tags are ignored).

| Ch | Tag |
|---|---|
| 0 | `ch0-setup` |
| 1 | `ch1-legacy-dashboard` |
| 2 | `ch2-raw-schema` |
| 3 | `ch3-rules` |
| 4 | `ch4-business-glossary` |
| 5 | `ch5-expert-judgment` |
| 6 | `ch6-metric-layer` |
| 7 | `ch7-trust` |

Re-cut a tag under the same name; never leave an old and a new tag for one Chapter side by side.

## Annotation convention

The tag message is what a follower reads instead of watching the video. `demo chapter N` prints it after the jump,
and `git tag -n99 ch3-rules` or `git show ch3-rules` shows it at any time. Use this shape:

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
git tag -a ch3-rules -F ch3.txt          # first cut
git tag -a -f ch3-rules -F ch3.txt <sha> # re-cut (before publishing only)
```

## Tag policy

- **Until recording, tags are re-cut freely.** Fixing an earlier chapter means rewriting `main` from that point and
  re-cutting that chapter's tag and every later one, so each chapter stays clean on camera.
- **Once a chapter is recorded and published, its tag is frozen.** It is never moved or deleted, and `main` is no
  longer rewritten before it. Later fixes are new commits on `main`; if a fix matters to followers, say so in the
  README rather than moving the tag. This keeps followers' clones and links working.
- Pushing a re-cut tag needs `git push --force origin <tag>`. After publishing, never do that.
