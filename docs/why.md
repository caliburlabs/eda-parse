# Why eda-parse Exists

## The structural gap

Chip-design complexity is growing roughly 50% per year while design productivity grows only about 20% per year. That gap — chronicled by SemiAnalysis in its 2026 EDA primer — is structural, not cyclical: the AI-driven explosion in compute demands ever-bigger SoCs (AMD's MI455X packs 320 billion transistors across twelve dies on 2nm/3nm), one-third of the U.S. semiconductor workforce is over fifty-five, and EE graduate pipelines aren't filling the gap. Verification alone now consumes up to **70% of total project effort** and verification engineers are the fastest-growing role in chip development.

The industry's response has been Electronic Design Automation (EDA) — the software layer that translates human intent into manufacturable silicon. Without EDA, no chip designed after the mid-1980s would exist. But the EDA layer itself runs on file formats — Liberty (`.lib`), LEF, DEF, SDC, VCD, SPEF, GDSII, plus dozens of vendor-specific reports and logs. Those formats carry the actual design information; everything else (RAG pipelines, agent workflows, code-review bots, retrieval over engineering corpora) needs to read them.

## What's broken

Every serious AI-for-EDA team is currently building the same parser layer privately:

- **Synopsys (DSO.ai)**, **Cadence (Cerebrus / Joint AI)**, **Siemens (Fuse)** — the EDA Big Three, each with its own internal agent platform and its own private parsers. Siemens names "specialized parsers for EDA file formats" as a Fuse differentiator.
- **NVIDIA** — internal agentic flows for "AI accelerators designing future AI accelerators."
- **Cognichip, ChipAgents, Astrus, Normal Computing** — startups in adjacent lanes, each rebuilding the same ingestion layer.
- **Academic groups** (UCSD's Kahng with ORFS-agent, multiple others) — published agents that needed parsers built first.

Nobody shares. The work gets reinvented behind every NDA. The parser layer is treated as a moat instead of common infrastructure, which slows everyone outside the largest teams and concentrates capability where the engineering budget is biggest.

## The wedge

`eda-parse` is the open observability layer for chip-design artifacts. It deliberately occupies the lane the closed agents from Synopsys/Cadence/Siemens/NVIDIA *don't* compete on: not optimization (DSO.ai, Cerebrus, ORFS-agent all do PPA tuning), but **diagnosis and reading**. The parser turns dense EDA bytes into structured, retrievable, LLM-friendly documents — and stops there.

What that gets us:

1. **Parse common EDA formats into structured Python objects** — Liberty, LEF, SDC today; DEF, VCD, SPEF on the roadmap. Validated against real industrial PDKs (SKY130, NanGate FreePDK45, ASAP7), not toy fixtures.
2. **Emit semantic chunks ready for embedding and retrieval** — one per cell for Liberty, one per macro for LEF, one per constraint for SDC. Chunk metadata is structured for vector-store filtering.
3. **Preserve metadata + raw AST** — agent-callable summaries on top, full AST underneath for consumers who need lower-level access.
4. **LangChain-compatible loaders** — drop-in for any RAG stack; LangChain itself is an optional extra so the core library has zero ML dependencies.

`eda-parse` is the substrate. The complementary half — `benchmarks/timing_diagnosis/` and the agent harness in `benchmarks/timing_diagnosis/agent.py` — is the *measurement layer* that turns "we have parsers" into "here is whether agents using these parsers can actually do EDA work." See [bench-design.md](bench-design.md) for that side.

## Why now

SemiAnalysis Part 3 (forthcoming, 2026) will name and frame "agentic chip design flows" as a category. When it does, every AI-EDA pitch will need to answer: *what's measurable here?* Today there is no shared answer. The first credible public benchmark for agent capability on chip-design diagnosis becomes the citation rather than a footnote.

The Calibur Labs bet is that **openness + observability + measurement** beats "build a better closed agent" — because the closed agents have to compete against the open instrument. We're not trying to build the next Cerebrus. We're building the layer that makes any agent's work on chip artifacts legible, comparable, and falsifiable.

## What this is not

- **Not a replacement for OpenSTA, OpenROAD, or KLayout** — those are EDA tools. eda-parse is the data-ingestion layer beneath an LLM stack.
- **Not a high-fidelity simulator** — we extract the structured fields useful for retrieval and reasoning, not every numerical detail of every LUT. Raw AST is preserved for consumers that need depth.
- **Not a reverse-engineering project for proprietary binary formats** (FSDB, OpenAccess libraries). Where open work exists upstream, we wrap; where it doesn't, we don't reimplement.
- **Not a place for proprietary PDK fixtures.** Test fixtures are SKY130 / FreePDK45 / ASAP7 (all redistributable). Validation against TSMC, GPDK, AMS, MUMPs happens privately on academic-cluster instances; only summary statistics ever come back into the public repo.

## References

- SemiAnalysis, *The EDA Primer: From RTL to Silicon* (2026-05). The 50% / 20% productivity gap, 70% verification effort, and Big Three landscape are sourced here.
- Siemens Fuse EDA AI Agent — names "specialized parsers for EDA file formats" as a moat.
- ChipAgents — flags EDA toolchain complexity as an agent problem.
- Simon Davidmann, *The Real EDA Problem AI Is Not Solving* — argues for more openness in the AI-EDA stack.
- Kahng et al., *ORFS-agent: Tool-Using Agents for Chip Design Optimization* (arXiv 2506.08332, 2025) — the closest published prior art; owns the PPA-optimization lane while the diagnosis lane stays open.
- METRICS2.1 (Jung, Kahng, Kim, Varadarajan, ICCAD 2021) — the canonical JSON metric schema for ORFS, which the bench grader's golden format aligns with.
