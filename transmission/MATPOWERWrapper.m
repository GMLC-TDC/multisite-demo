classdef MATPOWERWrapper
    
   properties
      config_data
      start_time
      end_time
      duration
      MATPOWERModifier
      mpc
      RT_bids =  cell(0)
      RT_allocations =  cell(0)
      octave
      helics_data = struct()
      profiles = struct();
      results =  struct('PF', 1,'RTM', {},'DAM', {});
      
   end
   
   methods
       %% Intializing the Wrapper %% 
       %{
        Inputs: 1.  config_file : Configuration file in JSON format 
        Inputs: 2.  isOctave : Flag to trigger between Octave and MATLAB
        Oututs: 1.  Instantiated Wrapper Object
        %}
       
       function obj = MATPOWERWrapper(config_file, isOctave)
           if isOctave == 1
             pkg load json ;
           end
           obj.config_data = read_json(config_file);
           obj.start_time  = datenum(obj.config_data.start_time, 'yyyy-mm-dd HH:MM:SS');
           obj.end_time    = datenum(obj.config_data.end_time, 'yyyy-mm-dd HH:MM:SS');
           obj.duration = (obj.end_time - obj.start_time)*24*3600;
           case_name = strcat(obj.config_data.matpower_most_data.datapath, obj.config_data.matpower_most_data.case_name);
           obj.MATPOWERModifier = MATPOWERModifier(case_name);
           obj.mpc = obj.MATPOWERModifier.MATPOWERModel;
           obj.results(1).PF =  struct('VM',{}, 'VA', {});
           obj.results(1).RTM =  struct('PG',{} , 'PD', {}, 'LMP', {});
           obj.octave = isOctave; 
           
           if obj.config_data.include_physics_powerflow
               obj.RT_bids =  cell(length(obj.mpc.bus(:,3)),1);
               obj.RT_allocations =  cell(length(obj.mpc.bus(:,3)),1);
           end
           
       end
       
       %% Loading and Storing profiles in the Wrapper Clasess%% 
       function obj = read_profiles(obj, input_fieldname, output_fieldname)
           
           profile_info = obj.config_data.matpower_most_data.(input_fieldname);
           data_path = obj.config_data.matpower_most_data.datapath; 
           input_file_name = strcat(data_path, profile_info.filename);  
           input_resolution = profile_info.resolution;
           input_data_reference_time = datenum(profile_info.starting_time, 'yyyy-mm-dd HH:MM:SS');
           required_resolution = obj.config_data.physics_powerflow.interval;
           
           %{ 
           Calculating Start & End points to load only the profile data required for Simulation.
           This will help reduce the memory by not having to store a year worth of data.  
           %}
           start_data_point = (obj.start_time - input_data_reference_time)*3600*24/input_resolution;
           end_data_point   = (obj.end_time - input_data_reference_time)*3600*24 /input_resolution;
           start_column = min(profile_info.data_map.columns)-1;
           end_column = max(profile_info.data_map.columns)-1;
           %{ 
            Loadind data based on the simulation duration.  
            Assumption:
            
                The profiles are provided in csv.
                The simulation duration is a subset of the duration of the data.  
                If else, The user is expected to adjust the start/end dates or the profile. 
           %}
           data  = dlmread(input_file_name, ',', [start_data_point+1, 0, end_data_point+1, end_column]);    
           for idx = 1: length(profile_info.data_map.columns)
               data_idx = profile_info.data_map.columns(idx);
               %fprintf('Loading %s for bus/gen %d from input column \n', output_fieldname, data_idx);
               [profiles(:,data_idx), profile_intervals] = interpolate_profile_to_powerflow_interval(data(:,data_idx), input_resolution, required_resolution, obj.duration);
           end
           profiles(:,1) = profile_intervals;
           obj.profiles.(output_fieldname) = profiles;
       end 
        
       %% Updating current Load from profiles in the Wrapper Clasess%% 
       function obj = update_loads_from_profiles(obj, time, profile_info_fieldname, profile_fieldname)
         
           profile = obj.profiles.(profile_fieldname);
           profile_row = find(time==profile(:,1));
           
           profile_info = obj.config_data.matpower_most_data.(profile_info_fieldname);
           profile_info_col_idx = profile_info.data_map.columns;
           profile_info_bus_idx = profile_info.data_map.bus;

           kW_kVAR_ratio = obj.mpc.bus(:,3)./ obj.mpc.bus(:,4);
           obj.mpc.bus(profile_info_bus_idx, 3) = profile(profile_row, profile_info_col_idx)';
           obj.mpc.bus(profile_info_bus_idx, 4) = obj.mpc.bus(profile_info_bus_idx, 3) ./ kW_kVAR_ratio; 
    
       end
       
       %% Updating VRE Generators from profiles in the Wrapper Clasess%% 
       function obj = update_VRE_from_profiles(obj, time, profile_info_fieldname, profile_fieldname)
         
           profile = obj.profiles.(profile_fieldname);
           profile_row = find(time == profile(:,1));
           
           profile_info = obj.config_data.matpower_most_data.(profile_info_fieldname);
           profile_info_col_idx = profile_info.data_map.columns;
           profile_info_gen_idx = profile_info.data_map.gen;

           obj.mpc.gen(profile_info_gen_idx, 9) = profile(profile_row, profile_info_col_idx)';   
    
       end
       
       %% Temporary testing functions for bidding%% 
       function [P_Q] = get_bids_from_cosimulation(obj, time, flexibility, price_range)
            
            %%   Get Flex and Inflex loads   %%
            cosim_buses = obj.config_data.cosimulation_bus;
            P_Q = struct;
            for i = 1:length(cosim_buses)
                cosim_bus = cosim_buses(i);
                profile = obj.profiles.('load_profile');
                profile_row = find(time==profile(:,1));
                load_data = profile(profile_row, cosim_bus+1);
                constant_load = load_data*(1-flexibility); 
                flex_load = load_data*(flexibility); 
                Q_values = [0 flex_load];
                P_values = [max(price_range) min(price_range)];
                LMPvsQ = polyfit(Q_values,P_values,1);
                Q = linspace(0, flex_load, 10);
                P = polyval(LMPvsQ, Q);
                Rel_Cost = 1*P.*(Q); 
                for i = 1:length(Rel_Cost)
                    Actual_cost(i) = sum(Rel_Cost(1:i));
                end    
                P_Q(cosim_bus).bid = polyfit(Q,Actual_cost,2);
                P_Q(cosim_bus).range = [0,flex_load];
                P_Q(cosim_bus).constant_load = constant_load;
            end
            
            %%   Plotting PQ Bids   %%
