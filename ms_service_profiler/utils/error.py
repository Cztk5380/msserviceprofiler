class ExportError(Exception):
    def __init__(self, message):
        super().__init__(message)  # 调用父类的构造函数
        self.message = message

    def __str__(self):
        return f"ExportError: {self.message}"


class ParseError(Exception):
    def __init__(self, message):
        super().__init__(message)  # 调用父类的构造函数
        self.message = message

    def __str__(self):
        return f"ParseError: {self.message}"


class DataFrameMissingError(ParseError):
    def __init__(self, key, message="Failed to read dataframe"):
        # 调用父类的构造函数初始化异常消息
        super().__init__(message)
        self.key = key  # 错误发生的路径
        self.message = message  # 错误的详细信息

    def __str__(self):
        # 返回详细的错误信息
        return f"{self.message}: {self.key} not exists."


class MessageError(ParseError):
    pass

class DatabaseError(Exception):
    """数据库相关错误"""
    pass

class ValidationError(ParseError):
    """数据验证错误"""
    pass


class KeyMissingError(ParseError):
    def __init__(self, key, message="Failed to parse data"):
        # 调用父类的构造函数初始化异常消息
        super().__init__(message)
        self.key = key  # 错误发生的路径
        self.message = message  # 错误的详细信息

    def __str__(self):
        # 返回详细的错误信息
        return f"{self.message}: {self.key} not exists."


class LoadDataError(ParseError):
    def __init__(self, path, message="Failed to load data"):
        # 调用父类的构造函数初始化异常消息
        super().__init__(message)
        self.path = path  # 错误发生的路径
        self.message = message  # 错误的详细信息

    def __str__(self):
        # 返回详细的错误信息
        return f"{self.message}: {self.path}"


