from scipy.spatial import distance
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from math import *
import helics as h
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


def cplx(mag, ang):
    return mag*cos(ang * pi / 180) + 1j * mag * sin(ang * pi / 180)

class Vsource:
    def __init__(self, base_v):
        self.base_v = base_v
        self.v = np.array([
            cplx(self.base_v, 0),
            cplx(self.base_v, 120),
            cplx(self.base_v, 240), 
        ])
        return
    
    def voltage(self, v1, v2, v3):
        return np.array([v1, v2, v3])

class Distribution(Vsource):
    
    def __init__(self, base_v = 12470, loads_mva=[10+ 1j * 5, 7+ 1j * 5, 1.5 + 1j * 0.5], phase_cond = "2/0_acsr", neut_cond = "1/0_acsr", length_mi = 1.00, iter= 10, damp_coef=0.2):
        super().__init__(base_v) 
        self.iter = iter
        self.damp_coef = damp_coef
        self.va = [1e6 * mva for mva in loads_mva]
        self.line = Line(phase_cond, neut_cond, length_mi) 
        self.loads = [Load(s.real, s.imag, 0.333, 0.333, 0.333, 0.333, 0.333, 0.333) for s in self.va]
    
    def solve(self, v1, v2, v3, hour=0):
        vsrc = self.voltage(v1, v2, v3)
        v = self.voltage(v1, v2, v3)

        for j in range(self.iter): 
            s = []
            for k, ld in enumerate(self.loads):     
                s.append(ld.power(abs(v[k]), hour))
            s = np.array(s)
            i = np.array([np.conj(s / v)]).T         
            dv = np.matmul(self.line.zabc,  i)[:,0]
            v = vsrc - dv * self.damp_coef
            print(pd.DataFrame(v))
        
        line_losses = np.matmul(self.line.zabc,  i**2)
        total_load = line_losses + s
        return s  / 1e6
    
    
    def step(self, v1, v2, v3, hour=0, iter=0):
        if iter == 0:
            self.vsrc = self.voltage(v1, v2, v3)
            self.v = self.voltage(v1, v2, v3)
        
        s = []
        for k, ld in enumerate(self.loads):     
            s.append(ld.power(abs(self.v[k]), hour))
        s = np.array(s)
        i = np.array([np.conj(s / self.v)]).T         
        dv = np.matmul(self.line.zabc,  i)[:,0]
        self.v = self.vsrc - dv * self.damp_coef
        return s / 1e6
    
class Line:
    
    conductors = {
        "1/0_acsr" : {
            "gmr": 0.00446,
            "r": 1.12,
            "D": 0.398
        },
        "2/0_acsr" : {
            "gmr":0.0051,
            "r": 0.895,
            "D": 0.447,
        },
        "3/0_acsr" : {
            "gmr": 0.006,
            "r": 0.723,
            "D": 0.502,
        },
        "4/0_acsr" : {
            "gmr": 0.00814,
            "r": 0.592,
            "D": 0.563
        }
    }
    
    def __init__(self, phase_cond, neut_cond, length_mi):
        self.node_from = []
        self.node_to = []
        
        line_coordinates_feet = np.array([(-3, 28), (0, 28), (3, 28), (0.5, 24)])
        ri = [self.conductors[phase_cond]["r"]  for i in range(3)]
        ri.append(self.conductors[neut_cond]["r"])
        
        gmri = [self.conductors[phase_cond]["gmr"]  for i in range(3)]
        gmri.append(self.conductors[neut_cond]["gmr"])
        
        d = distance.cdist(line_coordinates_feet, line_coordinates_feet, 'euclidean')
        for i in range(len(d)):
            d[i,i] = gmri[i]
        
        
        self.z = np.zeros(d.shape, dtype='complex')
        r, c = self.z.shape
        for i in range(r):
            for j in range(c):
                if i != j:
                    self.z[i,j] = 0.09560 + 1j * 0.12134* (log(1/ d[i,j]) + 7.93402)
                else:
                    self.z[i,j] = ri[i] + 0.09560 + 1j * 0.12134* (log(1/ d[i,j]) + 7.93402)
        
        self.z = self.z * length_mi
        self.kron_reduce()
           
        return
    
    def kron_reduce(self):
        zij = self.z[:-1, :-1]
        zin = self.z[:-1, -1]
        zni = self.z[-1, :-1]
        znn = self.z[-1, -1]
        
        Znn_inv = 1 / znn
        self.zabc = zij - zin * Znn_inv * zni

