'use client'
import { createContext, useContext } from "react"
import { AppRuntime } from "./runtime"

type AppRuntimeType = typeof AppRuntime

const RuntimeContext = createContext<AppRuntimeType>(AppRuntime)

export const useRuntime = () => useContext(RuntimeContext)

export const RuntimeProvider = ({ children }: { children: React.ReactNode }) => (
  <RuntimeContext.Provider value={AppRuntime}>
    {children}
  </RuntimeContext.Provider>
)
