'use client'
import { createContext, useContext } from "react"
import { LeadsAppRuntime } from "./leadsRuntime"

type LeadsAppRuntimeType = typeof LeadsAppRuntime

const LeadsRuntimeContext = createContext<LeadsAppRuntimeType>(LeadsAppRuntime)

export const useLeadsRuntime = () => useContext(LeadsRuntimeContext)

export const LeadsRuntimeProvider = ({ children }: { children: React.ReactNode }) => (
  <LeadsRuntimeContext.Provider value={LeadsAppRuntime}>
    {children}
  </LeadsRuntimeContext.Provider>
)
