"""Layer 3 (content): turns key presses into text and spots launcher shortcuts / shell keywords."""
from evdev import ecodes as ec

CHARS = {}
for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    CHARS[getattr(ec, f"KEY_{c}")] = (c.lower(), c)
for d, s in zip("1234567890", "!@#$%^&*()"):
    CHARS[getattr(ec, f"KEY_{d}")] = (d, s)
CHARS.update({
    ec.KEY_SPACE: (" ", " "), ec.KEY_MINUS: ("-", "_"), ec.KEY_DOT: (".", ">"),
    ec.KEY_COMMA: (",", "<"), ec.KEY_SLASH: ("/", "?"), ec.KEY_SEMICOLON: (";", ":"),
    ec.KEY_EQUAL: ("=", "+"), ec.KEY_APOSTROPHE: ("'", '"'),
    ec.KEY_BACKSLASH: ("\\", "|"), ec.KEY_ENTER: ("\n", "\n"), ec.KEY_TAB: ("\t", "\t"),
})
SHIFT = {ec.KEY_LEFTSHIFT, ec.KEY_RIGHTSHIFT}
CTRL = {ec.KEY_LEFTCTRL, ec.KEY_RIGHTCTRL}
ALT = {ec.KEY_LEFTALT, ec.KEY_RIGHTALT}
META = {ec.KEY_LEFTMETA, ec.KEY_RIGHTMETA}


class ContentAnalyzer:
    def __init__(self, keywords):
        self.keywords = [k.lower() for k in keywords]
        self.pressed = set()
        self.buffer = ""
        self.hits = []
        self.launcher = None

    def feed(self, code, value):
        """value: 1 = key down, 0 = key up."""
        if value == 0:
            self.pressed.discard(code)
            return
        self.pressed.add(code)
        shift = bool(self.pressed & SHIFT)
        ctrl, alt, meta = (bool(self.pressed & s) for s in (CTRL, ALT, META))
        if code == ec.KEY_R and meta:
            self.launcher = self.launcher or "Win+R"
        elif code == ec.KEY_T and ctrl and alt:
            self.launcher = self.launcher or "Ctrl+Alt+T"
        elif code == ec.KEY_F2 and alt:
            self.launcher = self.launcher or "Alt+F2"
        elif code == ec.KEY_BACKSPACE:
            self.buffer = self.buffer[:-1]
        elif code in CHARS and not (ctrl or alt or meta):
            self.buffer = (self.buffer + CHARS[code][1 if shift else 0])[-300:]
            low = self.buffer.lower()
            for kw in self.keywords:
                if kw in low and kw not in self.hits:
                    self.hits.append(kw)
