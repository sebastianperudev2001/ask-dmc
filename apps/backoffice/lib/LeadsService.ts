import { Context, Stream } from "effect"
import type { LeadsError } from "@/types/errors"
import type { LeadOut } from "@/types/leads"

// /ws/leads is push-only (agent-service LeadBroadcaster) — unlike ChatService, there is
// no sendMessage-equivalent effect here, only an event stream (Functional Design
// frontend-components.md Section 1/3).
export type LeadWireEvent =
  | { _tag: "snapshot"; leads: LeadOut[] }
  | { _tag: "leadEvent"; eventType: "created" | "score_changed" | "motivation_set"; lead: LeadOut }

export class LeadsService extends Context.Tag("LeadsService")<
  LeadsService,
  {
    readonly events: Stream.Stream<LeadWireEvent, LeadsError>
  }
>() {}
