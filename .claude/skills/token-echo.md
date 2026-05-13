---
name: token-echo
description: Compresses and maintains conversation context efficiently. Use when context is getting long, token usage is high, or to preserve important information across interactions.
---

When managing context compression ("token echo"), follow this strategy:

## 1. Detect Context Growth
- Identify when conversation becomes long or repetitive
- Recognize redundant explanations or repeated ideas
- Trigger compression when signal-to-noise ratio drops

## 2. Extract Core Information
Condense the conversation into:
- **Goals**: What the user is trying to achieve
- **State**: Current progress or situation
- **Key Data**: Important variables, decisions, constraints
- **Problems**: Errors, blockers, unresolved issues

## 3. Remove Redundancy
- Eliminate repeated explanations
- Merge similar ideas into one concise statement
- Drop irrelevant or outdated context

## 4. Create a "Compressed Memory Block"
Rewrite context into a structured compact format:

Keep it minimal but complete.

## 5. Progressive Compression (Token Echo)
- Each new interaction:
  - Update only what changed
  - Reuse previous compressed block
  - Avoid re-expanding old context
- Think of it as "state sync", not "conversation replay"

## 6. Smart Re-expansion
- Expand details ONLY when needed
- If user asks for specifics, reconstruct from compressed data
- Never dump full original context unless necessary

## 7. Optimization Heuristics
- Prefer bullet points over paragraphs
- Replace verbose text with structured data
- Use short labels instead of explanations
- Keep under ~30–40% of original token size

## 8. Safety Check
Before finalizing:
- Ensure no critical info was lost
- Verify goals and constraints are preserved
- Maintain logical continuity

## Output Style
- Always show the compressed block when compression occurs
- Keep it clean, structured, and readable
- Avoid unnecessary prose

Goal: Maximize information density while minimizing token usage.
## 9. Compression Modes
- LIGHT: small cleanup, minimal reduction
- MEDIUM: structured summary (default)
- AGGRESSIVE: extreme compression, only critical info

Choose mode based on context size and importance.