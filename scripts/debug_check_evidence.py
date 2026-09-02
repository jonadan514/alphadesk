"""normalize_theme_evidence.py 결과 확인용 임시 스크립트 - 확인 후 삭제."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db

conn = get_db()
rows = conn.execute(
    "SELECT theme_id, ticker, evidence FROM theme_members "
    "WHERE approved=1 AND theme_id='autonomous_driving' ORDER BY ticker"
).fetchall()
for r in rows:
    print(f"{r[0]} {r[1]}: {r[2]}")
conn.close()
