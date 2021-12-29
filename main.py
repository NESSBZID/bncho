#!/usr/bin/env python3.9
"""
gulag - a dev-oriented osu! server implementation from TCP/IP sockets.

if you're interested in development, my test server is usually
up at https://c.cmyui.xyz. just use the same `-devserver cmyui.xyz`
connection method you would with any other modern server and you
should have no problems connecting. registration is done in-game
with osu!'s built-in registration (if you're worried about not being
properly connected while registering, the server should send back
https://i.cmyui.xyz/8-Vzy9NllPBp5K7L.png if you use a random login).

you can also test gulag's rest api using my test server,
e.g https://osu.cmyui.xyz/api/get_player_scores?id=3&scope=best
"""
import asyncio
import os
import signal
import socket

import cmyui
from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.logging import RGB

import app.api
import app.context
import app.objects.collections
import app.state
import app.utils
import bg_loops

# set the current working directory to /gulag
os.chdir(os.path.dirname(os.path.realpath(__file__)))


async def run_server() -> int:
    """Begin listening for and handling connections for all endpoints."""

    # we'll be working on top of giants - most closely linux's
    # implementation of the bsd tcp/ip socket interface.
    # python: https://docs.python.org/3/library/socket.html
    # linux/c: https://man7.org/linux/man-pages/man2/socket.2.html

    # these implement tcp/ip over ethernet for us, and osu!stable uses
    # http1.0 & tls1.0 (ssl) ontop of this. linux will parse the ethernet,
    # ipv4, and tcp packets for us, giving us the http packet inside.
    # we'll need to parse the http data, find the appropriate handler
    # we've made for the job, and dispatch the connection to it.

    # at the moment, much of the web code is imported a python module of mine
    # though over time code has slowly been trickling into gulag, and perhaps
    # eventually we will have a full web server implementation in this codebase.
    # https://github.com/cmyui/cmyui_pkg/blob/master/cmyui/web.py
    server = cmyui.Server(
        name=f"gulag v{app.state.settings.VERSION}",
        gzip=4,
        debug=app.state.settings.DEBUG,
    )

    # fetch our server's endpoints; gulag supports
    # osu!'s handlers across multiple domains.
    from app.api.ava import domain as ava_domain  # a.ppy.sh
    from app.api.cho import domain as cho_domain  # c.ppy.sh
    from app.api.map import domain as map_domain  # b.ppy.sh
    from app.api.osu import domain as osu_domain  # osu.ppy.sh

    server.add_domains({ava_domain, cho_domain, map_domain, osu_domain})

    # support both INET and UNIX sockets
    if app.utils.is_inet_address(app.state.settings.SERVER_ADDR):
        sock_family = socket.AF_INET
    elif isinstance(app.state.settings.SERVER_ADDR, str):
        sock_family = socket.AF_UNIX
    else:
        raise ValueError("Invalid socket address.")

    if sock_family == socket.AF_UNIX:
        # using unix socket
        if os.path.exists(app.state.settings.SERVER_ADDR):
            if (
                app.utils.processes_listening_on_unix_socket(
                    app.state.settings.SERVER_ADDR,
                )
                != 0
            ):
                # server is still running
                log(
                    f"There are other processes listening on {app.state.settings.SERVER_ADDR}.\n"
                    f"If you've lost it, gulag can be killed gracefully with SIGINT.",
                    Ansi.LRED,
                )
                await app.utils.cancel_housekeeping_tasks()
                return 1
            else:
                # no processes listening on the socket, just remove it's file
                os.remove(app.state.settings.SERVER_ADDR)

    # create our transport layer socket; osu! uses tcp/ip
    with socket.socket(sock_family, socket.SOCK_STREAM) as listening_sock:
        listening_sock.setblocking(False)  # asynchronous
        listening_sock.bind(app.state.settings.SERVER_ADDR)

        if sock_family == socket.AF_UNIX:
            # using unix socket - give the socket file
            # appropriate (read, write) permissions
            os.chmod(app.state.settings.SERVER_ADDR, 0o666)

        listening_sock.listen(10)  # TODO: customizability or autoscale
        log(f"-> Listening @ {app.state.settings.SERVER_ADDR}", RGB(0x00FF7F))

        app.state.shutting_down = False  # TODO: where to put this

        while not app.state.shutting_down:
            # TODO: this timeout based-solution can be heavily
            #       improved and refactored out.
            try:
                conn, _ = await asyncio.wait_for(
                    fut=app.state.loop.sock_accept(listening_sock),
                    timeout=0.50,
                )
            except asyncio.TimeoutError:
                pass
            else:
                task = app.state.loop.create_task(server.handle(conn))
                task.add_done_callback(app.utils._conn_finished_cb)
                app.state.sessions.ongoing_connections.add(task)

    if sock_family == socket.AF_UNIX:
        # using unix socket - remove from filesystem
        os.remove(app.state.settings.SERVER_ADDR)

    return 0


