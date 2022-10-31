import base64
import hashlib
import sys

def sha256b64(s: str) -> str:
    return base64.b64encode(hashlib.sha256(str(s).encode("utf-8")).digest()).decode("utf-8")
print('fucker', sha256b64('./pyteal_helpers/hash.py'))
if __name__ == "__main__":
    print('ini', sys.argv)
    s = sys.argv[1]

    print(s)
    print(sha256b64(s))
