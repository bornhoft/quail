import numpy as np

TimeStepping = {
    "StartTime" : 0.,
    "EndTime" : 0.5,
    "NumTimeSteps" : 40,
    "TimeScheme" : "ADER",
}

Numerics = {
    "InterpOrder" : 2,
    "InterpBasis" : "LagrangeSeg",
    "InterpolateIC" : True,
    "Solver" : "ADERDG",
}

Output = {
    "WriteInterval" : 1,
    "WriteInitialSolution" : True,
    "AutoProcess" : True,
}

Mesh = {
    "File" : None,
    "ElementShape" : "Segment",
    "NumElems_x" : 16,
    "xmin" : -1.,
    "xmax" : 1.,
    # "PeriodicBoundariesX" : ["xmin","xmax"]
}

Physics = {
    "Type" : "ConstAdvScalar",
    "ConvFlux" : "LaxFriedrichs",
    "ConstVelocity" : 1.,
}

InitialCondition = {
    "Function" : "Sine",
    "omega" : 2*np.pi,
}

ExactSolution = InitialCondition.copy()

BoundaryConditions = {
    "Left" : {
	    "Function" : "Sine",
	    "omega" : 2*np.pi,
    	"BCType" : "StateAll",
    },
    "Right" : {
    	"BCType" : "Extrapolate",
    },
}