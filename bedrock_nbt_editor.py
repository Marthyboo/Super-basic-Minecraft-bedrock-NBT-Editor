from __future__ import annotations

import struct
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10
TAG_INT_ARRAY = 11
TAG_LONG_ARRAY = 12

TAG_NAMES = {
    TAG_END: "end",
    TAG_BYTE: "byte",
    TAG_SHORT: "short",
    TAG_INT: "int",
    TAG_LONG: "long",
    TAG_FLOAT: "float",
    TAG_DOUBLE: "double",
    TAG_BYTE_ARRAY: "byte_array",
    TAG_STRING: "string",
    TAG_LIST: "list",
    TAG_COMPOUND: "compound",
    TAG_INT_ARRAY: "int_array",
    TAG_LONG_ARRAY: "long_array",
}

ARRAY_ELEMENT_TAG = {
    TAG_BYTE_ARRAY: TAG_BYTE,
    TAG_INT_ARRAY: TAG_INT,
    TAG_LONG_ARRAY: TAG_LONG,
}

INT_TAGS = {TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG}
FLOAT_TAGS = {TAG_FLOAT, TAG_DOUBLE}
NUMERIC_TAGS = INT_TAGS | FLOAT_TAGS
SCALAR_TAGS = NUMERIC_TAGS | {TAG_STRING}


@dataclass
class NbtNode:
    tag_id: int
    value: object
    name: str | None = None
    list_type: int | None = None


@dataclass
class LoadedLevelDat:
    path: Path
    header_version: int
    root: NbtNode


class NbtReader:
    def __init__(self, data: bytes) -> None:
        self.data = memoryview(data)
        self.offset = 0

    def read(self, fmt: str):
        size = struct.calcsize(fmt)
        values = struct.unpack_from(fmt, self.data, self.offset)
        self.offset += size
        return values[0] if len(values) == 1 else values

    def read_u8(self) -> int:
        return self.read("<B")

    def read_string(self) -> str:
        length = self.read("<H")
        chunk = bytes(self.data[self.offset : self.offset + length])
        self.offset += length
        return chunk.decode("utf-8", errors="replace")

    def read_payload(self, tag_id: int, name: str | None = None) -> NbtNode:
        if tag_id == TAG_BYTE:
            return NbtNode(tag_id, self.read("<b"), name)
        if tag_id == TAG_SHORT:
            return NbtNode(tag_id, self.read("<h"), name)
        if tag_id == TAG_INT:
            return NbtNode(tag_id, self.read("<i"), name)
        if tag_id == TAG_LONG:
            return NbtNode(tag_id, self.read("<q"), name)
        if tag_id == TAG_FLOAT:
            return NbtNode(tag_id, self.read("<f"), name)
        if tag_id == TAG_DOUBLE:
            return NbtNode(tag_id, self.read("<d"), name)
        if tag_id == TAG_STRING:
            return NbtNode(tag_id, self.read_string(), name)
        if tag_id == TAG_BYTE_ARRAY:
            length = self.read("<i")
            if length:
                values = list(struct.unpack_from(f"<{length}b", self.data, self.offset))
                self.offset += length
            else:
                values = []
            return NbtNode(tag_id, values, name)
        if tag_id == TAG_INT_ARRAY:
            length = self.read("<i")
            if length:
                values = list(struct.unpack_from(f"<{length}i", self.data, self.offset))
                self.offset += length * 4
            else:
                values = []
            return NbtNode(tag_id, values, name)
        if tag_id == TAG_LONG_ARRAY:
            length = self.read("<i")
            if length:
                values = list(struct.unpack_from(f"<{length}q", self.data, self.offset))
                self.offset += length * 8
            else:
                values = []
            return NbtNode(tag_id, values, name)
        if tag_id == TAG_LIST:
            child_type = self.read_u8()
            length = self.read("<i")
            children = [self.read_payload(child_type) for _ in range(length)]
            return NbtNode(tag_id, children, name, child_type)
        if tag_id == TAG_COMPOUND:
            children: dict[str, NbtNode] = {}
            while True:
                child_tag = self.read_u8()
                if child_tag == TAG_END:
                    break
                child_name = self.read_string()
                children[child_name] = self.read_payload(child_tag, child_name)
            return NbtNode(tag_id, children, name)
        raise ValueError(f"Unsupported tag id: {tag_id}")

    def read_named_root(self) -> NbtNode:
        tag_id = self.read_u8()
        name = self.read_string()
        return self.read_payload(tag_id, name)


