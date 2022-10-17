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
import pprint
import json

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

# Setting up pretty printing, mostly for debugging.
pp = pprint.PrettyPrinter(indent=4)


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
    #logger.info(pp.pformat(fed))

    logger.info(f"Created federate {fed.name}")
    logger.debug(f"\tNumber of subscriptions: {fed.n_inputs}")
    logger.debug(f"\tNumber of publications: {fed.n_publications}")

    # Diagnostics to confirm JSON config correctly added the required
    #   publications and subscriptions
    subid = {}
    pubid = {}
    logger.info("Subscription details:")
    #logger.info(pp.pformat(fed.subscriptions))
    
    for i in range(0, fed.n_inputs):
        # logger.info(f"k: {k}")
        # logger.info(f"v: {v}")
        subid[i] = fed.get_subscription_by_index(i)
        logger.debug(f"\tRegistered subscription---> {subid[i].target}")

    for i in range(0, fed.n_publications):
        pubid[i] = fed.get_publication_by_index(i)
        #logger.info(pp.pformat(pubid[i]))
        logger.debug(f"\tRegistered publication---> {pubid[i].name}")
        
        

    ##########  Setting up data structures ################
    hours_of_sim = 24
    total_interval = int(hours_of_sim * 60 * 60)
    #update_interval = int(fed.property["TIME_PERIOD"])
    grantedtime = 0

    

    
    # Data collection lists
    pub_data = []
    sub_data = []
    for j in range(0, fed.n_publications):
        pub_data.append([[],[]])
        sub_data.append([[],[]])
        
    
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
    
    double_idx = [0, 1, 3, 4]
    complex_idx = [2, 5, 6, 8, 9, 10]
    json_idx = [7]
    default_sub_values = [
        1000.0,
        1000.0,
        21.7+12.7j,
        1000.0,
        1000.0,
        29.5+16.6j,
        13.5+5.8j,
        '{"constant_kW": 13.5, "constant_kVAR": 5.8, "P_bid": [100, 100], "Q_bid": [100, 100]}',
        14.9+5j,
        3.5+1.8j,
        6.1+1.6j
    ]
    
    
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
        
    nominal_bid = [
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        {"constant_kW": 13.5, "constant_kVAR": 5.8, "P_bid": [100, 100], "Q_bid": [100, 100]},
        0,
        0,
        0]
        
    # Arbitrarily defined initial bus voltages
    voltage_V = [
        0,
        0,
        100000.0+10000j,
        0,
        0,
        100000.0+10000j,
        100000.0+10000j,
        0,
        100000.0+10000j,
        100000.0+10000j,
        100000.0+10000j]
        
    # Arbitrarily defined initial generator setpoint fuel consumption
    mmbtu_using = [
        1000.0,
        1000.0,
        0,
        1000.0,
        1000.0,
        0,
        0,
        0,
        0,
        0,
        0]
        
    # Arbitrarily defined available MMBtu from ng federates
    nominal_mmbtu_avail = [
        1000.0,
        1000.0,
        0,
        1000.0,
        1000.0,
        0,
        0,
        0,
        0,
        0,
        0]
        
    # Arbitrarily defined initial energy price
    energy_price = 100
    
    
    # Defining default values for the subscriptions by API since doing so is
    #   not supported via JSON config at the time of this writing.
    logger.info('Setting default values')
    for idx, val in enumerate(default_sub_values):
        logger.info(f'\tdefault value for {subid[idx].target}: {default_sub_values[idx]}')
        #subid[i].set_default(default_sub_values[i])
        if idx in double_idx:
            h.helicsInputSetDefaultDouble(subid[idx], default_sub_values[idx])
        elif idx in complex_idx:
            h.helicsInputSetDefaultComplex(subid[idx], default_sub_values[idx])
        elif idx in json_idx:
            h.helicsInputSetDefaultString(subid[idx], default_sub_values[idx])
    
    granted_time = 0  
    
    # keeping track of past bids to only update when a new value comes indent
    past_bid = nominal_bid[7]

    ##############  Entering Execution Mode  ##################################
    fed.enter_executing_mode()
    logger.info("Entered HELICS execution mode")
    
    logger.info('Checking defaults for all subscriptions')
    for idx in range(0, fed.n_inputs):
        logger.info(f'\tsubscription: {subid[idx].target} (sub. index: {idx})')
        if idx in double_idx:
            logger.info(f'\t\tdouble default value: {subid[idx].double}')
        elif idx in complex_idx:
            logger.info(f'\t\tcomplex default value: {subid[idx].complex}')
        elif idx in json_idx:
            logger.info(f'\t\tcomplex default value: {pp.pformat(subid[idx].json)}')
    
    
    # As long as granted time is in the time range to be simulated...   
    while granted_time < total_interval:

        # Time request for the next physical interval to be simulated
        requested_time = total_interval
        # logger.debug(f"Requesting time {requested_time}")
        granted_time = fed.request_time(requested_time)
        logger.debug(f'Granted time {granted_time} ({granted_time/3600} of {hours_of_sim} hours)')
        hour = granted_time / 3600

        # Iterating over publications in this case since this example
        #  uses only one charging voltage for all five batteries

            
        for j in range(0, fed.n_subscriptions):
            logger.info(f'\tProcessing subscription: {subid[j].target} (sub. index: {j})')
            if nominal_load[j] != 0:
                # Scaling loads so distribution load matches nominal load assumed 
                #   by transmission model
                scaled_load = subid[j].complex * load_scaling[j]
                logger.info(f'\t\tscaled_load: {scaled_load}')
                load_mag = abs(scaled_load)
                sub_data = collect_data(sub_data, j, hour, load_mag)
            
                # Scaling bus voltage due to change in load
                # Calculating the magnitude of difference between the nominal and 
                #   provided load and scaling nodal voltage appropriately
                #   (increase load = decreased voltage)
                # Voltage impact factor minimizes change in voltage due to change in load
                #   to keep voltage impact reasonable
                voltage_impact_factor = 0.5
                load_scaling_factor = (abs(scaled_load) - abs(nominal_load[j])) / abs(nominal_load[j])
                voltage_impact_factor = 1 - (voltage_impact_factor * load_scaling_factor)
                voltage_V[j] = voltage_V[j] * voltage_impact_factor
                logger.info(f'\t\tload_scaling_factor: {load_scaling_factor}')
                logger.info(f'\t\tvoltage_impact_factor: {voltage_impact_factor}')
                logger.info(f'\t\tvoltage_V: {voltage_V[j]}')
                # Pythonic API not working for me right now
                # pubid[j].publish(voltage_V)
                h.helicsPublicationPublishComplex(pubid[j], voltage_V[j])
                logger.info(f'\t\tPublishing voltage_V: {voltage_V[j]}')
                Vmag = abs(voltage_V[j])
                pub_data = collect_data(pub_data, j, hour, Vmag)
                
            elif nominal_bid[j] != 0:
                # Adjusting energy price (the publication next in order) based
                #   on the same change in load
                energy_bid_string = subid[j].string
                energy_bid = json.loads(energy_bid_string)
                logger.info(f'\t\tenergy_bid: {pp.pformat(energy_bid_string)}')
                #Bid JSON looks like:
                #{
                #    "constant_kW": double,
                #    "constant_kVAR": double,
                #    "P_bid":[
                #        double,
                #        double,
                #        ...
                #   ],
                #    "Q_bid":[
                #        double,
                #        double,
                #        ...
                #    ],
                #}
                if past_bid["constant_kW"] != energy_bid["constant_kW"]:
                    logger.info("\t\tNew bid, update price")
                    logger.info(f'\t\t\tcurrent energy_price: {energy_price}')
                    past_bid = energy_bid
                    sub_data = collect_data(sub_data, j, hour, energy_bid["constant_kW"])
                    bid_scaling_factor = (energy_bid["constant_kW"] - nominal_bid[j]["constant_kW"]) / nominal_bid[j]["constant_kW"]
                    price_impact_factor = 0.2
                    energy_scaling_factor = bid_scaling_factor * price_impact_factor
                    energy_price = energy_price * (1 + energy_scaling_factor)
                    logger.info(f'\t\t\tbid_scaling_factor: {bid_scaling_factor}')
                    logger.info(f'\t\t\tenergy_scaling_factor: {energy_scaling_factor}')
                    logger.info(f'\t\t\tenergy_price: {energy_price}')
                
                    # pubid[j].publish(energy_price)
                    h.helicsPublicationPublishDouble(pubid[j], energy_price)
                    logger.info(f'\t\tPublishing energy_price: {energy_price}')
                    pub_data = collect_data(pub_data, j, hour, energy_price)
                else:
                    logger.info("\t\tNo new bid")
                
            elif nominal_mmbtu_avail[j] != 0:            
                # Scaling all bus voltages due to change in generator output due to lack of fuel
                mmbtu_avail = subid[j].double
                sub_data = collect_data(sub_data, j, hour, mmbtu_avail)
                logger.info(f'\t\tmmbtu_avail: {mmbtu_avail}')
                mmbtu_using[j] = max(mmbtu_using[j], mmbtu_avail)
                logger.info(f'\t\tmmbtu_using: {mmbtu_using[j]}')
                # Pythonic API not working for me right now
                # pubid[j].publish(mmbtu_using)
                h.helicsPublicationPublishDouble(pubid[j], mmbtu_using[j])
                logger.info(f'\t\tPublishing mmbtu_using: {mmbtu_using[j]}')
                pub_data = collect_data(pub_data, j, hour, mmbtu_using[j])
            
    destroy_federate(fed)


    logger.info('Making graphs')
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
                    'Bus 13 inflexible energy bid quantity (MWh)',
                    'Bus 14 load (MVA)',
                    'Bus 11 load (MVA)',
                    'Bus 12 load (MVA)']
    graph_file_names = [
                    'Node 2 Natural Gas.png',
                    'Node 3 Natural Gas.png',
                    'Node 2 Distribution.png',
                    'Node 6 Natural Gas.png',
                    'Node 8 Natural Gas.png',
                    'Node 9 Distribution.png',
                    'Node 13 Distribution.png',
                    'Node 13 Prices.png',
                    'Node 14 Distribution.png',
                    'Node 11 Distribution.png',
                    'Node 12 Distribution.png']
   
   
    for j in range(0, fed.n_publications):
        fig, ax1 = plt.subplots()
        ax1.plot(pub_data[j][0], pub_data[j][1])
        ax2 = ax1.twinx()
        ax2.plot(sub_data[j][0], sub_data[j][1])
        ax1.set_xlabel('simulation time (hr)')
        ax1.set_ylabel(pub_labels[j])
        ax2.set_ylabel(sub_labels[j])
        plt.show()
        plt.savefig(graph_file_names[j])
        
