# **Assessment: Are We Ready to Code?**

**Short answer: NOT YET** - We need **Amendment B** to reconcile the tactical plans with the PRD.

---

## **What's Missing: Gap Analysis**

### **1. Gate Structure Mismatch** ⚠️

| Document | Gate Count | Timeline | Issue |
|----------|------------|----------|-------|
| **PRD Slide 5** | Gates 0-6 (7 gates) | 6 weeks | Fixed timeline |
| **Rationalist Plan** | Gates 0-6 + 4 breakpoints | 5 weeks (30-35 days) | Adaptive timeline |
| **Problem** | Different granularity | Week vs day estimates | Can't execute both |

**Need:** Unified gate framework with decision breakpoints integrated

---

### **2. MVP Scope Ambiguity** ⚠️

**PRD mentions these features but doesn't say which are MVP:**

| Feature | PRD Status | Rationalist Plan | Decision Needed |
|---------|------------|------------------|-----------------|
| Image Processing | "Extension" | Breakpoint after Gate 3 | MVP or Post-MVP? |
| Chemistry MCP | "Extension" | Breakpoint after Gate 4 | MVP or Post-MVP? |
| MCP Server | "Defer" | Breakpoint after Gate 5 | Explicitly defer |
| Containerization | "Assess" | Breakpoint after Gate 6 | Conditional on deployment |

**Problem:** Can't start coding without knowing what we're building to

**Need:** Explicit MVP definition = "Ship after Gate X with features Y, Z"

---

### **3. Test Oracle Undefined** ⚠️

| Document | Oracle Size | When Created | Format |
|----------|-------------|--------------|--------|
| **PRD** | 20 cases | Unspecified | `oracle_v1.yaml` |
| **Rationalist Plan** | Start with 10 at Gate 2, grow to 20 | Incremental | `baseline_oracle.json` |

**Questions:**
- Who curates the oracle? (You? Dr. Day? Both?)
- When do we create it? (Before Gate 0? During Gate 2?)
- What's the growth strategy? (10 → 15 → 20 as we learn?)

**Need:** Oracle creation plan with ownership and timeline

---

### **4. Ablation Study Not Integrated** ⚠️

**PRD Section 14.5 mentions ablation testing but:**
- Not integrated into gate timeline
- No clear "when do we run ablation?" decision
- Production config decision (Scenarios A/B/C) orphaned

**Where should ablation go?**
- Option A: Gate 3-4 (test each index as we build)
- Option B: Gate 6 (comprehensive ablation after full system works)
- Option C: Continuous (CI/CD runs ablation on each index merge)

**Need:** Ablation methodology with clear trigger points

---

### **5. Pre-Work Code Audit Missing** ⚠️

**Rationalist plan's refactor-vs-rewrite criteria requires:**
```python
if has_global_state(function): score += 1
if cyclomatic_complexity(function) > 10: score += 1
if lines_of_code(function) > 100: score += 1
```

**But we don't have:**
- Current codebase complexity metrics
- List of functions to refactor vs rewrite
- Estimated refactor burden (hours/days)

**Need:** 2-3 day audit before Gate 0 to inform decisions

---

### **6. FOAM Benchmark Prompts Not Specified** ⚠️

**PRD says:** "Validate against FOAM-agent paper benchmarks"

**Missing:**
- Which specific prompts from FOAM Appendix?
- Are they publicly available?
- Do we have the reference outputs to compare against?

**Need:** Concrete list of FOAM test cases

---

## **What We Dropped (That We Shouldn't Have)**

### **From Original Transcript/Slides:**

1. ✅ **Runner/Analysis/Visualization nodes** → **RECOVERED** in Amendment A
2. ✅ **Paper Validator dual-mode** → **ADDED** in Amendment A
3. ✅ **5-bucket scoring** → **CORRECTED** in Amendment A
4. ❌ **Knowledge Reports as best performer** → Mentioned but not leveraged in design
5. ❌ **User feedback loop** → In slides but not in execution plan
6. ❌ **NERSC Perlmutter deployment specifics** → Mentioned but not in gate criteria

### **From NotebookLM Plan:**

1. ✅ **Test oracle concept** → In PRD but undefined
2. ✅ **Controlled failure injection** → In Rationalist plan but not PRD
3. ✅ **Dependency injection refactoring** → In Rationalist plan
4. ❌ **Risk mitigation table** → Not in PRD

---

