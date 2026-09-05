# Next implementation plan

This document is the handoff for the next PMM Engine development session. It
starts from commit `bd1af51`, where the analytical shape backend is the default,
the Whitney midpoint-fiber backend is selectable, and 22 tests pass.

## Outcomes for the next phase

1. Make the 2D capacity charts easier to interpret during design review.
2. Support one or more circular voids in routine sections.
3. Import irregular section geometry from DXF and prove the workflow with a
   concave Christmas-tree section containing small circular voids.
4. Display steel and concrete material relationships as plots without
   presenting the Whitney stress block as a physical nonlinear material law.

## Decisions already made

- Keep 2D PMM views as the standard workflow; 3D remains an on-demand view.
- Keep analytical shape integration as the production default for Whitney
  strength calculations. Fiber analysis remains available for convergence
  checks and becomes the required path for future nonlinear material laws.
- Use a robust geometry library behind the section interface for concave,
  holed, and multipart geometry. The current dependency-free clipper remains a
  fast path for simple convex polygons, not the arbitrary-DXF solution.
- Preserve DXF circles as circle primitives so routine circular openings can
  eventually use exact circular-segment area and centroid integration. Any
  tessellation must record its chord tolerance and approximation error.
- Upload DXF file bytes to the server. Do not send an engineer's local Windows
  file path because that path is not accessible or trustworthy on a network
  analysis server.
- Treat the Whitney block as an ACI design idealization. It may be plotted as a
  clearly labeled equivalent block diagram, but it must not be labeled as a
  nonlinear concrete stress-strain curve.

## Milestone 1 — chart readability

### Scope

- Add a compact legend for capacity, demand, capacity intersection, and axial
  limits.
- Show the selected demand ray and mark both the demand point and its radial
  intersection with the capacity contour.
- Color demand markers by utilization: green at `DCR <= 0.90`, amber from
  `0.90` through `1.00`, and red above `1.00`. Continue to print the numeric
  DCR so color is not the only signal.
- Add hover/tap details containing load name, Pu, Mx, My, capacity radius, DCR,
  status, and any equilibrium warning.
- Improve tick formatting, unit labels, whitespace, and label collision
  handling. Keep the centered axes and restrained visual style based on
  `PMMchart.png`.
- Add `Reset view` and optional `Show grid` controls. Do not make the grid the
  default if it reduces similarity to the reference chart.
- Keep demand-row selection synchronized with all 2D and 3D views.
- Add SVG and PNG export after the interactive chart behavior is stable.

### Acceptance tests

- Selecting each demand row moves the ray, intersection marker, annotation,
  and highlighted row to the same load case.
- A demand at DCR 0.90, 1.00, and greater than 1.00 receives the intended
  visual state and still has a readable text status.
- Pure Mx, pure My, biaxial, zero-moment, and out-of-range Pu cases render
  without JavaScript errors or non-finite coordinates.
- The chart remains legible at a 1366 x 768 office-laptop viewport and at the
  existing mobile breakpoint.

## Milestone 2 — circular voids

### Input and user interface

- Add a `Voids` section/table with `label`, `x`, `y`, and `diameter` fields in
  inches, plus add/remove controls.
- Draw voids in the section preview and report concrete area, void area, and
  centroid shift.
- Extend the JSON request with an optional collection such as:

  ```json
  {
    "section": {
      "voids": [
        {"type": "circle", "label": "V1", "x_in": 0, "y_in": 0, "diameter_in": 4}
      ]
    }
  }
  ```

  Existing schema-version-1 rectangular requests must remain valid.

### Engine work

- Introduce a geometry boundary abstraction that can represent solids, polygon
  holes, exact circles, and later multipolygons without coupling the mechanics
  layer to DXF.
- Subtract void area and first moments from section properties, Whitney
  compression resultants, bar-displacement checks, and the ACI axial limit.
- Exclude void cells from the fiber mesh.
- For the first release, reject voids that lie partly outside the solid,
  overlap another void, or contain a reinforcing-bar center. Return a precise
  validation message rather than repairing geometry silently.
- Report the integration route and geometric approximation tolerance in the
  printed calculation.

### Acceptance tests

- Centered circular void: exact area reduction, no centroid shift, and symmetric
  PM curves.
- Eccentric circular void: correct area and centroid from an independent hand
  calculation; asymmetric positive/negative capacity as expected.
- Two circular voids: correct combined area with no double subtraction.
- Shape-versus-refined-fiber comparison at several strain planes and PMM demand
  points.
- Invalid outside, overlapping, zero-diameter, and bar-in-void inputs fail with
  actionable errors.

## Milestone 3 — DXF irregular-section import

### Import contract

- Add an import endpoint that accepts raw DXF bytes, a filename, and an
  explicit units override. This is easier for both the browser and VBA than
  server-side path access.
- Use `ezdxf` for parsing and Shapely for loop validation, containment,
  polygonization, and repair diagnostics.
