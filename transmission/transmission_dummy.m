% Author: Orestis Vasios (orestis.vasios@pnnl.gov)
% Work in progress.
% Last edit: 10/07/2022

clear all
clc

%% Check if MATLAB or OCTAVE
isOctave = exist('OCTAVE_VERSION', 'builtin') ~= 0;

%% Load Model
wrapper_startup_orestis;