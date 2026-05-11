# Why eda-parse Exists

AI-native EDA systems need more than RTL snippets and natural-language specs. Real design work lives in dense artifacts: Liberty timing libraries, LEF/DEF physical data, SDC constraints, VCD waveforms, SPEF parasitics, reports, logs, scripts, and internal documentation.

Most teams building retrieval or agent workflows over chip data end up writing the same adapters privately. Siemens describes specialized EDA parsers as part of its Fuse EDA AI stack, ChipAgents points to the complexity of EDA toolchains as an agent problem, and Simon Davidmann has argued that useful AI for EDA needs more open structure, data, and collaboration across the stack.

`eda-parse` is a small infrastructure layer for that gap:

1. Parse common EDA formats into structured Python objects.
2. Emit semantic chunks suitable for embedding and retrieval.
3. Preserve metadata for filtering, provenance, and validation.
4. Provide LangChain-compatible loaders without hiding the raw AST.

This is not a claim to solve chip design. It is plumbing for teams building systems that need to understand chip-design artifacts.

## References

- Siemens Fuse EDA AI Agent press release: https://news.siemens.com/en-us/siemens-fuse-eda-ai-agent/
- ChipAgents blog on AI agents and EDA toolchains: https://chipagents.ai/blogs/ai-agents-tool-selection
- Simon Davidmann, "The Real EDA Problem AI Is Not Solving": https://www.ednasia.com/the-real-eda-problem-ai-is-not-solving/
