# Initial architecture decisions

## Mechanics before user interface

The Python calculation package is the product core. Excel will translate
workbook tables into versioned input objects and write result objects back to
the workbook. No equilibrium, material, or code logic should live in cells or
VBA.

## Hybrid integration

The primary ultimate-strength backend uses analytical polygon clipping for an
equivalent rectangular concrete stress block and discrete reinforcing bars.
This avoids mesh sensitivity for routine code PMM analysis.

A concrete-fiber backend will implement the same resultant interface later. It
will be used for general stress-strain laws, moment-curvature, service response,
and as an independent numerical comparison for the analytical backend.

## Nominal mechanics separated from code resistance

The section solver returns nominal force and moment resultants, strains,
stresses, and equilibrium information. Separate code modules will apply
strength-reduction factors, axial caps, and code-specific classifications.

## Direct demand checks

For asymmetric sections, neutral-axis angle does not generally equal moment
vector angle. The current direct method solves neutral-axis depth at each
sampled orientation to form an Mx-My contour at the demand Pu, then intersects
the demand ray with that contour. It does not use a Bresler approximation.
Adaptive angular refinement and a continuous two-variable solver are planned;
until then, the reported DCR accuracy is governed by the selected angle step.

## Reproducibility

The canonical project format will be versioned JSON. Excel, DXF, and future
analysis-program integrations will be adapters around that format. Calculation
results will record engine version, code-module version, units, tolerances, and
input hash.
