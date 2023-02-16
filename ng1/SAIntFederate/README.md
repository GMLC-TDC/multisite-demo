# SAInt Gas Federate for the multisite-demo
## To run the SAInt_GasFederate
 - It works with "tcp" protocol. The "zmq" is not working currently.
 - This program needs SAInt 3.2 and above and a .NET environment.
 - Make sure that a reference to *SAInt-Core.dll* is correctly added to the *GasFederate* and *SAIntHelicsLib* projects. The default path is: *C:\Program Files\encoord\SAInt x.xx\SAInt-Core.dll*. 
 - Run the broker locally/remotely.
 - Run the c# *GasFederate* project (GasFederate.cs) which is located inside the GasFederate folder in x64 platform. Make sure that a reference to SAInt-Core.dll is properly added to this project.
 - If you want to see the log messages in the console, run the *GasFederate* in Debug mode. If you want to save the logs into a text file, run the *GasFederate* in Release mode. 
 - Results will be stored in the *..Networks\Demo\Output* folder.