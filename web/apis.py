class APIError(Exception):
    """API错误基类，包括错误（必须），数据（可选）和消息（可选）"""

    def __init__(self, error, data='', message=''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message


class APIValueError(APIError):
    """输入值有误或无效。指定表单输入错误段"""

    def __init__(self, field, message=''):
        super(APIValueError, self).__init__("value: invalid", field, message)


class APIResourceNotFoundError(APIError):
    """找不到资源。指定数据资源名称"""

    def __init__(self, field, message=''):
        super(APIResourceNotFoundError, self).__init__("value:notfound", field, message)


class APIPermissionError(APIError):
    """api没有权限"""

    def __init__(self, message=''):
        super(APIPermissionError, self).__init__("permission:forbidden", "permission", message)


class Page(object):
    def __init__(self, item_count, page_index=1, page_size=10):
        self.item_count = item_count
        self.page_size = page_size
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
        if (item_count == 0) or (page_index > self.page_count):
            self.offset = 0
            self.limit = 0
            self.page_index = 1
        else:
            self.page_index = page_index
            self.offset = self.page_size * (page_index - 1)
            self.limit = self.page_size
        self.has_next = self.page_index < self.page_count
        self.has_previous = self.page_index > 1

    def __str__(self):
        return f"item_count: {self.item_count}, page_count: {self.page_count}, page_index: {self.page_index}, " \
               f"page_size: {self.page_size}, offset: {self.offset}, limit: {self.limit} "

    __repr__ = __str__
