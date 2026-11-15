from pynput import keyboard


SPECIAL_KEYS = {
    "Right": keyboard.Key.right,
    "Left": keyboard.Key.left,
    "Up": keyboard.Key.up,
    "Down": keyboard.Key.down,
    "Page_Up": keyboard.Key.page_up,
    "Page_Down": keyboard.Key.page_down,
    "Home": keyboard.Key.home,
    "End": keyboard.Key.end,
    "space": keyboard.Key.space,
    "Return": keyboard.Key.enter,
    "Tab": keyboard.Key.tab,
    "BackSpace": keyboard.Key.backspace,
    "Delete": keyboard.Key.delete,
    "Insert": keyboard.Key.insert,
}

for n in range(1, 25):
    key_obj = getattr(
        keyboard.Key,
        f"f{n}",
        None
    )

    if key_obj is not None:
        SPECIAL_KEYS[f"F{n}"] = key_obj


def send_key(key_name):
    ctl = keyboard.Controller()

    key_name = key_name.strip()

    if key_name in SPECIAL_KEYS:
        key = SPECIAL_KEYS[key_name]

    elif len(key_name) == 1:
        key = key_name

    else:
        raise ValueError(
            f"未対応のキーです: {key_name}"
        )

    ctl.press(key)
    ctl.release(key)

