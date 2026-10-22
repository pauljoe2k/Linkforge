"""Device-type classification from a User-Agent string.

Deliberately naive sniffing for the MVP: a writable mapping is more
valuable than a heavyweight UA library here. Mobile and tablet tokens
are checked first (they are the most specific), then anything desktop-y,
then 'other' for bots, curl, Postman, etc.
"""

from typing import Final

MOBILE_TOKENS: Final[tuple[str, ...]] = (
    "iphone", "ipod", "android", "mobile", "windows phone", "blackberry",
)
TABLET_TOKENS: Final[tuple[str, ...]] = ("ipad", "tablet", "kindle", "playbook")
DESKTOP_TOKENS: Final[tuple[str, ...]] = (
    "windows nt", "macintosh", "mac os", "linux x86", "cros", "x11",
)


def classify_device(user_agent: str | None) -> str:
    ua = (user_agent or "").lower()
    if not ua:
        return "other"
    if any(tok in ua for tok in TABLET_TOKENS):
        return "tablet"
    if any(tok in ua for tok in MOBILE_TOKENS):
        return "mobile"
    if any(tok in ua for tok in DESKTOP_TOKENS):
        return "desktop"
    return "other"
