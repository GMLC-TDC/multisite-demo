% Author: Orestis Vasios (orestis.vasios@pnnl.gov)
% Work in progress.
% Last edit: 10/12/2022

clear all
clc

%% Check if MATLAB or OCTAVE.
isOctave = exist('OCTAVE_VERSION', 'builtin') ~= 0;

%% Load Model
% FIXME: Each user must use an appropriate file below that
% contains appropriate paths to matHELICS and any other
% necessary utility.
wrapper_startup_orestis;
Wrapper = MATPOWERWrapper('matpowerwrapper_config.json', isOctave);

%% Read profile and save it within a strcuture called load
% FIXME: The line below should be uncommented once we decide on a load
% profile.
%Wrapper = Wrapper.read_profiles('load_profile_info', 'load_profile');

if Wrapper.config_data.include_helics
    if isOctave
        helics;
    else
        import helics.*
    end
    
    Wrapper = Wrapper.read_profiles('load_profile_info', 'load_profile');
end

tnext_physics_powerflow = Wrapper.config_data.physics_powerflow.interval;
tnext_real_time_market = Wrapper.config_data.real_time_market.interval;
tnext_day_ahead_market = Wrapper.config_data.day_ahead_market.interval;

time_granted = 0;
next_helics_time =  min([tnext_physics_powerflow, tnext_real_time_market, tnext_day_ahead_market]);

price_range = [10, 30];
flexiblity = 0.2;

while time_granted <= Wrapper.duration
    next_helics_time =  min([tnext_physics_powerflow, tnext_real_time_market, tnext_day_ahead_market]);
    
    if Wrapper.config_data.include_helics
        time_granted  = helicsFederateRequestTime(Wrapper.helics_data.fed, next_helics_time);
        fprintf('Wrapper: Requested  %ds in time and got Granted %d\n', next_helics_time, time_granted)
    else
        time_granted = next_helics_time;
    end
end