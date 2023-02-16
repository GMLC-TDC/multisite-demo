using System;
using h = helics;
using SAIntHelicsLib;
namespace SAInt_GasFederate
{
    class SAIntDummy
    {

        static void Main(string[] args)
        {

            // Get HELICS version
            Console.WriteLine($"Gas: HELICS version ={h.helicsGetVersion()}");

            // Create value federate
            Console.WriteLine("Gas: Creating Value Federate");
            //SWIGTYPE_p_void vfed = h.helicsCreateValueFederate("Gas Federate", fedinfo);
            SWIGTYPE_p_void vfed = h.helicsCreateCombinationFederateFromConfig(@"..\..\..\..\GasFederate\SAInt_ng1_Config.json");
            Console.WriteLine("Gas: Value federate created");
            // Set one second message interval
            double period = 1;
            Console.WriteLine("Gas: Setting Federate Timing");
            h.helicsFederateSetTimeProperty(vfed, (int)HelicsProperties.HELICS_PROPERTY_TIME_PERIOD, period);

            // check to make sure setting the time property worked
            double update_interval = h.helicsFederateGetTimeProperty(vfed, (int)HelicsProperties.HELICS_PROPERTY_TIME_PERIOD);
            Console.WriteLine($"Gas: Time period: {update_interval}");

            // set number of HELICS time steps based on scenario
            double total_time = 100;
            Console.WriteLine($"Gas: Number of time steps in the scenario: {total_time}");

            // set max iteration at 20
            h.helicsFederateSetIntegerProperty(vfed, (int)HelicsProperties.HELICS_PROPERTY_INT_MAX_ITERATIONS, 20);
            int Iter_max = h.helicsFederateGetIntegerProperty(vfed, (int)HelicsProperties.HELICS_PROPERTY_INT_MAX_ITERATIONS);
            Console.WriteLine($"Gas: Max iterations per time step: {Iter_max}");

            // corresponds to transmission node 6
            SWIGTYPE_p_void AvailableActivePowerN06 = h.helicsFederateRegisterGlobalTypePublication(vfed, "ng1/node.6.avail", "double", "MW");
            SWIGTYPE_p_void RequieredActivePowerN06 = h.helicsFederateRegisterSubscription(vfed, "transmission/node.6.requested", "MW");

            // corresponds to transmission node 8
            SWIGTYPE_p_void AvailableActivePowerN08 = h.helicsFederateRegisterGlobalTypePublication(vfed, "ng1/node.8.avail", "double", "MW");
            SWIGTYPE_p_void RequieredActivePowerN08 = h.helicsFederateRegisterSubscription(vfed, "transmission/node.8.requested", "MW");


            // Switch to release mode to enable console output to file
#if !DEBUG
            // redirect console output to log file
            FileStream ostrm;
            StreamWriter writer;
            TextWriter oldOut = Console.Out;
            ostrm = new FileStream(OutputFolder + "Log_gas_federate.txt", FileMode.OpenOrCreate, FileAccess.Write);
            writer = new StreamWriter(ostrm);
            Console.SetOut(writer);
#endif
            double granted_time = 0;
            double requested_time = 0;

            // start initialization mode
            h.helicsFederateEnterInitializingMode(vfed);
            Console.WriteLine("\nGas: Entering Initialization Mode");
            Console.WriteLine("======================================================\n");
            h.helicsPublicationPublishDouble(AvailableActivePowerN06, 0);
            Console.WriteLine(String.Format("Gas-S: Time {0}\t N06\t ActivePower = {1} [MW]\t ThermalPower = {2} [MW]", 0, 0, 0));
            h.helicsPublicationPublishDouble(AvailableActivePowerN08, 0);
            Console.WriteLine(String.Format("Gas-S: Time {0}\t N08\t ActivePower = {1} [MW]\t ThermalPower = {2} [MW]", 0, 0, 0));

            Console.WriteLine("\nGas:Entering Execution Mode\n");
            h.helicsFederateEnterExecutingMode(vfed);

            // Heat rate coefficients
            double HR0 = 20;           // MJ/kWh
            double HR1 = -0.075;       // (MJ/kWh)/MW 
            double HR2 = 0.001;        // (MJ/kWh)/(MW*MW)
            double GetHR(double x) => HR0 + HR1 * x + HR2 * x * x;

            double GCV = 39;            // MJ/m^3

            double QMAX = 1000;        // m^3/s
            double QMIN = 0;       // m^3/s

            double CheckQLimit(double QSET)
            {
                double Q;
                if (QSET > QMAX) Q = QMAX;
                else if (QSET < QMIN) Q = QMIN;
                else Q = QSET;
                return Q;
            }

            while (granted_time < total_time)
            {
                // Time request for the next physical interval to be simulated
                requested_time = granted_time + update_interval;
                Console.WriteLine($"Requesting time {requested_time}");
                granted_time = h.helicsFederateRequestTime(vfed, requested_time);
                Console.WriteLine($"Granted time {granted_time}");

                //############ Subscription from Transmission Nodes 6 and 8 ############
                // Get the power output of node 6 in MW
                double ActivePowerRequested_Node6_MW = h.helicsInputGetDouble(RequieredActivePowerN06);

                double RequiredThermalPowerN06 = GetHR(ActivePowerRequested_Node6_MW) * ActivePowerRequested_Node6_MW / 3.6;

                Console.WriteLine(String.Format("Gas-R: Time {0}\t N06\t ActivePowerRequested = {1:0.000} [MW]\t ThermalPowerRequested = {2:0.000} [MW]", requested_time, ActivePowerRequested_Node6_MW, RequiredThermalPowerN06));

                // Get the power output of node 8 in MW
                double ActivePowerRequested_Node8_MW = h.helicsInputGetDouble(RequieredActivePowerN08);

                double RequiredThermalPowerN08 = GetHR(ActivePowerRequested_Node8_MW) * ActivePowerRequested_Node8_MW / 3.6;

                Console.WriteLine(String.Format("Gas-R: Time {0}\t N08\t ActivePowerRequested = {1:0.000} [MW]\t ThermalPowerRequested = {2:0.000} [MW]", requested_time, ActivePowerRequested_Node6_MW, RequiredThermalPowerN08));

                //############ Publication for Transmission Node 6 ################

                // Calculate the gas off take for Node 6 and check the limit
                double QSET_Node6 = RequiredThermalPowerN06 / GCV;
                Console.WriteLine($"QSET requested from transmission Node 6 (m^3/s): {QSET_Node6}");
                // Check for QSET limits
                QSET_Node6 = CheckQLimit(QSET_Node6);
                Console.WriteLine($"QSET available for transmission Node 6 (m^3/s): {QSET_Node6}");
                double Pthermal_Node6_MW = GCV * QSET_Node6;

                double P_Node6_MW_new = MappingFactory.GetActivePowerFromAvailableThermalPower(Pthermal_Node6_MW, ActivePowerRequested_Node6_MW);

                // Publish available active power in MW
                h.helicsPublicationPublishDouble(AvailableActivePowerN06, P_Node6_MW_new);
                Console.WriteLine(String.Format("Gas-S: Time {0}\t N06\t ActivePower = {1} [MW]\t ThermalPower = {2} [MW]", granted_time, P_Node6_MW_new, Pthermal_Node6_MW));

                //############ Publication for Transmission Node 6 ################

                // Calculate the gas off take for Node 6 and check the limit
                double QSET_Node8 = RequiredThermalPowerN08 / GCV;
                Console.WriteLine($"QSET requested from transmission Node 8 (m^3/s): {QSET_Node8}");
                // Check for QSET limits
                QSET_Node8 = CheckQLimit(QSET_Node8);
                Console.WriteLine($"QSET available for transmission Node 8 (m^3/s): {QSET_Node8}");
                double Pthermal_Node8_MW = GCV * QSET_Node8;

                double P_Node8_MW_new = MappingFactory.GetActivePowerFromAvailableThermalPower(Pthermal_Node8_MW, ActivePowerRequested_Node8_MW);

                // Publish available active power in MW
                h.helicsPublicationPublishDouble(AvailableActivePowerN08, P_Node8_MW_new);
                Console.WriteLine(String.Format("Gas-S: Time {0}\t N08\t ActivePower = {1} [MW]\t ThermalPower = {2} [MW]", granted_time, P_Node8_MW_new, Pthermal_Node8_MW));
            }

            h.helicsFederateRequestTime(vfed, total_time + 1);
            h.helicsFederateFinalize(vfed);
            Console.WriteLine("Gas: Federate finalized");
            h.helicsFederateFree(vfed);
        }
    }
}