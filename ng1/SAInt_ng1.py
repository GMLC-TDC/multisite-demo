# Dummy federate of gas network  - SAInt tool

import helics as h
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

def destroy_federate(fed):
    h.helicsFederateRequestTime(fed, h.HELICS_TIME_MAXTIME)
    h.helicsFederateDisconnect(fed)
    h.helicsFederateFree(fed)
    h.helicsCloseLibrary()
    logger.info("Federate finalized")

# Calculating the electrical output from the thermal power input iteratively
def CalculatePMW (Y, X0):
    iter = 0
    X_new = X0
    while iter < 20:       
        delY = Y*3.6 - (HR0*X_new + HR1*X_new*X_new + HR2*X_new*X_new*X_new) # = Pthermal/3.6
        if abs(delY) > 0.0001:
            delY_delX = -(HR0 + 2*HR1*X_new + 3*HR2*X_new*X_new)
            X_new = X_new - delY/delY_delX
            iter+=1
        else: break         
    return X_new

# Check for gas off-take limits
def CheckQLimit(QSet):
    if QSet > QMax:
        QSet = QMax
    elif QSet < QMin:
        QSet = QMin
    return QSet

# Calculate thermal power from active power using heat rate
def CalcPthermal(Pg):
    HR = HR0 + HR1*Pg + HR2*Pg*Pg
    return HR*Pg/3.6   # 3.6 is a MJ/kWh to MJ/MWh conversion factor  

if __name__ == "__main__":
    
    ##########  Registering  federate and configuring from JSON #############
    
    fed = h.helicsCreateValueFederateFromConfig("SAInt_ng1_Config.json")
    federate_name = h.helicsFederateGetName(fed)
    logger.info(f"Created federate {federate_name}")

    sub_count = h.helicsFederateGetInputCount(fed)
    logger.debug(f"\tNumber of subscriptions: {sub_count}")
    pub_count = h.helicsFederateGetPublicationCount(fed)
    logger.debug(f"\tNumber of publications: {pub_count}")
    
    # start initialization mode
    h.helicsFederateEnterInitializingMode(fed)
    fed.publications["ng1/node.6.avail"].publish(0)
    fed.publications["ng1/node.8.avail"].publish(0)

    ##############  Entering Execution Mode  ##################################
    h.helicsFederateEnterExecutingMode(fed)
    logger.info("Entered HELICS execution mode")

    print(fed.publications.keys())
    print(fed.subscriptions.keys())
    
    update_interval = int(h.helicsFederateGetTimeProperty(fed, h.HELICS_PROPERTY_TIME_PERIOD))
    grantedtime = 0
    total_interval = 10
    # Heat rate coefficients
    HR0 = 20           # MJ/kWh
    HR1 = -0.075       # (MJ/kWh)/MW 
    HR2 = 0.001        # (MJ/kWh)/(MW*MW)
    GCV = 39           # MJ/m^3
    QMin = 0           # m^3/s
    QMax = 1000        # m^3/s
     
    # As long as granted time is in the time range to be simulated...
    while grantedtime < total_interval:

        # Time request for the next physical interval to be simulated
        requested_time = grantedtime + update_interval
        logger.debug(f"Requesting time {requested_time}")
        grantedtime = h.helicsFederateRequestTime(fed, requested_time)
        logger.debug(f"Granted time {grantedtime}")

        ############# Subscription from Transmission Nodes 6 and 8 ############

        # Get the power output of node 6 in MW
        P_Node6_MW = fed.subscriptions["transmission/node.6.requested"].double
        logger.debug(f"\tReceived P_MW {P_Node6_MW:.2f}" f" from input Transmission Node 6")   
        
        # Get the power output of node 8 in MW
        P_Node8_MW = fed.subscriptions["transmission/node.8.requested"].double
        logger.debug(f"\tReceived P_MW {P_Node8_MW:.2f}" f" from input Transmission Node 8")
        
        ############# Publication for Transmission Node 6 ################
        
        # Calculate the thermal power and gas off take for Node 6
        Pthermal_Node6_MW = CalcPthermal(P_Node6_MW)
        QSET_Node6 = Pthermal_Node6_MW/GCV
        logger.debug(f"\tQSET requested from transmission Node 6 (m^3/s): {QSET_Node6:.2f}")
        
        # Check for QSET limits
        QSET_Node6 = CheckQLimit(QSET_Node6)
        logger.debug(f"\tQSET available for transmission Node 6 (m^3/s): {QSET_Node6:.2f}")
       
        Pthermal_Node6_MW = GCV * QSET_Node6
        
        P_Node6_MW_new = CalculatePMW (Pthermal_Node6_MW, P_Node6_MW)
        
        # Publish available active power in MW
        fed.publications["ng1/node.6.avail"].publish(P_Node6_MW_new)
        logger.debug(f"\tElectrical output power available for Node 6 " f"{P_Node6_MW_new:.2f}")

        ############# Publication for Transmission Node 8 #################################

        # Calculate the thermal power and gas off take for Node 8
        Pthermal_Node8_MW = CalcPthermal(P_Node8_MW)
        QSET_Node8 = Pthermal_Node8_MW/GCV
        logger.debug(f"\tQSET requested from transmission Node 8 (m^3/s): {QSET_Node8:.2f}")
        
        # Check for QSET limits
        QSET_Node8 = CheckQLimit(QSET_Node8)
        logger.debug(f"\tQSET available for transmission Node 8 (m^3/s): {QSET_Node8:.2f}")
        
        Pthermal_Node8_MW = GCV * QSET_Node8
        
        P_Node8_MW_new = CalculatePMW (Pthermal_Node8_MW, P_Node8_MW)
        
        # Publish available active power in MW
        fed.publications["ng1/node.8.avail"].publish(P_Node8_MW_new)
        logger.debug(f"\tElectrical output power available for Node 8 " f"{P_Node8_MW_new:.2f}")

    # Cleaning up HELICS stuff once we've finished the co-simulation.
    destroy_federate(fed)
    
