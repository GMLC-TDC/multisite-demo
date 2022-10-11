% Author: Orestis Vasios (orestis.vasios@pnnl.gov)
% Work in progress.
% Last edit: 10/07/2022

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