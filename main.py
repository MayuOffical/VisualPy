import io
import json
import os
import subprocess
import sys
import threading

import dearpygui.dearpygui as dpg

import Compiler

dpg.create_context()
Compiler.Init_File()

node_editor_tag = "node_editor"
node_id = 0
current_file = None

node_registry = {}
attr_to_pin = {}
attr_to_node = {}
link_registry = {}
pin_values = {}
variables = {}
all_pins = []
clipboard_nodes = []
console_globals = {"__builtins__": __builtins__}

TYPE_COLORS = {
    "float": [255, 165, 0, 255],
    "int": [100, 200, 255, 255],
    "string": [200, 100, 255, 255],
    "bool": [100, 255, 100, 255],
    "any": [200, 200, 200, 255],
    None: [150, 150, 150, 255],
}


def types_compatible(out_type, in_type):
    if in_type == "any" or out_type == "any":
        return True
    return out_type == in_type


node_type_map = {}


def load_node_definitions(directory="Node"):
    definitions = []
    if not os.path.exists(directory):
        print(f"[警告] '{directory}' ディレクトリが見つかりません")
        return definitions
    for filename in sorted(os.listdir(directory)):
        if filename.endswith(".json"):
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    definitions.append(json.load(f))
            except Exception as e:
                print(f"[エラー] {filename}: {e}")
    return definitions


def add_node(label, InputOn, OutputOn, arg,
             category="", output_type=None, input_type=None, color=None, defn=None, pos=None):
    global node_id
    all_pins = []
    node_id += 1
    node_tag = f"node_{node_id}"
    node_color = color if color else [100, 100, 100]
    input_pins = []
    output_attr_id = None

    if pos is None:
        pos = (425, 300)

    with dpg.node(tag=node_tag, parent=node_editor_tag, label=label, pos=pos):

        with dpg.theme() as node_theme:
            with dpg.theme_component(dpg.mvNode):
                dpg.add_theme_color(dpg.mvNodeCol_TitleBar,
                                    node_color + [255], category=dpg.mvThemeCat_Nodes)
                dpg.add_theme_color(dpg.mvNodeCol_TitleBarHovered,
                                    [min(c + 40, 255) for c in node_color] + [255],
                                    category=dpg.mvThemeCat_Nodes)
                dpg.add_theme_color(dpg.mvNodeCol_TitleBarSelected,
                                    [min(c + 70, 255) for c in node_color] + [255],
                                    category=dpg.mvThemeCat_Nodes)
        dpg.bind_item_theme(node_tag, node_theme)

        if InputOn:
            with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Input) as attr:
                dpg.add_text(f"Input ({input_type})" if input_type else "Input")
                all_pins.append({"type": "input", "attr_id": attr})
                attr_to_pin[attr] = {"node_tag": node_tag, "pin_index": len(all_pins) - 1, "kind": "input"}

        skip_rate = 0
        skip = 0
        for i in range(len(arg)):
            if skip_rate == 1:
                skip = 0
            if arg[i] == 0:
                break
            elif arg[i] == "FloatInput":
                with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Static):
                    widget = dpg.add_input_float(label=arg[i + 1], width=150)
                    all_pins.append({"type": "static", "widget": widget})
                    skip = 1
                    skip_rate = 0
            elif arg[i] == "IntInput":
                with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Static):
                    widget = dpg.add_input_int(label=arg[i + 1], width=150)
                    all_pins.append({"type": "static", "widget": widget})
                    skip = 1
                    skip_rate = 0
            elif arg[i] == "StringInput":
                with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Static):
                    widget = dpg.add_input_text(label=arg[i + 1], width=150)
                    all_pins.append({"type": "static", "widget": widget})
                    skip = 1
                    skip_rate = 0
            else:
                if skip == 0:
                    with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Input) as attr:
                        dpg.add_text(arg[i])
                        all_pins.append({"type": "input", "attr_id": attr})
                        attr_to_pin[attr] = {"node_tag": node_tag, "pin_index": len(all_pins) - 1, "kind": "input"}
                elif skip_rate == 0:
                    skip_rate = 1

        if OutputOn:
            with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Output) as attr:
                dpg.add_text(f"Output ({output_type})" if output_type else "Output")
                output_attr_id = attr
                attr_to_pin[attr] = {"node_tag": node_tag, "pin_index": 0, "kind": "output"}

    node_type_map[node_tag] = {"output_type": output_type, "input_type": input_type}

    node_registry[node_tag] = {
        "id": node_id,
        "label": label,
        "category": category,
        "output_type": output_type,
        "input_type": input_type,
        "input_pins": input_pins,
        "all_pins": all_pins,
        "output_attr": output_attr_id,
        "links_in": [],
        "links_out": [],
        "defn": defn,
    }


