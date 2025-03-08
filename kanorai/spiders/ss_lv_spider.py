import scrapy
from urllib.parse import urlencode
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import re
from datetime import datetime

class EnhancedSsLvSpider(CrawlSpider):
    name = "kanorai_pro_enhanced"
    allowed_domains = ["ss.lv"]
    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS": 4,
        "RETRY_TIMES": 5,
        "ZYTE_SMARTPROXY_ENABLED": True,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "COOKIES_ENABLED": True
    }

    start_urls = ["https://www.ss.lv/lv/real-estate/flats/riga/centre/filter/"]

    def parse(self, response):
        self.logger.info(f"🔍 Parsing URL: {response.url}")
        listings = response.css("tr[id^='tr_']:not(.head_line)")
        self.logger.info(f"🔍 Found {len(listings)} listings")

        for listing in listings:
            item = {
                'transaction_type': listing.xpath(".//td[2]/text()").get(default="").strip(),
                'price': listing.xpath(".//td[5]/text()").get(default="").strip(),
                'url': response.urljoin(listing.css("a.am::attr(href)").get()),
                'furniture_status': listing.xpath(
                    ".//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'mēbel')]/text()"
                ).get(default="").strip(),
            }

            self.logger.info(f"🔍 Extracted BEFORE FILTER: {item}")

            # ✅ 1. Skip listings without transaction type
            if not item['transaction_type']:
                self.logger.warning(f"❌ Skipping {item['url']} - Missing transaction type")
                continue

            # ✅ 2. Only allow "Izīrē" (For Rent)
            if item['transaction_type'] != "Izīrē":
                self.logger.warning(f"❌ Skipping {item['url']} - Not 'Izīrē' (Value: {item['transaction_type']})")
                continue

            # ✅ 3. Ensure price is valid
            price_data = self.parse_pricing(item['price'])
            if not price_data or price_data["price"] < 450:  # Minimum 450 EUR
                self.logger.warning(f"❌ Skipping {item['url']} - Price too low")
                continue
            item.update(price_data)

            # ✅ 4. Filter based on furniture status
            if "Bez mēbelēm" in item['furniture_status']:
                self.logger.warning(f"❌ Skipping {item['url']} - No furniture")
                continue
            if "Mēbelētu" not in item['furniture_status']:
                self.logger.warning(f"❌ Skipping {item['url']} - Not marked as furnished")
                continue

            self.logger.info(f"✅ Saved: {item}")
            yield item

        self.logger.info(f"✅ Scraped data saved to: apartments.json")

    def parse_pricing(self, price_text):
        """ Extract price from the text """
        clean_text = price_text.replace("\xa0", "").replace(" ", "")
        match = re.search(r"(\d+[\d,.]*)", clean_text)
        if match:
            price = float(match.group(1).replace(",", "."))
            return {"price": price, "currency": "€" if "€" in price_text else "EUR"}
        return None
