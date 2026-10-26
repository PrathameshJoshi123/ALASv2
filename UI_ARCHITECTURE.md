# ALAS UI Architecture & Design System Specification

## 1. System Vision & Aesthetic Principles
The **Autonomous Legal Advisory System (ALAS)** is an institutional-grade legal tech application designed for law firm associates, legal counsels, and litigators.
- **Tone**: Authoritative, calm, utilitarian, high-density, and precision-driven (comparable to Linear, Harvey, Ironclad).
- **Anti-Patterns (Avoid)**: No whimsical AI gradients, neon glows, decorative sparkles, or misleading placeholder names.
- **Layout Consistency**: Strict 8pt grid, predictable page header anatomy, and standardized action bars.

---

## 2. Directory Structure

```
frontend/
├── app/
│   ├── globals.css                       # Design tokens, CSS variables, typography
│   ├── layout.tsx                        # Global HTML shell & toast provider
│   ├── page.tsx                          # Public landing page
│   └── dashboard/
│       ├── layout.tsx                    # Shell layout (Header + Sidebar + Main)
│       ├── page.tsx                      # Executive Overview & Command Center
│       ├── analysis/                     # Pillar 1: Contract Analysis Hub
│       │   ├── page.tsx                  # Analysis repository & risk filters
│       │   ├── upload/page.tsx           # Document intake & audit configuration
│       │   └── [id]/page.tsx             # Deep inspection suite & Kanoon citations
│       ├── drafting/                     # Pillar 2: Contract Drafting Studio
│       │   ├── page.tsx                  # Blueprint generator & templates
│       │   └── editor/[id]/page.tsx      # Live drafting & redlining studio
│       ├── cases/                        # Pillar 3: Case Files & Litigation
│       │   ├── page.tsx                  # Case repository & intake
│       │   ├── [id]/page.tsx             # Multi-doc workspace & upload
│       │   └── [id]/results/page.tsx     # Chronological timeline & cross-doc synthesis
│       ├── analytics/                    # Operational metrics
│       └── settings/                     # User preferences & firm profile
├── components/
│   ├── ui/                               # Shadcn atomic component library
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── badge.tsx
│   │   ├── input.tsx
│   │   ├── textarea.tsx
│   │   ├── tabs.tsx
│   │   ├── dialog.tsx
│   │   ├── table.tsx
│   │   ├── separator.tsx
│   │   └── scroll-area.tsx
│   └── dashboard/                        # Domain-specific components
│       ├── Header.tsx                    # Global institutional header
│       ├── Sidebar.tsx                   # Unified 4-pillar sidebar
│       ├── ClauseRedlineModal.tsx        # Clause diff & redrafting dialog
│       ├── JuristChatDrawer.tsx          # Real-time legal research assistant
│       └── DraftingStreamConsole.tsx     # 6-stage autonomous drafting visualizer
├── services/
│   └── api.ts                            # Typed Axios API client
└── lib/
    └── utils.ts                          # `cn()` helper (clsx + tailwind-merge)
```

---

## 3. Design Tokens & Styling Guide

### A. Color Palette
```css
:root {
  --background: 210 40% 98%;          /* #F8FAFC (slate-50) */
  --foreground: 222 47% 11%;          /* #0F172A (slate-900) */
  
  --card: 0 0% 100%;                  /* #FFFFFF */
  --card-foreground: 222 47% 11%;     /* #0F172A */
  
  --popover: 0 0% 100%;
  --popover-foreground: 222 47% 11%;
  
  --primary: 222 47% 11%;             /* #0F172A Deep Institutional Slate */
  --primary-foreground: 210 40% 98%;  /* #F8FAFC */
  
  --secondary: 214 32% 91%;           /* #E2E8F0 */
  --secondary-foreground: 222 47% 11%;
  
  --muted: 210 40% 96%;               /* #F1F5F9 */
  --muted-foreground: 215 16% 47%;    /* #64748B */
  
  --accent: 221 83% 53%;              /* #2563EB Corporate Blue */
  --accent-foreground: 210 40% 98%;
  
  --destructive: 0 84% 60%;           /* #EF4444 Danger */
  --destructive-foreground: 210 40% 98%;
  
  --border: 214 32% 91%;              /* #E2E8F0 (Subtle borders) */
  --input: 214 32% 91%;
  --ring: 221 83% 53%;                /* #2563EB */
  
  --radius: 0.5rem;                   /* 8px standard radius */
}
```

### B. Status Badges & Semantics
- **Critical / High Risk**: Rose / Red (`bg-red-50 text-red-700 border-red-200`)
- **Medium Risk / Pending**: Amber (`bg-amber-50 text-amber-700 border-amber-200`)
- **Low Risk / Approved**: Emerald (`bg-emerald-50 text-emerald-700 border-emerald-200`)
- **Analyzing / Active**: Blue / Indigo (`bg-blue-50 text-blue-700 border-blue-200`)
- **Neutral / Draft**: Slate (`bg-slate-100 text-slate-700 border-slate-200`)

### C. Standard Page Anatomy
Every dashboard page must follow this structured anatomy:
```tsx
<div className="p-8 lg:p-10 max-w-7xl mx-auto space-y-8">
  {/* 1. Page Header */}
  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
    <div>
      <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
        <span>Section</span> / <span>Subsection</span>
      </div>
      <h1 className="text-2xl font-bold tracking-tight text-foreground">Page Title</h1>
      <p className="text-sm text-muted-foreground mt-1">Clear, professional description of the legal utility.</p>
    </div>
    <div className="flex items-center gap-3">
      {/* Primary and secondary page actions using <Button> */}
    </div>
  </div>

  {/* 2. Main Content Body (Grid or Tables using Shadcn UI) */}
  <div className="space-y-6">
    {/* Cards, Tables, Tabs */}
  </div>
</div>
```

---

## 4. UI Component Library (`@/components/ui`)
All pages must use atomic primitives from `@/components/ui`:
- **`Button`**: Consistent heights, paddings, loading spinners, and variant colors.
- **`Card`**: Standardized border (`border-border`), background (`bg-card`), and padding.
- **`Badge`**: Uniform pill size and typographic style.
- **`Input` / `Textarea`**: Standardized focus ring (`focus:ring-2 focus:ring-ring focus:border-transparent`).
- **`Dialog`**: Unified backdrop blur and accessible focus trap for modals.
- **`Table`**: Structured headers, row hover states, and responsive overflow wrappers.
- **`Tabs`**: Clean pill or underline tab switches.

---

## 5. Routing Rules & Prohibitions
1. **Never use `tenant-files`**: The drafting and live redline studio lives under `/dashboard/drafting/editor/[id]`.
2. **Never use `my-contracts`**: Contracts to be analyzed live under `/dashboard/analysis`.
3. **Never use `templates` for drafting**: The contract blueprint and drafting studio lives under `/dashboard/drafting`.
4. **Never create dead links**: All sidebar and header links must navigate to active, working pages.
