"""Tests for advanced OSINT tools — scan_phone_advanced, compare_avatars, stylometry"""

import pytest
from osint_agent import advanced_tools


def test_dhash_same_image():
    """dHash ของรูปเดียวกันต้องเหมือนกัน"""
    # สร้างรูปสี่เหลี่ยมสีเดียวกัน 2 รูป
    from PIL import Image
    import io

    img1 = Image.new("RGB", (100, 100), color="red")
    img2 = Image.new("RGB", (100, 100), color="red")

    buf1 = io.BytesIO()
    buf2 = io.BytesIO()
    img1.save(buf1, format="PNG")
    img2.save(buf2, format="PNG")

    hash1 = advanced_tools.compute_dhash(buf1.getvalue())
    hash2 = advanced_tools.compute_dhash(buf2.getvalue())

    assert hash1 == hash2


def test_dhash_different_images():
    """dHash ของรูปต่างกันต้องต่างกัน"""
    from PIL import Image, ImageDraw
    import io

    # สร้างรูปที่มีลวดลายต่างกัน
    img1 = Image.new("RGB", (100, 100), color="white")
    draw1 = ImageDraw.Draw(img1)
    draw1.rectangle([10, 10, 50, 50], fill="black")  # สี่เหลี่ยมซ้ายบน

    img2 = Image.new("RGB", (100, 100), color="white")
    draw2 = ImageDraw.Draw(img2)
    draw2.rectangle([50, 50, 90, 90], fill="black")  # สี่เหลี่ยมขวาล่าง

    buf1 = io.BytesIO()
    buf2 = io.BytesIO()
    img1.save(buf1, format="PNG")
    img2.save(buf2, format="PNG")

    hash1 = advanced_tools.compute_dhash(buf1.getvalue())
    hash2 = advanced_tools.compute_dhash(buf2.getvalue())

    assert hash1 != hash2


def test_hamming_distance():
    """Hamming distance ต้องคำนวณถูกต้อง"""
    # 0000 vs 0001 = 1 bit ต่าง
    assert advanced_tools.hamming_distance("0", "1") == 1
    # ffff vs 0000 = 16 bits ต่าง (4 hex digits × 4 bits)
    assert advanced_tools.hamming_distance("ffff", "0000") == 16
    # เหมือนกัน = 0
    assert advanced_tools.hamming_distance("abcd", "abcd") == 0


def test_compare_avatars_same():
    """เปรียบเทียบรูปเดียวกันต้องได้ matched=True"""
    from PIL import Image
    import io

    img = Image.new("RGB", (100, 100), color="green")
    buf1 = io.BytesIO()
    buf2 = io.BytesIO()
    img.save(buf1, format="PNG")
    img.save(buf2, format="PNG")

    result = advanced_tools.compare_avatars(buf1.getvalue(), buf2.getvalue())

    assert result["matched"] is True
    assert result["similarity_percentage"] == 100.0
    assert result["hamming_distance"] == 0


def test_stylometry_identical_text():
    """ข้อความเดียวกันต้องได้ similarity = 1.0"""
    text = "This is a test sentence with enough characters to pass the minimum requirement for stylometry analysis."
    result = advanced_tools.correlate_stylometry(text, text)

    assert result["similarity"] == 1.0
    assert "เขียนโดยคนเดียวกันมาก" in result["interpretation"]


def test_stylometry_different_text():
    """ข้อความที่ต่างกันมากต้องได้ similarity ต่ำ"""
    text1 = "This is a very formal academic writing style with complex sentence structures and sophisticated vocabulary."
    text2 = "yo dude this is super casual text lol wtf omg haha rofl totally different vibe man"

    result = advanced_tools.correlate_stylometry(text1, text2)

    # ควรได้ค่าต่ำ เพราะลีลาเขียนต่างกันมาก
    assert result["similarity"] < 0.7


def test_stylometry_too_short():
    """ข้อความสั้นเกินไปต้องมี warning"""
    result = advanced_tools.correlate_stylometry("short", "text")

    assert "warning" in result
    assert "40" in result["warning"]


def test_scan_phone_invalid():
    """เบอร์ไม่ถูกต้องต้อง return is_valid=False"""
    import asyncio

    result = asyncio.run(advanced_tools.scan_phone("invalid"))

    assert result.is_valid is False
    assert result.error is not None


def test_scan_phone_valid_format():
    """เบอร์ที่ถูกต้องต้อง parse ได้"""
    import asyncio

    # เบอร์ไทยตัวอย่าง (อาจไม่ได้จัดสรรจริง แต่รูปแบบถูก)
    result = asyncio.run(advanced_tools.scan_phone("+66812345678"))

    assert result.is_valid is True
    assert result.country_iso == "TH"
    assert result.e164 == "+66812345678"
    assert "whatsapp" in result.footprint_urls
    assert "telegram" in result.footprint_urls
    assert result.whatsapp_url == result.footprint_urls["whatsapp"]


def test_phone_names_are_returned_in_existing_associated_names_field(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url):
            return SimpleNamespace(status_code=200, text='<b>Example Person</b>')

    monkeypatch.setattr(advanced_tools.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(advanced_tools.scan_phone("+66812345678"))
    assert "Example Person" in result.associated_names
