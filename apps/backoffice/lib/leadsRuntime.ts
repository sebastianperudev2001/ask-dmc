import { ManagedRuntime } from "effect"
import { WsLeadsServiceLive } from "./WsLeadsService"

export const LeadsAppRuntime = ManagedRuntime.make(WsLeadsServiceLive)