class Load:  
    
    V0 = 12470
    
    p_mult = [
        0.234691835,
        0.229034317,
        0.227490826,
        0.222013942,
        0.195736465,
        0.193091067,
        0.193435559,
        0.191517371,
        0.192126068,
        0.191746793,
        0.189942295,
        0.192108579,
        0.192941868,
        0.192050569,
        0.194871089,
        0.196599609,
        0.194925606,
        0.1958755,
        0.194701331,
        0.195934406,
        0.271757251,
        0.251337621,
        0.260453095,
        0.251741707,
        0.251436243,
    ]
    q_mult = [
        0.278016439,
        0.277619014,
        0.277022846,
        0.276474464,
        0.277174515,
        0.278060909,
        0.278921556,
        0.279590884,
        0.280457674,
        0.281393433,
        0.28235974,
        0.282888484,
        0.283838129,
        0.284713835,
        0.285651877,
        0.285835895,
        0.284156868,
        0.282273533,
        0.280600101,
        0.306000758,
        0.334530701,
        0.334195778,
        0.318559143,
        0.279674607,
        0.281256544,
    ]
    
    def __init__(self, P_base_zip, Q_base_zip, a0, a1, a2, b0, b1, b2):
        self.P_base_zip = P_base_zip
        self.Q_base_zip = Q_base_zip
        self.a0= a0
        self.a1 = a1
        self.a2 = a2
        self.b0 = b0
        self.b1 = b1
        self.b2 = b2

        
    def power(self, v:float, hour:int=0):
        p_base = self.P_base_zip * self.p_mult[hour]
        q_base = self.Q_base_zip * self.q_mult[hour]
        P = p_base * (self.a0  + self.a1 * (v/self.V0) + self.a2* (v/self.V0)**2)
        Q = q_base * (self.b0  + self.b1 * (v/self.V0) + self.b2* (v/self.V0)**2)
        return P + 1j* Q

def destroy_federate(fed):
    """
    As part of ending a HELICS co-simulation it is good housekeeping to
    formally destroy a federate. Doing so informs the rest of the
    federation that it is no longer a part of the co-simulation and they
    should proceed without it (if applicable). Generally this is done
    when the co-simulation is complete and all federates end execution
    at more or less the same wall-clock time.
    :param fed: Federate to be destroyed
    :return: (none)
    """
     # Adding extra time request to clear out any pending messages to avoid
    #   annoying errors in the broker log. Any message are tacitly disregarded.
    grantedtime = h.helicsFederateRequestTime(fed, h.HELICS_TIME_MAXTIME)
    status = h.helicsFederateDisconnect(fed)
    h.helicsFederateFree(fed)
    h.helicsCloseLibrary()
    logger.info("Federate finalized")



if __name__ == "__main__":
    
    
    
    fed = h.helicsCreateValueFederateFromConfig("distribution_config.json")
    
    logger.info(f"Created federate {fed.name}")
    logger.debug(f"\tNumber of subscriptions: {fed.n_inputs}")
    logger.debug(f"\tNumber of publications: {fed.n_publications}")
    
    hours_of_sim = 24
    total_interval = int(hours_of_sim * 60 * 60)
    granted_time = 0
    max_iterations = 10


    fed.enter_executing_mode()
    logger.info("Entered HELICS execution mode")

    update_interval = int(h.helicsFederateGetTimeProperty(fed, h.HELICS_PROPERTY_TIME_PERIOD)) * 60 * 60

    dist = Distribution()
    while granted_time < total_interval:
        requested_time = granted_time + update_interval
        logger.debug(f"Requesting time {requested_time}")
        granted_time = fed.request_time(requested_time)
        logger.debug(f"Granted time {granted_time}")
        
        v = fed.subscriptions['pcc.2.pnv'].double
        if v > 1.12 or v < 0.0:
            v = 12470
        
        s_total = None
        for i in range(max_iterations):
            s = dist.step(
                cplx(v, 0),
                cplx(v, 120),
                cplx(v, 240),
                int(granted_time / 3600),
                i      
            )
            s_total = sum(s)
            print(s_total)
        
        fed.publications['distribution_2/pcc.2.pq'].publish(s_total)

        
    destroy_federate(fed)


