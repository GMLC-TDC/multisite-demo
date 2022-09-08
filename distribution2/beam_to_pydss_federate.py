# this file creates an intermediate federate
# it maps the coordinates from TEMPO to the nearest charging
# station modeled in PyDSS


# UPDATE: Presumably dont need this any more because the SPMC takes its place


import time
import helics as h
import numpy as np
import logging
import json
import os
import sys

def run_beam_to_pydss_federate(station_bus_pairs, broker_ip):
    logging.basicConfig(filename='beam_to_pydss_fed.log', level=logging.DEBUG)
    fedinfo = h.helicsCreateFederateInfo()

    # set the name
    h.helicsFederateInfoSetCoreName(fedinfo, "beam_to_pydss_fed")

    # set core type
    h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq_ss")

    fed_init_string = f"--federates=1 --broker_address={broker_ip} --port=23404"# --interface={broker_ip}"
    print(fed_init_string)
    # set initialization string
    h.helicsFederateInfoSetCoreInitString(fedinfo, fed_init_string) #f"--federates=1 --broker_address=tcp://{broker_ip}")

    # set message interval
    deltat = 1.0  # smallest discernable interval to this federate
    h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, deltat)

    # create federate
    cfed = h.helicsCreateCombinationFederate("beam_to_pydss_fed", fedinfo)
    print("beam_to_pydss_fed created")
    logging.info("beam_to_pydss_fed created")

    # register publications
    # publish an ordered list of charging station codes in same order as charging loads
    pubs_station_loads = {}

    for s in range(len(station_bus_pairs)):
        station_id = station_bus_pairs[s][0]
        pubs_station_loads[station_id] = h.helicsFederateRegisterPublication(cfed, "Load."+station_id, 4, "")
    print("publications registered")

    # register subscriptions 
    # subscribe to information from TEMPO such that you can map to PyDSS modeled charging stations
    subs_charger_loads = h.helicsFederateRegisterSubscription(cfed, "beamFederate/chargingLoad", "kW") # subscribes from the spmc federate in controlled case
    ##subs_power_limit = h.helicsFederateRegisterSubscription(cfed, "trans_federate/cs_power_limits", "kW")
    #print("subscriptions registered")

    # enter execution mode
    h.helicsFederateEnterExecutingMode(cfed)
    print("beam_to_pydss_federate in execution mode")
    logging.info("beam_to_pydss_federate in execution mode")

    currenttime = -1
    timebin = 300
    # start execution loop
    for t in range(0, 24*3600, timebin):
        if t==0:
            t=0.01
        print(f'requesting time {t}')
        while currenttime < t:
            currenttime = h.helicsFederateRequestTime(cfed, t)
            time.sleep(0.01)
        print(f'time requested: {t}, time granted: {currenttime}')
        charger_load_json = json.loads(h.helicsInputGetString(subs_charger_loads))
        #charger_load_json = []
        logging.debug("charger loads received at currenttime: " + str(t) + " seconds: {charger_load_json}")
        updated_station_ids = []
        #updated_station_ids = ['cs_privatevehicle_43_residential_homelevel1(1_8|ac)', 'cs_privatevehicle_43_residential_homelevel2(7_2|ac)']
        #updated_station_q = []
        #updated_station_p = []
        updated_station_loads = []
        logging.info('Logging this as CSV')
        logging.info('stationId,estimatedLoad,currentTime')
        if isinstance(charger_load_json,float):
            print(f'charger load is float: {charger_load_json}')
        else:
            print(charger_load_json)
            for station in charger_load_json:
                if 'reservedFor' in station.keys():
                    #taz = station['tazId']
                    parking_type = station['reservedFor'].replace('(','').replace(')','')
                    charger_type = 'publiclevel2|7.2ac'#station['chargingPointType']
                    manager_id = station['parkingZoneId']
                else:
                    #taz = station['subSpace']
                    parking_type = station['pType'] #station['parking_Type']
                    charger_type = 'publiclevel2|7.2ac'#station['chrgType']
                    manager_id = station[0]
                n_plugs = 1 #station['numChargers']
                station_id = ('cs_'+str(manager_id)+'_'+str(charger_type)).replace('.','').lower().replace('(','').replace(')','').replace('|','') # +'_'+str(n_plugs)
                station_load = float(station['estimatedLoad'])
                station_q_load = get_reactive_load(station_load, charger_type)
                updated_station_ids.append(station_id)
                updated_station_loads.append([station_load, station_q_load])
                load_str = f'station: {station_id} load: {[station_load, station_q_load]} time: {t}'
                print(load_str)
                logging.info(load_str)

        # uncomment this when pydss is included
        for i in range(len(updated_station_ids)):
            # publish the station assignments
            updated_station = updated_station_ids[i]
            updated_load = updated_station_loads[i]
            if updated_station in pubs_station_loads:
                h.helicsPublicationPublishVector(pubs_station_loads[updated_station], updated_load)#[station_P, station_Q])
        # also publish all the others
        print('updated stations loads published')
        for station_pub in pubs_station_loads:
            if station_pub not in updated_station_ids:
                h.helicsPublicationPublishVector(pubs_station_loads[station_pub], [0.001, 0.0])
        print('unupdated station loads published')
    # close the federate
    h.helicsFederateFinalize(cfed)
    print("mapping federate finalized")
    logging.warning("beam_to_pydss_federate finalized")

    h.helicsFederateFree(cfed)
    h.helicsCloseLibrary()


###############################################################################
def load_station_bus_pairs(station_bus_pairs_file='/home/npanossi/gemini-helper/gemini_helper/station_bus_pairs.csv'):
    with open(station_bus_pairs_file, 'r') as sbpfile:
        station_bus_list = sbpfile.readlines()
    station_bus_pairs = []
    for sbp in station_bus_list:
        pair = sbp.split(',')
        station_id = pair[0].strip()
        bus_name = pair[1].strip()
        station_bus_pairs.append((station_id, bus_name))
    return station_bus_pairs

def get_reactive_load(real_load, charger_type, pf=0.98):
    reactive_load = (real_load/pf)*np.sin(np.arccos(pf)) #0.95 pf = active/apparent, reactive = apparent*sin(theta), active = apparent*cos(theta), reactive = (active/0.95)sin(cos-1(0.95))
    return reactive_load

if __name__ == "__main__":
    station_bus_pairs_file = sys.argv[1]
    station_bus_pairs = load_station_bus_pairs(station_bus_pairs_file)
    print("stations_list_loaded")
    print(sys.argv)
    broker_ip = sys.argv[2]
    run_beam_to_pydss_federate(station_bus_pairs,broker_ip)
