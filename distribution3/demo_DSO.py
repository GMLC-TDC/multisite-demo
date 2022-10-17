import math
import json
import numpy as np
import helics as h
import pandas as pd
from datetime import datetime, timedelta
import logging
import random as r
import pprint
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

# Setting up pretty printing, mostly for debugging.
pp = pprint.PrettyPrinter(indent=4)

r.seed(2608)

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

def create_broker(simulators):
    initstring = "--federates=" + str(simulators) + " --name=mainbroker"
    broker = h.helicsCreateBroker("zmq", "", initstring)
    isconnected = h.helicsBrokerIsConnected(broker)
    if isconnected == 1:
        pass

    return broker


def get_load_profiles(wrapper_config):

    load_profile_path = wrapper_config['matpower_most_data']['datapath'] + wrapper_config['matpower_most_data']['load_profile_info']['filename']
    input_resolution = wrapper_config['matpower_most_data']['load_profile_info']['resolution']
    input_data_reference_time =  datetime.strptime(wrapper_config['matpower_most_data']['load_profile_info']['starting_time'], '%Y-%m-%d %H:%M:%S')
    start_data_point = int((start_date - input_data_reference_time).total_seconds() / input_resolution)
    end_data_point   = int((end_date - input_data_reference_time).total_seconds() / input_resolution)
    load_profile_data = pd.read_csv(load_profile_path, skiprows = start_data_point+1, nrows=(end_data_point-start_data_point)+1, header=None)
    new_col_idx = load_profile_data.shape[1]
    load_profile_data[new_col_idx] = pd.date_range(start=start_date, end = end_date, freq='5min')
    load_profile_data.set_index(new_col_idx, inplace=True)
    sample_interval = str(wrapper_config['physics_powerflow']['interval'])+'s'
    load_profile_data_pf_interval = load_profile_data.resample(sample_interval).interpolate()

    return load_profile_data_pf_interval


def create_helics_configuration(helics_config, filename):
    Transmission_Sim_name = helics_config['name']
    helics_config['coreInit'] = '--federates=1'
    helics_config['coreName'] = 'DSO Federate'
    helics_config['name'] = 'DSOSim'
    helics_config['publications'] = [];
    helics_config['subscriptions'] = [];

    for bus in wrapper_config['cosimulation_bus']:
        helics_config['publications'].append({'global': bool(True),
                                           'key': str(helics_config['name']+ '.pcc.' + str(bus) + '.pq'),
                                           'type': str('complex')
                                           })
        helics_config['publications'].append({'global': bool(True),
                                           'key': str(helics_config['name']+ '.pcc.' + str(bus) + '.rt_energy.bid'),
                                           'type': str('JSON')
                                           })

        helics_config['subscriptions'].append({'required': bool(False),
                                           'key': str(Transmission_Sim_name + '.pcc.' + str(bus) + '.pnv'),
                                           'type': str('complex')
                                           })
        helics_config['subscriptions'].append({'required': bool(False),
                                           'key': str(Transmission_Sim_name + '.pcc.' + str(bus) + '.rt_energy.cleared'),
                                           'type': str('JSON')
                                           })

    out_file = open(filename, "w")
    json.dump(helics_config, out_file, indent=4)
    out_file.close()

    return

if __name__ == "__main__":
    json_path = './matpowerwrapper_config.json'
    with open(json_path, 'r') as f:
        wrapper_config = json.loads(f.read())
        
