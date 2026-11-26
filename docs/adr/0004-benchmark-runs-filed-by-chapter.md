# Benchmark runs are filed by Chapter, and the Chapter comes from the checked-out tag

The **Accuracy matrix** needs every run tied to a **Chapter** and a set (Working or Held-out), but `nao test`'s results file records neither, nor the questions' tags. `demo benchmark` therefore files each run under `benchmark-results/ch<N>/<set>/results_<timestamp>.json`, and `demo report` reads the Chapter and set from that folder and the Tier from the question's YAML (joined by question name). The Chapter is the one whose `chN-*` tag is checked out, which is the state `demo chapter N` leaves you in; anywhere else (a work-in-progress commit) the run refuses until you pass `--chapter N`, so a run is never silently credited to the wrong Chapter. The latest file per Chapter and set wins; older ones are kept as history.

## Considered options

- **Infer the Chapter from the nearest earlier tag** (`git describe`): rejected, because a run made while building Chapter 4 would be filed as Chapter 3.
- **Commit the results**: rejected for now. They hold sample answer rows, and keeping them git-ignored means they survive chapter jumps (ignored files are kept), so the matrix collects one column per Chapter. The numbers that matter are copied into each tag's annotation (docs/chapters.md).

## Consequences

- A result file only counts for its own set's questions: a Held-out question found in a Working-set run is ignored, so Held-out results can never leak into Working-set Accuracy.
- A question is correct only with 3 runs, all passed; fewer runs (an interrupted run) count as incorrect and are listed in the report.
- The questions live in the nao project (`nao/tests/`, where `nao test` looks) and `nao/.naoignore` hides that folder from the agent's file tools.
