"""Capture one owned page's initial ClientHello without a certificate or TLS server."""

import asyncio

from playwright.async_api import Error as PlaywrightError

from .client_hello import ClientHelloError, read_client_hello, selected_shape


async def capture_client_hello(page) -> dict:
    """Navigate a disposable page to loopback; the HTTPS request deliberately fails."""
    future = asyncio.get_running_loop().create_future()
    handlers = []
    first = True
    primary = None

    async def handle(reader, writer):
        nonlocal first
        handlers.append(asyncio.current_task())
        selected = first
        first = False
        try:
            if not selected:
                return
            peer = writer.get_extra_info("peername")
            if not peer or peer[0] != "127.0.0.1":
                raise ClientHelloError("Owned fixture received a non-loopback connection")
            parsed = await read_client_hello(reader)
            writer.close()
            await writer.wait_closed()
            server.close()
            if not future.done():
                future.set_result(parsed)
        except Exception as error:
            if not future.done():
                future.set_exception(error)
        finally:
            writer.close()
            server.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        try:
            await page.goto(f"https://localhost:{port}/owned-clienthello", timeout=10000)
        except PlaywrightError as error:
            expected = ("net::ERR_CONNECTION_CLOSED", "net::ERR_CONNECTION_RESET", "net::ERR_CONNECTION_REFUSED")
            if not any(code in str(error) for code in expected):
                raise
        else:
            raise ClientHelloError("The fixture never sends a ServerHello or certificate")
        parsed = await asyncio.wait_for(future, timeout=5)
        if page.is_closed() or not page.context.browser.is_connected():
            raise ClientHelloError("Owned browser/page closed during ClientHello capture")
        return {**parsed, "navigation_failed_as_designed": True,
                "selected_shape": selected_shape(parsed["hello"])}
    except BaseException as error:
        primary = error
        raise
    finally:
        server.close()
        await server.wait_closed()
        for task in handlers:
            if not task.done():
                task.cancel()
        if handlers:
            outcomes = await asyncio.gather(*handlers, return_exceptions=True)
            failures = [value for value in outcomes if isinstance(value, BaseException)
                        and not isinstance(value, asyncio.CancelledError)]
            if failures:
                if primary is not None:
                    primary.add_note("Loopback handler cleanup failed: " + str(failures[0]))
                else:
                    raise ClientHelloError("Loopback handler cleanup failed") from failures[0]
        if not future.done():
            future.cancel()
        elif not future.cancelled():
            future.exception()
