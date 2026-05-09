import os

ignore_Node = ["StartPoint", "exit"]


def Init_File():
    open('./Generation.py', "w").close()


def uninit_File():
    os.remove('./Generation.py')


def Add_Code(label_name, pin, value, IndentCounter):
    if label_name in ignore_Node:
        return None, IndentCounter

    indent = "   " * IndentCounter

    with open("Generation.py", "a", encoding="utf-8") as f:
        if label_name in ("IntValue", "FloatValue"):
            f.write(f"{indent}{value[1]} = {(value[2])}\n")
            return value[1], IndentCounter

        elif label_name == "StringValue":
            f.write(f"{indent}{value[1]} = {repr(value[2])}\n")
            return value[1], IndentCounter

        elif label_name == "MagicString":
            return f'"{value[0]}"', IndentCounter

        elif label_name == "BoolValue":
            if value[2] == 0:
                f.write(f"{indent}{value[1]} = False\n")
                return value[1], IndentCounter
            elif value[2] == 1:
                f.write(f"{indent}{value[1]} = True\n")
                return value[1], IndentCounter


        elif label_name == "plus":
            if isinstance(value[0], str) or isinstance(value[1], str):
                return None, IndentCounter
            f.write(f"{indent}{value[0]} += {(value[1])}\n")
            return value[0], IndentCounter

        elif label_name == "minus":
            f.write(f"{indent}{value[0]} -= {(value[1])}\n")
            return value[0], IndentCounter

        elif label_name == "multiplication":
            f.write(f"{indent}{value[0]} *= {(value[1])}\n")
            return value[0], IndentCounter

        elif label_name == "division":
            f.write(f"{indent}{value[0]} /= {(value[1])}\n")
            return value[0], IndentCounter

        elif label_name == "Value":
            return value[1], IndentCounter

        elif label_name == "UseFunction":
            if value[1] == "System":
                f.write(f"{indent}{value[3]} = {value[2]}({value[3]})\n")
            else:
                f.write(f"{indent}{value[3]} = {value[1]}.{value[2]}({value[3]})\n")
            return value[3], IndentCounter

        elif label_name == "Import":
            import_text = f"import {value[0]}\n"
            with open("Generation.py", "r", encoding="utf-8") as r:
                original = r.read()
            with open("Generation.py", "w", encoding="utf-8") as w:
                w.write(import_text + original)
            return None, IndentCounter

        elif label_name == "If":
            f.write(f"{indent}if {value[0]} {value[2]} {value[1]}:\n")
            return None, IndentCounter + 1

        elif label_name == "Print":
            f.write(f"{indent}print({value[1]})\n")
            return None, IndentCounter

    return None, IndentCounter
