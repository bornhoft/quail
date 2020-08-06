import code

import processing.post as post
import processing.plot as plot
import processing.readwritedatafiles as readwritedatafiles

### Postprocess
fname = "ader_final.pkl"
solver = readwritedatafiles.read_data_file(fname)
print('Solution Final Time:', solver.Time)

# Unpack
mesh = solver.mesh
physics = solver.physics

# Error
TotErr, _ = post.L2_error(mesh, physics, solver, "Scalar")
# Plot
plot.PreparePlot()
plot.plot_solution(mesh, physics, solver, "Scalar", plot_numerical=True, plot_exact=False, plot_IC=False, create_new_figure=True,
                        ylabel=None, fmt='bo', legend_label="DG", equidistant_pts=True,
                        include_mesh=False, regular_2D=False, equal_AR=False)
plot.plot_solution(mesh, physics, solver, "Scalar", plot_exact=True, plot_numerical=False, create_new_figure=False, fmt='k-')
plot.plot_solution(mesh, physics, solver, "Scalar", plot_IC=True, plot_numerical=False, create_new_figure=False, fmt='k--')

plot.ShowPlot()