# -*- coding: utf-8 -*-
import time
import helics as h
from math import pi
import random
import sys
import logging
import toml

logging.basicConfig(filename='subtrans_federate.log', level=logging.INFO)
region_list = str(sys.argv[2:]).replace('[','').replace(']','').replace("'",'').replace(",",' ')
regions = region_list.split(' ') #['full_network']
fed_name = 'subtrans_federate'
fedinitstring = "--federates=1 --timeout=60min --broker_address {} --port 23404".format(sys.argv[1])
deltat = 0.01

helicsversion = h.helicsGetVersion()

print(fed_name + ": Helics version = {}".format(helicsversion))

# Create Federate Info object that describes the federate properties #
fedinfo = h.helicsCreateFederateInfo()

# Set Federate name #
h.helicsFederateInfoSetCoreName(fedinfo, fed_name)

# Set core type from string #
h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq_ss") #"zmq"

# Federate init string #
h.helicsFederateInfoSetCoreInitString(fedinfo, fedinitstring)

# Set the message interval (timedelta) for federate. Note th#
# HELICS minimum message time interval is 1 ns and by default
# it uses a time delta of 1 second. What is provided to the
# setTimedelta routine is a multiplier for the default timedelta.

# Set one second message interval #
h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, deltat)
h.helicsFederateInfoSetIntegerProperty(fedinfo, h.helics_property_int_log_level, 7)

# Create value federate #
vfed = h.helicsCreateValueFederate(fed_name, fedinfo)
print("Value federate created")

# Register the publication #
feeder_subs=[]
feeders=[]
trans_subs = []
region_loads = []
#for region in regions:
#    region_subs = f"{region}/Scenarios/{region}/ExportLists/Subscriptions.toml"
#    with open(region_subs, 'r') as rf:
#        subs_toml = toml.load(rf)
#    for sub in subs_toml.keys():
#        if sub.startswith('Load'):
#            feeder = sub.split('.')[-1]
#            feeder_sub = subs_toml[sub]["Subscription ID"]
#            feeders.append(feeder)
#            feeder_subs.append(feeder_sub)
# tab in the two lines below for original
for region in regions:
    trans_subs.append(h.helicsFederateRegisterSubscription(vfed, f"trans_federate/{region}.voltage", 'pu'))
    region_loads.append(h.helicsFederateRegisterPublication(vfed, f"{region}.Circuit.full_network.TotalPower", 2, "kW"))
print(fed_name+": Publication and subscription to transmission registered")

pubs = []
subs = []
#n_feeders = len(feeders)
#for i_fed in range(n_feeders):
#    feeder = feeders[i_fed]
#    feeder_sub = feeder_subs[i_fed]
#    voltage_pub = f"{fed_name}.Load.{feeder}.puVmagAngle"
#    print(voltage_pub)
#    pubs.append(h.helicsFederateRegisterGlobalPublication(vfed, voltage_pub, 2, "pu"))
#    logging.info(fed_name + ": "+feeder+ " voltage publication registered")
#    subs.append(h.helicsFederateRegisterSubscription(vfed, feeder_sub, "kW"))
#    logging.info(fed_name + ": "+feeder+" Real and reactive load subscription registered")
feeder_name = 'p13ulv9380' # this is the name of a feeder from a SMART-DS simulation that is used in this dummy sim
for region in regions:
    voltage_pub = f"{region}.Load.{feeder_name}.puVmagAngle"
    pubs.append(h.helicsFederateRegisterGlobalPublication(vfed, voltage_pub, 2, "pu"))
    feeder_sub = f'{feeder_name}.Circuit.{feeder_name}.TotalPower' # with PyDSS may need to change sub format to f'{feeder_name}.Circuit.full_network.TotalPower'
    subs.append(h.helicsFederateRegisterSubscription(vfed, feeder_sub, "kW"))
logging.info(f"{fed_name}: pubs and subs registered with distribution side.")

# edit this when running with control
#pubs.append(h.helicsFederateRegisterPublication(vfed, "cs_power_limits", 1, "kw")

# Enter execution mode #
h.helicsFederateEnterExecutingMode(vfed)
print(fed_name + ": Entering execution mode")

# start execution loop #
currenttime = -1 
desiredtime = 0.01
t = 0.00
end_time = 24*3600 + 300
while desiredtime <= end_time:
    # publish
    print(f'requesting time {desiredtime} with currenttime: {currenttime}')
    currenttime = h.helicsFederateRequestTime(vfed, desiredtime)
    #currenttime, iteration_state= h.helicsFederateRequestTimeIterative(vfed, desiredtime, True)#h.helics_iteration_request_iterate_if_needed)
    print(f'time granted = {currenttime}')
    if currenttime >= desiredtime:
        for p in pubs:
            print(f"publishing voltage for time {currenttime}")
            logging.info("publishing 69kV voltage for time: {}".format(currenttime))
            h.helicsPublicationPublishVector(p, [1.01/0.00002510218561694025])#+ random.random()/100 + 0.03

        total_kw = 0
        total_kvar = 0
        for i in range(len(regions)):#range(n_feeders):
            feeder = feeder_name #feeder = feeders[i]
            power_vector = h.helicsInputGetVector(subs[i])
            if isinstance(power_vector, list):
                total_kw += power_vector[0]
                if len(power_vector)>1:
                    total_kvar += power_vector[1]
            print(f"feeder {feeder} load {power_vector} for time {currenttime}")
            logging.info("Circuit {} active power demand: {} kW at time: {}.".format(feeder, power_vector, currenttime))
        for i_trans in range(len(regions)):
            trans_sub=trans_subs[i_trans]
            trans_pub=region_loads[i_trans]
            region = regions[i_trans]
            trans_v = h.helicsInputGetDouble(trans_sub)
            print(f"region {region} feed-in voltage {trans_v} for time {currenttime}")
            h.helicsPublicationPublishVector(trans_pub, [total_kw, total_kvar])
            print(f"region {region} total load published as {total_kw}kW, {total_kvar}kvar")

        t += 1
    desiredtime = t*5*60

#
# all other federates should have finished, so now you can close the broker
h.helicsFederateFinalize(vfed)
print(fed_name+": Transmission Federate finalized")


h.helicsFederateDestroy(vfed)
print(fed_name+": transmission federate destroyed")
h.helicsFederateFree(vfed)
print("federate freed")
h.helicsCloseLibrary()
print("library closed")

