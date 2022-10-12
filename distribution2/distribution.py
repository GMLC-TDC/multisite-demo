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
    
    def __init__(self, base_v = 12470, loads_mva=[10+ 1j * 5, 7+ 1j * 5, 1.5 + 1j * 0.5], phase_cond = "2/0_acsr", neut_cond = "1/0_acsr", length_mi = 1.00, iter= 100, damp_coef=0.2):
        super().__init__(base_v) 
        self.iter = iter
        self.damp_coef = damp_coef
        self.va = [1e6 * mva for mva in loads_mva]
        self.line = Line(phase_cond, neut_cond, length_mi) 
        self.loads = [Load(s.real, s.imag, 0.333, 0.333, 0.333, 0.333, 0.333, 0.333) for s in self.va]
    
    def solve(self, v1, v2, v3):
        vsrc = self.voltage(v1, v2, v3)
        v = self.voltage(v1, v2, v3)

        for j in range(self.iter): 
            s = []
            for k, ld in enumerate(self.loads):     
                s.append(ld.power(abs(v[k])))
            s = np.array(s)
            i = np.array([np.conj(s / v)]).T         
            dv = np.matmul(self.line.zabc,  i)[:,0]
            v = vsrc - dv * self.damp_coef
            print(pd.DataFrame(v))

        line_losses = np.matmul(self.line.zabc,  i**2)
        total_load = line_losses + s
        return s  / 1e6
    
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
    
    def __init__(self, P_base_zip, Q_base_zip, a0, a1, a2, b0, b1, b2):
        self.P_base_zip = P_base_zip
        self.Q_base_zip = Q_base_zip
        self.a0= a0
        self.a1 = a1
        self.a2 = a2
        self.b0 = b0
        self.b1 = b1
        self.b2 = b2

        
    def power(self, v:float):
        P = self.P_base_zip * (self.a0  + self.a1 * (v/self.V0) + self.a2* (v/self.V0)**2)
        Q = self.Q_base_zip * (self.b0  + self.b1 * (v/self.V0) + self.b2* (v/self.V0)**2)
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

def collect_data(data_list, idx, time, value):
    data_list[idx][0].append(time)
    data_list[idx][1].append(value)
    return data_list


if __name__ == "__main__":
    
    fed = h.helicsCreateValueFederateFromConfig("distribution_config.json")
    
    logger.info(f"Created federate {fed.name}")
    logger.debug(f"\tNumber of subscriptions: {fed.n_inputs}")
    logger.debug(f"\tNumber of publications: {fed.n_publications}")


    subid = {}
    pubid = {}
    for k, v in fed.subscriptions.items():
        logger.debug(f"\tRegistered subscription---> {k}")
        subid[k] = fed.get_subscription_by_name(k)

    for k, v in fed.publications.items():
        logger.debug(f"\tRegistered publication---> {k}")
        pubid[k] = fed.get_publication_by_name(k)
    
    hours_of_sim = 24
    total_interval = int(hours_of_sim * 60 * 60)
    #update_interval = int(fed.property["TIME_PERIOD"])
    grantedtime = 0

    # Data collection lists
    pub_data = []
    sub_data = []
    for j in range(0, fed.n_publications):
        pub_data[j] = tuple([],[])
        sub_data[j] = tuple([],[])

    fed.enter_executing_mode()
    logger.info("Entered HELICS execution mode")


    dist = Distribution()

    while grantedtime < total_interval:
        
        requested_time = total_interval
        logger.debug(f"Requesting time {requested_time}")
        granted_time = fed.request_time(requested_time)
        logger.debug(f"Granted time {granted_time}")
        hour = granted_time / 3600
        
        v = None
        v = subid[0].complex
        sub_data = collect_data(sub_data, j, hour, v)
            
        s = dist.solve(
            cplx(v, 0),
            cplx(v, 120),
            cplx(v, 240), 
        )
        s_total = sum(s)

        pubid[0].publish(s_total)
        pub_data = collect_data(pub_data, j, hour, s_total)
        
    destroy_federate(fed)

    for j in range(0, fed.n_publications):
        fig, ax1 = plt.subplots()
        ax1.plot(pub_data[j][0], pub_data[j][1])
        ax2 = ax1.twinx()
        ax2.plot(sub_data[j][0], sub_data[j][1])
        ax1.set_xlabel('simulation time (hr)')
        plt.show()
        

