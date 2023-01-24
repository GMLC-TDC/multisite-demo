the contents of this folder are the dummy federates for the uncontrolled case of NREL 4.5
This is transportation + distribution with BEAM and PyDSS.
The PyDSS instance here uses the gemini branch of PyDSS which can be cloned at https://github.com/NREL/PyDSS/tree/gemini
and the path where you have cloned it should be put in line 20 of run_distribution_federate.py
This communication is replicated using a small dummy recording and list of stations paired with busnames 
to show what the BEAM charging station loads are and where they should be loaded onto the distribution
system model.

The runner-allfeds0.json in this folder can be run with the helics cli to run just this portion of the co-simulation.
The runner-dist2_dummies.json in this folder can be used to run these federates with a master broker for the co-simulation.
If the runner-dist2_dummies.json is used with a broker on another machine/node, then the IPs in that json must be updated.
All federates also assume default ports, so those may need updated when running across multiple machines. 
The runner-dist2_real.json in this folder can be used to run a real PyDSS distribution system federate instead of the dummy within the co-simulation.1

The inputs and outputs required for the controlled case are commented out in these dummy federates
and the controller federates are not contained here.

To run use command: helics --verbose run --path runner-allfeds0.json

The logs will show that the first charging station is changed to 7.2kW of load.
