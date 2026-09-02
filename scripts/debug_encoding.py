"""매크로 스냅샷 한글 라벨 깨짐 원인 추적용 임시 스크립트 - 확인 후 삭제."""
import json
import locale
import os
import sys

print("=== 환경 ===")
print("locale.getpreferredencoding():", locale.getpreferredencoding())
print("sys.getdefaultencoding():", sys.getdefaultencoding())
print("sys.stdout.encoding:", sys.stdout.encoding)
print("LANG:", os.environ.get("LANG"))
print("LC_ALL:", os.environ.get("LC_ALL"))
print("PYTHONIOENCODING:", os.environ.get("PYTHONIOENCODING"))

label = "미국 10년물 국채금리"
print()
print("=== 문자열 원본 ===")
print("repr:", repr(label))
print("utf-8 bytes:", label.encode("utf-8"))
print("len(label):", len(label))

# _TursoConn._arg()가 하는 것과 동일 - str(v)
val = str(label)
print()
print("=== str(v) 이후 ===")
print("동일한가:", val == label)
print("utf-8 bytes:", val.encode("utf-8"))

# json.dumps 이후
dumped = json.dumps({"value": val})
print()
print("=== json.dumps 이후 ===")
print("repr:", repr(dumped))

# requests의 json= 파라미터가 실제로 보내는 바이트 확인
import requests
req = requests.Request("POST", "https://example.com", json={"label": val}).prepare()
print()
print("=== requests가 실제로 보낼 body 바이트 ===")
print(req.body)
print("utf-8로 디코드 시도:", req.body.decode("utf-8"))
