import customtkinter as ctk
from functools import wraps
from db.database import TableSchema, TableField, ColumnType


# Декоратор для обработки ошибок
def catch_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_message = f"Произошла ошибка: {str(e)}"
            args[0].show_error_message(error_message)  # Выводим сообщение через метод show_error_message

    return wrapper


class TableEditorApp(ctk.CTk):
    def __init__(self, db_manager):
        super().__init__()

        self.db_manager = db_manager
        self.selected_table = None
        self.field_entries = []

        self.title("Редактор таблиц")
        self.geometry("900x650")

        # Левая панель с таблицами
        self.left_frame = ctk.CTkFrame(self, width=200, corner_radius=10)
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)

        # Правая панель для редактирования полей
        self.right_frame = ctk.CTkFrame(self, corner_radius=10)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # Кнопка для загрузки списка таблиц
        self.load_tables_button = ctk.CTkButton(self.left_frame, text="Загрузить таблицы", command=self.load_tables)
        self.load_tables_button.pack(pady=10)

        # Контейнер для радиокнопок (список таблиц)
        self.table_radio_var = ctk.StringVar()
        self.tables_frame = ctk.CTkFrame(self.left_frame, corner_radius=5)
        self.tables_frame.pack(fill="y", expand=True)

        # Кнопки для управления
        self.add_table_button = ctk.CTkButton(self.right_frame, text="Добавить новую таблицу",
                                              command=self.add_new_table)
        self.add_table_button.pack(side="top", pady=10)

        self.edit_table_button = ctk.CTkButton(self.right_frame, text="Редактировать выбранную таблицу",
                                               command=self.edit_table)
        self.edit_table_button.pack(side="top", pady=10)

        self.delete_table_button = ctk.CTkButton(self.right_frame, text="Удалить выбранную таблицу",
                                                 command=self.delete_table)
        self.delete_table_button.pack(side="top", pady=10)

        # Поле для отображения выбранной таблицы и ее полей
        self.fields_frame = ctk.CTkFrame(self.right_frame, corner_radius=5)
        self.fields_frame.pack(fill="both", expand=True)

        # Кнопки для сохранения и отмены изменений
        self.save_button = None
        self.cancel_button = None

        # Кнопка для добавления нового поля при редактировании таблицы
        self.add_field_button = None

        # Поле для отображения ошибок
        self.error_frame = ctk.CTkFrame(self.right_frame, corner_radius=5)
        self.error_textbox = ctk.CTkTextbox(self.error_frame, height=60, wrap="word")
        self.error_textbox.pack(expand=True, fill="both", padx=5, pady=5)
        self.error_frame.pack(fill="x", padx=10, pady=5)
        self.error_frame.pack_forget()  

    def show_info_message(self, message):
        """Метод для вывода информационного сообщения"""
        self.error_textbox.configure(fg_color="green", text_color="white")
        self.error_textbox.delete("1.0", "end")
        self.error_textbox.insert("1.0", message)
        self.error_frame.pack(fill="x", padx=10, pady=5)

    def show_error_message(self, message):
        """Метод для вывода сообщения об ошибке"""
        self.error_textbox.configure(fg_color="red", text_color="white")
        self.error_textbox.delete("1.0", "end")
        self.error_textbox.insert("1.0", message)
        self.error_frame.pack(fill="x", padx=10, pady=5)

    @catch_errors
    def load_tables(self):
        for widget in self.tables_frame.winfo_children():
            widget.destroy()

        tables = self.db_manager.get_tables()  

        for table_name in tables:
            radio_button = ctk.CTkRadioButton(self.tables_frame, text=table_name, variable=self.table_radio_var,
                                              value=table_name)
            radio_button.pack(anchor="w", padx=10, pady=5)

        if tables:
            self.table_radio_var.set(tables[0])  # По умолчанию выбираем первую таблицу

    @catch_errors
    def edit_table(self):
        selected_table = self.table_radio_var.get()
        if selected_table:
            self.show_table_form(selected_table)
        else:
            self.show_error_message("Не выбрана таблица для редактирования")

    def show_table_form(self, table_name):
        for widget in self.fields_frame.winfo_children():
            widget.destroy()

        self.field_entries.clear()

        columns = self.db_manager.get_table_fields(table_name)

        for col_name, col_type, is_nullable, is_primary in columns:
            if isinstance(col_type, ColumnType):
                type_str = col_type.value
            elif isinstance(col_type, str):
                type_str = col_type
            else:
                type_str = str(col_type)

            available_types = ["INTEGER", "FLOAT", "VARCHAR(255)", "DATE"]
            if type_str not in available_types:
                type_mapping = {
                    'integer': 'INTEGER',
                    'double precision': 'FLOAT',
                    'character varying': 'VARCHAR(255)',
                    'timestamp': 'DATE'
                }
                type_str = type_mapping.get(type_str.lower(), 'VARCHAR(255)')

            self.add_field(col_name, type_str, is_primary)

        if not self.add_field_button or not self.add_field_button.winfo_exists():
            self.add_field_button = ctk.CTkButton(
                self.fields_frame,
                text="Добавить столбец",
                command=self.add_new_field
            )
            self.add_field_button.pack(pady=10)

        self.show_save_cancel_buttons()

    @catch_errors
    def add_new_table(self):
        for widget in self.fields_frame.winfo_children():
            widget.destroy()

        self.field_entries.clear()

        self.new_table_name_entry = ctk.CTkEntry(self.fields_frame, placeholder_text="Имя новой таблицы")
        self.new_table_name_entry.pack(pady=10)

        self.add_field()

        if not self.add_field_button:
            self.add_field_button = ctk.CTkButton(self.fields_frame, text="Добавить поле", command=self.add_field)
            self.add_field_button.pack(pady=10)

        save_table_button = ctk.CTkButton(self.fields_frame, text="Создать таблицу", command=self.save_new_table)
        save_table_button.pack(pady=10)

        self.show_save_cancel_buttons()

    def add_field(self, field_name="", field_type="VARCHAR(255)", is_primary=False):
        field_frame = ctk.CTkFrame(self.fields_frame, corner_radius=5)
        field_frame.pack(fill="x", padx=10, pady=5)

        field_name_entry = ctk.CTkEntry(field_frame, width=200, placeholder_text="Имя поля")
        field_name_entry.pack(side="left", padx=5)
        field_name_entry.insert(0, field_name)

        available_types = ["INTEGER", "FLOAT", "VARCHAR(255)", "DATE"]

        field_type_menu = ctk.CTkOptionMenu(
            field_frame,
            values=available_types
        )
        field_type_menu.pack(side="left", padx=5)

        if field_type in available_types:
            field_type_menu.set(field_type)
        else:
            field_type_menu.set(available_types[0])

        primary_key_var = ctk.CTkCheckBox(field_frame, text="Primary", onvalue=True, offvalue=False)
        primary_key_var.pack(side="left", padx=5)
        if is_primary:
            primary_key_var.select()

        delete_field_button = ctk.CTkButton(
            field_frame,
            text="Удалить",
            command=lambda: self.delete_field_from_form(field_frame)
        )
        delete_field_button.pack(side="right", padx=5)

        self.field_entries.append((field_name_entry, field_type_menu, primary_key_var))

    def delete_field_from_form(self, field_frame):
        field_frame.destroy()
        self.field_entries = [(name, type, primary) for name, type, primary in self.field_entries if
                              name.master.winfo_exists()]

    @catch_errors
    def save_new_table(self):
        table_name = self.new_table_name_entry.get()
        if not table_name:
            self.show_error_message("Имя таблицы не может быть пустым")
            return

        fields = {}
        for field_entry in self.field_entries:
            field_name = field_entry[0].get()
            field_type = ColumnType(field_entry[1].get())
            is_primary = field_entry[2].get()
            fields[field_name] = TableField(name=field_name, type=field_type, is_primary=is_primary)

        try:
            schema = TableSchema(name=table_name, fields=fields)
            self.db_manager.create_table_with_fields(schema)
            self.show_info_message(f"Таблица '{table_name}' создана.")
            self.load_tables()

            for widget in self.fields_frame.winfo_children():
                widget.destroy()
            self.field_entries.clear()

        except ValueError as e:
            self.show_error_message(str(e))
    ##

    @catch_errors
    def add_new_field(self):
        """Добавление нового поля только если оно не существует"""
        new_field_name = f"Field_{len(self.field_entries) + 1}"

        existing_field_names = {entry[0].get() for entry in self.field_entries}

        while new_field_name in existing_field_names:
            new_field_name = f"{new_field_name}_1"

        self.add_field(new_field_name)


    @catch_errors
    def delete_table(self):
        selected_table = self.table_radio_var.get()
        if selected_table:
            self.db_manager.delete_table(selected_table)
            self.load_tables()
            self.show_error_message(f"Таблица '{selected_table}' удалена.")
        else:
            self.show_error_message("Не выбрана таблица для удаления")

    @catch_errors
    def delete_field(self, field_name):
        selected_table = self.table_radio_var.get()
        if selected_table:
            self.db_manager.delete_column(selected_table, field_name)
            self.show_table_form(selected_table)  # Перезагрузка формы для отображения изменений
            self.show_error_message(f"Поле '{field_name}' удалено из таблицы '{selected_table}'.")
        else:
            self.show_error_message("Не выбрана таблица для удаления поля")

    def show_save_cancel_buttons(self):
        if not self.save_button:
            self.save_button = ctk.CTkButton(self.right_frame, text="Сохранить изменения", command=self.save_changes)
            self.save_button.pack(side="left", padx=5, pady=5)

        if not self.cancel_button:
            self.cancel_button = ctk.CTkButton(self.right_frame, text="Отменить изменения", command=self.cancel_changes)
            self.cancel_button.pack(side="right", padx=5, pady=5)

