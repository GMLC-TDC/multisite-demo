using System;
using System.Linq;
using System.Collections.Generic;
using System.IO;
using SAInt_API;
using SAInt_API.Library;
using SAInt_API.Library.Units;
using SAInt_API.Model.Network;
using SAInt_API.Model.Network.Hub;
using SAInt_API.Model.Network.Electric;
using SAInt_API.Model.Network.Fluid.Gas;

using SAInt_API.Model;
using SAInt_API.Model.Scenarios;

using h = helics;
using System.Net.Sockets;
using System.Net;

namespace SAIntHelicsLib
{

    public static class MappingFactory
    {        
        public static double eps = 0.001;

         public static void PublishAvailableFuelRate(int HorizonStartingTimeStep, int Iter, List<ElectricGasMapping> MappingList)
        {
            int Horizon = MappingList.First().Horizon;
            int kstep;

            foreach (ElectricGasMapping m in MappingList)
            {
                for (int i = 0; i < Horizon; i++)
                {
                    kstep = i + HorizonStartingTimeStep;
                    DateTime DateTimeStep = m.GFG.GNET.SCE.dTime[kstep];

                    GasNode GNODE = (GasNode)m.GFG.GDEM.NetNode;
                    double Pressure = (GNODE.get_P(kstep)) / 1e5; // in bar
                    double MinPressure = GNODE.get_PMIN(kstep) / 1e5; // in bar

                    double AvailableFuelRate = m.GFG.GDEM.get_Q(kstep); // in sm3/s
                    
                    h.helicsPublicationPublishDouble(m.AvailableFuelRate[i], AvailableFuelRate);

                    h.helicsPublicationPublishDouble(m.PressureRelativeToPmin[i], Pressure - MinPressure);

                    Console.WriteLine(String.Format("Gas-S: Time {0}\t iter {1}\t {2}\t FuelRateAvailable = {3:0.000} [sm3/s]\t QSET = {3:0.000} [sm3/s]\t P {5:0.000} [bar]",
                        DateTimeStep, Iter, m.GFG.GDEM, AvailableFuelRate, m.GFG.GDEM.get_QSET(kstep), Pressure));
                    m.sw.WriteLine(String.Format("{3}\t\t{0}\t\t\t{1}\t\t {2:0.00000} \t {4:0.00000}",
                        kstep, Iter, Pressure, DateTimeStep, AvailableFuelRate));
                }
            }
        }
        
        public static bool SubscribeToRequiredFuelRate(int HorizonStartingTimeStep, int Iter, List<GasDemand> GDEMs, string Init = "Execute")
        {
            int Horizon = GDEMs.First().Horizon;

            bool HasViolations = false;

            Units Unit = new Units(UnitTypeList.Q, UnitList.sm3_s);

            foreach (ElectricGasMapping demand in GDEMs)
            {
                for (int i = 0; i < Horizon; i++)
                {
                    int kstep = HorizonStartingTimeStep + i;
                    DateTime DateTimeStep = demand.GDEM.GNET.SCE.dTime[kstep];// + new TimeSpan(0, 0, gtime * (int)GNET.SCE.dt);
                     

                    if (Init == "Initialization")
                    {
                        if (RequieredFuelRate < 0)
                        {
                            HasViolations = true;
                        }
                        if (HasViolations) return HasViolations;
                        else
                        {
                            Console.WriteLine(String.Format("Gas-R: Initialization Time {0}\t iter {1}\t {2}\t RequieredFuelRate = {3:0.0000} [m3/s]", DateTimeStep, Iter, demand.GFG.GDEM, RequieredFuelRate));
                            continue;
                        }
                    }

                    Console.WriteLine(String.Format("Gas-R: Time {0}\t iter {1}\t {2}\t RequieredFuelRate = {3:0.0000} [m3/s]", DateTimeStep, Iter, demand.GFG.GDEM, RequieredFuelRate));

                    demand.LastVal[i].Add(RequieredFuelRate);
                                   
                    double AvailableFuelRate = demand.GFG.GDEM.get_Q(kstep);

                    if (Math.Abs(AvailableFuelRate - RequieredFuelRate) > eps)
                    {
                        foreach (var evt in demand.GFG.GDEM.SceList.Where(xx => xx.ObjPar == CtrlType.QSET && xx.StartTime == DateTimeStep))
                        {
                            evt.Unit = Unit;
                            evt.ObjVal = RequieredFuelRate;
                            evt.StartTime = DateTimeStep;
                            evt.Processed = false;
                            evt.Active = true;
                            evt.Info = "HELICS";
                        }

                        Console.WriteLine(String.Format("Gas-E: Time {0}\t iter {1}\t {2}\t QSET = {3:0.0000} [sm3/s]",
                            DateTimeStep, Iter, demand.GFG.GDEM, demand.GFG.GDEM.get_QSET(kstep)));

                        HasViolations = true;
                    }
                    else
                    {
                        int Count = demand.LastVal[i].Count;
                        if (Count > 2)
                        {
                            if ((Math.Abs(demand.LastVal[i][Count - 2] - demand.LastVal[i][Count - 1]) > eps) || (Math.Abs(demand.LastVal[i][Count - 3] - demand.LastVal[i][Count - 2]) > eps))
                            {
                                HasViolations = true;
                            }
                        }
                        else
                        {
                            HasViolations = true;
                        }
                    }
                }
            }
            Console.WriteLine($"Gas HasViolations?: {HasViolations}");
            return HasViolations;
        }
    

        public static List<ElectricGasMapping> CoupledGasDemands(IList<GasDemand> GDEMs)
        {
            List<ElectricGasMapping> MappingList = new List<ElectricGasMapping>();

            foreach (GasDemand demand in GDEMs)
            {
                var mapitem = new ElectricGasMapping() { GDEM = demand };

                Units Unit = new Units(UnitTypeList.Q, UnitList.sm3_s);

                // Initialize events for each time step before simulation
                for (int kstep = 0; kstep <= demand.GNET.SCE.NN; kstep++)
                {
                    DateTime DateTimeStep = demand.GNET.SCE.dTime[kstep];

                    bool IsThereQsetEvent = demand.SceList.Any(xx => xx.ObjPar == CtrlType.QSET && xx.StartTime == DateTimeStep);
                    if (!IsThereQsetEvent)
                    {
                        ScenarioEvent QsetEvent = new ScenarioEvent(demand, CtrlType.QSET, demand.get_QSET(kstep), Unit)
                        {
                            Processed = false,
                            StartTime = DateTimeStep,
                            Active = true
                        };
                        demand.GNET.SCE.AddEvent(QsetEvent);
                    }
                }

                MappingList.Add(mapitem);
            }
            return MappingList;
        }
      
    }

  
    public class ElectricGasMapping
    {
        public GasDemand GDEM;
        public SWIGTYPE_p_void RequieredActivePower;
        public SWIGTYPE_p_void AvailableActivePower;

        public StreamWriter sw;
    }

    public class TimeStepInfo
    {
        public int HorizonStep, IterationCount;
        public DateTime time;
    }
}
