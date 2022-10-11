function helicsStartup(libraryName, headerName)
% function to load the helics library prior to execution
if (nargin==0)
	cpath=fileparts(mfilename('fullpath'));
	libraryName='helics.dll';
end

if (nargin<2)
	headerName=fullfile(cpath,'include','helics_minimal.h');
end

if (~isempty(libraryName))
	if ~libisloaded('libHelics')
		loadlibrary(libraryName,headerName);
	end
else
	disp('Unable to find library for HELICS')
end