def link_callback(sender, app_data):
    out_attr, in_attr = app_data[0], app_data[1]
    link_id = dpg.add_node_link(out_attr, in_attr, parent=sender)

    from_pin = attr_to_pin.get(out_attr, {})
    to_pin = attr_to_pin.get(in_attr, {})
    from_node = from_pin.get("node_tag")
    to_node = to_pin.get("node_tag")
    to_pin_index = to_pin.get("pin_index", 0)

    link_registry[link_id] = {
        "from_node": from_node,
        "from_attr": out_attr,
        "to_node": to_node,
        "to_attr": in_attr,
        "to_pin_index": to_pin_index,
    }

    if from_node and from_node in node_registry:
        node_registry[from_node]["links_out"].append({
            "link_id": link_id, "to_node": to_node, "to_attr": in_attr
        })
    if to_node and to_node in node_registry:
        node_registry[to_node]["links_in"].append({
            "link_id": link_id, "from_node": from_node,
            "from_attr": out_attr, "to_pin_index": to_pin_index
        })


def _remove_link_from_registry(link_id):
    info = link_registry.pop(link_id, None)
    if info is None:
        return
    from_node = info["from_node"]
    to_node = info["to_node"]
    if from_node and from_node in node_registry:
        node_registry[from_node]["links_out"] = [
            l for l in node_registry[from_node]["links_out"] if l["link_id"] != link_id
        ]
    if to_node and to_node in node_registry:
        node_registry[to_node]["links_in"] = [
            l for l in node_registry[to_node]["links_in"] if l["link_id"] != link_id
        ]


def delink_callback(sender, app_data):
    link_id = app_data
    _remove_link_from_registry(link_id)
    dpg.delete_item(link_id)


def delete_selected():
    for node_dpg_id in dpg.get_selected_nodes(node_editor_tag):
        alias = dpg.get_item_alias(node_dpg_id)
        node_tag = alias if alias in node_registry else node_dpg_id

        if node_tag in node_registry:
            info = node_registry[node_tag]
            related_links = (
                    [l["link_id"] for l in info["links_in"]] +
                    [l["link_id"] for l in info["links_out"]]
            )
            for lid in related_links:
                if dpg.does_item_exist(lid):
                    dpg.delete_item(lid)
                _remove_link_from_registry(lid)

            del node_registry[node_tag]
            node_type_map.pop(node_tag, None)

        dpg.delete_item(node_dpg_id)

    for link_id in dpg.get_selected_links(node_editor_tag):
        _remove_link_from_registry(link_id)
        dpg.delete_item(link_id)


def copy_selected():
    global clipboard_nodes
    clipboard_nodes = []
    selected = dpg.get_selected_nodes(node_editor_tag)
    if not selected:
        return
    for node_dpg_id in selected:
        alias = dpg.get_item_alias(node_dpg_id)
        node_tag = alias if alias in node_registry else node_dpg_id
        if node_tag not in node_registry:
            continue
        info = node_registry[node_tag]
        pos = dpg.get_item_pos(node_tag)
        sv = []
        for pin in info["all_pins"]:
            if pin["type"] == "static":
                sv.append(dpg.get_value(pin["widget"]))
            else:
                sv.append(None)
        clipboard_nodes.append({
            "defn": info["defn"],
            "sv": sv,
            "pos": pos,
        })


