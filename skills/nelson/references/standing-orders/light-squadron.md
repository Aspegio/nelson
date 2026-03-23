# Standing Order: Light Squadron

Do not group independent tasks onto fewer captains than their independence warrants.

**Symptoms:**
- Multiple sections, documents, or code areas are bundled onto one captain when they share no files and have no sequencing dependency.
- The captain serializes work that could run concurrently, extending wall-clock time with no benefit.
- The battle plan has fewer captains than there are independent work units.
- Admiral defaults to "3 captains" framing without first counting the parallelizable leaves.

**Remedy:** Split bundled tasks onto separate captains. The number of captains should equal the number of truly independent work units, not a size tier. The cost of an additional haiku captain on a research or analysis mission is near zero; the cost of serialization is the full wall-clock time of the second task.

When deciding how many captains to form, ask: "What is the maximum number of tasks that can run concurrently with zero shared state?" That number is the target captain count, bounded by the squadron cap.

Only bundle tasks onto one captain when they:
- Share files that would cause conflicts if edited in parallel, or
- Have a genuine sequencing dependency (task B requires output of task A), or
- Are so small that the context-setup cost of a separate agent clearly exceeds the work itself.
