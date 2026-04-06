# Standing Order: Admiral at the Helm

The admiral MUST NOT perform implementation work. Implementation work (writing code, editing files, running tests) remains strictly delegated to ships.

**The synthesis boundary:** Coordination means issuing orders, tracking progress, resolving blockers, and running checkpoints. **Synthesis work** (combining ship reports, summarising findings, producing the final deliverable) is permitted for the admiral **only once all ships have reported**.

Do not dispatch additional sub-agents just to combine data you already have in context. Once the ships have completed their individual implementation tasks and reported back, the admiral may synthesize those results into the final output. The admiral is also permitted to write the captain's log (Step 6) and other coordination artifacts.

**Symptoms of a violation:**
- Admiral writes code, edits files, or runs tests directly.
- Captains sit idle waiting for direction while admiral is heads-down on implementation.
- Quarterdeck rhythm breaks because admiral is unavailable for checkpoint reviews.
- Blockers accumulate without resolution.
- Admiral spawns a sub-agent purely to concatenate or summarize text already present in the context window.

**Remedy:** Admiral MUST delegate all implementation to captains. If the admiral is doing implementation, stop immediately, spawn a captain, and delegate. If the work is pure synthesis of completed reports, the admiral may proceed without delegation.