- Initially accept closed `LWPOLYLINE`/`POLYLINE`, stitched `LINE`/`ARC` loops,
  and `CIRCLE`. Tessellate splines only when an explicit chord tolerance is
  supplied.
- Establish preferred layers: `PMM_SECTION`, `PMM_VOID`, and `PMM_REBAR`.
  Also support nested-loop inference, but require preview confirmation when
  layer meaning is ambiguous.
- Read `$INSUNITS`; require the user to choose units when it is missing or
  unitless. Normalize coordinates to inches before creating the canonical
  section object.
- Reject open loops, self-intersections, duplicate boundaries, unsupported
  entities, and unreasonable scale with entity-specific warnings.
- Constrain uploads by file size, entity count, vertex count, parse time, and
  nesting depth before this is deployed to the office server.

### Christmas-tree fixture

Create `tests/fixtures/christmas_tree_with_voids.dxf` in inches with this
closed, symmetric, concave exterior polyline:

```text
(-2,0), (2,0), (2,2), (6,2), (3.5,5), (5,5), (2.5,8),
(4,8), (0,13), (-4,8), (-2.5,8), (-5,5), (-3.5,5),
(-6,2), (-2,2)
```

Add five `CIRCLE` voids, all on `PMM_VOID`:

| Label | Center (in) | Diameter (in) |
|---|---:|---:|
| V1 | (0, 10) | 0.750 |
| V2 | (-1.5, 7) | 0.500 |
| V3 | (1.5, 7) | 0.500 |
| V4 | (-2, 4) | 0.625 |
| V5 | (2, 4) | 0.625 |

The exterior shoelace area is `79.000 in²`; the exact combined circular-void
area is `1.448077864 in²`; the expected concrete area is
`77.551922136 in²`. Symmetry requires `centroid_x = 0` within tolerance.
Reinforcement will be supplied separately with the explicit-bar table so the
fixture isolates geometry import.

### Acceptance tests

- Import returns the expected exterior, five exact circle records, area, bounds,
  and x-centroid without modifying the DXF file.
- The preview visibly shows the concave tree outline and all five openings.
- The shape solver completes a 10-degree PMM sweep without geometry errors.
- A refined fiber run approaches the shape result within a documented
  tolerance at selected strain planes.
- A deliberately open tree outline and an out-of-bounds circle produce clear
  failures.
- The same uploaded file produces the same normalized geometry hash on Windows
  and macOS.

## Milestone 4 — stress-strain and design-model plots

### Material interface

- Define a common material protocol with model identifier, validated parameters,
  stress evaluation, characteristic strains, and a method that returns sampled
  plotting points.
- Preserve the current elastic-perfectly-plastic steel model and plot `fy`,
  `Es`, and yield strain on symmetric tension/compression axes.
- For Whitney, show a separate `ACI equivalent stress block` diagram with
  `0.85 f'c`, `beta1`, and `eps_cu`. Include the note: `Design idealization —
  not a constitutive stress-strain curve`.
- When the first nonlinear concrete model is implemented, show its actual
  stress-strain curve on the same materials panel with its confinement and
  ultimate-strain parameters.
- Allow markers for bar strains/stresses from a selected PMM capacity point as
  a later enhancement; do not block the initial material-chart release on it.

### Acceptance tests

- Steel plot reaches `+fy` and `-fy` at the correct yield strains and remains
  capped beyond yield.
- Changing `fc`, `fy`, or `Es` updates the relevant plot and annotations.
- Whitney is never labeled `nonlinear` or shown as measured material behavior.
- Plot samples contain only finite JSON values and render at narrow and wide
  viewports.

## Recommended implementation order and commits

1. `Improve PMM chart inspection and demand visualization`
2. `Add canonical holed-section geometry and circular voids`
3. `Add DXF import API and Christmas-tree geometry fixture`
4. `Add material model plotting interface and UI`
5. `Document validation results and update Excel request examples`

Chart work can proceed independently, but void support must establish the
canonical geometry model before the DXF adapter is written. The DXF parser
must output that model rather than creating a second analysis representation.

## Verification and performance gates

- Run the complete Python and JavaScript checks after each milestone.
- Add hand-calculated area/centroid cases before comparing PMM envelopes.
- Compare representative results with spColumn and at least one independent
  calculation; record input conventions and sign conversions.
- Record solver time separately from DXF parsing and chart rendering.
- Provisional target: a routine rectangle with up to ten circular voids, three
  demands, and a 5-degree shape-based sweep should complete in under two
  seconds on the reference workstation. Treat this as a benchmark to measure,
  not a guarantee to engineer around blindly.
- Never accept a geometry repair, coarse tessellation, or non-converged fiber
  equilibrium without returning a visible warning and diagnostic value.

## Start-of-session checklist

```bash
cd /Users/anandharammourougassamy/pmm-engine
git pull --ff-only
python3 -m pytest
PYTHONPATH=src python3 -m pmm_engine.webapp --port 3000
```

Then open `http://localhost:3000`, start with Milestone 1, and retain the
existing 20 x 30 in section as the regression baseline.
