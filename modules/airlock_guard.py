"""Keep closed-Airlock arrivals outside the studio's HTTP and socket surfaces."""
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from . import auth
from .route_security import auth_enforced

AIRLOCK_PAGE = '/static/human_visits.html'
PUBLIC_READS = {
    '/health', '/login', AIRLOCK_PAGE,
    '/static/login.html', '/static/reach_auth.js', '/static/human_visits.js',
    '/static/waiting_room_host.js', '/api/auth/status', '/api/guests/event',
    '/api/governance/waiting-room/host', '/api/governance/terms',
}
PUBLIC_WRITES = {
    '/api/auth/login', '/api/auth/setup', '/api/auth/logout',
    '/api/guests/arrival', '/api/guests/arrival/status',
    '/api/guests/challenge', '/api/guests/request', '/api/guests/status',
}


class AirlockGuardMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        kind = scope['type']
        if kind not in {'http', 'websocket'} or not auth_enforced():
            return await self.app(scope, receive, send)
        connection = HTTPConnection(scope)
        method = scope.get('method', '')
        path = scope['path']
        if kind == 'http' and (
            (method in {'GET', 'HEAD'} and (path in PUBLIC_READS or path.startswith('/static/fonts/')))
            or (method == 'POST' and path in PUBLIC_WRITES)
            or method == 'OPTIONS'
        ):
            return await self.app(scope, receive, send)

        # PubWorld verifies its browser credentials in the first frame before sending studio state.
        if kind == 'websocket' and path.startswith('/pubworld/ws/'):
            return await self.app(scope, receive, send)
        authorization = connection.headers.get('authorization', '')
        bearer = authorization[7:].strip() if authorization.lower().startswith('bearer ') else ''
        token = bearer
        if not authorization and (kind == 'websocket' or method in {'GET', 'HEAD'}):
            token = connection.cookies.get(auth.WS_SESSION_COOKIE, '')
        if token and await run_in_threadpool(auth.decode_access_token, token):
            return await self.app(scope, receive, send)

        admission = getattr(connection.app.state, 'guest_admission', None)
        if admission is None or not (await run_in_threadpool(admission.settings))['locked']:
            return await self.app(scope, receive, send)
        if kind == 'websocket':
            await send({'type': 'websocket.close', 'code': 4401, 'reason': 'Airlock admission required'})
            return
        document = (connection.headers.get('sec-fetch-dest') in {'document', 'iframe'}
                    or 'text/html' in connection.headers.get('accept', ''))
        if method in {'GET', 'HEAD'} and document and not path.startswith('/api/'):
            response = RedirectResponse(AIRLOCK_PAGE + '?mode=join', status_code=303,
                                        headers={'Cache-Control': 'no-store'})
        else:
            response = JSONResponse({'detail': 'Airlock admission required'}, status_code=401,
                                    headers={'Cache-Control': 'no-store'})
        await response(scope, receive, send)
