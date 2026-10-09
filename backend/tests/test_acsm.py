from datetime import datetime, timezone

import pytest

from liseo.acsm import AcsmError, parse_acsm

SAMPLE = """<?xml version="1.0"?>
<fulfillmentToken fulfillmentType="loan" auth="user"
    xmlns="http://ns.adobe.com/adept"
    xmlns:dc="http://purl.org/dc/elements/1.1/">
  <operatorURL>http://acs4.edenlivres.fr/fulfillment</operatorURL>
  <transaction>eden:Loan:example</transaction>
  <expiration>2026-12-01T18:00:00+01:00</expiration>
  <resourceItemInfo>
    <resourceItem>
      <metadata>
        <dc:title>Plus grand que le ciel</dc:title>
        <dc:creator>Virginie Grimaldi</dc:creator>
        <dc:format>application/epub+zip</dc:format>
      </metadata>
    </resourceItem>
  </resourceItemInfo>
  <permissions>
    <display>
      <until>2027-01-15T18:00:00+01:00</until>
    </display>
  </permissions>
</fulfillmentToken>
""".encode()


def test_parse_loan_metadata():
    info = parse_acsm(SAMPLE)
    assert info.fulfillment_type == "loan"
    assert info.auth == "user"
    assert info.operator_host == "acs4.edenlivres.fr"
    assert info.transaction == "eden:Loan:example"
    assert info.title == "Plus grand que le ciel"
    assert info.creator == "Virginie Grimaldi"
    assert info.format == "application/epub+zip"
    assert info.display_until == datetime(2027, 1, 15, 17, 0, tzinfo=timezone.utc)
    assert info.expired(datetime(2026, 10, 9, tzinfo=timezone.utc)) is False
    assert info.expired(datetime(2026, 12, 2, tzinfo=timezone.utc)) is True


def test_reject_unknown_operator_shape():
    payload = SAMPLE.replace(
        b"http://acs4.edenlivres.fr/fulfillment",
        b"file:///tmp/loan",
    )
    with pytest.raises(AcsmError):
        parse_acsm(payload)


def test_reject_entity_declaration():
    payload = b"""<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe "no">]><fulfillmentToken/>"""
    with pytest.raises(AcsmError):
        parse_acsm(payload)


def test_missing_operator():
    with pytest.raises(AcsmError):
        parse_acsm(b'<fulfillmentToken fulfillmentType="loan"/>')
