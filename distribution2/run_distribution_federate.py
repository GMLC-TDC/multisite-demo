import sys
import os
import toml
import time

#from .utils import GEMINI_XFC_SCRATCH_FOLDER

CURRENT_DIRECTORY = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
FED_DIRECTORY = os.path.join(CURRENT_DIRECTORY, sys.argv[2]) #GEMINI_XFC_SCRATCH_FOLDER / sys.argv[2]
#update the broker ip address
data=toml.load(open(os.path.join(FED_DIRECTORY, 'simulation.toml')))
data['Helics'].update({"Broker":sys.argv[1]})
with open(os.path.join(FED_DIRECTORY, "simulation.toml"),mode="w") as fil:
    toml.dump(data,fil)

# pause to make sure toml is saved correctly before running federate
time.sleep(5)

# run federate
pydss_path=r'C:\\Users\\npanossi\\Documents\\PyDSS' # this will need updated based on where you have it installed
sim_path= FED_DIRECTORY
sim_file=r'simulation.toml'
def run_pyDSS(sim_path):
    print(pydss_path, sim_path)
    sys.path.append(pydss_path)
    sys.path.append(os.path.join(pydss_path, 'PyDSS'))
    from pydss_project import PyDssProject
    project = PyDssProject.load_project(sim_path)
    project.run()

if __name__ == "__main__":
    #pydss_path = r'/projects/geminixfc/PyDSS_geminixfc/PyDSS'
    sim_path = FED_DIRECTORY
    #sim_file = r'simulation.toml'
    run_pyDSS(sim_path)