#####

    @catch_errors
    def save_changes(self):
        selected_table = self.table_radio_var.get()
        if not selected_table:
            self.show_error_message("Не выбрана таблица для сохранения изменений")
            return

        primary_key_count = sum(1 for field_entry in self.field_entries if field_entry[2].get())

        if primary_key_count > 1:
            self.show_error_message("Таблица не может иметь несколько первичных ключей")
            return

        if primary_key_count == 0:
            current_fields = self.db_manager.get_table_fields(selected_table)
            has_existing_primary = any(field[3] for field in current_fields)

            if not has_existing_primary:
                response = self.show_yes_no_dialog(
                    "Предупреждение",
                    "Таблица не имеет первичного ключа. Продолжить?"
                )
                if not response:
                    return

        try:
            current_fields = self.db_manager.get_table_fields(selected_table)
            current_field_names = [field[0] for field in current_fields]
            new_field_names = [field_entry[0].get() for field_entry in self.field_entries]

            if any(field[3] for field in current_fields):
                self.db_manager.remove_primary_key(selected_table)

            for field_name in current_field_names:
                if field_name not in new_field_names:
                    self.db_manager.delete_column(selected_table, field_name)

            for field_entry in self.field_entries:
                field_name = field_entry[0].get()
                new_type = ColumnType(field_entry[1].get())

                if field_name not in current_field_names:
                    self.db_manager.add_column(selected_table, field_name, new_type.value)
                else:
                    current_type = next(field[1] for field in current_fields if field[0] == field_name)
                    if new_type != current_type:
                        try:
                            self.db_manager.alter_column_type_with_using(
                                table_name=selected_table,
                                column_name=field_name,
                                new_type=new_type.value
                            )
                        except Exception as e:
                            if "USING" in str(e):
                                response = self.show_yes_no_dialog(
                                    "Предупреждение",
                                    f"Невозможно автоматически преобразовать тип столбца '{field_name}'. Хотите выполнить принудительное преобразование?"
                                )
                                if response:
                                    self.db_manager.force_alter_column_type(
                                        table_name=selected_table,
                                        column_name=field_name,
                                        new_type=new_type.value
                                    )
                                else:
                                    raise e
                            else:
                                raise e

            for field_entry in self.field_entries:
                if field_entry[2].get():  
                    self.db_manager.add_primary_key(
                        table_name=selected_table,
                        column_name=field_entry[0].get()
                    )
                    break  

            self.show_info_message(f"Изменения в таблице '{selected_table}' сохранены.")
            self.show_table_form(selected_table)  

        except Exception as e:
            self.db_manager.rollback_transaction()
            self.show_error_message(f"Ошибка при сохранении изменений: {str(e)}")

    def handle_column_conversion_error(self, error_message, table_name):
        column_name = error_message.split('"')[1]
        new_type = error_message.split("::")[1].strip()

        response = self.show_yes_no_dialog(
            "Ошибка конвертации типа",
            f"Возникла проблема при конвертации столбца '{column_name}' в тип {new_type}.\n"
            "Хотите попробовать выполнить конвертацию с потенциальной потерей данных?"
        )

        if response:
            try:
                self.db_manager.alter_column_type_with_using(
                    table_name=table_name,
                    column_name=column_name,
                    new_type=new_type.rstrip('",.')  
                )
                self.show_info("Успех", f"Столбец '{column_name}' успешно сконвертирован в тип {new_type}.")
            except Exception as e:
                self.show_error("Ошибка", f"Ошибка при конвертации: {str(e)}")
        else:
            self.show_info("Информация", "Операция отменена.")

    def cancel_changes(self):
        selected_table = self.table_radio_var.get()
        if selected_table:
            try:
                self.db_manager.rollback_transaction()

                self.show_table_form(selected_table)

                self.show_info_message("Изменения отменены.")
            except Exception as e:
                self.show_error_message(f"Ошибка при отмене изменений: {str(e)}")
        else:
            self.show_info_message("Нет выбранной таблицы для отмены изменений.")

    def show_yes_no_dialog(self, title, message):
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("300x150")
        dialog.resizable(False, False)

        label = ctk.CTkLabel(dialog, text=message, wraplength=250)
        label.pack(pady=10)

        result = ctk.BooleanVar()

        def on_yes():
            result.set(True)
            dialog.destroy()

        def on_no():
            result.set(False)
            dialog.destroy()

        yes_button = ctk.CTkButton(dialog, text="Да", command=on_yes)
        yes_button.pack(side="left", padx=20, pady=10)

        no_button = ctk.CTkButton(dialog, text="Нет", command=on_no)
        no_button.pack(side="right", padx=20, pady=10)

        dialog.grab_set()  
        self.wait_window(dialog)

        return result.get()

    def show_info(self, title, message):
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("400x320")
        dialog.resizable(False, False)

        label = ctk.CTkLabel(dialog, text=message, wraplength=250)
        label.pack(pady=10)

        ok_button = ctk.CTkButton(dialog, text="OK", command=dialog.destroy)
        ok_button.pack(pady=10)

        dialog.grab_set()
        self.wait_window(dialog)

    def show_error(self, title, message):
        self.show_info(title, message)
