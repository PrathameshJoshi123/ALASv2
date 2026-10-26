# Agent Guidelines for ALAS UI Development

## ⚠️ MANDATORY RULE: READ UI ARCHITECTURE FIRST
Before creating, refactoring, or modifying any page or component in this repository, **YOU MUST READ AND ADHERE TO**:
👉 [`UI_ARCHITECTURE.md`](file:///d:/My_Space/MajorProject/UI_ARCHITECTURE.md)

Every UI element in ALAS must strictly comply with the architectural and aesthetic standards defined in that document.

---

## Core Development Rules

### 1. Non-AI, Institutional Legal Aesthetic
- **NO Generic AI Styling**: Never use multi-colored rainbow gradients, glowing neon boxes, floating sparkle badges, or tacky animations.
- **Tone**: Clean, authoritative, dense, high-contrast, institutional legal tech (like Linear, Ironclad, Harvey).
- **Colors**: Rely on slate neutrals (`#0F172A`, `#F8FAFC`, `#E2E8F0`), restrained blue accents (`#2563EB`), and muted semantic colors for risks.

### 2. Component Reusability with Shadcn UI
- **Always Reuse `@/components/ui`**:
  - Never write raw `<button className="...">` or ad-hoc custom card wrappers when a Shadcn primitive (`<Button>`, `<Card>`, `<Badge>`, `<Input>`, `<Dialog>`, `<Table>`, `<Tabs>`) exists in `frontend/components/ui/`.
  - Combine class names using the `cn(...)` utility from `@/lib/utils`.

### 3. Strict Routing & Information Architecture
- **Contract Analysis**:
  - Root: `/dashboard/analysis`
  - Upload: `/dashboard/analysis/upload`
  - Detail Suite: `/dashboard/analysis/[id]`
- **Contract Drafting**:
  - Studio Home: `/dashboard/drafting`
  - Live Editor & Redline Studio: `/dashboard/drafting/editor/[id]`
- **Case Files (Litigation)**:
  - Repository: `/dashboard/cases`
  - Case Workspace: `/dashboard/cases/[id]`
  - Chronological Timeline & Cross-Doc Intel: `/dashboard/cases/[id]/results`
- **Executive Command Center**:
  - Route: `/dashboard`
- **FORBIDDEN ROUTES**:
  - Never resurrect `/dashboard/tenant-files`, `/dashboard/templates`, or `/dashboard/my-contracts`.

### 4. Code Quality & Consistency
- All new pages must implement the Standard Page Anatomy defined in `UI_ARCHITECTURE.md`.
- Always handle loading, empty, and error states gracefully with skeleton loaders or clean empty state cards.
- Ensure full keyboard accessibility, clear focus rings, and responsive mobile/desktop layouts.
- Preserve all existing API client methods and contracts in `frontend/services/api.ts`.
