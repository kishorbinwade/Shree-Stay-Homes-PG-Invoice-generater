"""Local SMTP sink for end-to-end testing of the invoice email flow.
Accepts AUTH with password 'secret', writes every received message (raw bytes)
as base64 JSON lines to /tmp/smtp_inbox.jsonl.
"""
import base64
import json
import time
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword

PASSWORD = b"secret"


class Authenticator:
    def __call__(self, server, session, envelope, mechanism, auth_data):
        if isinstance(auth_data, LoginPassword) and auth_data.password == PASSWORD:
            return AuthResult(success=True)
        return AuthResult(success=False)


class Handler:
    async def handle_DATA(self, server, session, envelope):
        raw = envelope.content
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        with open("/tmp/smtp_inbox.jsonl", "a") as f:
            f.write(json.dumps({
                "mail_from": envelope.mail_from,
                "rcpt_tos": list(envelope.rcpt_tos),
                "content_b64": base64.b64encode(raw).decode(),
            }) + "\n")
        print(f"RECEIVED -> {envelope.rcpt_tos}", flush=True)
        return "250 OK"


if __name__ == "__main__":
    controller = Controller(Handler(), hostname="127.0.0.1", port=1025,
                            auth_require_tls=False, authenticator=Authenticator())
    controller.start()
    print("SMTP sink listening on 127.0.0.1:1025", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        controller.stop()
