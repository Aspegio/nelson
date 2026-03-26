# Standing Order: Light Squadron

Do not group independent tasks onto fewer captains than their independence warrants.

**Symptoms:**
- Multiple sections, documents, or code areas are bundled onto one captain when they share no files and have no sequencing dependency.
- The captain serializes work that could run concurrently, extending wall-clock time with no benefit.
- The battle plan has fewer captains than there are independent work units.
- Admiral defaults to a fixed captain count without first counting the parallelizable leaves.

**Remedy:** Split bundled tasks onto separate captains. The number of captains should equal the number of truly independent work units, bounded by the squadron cap.

Ask: "What is the maximum number of tasks that can run concurrently with zero shared state?" That number is the target captain count.

Only bundle tasks onto one captain when they:
- Share files where parallel edits would produce unresolvable merge conflicts (same functions, tight coupling) — use `isolation: "worktree"` when files overlap but merge cost is justified (see `squadron-composition.md`), or
- Have a genuine sequencing dependency (task B requires output of task A), or
- Are so small that the context-setup cost of a separate agent clearly exceeds the work itself.

See also `standing-orders/crew-without-canvas.md` for the inverse risk: do not add agents without reducing critical path length.
