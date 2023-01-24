import time
import helics as h
import sys
import logging
import toml

### federate configuration
federate_name = 'distribution_2'
feeder_name= 'p13uhs12_1247'
region = feeder_name.split('h')[0]
start_time = 0
timestep = 300 #seconds
end_time = 24*3600 #24 hours

### Setup federate
logging.basicConfig(filename=f'{federate_name}.log', level=logging.DEBUG)
fed_name = feeder_name
if len(sys.argv)>1:
    broker_ip = sys.argv[1]
else:
    broker_ip = '127.0.0.1'
fedinitstring = f"--federates=1 --timeout=60min --broker_address {broker_ip} --port 23404"
deltat = 0.01
helicsversion = h.helicsGetVersion()
print(fed_name + ": Helics version = {}".format(helicsversion))
# Create Federate Info object that describes the federate properties #
fedinfo = h.helicsCreateFederateInfo()
# Set Federate name #
h.helicsFederateInfoSetCoreName(fedinfo, fed_name)
# Set core type from string #
h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq_ss") #"tcp_ss"
# Federate init string #
h.helicsFederateInfoSetCoreInitString(fedinfo, fedinitstring)
# Set 0.01 second message interval #
h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, deltat)
h.helicsFederateInfoSetIntegerProperty(fedinfo, h.helics_property_int_log_level, 7)
# Create value federate #
vfed = h.helicsCreateValueFederate(fed_name, fedinfo)
print("Value federate created")
# create all dummy busses #
with open('mini_station_bus_pairs.csv', 'r') as sbp_file:
    sbp_lines = sbp_file.readlines()
bus_names = []
charger_names = []
for sbp_line in sbp_lines:
    bus_names.append(sbp_line.split(', ')[1].replace('\n',''))
    charger_names.append(sbp_line.split(', ')[0])
n_buses = len(bus_names)
logging.debug(f'bus names: {bus_names}')
logging.debug(f'charger names: {charger_names}')
trunk_name = feeder_name.split('_')[0]
bus_voltages = [1.0 for i_bus in range(n_buses)] # p.u.
bus_currents = [[100, 120] for i_bus in range(n_buses)] # amps currentMagAng
logging.debug(f'bus currents: {bus_currents}')
bus_loads = [[100, 10] for i_bus in range(n_buses)] # real and reactive in kVA
new_bus_loads = [[100,10] for i_bus in range(n_buses)]
total_bus_loads = [[10000,2000] for i_bus in range(n_buses)]
battery_soc = [50 for i_charger in charger_names] 

### register publications
#volt_pubs = []
#current_pubs = []
power_pubs = []
#soc_pubs = []
for i_bus in range(n_buses):
    #volt_pubs.append(h.helicsFederateRegisterGlobalPublication(vfed, f'{bus_names[i_bus]}.Load.{bus_names[i_bus]}.puVmagAngle', 2, '')) # per unit not recognized, so leave that entry blank
    #logging.debug(f'voltage publication: {bus_names[i_bus]}.Load.{bus_names[i_bus]}.puVmagAngle registered')
    #current_pubs.append(h.helicsFederateRegisterGlobalPublication(vfed, f'{bus_names[i_bus]}.Lines.{bus_names[i_bus]}.CurrentsMagAng', h.HELICS_DATA_TYPE_VECTOR, ''))
    #logging.debug(f'current publication: {bus_names[i_bus]}.Lines.{bus_names[i_bus]}.CurrentsMagAng registered')
    power_pubs.append(h.helicsFederateRegisterGlobalPublication(vfed, f'{bus_names[i_bus]}.Circuit.{bus_names[i_bus]}.TotalPower', h.HELICS_DATA_TYPE_VECTOR, '')) #real and reactive
    logging.debug(f'total feeder power publication: {bus_names[i_bus]}.Circuit.{bus_names[i_bus]}.TotalPower registered')
    #soc_pubs.append(h.helicsFederateRegisterGlobalPublication(vfed, f'{fed_name}/Storage.storage_{charger_names[i_bus]}.percstored', h.HELICS_DATA_TYPE_DOUBLE, ''))
    #logging.debug(f'storage SOC {fed_name}/Storage.storage_{charger_names[i_bus]}.percstored registered')

