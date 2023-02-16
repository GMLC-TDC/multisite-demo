using System;
using System.Linq;
using System.Collections.Generic;
using System.IO;
using SAInt_API.Library.Units;
using SAInt_API.Model.Network.Fluid.Gas;
using SAInt_API.Model;
using SAInt_API.Model.Scenarios;

using h = helics;

namespace SAIntHelicsLib
{

    public static class MappingFactory
    { 
        static double HR0 = 20;           // MJ/kWh
        static double HR1 = -0.075;       // (MJ/kWh)/MW 
        static double HR2 = 0.001;        // (MJ/kWh)/(MW*MW)
        static double GetHR(double x) => HR0 + HR1 * x + HR2 * x * x;
        static double GetdF_by_dx(double x) => -(HR0 + 2 * HR1 * x + 3 * HR2 * x * x);

        public static void PublishAvailableActivePower(int kstep, List<ElectricGasMapping> MappingList)
        {
            foreach (ElectricGasMapping m in MappingList)
            {
                GasNode GNODE = (GasNode)m.GDEM.NetNode;
                double Pressure = (GNODE.get_P(kstep)) / 1e5; // in bar
                double MinPressure = GNODE.get_PMIN(kstep) / 1e5; // in bar
                double GCV = GNODE.get_NQ(kstep).GCV / 1e6; // in MJ/m3    

                double GasOfftake = m.GDEM.get_Q(kstep);
                double ThermalPower = GasOfftake * GCV;
                double ActivePower = GetActivePowerFromAvailableThermalPower(ThermalPower, ThermalPower / 0.3); // rough approximation efficiency = 0.3

                h.helicsPublicationPublishDouble(m.AvailableActivePower, ActivePower);

                Console.WriteLine(String.Format("Gas-S: Time {0}\t {1}\t ActivePower = {2:0.000} [MW]\t ThermalPower = {3:0.000} [MW]\t Q {4:0.000} [sm3/s]\t P {5:0.000} [bar]",
                    m.GDEM.GNET.SCE.dTime[kstep], m.GDEM, ActivePower, ThermalPower, GasOfftake, Pressure));
            }
        }

        public static double GetActivePowerFromAvailableThermalPower(double Pth, double InitVal)
        {
            double Get_dF(double x) => 3.6 * Pth - x * GetHR(x);

            int maxiter = 30;
            int i = 0;
            double ActivePower = InitVal;
            double Residual;

            while (i < maxiter)
            {
                Residual = Math.Abs(Get_dF(ActivePower));
                if (Residual < 1e-6)
                {
                    return ActivePower;
                }
                else if (GetdF_by_dx(ActivePower) != 0)
                {
                    ActivePower -= Get_dF(ActivePower) / GetdF_by_dx(ActivePower);
                }
                else
                {
                    ActivePower -= 0.0001;
                }
                i += 1;
            }

            return ActivePower;
        }

        public static void SubscribeToRequiredActivePower(int kstep, List<ElectricGasMapping> MappingList)
        {
            Units Unit = new Units(UnitTypeList.Q, UnitList.sm3_s);

            foreach (ElectricGasMapping m in MappingList)
            {
                GasNode GNODE = (GasNode)m.GDEM.NetNode;
                DateTime DateTimeStep = m.GDEM.GNET.SCE.dTime[kstep];
                // get publication from electric federate
                double RequiredActivePower = h.helicsInputGetDouble(m.RequieredActivePower);
                
                double RequiredThermalPower = GetHR(RequiredActivePower)* RequiredActivePower/3.6;

                Console.WriteLine(String.Format("Gas-R: Time {0}\t {1}\t ActivePowerRequested = {2:0.000} [MW]", DateTimeStep, m.GDEM, RequiredActivePower));

                //get currently available thermal power 
                double GCV = GNODE.get_NQ(kstep).GCV / 1e6; // in MJ/m3   
                double AvailableThermalPower = GCV * m.GDEM.get_Q(kstep);
                foreach (var evt in m.GDEM.SceList.Where(xx => xx.ObjPar == CtrlType.QSET && xx.StartTime == DateTimeStep))
                    {
                        evt.ObjVal = RequiredThermalPower / GCV;
                        evt.Unit = Unit;
                        evt.Processed = false;
                        evt.Active = true;
                        evt.Info = "HELICS";
                    }
                Console.WriteLine(String.Format("Gas-E: Time {0}\t {1}\t QSET = {2:0.000} [sm3/s]",
                        DateTimeStep, m.GDEM, m.GDEM.get_QSET(kstep)));                
            }
        }

        public static List<ElectricGasMapping> CoupledGasDemands(IList<GasDemand> GDEMs, SWIGTYPE_p_void vfed)
        {
            List<ElectricGasMapping> MappingList = new List<ElectricGasMapping>();

            Units Unit = new Units(UnitTypeList.Q, UnitList.sm3_s);
            foreach (GasDemand demand in GDEMs)
            {
                var mapitem = new ElectricGasMapping() { GDEM = demand };
                 
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

                // Register Publication and Subscription for coupling points
                if (demand.Name == "N15") // corresponds to transmission node 6
                {
                    mapitem.AvailableActivePower = h.helicsFederateRegisterGlobalTypePublication(vfed, "ng1/node.6.avail", "double", "MW");
                    mapitem.RequieredActivePower = h.helicsFederateRegisterSubscription(vfed, "transmission/node.6.requested", "MW");
                }
                else if (demand.Name == "N21") // corresponds to transmission node 8
                {
                    mapitem.AvailableActivePower = h.helicsFederateRegisterGlobalTypePublication(vfed, "ng1/node.8.avail", "double", "MW");
                    mapitem.RequieredActivePower = h.helicsFederateRegisterSubscription(vfed, "transmission/node.8.requested", "MW");
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
}
