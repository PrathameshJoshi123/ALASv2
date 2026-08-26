---
name: obligation-rights
description: >
  Extract contractual obligations, rights, permissions, prohibitions,
  conditions, triggers, deadlines, exceptions, and consequences for each
  party. Use after relevant clauses have been identified or when the
  orchestrator needs a party-centric view of the contract.
---

# Obligations and Rights Analysis

## Role

Translate contractual operative language into structured party-centric
obligations and rights without inventing meaning.

## Retrieval

Use the chunk retrieval tools.

Retrieve the complete provision and any definitions or referenced sections
needed to determine the obligation's scope.

Do not rely on a clause title alone.

## Classify

Distinguish:

- obligation: a party is required to act/refrain
- right: a party is entitled to act or demand something
- permission: a party may act
- prohibition: a party must not act
- condition: an event/state that controls another provision
- trigger: event that activates an obligation/right
- representation/warranty: statement with contractual significance
- consequence/remedy: result following an event or breach

## Extraction model

For each material item identify:

- actor
- obligation/right type
- action
- object
- beneficiary
- trigger
- condition
- deadline
- frequency
- duration
- exception
- prerequisite
- consequence
- survival
- supporting section/chunk IDs

Use null/unknown when the contract does not specify a field.

## Conditional language

Pay special attention to:

- if
- when
- upon
- provided that
- subject to
- unless
- except
- after
- before
- within
- no later than
- from and after
- until
- during
- following termination

Do not convert a conditional obligation into an unconditional one.

## Party identity

Use resolved entity information when available, but verify the relevant
contractual role in the provision itself.

Do not assume "Company" always means the same role if the contract defines it
differently.

## Deadlines and dates

Preserve exact contractual language.

Do not calculate dates unless the necessary reference date and calculation
rules are explicit.

If a deadline depends on another event, represent that dependency.

## Exceptions and carve-outs

An exception can materially change an obligation. Include it in the finding.

Do not report "Party A must X" if the actual clause says "Party A must X except
under Y" without recording the exception.

## Evidence

Every material obligation/right must be traceable to its provision.

## Output

Return structured party-centric findings suitable for downstream risk and
cross-reference analysis.
