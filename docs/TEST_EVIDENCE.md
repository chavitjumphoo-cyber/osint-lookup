# หลักฐานผลการทดสอบ

วันที่บันทึก: 12 พ.ย. 2026 · สภาพแวดล้อม: macOS, Python 3.13 (venv)

## คำสั่งและผลรวม

```bash
$ .venv/bin/python -m pytest -q
........................................................................ [ 31%]
........................................................................ [ 63%]
........................................................................ [ 94%]
............                                                             [100%]
228 passed in 13.10s
```

## กรณีทดสอบด้านความปลอดภัยและการเข้าถึง (12 กรณี)

| # | กรณี | ไฟล์ | ผล |
|---|---|---|---|
| 1 | hash รหัสผ่านถูกต้อง/ผิด | `tests/test_auth.py::test_password_hash_roundtrip` | ผ่าน |
| 2 | login สำเร็จและไม่สนตัวพิมพ์ | `test_authenticate_success_and_case_insensitive` | ผ่าน |
| 3 | รหัสผิด/บัญชีปิดใช้งาน | `test_authenticate_rejects_wrong_password_and_inactive` | ผ่าน |
| 4 | ล็อกหลังผิด 5 ครั้ง | `test_lockout_after_five_failures` | ผ่าน |
| 5 | token ถูกแก้/รูปแบบผิด | `test_token_roundtrip_and_tamper` | ผ่าน |
| 6 | token หมดอายุ | `test_expired_token_rejected` | ผ่าน |
| 7 | ตารางสิทธิ์ viewer/analyst/admin | `test_permission_matrix` | ผ่าน |
| 8 | API ไม่มี token → 401 | `test_api_requires_login` | ผ่าน |
| 9 | login แล้วเรียก /auth/me | `test_api_login_and_me` | ผ่าน |
| 10 | viewer อ่านได้แต่สร้าง run → 403 | `test_viewer_read_only` | ผ่าน |
| 11 | admin ดูผู้ใช้ได้ analyst ไม่ได้ | `test_admin_lists_users_but_analyst_cannot` | ผ่าน |
| 12 | login/ล้มเหลวถูกบันทึก audit | `test_login_is_audited` | ผ่าน |

## กรณีทดสอบข้อมูลผิดรูปแบบและความถูกต้อง

| กรณี | ไฟล์ | ผล |
|---|---|---|
| เป้าหมายว่าง → 422 | `tests/test_api.py::test_validation_error` | ผ่าน |
| run ไม่มีจริง → 404 envelope | `test_missing_run_is_envelope` | ผ่าน |
| แยกสถานะ empty/blocked/failed/unknown | `tests/test_evidence.py::test_classify_status_categories` | ผ่าน |
| hash ตรวจจับเนื้อหาถูกแก้ | `test_hash_is_stable_and_verifiable` | ผ่าน |
| 403 จากแพลตฟอร์ม = blocked | `tests/test_platform_scanner.py::test_403_is_blocked` | ผ่าน |
| 200 ไม่มี marker = unknown | `test_200_without_marker_is_unknown` | ผ่าน |
| URL private network ถูกบล็อก | `tests/test_browser.py::test_fetch_error_carries_stderr` | ผ่าน |
| timeout ของ browser | `test_timeout_raises` | ผ่าน |

## การทดสอบด้วยมือ (สาธิต)

| ขั้น | ผลที่คาด | ผลจริง |
|---|---|---|
| login viewer แล้ว POST /investigate | 403 forbidden | ตรง |
| login analyst แล้ว POST /investigate | 202 run_id | ตรง |
| ไม่ส่ง Authorization ไป GET /runs | 401 unauthorized | ตรง |
| แก้บรรทัดใน audit.jsonl | verify FAIL พร้อมเลขบรรทัด | ตรง |
| แก้ผลลัพธ์ finding แล้ว verify hash | valid=false | ตรง |