class NbtWriter:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def write(self, fmt: str, *values: object) -> None:
        self.buffer.extend(struct.pack(fmt, *values))

    def write_string(self, value: str) -> None:
        encoded = value.encode("utf-8")
        self.write("<H", len(encoded))
        self.buffer.extend(encoded)

    def write_named_root(self, node: NbtNode) -> bytes:
        self.write("<B", node.tag_id)
        self.write_string(node.name or "")
        self.write_payload(node)
        return bytes(self.buffer)

    def write_payload(self, node: NbtNode) -> None:
        tag_id = node.tag_id

        if tag_id == TAG_BYTE:
            self.write("<b", int(node.value))
            return
        if tag_id == TAG_SHORT:
            self.write("<h", int(node.value))
            return
        if tag_id == TAG_INT:
            self.write("<i", int(node.value))
            return
        if tag_id == TAG_LONG:
            self.write("<q", int(node.value))
            return
        if tag_id == TAG_FLOAT:
            self.write("<f", float(node.value))
            return
        if tag_id == TAG_DOUBLE:
            self.write("<d", float(node.value))
            return
        if tag_id == TAG_STRING:
            self.write_string(str(node.value))
            return
        if tag_id == TAG_BYTE_ARRAY:
            values = [int(item) for item in node.value]
            self.write("<i", len(values))
            if values:
                self.buffer.extend(struct.pack(f"<{len(values)}b", *values))
            return
        if tag_id == TAG_INT_ARRAY:
            values = [int(item) for item in node.value]
            self.write("<i", len(values))
            if values:
                self.buffer.extend(struct.pack(f"<{len(values)}i", *values))
            return
        if tag_id == TAG_LONG_ARRAY:
            values = [int(item) for item in node.value]
            self.write("<i", len(values))
            if values:
                self.buffer.extend(struct.pack(f"<{len(values)}q", *values))
            return
        if tag_id == TAG_LIST:
            child_type = node.list_type if node.list_type is not None else TAG_END
            children = list(node.value)
            self.write("<B", child_type)
            self.write("<i", len(children))
            for child in children:
                self.write_payload(child)
            return
        if tag_id == TAG_COMPOUND:
            for child_name, child in node.value.items():
                self.write("<B", child.tag_id)
                self.write_string(child_name)
                self.write_payload(child)
            self.write("<B", TAG_END)
            return
        raise ValueError(f"Unsupported tag id: {tag_id}")


def load_level_dat(path: Path) -> LoadedLevelDat:
    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"{path} is too small to be a valid Bedrock level.dat file.")
    header_version, payload_length = struct.unpack("<II", data[:8])
    payload = data[8 : 8 + payload_length]
    if len(payload) != payload_length:
        raise ValueError(
            f"{path} says its payload is {payload_length} bytes, but only {len(payload)} bytes are present."
        )
    reader = NbtReader(payload)
    root = reader.read_named_root()
    if root.tag_id != TAG_COMPOUND:
        raise ValueError(f"{path} root tag is {root.tag_id}, expected a compound.")
    return LoadedLevelDat(path=path, header_version=header_version, root=root)


def write_level_dat(path: Path, header_version: int, root: NbtNode) -> None:
    payload = NbtWriter().write_named_root(root)
    path.write_bytes(struct.pack("<II", header_version, len(payload)) + payload)


def parse_bool_like(value: str) -> int:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return 1
    if normalized in {"0", "false", "no", "off"}:
        return 0
    raise ValueError("Expected 0/1 or true/false.")


def format_scalar_value(node: NbtNode) -> str:
    if node.tag_id == TAG_STRING:
        return str(node.value)
    return str(node.value)


def summarize_value(node: NbtNode) -> str:
    if node.tag_id == TAG_COMPOUND:
        return f"{len(node.value)} entries"
    if node.tag_id == TAG_LIST:
        child_type = TAG_NAMES.get(node.list_type or TAG_END, str(node.list_type))
        return f"{len(node.value)} x {child_type}"
    if node.tag_id in {TAG_BYTE_ARRAY, TAG_INT_ARRAY, TAG_LONG_ARRAY}:
        return f"{len(node.value)} values"
    text = format_scalar_value(node)
    return text if len(text) <= 80 else f"{text[:77]}..."


