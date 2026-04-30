import os

ignore_Node = ["StartPoint", "exit"]


def Init_File():
    open('./Generation.py', "w").close()


def uninit_File():
    os.remove('./Generation.py')


def Add_Code(label_name, pin, value):
    if label_name in ignore_Node:
        return None

    with open("Generation.py", "a", encoding="utf-8") as f:
        if label_name in ("IntValue", "FloatValue"):
            f.write(f"{value[1]} = {(value[2])}\n")
            return value[1]

        elif label_name == "StringValue":
            f.write(f"{value[1]} = {repr(value[2])}\n")
            return value[1]

        elif label_name == "plus":
            if isinstance(value[0], str):
                return None
            elif isinstance(value[1], str):
                return None

            f.write(f"{value[0]} += {(value[1])}\n")
            return value[0]

        elif label_name == "minus":
            f.write(f"{value[0]} -= {(value[1])}\n")
            return value[0]

        elif label_name == "multiplication":
            f.write(f"{value[0]} *= {(value[1])}\n")
            return value[0]

        elif label_name == "division":
            f.write(f"{value[0]} /= {(value[1])}\n")
            return value[0]

        elif label_name == "Value":
            return value[1]

        elif label_name == 'UseFunction':
            if value[1] == "System":
                f.write(f"{value[3]} = {value[2]}({value[3]})\n")
                return value[3]
            else:
                f.write(f"{value[3]} = {value[1]}.{value[2]}({value[3]})\n")
                return value[3]
        elif label_name == "Import":
            import_text = f"import {value[0]}\n"
            with open("Generation.py", "r", encoding="utf-8") as r:
                original = r.read()
            with open("Generation.py", "w", encoding="utf-8") as w:
                w.write(import_text + original)

            return None
        elif label_name == "Print":
            f.write(f"print({value[0]})\n")
            return None

    return None