def paste_nodes():
    if not clipboard_nodes:
        return
    for entry in clipboard_nodes:
        d = entry["defn"]
        old_pos = entry["pos"]
        new_pos = (old_pos[0] + 30, old_pos[1] + 30)
        add_node(
            label=d["label"],
            InputOn=d["InputOn"],
            OutputOn=d["OutputOn"],
            arg=d["arg"],
            category=d.get("category", ""),
            output_type=d.get("output_type"),
            input_type=d.get("input_type"),
            color=d.get("color", [100, 100, 100]),
            defn=d,
            pos=new_pos,
        )
        tag = f"node_{node_id}"
        for j, pin in enumerate(node_registry[tag]["all_pins"]):
            if pin["type"] == "static" and j < len(entry["sv"]) and entry["sv"][j] is not None:
                dpg.set_value(pin["widget"], entry["sv"][j])


def key_press_handler(sender, app_data):
    key = app_data
    ctrl = dpg.is_key_down(dpg.mvKey_LControl) or dpg.is_key_down(dpg.mvKey_RControl)
    if key == dpg.mvKey_Delete:
        delete_selected()
    elif ctrl and key == dpg.mvKey_C:
        copy_selected()
    elif ctrl and key == dpg.mvKey_V:
        paste_nodes()


def get_execution_order():
    start_nodes = [
        tag for tag, info in node_registry.items()
        if info["label"] == "StartPoint"
    ]

    if not start_nodes:
        append_console("[警告] 'StartPoint' ノードが見つかりません\n")
        return []

    reachable = set()
    stack = list(start_nodes)
    while stack:
        tag = stack.pop()
        if tag in reachable:
            continue
        reachable.add(tag)
        for link in node_registry[tag]["links_out"]:
            nxt = link["to_node"]
            if nxt and nxt in node_registry:
                stack.append(nxt)

    in_degree = {tag: 0 for tag in reachable}
    for tag in reachable:
        for link in node_registry[tag]["links_out"]:
            nxt = link["to_node"]
            if nxt in in_degree:
                in_degree[nxt] += 1

    queue = [tag for tag in start_nodes if tag in in_degree]
    order = []
    while queue:
        current = queue.pop(0)
        order.append(current)
        for link in node_registry[current]["links_out"]:
            nxt = link["to_node"]
            if nxt in in_degree:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)

    return order


def append_console(text):
    current = dpg.get_value("console_output")
    dpg.set_value("console_output", current + text)
    dpg.set_y_scroll("console_scroll", dpg.get_y_scroll_max("console_scroll"))


def run_generation():
    proc = subprocess.Popen(
        ["python", "Generation.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8"
    )
    for line in proc.stdout:
        append_console(line)
    proc.wait()
    append_console(f"[終了 code={proc.returncode}]\n")


def run_callback():
    global pin_values
    pin_values = {}
    order = get_execution_order()
    IndentCounter = 0
    if not order:
        return

    Compiler.Init_File()

    for i, tag in enumerate(order):
        info = node_registry[tag]
        label = info["label"]
        all_pins = info["all_pins"]

        input_values = []
        for pin in all_pins:
            if pin["type"] == "static":
                input_values.append(dpg.get_value(pin["widget"]))
            else:
                input_values.append(None)

        for link in info["links_in"]:
            idx = link["to_pin_index"]
            input_values[idx] = pin_values.get(link["from_attr"])

        result, IndentCounter = Compiler.Add_Code(label, all_pins, input_values, IndentCounter)

        if result is not None and info["output_attr"] is not None:
            pin_values[info["output_attr"]] = result

    append_console("=== Run ===\n")
    threading.Thread(target=run_generation, daemon=True).start()


def execute_console_command(sender=None, app_data=None):
    command = dpg.get_value("console_input")
    if not command.strip():
        return
    dpg.set_value("console_input", "")
    dpg.focus_item("console_input")
    append_console(f"> {command}\n")

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        try:
            result = eval(compile(command, "<input>", "eval"), console_globals)
            if result is not None:
                sys.stdout.write(repr(result) + "\n")
        except SyntaxError:
            exec(compile(command, "<input>", "exec"), console_globals)
    except Exception as e:
        sys.stderr.write(f"{type(e).__name__}: {e}\n")
    finally:
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    if out:
        append_console(out)
    if err:
        append_console(err)


def new_vsp():
    global current_file
    for tag in list(node_registry.keys()):
        for lid in ([l["link_id"] for l in node_registry[tag]["links_in"]] +
                    [l["link_id"] for l in node_registry[tag]["links_out"]]):
            if dpg.does_item_exist(lid):
                dpg.delete_item(lid)
            link_registry.pop(lid, None)
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)
        del node_registry[tag]
    node_type_map.clear()
    attr_to_pin.clear()
    link_registry.clear()
    pin_values.clear()
    variables.clear()
    current_file = None
    dpg.set_viewport_title("VisualPy - New")


