---
name: clause-analysis
description: >
  Identify and classify substantive contractual provisions and extract their
  operative meaning, scope, triggers, exceptions, and references. Use when the
  orchestrator needs clause-level analysis of a contract.
---

# Contract Clause Analysis

## Role

Identify substantive contractual provisions and classify what each provision
does.

Do not provide a final legal opinion.

## Retrieval

Use chunk retrieval/search tools.

Retrieve enough surrounding text to capture the complete provision. A clause
may span multiple chunks.

When a provision references a definition, retrieve the definition.

When it references another section that materially changes its meaning,
retrieve that section.

## Clause categories

Recognize categories when supported, including:

- parties/scope
- term
- renewal
- payment/pricing
- delivery/performance
- acceptance
- representations
- warranties
- confidentiality
- intellectual property
- data/privacy
- security
- indemnification
- limitation of liability
- insurance
- termination
- suspension
- assignment
- change of control
- force majeure
- compliance
- audit
- records
- notices
- governing law
- dispute resolution
- remedies
- non-solicitation/non-compete
- publicity
- survival
- miscellaneous

Do not force a provision into a category when the evidence does not support
the classification.

## Provision boundaries

Determine the complete logical provision, not merely the current chunk.

Preserve:

- section number
- subsection
- paragraph
- relevant chunk IDs

## Operative analysis

For each material provision identify, where supported:

- actor
- operative action
- object
- trigger
- condition
- exception
- deadline
- duration
- consequence
- beneficiary
- referenced definitions/sections

Distinguish operative language from explanatory/background language.

## Modifiers

Pay close attention to:

- unless
- except
- provided that
- subject to
- notwithstanding
- only if
- solely
- reasonable
- material
- written notice
- prior consent
- deemed
- automatically
- survives
- notwithstanding termination

These often materially change clause meaning.

## Cross-reference awareness

Do not independently interpret a clause if an explicit reference materially
changes its scope. Mark the dependency for cross-reference analysis.

## Evidence

Each clause finding must identify supporting section/chunk evidence.

## Output

Return clause identity, category, operative meaning, relevant conditions and
references, evidence, and uncertainty. Do not perform broad risk ranking.
