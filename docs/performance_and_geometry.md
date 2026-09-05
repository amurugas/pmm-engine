# Performance and arbitrary-geometry strategy

Speed and geometry freedom are product requirements. The target is not merely
feature parity with spColumn; routine sections should use specialized exact
integrals while imported geometry passes through a general compiled kernel.

## Canonical geometry model

Represent the section as typed primitives and constructive regions:

- rectangles and general polygons for solids;
- exact circles for solid regions and voids;
- nested polygons/circles for holes and multiple solids;
- discrete bar objects plus rectangular, circular, and multi-layer generators;
- a normalized coordinate system, units, tolerances, and material-region IDs.

Do not convert every circle into fibers or a coarse polygon. A circular segment
intersected by a compression half-plane has exact area and centroid formulas;
using those formulas preserves both speed and accuracy for the common circular
void case.

## Fast Whitney-block kernel

1. Use analytical shape integration as the default. A constant Whitney stress
   block needs area and first moments, not thousands of concrete fibers.
2. Precompile each section. For every angular direction, cache vertex
   projections and geometry events instead of rebuilding topology at every
   neutral-axis depth.
3. Evaluate all reinforcing bars with contiguous numeric arrays. Bar strains,
   stresses, forces, and moments are naturally vectorized.
4. Detect symmetry and calculate only the unique quadrant or half-surface, then
   mirror results with explicit verification checks.
5. Use continuation: the solution at the prior angle/Pu is the initial bracket
   or estimate for the next point.
6. Compute demand points first. Solve the two equilibrium/direction equations
   near each demand ray, and build dense contours only for plots.
7. Refine angles adaptively where curvature, phi, topology, or DCR error changes
   rapidly. A fixed 10-degree visualization mesh should not control final DCR.
8. Keep geometry preprocessing libraries out of the hot loop. Shapely/GEOS can
   validate and normalize imported topology; the repeated capacity kernel
   should operate on compiled numeric primitives.

If profiling later shows Python overhead dominates, move only the compiled
section evaluator to a Rust/PyO3 or C++ extension with Windows wheels. Preserve
the Python API and verification suite. A rewrite should follow measurements,
not precede them.

## Fiber backend

The fiber engine remains optional for nonlinear concrete, confinement models,
moment-curvature, and verification. Use boundary-conforming triangular cells,
adaptive refinement, and vectorized material evaluation. Never make a uniform
fiber mesh the mandatory path for Whitney PMM capacity.

## DXF import pipeline

DXF is an input adapter, not the internal model:

1. Read `$INSUNITS`; require an explicit user decision for unitless drawings.
2. Map configurable layers to solids, openings, bars, and material regions.
3. Support closed `LWPOLYLINE`, `POLYLINE`, and `CIRCLE` first.
4. Add `LINE`, `ARC`, `ELLIPSE`, and `SPLINE` by building an endpoint graph and
   joining edges into closed loops within a visible snap tolerance.
5. Preserve circles and arcs as analytical primitives where possible. Flatten
   splines only to a user-visible chord/area tolerance.
6. Detect open loops, gaps, duplicate/overlapping edges, self-intersections,
   nonplanar entities, ambiguous nesting, and bars outside concrete.
7. Show a preview with repaired endpoints highlighted. Never silently heal a
   gap beyond tolerance.
8. Classify nested loops by containment and winding into solids and voids, then
   emit versioned canonical JSON plus an import report.

The DXF parser should run in a constrained worker with file-size, entity-count,
time, and memory limits. The server must accept uploaded bytes or normalized
geometry, never an arbitrary server-side file path supplied by Excel.

## Performance acceptance tests

Establish benchmarks before adding features:

- first run and cached run for a rectangular section;
- rectangle with one and multiple circular voids;
- 100, 1,000, and 10,000 bars;
- irregular DXF with increasing vertex/entity counts;
- 1, 10, 50, and 150 simultaneous users;
- 2-, 5-, and 10-degree contours plus adaptive DCR refinement;
- numerical agreement between specialized, general-shape, and refined-fiber
  paths at published control points.

Track p50, p95, and p99 server time separately for geometry compilation,
capacity generation, demand checking, serialization, and Excel write-back.
