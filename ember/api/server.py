"""Ember API server implementation using Starlette."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from ..ai import CommandExecutionLog, LlamaSession
    from ..agents import AgentRegistry
    from ..configuration import ConfigurationBundle
    from ..slash_commands import CommandRouter

logger = logging.getLogger("ember.api.server")


class APIServerState(str, Enum):
    """API server lifecycle states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class EmberAPIServer:
    """HTTP/WebSocket API server for remote Ember interaction."""

    config_bundle: "ConfigurationBundle"
    router: Optional["CommandRouter"] = None
    llama_session: Optional["LlamaSession"] = None
    agent_registry: Optional["AgentRegistry"] = None
    command_history: List["CommandExecutionLog"] = field(default_factory=list)

    # Server state
    _state: APIServerState = field(default=APIServerState.STOPPED, init=False)
    _server: Optional[Any] = field(default=None, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)
    _loop: Optional[asyncio.AbstractEventLoop] = field(default=None, init=False)

    @property
    def state(self) -> APIServerState:
        """Current server state."""
        return self._state

    @property
    def host(self) -> str:
        """Configured host address."""
        api_config = self._get_api_config()
        return api_config.get("host", "127.0.0.1")

    @property
    def port(self) -> int:
        """Configured port number."""
        api_config = self._get_api_config()
        return int(api_config.get("port", 8000))

    @property
    def api_key(self) -> str:
        """Get or generate the API key."""
        from .auth import APIKeyManager
        manager = APIKeyManager(self.config_bundle.vault_dir)
        return manager.get_or_generate_key()

    def _get_api_config(self) -> Dict[str, Any]:
        """Get API configuration from bundle."""
        if self.config_bundle.merged:
            return self.config_bundle.merged.get("api", {}) or {}
        return {}

    def _create_app(self) -> Any:
        """Create the Starlette application."""
        try:
            from starlette.applications import Starlette
            from starlette.middleware import Middleware
            from starlette.middleware.cors import CORSMiddleware
            from starlette.routing import Route, WebSocketRoute
        except ImportError as e:
            raise RuntimeError(
                "Starlette is not installed. Run 'pip install starlette uvicorn' "
                f"to enable API mode. (Error: {e})"
            )

        from .routes import (
            health_handler,
            status_handler,
            agents_handler,
            agent_trigger_handler,
            config_handler,
            history_handler,
            chat_handler,
            chat_stream_handler,
            websocket_chat_handler,
        )

        # Build middleware list
        middleware = []
        api_config = self._get_api_config()
        cors_origins = api_config.get("cors_origins", [])

        if cors_origins:
            middleware.append(
                Middleware(
                    CORSMiddleware,
                    allow_origins=cors_origins,
                    allow_credentials=True,
                    allow_methods=["*"],
                    allow_headers=["*"],
                )
            )

        # API key authentication middleware
        middleware.append(Middleware(self._auth_middleware_class()))

        # Define routes
        routes = [
            Route("/health", health_handler, methods=["GET"]),
            Route("/api/v1/status", status_handler, methods=["GET"]),
            Route("/api/v1/agents", agents_handler, methods=["GET"]),
            Route("/api/v1/agents/{name}", agent_trigger_handler, methods=["POST"]),
            Route("/api/v1/config", config_handler, methods=["GET"]),
            Route("/api/v1/history", history_handler, methods=["GET"]),
            Route("/api/v1/chat", chat_handler, methods=["POST"]),
            Route("/api/v1/chat/stream", chat_stream_handler, methods=["POST"]),
            WebSocketRoute("/ws/chat", websocket_chat_handler),
        ]

        app = Starlette(
            routes=routes,
            middleware=middleware,
            on_startup=[self._on_startup],
            on_shutdown=[self._on_shutdown],
        )

        # Store reference to server in app state
        app.state.ember_server = self

        return app

    def _auth_middleware_class(self) -> type:
        """Create an authentication middleware class."""
        server = self

        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import JSONResponse

        class AuthMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                # Skip auth for health endpoint
                if request.url.path == "/health":
                    return await call_next(request)

                # Check API key
                api_key = request.headers.get("X-API-Key", "")
                if not api_key:
                    api_key = request.query_params.get("api_key", "")

                from .auth import APIKeyManager
                manager = APIKeyManager(server.config_bundle.vault_dir)

                if not manager.validate_key(api_key):
                    return JSONResponse(
                        {"error": "Invalid or missing API key"},
                        status_code=401
                    )

                return await call_next(request)

        return AuthMiddleware

    async def _on_startup(self) -> None:
        """Called when the server starts."""
        logger.info("API server starting on %s:%s", self.host, self.port)
        self._state = APIServerState.RUNNING

    async def _on_shutdown(self) -> None:
        """Called when the server stops."""
        logger.info("API server shutting down")
        self._state = APIServerState.STOPPED

    def start(self, blocking: bool = False) -> bool:
        """Start the API server.

        Args:
            blocking: If True, block until server stops. If False, run in background thread.

        Returns:
            True if server started successfully.
        """
        if self._state == APIServerState.RUNNING:
            logger.warning("API server is already running")
            return False

        try:
            import uvicorn
        except ImportError as e:
            logger.error("uvicorn is not installed: %s", e)
            self._state = APIServerState.ERROR
            return False

        self._state = APIServerState.STARTING
        app = self._create_app()

        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)

        if blocking:
            # Run in current thread
            try:
                asyncio.run(self._server.serve())
            except Exception as e:
                logger.exception("API server error: %s", e)
                self._state = APIServerState.ERROR
                return False
        else:
            # Run in background thread
            self._thread = threading.Thread(
                target=self._run_in_thread,
                daemon=True,
                name="ember-api-server",
            )
            self._thread.start()

            # Wait briefly for server to start
            import time
            for _ in range(20):  # Wait up to 2 seconds
                time.sleep(0.1)
                if self._state == APIServerState.RUNNING:
                    break

        return self._state == APIServerState.RUNNING

    def _run_in_thread(self) -> None:
        """Run the server in a background thread."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._server.serve())
        except Exception as e:
            logger.exception("API server thread error: %s", e)
            self._state = APIServerState.ERROR
        finally:
            if self._loop:
                self._loop.close()
            self._state = APIServerState.STOPPED

    def stop(self) -> bool:
        """Stop the API server.

        Returns:
            True if server stopped successfully.
        """
        if self._state != APIServerState.RUNNING:
            logger.warning("API server is not running")
            return False

        self._state = APIServerState.STOPPING

        if self._server:
            self._server.should_exit = True

        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._state = APIServerState.STOPPED
        self._server = None
        self._thread = None

        return True

    def status(self) -> Dict[str, Any]:
        """Get server status information."""
        return {
            "state": self._state.value,
            "host": self.host,
            "port": self.port,
            "url": f"http://{self.host}:{self.port}" if self._state == APIServerState.RUNNING else None,
        }


__all__ = ["EmberAPIServer", "APIServerState"]