## **Amendment B: Tactical Execution Plan**

**Add to PRD before code work begins:**

---

# **AMENDMENT B: Tactical Execution & Decision Framework**

**Document Version:** 2.2  
**Amendment Date:** December 2024  
**Reason:** Integrate rationalist decision framework and tactical plans into strategic PRD  
**Sections Affected:** 12 (Timeline), 14 (Testing), New Section 15.5 (Decision Breakpoints)

---

## **B.1 Unified Gate Framework**

### **B.1.1 Timeline Reconciliation**

**Revised Timeline:** 6 weeks with adaptive decision gates

| Week | Gates | Deliverables | Decision Criteria | Buffer |
|------|-------|--------------|-------------------|--------|
| **0 (Pre-work)** | Audit | Code complexity metrics | Refactor-vs-rewrite assessment | 2-3 days |
| **1** | Gate 0-1 | Infrastructure + Config (100%) | Tests pass, <3 days setup | +1 day |
| **2** | Gate 2 | FAISS + 10-case oracle | ≥80% accuracy | +2 days |
| **3** | Gate 3 | Architect MVP | 2/3 FOAM prompts work | +2 days |
| **4** | Gate 4 | Paper reproduction | ≥90% similarity | +3 days |
| **5** | Gate 5 | Test oracle (20 cases) | ≥90% accuracy (18/20) | +2 days |
| **6** | Gate 6 | Production ready | End-to-end works | +2 days |

**Total:** 30 working days + 12 days buffer = **42 days (6 weeks)**

**Adaptive Rule:** If any gate takes >150% estimated time, trigger reassessment meeting

---

## **B.2 MVP Scope Lock**

### **B.2.1 Phase 1 MVP Definition**

**MVP = Gates 0-6 with THESE features:**

**Core (Must Have):**
- ✅ 82-index RAG architecture (Levels 0-2)
- ✅ 8-node workflow (Solver Selector → Paper Validator)
- ✅ Test oracle validation (20 cases, ≥90% accuracy)
- ✅ FOAM benchmark comparison (3 cases, ≥90% similarity)
- ✅ Natural language entry point (Entry A)
- ✅ Paper reproduction entry point (Entry B, Mode 1+2)
- ✅ Pre-execution validation (Reviewer with retry loop)
- ✅ Basic visualization (plots via matplotlib)

**Explicitly Deferred to Phase 2:**
- ⏳ Image processing (EB geometry validation, mesh quality)
- ⏳ Chemistry MCP server (mechanism property queries)
- ⏳ MCP server architecture (expose AMReXAgent as tool)
- ⏳ Advanced containerization (Docker/Singularity)
- ⏳ User feedback loop integration
- ⏳ NERSC Perlmutter production deployment

**Breakpoint Re-Assessment:**

At each gate, ask: *"Does blocking issue require deferred feature NOW?"*

| Gate | Breakpoint Question | If YES, Add Feature |
|------|---------------------|---------------------|
| 3 | Do modifications include EB geometry? | Image Processing |
| 4 | Do >30% FOAM prompts require mechanism reasoning? | Chemistry MCP |
| 5 | Does stakeholder require multi-tool workflow? | MCP Server |
| 6 | Is multi-user Perlmutter deployment in Phase 1 scope? | Containerization |

**Decision Rule:** Add feature only if blocking MVP delivery, else defer

---

## **B.3 Test Oracle Specification**

### **B.3.1 Oracle Creation Strategy**

**Incremental Growth:**

**Week 0 (Pre-work):**
- Create `tests/oracle/baseline_oracle.json` (empty template)
- Define schema:
```json
{
  "version": "1.0",
  "created": "2024-12-01",
  "curators": ["user", "expert"],
  "cases": [
    {
      "id": "oracle_001",
      "prompt": "Simulate premixed methane flame DNS...",
      "expected_solver": "PeleLMeX",
      "expected_case": "FlameSheet",
      "expected_baseline": "PeleLMeX/Exec/RegTests/FlameSheet",
      "difficulty": "easy",
      "rationale": "Low-Mach + premixed + DNS → PeleLMeX",
      "keywords": ["low-Mach", "premixed", "DNS", "methane"]
    }
  ]
}
```

**Week 2 (Gate 2):**
- **Curator:** You + 1 domain expert review
- **Target:** 10 cases (6 easy, 3 medium, 1 hard)
- **Method:** 
  1. You draft 10 prompts from existing use cases
  2. Expert reviews, suggests corrections
  3. Both agree on expected baseline