### register subscriptions
load_subs = [] # these are the charging station loads
battery_subs = []
for i_bus in range(n_buses):
    load_subs.append(h.helicsFederateRegisterSubscription(vfed, f'beam_to_pydss_fed/Load.{charger_names[i_bus]}', 'kW')) #f'taz_name_spmc/Load.{charger_names[i_bus]}', 'kW'))
    logging.debug(f'charger load beam_to_pydss_fed/Load.{charger_names[i_bus]} registered')
#for i_battery in range(len(charger_names)):
#    battery_subs.append(h.helicsFederateRegisterSubscription(vfed, f'taz_name_spmc/btms_{charger_names[i_battery]}charge', 'kW'))
#    logging.debug(f'behind the meter storage charging power subscription registered as taz_name_spmc/btms_{charger_names[i_battery]}charge')

# enter executing mode
h.helicsFederateEnterExecutingMode(vfed)
print(fed_name + ": Entering execution mode")


### run through time with federate
granted_t = 0.0
for fed_t in range(0, end_time+timestep, timestep):
    if fed_t <= 0:
        fed_t = 0.01 # helics has a hard time co-iterating at the 0th timestep
    logging.info(f'requesting {fed_t} with granted time {granted_t}')
    while fed_t > granted_t:
        granted_t = h.helicsFederateRequestTime(vfed, fed_t)
        time.sleep(0.01)
    logging.debug(f'granted time {granted_t}')
    # publish and subscribe
    for i_bus in range(n_buses):
        #h.helicsPublicationPublishDouble(volt_pubs[i_bus], bus_voltages[i_bus])
        #h.helicsPublicationPublishVector(current_pubs[i_bus], bus_currents[i_bus])
        h.helicsPublicationPublishVector(power_pubs[i_bus], total_bus_loads[i_bus])
        #h.helicsPublicationPublishDouble(soc_pubs[i_bus], battery_soc[i_bus]) 
        # get charging station loads
        charger_load = h.helicsInputGetVector(load_subs[i_bus])
        if fed_t < 600 and (not isinstance(charger_load, list) or abs(charger_load[0])>10e20):
            logging.warning(f'charger load read as {charger_load} at time {fed_t}, continuing with {new_bus_loads[i_bus]}')
        else:
            new_bus_loads[i_bus] = charger_load
            logging.debug(f'bus load {charger_names[i_bus]} read as {new_bus_loads[i_bus]}')
        # get battery charging
        #battery_power = h.helicsInputGetDouble(battery_subs[i_bus])
        #if fed_t < 600 and abs(battery_power)>10e20:
        #    logging.warning(f'battery power read as {battery_power} at time {fed_t}, continuing with SOC at {battery_soc[i_bus]}')
        #else:
        #    battery_soc[i_bus] = battery_soc[i_bus] - battery_power
        #    logging.debug(f'battery state of charge at {charger_names[i_bus]} changed to {battery_soc[i_bus]}')
    # dummy voltage response
    for i_bus in range(n_buses):
        total_bus_loads[i_bus][0] = total_bus_loads[i_bus][0] + new_bus_loads[i_bus][0] - bus_loads[i_bus][0]
        #if new_bus_loads[i_bus][0] > bus_loads[i_bus][0]:
        #    bus_voltages[i_bus] = bus_voltages[i_bus] - 0.01
        #    bus_currents[i_bus][0] = bus_currents[i_bus][0] + 5
        #if new_bus_loads[i_bus][0] < bus_loads[i_bus][0]:
        #    bus_voltages[i_bus] = bus_voltages[i_bus] + 0.01
        #    bus_currents[i_bus][0] = bus_currents[i_bus][0] - 5
    bus_loads = new_bus_loads
    logging.debug(f'bus voltages in response to new laods: {bus_voltages}')
   
### close out federate
#h.helicsFederateFinalize(vfed)
h.helicsFederateDisconnect
logging.info(fed_name+": dummy_distribution_federate finalized")
h.helicsFederateDestroy(vfed)
logging.debug(fed_name+": dummy_distribution_federate destroyed")
h.helicsFederateFree(vfed)
logging.debug("federate freed")
h.helicsCloseLibrary()
logging.debug("library closed")
