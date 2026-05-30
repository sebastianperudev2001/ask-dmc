import { ManagedRuntime } from "effect"
import { HttpChatService } from "./HttpChatService"

export const AppRuntime = ManagedRuntime.make(HttpChatService)
