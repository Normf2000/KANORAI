import scrapy
from urllib.parse import urlencode
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import re
from datetime import datetime
from kanorai.items import ApartmentItem  # Ensure this exists in your project

class EnhancedSsLvSpider(CrawlSpider):
    name = "kanorai_pro_enhanced"
    allowed_domains = ["ss.lv"]
    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS": 4,
        "RETRY_TIMES": 5,
        "ZYTE_SMARTPROXY_ENABLED": True,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "COOKIES_ENABLED": True,
        "FEEDS": {
            "apartments.json": {
                "format": "json",
                "encoding": "utf8",
                "store_empty": False,
                "indent": 4,
            }
        }
    }

    rules = (
        Rule(LinkExtractor(restrict_xpaths="//a[contains(text(), 'Nākamie')]"), follow=True),
        Rule(LinkExtractor(restrict_css="tr[id^='tr_']:not(.head_line)"), callback="parse_item"),
    )

    def __init__(self, min_price=450, scrape_today_only=False, **kwargs):
        self.min_price = float(min_price)
        self.scrape_today_only = scrape_today_only
        self.base_url = "https://www.ss.lv/lv/real-estate/flats/riga/centre/filter/?sell_type=2"
        super().__init__(**kwargs)
        self.start_urls = [self.base_url]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={
                    "zyte_smartproxy": True,
                    "zyte_smartproxy_extra": {
                        "proxy_country": "lv",
                        "javascript": True,
                        "headers": {"Accept-Language": "lv, en-US;q=0.7"}
                    }
                },
                errback=self.handle_error
            )

    def handle_error(self, failure):
        self.logger.error(f"🚨 Request failed: {failure.value}")

    def parse(self, response):
        self.logger.info(f"🔍 Parsing URL: {response.url}")
        listings = response.css("tr[id^='tr_']:not(.head_line)")
        self.logger.info(f"🔍 Found {len(listings)} listings")

        extracted_items = []
        for listing in listings:
            item = {
                "transaction_type": listing.xpath("normalize-space(.//td[2]/text())").get(),
                "price": listing.xpath("normalize-space(.//td[5]/text())").get(),
                "url": response.urljoin(listing.css("a.am::attr(href)").get()),
                "furniture_status": listing.xpath(
                    ".//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'mēbel')]/text()"
                ).get(default="").strip(),
            }

            self.logger.info(f"🔍 Extracted BEFORE FILTER: {item}")

            # ✅ 1. Skip listings without transaction type
            if not item["transaction_type"]:
                self.logger.warning(f"❌ Skipping {item['url']} - Missing transaction type")
                continue

            # ✅ 2. Only allow "Izīrē" (For Rent)
            if "Izīrē" not in item["transaction_type"]:
                self.logger.warning(f"❌ Skipping {item['url']} - Not 'Izīrē' (Value: {item['transaction_type']})")
                continue

            # ✅ 3. Ensure price is valid
            price_data = self.parse_pricing(item["price"])
            if not price_data or price_data["price"] < self.min_price:
                self.logger.warning(f"❌ Skipping {item['url']} - Price too low ({price_data})")
                continue
            item.update(price_data)

            # ✅ 4. Filter based on furniture status
            if "Bez mēbelēm" in item["furniture_status"]:
                self.logger.warning(f"❌ Skipping {item['url']} - No furniture")
                continue
            if "Mēbelētu" not in item["furniture_status"]:
                self.logger.warning(f"❌ Skipping {item['url']} - Not marked as furnished")
                continue

            self.logger.info(f"✅ Saved: {item}")
            extracted_items.append(item)

        if not extracted_items:
            self.logger.warning("⚠️ No listings matched criteria. Check filters.")

        return extracted_items  # ✅ Important: Ensure Scrapy actually returns data

    def parse_pricing(self, price_text):
        """ Extract price from the text """
        if not price_text:
            return None

        clean_text = price_text.replace("\xa0", "").replace(" ", "").replace("€", "")
        match = re.search(r"(\d+[\d,.]*)", clean_text)
        if match:
            price = float(match.group(1).replace(",", "."))
            return {"price": price, "currency": "€"}
        return None