%             Q = linspace(constant_load, constant_load+flex_load, 10);
%             P = polyval(P_Q(cosim_bus).bid, Q);
%             plot([0, constant_load, Q],[max(price_range), max(price_range), P]);
            
       end
        
       %% Running PF to emulate System States %% 
       function obj = run_power_flow(obj, time)       

           mpoptPF = mpoption('verbose', 0, 'out.all', 0, 'pf.nr.max_it', 20, 'pf.enforce_q_lims', 0, 'model', obj.config_data.physics_powerflow.type);

           solution = runpf(obj.mpc, mpoptPF);  
           obj.mpc.bus(:,8:9) = solution.bus(:, 8:9);
           obj.mpc.gen(:,2:3) = solution.gen(:, 2:3);
           
           if isempty(obj.results.PF)
               obj.results.PF(1).VM = [time solution.bus(:, 8)'];
           else
               obj.results.PF.VM = [obj.results.PF.VM; time solution.bus(:, 8)'];
           end       
       end
       
       %% Running OPF to emulate Real Time Market %% 
       function obj = run_RT_market(obj, time)  
         
           mpoptOPF = mpoption('verbose', 0, 'out.all', 0, 'model', obj.config_data.real_time_market.type);
           solution = rundcopf(obj.mpc, mpoptOPF); 
           obj.mpc.gen(:,2:3) = solution.gen(:, 2:3);
           obj.mpc.bus(:,8:17) = solution.bus(:, 8:17);
           if solution.success == 1
               if isempty(obj.results.RTM)
                   obj.results.RTM(1).PG  = [time solution.gen(:, 2)'];
                   obj.results.RTM(1).PD  = [time solution.bus(:, 3)'];
                   obj.results.RTM(1).LMP = [time solution.bus(:, 14)'];
               else
                   obj.results.RTM.PG  = [obj.results.RTM.PG;  time solution.gen(:, 2)'];
                   obj.results.RTM.PD  = [obj.results.RTM.PD;  time solution.bus(:, 3)'];
                   obj.results.RTM.LMP = [obj.results.RTM.LMP; time solution.bus(:, 14)'];
               end  
           else
               fprintf('Wrapper: OPF failed to converged at %d, retrying', time/3600);
               %% Increasing the branch flow %%
               obj.mpc.branch(:,6:8) = obj.mpc.branch(:,6:8)*1.2;
               solution = rundcopf(obj.mpc, mpoptOPF); 
               obj.mpc.gen(:,2:3) = solution.gen(:, 2:3);
               obj.mpc.bus(:,8:17) = solution.bus(:, 8:17);
               obj.results.RTM.PG  = [obj.results.RTM.PG;  time solution.gen(:, 2)'];
               obj.results.RTM.PD  = [obj.results.RTM.PD;  time solution.bus(:, 3)'];
               obj.results.RTM.LMP = [obj.results.RTM.LMP; time solution.bus(:, 14)'];
               
           end
               
       end
       
       %% Preparing HELICS configuration %%
       function obj = prepare_helics_config(obj, config_file_name, SubSim)

           obj.config_data.helics_config.coreInit = "--federates=1";
           obj.config_data.helics_config.coreName = "Transmission Federate";
           obj.config_data.helics_config.publications = [];
           obj.config_data.helics_config.subscriptions = [];

            for i = 1:length(obj.config_data.cosimulation_bus)
                cosim_bus = obj.config_data.cosimulation_bus(i);
                %%%%%%%%%%%%%%%%% Creating Pubs & Subs for physics_powerflow %%%%%%%%%%%%%%%%%
                if obj.config_data.include_physics_powerflow
                    publication.key =   strcat (obj.config_data.helics_config.name, '.pcc.', mat2str(cosim_bus), '.pnv');
                    publication.type =   "complex";
                    publication.global =   true;
                    obj.config_data.helics_config.publications = [obj.config_data.helics_config.publications publication];

                    subscription.key =   strcat (SubSim, '.pcc.', mat2str(cosim_bus), '.pq');
                    subscription.type =   "complex";
                    subscription.required =   true;
                    obj.config_data.helics_config.subscriptions = [obj.config_data.helics_config.subscriptions subscription];
                end
                %%%%%%%%%%%%%%%%% Creating Pubs & Subs for real time market %%%%%%%%%%%%%%%%%%    
                if obj.config_data.include_real_time_market
                    publication.key =   strcat (obj.config_data.helics_config.name, '.pcc.', mat2str(cosim_bus), '.rt_energy.cleared');
                    publication.type =   "JSON";
                    publication.global =   true;
                    obj.config_data.helics_config.publications = [obj.config_data.helics_config.publications publication];  

                    subscription.key =   strcat (SubSim, '.pcc.', mat2str(cosim_bus), '.rt_energy.bid');
                    subscription.type =   "JSON";
                    subscription.required =   true;
                    obj.config_data.helics_config.subscriptions = [obj.config_data.helics_config.subscriptions subscription];
                end
                %%%%%%%%%%%%%%%%% Creating Pubs & Subs for day ahead market %%%%%%%%%%%%%%%%%% 
                if obj.config_data.include_day_ahead_market
                    publication.key =   strcat (obj.config_data.helics_config.name, '.pcc.', mat2str(cosim_bus), '.da_energy.cleared');
                    publication.type =   "JSON";
                    publication.global =   true;
                    obj.config_data.helics_config.publications = [obj.config_data.helics_config.publications publication];

                    subscription.key =   strcat (SubSim, '.pcc', mat2str(cosim_bus), '.da_energy.bid');
                    subscription.type =   "JSON";
                    subscription.required =   true;
                    obj.config_data.helics_config.subscriptions = [obj.config_data.helics_config.subscriptions subscription];
                end
            end
            write_json(config_file_name, obj.config_data.helics_config);
       end
       
       %% Initializing Federate for HELICS-based Co-simulation %%
       function obj = start_helics_federate(obj, config_file_name)
           
           %% Importing the HELICS Libraries %%
           if obj.octave
               helics; 
           else
               import helics.*
           end
           
           %% Initializing HELICS Federate %%
           fprintf('Wrapper: Helics version = %s\n', helicsGetVersion)
           fed = helicsCreateCombinationFederateFromConfig(config_file_name);
           obj.helics_data.('fed') = fed;
           
           pubkeys_count = helicsFederateGetPublicationCount(fed);
           pub_keys = cell(pubkeys_count, 1);
           for pub_idx = 1:pubkeys_count
               pub_object = helicsFederateGetPublicationByIndex(fed, pub_idx-1);
               pub_keys(pub_idx) = cellstr(helicsPublicationGetName(pub_object));
           end
           obj.helics_data.('pub_keys')  = pub_keys;
           fprintf('Wrapper: Registered %d HELICS publications \n', pubkeys_count);
           subkeys_count = helicsFederateGetInputCount(fed);
           sub_keys = cell(subkeys_count, 1);
           for sub_idx = 1:subkeys_count
               sub_object = helicsFederateGetInputByIndex(fed, sub_idx-1);
               sub_keys(sub_idx) = cellstr(helicsSubscriptionGetTarget(sub_object));
           end
           obj.helics_data.('sub_keys')  = sub_keys;
           fprintf('Wrapper: Registered %d HELICS subscriptions \n', subkeys_count);
           helicsFederateEnterExecutingMode(fed);
           
       end
       
       %% Updating loads from Cosimulation 
       function obj = get_loads_from_helics(obj)
    
           %% Importing the HELICS Libraries %%
           if obj.octave
               helics; 
           else
               import helics.*
           end
           
           for bus_idx= 1 : length(obj.config_data.cosimulation_bus)
               cosim_bus = obj.config_data.cosimulation_bus(bus_idx);
               temp = strfind(obj.helics_data.sub_keys, strcat('.pcc.', mat2str(cosim_bus), '.pq'));
               subkey_idx = find(~cellfun(@isempty,temp));
               sub_object = helicsFederateGetSubscription(obj.helics_data.fed, obj.helics_data.sub_keys{subkey_idx});
               demand = helicsInputGetComplex(sub_object);
               fprintf('Wrapper: Got Load %d+%d from Cosim bus %d\n', real(demand), imag(demand), cosim_bus);
                
               obj.mpc.bus(cosim_bus, 3) = real(demand);
               obj.mpc.bus(cosim_bus, 4) = imag(demand);
           end 
    
       end
       
       %% Send updated Voltages to Cosimulation
       function obj = send_voltages_to_helics(obj)
           %% Importing the HELICS Libraries %%
           if obj.octave
               helics; 
           else
               import helics.*
           end
           
           for bus_idx= 1 : length(obj.config_data.cosimulation_bus)
               cosim_bus = obj.config_data.cosimulation_bus(bus_idx);
               cosim_bus_voltage = obj.mpc.bus(cosim_bus, 8) * obj.mpc.bus(cosim_bus, 10);
               cosim_bus_angle = obj.mpc.bus(cosim_bus, 9)*pi/180;
               [voltage_real, voltage_imag] = pol2cart(cosim_bus_angle, cosim_bus_voltage);
                
               temp = strfind(obj.helics_data.pub_keys, strcat('.pcc.', mat2str(cosim_bus), '.pnv'));
               pubkey_idx = find(~cellfun(@isempty,temp));
               pub_object = helicsFederateGetPublication(obj.helics_data.fed, obj.helics_data.pub_keys{pubkey_idx});
               helicsPublicationPublishComplex(pub_object, complex(voltage_real, voltage_imag));
               fprintf('Wrapper: Sending Voltages %d+%d to Cosim bus %d\n', voltage_real, voltage_imag, cosim_bus);
           end
       end
            
       %% Get Bids from Cosimulation
       function obj = get_bids_from_helics(obj)
           %% Importing the HELICS Libraries %%
           if obj.octave
               helics; 
           else
               import helics.*
           end
           
           for bus_idx= 1 : length(obj.config_data.cosimulation_bus)
               cosim_bus = obj.config_data.cosimulation_bus(bus_idx);
               temp = strfind(obj.helics_data.sub_keys, strcat('.pcc.', mat2str(cosim_bus), '.rt_energy.bid'));
               subkey_idx = find(~cellfun(@isempty,temp));
               sub_object = helicsFederateGetSubscription(obj.helics_data.fed, obj.helics_data.sub_keys{subkey_idx});
               raw_bid = helicsInputGetString(sub_object);
               
               DSO_bid = jsondecode(raw_bid);
               fprintf('Wrapper: Got bids from Cosim bus %d\n', cosim_bus);
               obj.RT_bids{cosim_bus} = DSO_bid;
           end
       end
       
        %% Send Allocations to Cosimulation 
       function obj = send_allocations_to_helics(obj)
           %% Importing the HELICS Libraries %%
           if obj.octave
               helics; 
           else
               import helics.*
           end
           
           for bus_idx= 1 : length(obj.config_data.cosimulation_bus)
               cosim_bus = obj.config_data.cosimulation_bus(bus_idx);
               temp = strfind(obj.helics_data.pub_keys, strcat('.pcc.', mat2str(cosim_bus), '.rt_energy.cleared'));
               pubkey_idx = find(~cellfun(@isempty,temp));
               pub_object = helicsFederateGetPublication(obj.helics_data.fed, obj.helics_data.pub_keys{pubkey_idx});
                
               raw_allocation = jsonencode (obj.RT_allocations{cosim_bus});
               helicsPublicationPublishString(pub_object, raw_allocation);
               fprintf('Wrapper: Send Cleared Values to Cosim bus %d\n', cosim_bus);
            end    
       end
       
   end

end   

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%% Interpolate Input Profile  %%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Utility Functions %%
function [required_profile, required_intervals] = interpolate_profile_to_powerflow_interval(input_data, input_data_resolution, required_resolution, duration)
  
            raw_data_duration  = (length(input_data)-1)*input_data_resolution;
            raw_data_intervals = linspace(0, raw_data_duration, (raw_data_duration/input_data_resolution)+1)';
            required_intervals = linspace(0, duration, (duration/required_resolution)+1)';
            if raw_data_intervals(1) <= required_intervals(1) && raw_data_intervals(end) >= required_intervals(end)
                interpolated_data = interp1 (raw_data_intervals, input_data, required_intervals, "spline");
                %%    required_profile = [required_intervals interpolated_data];
                required_profile = interpolated_data;
                %fprintf('Interpolating input profile for simulation intervals \n');  
            else
                %fprintf('Simulation intervals is out of interpolation range for the input profile');  
                %%    required_profile = [raw_data_intervals input_data];
                required_profile = input_data;
            end
end
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%% Read Json Configuration %%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
function val = read_json(file)
           fid = fopen(file); 
           raw = fread(fid,inf); 
           str = char(raw'); 
           fclose(fid); 
           val = jsondecode(str);
end 
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%% Write Json Configuration %%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
function write_json(file, data)
    str = jsonencode (data);
    fid = fopen(file, 'w'); 
    fwrite(fid, str);
    fclose(fid); 
end