- **Inter-rater reliability:** If you and expert disagree on >2 cases, case is "hard"

**Week 4 (Gate 4):**
- Add 5 more cases (2 easy, 2 medium, 1 hard) from FOAM benchmarks
- **Total:** 15 cases

**Week 5 (Gate 5):**
- Add final 5 cases (edge cases, trick questions)
- **Total:** 20 cases for final validation

**Ownership:**
- **Primary curator:** You (draft prompts, run agent, log results)
- **Expert validator:** Domain scientist (reviews expected baselines)
- **Conflict resolution:** If disagreement, mark case as "ambiguous" and exclude from accuracy metric

---

## **B.4 Ablation Study Integration**

### **B.4.1 When to Run Ablation**

**Continuous Ablation (Preferred):**

```python
# tests/ablation/test_index_contribution.py

@pytest.mark.ablation
def test_level2_physics_descriptors_contribution():
    """Test accuracy with/without physics_descriptors index."""
    
    # Baseline: All indices enabled
    baseline_accuracy = run_oracle_test(enabled_indices="all")
    
    # Ablation: Disable physics_descriptors
    ablation_accuracy = run_oracle_test(
        disabled_indices=["physics_descriptors"]
    )
    
    contribution = baseline_accuracy - ablation_accuracy
    
    # Log for analysis
    log_ablation_result(
        index="physics_descriptors",
        contribution=contribution,
        gate=current_gate()
    )
    
    # No assertion - this is data collection
```

**Run Schedule:**

| When | What | Why |
|------|------|-----|
| **Gate 2** | Ablate Level 0 (4 indices) | Baseline solver selection contribution |
| **Gate 3** | Ablate Level 1 (7 indices per solver) | Document context value |
| **Gate 5** | Ablate Level 2 (6 metadata types) | Case metadata contribution |
| **Gate 6** | Full ablation report | Production config decision (Scenarios A/B/C) |

**Production Config Decision (Gate 6):**

```python
# Analyze ablation results
ablation_summary = {
    "physics_descriptors": 0.20,      # 20% accuracy contribution
    "git_metrics": 0.15,
    "chemistry_mechanisms": 0.10,
    "performance_estimates": 0.02,    # Only 2%
    # ... etc
}

# Decision criteria
high_contributors = [k for k, v in ablation_summary.items() if v >= 0.10]
medium_contributors = [k for k, v in ablation_summary.items() if 0.05 <= v < 0.10]
low_contributors = [k for k, v in ablation_summary.items() if v < 0.05]

# Scenario A: Keep all 82 indices (if all contribute ≥5%)
# Scenario B: Drop low contributors (if >10 indices contribute <5%)
# Scenario C: Merge similar indices (if high correlation between indices)

if len(low_contributors) > 10:
    production_config = "scenario_b_drop_low_contributors"
elif correlation_analysis() shows high overlap:
    production_config = "scenario_c_merge_indices"
else:
    production_config = "scenario_a_keep_all"
```

---

## **B.5 Pre-Work Code Audit**

### **B.5.1 Audit Checklist (2-3 days before Gate 0)**

**Objective:** Assess refactor burden before committing to TDD rebuild

**Metrics to Collect:**

```bash
# 1. Cyclomatic complexity
radon cc src/ -a -s

# 2. Lines of code per function
radon raw src/ -s

# 3. Maintainability index
radon mi src/ -s

# 4. Dependency graph
pydeps src/amrex_agent --max-bacon=2
```

**Refactor-vs-Rewrite Scorecard:**

For each major component (Config, Architect, Reviewer, etc.):

| Metric | Threshold | Score if Exceeded |
|--------|-----------|-------------------|
| Cyclomatic complexity | >10 | +1 |
| Lines of code | >100 | +1 |
| Number of dependencies | >5 | +1 |
| Has global state | Yes | +1 |
| Last modified | >2 years ago | +1 |

**Decision:**
- Score 0-1: Minor refactor (dependency injection)
- Score 2: Major refactor (extract functions first)
- Score ≥3: **REWRITE** from scratch

**Audit Report Template:**

