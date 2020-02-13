import logging

import aiomysql


def log(sql, args=()):
    logging.info(f"SQL: {sql}")


async def create_pool(loop, **kwargs):
    logging.info("Creating database connection pool...")
    global __pool
    __pool = await aiomysql.create_pool(
        host=kwargs.get("host", "localhost"),
        port=kwargs.get("port", 3306),
        user=kwargs["user"],
        password=kwargs["password"],
        db=kwargs["db"],
        charset=kwargs.get("charset", "utf8"),
        autocommit=kwargs.get("autocommit", True),
        maxsize=kwargs.get("maxsize", 10),
        minsize=kwargs.get("minsize", 1),
        loop=loop
    )


async def execute(sql, *args, autocommit=True):
    log(sql)
    async with __pool.get() as con:
        if not autocommit:
            await con.begin()
        try:
            async with con.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace("?", "%s"), args)
                affected = cur.rowcount
            if not autocommit:
                await con.commit()
        except BaseException as e:
            if not autocommit:
                await con.rollback()
            raise
        return affected


async def select(sql, args, size=None):
    log(sql, args)
    global __pool
    async with __pool.get() as con:
        async with con.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql.replace("?", "%s"), args or ())
            rs = await cur.fetchmany(size) if size else await cur.fetchall()
        logging.info(f"Rows returned: {len(rs)}")
        return rs


def create_args_string(num):
    lis = []
    for _ in range(num):
        lis.append("?")
    return ", ".join(lis)


class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return f"<{self.__class__.__name__}, {self.column_type}: {self.name}>"


class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, "boolean", False, default)


class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, "bigint", primary_key, default)


class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, "real", primary_key, default)


class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl="varchar(100)"):
        super().__init__(name, ddl, primary_key, default)


class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, "text", False, default)


class ModelMetaclass(type):
    def __new__(mcs, name, bases, attrs):
        if name == "Model":
            return type.__new__(mcs, name, bases, attrs)
        table_name = attrs.get("__table__", None) or name
        logging.info(f"Found model: {name} (table: {table_name})")
        mappings = {}
        fields = []
        primary_key = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info(f"  Found mapping: {k} ==> {v}")
                mappings[k] = v
                if v.primary_key:
                    # 找到主键
                    if primary_key:
                        raise Exception(f"Duplicate primary key for field: {k}")
                    primary_key = k
                else:
                    fields.append(k)
        if not primary_key:
            raise Exception("Primary key not found.")
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map(lambda f: f"`{f}`", fields))
        attrs["__mappings__"] = mappings  # 保存属性和列的映射关系
        attrs["__table__"] = table_name
        attrs["__primary_key__"] = primary_key  # 主键属性名
        attrs["__fields__"] = fields  # 除主键外的属性名
        attrs["__select__"] = f"""select `{primary_key}`, {', '.join(escaped_fields)} from `{table_name}`"""
        attrs["__insert__"] = f"""insert into `{table_name}` ({', '.join(
            escaped_fields)}, `{primary_key}`) values ({create_args_string(len(escaped_fields) + 1)})"""
        attrs["__update__"] = f"""update `{table_name}` set {', '.join(
            map(lambda f: f"`{mappings.get(f).name or f}`=?", fields))} where `{primary_key}`=?"""
        attrs["__delete__"] = f"""delete from `{table_name}` where `{primary_key}`=?"""
        return type.__new__(mcs, name, bases, attrs)


class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kwargs):
        super(Model, self).__init__(**kwargs)

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % item)

    def __setattr__(self, key, value):
        self[key] = value

    def get_value(self, key):
        return getattr(self, key, None)

    def get_value_or_default(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug(f"Using default value for {key}: {str(value)}")
                setattr(self, key, value)
        return value

    @classmethod
    async def find_all(cls, where=None, args=None, **kwargs):
        """ find object by where clause."""
        sql = [cls.__select__]
        if where:
            sql.append("where")
            sql.append(where)
        if args is None:
            args = []
        order_by = kwargs.get("order_by", None)
        if order_by:
            sql.append("order by")
            sql.append(order_by)
        limit = kwargs.get("limit", None)
        if limit is not None:
            sql.append("limit")
            if isinstance(limit, int):
                sql.append("?")
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append("?, ?")
                args.extend(limit)
            else:
                raise ValueError(f"Invalid limit values: {str(limit)}")
        rs = await select(" ".join(sql), args)
        return [cls(**r) for r in rs]

    @classmethod
    async def find_number(cls, select_field, where=None, args=None):
        """ find number by select and where."""
        sql = [f"select {select_field} _num_ from `{cls.__table__}`"]
        if where:
            sql.append("where")
            sql.append(where)
        rs = await select(" ".join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]["_num_"]

    @classmethod
    async def find(cls, pk):
        """ find object by primary key."""
        rs = await select(f"{cls.__select__} where `{cls.__primary_key__}`=?", [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    async def save(self):
        args = list(map(self.get_value_or_default, self.__fields__))
        args.append(self.get_value_or_default(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warning(f"Failed to insert record: affected rows: {rows}")

    async def update_(self):
        args = list(map(self.get_value, self.__fields__))
        args.append(self.get_value(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warning(f"Failed to update by primary key: affected rows: {rows}")

    async def remove(self):
        args = [self.get_value(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warning(f"Failed to remove by primary key: affected rows: {rows}")