def find_first_level_dat(base_dir: Path) -> Path | None:
    try:
        return next(base_dir.rglob("level.dat"))
    except StopIteration:
        return None


def get_node(root: NbtNode, path: Iterable[str]) -> NbtNode | None:
    current = root
    for part in path:
        if current.tag_id != TAG_COMPOUND:
            return None
        current = current.value.get(part)
        if current is None:
            return None
    return current


def require_node(root: NbtNode, path: Iterable[str]) -> NbtNode:
    node = get_node(root, path)
    if node is None:
        dotted = ".".join(path)
        raise ValueError(f"Missing expected tag: {dotted}")
    return node


def find_child_key(compound: NbtNode, wanted_name: str) -> str | None:
    if compound.tag_id != TAG_COMPOUND:
        return None
    if wanted_name in compound.value:
        return wanted_name
    wanted_lower = wanted_name.lower()
    for existing_name in compound.value:
        if existing_name.lower() == wanted_lower:
            return existing_name
    return None


def ensure_compound(root: NbtNode, path: Iterable[str]) -> NbtNode:
    current = root
    for part in path:
        if current.tag_id != TAG_COMPOUND:
            raise ValueError(f"Cannot create {part} under non-compound tag {current.name!r}.")
        actual_name = find_child_key(current, part) or part
        child = current.value.get(actual_name)
        if child is None:
            child = NbtNode(TAG_COMPOUND, {}, name=actual_name)
            current.value[actual_name] = child
        elif child.tag_id != TAG_COMPOUND:
            raise ValueError(f"Expected compound at {actual_name}, found {TAG_NAMES[child.tag_id]}.")
        current = child
    return current


def set_byte_tag(root: NbtNode, path: Iterable[str], value: int) -> NbtNode:
    parts = tuple(path)
    if not parts:
        raise ValueError("Path must contain at least one tag name.")
    parent = ensure_compound(root, parts[:-1])
    leaf_name = find_child_key(parent, parts[-1]) or parts[-1]
    node = parent.value.get(leaf_name)
    if node is None:
        node = NbtNode(TAG_BYTE, int(value), name=leaf_name)
        parent.value[leaf_name] = node
    else:
        node.tag_id = TAG_BYTE
        node.name = leaf_name
        node.list_type = None
        node.value = int(value)
    return node


