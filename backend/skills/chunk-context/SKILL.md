---
name: chunk-context
description: >
  Analyze local context around contract chunks, including section boundaries,
  continuation, party/speaker position, incomplete references, anaphora, and
  dependencies between neighboring chunks. Use when a chunk's meaning depends
  on surrounding contract text.
---

# Chunk Context Analysis

## Role

Determine the contextual meaning of a contract chunk without over-interpreting
it.

The current chunk is the primary source of truth.

## Retrieval

Use the chunk retrieval tools available to you.

When analyzing a chunk, retrieve neighboring chunks when needed to resolve:

- sentence continuation
- paragraph continuation
- section boundaries
- pronouns
- "the foregoing"
- "such party"
- "the agreement"
- "the aforesaid"
- incomplete references
- party identity

Do not retrieve broad portions of the document unless local context is
insufficient.

## Analyze

Determine, when supported:

- section type
- section title
- document role
- party/speaker position
- topic
- whether the chunk continues from the previous chunk
- whether it continues into the next chunk
- dependencies on preceding/following chunks
- incomplete or anaphoric references
- important contextual warnings

## Critical distinctions

Do not confuse:

- allegation with finding
- submission with fact
- argument with factual assertion
- party position with neutral statement
- cited law with applied law
- evidence description with established fact
- definition reference with definition content

For ordinary commercial contracts, adapt these distinctions to contractual
language while preserving the same evidence discipline.

## Neighbor use

Use neighboring chunks only to interpret the current chunk.

Do not copy unrelated facts from neighbors into the current chunk's findings.

If the current chunk and neighbors conflict, report the conflict rather than
choosing silently.

## Merged chunks

If the input indicates that multiple original chunks were merged:

- analyze the merged text as a coherent logical unit;
- preserve awareness of original chunk IDs;
- identify internal boundaries when relevant;
- do not assume the merged text represents one contractual clause.

## Uncertainty

Use UNKNOWN/uncertain when context cannot be resolved from available text.

Never fill missing context from general contract conventions.

## Output

Return contextual findings with chunk IDs and evidence references. Focus on
context, not entity normalization, risk, or broad clause analysis.
