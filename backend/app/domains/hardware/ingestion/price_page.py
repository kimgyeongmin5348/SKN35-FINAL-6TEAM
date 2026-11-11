"""Conservative extraction of a separately identified component price."""

import re
from html import unescape
from html.parser import HTMLParser

from app.domains.hardware.ingestion.common import price_value


def identity_text(value):
    return re.sub(r"\s+", "", unescape(value or "").removeprefix("[다나와]"))


class PricePageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = None
        self.product_codes = set()
        self.prices = []
        self.shipping_toggle = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("property") == "og:title":
            self.title = attrs.get("content")
        if attrs.get("data-productcode"):
            self.product_codes.add(attrs["data-productcode"])
        if tag == "input" and attrs.get("id") == "add_delivery":
            self.shipping_toggle = "checked" in attrs
        if (
            "sell-price" in attrs.get("class", "").split()
            and "data-base-price" in attrs
            and "data-delivery-price" in attrs
        ):
            self.prices.append((attrs["data-base-price"], attrs["data-delivery-price"]))


def parse_component_price_page(content, match):
    parser = PricePageParser()
    parser.feed(content)
    code = match.get("danawa_product_code")
    if code not in parser.product_codes or identity_text(parser.title) != identity_text(
        match.get("expected_listing_name")
    ):
        return {"verified": False, "reason": "PAGE_IDENTITY_MISMATCH"}
    prices = set(parser.prices)
    if len(prices) != 1 or parser.shipping_toggle is None:
        return {"verified": False, "reason": "NO_UNAMBIGUOUS_BASE_PRICE"}
    raw_base, raw_delivery = prices.pop()
    base = price_value(raw_base)
    if base is None or not re.fullmatch(r"\d+", raw_delivery):
        return {"verified": False, "reason": "INVALID_BASE_OR_DELIVERY_PRICE"}
    # Never subtract a presumed delivery fee from minPrice. Use the separate field.
    return {
        "verified": True,
        "product_code": code,
        "product_name": match["expected_listing_name"],
        "component_price": str(base),
        "basis": "data-base-price (delivery separately identified)",
        "delivery_price_observed": raw_delivery,
        "shipping_toggle_checked": parser.shipping_toggle,
    }
