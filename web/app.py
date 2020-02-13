import asyncio
import logging

from aiohttp import web

logging.basicConfig(level=logging.INFO)


def index(request):
    return web.Response(body=b"<h1>Hello Word!</h1>", headers={"content-type": "text/html"})


async def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route("GET", "/", index)
    srv = await loop.create_server(app.make_handler(), "127.0.0.1", 9527)
    logging.info("Server Started at http://127.0.0.1:9527...")
    return srv


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init(loop))
    loop.run_forever()


if __name__ == '__main__':
    main()
