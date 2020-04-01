"""Url Handlers"""
import hashlib
import json
import logging
import re
import time

from aiohttp import web

from apis import APIValueError, APIError
from config import configs
from coroweb import get, post
from models import User, Blog, next_id

_COOKIE_KEY = configs.session.secret
COOKIE_NAME = "aw_session"
_COOKIE_TIMEOUT = 60 * 60 * 24
_RE_EMAIL = re.compile(r"^[a-z0-9.\-_]+@[a-z0-9\-_]+([.a-z0-9\-_]+){1,4}$")
_RE_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SESSION_TIMEOUT = 60 * 60 * 24


@get("/")
async def index(request):
    summary = "Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    blogs = [
        Blog(id="1", name="Test Blog", summary=summary, created_at=time.time() - 60 * 2),
        Blog(id="2", name="Something New", summary=summary, created_at=time.time() - 60 * 60),
        Blog(id="3", name="Learn Swift", summary=summary, created_at=time.time() - 60 * 60 * 2)
    ]
    return {
        "__template__": "blogs.html",
        "blogs": blogs
    }


@get('/api/users')
async def api_get_users():
    users = await User.find_all(order_by='created_at desc')
    for u in users:
        u.pwd = "******"
    return dict(users=users)


@get('/login')
def login():
    return {
        "__template__": "login.html"
    }


@get('/logout')
def logout(request):
    referer = request.headers.get("Referer")
    r = web.HTTPFound(referer or "/")
    r.set_cookie(COOKIE_NAME, "-deleted-", max_age=0, httponly="True")
    logging.info("user logout.")
    return r


@get('/register')
def register():
    return {
        "__template__": "register.html"
    }


@post("/api/authenticate")
async def authenticate(*, email, pwd):
    if not email:
        raise APIValueError("email", "Invalid email.")
    if not pwd:
        raise APIValueError("password", "Invalid password.")
    users = await User.find_all("email=?", [email])
    if len(users) == 0:
        raise APIValueError("email", "Email not exist.")
    user = users[0]
    # 校验密码
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode("utf-8"))
    sha1.update(b":")
    sha1.update(pwd.encode("utf-8"))
    if user.pwd != sha1.hexdigest():
        raise APIValueError("password", "Invalid password.")
    # 校验通过，生成cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, _COOKIE_TIMEOUT), max_age=_SESSION_TIMEOUT, httponly="True")
    user.pwd = "123123"
    r.content_type = "application/json"
    r.body = json.dumps(user, ensure_ascii=False).encode("utf-8")
    return r


@post("/api/users")
async def api_register_user(*, email, name, pwd):
    if not name or not name.strip():
        raise APIValueError("name")
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError("email")
    if not pwd or not _RE_SHA1.match(pwd):
        raise APIValueError("password")
    users = await User.find_all("email=?", [email])
    if len(users) > 0:
        raise APIError("register: failed", "email", "Email is already in use.")
    uid = next_id()
    sha1_pwd = f"{uid}:{pwd}"
    user = User(id=uid, name=name.strip(), email=email, pwd=hashlib.sha1(sha1_pwd.encode("utf-8")).hexdigest(),
                image=f"http://www.gravatar.com/avatar/{hashlib.md5(email.encode('utf-8')).hexdigest()}?d=mm&s=120")
    await user.save()
    # 生成session
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, _COOKIE_TIMEOUT), max_age=_SESSION_TIMEOUT, httponly="True")
    user.pwd = "123123"
    r.content_type = "application/json"
    r.body = json.dumps(user, ensure_ascii=False).encode("utf-8")
    return r


async def cookie2user(cookie_str):
    """
    分析cookie，如果cookie有效则加载用户
    :param cookie_str: cookie字符串
    :return: 无或user对象
    """
    if not cookie_str:
        return None
    try:
        lis = cookie_str.split("-")
        if len(lis) != 3:
            return None
        uid, expires, sha1 = lis
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = f"{uid}-{user.pwd}-{expires}-{_COOKIE_KEY}"
        if sha1 != hashlib.sha1(s.encode("utf-8")).hexdigest():
            logging.info("Invalid sha1")
            return None
        user.pwd = "******"
        return user
    except Exception as e:
        logging.exception(e)
        return None


def user2cookie(user, max_age):
    """
    根据用户(id-expires-sha1)生成cookie
    :param user: 用户对象
    :param max_age: cookie有效期
    :return: cookie字符串
    """
    expires = str(int(time.time() + max_age))
    s = f"{user.id}-{user.pwd}-{expires}-{_COOKIE_KEY}"
    lis = [user.id, expires, hashlib.sha1(s.encode("utf-8")).hexdigest()]
    return "-".join(lis)
