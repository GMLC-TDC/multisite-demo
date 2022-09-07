# -*- coding: utf-8 -*-
"""
Created on 09/02/2022

Dummy federate for the transmission system model used in the HELICS+ capstone project

@author: Trevor Hardy
trevor.hardy@pnnl.gov
"""

import matplotlib.pyplot as plt
import helics as h
import logging


logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


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

    ##########  Registering  federate and configuring from JSON ################
    fed = h.helicsCreateValueFederateFromConfig("transmission_config.json")

    logger.info(f"Created federate {fed.name}")
    logger.debug(f"\tNumber of subscriptions: {fed.n_inputs}")
    logger.debug(f"\tNumber of publications: {fed.n_publications}")

    # Diagnostics to confirm JSON config correctly added the required
    #   publications and subscriptions
    subid = {}
    pubid = {}
    for k, v in fed.subscriptions.items():
        logger.debug(f"\tRegistered subscription---> {k}")
        subid[k] = fed.get_subscription_by_name(k)

    for k, v in fed.publications.items():
        logger.debug(f"\tRegistered publication---> {k}")
        pubid[k] = fed.get_publication_by_name(k)
        
        

    ##########  Setting up data structures ################
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
        
    
    # Assumes the subscriptions are in the following order:
    #   0   ng2/node.2.avail
    #   1   ng2/node.3.avail
    #   2   distribution1/pcc.2.pq
    #   3   ng1/node.6.avail
    #   4   ng1/node.8.avail
    #   5   distribution2/pcc.9.pq
    #   6   distribution3/pcc.13.pq
    #   7   distribution3_TE_agents/pcc.13.rt_energy.bid
    #   8   distribution4/pcc.14.pq
    #   9   distribution5/pcc.11.pq
    #   10  distribution5/pcc.12.pq
    
    # Scaling-factors for each subscription; not all subscriptions are for 
    #   distribution loads
    load_scaling = [
        0,
        0,
        1,
        0,
        0,
        1,
        1,
        0,
        1,
        1,
        1]
        
    # Nominal load values for each bus (in subscription order):
        nominal_load = [
        0,
        0,
        21.7+12.7j,
        0,
        0,
        29.5+16.6j,
        13.5+5.8j,
        0,
        14.9+5j,
        3.5+1.8j,
        6.1+1.6j]
        
    nominal_bid = 1000]
        
    # Arbitrarily defined initial bus voltages
    voltage_V = [
        0,
        0,
        100000,
        0,
        0,
        100000,
        100000,
        0,
        100000,
        100000,
        100000]
        
    # Arbitrarily defined initial generator setpoint fuel consumption
    mmbtu_using = [
        1000,
        1000,
        0,
        1000,
        1000,
        0,
        0,
        0,
        0,
        0,
        0]
        
    # Arbitrarily defined initial generator setpoint fuel consumption
    energy_price = 100
    
    
        

    ##############  Entering Execution Mode  ##################################
    fed.enter_executing_mode()
    logger.info("Entered HELICS execution mode")
    # As long as granted time is in the time range to be simulated...
    while grantedtime < total_interval:

        # Time request for the next physical interval to be simulated
        requested_time = total_interval
        # logger.debug(f"Requesting time {requested_time}")
        granted_time = fed.request_time(requested_time)
        logger.debug(f"Granted time {granted_time}")
        hour = granted_time / 3600

        # Iterating over publications in this case since this example
        #  uses only one charging voltage for all five batteries

            
        for j in range(0, fed.n_subscriptions):
            logger.info(f'\tsubscription: {fed.subscriptions[j]}')
            if nominal_load[j] != 0:
                # Scaling loads so distribution load matches nominal load assumed 
                #   by transmission model
                scaled_load = subid[j].complex * load_scaling[j]
                logger.info(f'\t\tscaled_load: {scaled_load[j]}')
                sub_data = collect_data(sub_data, j, hour, scaled_load)
            
                # Scaling bus voltage due to change in load
                # Calculating the magnitude of difference between the nominal and 
                #   provided load and scaling nodal voltage appropriately
                #   (increase load = decreased voltage)
                # Voltage impact factor minimizes change in voltage due to change in load
                voltage_impact_factor = 0.5
                load_scaling_factor = (abs(scaled_load) - abs(nominal_load[j]))/abs(nominal_load[j]))
                voltage_impact_factor = 1 - (voltage_impact_factor * load_scaling_factor)
                voltage_V[j] = voltage_V[j] * load_scaling_factor
                logger.info(f'\t\tload_scaling_factor: {load_scaling_factor}')
                logger.info(f'\t\tvoltage_impact_factor: {voltage_impact_factor}')
                logger.info(f'\t\tvoltage_V: {voltage_V[j]}')
                pubid[j].publish(voltage_V)
                pub_data = collect_data(pub_data, j, hour, voltage_V)
                
                # Adjusting energy price (the publication next in order) based
                #   on the same change in load
                energy_bid = subid[j+1].vector # JSON with "price", "quantity" keys
                sub_data = collect_data(sub_data, j+1, hour, energy_bid['quantity'])
                bid_scaling_factor = (energy_bid['quantity'] - nominal_bid)/nominal_bid)
                price_impact_factor = 1
                energy_scaling_factor = 1 + (bid_scaling_factor * price_impact_factor)
                energy_price = energy_price * energy_scaling_factor
                logger.info(f'\t\tenergy_scaling_factor: {energy_scaling_factor}')
                logger.info(f'\t\tenergy_price: {energy_price}')
                pudid[j+1].publish(energy_price)
                pub_data = collect_data(pub_data, j, hour, energy_price)
                
            elif nominal_mmbtu_avail[j] != 0:            
                # Scaling all bus voltages due to change in generator output due to lack of fuel
                mmbtu_avail = subid[j].double
                sub_data = collect_data(sub_data, j, hour, mmbtu_avail)
                logger.info(f'\t\tmmbtu_avail: {mmbtu_avail}')
                mmbtu_using[j] = max(mmbtu_using[j], mmbtu_avail)
                logger.info(f'\t\tmmbtu_using: {mmbtu_using[j]}')
                pubid[j].publish(mmbtu_using)
                pub_data = collect_data(pub_data, j, hour, mmbtu_using)
            
    destroy_federate(fed)



    # Printing out final results graphs for comparison/diagnostic purposes.
    pub_labels = [  'MMBtu using', 
                    'MMBtu using', 
                    'Bus 2 voltage (V)', 
                    'MMBtu using', 
                    'MMBtu using',
                    'Bus 9 voltage (V)',
                    'Bus 13 voltage (V)',
                    'Bus 13 LMP ($/MWh)',
                    'Bus 14 voltage (V)',
                    'Bus 11 voltage (V)',
                    'Bus 12 voltage (V)']
    sub_labels = [  'MMBtu available', 
                    'MMBtu available', 
                    'Bus 2 load (MVA)', 
                    'MMBtu available', 
                    'MMBtu available',
                    'Bus 9 load (MVA)',
                    'Bus 13 load (MVA)',
                    'Bus 13 energy bid quantity (MWh)',
                    'Bus 14 load (MVA)',
                    'Bus 11 load (MVA)',
                    'Bus 12 load (MVA)']
   
    for j in range(0, fed.n_publications):
        fig, ax1 = plt.subplots()
        ax1.plot(pub_data[j][0], pub_data[j][1])
        ax2 = ax1.twinx()
        ax2.plot(sub_data[j][0], sub_data[j][1])
        ax1.set_xlabel('simulation time (hr)')
        ax1.set_ylabel(pub_labels[j])
        ax2.set_ylabel(sub_labels[j])
        plt.show()
        
