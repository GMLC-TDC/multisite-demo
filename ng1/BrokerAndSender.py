# -*- coding: utf-8 -*-
import helics as h
import time
import struct
import math

# helics_broker --broker_address=54.67.2.187 --localinterface=127.0.0.1 -f 1 --loglevel=trace -t zmq_ss

print("HELICS version=" + str(h.helicsGetVersion()))

initstring = "-f 2 --name=mainbroker --loglevel=trace"
broker = h.helicsCreateBroker("zmq_ss", "", initstring)

fed = h.helicsCreateCombinationFederateFromConfig("Sender.json")
# start initialization mode
h.helicsFederateEnterInitializingMode(fed)
fed.publications["transmission/node.6.requested"].publish(0)
fed.publications["transmission/node.8.requested"].publish(0)

print(fed.publications.keys())
print(fed.subscriptions.keys())

h.helicsFederateEnterExecutingMode(fed)

for request_time in range(1, 97):
    h.helicsFederateRequestTime(fed, request_time)
    fed.publications["transmission/node.6.requested"].publish(request_time*math.pi)
    fed.publications["transmission/node.8.requested"].publish(2*request_time*math.pi)
    data1 = fed.subscriptions["ng1/node.6.avail"].double
    data2 = fed.subscriptions["ng1/node.8.avail"].double
    print(data1)
    print(data2)

h.helicsFederateDisconnect(fed)
h.helicsFederateFree(fed)
h.helicsCloseLibrary()