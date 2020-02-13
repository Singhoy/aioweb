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