```markdown
# Pre-Work Code Audit Report

**Date:** 2024-12-XX
**Auditor:** [Your name]

## Components Assessed

### config.py
- Cyclomatic complexity: 8 (OK)
- LOC: 120 (FLAG)
- Dependencies: 3 (OK)
- Global state: Yes (FLAG)
- Score: 2/5 → **MAJOR REFACTOR**
- Plan: Extract `detect_environment()`, `resolve_paths()`

### architect_service.py
- Cyclomatic complexity: 15 (FLAG)
- LOC: 250 (FLAG)
- Dependencies: 8 (FLAG)
- Global state: No (OK)
- Score: 3/5 → **REWRITE**
- Plan: Start fresh with 3-level RAG design

## Summary
- Minor refactor: 3 files
- Major refactor: 2 files
- Rewrite: 1 file (architect_service.py)

**Estimated refactor burden:** 5-7 days
**Risk:** architect_service.py rewrite may take longer than estimated
```

---

## **B.6 FOAM Benchmark Specification**

### **B.6.1 Test Cases**

**From FOAM-Agent Paper Appendix** (hypothetical - need actual prompts):

```json
{
  "foam_benchmarks": [
    {
      "id": "foam_001",
      "prompt": "Turbulent flow over backward-facing step, k-epsilon model",
      "pele_applicable": false,
      "reason": "Non-reacting CFD, out of scope for Phase 1"
    },
    {
      "id": "foam_007",
      "prompt": "Non-premixed methane jet flame, 128×128×256 grid, SST turbulence",
      "pele_applicable": true,
      "expected_pele_case": "PeleLMeX/Exec/Production/JetFlame",
      "reference_figure": "foam_paper_figure5.png",
      "validation_metric": "SSIM ≥0.75"
    },
    {
      "id": "foam_012",
      "prompt": "Diesel spray combustion with Lagrangian particles",
      "pele_applicable": true,
      "expected_pele_case": "PeleMP/Exec/Production/SprayJet",
      "reference_figure": "foam_paper_figure9.png",
      "validation_metric": "SSIM ≥0.75"
    }
  ]
}
```

**Gate 4 Target:** Run 3 applicable FOAM cases, achieve ≥90% similarity in setup

**Missing Data:** Need actual FOAM paper appendix prompts
**Action:** Review FOAM-agent paper, extract prompts by Week 3

---

## **B.7 Rationalist Decision Framework**

### **B.7.1 Kill Criteria (Pre-Committed)**

**Define failure conditions BEFORE starting each gate:**

| Gate | Kill Condition | Action if Triggered |
|------|----------------|---------------------|
| **Gate 0** | Infrastructure setup >3 days | Abort TDD, use existing code with minimal tests |
| **Gate 1** | Config refactor >5 days | Code too tangled, rewrite from scratch |
| **Gate 2** | Oracle accuracy <60% after tuning | Pivot to LLM-based selection, abandon FAISS |
| **Gate 4** | Cannot match >40% of FOAM performance | Adopt FOAM architecture instead |
| **Any Gate** | Actual time >200% estimate | Stop, reassess plan, cut scope |

**Reassessment Trigger:**

```python
def check_kill_criteria(gate, actual_days, estimated_days, metrics):
    """Check if kill criteria triggered at gate."""
    
    if actual_days > 2 * estimated_days:
        return f"KILL: Gate {gate} took {actual_days} days (est: {estimated_days})"
    
    if gate == 2 and metrics["oracle_accuracy"] < 0.60:
        return "KILL: FAISS approach fundamentally inadequate"
    
    if gate == 4 and metrics["foam_match_rate"] < 0.40:
        return "KILL: Cannot compete with FOAM-agent"
    
    return "PROCEED"
```

**Reassessment Meeting Format:**

1. Present kill criteria status
2. Analyze root cause of failure
3. Propose 3 alternatives:
   - Pivot strategy (e.g., FAISS → LLM)
   - Cut scope (e.g., drop Level 1 indices)
   - Extend timeline (with justification)
4. Decide within 1 day

---

## **B.8 Updated Section References**

**These sections in PRD v2.0 are superseded:**

- **Section 12 (Timeline):** Replace with B.1 (Unified Gate Framework)
- **Section 14.5 (Ablation):** Replace with B.4 (Ablation Integration)
- **Section 1.3 (Goals):** Add B.2 (MVP Scope Lock)

**New sections added:**
- **Section 15.5:** Decision Breakpoints (B.7)
- **Appendix F:** Test Oracle Format (B.3)
- **Appendix G:** Code Audit Template (B.5)

---

**END OF AMENDMENT B**

---