def save_vsp(filepath):
    global current_file
    os.makedirs("saves", exist_ok=True)

    node_list = list(node_registry.keys())
    nodes_data = []
    for tag in node_list:
        info = node_registry[tag]
        pos = dpg.get_item_pos(tag)
        static_values = []
        for pin in info["all_pins"]:
            if pin["type"] == "static":
                static_values.append(dpg.get_value(pin["widget"]))
            else:
                static_values.append(None)
        nodes_data.append({
            "defn": info["defn"],
            "pos": pos,
            "sv": static_values,
        })

    links_data = []
    for lid, linfo in link_registry.items():
        from_tag = linfo["from_node"]
        to_tag = linfo["to_node"]
        if from_tag not in node_list or to_tag not in node_list:
            continue
        links_data.append([
            node_list.index(from_tag),
            node_list.index(to_tag),
            linfo["to_pin_index"],
        ])

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"n": nodes_data, "l": links_data}, f, ensure_ascii=False, separators=(',', ':'))

    current_file = filepath
    dpg.set_viewport_title(f"VisualPy - {os.path.basename(filepath)}")
    append_console(f"[保存] {filepath}\n")


def load_vsp(filepath):
    global current_file
    new_vsp()

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    created_tags = []
    for entry in data["n"]:
        d = entry["defn"]
        add_node(
            label=d["label"],
            InputOn=d["InputOn"],
            OutputOn=d["OutputOn"],
            arg=d["arg"],
            category=d.get("category", ""),
            output_type=d.get("output_type"),
            input_type=d.get("input_type"),
            color=d.get("color", [100, 100, 100]),
            defn=d,
            pos=entry["pos"],
        )
        tag = f"node_{node_id}"
        static_values = entry.get("sv", [])
        for j, pin in enumerate(node_registry[tag]["all_pins"]):
            if pin["type"] == "static" and j < len(static_values) and static_values[j] is not None:
                dpg.set_value(pin["widget"], static_values[j])
        created_tags.append(tag)

    for linfo in data["l"]:
        from_tag = created_tags[linfo[0]]
        to_tag = created_tags[linfo[1]]
        to_pin_index = linfo[2]

        from_attr = node_registry[from_tag]["output_attr"]
        to_pins = node_registry[to_tag]["all_pins"]
        if to_pin_index >= len(to_pins):
            continue
        to_attr = to_pins[to_pin_index].get("attr_id")
        if from_attr is None or to_attr is None:
            continue

        link_id = dpg.add_node_link(from_attr, to_attr, parent=node_editor_tag)
        link_registry[link_id] = {
            "from_node": from_tag,
            "from_attr": from_attr,
            "to_node": to_tag,
            "to_attr": to_attr,
            "to_pin_index": to_pin_index,
        }
        node_registry[from_tag]["links_out"].append({
            "link_id": link_id, "to_node": to_tag, "to_attr": to_attr
        })
        node_registry[to_tag]["links_in"].append({
            "link_id": link_id, "from_node": from_tag,
            "from_attr": from_attr, "to_pin_index": to_pin_index
        })

    current_file = filepath
    dpg.set_viewport_title(f"VisualPy - {os.path.basename(filepath)}")
    append_console(f"[Load] {filepath}\n")


