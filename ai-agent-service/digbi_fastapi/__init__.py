from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from typing import Callable, List

__all__ = [
    "FastAPI",
    "APIRouter",
    "Request",
    "JSONResponse",
    "TestClient",
]

class APIRouter:
    def __init__(self):
        self.routes: List[Route] = []

    def add_api_route(self, path: str, endpoint: Callable, methods: list):
        self.routes.append(Route(path, endpoint, methods=methods))

    def get(self, path: str):
        def decorator(func: Callable):
            self.add_api_route(path, func, ["GET"])
            return func
        return decorator

    def post(self, path: str):
        def decorator(func: Callable):
            self.add_api_route(path, func, ["POST"])
            return func
        return decorator

    def put(self, path: str):
        def decorator(func: Callable):
            self.add_api_route(path, func, ["PUT"])
            return func
        return decorator

    def include_router(self, router: "APIRouter", prefix: str = ""):
        for r in router.routes:
            self.add_api_route(prefix + r.path, r.endpoint, list(r.methods))

class FastAPI(Starlette):
    def include_router(self, router: APIRouter, prefix: str = ""):
        for r in router.routes:
            self.router.routes.append(Route(prefix + r.path, r.endpoint, methods=list(r.methods)))

    def get(self, path: str):
        def decorator(func: Callable):
            self.add_route(path, func, methods=["GET"])
            return func
        return decorator

    def post(self, path: str):
        def decorator(func: Callable):
            self.add_route(path, func, methods=["POST"])
            return func
        return decorator

    def put(self, path: str):
        def decorator(func: Callable):
            self.add_route(path, func, methods=["PUT"])
            return func
        return decorator