#     Hard-coding values for multi-site demo
#     case_path = wrapper_config['matpower_most_data']['datapath'] + wrapper_config['matpower_most_data']['case_name']
#     with open(case_path, 'r') as f:
#         logger.info(f.read())
#         case = json.loads(f.read())

    timestamp = []
    load_data = []

    start_date = datetime.strptime(wrapper_config['start_time'], '%Y-%m-%d %H:%M:%S')
    end_date   = datetime.strptime(wrapper_config['end_time'], '%Y-%m-%d %H:%M:%S')
    duration   = (end_date - start_date).total_seconds()


    ##### Getting Load Profiles from input Matpower data #####
    # Hard-coding load for multi-side demo
    #load_profiles = get_load_profiles(wrapper_config)


    ##### Setting up HELICS Configuration #####
    logger.info('DSO: HELICS Version {}'.format(h.helicsGetVersion()))
    helics_config_filename = 'demo_DSO.json'
    #create_helics_configuration(wrapper_config['helics_config'], helics_config_filename)

    ##### Starting HELICS Broker #####
    # h.helicsBrokerDisconnect(broker)
    # broker = create_broker(2)


    ##### Registering DSO Federate #####
    fed = h.helicsCreateCombinationFederateFromConfig('demo_DSO.json')
    logger.info('DSO: Registering {} Federate'.format(h.helicsFederateGetName(fed)))

    pubkeys_count = h.helicsFederateGetPublicationCount(fed)
    pub_keys = []
    for pub_idx in range(pubkeys_count):
        pub_object = h.helicsFederateGetPublicationByIndex(fed, pub_idx)
        pub_keys.append(h.helicsPublicationGetName(pub_object))
    logger.info('DSO: {} Federate has {} Publications'.format(h.helicsFederateGetName(fed), pubkeys_count))


    subkeys_count = h.helicsFederateGetInputCount(fed)
    sub_keys = []
    for sub_idx in range(subkeys_count):
        sub_object = h.helicsFederateGetInputByIndex(fed, sub_idx)
        sub_keys.append(h.helicsSubscriptionGetTarget(sub_object))
    logger.info('DSO: {} Federate has {} Inputs'.format(h.helicsFederateGetName(fed), subkeys_count))

    # logger.info(pub_keys)
    # logger.info(sub_keys)

    #####  Entering Execution for DSO Federate #####
    status = h.helicsFederateEnterExecutingMode(fed)
    logger.info('DSO: Federate {} Entering execution'.format(h.helicsFederateGetName(fed)))

    buffer = 1  ###### Buffer to sending out data before the Operational Cycle  ######
    tnext_physics_powerflow = wrapper_config['physics_powerflow']['interval']-buffer
    tnext_real_time_market  = wrapper_config['real_time_market']['interval']-buffer
    tnext_day_ahead_market  = wrapper_config['day_ahead_market']['interval']-buffer


    # duration = 300
    time_granted = -1
    
    flexibility = .20
    blocks = 10
    P_range = np.array([10, 30]) 
    nominal_cleared_price = 100
    cleared_price = 100 # Initial value
    
    while time_granted <= duration:
        
        next_helics_time = min([tnext_physics_powerflow, tnext_real_time_market, tnext_day_ahead_market]);
        
        time_granted = h.helicsFederateRequestTime(fed, next_helics_time)

        logger.info('DSO: Requested {}s and got Granted {}s'.format(next_helics_time, time_granted))
        current_time = start_date + timedelta(seconds=time_granted)
        logger.info('\tDSO: Current Time is {}'.format(current_time))


        ######## Real time Market Intervals ########
        if time_granted >= tnext_real_time_market and wrapper_config['include_real_time_market']:
            
            profile_time = current_time + timedelta(seconds=buffer)
            # Hard-coding value for multi-site demo
            # data_idx = load_profiles.index[load_profiles.index == profile_time]
            # current_load_profile = load_profiles.loc[data_idx]
            for cosim_bus in wrapper_config['cosimulation_bus']:
