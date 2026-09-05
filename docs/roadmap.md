# Development roadmap

## Milestone 1: mechanics kernel — complete

- Section, concrete region, and discrete bar data models
- Convex polygon clipping and section properties
- Equivalent rectangular concrete block
- Elastic-perfectly plastic steel
- Nominal force and biaxial moment resultants
- Axial-force equilibrium at a fixed neutral-axis angle
- Rectangular perimeter reinforcement layout
- Initial verification tests

## Milestone 2: dual integration backends — complete for rectangular baseline

- Common result object for analytical shape and concrete fiber integration
- Midpoint-grid fiber mesher
- Same-strain-plane convergence comparison
- PM curves, constant-Pu contours, and DCRs selectable through the web/API — complete
- Add boundary-aware or triangulated mesh for arbitrary concave geometry
- Add mesh diagnostics and automatic convergence study
- Export comparison records to CSV and Excel

The same-strain-plane comparison is the baseline. Both backends use the same
equivalent rectangular concrete block and the same bar model, so differences
measure spatial discretization only.

## Milestone 3: initial nominal/factored PMM analysis — in progress

- Generate uniaxial interaction curves from controlled strain states — complete
- Generate sampled constant-Pu `Mx-My` contours — complete
- Compute radial demand/capacity ratios — complete
- Add adaptive angular refinement and solve orientation continuously
- Generate adaptive `P-Mx-My` surfaces
- Detect disconnected or non-convex `Mx-My` contours
- Interpolate surface data with documented error bounds
- Batch-check load combinations

## Milestone 4: design-code layer — initial ACI 318-19 layer complete

- ACI 318-19 strength-reduction factors — complete
- Maximum axial compression cap — complete
- Tied and spiral confinement classifications — complete
- Tension-, transition-, and compression-controlled states — complete
- High-strength reinforcement provisions
- Nominal and factored result surfaces
- Code references attached to each transformation

ACI 318-25 should be implemented as a separate module rather than overwriting
the ACI 318-19 behavior.

## Milestone 5: Excel workflow — bridge implemented, workbook pending

- Versioned JSON project schema — complete
- Workbook tables for materials, regions, vertices, bars, and loads
- xlwings/VBA Analyze macro — source module complete
- Section preview and reinforcement plot
- P-M curves, Mx-My slices, and load-point tables
- 2D-first capacity workspace with a toggleable 3D onion viewer — complete
- Advanced analysis settings for integration method and angular sampling — complete
- Step-by-step calculation sheet and print-preview button — source complete
- Engine version, input hash, warnings, and convergence details in every run
- Cross-platform button workflow before optional Windows UDFs

## Milestone 6: nonlinear fiber analysis

- General concrete and steel stress-strain protocols
- Parabolic concrete compression response
- Steel strain hardening
- Curvature-controlled and axial-force-controlled response
- Moment-curvature analysis
- Service-level stress and strain results
- Mesh refinement and convergence reporting

This backend should not be described as more accurate merely because it uses
fibers. Accuracy depends on the constitutive law, mesh, convergence criteria,
and whether the requested result is code strength or physical response.

## Verification gates

No milestone should be treated as production-ready until it passes:

1. Hand-calculated control points for regular sections.
2. Translation, rotation, reflection, and unit invariance.
3. Analytical shape versus refined fiber comparisons.
4. Published design examples.
5. Cross-program checks against at least two established section tools.
6. Regression tests for every fixed defect.
