# Shape versus fiber baseline

Both backends use the identical Whitney stress block, steel model, bar layout,
neutral-axis orientation, and neutral-axis depth. Only concrete integration
changes. Therefore, the differences below measure mesh discretization error;
they do not compare Whitney behavior to a nonlinear concrete law.

For the 20 x 30 in starter section, the oblique case at theta = 37 degrees and
Pn = 1000 kip gives the following moment-magnitude errors relative to analytical
shape integration:

| Long-axis divisions | Fibers | Target cell (in) | Moment error |
|---:|---:|---:|---:|
| 10 | 70 | 3.0000 | 0.88396% |
| 20 | 280 | 1.5000 | 0.08705% |
| 40 | 1,080 | 0.7500 | -0.08517% |
| 80 | 4,320 | 0.3750 | -0.02099% |
| 160 | 17,120 | 0.1875 | 0.00503% |

Pure-axis convergence is less smooth because a discontinuous Whitney block can
cross an entire fiber row as the grid refines. This is a strong reason to use
analytical shape integration as the default for code PMM capacity. A fiber
backend remains valuable for nonlinear constitutive laws, moment-curvature,
service response, and independent convergence checks.
