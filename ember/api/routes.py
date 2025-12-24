"""API route handlers for the Ember API server."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response, JSONResponse, StreamingResponse
    from starlette.websockets import WebSocket

logger = logging.getLogger("ember.api.routes")


async def health_handler(request: "Request") -> "JSONResponse":
    """Health check endpoint."""
    from starlette.responses import JSONResponse

    return JSONResponse({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "ember-api",
    })


async def status_handler(request: "Request") -> "JSONResponse":
    """Get system status including agent state."""
    from starlette.responses import JSONResponse

    server = request.app.state.ember_server
    config = server.config_bundle

    # Get agent state
    agent_state = config.agent_state or {}

    return JSONResponse({
        "status": config.status,
        "vault_dir": str(config.vault_dir),
        "agents": agent_state,
        "diagnostics": [
            {"level": d.level, "message": d.message}
            for d in config.diagnostics
        ],
    })


async def agents_handler(request: "Request") -> "JSONResponse":
    """List all registered agents and their status."""
    from starlette.responses import JSONResponse

    server = request.app.state.ember_server
    registry = server.agent_registry

    agents = []
    enabled_state = registry.enabled(server.config_bundle)

    for name, definition in registry._registry.items():
        agents.append({
            "name": definition.name,
            "description": definition.description,
            "triggers": list(definition.triggers),
            "enabled": enabled_state.get(name, False),
            "requires_ready": definition.requires_ready,
        })

    return JSONResponse({"agents": agents})


async def agent_trigger_handler(request: "Request") -> "JSONResponse":
    """Trigger a specific agent."""
    from starlette.responses import JSONResponse

    server = request.app.state.ember_server
    agent_name = request.path_params.get("name", "")

    if not agent_name:
        return JSONResponse({"error": "Agent name required"}, status_code=400)

    registry = server.agent_registry
    definition = registry._registry.get(agent_name.lower())

    if not definition:
        return JSONResponse({"error": f"Agent '{agent_name}' not found"}, status_code=404)

    try:
        result = definition.handler(server.config_bundle)
        if hasattr(result, "to_dict"):
            result = result.to_dict()
        elif not isinstance(result, dict):
            result = {"status": "ok", "detail": str(result)}

        return JSONResponse({
            "agent": agent_name,
            "result": result,
        })
    except Exception as e:
        logger.exception("Failed to run agent '%s'", agent_name)
        return JSONResponse({
            "agent": agent_name,
            "error": str(e),
        }, status_code=500)


async def config_handler(request: "Request") -> "JSONResponse":
    """Get current configuration."""
    from starlette.responses import JSONResponse

    server = request.app.state.ember_server
    config = server.config_bundle

    # Filter out sensitive fields
    merged = dict(config.merged) if config.merged else {}
    if "api" in merged and "api_key" in merged["api"]:
        merged["api"]["api_key"] = "***"

    return JSONResponse({
        "status": config.status,
        "merged": merged,
    })


async def history_handler(request: "Request") -> "JSONResponse":
    """Get command execution history."""
    from starlette.responses import JSONResponse

    server = request.app.state.ember_server
    history = server.command_history

    limit = int(request.query_params.get("limit", "50"))
    history_slice = history[-limit:] if limit > 0 else history

    return JSONResponse({
        "history": [
            {"command": h.command, "output": h.output}
            for h in history_slice
        ],
        "total": len(history),
    })


async def chat_handler(request: "Request") -> "JSONResponse":
    """Send a message and get a response."""
    from starlette.responses import JSONResponse

    server = request.app.state.ember_server

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    message = body.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "Message required"}, status_code=400)

    try:
        # Use the LLM session to generate a response
        llama_session = server.llama_session
        if llama_session is None:
            return JSONResponse({
                "error": "LLM session not initialized"
            }, status_code=503)

        # Plan phase
        plan = llama_session.plan(message)

        # Execute any planned commands
        tool_outputs = []
        if plan.commands:
            for cmd_name in plan.commands:
                try:
                    result = server.router.handle(cmd_name, [], source="api")
                    tool_outputs.append(f"/{cmd_name}\n{result}")
                except Exception as e:
                    tool_outputs.append(f"/{cmd_name}\n[error] {e}")

        # Generate final response
        if plan.commands:
            tool_context = "\n\n".join(tool_outputs)
            response = llama_session.respond(message, tool_context)
        else:
            response = plan.response

        return JSONResponse({
            "response": response,
            "commands_run": plan.commands,
        })

    except Exception as e:
        logger.exception("Chat handler error")
        return JSONResponse({"error": str(e)}, status_code=500)


async def chat_stream_handler(request: "Request") -> "StreamingResponse":
    """Send a message and stream the response (Server-Sent Events)."""
    from starlette.responses import StreamingResponse

    server = request.app.state.ember_server

    try:
        body = await request.json()
    except json.JSONDecodeError:
        from starlette.responses import JSONResponse
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    message = body.get("message", "").strip()
    if not message:
        from starlette.responses import JSONResponse
        return JSONResponse({"error": "Message required"}, status_code=400)

    async def generate():
        try:
            llama_session = server.llama_session
            if llama_session is None:
                yield f"data: {json.dumps({'error': 'LLM session not initialized'})}\n\n"
                return

            # Plan phase (non-streaming)
            plan = llama_session.plan(message)
            yield f"data: {json.dumps({'type': 'plan', 'commands': plan.commands})}\n\n"

            # Execute commands
            tool_outputs = []
            if plan.commands:
                for cmd_name in plan.commands:
                    try:
                        result = server.router.handle(cmd_name, [], source="api")
                        tool_outputs.append(f"/{cmd_name}\n{result}")
                        yield f"data: {json.dumps({'type': 'command', 'name': cmd_name, 'status': 'complete'})}\n\n"
                    except Exception as e:
                        tool_outputs.append(f"/{cmd_name}\n[error] {e}")
                        yield f"data: {json.dumps({'type': 'command', 'name': cmd_name, 'status': 'error', 'error': str(e)})}\n\n"

            # Stream response
            tool_context = "\n\n".join(tool_outputs) if tool_outputs else ""
            for token, final_response in llama_session.respond_streaming(message, tool_context):
                if final_response is not None:
                    yield f"data: {json.dumps({'type': 'done', 'response': final_response})}\n\n"
                elif token:
                    yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"

        except Exception as e:
            logger.exception("Streaming chat error")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


async def websocket_chat_handler(websocket: "WebSocket") -> None:
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    server = websocket.app.state.ember_server

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "").strip()

            if not message:
                await websocket.send_json({"error": "Message required"})
                continue

            try:
                llama_session = server.llama_session
                if llama_session is None:
                    await websocket.send_json({"error": "LLM session not initialized"})
                    continue

                # Plan
                plan = llama_session.plan(message)
                await websocket.send_json({"type": "plan", "commands": plan.commands})

                # Execute commands
                tool_outputs = []
                if plan.commands:
                    for cmd_name in plan.commands:
                        try:
                            result = server.router.handle(cmd_name, [], source="api")
                            tool_outputs.append(f"/{cmd_name}\n{result}")
                            await websocket.send_json({
                                "type": "command",
                                "name": cmd_name,
                                "status": "complete"
                            })
                        except Exception as e:
                            tool_outputs.append(f"/{cmd_name}\n[error] {e}")

                # Stream response
                tool_context = "\n\n".join(tool_outputs) if tool_outputs else ""
                for token, final_response in llama_session.respond_streaming(message, tool_context):
                    if final_response is not None:
                        await websocket.send_json({
                            "type": "done",
                            "response": final_response
                        })
                    elif token:
                        await websocket.send_json({
                            "type": "token",
                            "text": token
                        })

            except Exception as e:
                logger.exception("WebSocket chat error")
                await websocket.send_json({"type": "error", "error": str(e)})

    except Exception:
        pass  # Client disconnected
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


__all__ = [
    "health_handler",
    "status_handler",
    "agents_handler",
    "agent_trigger_handler",
    "config_handler",
    "history_handler",
    "chat_handler",
    "chat_stream_handler",
    "websocket_chat_handler",
]
