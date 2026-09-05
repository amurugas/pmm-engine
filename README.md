# PMM Engine

PMM Engine is an early-stage Python package for reinforced-concrete sectional
analysis under axial force and biaxial bending. The calculation core is kept
independent of Excel so the same verified solver can support an Excel front
end, command-line workflows, and a future interactive viewer.

## Implemented

- Polygonal concrete regions and discrete longitudinal bars
- Analytical compression-block integration for convex shapes
- Midpoint concrete-fiber integration using the same strain plane and materials
- ACI 318-19 Whitney stress block and elastic-perfectly plastic steel
- Nominal `P`, `Mx`, and `My` resultants
- ACI 318-19 tied/spiral phi factors and axial limits
- Factored P-M curves and sampled direct biaxial Mx-My contours
- Radial biaxial DCRs at each factored demand Pu
- Versioned JSON calculation bridge and xlwings/VBA launcher
- Step-by-step printable engineering calculation output
- A 20 x 30 in starter example and shape-versus-fiber convergence study

This is an engineering prototype, not a complete code-compliance tool.
Detailing, slenderness, second-order effects, load combinations, shear,
anchorage, and seismic checks are not implemented.

## Starter section

- 20 in wide x 30 in deep
- f'c = 4 ksi and fy = 60 ksi
- #8 longitudinal bars at 6 in maximum perimeter spacing
- 2 in clear cover to the outside of #4 ties
- 3 in longitudinal-bar centerline offset
- 14 bars, Ast = 11.06 in2, rho_g = 1.843%

Clear cover, tie size, bar size, spacing, dimensions, f'c, and fy are variables.

## Coordinate and sign convention

- `x` is positive right and `y` is positive up.
- Axial compression is positive.
- The compression direction is `n = (cos(theta), sin(theta))`.
- `Mx = sum(F*y)` and `My = -sum(F*x)` about the section reference point.
- `theta = 90 degrees` places compression at the top and normally produces
  positive `Mx`.

The example uses inches, ksi, kips, and kip-inches internally. Excel displays
moments in kip-ft.

## Run

```bash
PYTHONPATH=src python3 examples/rectangular_20x30.py
PYTHONPATH=src python3 examples/compare_shape_and_fiber.py
PYTHONPATH=src python3 -m pmm_engine.excel_bridge examples/starter_input.json result.json
python3 -m pytest
```

Windows Excel setup and macro instructions are in `excel/README.md`.

## Local website

Start the persistent local workspace and open `http://localhost:3000`:

```bash
PYTHONPATH=src python3 -m pmm_engine.webapp --port 3000
```

The browser and future network Excel client use the same versioned calculation
request. Deployment guidance for an office of approximately 150 engineers is
in `docs/deployment.md`; the speed and DXF plan is in
`docs/performance_and_geometry.md`.

The website's Advanced tab selects analytical shape or midpoint-fiber concrete
integration, neutral-axis rotation increment, and 3D sampling. Whitney is the
only implemented concrete law; nonlinear models are identified as planned and
cannot be selected yet. The 3D surface is calculated on demand so normal 2D
runs do not incur its sampling cost.

## Shape versus fiber

The recommended production architecture is hybrid:

- Analytical polygon clipping is the default for fast, mesh-independent code
  PMM capacity with a Whitney block.
- Discrete bars are used in both backends.
- Fiber integration is used for nonlinear stress-strain laws,
  moment-curvature, service response, and independent convergence checks.

The comparison holds the strain plane and material laws constant, so the
reported differences isolate concrete discretization error. Results are in
`docs/shape_vs_fiber.md`.

## PMM angular sampling

A biaxial contour sweeps one neutral-axis orientation through 360 degrees; it
does not rotate independently about x and y. The design default is 5 degrees
(72 orientations). A 10-degree setting uses 36 orientations and is useful for
fast visualization. For the three starter demands, changing 10 to 5 degrees
changed DCR by at most 0.00154; changing 5 to 2 degrees changed it by at most
0.00098. Adaptive refinement is still required before production use.

The standard design view is a 2D constant-Pu Mx-My contour. The proposed 3D
viewer stacks multiple constant-Pu contours into an interactive onion plot.

## Current limits and next decisions

1. Member classification: column/wall versus beam, and tied versus spiral
2. DCR convergence tolerance and adaptive angular refinement
3. Robust concave, holed, and multi-region geometry through Shapely
4. Explicit-bar and imported-vertex tables in Excel
5. Hand calculations and cross-program benchmark cases
6. Repository license and intended distribution model

The dependency-free geometry kernel deliberately starts with convex rings.
Arbitrary concave and disconnected shapes are not yet production-ready.

## Code basis and warning

The phi transition follows the net tensile strain categories in ACI 318-19
Table 21.2.2, and the axial cap follows Section 22.4.2. The official code and
project-specific adopted requirements remain controlling:

- https://www.concrete.org/topicsinconcrete/318buildingcodeportal.aspx
- https://www.concrete.org/publications/getarticle.aspx?m=icap&pubID=51740277

Section PMM capacity does not evaluate deep-beam D-region behavior. If the
member qualifies as a deep beam, strut-and-tie, shear, bearing, anchorage, and
detailing checks remain separate required design work.
