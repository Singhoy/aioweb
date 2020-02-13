import asyncio
import json
import logging
import os
import time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static

logging.basicConfig(level=logging.INFO)


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return "1分钟前"
    if delta < 3600:
        return f"{delta // 60}分钟前"
    if delta < 86400:
        return f"{delta // 3600}小时前"
    if delta < 604800:
        return f"{delta // 86400}天前"
    dt = datetime.fromtimestamp(t)
    return f"{dt.year}年{dt.month}月{dt.day}日"


def init_jinja2(app, **kwargs):
    logging.info("Init jinja2...")
    options = dict(
        autoescape=kwargs.get("autoescape", True),
        block_start_string=kwargs.get("block_start_string", "{%"),
        block_end_string=kwargs.get("block_end_string", "%}"),
        variable_start_string=kwargs.get("variable_start_string", "{{"),
        variable_end_string=kwargs.get("variable_end_string", "}}"),
        auto_reload=kwargs.get("auto_reload", True)
    )
    path = kwargs.get("path", None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    logging.info(f"Set jinja2 template path: {path}")
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kwargs.get("filters", None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app["__templating__"] = env


async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == "POST":
            if request.content_type.startswith("application/json"):
                request.__data__ = await request.json()
                logging.info(f"Request json: {str(request.__data__)}")
            elif request.content_type.startswith("application/x-www-form-urlencoded"):
                request.__data__ = await request.post()
                logging.info(f"Request form: {request.__data__}")
        return await handler(request)

    return parse_data


async def init(loop):
    await orm.create_pool(loop=loop, host="127.0.0.1", port=3306, user="www", password="123", db="aioweb")
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory
    ])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, "handlers")
    add_static(app)
    srv = await loop.create_server(app.make_handler(), "127.0.0.1", 9527)
    logging.info("Server started at http:127.0.0.1:9527...")
    return srv


async def logger_factory(app, handler):
    async def logger(request):
        # 记录日志
        logging.info(f"Request: {request.method} {request.path}")
        # 继续处理请求
        return await handler(request)

    return logger


async def response_factory(app, handler):
    async def response(request):
        logging.info("Response handler...")
        # 结果
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = "application/octet-stream"
            return resp
        if isinstance(r, str):
            if r.startswith("redirect:"):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode("utf8"))
            resp.content_type = "text/html;charset=utf-8"
            return resp
        if isinstance(r, dict):
            template = r.get("__template__")
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode("utf8"))
                resp.content_type = "application/json;charset=utf-8"
                return resp
            else:
                resp = web.Response(body=app["__templating__"].get_template(template).render(**r).encode("utf8"))
                resp.content_type = "text/html;charset=utf-8"
                return resp
        if isinstance(r, int) and 100 <= r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(r, int) and 100 <= r < 600:
                return web.Response(t, str(m))
        resp = web.Response(body=str(r).encode("utf8"))
        resp.content_type = "text/plain;charset=utf-8"
        return resp

    return response


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init(loop))
    loop.run_forever()


if __name__ == '__main__':
    main()
