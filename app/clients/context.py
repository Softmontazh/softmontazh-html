import json

from .services import session_customer


def customer(request):
    c = session_customer(request)
    me = {"name": c.name, "phone": c.display_phone} if c and c.registered else None
    return {"me": c, "me_json": json.dumps(me, ensure_ascii=False).replace("</", "<\\/")}
