"""Url Handlers"""
import time

from coroweb import get
from models import User, Blog


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
