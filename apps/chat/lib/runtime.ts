import { ManagedRuntime } from "effect"
import { WsChatServiceLive } from "./WsChatService"

export const AppRuntime = ManagedRuntime.make(WsChatServiceLive)