#                 Hard-coding value for multi-site demo
#                 base_kW = case['bus'][cosim_bus-1][2]
#                 base_kVAR = case['bus'][cosim_bus - 1][3]
#                 current_kW = current_load_profile[cosim_bus].values[0]
                load_scaling_factor = 1 * (cleared_price - nominal_cleared_price)/nominal_cleared_price
                logger.info(f'\t\tload_scaling_factor: {load_scaling_factor}')
                current_kW = 12 + (2 * r.random()) - (5 * load_scaling_factor)
                logger.info(f'\t\tcurrent_kW: {current_kW}')
                constant_load = current_kW
                flex_load = current_kW*(flexibility)
                Q_values = np.linspace(0, flex_load, blocks)
                P_values = np.linspace(max(P_range), min(P_range), blocks)
                
                # Hard-coded value for multi-site demo
                # current_load = complex(current_kW, current_kW*base_kVAR/base_kW)
                current_load = complex(current_kW, current_kW*0.2)
                bid =  dict()
                bid['constant_kW'] = constant_load
                # bid['constant_kVAR'] = constant_load*base_kVAR/base_kW
                # Hard-coded value for multi-site demo
                bid['constant_kVAR'] = constant_load*0.2
                bid['P_bid'] = list(P_values)
                bid['Q_bid'] = list(Q_values)
                
                
                bid_raw = json.dumps(bid)
                
                 #####  Publishing current loads for Co-SIM Bus the ISO Simulator #####
                pub_key = [key for key in pub_keys  if ('pcc.' + str(cosim_bus) + '.rt_energy.bid') in key ]
                pub_object = h.helicsFederateGetPublication(fed, pub_key[0])
                status = h.helicsPublicationPublishString(pub_object, bid_raw)
                logger.info('\tDSO: Published Bids for Bus {}'.format(cosim_bus))
                logger.info(f'\t\t{pp.pformat(bid_raw)}')
                
                                
            time_request = time_granted+2
            while time_granted < time_request:
                time_granted = h.helicsFederateRequestTime(fed, time_request)

            logger.info('DSO: Requested {}s and got Granted {}s'.format(time_request, time_granted))

            for cosim_bus in wrapper_config['cosimulation_bus']:
                sub_key = [key for key in sub_keys  if ('pcc.' + str(cosim_bus) + '.lmp') in key ]
                logger.info(f'\tSubscription key: {sub_key[0]}')
                sub_object = h.helicsFederateGetSubscription(fed, sub_key[0])
                cleared_price = h.helicsInputGetDouble(sub_object)
                logger.info('\tDSO: Received cleared price {} for Bus {}'.format(cleared_price, cosim_bus))

            tnext_real_time_market = tnext_real_time_market + wrapper_config['real_time_market']['interval']           
            
            
            
        ######## Power Flow Intervals ########
        if time_granted >= tnext_physics_powerflow and wrapper_config['include_physics_powerflow']:
            
            profile_time = current_time + timedelta(seconds=buffer)
            # Hard-coding value for multi-site demo
#             data_idx = load_profiles.index[load_profiles.index == profile_time]
#             current_load_profile = load_profiles.loc[data_idx]
            for cosim_bus in wrapper_config['cosimulation_bus']:
#                 Hard-coding value for multi-site demo
#                 base_kW = case['bus'][cosim_bus-1][2]
#                 base_kVAR = case['bus'][cosim_bus - 1][3]
                # current_kW = current_load_profile[cosim_bus].values
                current_kW = 12 + (2 * r.random())
                # Hard-coded value for multi-site demo
                #current_load = complex(current_kW, current_kW*base_kVAR/base_kW)
                current_load = complex(current_kW, current_kW*0.2)

                #####  Publishing current loads for Co-SIM Bus the ISO Simulator #####
                pub_key = [key for key in pub_keys  if ('pcc.' + str(cosim_bus) + '.pq') in key ]
                pub_object = h.helicsFederateGetPublication(fed, pub_key[0])
                status = h.helicsPublicationPublishComplex(pub_object, current_load.real, current_load.imag)
                logger.info('\tDSO: Published {} demand for Bus {}'.format(current_load, cosim_bus))
                
                
            load_data.append(current_kW)
            timestamp.append(time_granted)

            time_request = time_granted+2
            while time_granted < time_request:
                time_granted = h.helicsFederateRequestTime(fed, time_request)

            logger.info('DSO: Requested {}s and got Granted {}s'.format(time_request, time_granted))

            for cosim_bus in wrapper_config['cosimulation_bus']:
                sub_key = [key for key in sub_keys  if ('pcc.' + str(cosim_bus) + '.pnv') in key ]
                sub_object = h.helicsFederateGetSubscription(fed, sub_key[0])
                voltage = h.helicsInputGetComplex(sub_object)
                logger.info('\tDSO: Received {} Voltage for Bus {}'.format(voltage, cosim_bus))

            tnext_physics_powerflow = tnext_physics_powerflow + wrapper_config['physics_powerflow']['interval']

    
    destroy_federate(fed)


    plt.plot(timestamp, load_data)
    plt.xlabel('Time(s)')
    plt.ylabel('Load (kW)')
    plt.savefig('Distribution 3 Real Load.png')