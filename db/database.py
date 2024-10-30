import psycopg2
from psycopg2 import sql
import logging
from pydantic import BaseModel, Field, validator
from typing import Dict
from enum import Enum

# Настройка логирования
logging.basicConfig(level=logging.INFO, filename='db.log')


class ColumnType(str, Enum):
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    VARCHAR = "VARCHAR(255)"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    NUMERIC = "NUMERIC"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
    CHARACTER_VARYING = "CHARACTER VARYING(255)"

    @classmethod
    def from_postgres_type(cls, pg_type: str) -> 'ColumnType':
        type_mapping = {
            'integer': cls.INTEGER,
            'double precision': cls.FLOAT,
            'character varying': cls.CHARACTER_VARYING,
            'varchar': cls.VARCHAR,
            'date': cls.DATE,
            'timestamp': cls.TIMESTAMP,
            'numeric': cls.NUMERIC,
            'text': cls.TEXT,
            'boolean': cls.BOOLEAN
        }
        return type_mapping.get(pg_type.lower(), cls.TEXT)


class DatabaseConfig(BaseModel):
    host: str
    port: int
    dbname: str
    user: str
    password: str


class TableField(BaseModel):
    name: str
    type: ColumnType
    is_primary: bool = False
    is_nullable: bool = True

    @validator('name')
    def validate_name(cls, v):
        # Заменяем пробелы на подчеркивания и удаляем недопустимые символы
        valid_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in v)
        # Если имя начинается с цифры, добавляем префикс
        if valid_name[0].isdigit():
            valid_name = 'f_' + valid_name
        return valid_name


class TableSchema(BaseModel):
    name: str
    fields: Dict[str, TableField]

    @validator('name')
    def validate_table_name(cls, v):
        if not v.isidentifier():
            raise ValueError(f"Invalid table name: {v}")
        return v


class Database:
    def __init__(self, config: DatabaseConfig):
        self.config = config.dict()
        self.connection = None
        self.cursor = None
        self.connect()

    def connect(self):
        try:
            self.connection = psycopg2.connect(**self.config)
            self.cursor = self.connection.cursor()
            logging.info("Connected to the database")
        except Exception as e:
            logging.error(f"Error connecting to the database: {e}")
            raise

    def close(self):
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
                logging.info("Database connection closed")
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")
            raise

    def reopen_cursor(self):
        try:
            if self.cursor and not self.cursor.closed:
                self.cursor.close()
            self.cursor = self.connection.cursor()
        except Exception as e:
            logging.error(f"Error reopening cursor: {e}")
            raise

    def execute_query(self, query: str, params=None):
        self.reopen_cursor()
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logging.error(f"Error executing query: {e}")
            raise

    def get_tables(self):
        self.reopen_cursor()
        try:
            self.cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema='public'
                ORDER BY table_name
            """)
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error fetching tables: {e}")
            raise

    def get_table_fields(self, table_name):
        self.reopen_cursor()
        try:
            query = sql.SQL("""
                SELECT 
                    c.column_name, 
                    c.data_type, 
                    c.is_nullable,
                    CASE WHEN pk.constraint_name IS NOT NULL THEN true ELSE false END as is_primary
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT ku.column_name, tc.constraint_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage ku
                        ON tc.constraint_name = ku.constraint_name
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                        AND tc.table_name = %s
                ) pk ON c.column_name = pk.column_name
                WHERE c.table_name = %s
                ORDER BY c.ordinal_position
            """)
            self.cursor.execute(query, (table_name, table_name))
            return [
                (row[0],  # name
                 ColumnType.from_postgres_type(row[1]),  # type
                 row[2] == 'YES',  # is_nullable
                 row[3])  # is_primary
                for row in self.cursor.fetchall()
            ]
        except Exception as e:
            logging.error(f"Error fetching fields for table {table_name}: {e}")
            raise

    def create_table_with_fields(self, schema: TableSchema):
        field_definitions = []
        primary_keys = []

        for field_name, field in schema.fields.items():
            field_def = f"{field_name} {field.type.value}"
            if not field.is_nullable:
                field_def += " NOT NULL"
            if field.is_primary:
                primary_keys.append(field_name)
            field_definitions.append(field_def)

        if primary_keys:
            field_definitions.append(f"PRIMARY KEY ({', '.join(primary_keys)})")

        create_query = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
            sql.Identifier(schema.name),
            sql.SQL(", ").join(map(sql.SQL, field_definitions))
        )

        self.execute_query(create_query)

    def update_table(self, table_name, new_fields):
        try:
            current_fields = self.get_table_fields(table_name)

            for new_field in new_fields:
                current_field = next((f for f in current_fields if f[0] == new_field.name), None)

                if current_field:
                    if current_field[1] != new_field.type:
                        query = f"ALTER TABLE {table_name} ALTER COLUMN {new_field.name} TYPE {new_field.type.value}"
                        self.execute_query(query)
                    if new_field.is_primary:
                        query = f"ALTER TABLE {table_name} ADD PRIMARY KEY ({new_field.name})"
                        self.execute_query(query)
                    else:
                        query = f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {table_name}_{new_field.name}_pkey"
                        self.execute_query(query)
                else:
                    query = f"ALTER TABLE {table_name} ADD COLUMN {new_field.name} {new_field.type.value}"
                    self.execute_query(query)

        except Exception as e:
            raise ValueError(str(e))

    def delete_table(self, table_name):
        query = sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table_name))
        self.execute_query(query)

    def delete_column(self, table_name, column_name):
        query = sql.SQL("ALTER TABLE {} DROP COLUMN IF EXISTS {}").format(
            sql. Identifier(table_name),
            sql.Identifier(column_name)
        )
        self.execute_query(query)

    def alter_column_type_with_using(self, table_name, column_name, new_type):
        query = f"""
        ALTER TABLE {table_name}
        ALTER COLUMN {column_name} TYPE {new_type} USING {column_name}::{new_type}
        """
        self.execute_query(query)

    def rollback_transaction(self):
        try:
            if self.connection:
                self.connection.rollback()
        except Exception as e:
            raise DatabaseError(f"Ошибка при откате транзакции: {str(e)}")

    def remove_primary_key(self, table_name):
        query = sql.SQL("ALTER TABLE {} DROP CONSTRAINT IF EXISTS {}"). \
            format(
            sql.Identifier(table_name),
            sql.Identifier(f"{table_name}_pkey")
        )
        self.execute_query(query)

    def add_primary_key(self, table_name, column_name):
        query = sql.SQL("ALTER TABLE {} ADD PRIMARY KEY ({})").format(
            sql.Identifier(table_name),
            sql.Identifier(column_name)
        )
        self.execute_query(query)

    def add_column(self, table_name, column_name, column_type, is_primary=False):
        query = sql.SQL("ALTER TABLE {} ADD COLUMN {} {}").format(
            sql.Identifier(table_name),
            sql.Identifier(column_name),
            sql.SQL(column_type)
        )
        self.execute_query(query)
        if is_primary:
            self.add_primary_key(table_name, column_name)

    def force_alter_column_type(self, table_name, column_name, new_type):
        query = sql.SQL("ALTER TABLE {} ALTER COLUMN {} TYPE {} USING {}::{}"). \
            format(
            sql.Identifier(table_name),
            sql.Identifier(column_name),
            sql.SQL(new_type),
            sql.Identifier(column_name),
            sql.SQL(new_type)
        )
        self.execute_query(query)