with dpg.window(label="##context_menu", tag="context_menu",
                show=False, popup=True, no_title_bar=True, min_size=[80, 20]):
    dpg.add_menu_item(label="Copy", callback=copy_selected)
    dpg.add_menu_item(label="Paste", callback=paste_nodes)
    dpg.add_menu_item(label="Delete", callback=delete_selected)

with dpg.handler_registry():
    dpg.add_key_press_handler(callback=key_press_handler)
    dpg.add_mouse_click_handler(
        button=dpg.mvMouseButton_Right,
        callback=lambda: dpg.configure_item("context_menu", show=True)
    )

with dpg.file_dialog(tag="dlg_open", directory_selector=False,
                     show=False, width=500, height=400,
                     callback=lambda s, a: load_vsp(a["file_path_name"])):
    dpg.add_file_extension(".vsp")

with dpg.file_dialog(tag="dlg_saveas", directory_selector=False,
                     show=False, width=500, height=400,
                     callback=lambda s, a: save_vsp(a["file_path_name"])):
    dpg.add_file_extension(".vsp")

node_definitions = load_node_definitions("Node")

categorized = {}
for defn in node_definitions:
    cat = defn.get("category", "Other")
    categorized.setdefault(cat, []).append(defn)

with dpg.window(label="ToolBOX", pos=(0, 0), width=150, height=700):
    for category, nodes in categorized.items():
        with dpg.collapsing_header(label=category, default_open=False):
            for defn in nodes:
                dpg.add_button(
                    label=defn["label"],
                    width=110,
                    callback=lambda s, a, d: add_node(
                        label=d["label"],
                        InputOn=d["InputOn"],
                        OutputOn=d["OutputOn"],
                        arg=d["arg"],
                        category=d.get("category", ""),
                        output_type=d.get("output_type"),
                        input_type=d.get("input_type"),
                        color=d.get("color", [100, 100, 100]),
                        defn=d,
                    ),
                    user_data=defn
                )
    with dpg.collapsing_header(label="RunBox", default_open=True):
        dpg.add_button(label="Run", width=110, callback=run_callback)

with dpg.window(label="Node Editor", pos=(150, 0), width=850, height=700, menubar=True):
    with dpg.menu_bar():
        with dpg.menu(label="File"):
            dpg.add_menu_item(label="New", callback=new_vsp)
            dpg.add_menu_item(label="Load",
                              callback=lambda: dpg.configure_item("dlg_open",
                                                                  default_path="saves", show=True))
            dpg.add_menu_item(label="Save",
                              callback=lambda: save_vsp(current_file) if current_file
                              else dpg.configure_item("dlg_saveas",
                                                      default_path="saves", show=True))
            dpg.add_menu_item(label="Save as",
                              callback=lambda: dpg.configure_item("dlg_saveas",
                                                                  default_path="saves", show=True))
        with dpg.menu(label="Edit"):
            dpg.add_menu_item(label="Copy  Ctrl+C", callback=copy_selected)
            dpg.add_menu_item(label="Paste  Ctrl+V", callback=paste_nodes)
            dpg.add_menu_item(label="Delete  Del", callback=delete_selected)

    with dpg.node_editor(tag=node_editor_tag,
                         callback=link_callback,
                         delink_callback=delink_callback):
        pass

with dpg.window(label="Console", pos=(0, 700), width=1000, height=300,
                no_close=True, no_move=True, no_resize=True):
    with dpg.child_window(tag="console_scroll", width=-1, height=240):
        dpg.add_input_text(
            tag="console_output",
            multiline=True,
            readonly=True,
            width=-1,
            height=-1,
            default_value="VisualPy Console\n"
        )
    with dpg.group(horizontal=True):
        dpg.add_text(">")
        dpg.add_input_text(
            tag="console_input",
            width=-50,
            on_enter=True,
            callback=execute_console_command,
        )
        dpg.add_button(label="Send", width=45, callback=execute_console_command)

dpg.create_viewport(title='VisualPy', width=1000, height=1000)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
Compiler.uninit_File()
dpg.destroy_context()