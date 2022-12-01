import helics as h
class Player:
    def __init__(self, input_file, broker_ip = '0.0.0', broker_port = 23404):
        with open(input_file) as f:
            self.data = f.read().splitlines()
        fedinfo = h.helicsCreateFederateInfo()
        if not broker_ip == '0.0.0':
            fed_init_str = f"--federates=1 --timeout=60min --broker_address {broker_ip} --port {broker_port}"
            h.helicsFederateInfoSetCoreName(fedinfo, 'Player')
            h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq_ss")
            h.helicsFederateInfoSetCoreInitString(fedinfo, fed_init_str)
        h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, 0.01)
        h.helicsFederateInfoSetIntegerProperty(fedinfo, h.helics_property_int_log_level, 7)
        self.federate = h.helicsCreateCombinationFederate("Player", fedinfo)
        for line in self.data:
            if line.startswith("#"):
                continue
            try:
                time, type, tag, value = line.split() #time, tag, value, type = line.split()
                self.federate.register_global_publication(tag, type)
            except:
                try:
                    time, tag, value = line.split()
                    self.federate.register_global_publication(tag, h.helics_data_type_string)
                    print(f'publication {tag} registered')
                except:
                    print('no further publications registered')
                    break
        #self.federate.enter_executing_mode()
        h.helicsFederateEnterExecutingMode(self.federate)
        print('player entered executing mode')

    def run(self):
        for line in self.data:
            if line.startswith("#"):
                continue
            try:
                time, tag, value, type = line.split()
            except:
                try:
                    time, tag, value = line.split()
                except:
                    continue
            time = float(time)
            if time<=0:
                time=0.01
            print(f'requesting time {time} with federate time {self.federate.current_time}')
            while self.federate.current_time < time:
                self.federate.request_time(time)
            self.federate.publications[tag].publish(value)
            print(f'publishing {tag} with {value}')
            
if __name__ == "__main__":
    import sys
    input_file = sys.argv[1]
    broker_ip = sys.argv[2]
    player_fed = Player(input_file, broker_ip)
    player_fed.run()
