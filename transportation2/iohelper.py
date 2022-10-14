import uuid
import json
from collections import OrderedDict, defaultdict

import helics as h


class IOHelper(object):

#=======================================================================================================================
	def create_federate(self,config):
		self.federate=h.helicsCreateValueFederateFromConfig(config)

#=======================================================================================================================
	def enter_execution_mode(self):
		self.federate.enter_executing_mode()

#=======================================================================================================================
	def setup_publications(self,config):
		self.pub=pub={}
		if 'publications' in config:
			for index,item in zip(range(h.helicsFederateGetPublicationCount(self.federate)),config['publications']):
				indexObj=h.helicsFederateGetPublicationByIndex(self.federate,index)
				thisPub=pub[h.helicsPublicationGetKey(indexObj)]={}
				thisPub['indexObj']=indexObj
				if item['type']=='bool':
					thisPub['method']='helicsPublicationPublishBoolean'
				elif item['type']=='double':
					thisPub['method']='helicsPublicationPublishDouble'
				elif item['type']=='string':
					thisPub['method']='helicsPublicationPublishString'

#=======================================================================================================================
	def setup_subscriptions(self,config):
		self.sub=sub={}
		if 'subscriptions' in config:
			for index,item in zip(range(h.helicsFederateGetInputCount(self.federate)),config['subscriptions']):
				indexObj=h.helicsFederateGetInputByIndex(self.federate,index)
				thisSub=sub[h.helicsInputGetKey(indexObj)]={}
				thisSub['indexObj']=indexObj
				thisSub['key']=item['key']
				if item['type']=='bool':
					thisSub['method']='helicsInputGetBoolean'
				elif item['type']=='double':
					thisSub['method']='helicsInputGetDouble'
				elif item['type']=='string':
					thisSub['method']='helicsInputGetString'

#=======================================================================================================================
	def finalize(self):
		h.helicsFederateFree(self.federate)
		h.helicsCloseLibrary()

#=======================================================================================================================
	def start_broker(self,nFeds):
		initstring = "-f {} --name=mainbroker".format(nFeds)
		self.broker = h.helicsCreateBroker("zmq", "", initstring)
		assert h.helicsBrokerIsConnected(self.broker)==1,"broker connection failed"


