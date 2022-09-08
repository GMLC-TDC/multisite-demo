the contents of this folder are the dummy federates for the uncontrolled case of NREL 4.5
This is transportation + distribution with BEAM and PyDSS.
This communication is replicated using a small dummy recording and list of stations paired with busnames 
to show what the BEAM charging station loads are and where they should be loaded onto the distribution
system model.

The json in this folder can be run with the helics cli to run just this portion of the co-simulation.

The inputs and outputs required for the controlled case are commented out in these dummy federates
and the controller federates are not contained here.

To run use command: helics --verbose run --path runner-allfeds0.json

The logs will show that the first charging station is changed to 7.2kW of load.
