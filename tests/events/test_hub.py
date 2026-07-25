from __future__ import annotations

import asyncio

from runtime.events import EventHub


def test_publish_routes_global_and_session_events_to_their_subscribers():
    hub = EventHub()
    global_events = []
    session_one_events = []
    session_two_events = []

    async def global_listener(message):
        global_events.append(message)

    async def session_one_listener(message):
        session_one_events.append(message)

    async def session_two_listener(message):
        session_two_events.append(message)

    hub.subscribe_global(global_listener)
    hub.subscribe_session("s1", session_one_listener)
    hub.subscribe_session("s2", session_two_listener)

    asyncio.run(hub.publish_global({"type": "status"}))
    asyncio.run(hub.publish_session("s1", {"type": "turn_done"}))

    assert global_events == [{"type": "status"}]
    assert session_one_events == [{"type": "turn_done"}]
    assert session_two_events == []


def test_subscription_handle_stops_future_delivery():
    hub = EventHub()
    events = []

    async def listener(message):
        events.append(message)

    unsubscribe = hub.subscribe_session("s1", listener)
    asyncio.run(hub.publish_session("s1", {"sequence": 1}))
    unsubscribe()
    asyncio.run(hub.publish_session("s1", {"sequence": 2}))

    assert events == [{"sequence": 1}]


def test_failed_global_listener_is_pruned_without_blocking_delivery():
    hub = EventHub()
    healthy_events = []
    failed_calls = 0

    async def healthy(message):
        healthy_events.append(message)

    async def failed(_message):
        nonlocal failed_calls
        failed_calls += 1
        raise RuntimeError("socket closed")

    hub.subscribe_global(healthy)
    hub.subscribe_global(failed)

    asyncio.run(hub.publish_global({"sequence": 1}))
    asyncio.run(hub.publish_global({"sequence": 2}))

    assert healthy_events == [{"sequence": 1}, {"sequence": 2}]
    assert failed_calls == 1


def test_failed_session_listener_is_pruned_only_from_its_session():
    hub = EventHub()
    healthy_events = []
    failed_calls = 0

    async def healthy(message):
        healthy_events.append(message)

    async def failed(_message):
        nonlocal failed_calls
        failed_calls += 1
        raise RuntimeError("socket closed")

    hub.subscribe_session("s1", healthy)
    hub.subscribe_session("s1", failed)
    hub.subscribe_session("s2", failed)

    asyncio.run(hub.publish_session("s1", {"sequence": 1}))
    asyncio.run(hub.publish_session("s1", {"sequence": 2}))
    asyncio.run(hub.publish_session("s2", {"sequence": 3}))

    assert healthy_events == [{"sequence": 1}, {"sequence": 2}]
    assert failed_calls == 2
