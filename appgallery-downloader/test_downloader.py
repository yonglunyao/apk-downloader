import pytest

from appgallery_downloader import parse_appid


def test_parse_appid_plain():
    assert parse_appid("C10406921") == "C10406921"


def test_parse_appid_hash_url():
    url = "https://appgallery.huawei.com/#/app/C100130495"
    assert parse_appid(url) == "C100130495"


def test_parse_appid_plain_url():
    url = "https://appgallery.huawei.com/app/C100130495"
    assert parse_appid(url) == "C100130495"


def test_parse_appid_invalid_raises():
    with pytest.raises(ValueError):
        parse_appid("not-an-appid")


from appgallery_downloader import build_download_url


def test_build_download_url():
    assert build_download_url("C10406921") == "https://appgallery.cloud.huawei.com/appdl/C10406921"


from appgallery_downloader import extract_filename


def test_extract_filename_from_cdn_url():
    url = (
        "https://appdl-1-drcn.dbankcdn.com/dl/appdl/application/apk/bc/"
        "bc2a32d236ff4485b9d6a1ee0461e19e/com.huawei.smarthome.2606131023.apk"
    )
    assert extract_filename(url, "C10406921") == "com.huawei.smarthome.2606131023.apk"


def test_extract_filename_strips_query():
    url = "https://store-drcn.hispace.dbankcloud.com/dl/appdl/x/com.example.app.apk?maple=0&trackId=0"
    assert extract_filename(url, "C100") == "com.example.app.apk"


def test_extract_filename_fallback_when_no_apk():
    url = "https://appgallery.cloud.huawei.com/appdl/C100130495"
    assert extract_filename(url, "C100130495") == "C100130495.apk"
