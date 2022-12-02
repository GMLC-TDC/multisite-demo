# -*- coding: utf-8 -*-
"""
Created on 12/2/2022

Tests connection to AWS-based broker-server used for the multi-site demo

@author: Trevor Hardy
trevor.hardy@pnnl.gov
"""

import helics as h
import logging


logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

def destroy_federate(fed):
    '''
    As part of ending a HELICS co-simulation it is good housekeeping to
    formally destroy a federate. Doing so informs the rest of the
    federation that it is no longer a part of the co-simulation and they
    should proceed without it (if applicable). Generally this is done
    when the co-simulation is complete and all federates end execution
    at more or less the same wall-clock time.

    :param fed: Federate to be destroyed
    :return: (none)
    '''

    # Adding extra time request to clear out any pending messages to avoid
    #   annoying errors in the broker log. Any message are tacitly disregarded.
    grantedtime = h.helicsFederateRequestTime(fed, h.HELICS_TIME_MAXTIME)
    status = h.helicsFederateDisconnect(fed)
    h.helicsFederateFree(fed)
    h.helicsCloseLibrary()
    logger.info('Federate finalized')


def create_value_federate(fedinitstring,name,period):
    fedinfo = h.helicsCreateFederateInfo()
    h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq_ss")
    h.helicsFederateInfoSetCoreInitString(fedinfo, fedinitstring)
    h.helicsFederateInfoSetIntegerProperty(fedinfo, h.helics_property_int_log_level, 1)
    h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_period, period)
    logger.info('Federate parameters set, creating federate....')
    fed = h.helicsCreateValueFederate(name, fedinfo)
    logger.info('...and federate is created.')
    return fed


if __name__ == "__main__":
 	##########  Registering  federate and configuring with API################
	fedinitstring = " --federates=1 --broker_address=54.67.2.187"
	name = "aws_broker_tester"
	period = 1
	logger.info(f'Creating federate {name}')
	fed = create_value_federate(fedinitstring,name,period)
	logger.info(f'Created federate {name}')
    
	pub_name = f'aws_broker_tester/test_pub'
	pubid = h.helicsFederateRegisterGlobalTypePublication(fed, pub_name, 'string')
	logger.debug(f'\tRegistered publication---> {pub_name}')
	sub_name = f'aws_broker_tester/test_pub'
	subid = h.helicsFederateRegisterSubscription(fed, sub_name)
	logger.debug(f'\tRegistered subscription---> {sub_name}')

	##############  Entering Execution Mode  ##################################
	h.helicsFederateEnterExecutingMode(fed)
	logger.info('Entered HELICS execution mode')
    
	requested_time = 1
	logger.debug(f'Requesting time {requested_time}')
	grantedtime = h.helicsFederateRequestTime (fed, requested_time)
	logger.debug(f'Granted time {grantedtime}')
	h.helicsPublicationPublishString(pubid, 'test_message')
	logger.debug('Published "test_message"')

	requested_time = 2
	logger.debug(f'Requesting time {requested_time}')
	grantedtime = h.helicsFederateRequestTime (fed, requested_time)
	logger.debug(f'Granted time {grantedtime}')
	sub_message = h.helicsInputGetString(subid)
	logger.debug(f'Got subscription message {sub_message}.')
    
	destroy_federate(fed)
	