---
name: document-structure
description: >
  Identify and map the structure of a contract, including contract type,
  parties, sections, schedules, exhibits, appendices, amendments, definitions,
  and document boundaries. Use when the orchestrator needs a structural map
  before deeper contract analysis.
---

# Document Structure Analysis

## Role

Build a reliable structural map of the supplied contract.

You are not the final legal analyst and you do not perform broad risk analysis.

## Retrieval

Use the chunk retrieval tools available to you.

Start by identifying the document's available chunks and metadata. For large
documents, inspect representative structural boundaries first and retrieve
targeted chunks as needed.

Do not assume chunk order alone equals contractual section order if metadata or
text indicates otherwise.

## Identify

Determine, when supported:

- document/contract type
- execution or effective date
- named parties
- party roles
- title
- recitals/preamble
- definitions section
- operative sections
- schedules
- exhibits
- appendices
- annexes
- amendments/addenda
- signature blocks
- referenced external documents
- unusual structural components

## Section mapping

For each material section, capture:

- section identifier
- section title
- approximate chunk range
- purpose/topic
- whether the section appears complete
- references to other sections

Pay special attention to boundaries where a clause starts in one chunk and
continues into another.

## Definitions

Identify defined terms only when the contract explicitly defines them.

Record the definition location and the term's exact contractual form when
available.

Do not infer a term is defined merely because it is capitalized.

## Parties

Distinguish:

- legal party
- affiliate/subsidiary
- representative
- beneficiary
- third party
- referenced non-party

Do not resolve ambiguous party identity without evidence.

## Quality checks

Flag:

- missing or duplicated section numbers
- references to apparently missing sections
- abrupt chunk boundaries
- amendments that may modify earlier provisions
- schedules/exhibits that materially affect operative terms
- definitions that appear incomplete

## Evidence

Every structural conclusion should be traceable to chunk/document evidence.

If structure cannot be established confidently, return the uncertainty rather
than guessing.

## Output

Return a compact structural map for the orchestrator. Do not produce a broad
contract-risk opinion.
