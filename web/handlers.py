"""Url Handlers"""
import hashlib
import json
import logging
import re
import time

from aiohttp import web

import markdown2
from apis import APIValueError, APIError, APIPermissionError, Page
from config import configs
from coroweb import get, post
from models import User, Blog, next_id, Comment

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


@get("/api/blogs")
async def api_blogs(*, page="1"):
    page_index = get_page_index(page)
    num = await Blog.find_number("count(id)")
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = await Blog.find_all(order_by="created_at desc", limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)


@get("/api/blogs/{id}")
async def api_get_blog(*, _id):
    return await Blog.find(_id)


@get('/api/users')
async def api_get_users():
    users = await User.find_all(order_by='created_at desc')
    for u in users:
        u.pwd = "123123"
    return dict(users=users)


@get("/blog/{id}")
async def get_blog(_id):
    blog = await Blog.find(_id)
    comments = await Comment.find_all("blog_id=?", [_id], order_by="created_at desc")
    for _ in comments:
        _.html_content = text2html(_.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        "__template__": "blog.html",
        "blog": blog,
        "comments": comments
    }


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


@get("/manage/blogs")
def manage_blogs(*, page="1"):
    return {
        "__template__": "manage_blogs.html",
        "page_index": get_page_index(page)
    }


@get("/manage/blogs/create")
def manage_create_blog():
    return {
        "__template__": "manage_blog_edit.html",
        "id": "",
        "action": "/api/blogs"
    }


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


@post("/api/blogs")
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError("name", "name cannot be empty.")
    if not summary or not summary.strip():
        raise APIValueError("summary", "summary cannot be empty.")
    if not content or not content.strip():
        raise APIValueError("content", "content cannot be empty.")
    blog = Blog(
        user_id=request.__user__.id,
        suer_name=request.__user__.name,
        user_image=request.__user__.image,
        name=name.strip(),
        summary=summary.strip(),
        content=content.strip()
    )
    await blog.save()
    return blog


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
        user.pwd = "123123"
        return user
    except Exception as e:
        logging.exception(e)
        return None


def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()


def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as v:
        pass
    return p if p > 1 else 1


def text2html(text):
    return "".join(
        map(
            lambda s: f"<p>{s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</p>",
            filter(lambda s: s.strip() != "", text.split("\n"))
        )
    )


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