async def main() -> int:
    """Initialize, and start up the server."""
    app.state.loop = asyncio.get_running_loop()

    async with (
        app.context.acquire_http_session() as app.state.services.http,
        app.context.acquire_mysql_db_pool() as app.state.services.database,
        app.context.acquire_redis_db_pool() as app.state.services.redis,
    ):
        # TODO: do we actually want to do this?
        # await app.state.services.check_for_dependency_updates()

        await app.utils.run_sql_migrations()

        with (
            app.context.acquire_geoloc_db_conn() as app.state.services.geoloc_db,
            app.context.acquire_datadog_client() as app.state.services.datadog,
        ):
            # prepare our ram caches, populating from sql where necessary.
            # this includes channels, clans, mappools, bot info, etc.
            async with app.state.services.database.connection() as db_conn:
                await app.objects.collections.initialize_ram_caches(db_conn)  # type: ignore

            # initialize housekeeping tasks to automatically manage
            # and ensure memory on ram & disk are kept up to date.
            await bg_loops.initialize_housekeeping_tasks()

            # handle signals so we can ensure a graceful shutdown
            sig_handler = app.utils.shutdown_signal_handler
            for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                app.state.loop.add_signal_handler(signum, sig_handler, signum)

            # TODO: restart signal handler with SIGUSR1

            # run the server, handling connections
            # until a termination signal is received.
            if exit_code := await run_server():
                return exit_code

            # we want to attempt to gracefully finish any ongoing connections
            # and shut down any of the housekeeping tasks running in the background.

            if app.state.sessions.ongoing_connections:
                await app.utils.await_ongoing_connections(timeout=5.0)

            await app.utils.cancel_housekeeping_tasks()

    return 0


if __name__ == "__main__":
    """After basic safety checks, start the event loop and call our async entry point."""
    app.utils.setup_runtime_environment()

    for safety_check in (
        app.utils.ensure_supported_platform,  # linux only at the moment
        app.utils.ensure_local_services_are_running,  # mysql (if local)
        app.utils.ensure_directory_structure,  # .data/ & achievements/ dir structure
        app.utils.ensure_dependencies_and_requirements,  # submodules & oppai-ng built
    ):
        if (exit_code := safety_check()) != 0:
            raise SystemExit(exit_code)

    """ Server should be safe to start """

    # TODO: where to store this
    # boot_time = datetime.now()

    # install any debugging hooks from
    # _testing/runtime.py, if present
    app.utils._install_debugging_hooks()

    # check our internet connection status
    has_internet = app.utils.check_connection(timeout=1.5)

    if not has_internet:
        log("No internet connection found, expect lacking functionality.", Ansi.LYELLOW)

    # show info & any contextual warnings.
    app.utils.display_startup_dialog()

    try:
        # use uvloop if available
        # https://github.com/MagicStack/uvloop
        import uvloop

        uvloop.install()
    except ModuleNotFoundError:
        pass

    raise SystemExit(asyncio.run(main()))

elif __name__ == "main":
    # check specifically for ASGI servers; many related projects use
    # them to run in production, and devs may assume we do as well.
    if app.utils.running_via_asgi_webserver():
        raise RuntimeError(
            "gulag implements it's own web framework implementation from "
            "transport layer (tcp/ip) posix sockets and does not rely on "
            "an ASGI server to serve connections; run it directy, `./main.py`",
        )
    else:
        raise RuntimeError("gulag should only be run directly, `./main.py`")
