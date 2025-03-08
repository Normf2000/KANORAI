import scrapy
import re
from urllib.parse import urljoin

class SsLvSpider(scrapy.Spider):
    name = "ss_lv_apartments"
    allowed_domains = ["ss.lv"]
    start_urls = ["https://www.ss.lv/lv/real-estate/flats/riga/centre/filter/?sell_type=2"]

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS": 4,
        "RETRY_TIMES": 5,
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

    def parse(self, response):
        self.logger.info(f"🔍 Parsing URL: {response.url}")
        listings = response.css("tr[id^='tr_']:not(.head_line)")
        self.logger.info(f"🔍 Found {len(listings)} listings")

        extracted_items = []
        for listing in listings:
            try:
                # Extract transaction type
                transaction_type = listing.xpath("normalize-space(.//td[2]//strong/text())").get()
                if not transaction_type:
                    transaction_type = listing.xpath("normalize-space(.//td[2]/text())").get()

                # Extract price
                price_raw = listing.xpath("normalize-space(.//td[5]//text())").get()
                price_clean = price_raw.replace("\xa0", "").replace(" ", "").replace("€", "") if price_raw else ""

                # Extract URL
                url = listing.css("a.am::attr(href)").get()
                full_url = urljoin(response.url, url) if url else ""

                # Extract furniture status
                furniture_status = listing.xpath(
                    "normalize-space(.//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'mēbel')]/text())"
                ).get()

                item = {
                    "transaction_type": transaction_type.strip() if transaction_type else "",
                    "price": price_clean.strip() if price_clean else "",
                    "url": full_url.strip() if full_url else "",
                    "furniture_status": furniture_status.strip() if furniture_status else "",
                }

                self.logger.info(f"🔍 Extracted BEFORE FILTER: {item}")

                # ✅ Skip if transaction type is missing
                if not item["transaction_type"]:
                    self.logger.warning(f"❌ Skipping {item['url']} - Missing transaction type")
                    continue

                # ✅ Only allow "Izīrē" (For Rent)
                if "Izīrē" not in item["transaction_type"]:
                    self.logger.warning(f"❌ Skipping {item['url']} - Not 'Izīrē' (Value: {item['transaction_type']})")
                    continue

                # ✅ Ensure price is valid
                price_numeric = re.search(r"(\d+[\d,.]*)", item["price"])
                if not price_numeric:
                    self.logger.warning(f"❌ Skipping {item['url']} - Invalid price format ({item['price']})")
                    continue

                item["price"] = float(price_numeric.group(1).replace(",", "."))
                if item["price"] < 450:  # Minimum price filter
                    self.logger.warning(f"❌ Skipping {item['url']} - Price too low ({item['price']}€)")
                    continue

                # ✅ Skip if no furniture
                if "Bez mēbelēm" in item["furniture_status"]:
                    self.logger.warning(f"❌ Skipping {item['url']} - No furniture")
                    continue

                # ✅ Skip if not marked as furnished
                if "Mēbelētu" not in item["furniture_status"]:
                    self.logger.warning(f"❌ Skipping {item['url']} - Not marked as furnished")
                    continue

                self.logger.info(f"✅ Saved: {item}")
                extracted_items.append(item)

            except Exception as e:
                self.logger.error(f"🚨 Error processing listing: {e}")

        if not extracted_items:
            self.logger.warning("⚠️ No listings matched criteria. Check filters.")

        return extracted_items  # ✅ Important: Scrapy must return data
