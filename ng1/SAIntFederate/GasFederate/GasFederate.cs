using System;
using System.IO;
using System.Collections.Generic;
using h = helics;
using SAInt_API;
using SAIntHelicsLib;
using SAInt_API.Library;
using SAInt_API.Library.Units;
using SAInt_API.Model.Network.Fluid.Gas;
using SAInt_API.Model.Network.Hub;

namespace SAInt_GasFederate
{
    class federate
    {
        static object GetObject(string funcName)
        {
            var func = typeof(API).GetMethod(funcName, System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
            return func.Invoke(null, new object[] { });
        }

        static void Main(string[] args)
        {
            string NetworkSourceFolder = @"..\..\..\..\Networks\Demo\";
            string NetFileName = "GNET25.gnet";
            string SceFileName = "CASE1.gsce";
            string StateFileName = "CMBSTEOPF.gcon";            
            string SolDescFileName = "gsolin.txt";

            string OutputFolder = NetworkSourceFolder + @"\Outputs\ACOPF_DynGas\" + SceFileName + @"\";
            Directory.CreateDirectory(OutputFolder);

            API.openGNET(NetworkSourceFolder + NetFileName);
            API.openGSCE(NetworkSourceFolder + SceFileName);
            API.openGCON(NetworkSourceFolder + StateFileName);

#if !DEBUG
            API.showSIMLOG(true);
#else
            API.showSIMLOG(false);
#endif

            // Get HELICS version
            Console.WriteLine($"Gas: HELICS version ={h.helicsGetVersion()}");
            
            // Create value federate
            Console.WriteLine("Gas: Creating Value Federate");
            //SWIGTYPE_p_void vfed = h.helicsCreateValueFederate("Gas Federate", fedinfo);
            SWIGTYPE_p_void vfed = h.helicsCreateCombinationFederateFromConfig(@"..\..\..\..\GasFederate\SAInt_ng1_Config.json");
            Console.WriteLine("Gas: Value federate created");

            //Identify the gas nodes that are coupled
            List<GasDemand> CoupledGDEMs = new List<GasDemand>();

            Units Unit = new Units(UnitTypeList.Q, UnitList.sm3_s);

            // GDEM.N15 coupled with transmission node.6
            // GDEM.N21 coupled with transmission node.8
            foreach (GasDemand demand in API.GNET.GasDemands)
            {
                if(demand.Name =="N15" || demand.Name == "N21")
                {
                    CoupledGDEMs.Add(demand);   
                }
            }
            // Load the mapping between the gas demands and the gas fired power plants 
            List<ElectricGasMapping> MappedGDEMs = MappingFactory.CoupledGasDemands(CoupledGDEMs, vfed);

            // Set one second message interval
            double period = 1;
            Console.WriteLine("Gas: Setting Federate Timing");
            h.helicsFederateSetTimeProperty(vfed, (int)HelicsProperties.HELICS_PROPERTY_TIME_PERIOD, period);

            // check to make sure setting the time property worked
            double update_interval = h.helicsFederateGetTimeProperty(vfed, (int)HelicsProperties.HELICS_PROPERTY_TIME_PERIOD);
            Console.WriteLine($"Gas: Time period: {update_interval}");

            // set number of HELICS time steps based on scenario
            double total_time = API.GNET.SCE.NN;
            Console.WriteLine($"Gas: Number of time steps in the scenario: {total_time}");

            // set max iteration at 20
            h.helicsFederateSetIntegerProperty(vfed, (int)HelicsProperties.HELICS_PROPERTY_INT_MAX_ITERATIONS, 20);
            int Iter_max = h.helicsFederateGetIntegerProperty(vfed, (int)HelicsProperties.HELICS_PROPERTY_INT_MAX_ITERATIONS);
            Console.WriteLine($"Gas: Max iterations per time step: {Iter_max}");

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
            MappingFactory.PublishAvailableActivePower(0, MappedGDEMs);

            Console.WriteLine("\nGas:Entering Execution Mode\n");
            h.helicsFederateEnterExecutingMode(vfed);

            int FirstTimeStep = 0;
            // this function is called each time the SAInt solver state changes
            Solver.SolverStateChanged += (object sender, SolverStateChangedEventArgs e) =>
            {

                if (e.SolverState == SolverState.BeforeTimeStep && e.TimeStep > 0)
                {  
                    if (FirstTimeStep == 0)
                    {
                        Console.WriteLine("======================================================\n");
                        Console.WriteLine("\nGas: Entering Main Co-simulation Loop");
                        Console.WriteLine("======================================================\n");
                        FirstTimeStep += 1;
                    }

                    requested_time = granted_time + update_interval;

                    //Iterative HELICS time request
                    Console.WriteLine($"\nGas Requested Time: {API.GNET.SCE.dTime[e.TimeStep]}, TimeStep: {e.TimeStep}");
                    granted_time = h.helicsFederateRequestTime(vfed, requested_time);
                    Console.WriteLine($"Gas Granted Co-simulation Time Step: {granted_time}, SolverState: {e.SolverState}");
                    // Subscribe to requested active power generation
                    MappingFactory.SubscribeToRequiredActivePower(e.TimeStep, MappedGDEMs);
                }

                else if (e.SolverState == SolverState.AfterTimeStep && e.TimeStep > 0)
                {
                    MappingFactory.PublishAvailableActivePower(e.TimeStep, MappedGDEMs);
                    Console.WriteLine($"Gas TimeStep: {e.TimeStep}, SolverState: {e.SolverState}");
                    e.RepeatTimeStep = 0;
                }                
            };

            Console.WriteLine("======================================================\n");
            Console.WriteLine("\nGas: Starting the Gas Simulation");
            Console.WriteLine("======================================================\n");
            // run the gas network model
            API.runGSIM();

            // request time for end of time + 1: serves as a blocking call until all federates are complete
            DateTime DateTimeRequested = API.GNET.SCE.EndTime.AddSeconds(API.GNET.SCE.dt);
            Console.WriteLine($"\nGas Requested Time Step: {total_time + 1} at Time: {DateTimeRequested}");
            h.helicsFederateRequestTime(vfed, total_time + 1);

#if !DEBUG
            // close out log file
            Console.SetOut(oldOut);
            writer.Close();
            ostrm.Close();
#endif
            API.writeGSOL(NetworkSourceFolder + SolDescFileName, OutputFolder + "gsolout_HELICS.xlsx");
            
            API.exportGSCE(OutputFolder + "GasScenarioEventsGSCE.xlsx");

            // finalize federate
            h.helicsFederateFinalize(vfed);
            Console.WriteLine("Gas: Federate finalized");
            h.helicsFederateFree(vfed);
            h.helicsCloseLibrary();

            foreach (ElectricGasMapping m in MappedGDEMs)
            {
                if (m.sw != null)
                {
                    m.sw.Flush();
                    m.sw.Close();
                }
            }
            var k = Console.ReadKey();
        }
    }
}