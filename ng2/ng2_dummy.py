import os
import json
import argparse
import logging

import helics as h

from iohelper import IOHelper


baseDir=os.path.dirname(os.path.abspath(__file__))
formatterStr='%(asctime)s::%(name)s::%(filename)s::%(funcName)s::'+\
	'%(levelname)s::%(message)s::%(threadName)s::%(process)d'
formatter = logging.Formatter(formatterStr)
fh = logging.FileHandler(os.path.join(baseDir,'logs','ng2.log'),mode='w')
fh.setFormatter(formatter)
fh.setLevel(10)
logger = logging.getLogger('ng2_logger')
logger.setLevel(10)
logger.addHandler(fh)


class NGFederate(IOHelper):

	def __init__(self,config):
		self.config=config
		self.dt=self.config['period']

#=======================================================================================================================
	def initialize(self,config=None):
		if not config:
			config=self.config
		self.create_federate(json.dumps(config))
		self.setup_publications(config)
		self.setup_subscriptions(config)
		logger.info('completed init')

#=======================================================================================================================
	def simulate(self,simEndTime=24):
		self.enter_execution_mode()
		logger.info('entered execution mode')

		grantedTime=0
		while grantedTime<simEndTime:
			# sub
			for entry in self.sub:
				if h.helicsInputIsUpdated(self.sub[entry]['indexObj']):
					val=h.__dict__[self.sub[entry]['method']](self.sub[entry]['indexObj'])

			# run
			pubData={self.config['name']+'/'+entry['key']:1 for entry in self.config['publications']}

			# publish
			for entry in self.pub:
				h.__dict__[self.pub[entry]['method']](self.pub[entry]['indexObj'],pubData[entry])

			grantedTime=h.helicsFederateRequestTime(self.federate,grantedTime+self.dt)
			logger.info(f'grantedTime::::{grantedTime}')

#=======================================================================================================================
if __name__=='__main__':
	"""Sample call: python3 ng2_dummy.py --standalone 1 --end_time 3600"""
	parser=argparse.ArgumentParser()
	parser.add_argument('-b','--start_broker',help='start broker',default=False)
	parser.add_argument('-s','--standalone',help='standalone test',default=False)
	parser.add_argument('-e','--end_time',help='simulation end time',default=86400,type=int)
	args=parser.parse_args()

	if args.standalone:
		args.start_broker=True
		baseDir=os.path.dirname(os.path.abspath(__file__))
		config=json.load(open(os.path.join(baseDir,'config_standalone.json')))
	else:
		baseDir=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		mainConfig=json.load(open(os.path.join(baseDir,'multi_site_config.json')))
		for entry in mainConfig:
			if entry['name']=='ng2':
				config=entry

	thisFed=NGFederate(config)
	if args.start_broker:
		thisFed.start_broker(1)
	thisFed.initialize()
	thisFed.simulate(simEndTime=args.end_time)
	thisFed.finalize()