class BedrockNbtEditor:
    ACHIEVEMENT_RESET_TAGS = (
        (("experiments_ever_used",), 0),
        (("saved_with_toggled_experiments",), 0),
        (("hasBeenLoadedInCreative",), 0),
        (("experiments", "experimental_creator_cameras"), 0),
        (("experiments", "gametest"), 0),
        (("experiments", "upcoming_creator_features"), 0),
    )

    COMMON_FIELDS = [
        ("Level Name", ("LevelName",), "string"),
        ("Game Mode", ("GameType",), "gamemode"),
        ("Difficulty", ("Difficulty",), "difficulty"),
        ("Random Seed", ("RandomSeed",), "long"),
        ("Spawn X", ("SpawnX",), "int"),
        ("Spawn Y", ("SpawnY",), "int"),
        ("Spawn Z", ("SpawnZ",), "int"),
        ("Time", ("Time",), "long"),
        ("Random Tick Speed", ("randomtickspeed",), "int"),
        ("Commands Enabled", ("commandsEnabled",), "bool"),
        ("Keep Inventory", ("keepinventory",), "bool"),
        ("Show Coordinates", ("showcoordinates",), "bool"),
        ("Daylight Cycle", ("dodaylightcycle",), "bool"),
        ("Weather Cycle", ("doweathercycle",), "bool"),
        ("PVP", ("pvp",), "bool"),
        ("Mob Griefing", ("mobgriefing",), "bool"),
        ("May Fly", ("abilities", "mayfly"), "bool"),
        ("Flying", ("abilities", "flying"), "bool"),
        ("Invulnerable", ("abilities", "invulnerable"), "bool"),
        ("Instant Build", ("abilities", "instabuild"), "bool"),
    ]

    GAME_MODE_CHOICES = (
        "0 - Survival",
        "1 - Creative",
        "2 - Adventure",
        "6 - Spectator",
    )

    DIFFICULTY_CHOICES = (
        "0 - Peaceful",
        "1 - Easy",
        "2 - Normal",
        "3 - Hard",
    )

    def __init__(self, root_window: tk.Tk, initial_path: Path | None = None) -> None:
        self.window = root_window
        self.window.title("Bedrock level.dat Editor")
        self.window.geometry("1280x820")
        self.window.minsize(980, 680)

        self.loaded: LoadedLevelDat | None = None
        self.path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select a Bedrock world folder or a level.dat file.")
        self.common_vars: dict[tuple[str, ...], tk.Variable] = {}
        self.tree_refs: dict[str, tuple[NbtNode, str]] = {}
        self.selected_item_id: str | None = None
        self.selected_ref: tuple[NbtNode, str] | None = None

        self.build_ui()

        if initial_path is not None:
            self.open_target(initial_path)

    def build_ui(self) -> None:
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x")

        ttk.Label(toolbar, text="Target").pack(side="left")
        ttk.Entry(toolbar, textvariable=self.path_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(toolbar, text="World Folder", command=self.choose_world_folder).pack(side="left")
        ttk.Button(toolbar, text="level.dat File", command=self.choose_level_dat).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Reload", command=self.reload_current).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Save", command=self.save_current).pack(side="left", padx=(8, 0))

        ttk.Label(
            outer,
            text="This editor targets Bedrock world settings in level.dat. The rest of the world save in db/ is LevelDB, not NBT.",
        ).pack(fill="x", pady=(8, 8))

        panes = ttk.Panedwindow(outer, orient="horizontal")
        panes.pack(fill="both", expand=True)

        left = ttk.Frame(panes, padding=(0, 0, 10, 0))
        right = ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)

        self.build_common_settings(left)
        self.build_raw_tree(right)

        ttk.Label(outer, textvariable=self.status_var, relief="sunken", anchor="w").pack(fill="x", pady=(8, 0))

    def build_common_settings(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="World Settings", padding=12)
        card.pack(fill="both", expand=True)

        for row, (label, path, field_type) in enumerate(self.COMMON_FIELDS):
            ttk.Label(card, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            if field_type == "bool":
                variable = tk.BooleanVar(value=False)
                widget = ttk.Checkbutton(card, variable=variable)
                widget.grid(row=row, column=1, sticky="w", pady=4)
            elif field_type == "gamemode":
                variable = tk.StringVar()
                widget = ttk.Combobox(card, textvariable=variable, values=self.GAME_MODE_CHOICES, state="readonly")
                widget.grid(row=row, column=1, sticky="ew", pady=4)
            elif field_type == "difficulty":
                variable = tk.StringVar()
                widget = ttk.Combobox(
                    card,
                    textvariable=variable,
                    values=self.DIFFICULTY_CHOICES,
                    state="readonly",
                )
                widget.grid(row=row, column=1, sticky="ew", pady=4)
            else:
                variable = tk.StringVar()
                widget = ttk.Entry(card, textvariable=variable)
                widget.grid(row=row, column=1, sticky="ew", pady=4)
            self.common_vars[path] = variable

        card.columnconfigure(1, weight=1)

        actions = ttk.Frame(card)
        actions.grid(row=len(self.COMMON_FIELDS), column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text="Apply Fields", command=lambda: self.apply_common_settings(show_message=True)).pack(
            side="left"
        )
        ttk.Button(actions, text="Refresh Fields", command=self.load_common_settings).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Re-enable Achievements", command=self.reenable_achievements).pack(
            side="left", padx=(8, 0)
        )

    def build_raw_tree(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="Raw NBT", padding=12)
        card.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(card, columns=("type", "value"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Path")
        self.tree.heading("type", text="Type")
        self.tree.heading("value", text="Value")
        self.tree.column("#0", width=360, stretch=True)
        self.tree.column("type", width=120, stretch=False)
        self.tree.column("value", width=360, stretch=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        yscroll = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        editor = ttk.Frame(card, padding=(0, 12, 0, 0))
        editor.grid(row=1, column=0, columnspan=2, sticky="ew")

        self.selected_path_var = tk.StringVar(value="Path: ")
        self.selected_type_var = tk.StringVar(value="Type: ")
        ttk.Label(editor, textvariable=self.selected_path_var).pack(anchor="w")
        ttk.Label(editor, textvariable=self.selected_type_var).pack(anchor="w", pady=(4, 0))

        self.raw_editor = tk.Text(editor, height=6, wrap="word")
        self.raw_editor.pack(fill="x", pady=(8, 8))

        raw_help = (
            "Edit scalar values directly. Byte tags accept 0/1 or true/false. "
            "Array tags accept comma-separated numbers."
        )
        ttk.Label(editor, text=raw_help).pack(anchor="w")

        buttons = ttk.Frame(editor)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Apply Selected Value", command=self.apply_selected_value).pack(side="left")
        ttk.Button(buttons, text="Expand All", command=self.expand_all).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Collapse All", command=self.collapse_all).pack(side="left", padx=(8, 0))

        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)

    def choose_world_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select Bedrock world folder")
        if folder:
            self.open_target(Path(folder))

    def choose_level_dat(self) -> None:
        path = filedialog.askopenfilename(
            title="Select level.dat",
            filetypes=(("Bedrock level.dat", "level.dat"), ("All files", "*.*")),
        )
        if path:
            self.open_target(Path(path))

    def resolve_level_path(self, target: Path) -> Path:
        if target.is_dir():
            level_path = target / "level.dat"
        else:
            level_path = target
        if not level_path.exists():
            raise FileNotFoundError(f"Could not find level.dat at {level_path}")
        return level_path

    def open_target(self, target: Path) -> None:
        try:
            level_path = self.resolve_level_path(target)
            self.loaded = load_level_dat(level_path)
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))
            self.status_var.set(f"Failed to open: {target}")
            return

        self.path_var.set(str(level_path))
        self.populate_tree()
        self.load_common_settings()
        self.status_var.set(f"Loaded {level_path}")

    def reload_current(self) -> None:
        if not self.loaded:
            messagebox.showinfo("Reload", "No file is loaded yet.")
            return
        self.open_target(self.loaded.path)

    def populate_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.tree_refs.clear()
        self.selected_item_id = None
        self.selected_ref = None
        self.clear_raw_editor()

        if not self.loaded:
            return

        root_node = self.loaded.root
        root_item = self.tree.insert("", "end", text=root_node.name or "(root)", values=("compound", summarize_value(root_node)))
        self.tree_refs[root_item] = (root_node, root_node.name or "(root)")
        self.populate_children(root_item, root_node, root_node.name or "(root)")
        self.tree.item(root_item, open=True)

    def populate_children(self, parent_item: str, node: NbtNode, path_text: str) -> None:
        if node.tag_id == TAG_COMPOUND:
            for child_name, child in node.value.items():
                child_path = f"{path_text}.{child_name}" if path_text != "(root)" else child_name
                item_id = self.tree.insert(
                    parent_item,
                    "end",
                    text=child_name,
                    values=(TAG_NAMES[child.tag_id], summarize_value(child)),
                )
                self.tree_refs[item_id] = (child, child_path)
                self.populate_children(item_id, child, child_path)
            return

        if node.tag_id == TAG_LIST:
            for index, child in enumerate(node.value):
                child_path = f"{path_text}[{index}]"
                label = f"[{index}]"
                child_type = TAG_NAMES[child.tag_id]
                item_id = self.tree.insert(
                    parent_item,
                    "end",
                    text=label,
                    values=(child_type, summarize_value(child)),
                )
                self.tree_refs[item_id] = (child, child_path)
                self.populate_children(item_id, child, child_path)

    def load_common_settings(self) -> None:
        if not self.loaded:
            return

        root = self.loaded.root
        for _, path, field_type in self.COMMON_FIELDS:
            node = get_node(root, path)
            if node is None:
                continue
            variable = self.common_vars[path]
            if field_type == "bool":
                variable.set(bool(int(node.value)))
            elif field_type == "gamemode":
                variable.set(self.match_choice(self.GAME_MODE_CHOICES, int(node.value)))
            elif field_type == "difficulty":
                variable.set(self.match_choice(self.DIFFICULTY_CHOICES, int(node.value)))
            else:
                variable.set(str(node.value))

    def match_choice(self, values: tuple[str, ...], current: int) -> str:
        prefix = f"{current} -"
        for value in values:
            if value.startswith(prefix):
                return value
        return f"{current} - Custom"

    def apply_common_settings(self, show_message: bool = False) -> bool:
        if not self.loaded:
            messagebox.showinfo("Apply fields", "No file is loaded yet.")
            return False

        try:
            for _, path, field_type in self.COMMON_FIELDS:
                node = require_node(self.loaded.root, path)
                variable = self.common_vars[path]
                if field_type == "bool":
                    node.value = 1 if variable.get() else 0
                elif field_type == "string":
                    node.value = str(variable.get())
                elif field_type in {"int", "long"}:
                    node.value = int(str(variable.get()).strip())
                elif field_type == "gamemode":
                    node.value = int(str(variable.get()).split(" - ", 1)[0])
                elif field_type == "difficulty":
                    node.value = int(str(variable.get()).split(" - ", 1)[0])
                else:
                    raise ValueError(f"Unsupported field type: {field_type}")
        except Exception as exc:
            messagebox.showerror("Apply fields failed", str(exc))
            return False

        self.refresh_tree_values()
        if show_message:
            self.status_var.set("Applied common fields to the in-memory NBT data.")
        return True

    def refresh_tree_values(self) -> None:
        for item_id, (node, _) in self.tree_refs.items():
            self.tree.set(item_id, "value", summarize_value(node))
        if self.selected_item_id:
            self.show_selected_value(self.selected_item_id)

    def reenable_achievements(self) -> None:
        if not self.loaded:
            messagebox.showinfo("Re-enable Achievements", "No file is loaded yet.")
            return

        changed_paths: list[str] = []
        try:
            for path, value in self.ACHIEVEMENT_RESET_TAGS:
                set_byte_tag(self.loaded.root, path, value)
                changed_paths.append(".".join(path))
        except Exception as exc:
            messagebox.showerror("Re-enable Achievements failed", str(exc))
            return

        self.populate_tree()
        self.load_common_settings()

        warnings: list[str] = []
        for path in (("commandsEnabled",), ("experimentalgameplay",)):
            node = get_node(self.loaded.root, path)
            if node is not None and node.tag_id == TAG_BYTE and int(node.value) != 0:
                warnings.append(f"{'.'.join(path)} is still {int(node.value)}")

        message_lines = [
            "Applied the requested achievement-related flags in memory.",
            "Click Save to write them to level.dat.",
            "",
            "Updated tags:",
            *changed_paths,
        ]
        if warnings:
            message_lines.extend(
                [
                    "",
                    "Possible blockers still present in this save:",
                    *warnings,
                ]
            )

        self.status_var.set("Applied achievement reset tags. Click Save to write the changes.")
        messagebox.showinfo("Re-enable Achievements", "\n".join(message_lines))

    def clear_raw_editor(self) -> None:
        self.selected_path_var.set("Path: ")
        self.selected_type_var.set("Type: ")
        self.raw_editor.configure(state="normal")
        self.raw_editor.delete("1.0", "end")
        self.raw_editor.configure(state="disabled")

    def on_tree_select(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        self.show_selected_value(selected[0])

    def show_selected_value(self, item_id: str) -> None:
        node, path_text = self.tree_refs[item_id]
        self.selected_item_id = item_id
        self.selected_ref = (node, path_text)
        self.selected_path_var.set(f"Path: {path_text}")
        self.selected_type_var.set(f"Type: {self.describe_tag(node)}")

        self.raw_editor.configure(state="normal")
        self.raw_editor.delete("1.0", "end")

        if node.tag_id in SCALAR_TAGS:
            self.raw_editor.insert("1.0", format_scalar_value(node))
            self.raw_editor.configure(state="normal")
        elif node.tag_id in {TAG_BYTE_ARRAY, TAG_INT_ARRAY, TAG_LONG_ARRAY}:
            self.raw_editor.insert("1.0", ", ".join(str(item) for item in node.value))
            self.raw_editor.configure(state="normal")
        else:
            self.raw_editor.insert("1.0", "Select a scalar or array value to edit it here.")
            self.raw_editor.configure(state="disabled")

    def describe_tag(self, node: NbtNode) -> str:
        if node.tag_id == TAG_LIST:
            child_type = TAG_NAMES.get(node.list_type or TAG_END, str(node.list_type))
            return f"list<{child_type}>"
        return TAG_NAMES[node.tag_id]

    def apply_selected_value(self) -> bool:
        if not self.selected_ref:
            messagebox.showinfo("Apply value", "Select a value in the raw NBT tree first.")
            return False

        node, path_text = self.selected_ref
        if node.tag_id not in SCALAR_TAGS and node.tag_id not in {TAG_BYTE_ARRAY, TAG_INT_ARRAY, TAG_LONG_ARRAY}:
            messagebox.showinfo("Apply value", "That node is a container. Pick a scalar child value instead.")
            return False

        raw_text = self.raw_editor.get("1.0", "end-1c")
        try:
            if node.tag_id == TAG_STRING:
                node.value = raw_text
            elif node.tag_id == TAG_BYTE:
                node.value = parse_bool_like(raw_text) if node.value in {0, 1} else int(raw_text.strip())
            elif node.tag_id in {TAG_SHORT, TAG_INT, TAG_LONG}:
                node.value = int(raw_text.strip())
            elif node.tag_id in {TAG_FLOAT, TAG_DOUBLE}:
                node.value = float(raw_text.strip())
            elif node.tag_id in {TAG_BYTE_ARRAY, TAG_INT_ARRAY, TAG_LONG_ARRAY}:
                node.value = self.parse_number_list(raw_text)
            else:
                raise ValueError(f"Editing is not implemented for tag {node.tag_id}.")
        except Exception as exc:
            messagebox.showerror("Apply value failed", f"{path_text}: {exc}")
            return False

        self.refresh_tree_values()
        self.status_var.set(f"Updated {path_text} in memory.")
        return True

    def parse_number_list(self, raw_text: str) -> list[int]:
        cleaned = raw_text.strip()
        if not cleaned:
            return []
        return [int(piece.strip()) for piece in cleaned.split(",") if piece.strip()]

    def maybe_apply_selected_value(self) -> bool:
        if not self.selected_ref:
            return True

        node, _ = self.selected_ref
        if node.tag_id not in SCALAR_TAGS and node.tag_id not in {TAG_BYTE_ARRAY, TAG_INT_ARRAY, TAG_LONG_ARRAY}:
            return True

        editor_text = self.raw_editor.get("1.0", "end-1c")
        if node.tag_id in {TAG_BYTE_ARRAY, TAG_INT_ARRAY, TAG_LONG_ARRAY}:
            current_text = ", ".join(str(item) for item in node.value)
        else:
            current_text = format_scalar_value(node)

        if editor_text == current_text:
            return True
        return self.apply_selected_value()

    def save_current(self) -> None:
        if not self.loaded:
            messagebox.showinfo("Save", "No file is loaded yet.")
            return

        if not self.apply_common_settings(show_message=False):
            return
        if not self.maybe_apply_selected_value():
            return

        level_path = self.loaded.path
        backup_path = level_path.with_name(f"{level_path.name}.bak.{datetime.now():%Y%m%d_%H%M%S}")
        try:
            backup_path.write_bytes(level_path.read_bytes())
            write_level_dat(level_path, self.loaded.header_version, self.loaded.root)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return

        self.status_var.set(f"Saved {level_path} and created backup {backup_path.name}")
        messagebox.showinfo("Saved", f"Saved changes.\nBackup created: {backup_path.name}")

    def expand_all(self) -> None:
        for item in self.tree.get_children():
            self.expand_branch(item)

    def expand_branch(self, item_id: str) -> None:
        self.tree.item(item_id, open=True)
        for child in self.tree.get_children(item_id):
            self.expand_branch(child)

    def collapse_all(self) -> None:
        for item in self.tree.get_children():
            self.collapse_branch(item)

    def collapse_branch(self, item_id: str) -> None:
        self.tree.item(item_id, open=False)
        for child in self.tree.get_children(item_id):
            self.collapse_branch(child)


def determine_initial_path() -> Path | None:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])

    cwd = Path.cwd()
    return find_first_level_dat(cwd)


def main() -> None:
    window = tk.Tk()
    initial_path = determine_initial_path()
    app = BedrockNbtEditor(window, initial_path=initial_path)
    if initial_path is None:
        app.status_var.set("No level.dat was auto-detected in this folder. Use the picker at the top.")
    window.mainloop()


if __name__ == "__main__":
    main()
