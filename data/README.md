# 데이터

- `hardware/`: 실제 부품 수집 원본, 검토 기록, 정규화 결과, 실행 보고서.

Python 코드는 `backend/app/domains/hardware/ingestion/`, DB 연결은
`backend/app/core/parts_database.py`, SQL은 `backend/app/db/sql/parts_catalog.sql`에 있습니다.
실행 방법과 데이터 정책은 [부품 데이터 안내](../docs/DATA_PIPELINE.md)를 참고하세요.
