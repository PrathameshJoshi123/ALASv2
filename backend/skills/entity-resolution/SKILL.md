---
name: entity-resolution
description: >
  Resolve and normalize parties, organizations, people, defined terms,
  affiliates, properties, documents, and other contractual entities across
  chunks. Use when references such as "the Company", "Affiliate", "Seller",
  "such party", or defined terms need identity resolution.
---

# Entity Resolution

## Role

Build reliable entity identity across the contract.

Your job is entity resolution, not legal risk analysis.

## Retrieval

Use the available chunk retrieval/search tools.

Start with the chunk containing the mention. Retrieve:

- the preceding/following context when needed;
- the party-identification section;
- the relevant definitions;
- other occurrences of the same term/reference;
- referenced provisions when identity depends on them.

Do not retrieve the whole contract unless necessary.

## Entity categories

Consider:

- legal parties
- individuals
- organizations
- affiliates
- subsidiaries
- parent entities
- representatives
- customers/vendors/licensees/licensors
- properties/assets
- contracts and referenced documents
- defined terms
- products/services
- regulatory or governmental entities

## Resolution procedure

For each material mention:

1. Capture the surface form.
2. Determine entity category.
3. Search for explicit identification or definition.
4. Check nearby context.
5. Check repeated mentions and contractual role.
6. Determine the canonical identity only if supported.
7. Record aliases/mentions.
8. Record evidence.
9. Assign confidence based on evidence, not intuition.

## Defined terms

A defined term should be resolved using its explicit contractual definition
when available.

Do not equate similarly named terms automatically.

Example:
"Affiliate" and "Affiliated Entity" are not necessarily the same entity.

## Pronouns and references

Resolve "it", "they", "such party", "the foregoing party", etc. only when
the grammatical and contractual context supports the resolution.

If two candidates remain plausible, preserve both possibilities and flag the
ambiguity.

## Party roles

Do not confuse identity with role.

A party may have multiple roles in different provisions. Preserve the legal
identity and separately record the role in context.

## Cross-document references

If the contract references another agreement/document, distinguish:

- the referenced document itself;
- parties to that document;
- terms defined by that document;
- entities mentioned inside it.

Do not import facts from an external document unless that document is actually
available to the system.

## Evidence

Every canonical resolution should have supporting chunk/section evidence.

## Output

Return normalized entity findings, aliases, roles, unresolved references,
confidence, and evidence.

Do not perform clause/risk analysis unless needed solely to resolve identity.
