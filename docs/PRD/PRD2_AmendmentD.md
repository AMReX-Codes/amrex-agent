This is a sophisticated architectural insight that moves the agent from "imitating examples" (which might be incomplete) to "understanding the solver's definition."

You are describing a transition from a **Retrieval-Based** approach (looking at what other users did in `inputs` files) to a **Schema-Based** approach (looking at what the C++ code actually allows via `ParmParse` and `GNUmakefile`).

This would effectively create a "Digital Twin" of the solver's input logic, enabling the Uncertainty Quantification (UQ) targeting you mentioned.

Here is a proposed **Amendment D** to the PRD to formalize this capability, distinguishing it from the simple file scraping currently in the plan.

---

### **AMENDMENT D: The Parameter Schema & UQ Index**
**Document Version:** 2.4
**Reason:** To solve the "truncated index" problem and enable high-fidelity validation and future UQ sweeps.

#### **D.1 New Index Type: `parameter_schema` (Level 3)**
**Current State:** The `input_templates` index scans text files and truncates at line 200. It misses parameters that only appear in complex cases or deep within the file.
**New Requirement:** Create a **Static Analysis Scraper** that scans the solver's C++ `Source/` directory, not just the `Exec/` case directories.

**Implementation Strategy:**
1.  **ParmParse Scraper:** The build script will scan `.cpp` files for AMReX `ParmParse` patterns:
    *   `pp.get("param_name", val)` $\rightarrow$ **Mandatory Parameter**
    *   `pp.query("param_name", val)` $\rightarrow$ **Optional Parameter** (with default `val`)
    *   `pp.queryarr("name", val)` $\rightarrow$ **Array Parameter**
2.  **GNUMakefile Scraper:** Parse `Make.package` and `GNUmakefile` to find logic gates:
    *   *Example:* `If definition="USE_EB" is TRUE, enable namespace "eb.*"`
3.  **Output Structure (JSON):**
    ```json
    {
      "parameter": "pelec.cfl",
      "type": "float",
      "source_file": "PeleC_advance.cpp",
      "impact_tier": "CRITICAL",
      "dependency": null,
      "description": "Courant number for time step control"
    },
    {
      "parameter": "eb.embedded_boundary_type",
      "type": "string",
      "source_file": "EB_init.cpp",
      "impact_tier": "HIGH",
      "dependency": "USE_EB=TRUE",
      "description": "Defines geometry generation method"
    }
    ```

#### **D.2 Hierarchy of Importance (The UQ Target)**
To address your request for an "importance hierarchy," the index will tag parameters with an **Impact Tier** based on heuristics derived from the `knowledge_base` reports:

*   **Tier 1: Physics Definition (Critical)**
    *   *Examples:* `geometry.is_periodic`, `pelec.chem_file`, `pelec.do_react`.
    *   *Impact:* Changing these changes the fundamental physical problem.
    *   *UQ Relevance:* Discrete choices (Scenario selection).

*   **Tier 2: Numerical Stability (High)**
    *   *Examples:* `pelec.cfl`, `amr.n_cell`, `algo.small_dens`.
    *   *Impact:* Controls accuracy and crashing.
    *   *UQ Relevance:* **Primary target for UQ.** (e.g., "Does the solution change if CFL 0.9 $\rightarrow$ 0.1?")

*   **Tier 3: Implementation Details (Medium)**
    *   *Examples:* `amr.blocking_factor`, `amr.max_grid_size`.
    *   *Impact:* optimization and memory layout, rarely physics.
    *   *UQ Relevance:* Low priority.

*   **Tier 4: I/O & Verbosity (Low)**
    *   *Examples:* `amr.plot_int`, `amr.v`, `pelec.sum_interval`.
    *   *Impact:* User experience only.
    *   *UQ Relevance:* Exclude from UQ sweeps.

#### **D.3 Integration with Input Writer**
Instead of blind text patching, the **Input Writer Node** will use this schema for **Context-Aware Validation**:
1.  **Check 1 (Existence):** "User requested `pelec.turb_model`, but that string is not found in any `ParmParse` call in the `PeleC` source code. Did you mean `pelec.les_model`?"
2.  **Check 2 (Logic):** "User requested `eb.sphere_radius`, but the `GNUmakefile` option `USE_EB` is currently `FALSE`."
3.  **Check 3 (UQ Suggestion):** "You are running a Production run. Would you like to generate a UQ ensemble varying **Tier 2** parameters (CFL, tolerances) by $\pm 10\%$?"

### **Comparison to Foam-Agent**
*   **Foam-Agent:** Uses a "Command Documentation Index". This is effectively a RAG lookup of the PDF documentation (User Guide). It relies on the documentation being up-to-date.
*   **AMReXAgent (Proposed Amendment):** Uses **Source Code Truth**. Because AMReX codes are research software, documentation often lags behind code. By scraping `ParmParse` calls directly from the C++ files, the AMReXAgent will know about flags added by a developer yesterday, even if they haven't been documented yet.

### **Summary of Gap Closure**
This Amendment closes the gap between "finding an example inputs file" (which might be outdated or simplified) and "generating a rigorously correct inputs file" that utilizes the full capability of the executable. It transforms the `input_templates` index from a **static gallery** into a **dynamic schema**.