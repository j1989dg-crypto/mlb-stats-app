import httpx

_client: httpx.AsyncClient = None

def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
        _client = httpx.AsyncClient(timeout=25.0, limits=limits, follow_redirects=True)
    return _client

async def close_client():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
