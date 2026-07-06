"""ChatWebSocketHandler — `/ws/chat` (renamed from `/ws/recommendation`, RF-I01).
Accepts free-form chat (`user_message`) and the widget's structured response
(`profile_data_submitted`). A single background receiver task (PATTERN-15) is the only
coroutine that calls `websocket.receive_json()` — it resolves pending tool-call futures
directly and queues `user_message` for the main loop, so a `collect_profile_data` pause
(business-logic-model.md Section 8.1) does not block receiving the widget's answer.
SECURITY-08 exception carried over from incremento 1: this endpoint is intentionally
public/unauthenticated."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from src.adapters.chat_agent_client import (
    ChatAgentClient,
    PaymentLinkCreated,
    ProfileDataRequested,
    RecommendationsReady,
    TextDelta,
)
from src.api.schemas import (
    CandidateSummary,
    PaymentLinkCreatedOut,
    ProfileDataPrefill,
    ProfileDataRequestedOut,
    ProfileDataSubmittedIn,
    RecommendationDoneMessage,
    SessionCreatedOut,
    TurnDoneOut,
    UserMessageIn,
)
from src.domain.models import MessageRole
from src.ports.conversation_message_repository import ConversationMessageRepository
from src.ports.conversation_session_store import ConversationSessionStore

logger = logging.getLogger("agent_service.chat_websocket")

_DISCONNECT_SENTINEL: UserMessageIn | None = None


class ChatWebSocketHandler:
    def __init__(
        self,
        agent_client_factory,
        conversation_message_repository: ConversationMessageRepository | None = None,
        conversation_session_store: ConversationSessionStore | None = None,
    ) -> None:
        """`agent_client_factory(on_profile_data_requested, pending_tool_calls, conversation_id) -> ChatAgentClient`
        — a callable, not a shared instance, because each connection needs its own
        ChatAgentClient closing over its own PendingToolCallRegistry, send callback, and
        stable conversation_id (see ChatAgentClient.__init__ docstring — Foundry's
        service_session_id rotates every turn and can't be used as a stable Lead key).

        `conversation_message_repository` persists the transcript so the frontend can
        rehydrate visible messages after a page reload (added after Build and Test —
        see migrations/003_create_conversation_messages.sql).

        `conversation_session_store` resolves the Foundry service_session_id to resume
        when the client only sends conversation_id (e.g. picking a past conversation
        from the real history list, added after user feedback) — the browser only ever
        keeps the single most-recent service_session_id in localStorage, so switching to
        an older conversation needs a server-side lookup by conversation_id instead.

        Both optional/None-able so existing tests with fakes that don't care about them
        keep working unchanged."""
        self._agent_client_factory = agent_client_factory
        self._conversation_message_repository = conversation_message_repository
        self._conversation_session_store = conversation_session_store

    async def handle_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()

        from src.domain.pending_tool_calls import PendingToolCallRegistry

        pending_tool_calls = PendingToolCallRegistry()
        user_message_queue: asyncio.Queue[UserMessageIn | None] = asyncio.Queue()
        conversation_id = str(uuid.uuid4())

        async def send_profile_data_requested(event: ProfileDataRequested) -> None:
            await websocket.send_json(
                ProfileDataRequestedOut(
                    call_id=event.call_id, prefill=ProfileDataPrefill(**event.prefill)
                ).model_dump(mode="json")
            )

        agent_client = self._agent_client_factory(
            send_profile_data_requested, pending_tool_calls, conversation_id
        )

        receiver_task = asyncio.create_task(
            self._receive_loop(websocket, pending_tool_calls, user_message_queue)
        )

        session = None
        conversation_id_resolved = False
        try:
            while True:
                message = await user_message_queue.get()
                if message is None:  # disconnect sentinel
                    break

                if not conversation_id_resolved:
                    # Resume the client's own conversation_id if it sent one back (page
                    # reload rehydration, or switching to a past conversation from the
                    # real history list) — otherwise keep the provisional one generated
                    # at connection start. Must happen before resolving the session and
                    # before persisting/streaming, so the right Foundry thread is looked
                    # up and the transcript/Lead stay under the same id across reloads.
                    if message.conversation_id:
                        conversation_id = message.conversation_id
                        agent_client.set_conversation_id(conversation_id)
                    conversation_id_resolved = True

                if session is None:
                    service_session_id = message.service_session_id
                    if not service_session_id and self._conversation_session_store is not None:
                        # Client only knows conversation_id (switched to a past
                        # conversation) — look up which Foundry thread to resume.
                        service_session_id = await self._conversation_session_store.get_service_session_id(
                            conversation_id
                        )
                    session = self._resolve_session(agent_client, service_session_id)

                if self._conversation_message_repository is not None:
                    await self._conversation_message_repository.append(
                        conversation_id, MessageRole.USER, message.text
                    )

                # BR-17b: re-evaluate the engagement floor (5+ user messages -> warm,
                # 10+ -> hot) after every user turn, not just at the 3 tool-call points.
                await agent_client.record_user_message()

                answer_text = ""
                try:
                    try:
                        async for event in agent_client.stream(message.text, session):
                            if isinstance(event, TextDelta):
                                answer_text += event.text
                            await self._send_event(websocket, event)
                    except asyncio.CancelledError:
                        # A pending tool-call future (e.g. collect_profile_data,
                        # PATTERN-15) was cancelled by pending_tool_calls.cancel_all()
                        # because the connection was torn down while the widget was
                        # still pending. asyncio.CancelledError is a BaseException
                        # (Python 3.8+), so it is NOT caught by `except Exception`
                        # below and would otherwise escape as an unhandled ASGI
                        # exception — found via user report of past conversations left
                        # with only the user's message and no bot reply.
                        logger.info("chat_turn_cancelled_by_disconnect")
                    except Exception:
                        # SECURITY-15: fail-safe — never leak internal details to the client.
                        logger.exception("unhandled_error_streaming_chat_response")

                    if self._conversation_message_repository is not None and answer_text:
                        await self._conversation_message_repository.append(
                            conversation_id, MessageRole.BOT, answer_text
                        )

                    await websocket.send_json(TurnDoneOut().model_dump(mode="json"))

                    # Sent after EVERY turn, not just the first: found via real E2E
                    # verification that Foundry's service_session_id is a rotating
                    # per-turn response id, not a stable thread id — the client must
                    # persist the latest value to correctly resume the conversation
                    # (see ChatAgentClient.__init__ docstring for the full explanation;
                    # Lead persistence uses conversation_id instead, which is why it's
                    # sent here too — see UserMessageIn.conversation_id docstring).
                    if getattr(session, "service_session_id", None):
                        if self._conversation_session_store is not None:
                            await self._conversation_session_store.set_service_session_id(
                                conversation_id, session.service_session_id
                            )
                        await websocket.send_json(
                            SessionCreatedOut(
                                service_session_id=session.service_session_id,
                                conversation_id=conversation_id,
                            ).model_dump(mode="json")
                        )
                except (WebSocketDisconnect, RuntimeError):
                    # Client disconnected mid-turn (e.g. closed the tab while the agent
                    # was still streaming) — sends after that point raise a RuntimeError
                    # from the ASGI layer, not WebSocketDisconnect. Found via real E2E
                    # verification (Build and Test), not just theoretical — nothing left
                    # to send to, so end the connection cleanly instead of propagating.
                    logger.info("chat_websocket_disconnected_mid_turn")
                    break
        finally:
            receiver_task.cancel()
            pending_tool_calls.cancel_all()

    @staticmethod
    def _resolve_session(agent_client: ChatAgentClient, service_session_id: str | None):
        if service_session_id:
            try:
                return agent_client.get_session(service_session_id)
            except Exception:
                logger.warning("failed_to_resume_session_creating_new_one")
        return agent_client.create_session()

    @staticmethod
    async def _send_event(websocket: WebSocket, event: Any) -> None:
        if isinstance(event, TextDelta):
            from src.api.schemas import RecommendationDeltaMessage

            await websocket.send_json(
                RecommendationDeltaMessage(delta=event.text).model_dump(mode="json")
            )
        elif isinstance(event, PaymentLinkCreated):
            await websocket.send_json(
                PaymentLinkCreatedOut(checkout_url=event.checkout_url).model_dump(mode="json")
            )
        elif isinstance(event, RecommendationsReady):
            await websocket.send_json(
                RecommendationDoneMessage(
                    candidates=[
                        CandidateSummary.from_candidate(candidate) for candidate in event.candidates
                    ]
                ).model_dump(mode="json")
            )

    async def _receive_loop(
        self,
        websocket: WebSocket,
        pending_tool_calls,
        user_message_queue: asyncio.Queue[UserMessageIn | None],
    ) -> None:
        try:
            while True:
                raw_message = await websocket.receive_json()
                await self._dispatch_incoming(raw_message, pending_tool_calls, user_message_queue)
        except WebSocketDisconnect:
            logger.info("chat_websocket_disconnected")
        except Exception:
            logger.exception("unhandled_error_in_chat_receive_loop")
        finally:
            # Cancel immediately, not just in handle_connection's finally: the main loop
            # can be blocked inside agent_client.stream() awaiting a pending tool call's
            # future (e.g. collect_profile_data) and would otherwise never notice this
            # disconnect at all — found via real Build and Test verification.
            pending_tool_calls.cancel_all()
            await user_message_queue.put(_DISCONNECT_SENTINEL)

    @staticmethod
    async def _dispatch_incoming(
        raw_message: dict,
        pending_tool_calls,
        user_message_queue: asyncio.Queue[UserMessageIn | None],
    ) -> None:
        message_type = raw_message.get("type")
        try:
            if message_type == "profile_data_submitted":
                submitted = ProfileDataSubmittedIn.model_validate(raw_message)
                pending_tool_calls.resolve(
                    submitted.call_id,
                    {
                        "budget": float(submitted.budget),
                        "max_duration_weeks": submitted.max_duration_weeks,
                        "professional_background": submitted.professional_background,
                        "desired_stack": submitted.desired_stack,
                    },
                )
            elif message_type == "user_message":
                await user_message_queue.put(UserMessageIn.model_validate(raw_message))
            else:
                logger.warning("unknown_message_type_ignored", extra={"type": message_type})
        except ValidationError:
            logger.warning("invalid_message_ignored", extra={"type": message_type})
