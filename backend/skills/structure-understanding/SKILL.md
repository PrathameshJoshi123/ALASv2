---
name: structure-understanding
description: >
  Analyze the template document's overall structure and layout. Use this skill
  to map template sections, headings, definitions, signature blocks, and placeholders.
---

# Structure Understanding Skill

## Role
Build a comprehensive, sequence-accurate structural map of the user-provided template document by reading all database chunks sequentially.

## Guidelines
1. **Mandatory Sequential Chunk Reading**:
   - You MUST read ALL chunks in the document sequentially starting from sequence 1.
   - Do NOT stop early, skip chunks, or guess the structure.
   - Verify the total chunk count first using `get_total_chunks_count`, then fetch chunks in increments (e.g. 1-15, 16-30, etc.) using `get_optimized_chunks_from_db` until you reach the total count.
2. **Detailed Extraction**:
   - Identify all major sections, clause headings, defined terms, boilerplate text, and blanks/placeholders.
   - Note the exact layout sequence.
