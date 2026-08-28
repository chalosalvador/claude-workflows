# Slidev deck template

Copy this into `slides/<name>.md`, replace every `{{placeholder}}`, delete the slides
you don't need. Copy [`assets/style.css`](assets/style.css) next to it as `style.css` —
Slidev auto-loads that exact filename from the slides directory.

**Target ~7 slides.** Cover → at a glance → one slide per workstream that moved →
roadmap → close. A deck that lists everything is a deck nobody reads.

The class vocabulary (`.kicker`, `.card`, `.why`, `.progress`, `.status-col`, `.pill`,
`.metric`) is defined in the stylesheet. Change the five variables at the top of that
file to rebrand the whole deck; a documented block swaps it to light. Both themes were
rendered and their pill contrast measured against WCAG AA.

---

````markdown
---
theme: default
title: {{Team or project}} — {{Period}}
info: |
  ## {{Team or project}}
  {{PERIOD_LABEL}}
class: text-center
transition: slide-left
mdc: true
fonts:
  sans: Inter
  mono: JetBrains Mono
---

<!-- Replace the SVG with your own mark, or drop the lockup entirely. -->
<div class="brand-lockup">
  <div class="brand-badge">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
         stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 12h4l3 8 4-16 3 8h4"/>
    </svg>
  </div>
  <div class="brand-wordmark">{{Project}}<span>{{one-line descriptor}}</span></div>
</div>

<div class="kicker mt-8">{{Weekly update}}</div>

# {{The one-line story of the period}}

{{PERIOD_LABEL}}

<div class="lead mt-6">
{{One honest sentence: what the team accomplished, and why it matters to the reader.}}
</div>

---
layout: center
class: text-center
---

<div class="kicker">Progress at a glance</div>

# {{One-line theme across the workstreams}}

<!-- One card per workstream that MOVED. Three is the shape this grid is tuned for;
     for four, switch to grid-cols-2 rather than cramming four across.
     Do NOT show a card for a workstream that did not move. -->
<div class="grid grid-cols-3 gap-5 mt-10 text-left">

<div class="card">
<div class="text-3xl mb-2">{{emoji}}</div>
<div class="card-title">{{Workstream}}</div>
{{one line, plain language}}
<div class="progress">
<div class="bar"><span class="fill-done" style="width:{{PCT}}%"></span></div>
<div class="bar-label"><b>{{X of Y}}</b> {{unit — e.g. screens wired}}</div>
</div>
</div>

<div class="card">
<div class="text-3xl mb-2">{{emoji}}</div>
<div class="card-title">{{Workstream}}</div>
{{one line}}
<div class="progress">
<div class="bar"><span class="fill-flight" style="width:{{PCT}}%"></span></div>
<div class="bar-label"><b>{{X of Y}}</b> {{unit}}</div>
</div>
</div>

<div class="card">
<div class="text-3xl mb-2">{{emoji}}</div>
<div class="card-title">{{Workstream}}</div>
{{one line}}
<div class="progress">
<div class="bar"><span class="fill-done" style="width:{{PCT}}%"></span></div>
<div class="bar-label"><b>{{X of Y}}</b> {{unit}}</div>
</div>
</div>

</div>

<div class="footnote mt-8">{{The one goal for the period, in a sentence.}}</div>

<!-- ===== Repeat the slide below once per workstream that moved. ===== -->

---

<div class="kicker">{{Workstream}}</div>

# {{Plain-language headline — an outcome, not a commit subject}}

<div class="grid grid-cols-2 gap-8 mt-6">

<div>

### Shipped
{{One framing sentence.}}

- {{outcome bullet}}
- {{outcome bullet}}
- {{outcome bullet}}

</div>

<div class="why">

### Where we are
{{Honest status. "Built", "wired" and "deployable" are not "live" — say which.
Name what is next.}}

<div class="progress">
<div class="bar"><span class="fill-flight" style="width:{{PCT}}%"></span></div>
<div class="bar-label"><b>{{X of Y}}</b> {{unit}} · next: {{the next piece}}</div>
</div>

</div>

</div>

---
layout: center
class: text-center
---

<div class="kicker">Roadmap</div>

# Where things stand

<div class="grid grid-cols-3 gap-6 mt-8 text-left text-sm">

<div class="status-col">
<div class="pill pill-done">✅ Shipped</div>

- {{item}}
- {{item}}

</div>

<div class="status-col">
<div class="pill pill-flight">🔨 In progress</div>

- {{item}}
- {{item}}

</div>

<div class="status-col">
<div class="pill pill-next">◻ Next</div>

- {{item}}
- {{item}}

</div>

</div>

<div class="footnote mt-8">Status as of {{DATE}} · based on work merged in this period.</div>

---
layout: center
class: text-center
---

# {{Closing line — the state in one sentence}}

<div class="lead mt-4">
Next: {{the honest next steps}}.
</div>

<div class="footnote mt-10">{{Project}} · {{PERIOD_LABEL}}</div>
````

---

## Optional: a metric row

Drop into any slide where a number is the story. Keep it to three.

````markdown
<div class="grid grid-cols-3 gap-6 mt-8 text-center">
  <div><div class="metric">{{N}}</div><div class="metric-label">{{what it counts}}</div></div>
  <div><div class="metric">{{N}}</div><div class="metric-label">{{what it counts}}</div></div>
  <div><div class="metric">{{N}}</div><div class="metric-label">{{what it counts}}</div></div>
</div>
````

---

## 🚨 Do not add a static architecture slide

It is the most requested addition and the one that reliably goes wrong. An architecture
diagram carried forward week after week as a "mostly-static reference" **drifts from the
real system while looking authoritative** — and a stale diagram in front of a
stakeholder is worse than no diagram, because they act on it.

If someone asks for one, re-derive every box from the infrastructure code *that run*,
never from last week's deck, and **name which environment it depicts**.

## Preview and export

```bash
npx @slidev/cli slides/<name>.md --open
```

⚠️ The package is **`@slidev/cli`**, not `slidev`.

🚨 **The theme is a separate package and `npx` cannot prompt for it.** In a bare
directory the first run dies with `The theme "@slidev/theme-default" was not found and
cannot prompt for installation` — measured. Install it once alongside the CLI:

```bash
npm i -D @slidev/cli @slidev/theme-default vue
```

Then run `npx @slidev/cli …` and it resolves locally. Export to PDF:

```bash
npx @slidev/cli export slides/<name>.md
```

Export needs a browser engine once: `npx playwright install chromium`.
