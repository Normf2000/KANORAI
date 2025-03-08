import scrapy
from urllib.parse import urlencode
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import re
from datetime import datetime
from kanorai.items import ApartmentItem

class EnhancedSsLvSpider(CrawlSpider):
    name = "kanorai_pro_enhanced"
    allowed_domains = ["ss.lv"]
    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS": 2,
        "RETRY_TIMES": 5,
        "ZYTE_SMARTPROXY_ENABLED": True,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "COOKIES_ENABLED": True,
        "FEED_FORMAT": "json",
        "FEED_URI": "apartments.json",
        "FEED_EXPORT_ENCODING": "utf-8"
    }

    rules = (
        Rule(LinkExtractor(restrict_xpaths="//a[contains(text(), 'Nākamie')]"), follow=True),
        Rule(LinkExtractor(restrict_css="tr[id^='tr_']:not(.head_line)"), callback="parse_item"),
    )

    def __init__(self, min_price=450, **kwargs):
        self.min_price = float(min_price)
        self.base_url = "https://www.ss.lv/lv/real-estate/flats/riga/centre/"
        super().__init__(**kwargs)
        self.start_urls = [f"{self.base_url}?{urlencode({'sell_type': '2'})}"]

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

    def parse_item(self, response):
        self.logger.info(f"🔍 Parsing listing: {response.url}")
        
        item = ApartmentItem()
        
        # Extract transaction type
        item['transaction_type'] = response.xpath('//td[contains(., "Darījuma veids")]/following-sibling::td/text()').get(default="").strip()
        
        # Extract price
        price_text = response.css('.ads_price::text').get(default="")
        price_data = self.parse_pricing(price_text)
        if not price_data or price_data["price"] < self.min_price:
            self.logger.warning(f"❌ Skipping {response.url} - Invalid price")
            return
        
        # Extract furniture status
        item['furniture_status'] = response.xpath('//td[contains(., "Mēbele")]/following-sibling::td/text()').get(default="").strip()
        
        # Add other fields
        item.update(price_data)
        item['url'] = response.url
        item['description'] = " ".join(response.css('#msg_div_msg::text').getall()).strip()
        item['posted_date'] = response.css('.msg_footer::text').get(default="").strip()
        
        # Validation checks
        if not self.is_valid_item(item):
            return
        
        self.logger.info(f"✅ Saving item: {item}")
        yield item

    def parse_pricing(self, price_text):
        """ Improved price parsing """
        clean_text = price_text.replace("\xa0", "").replace(" ", "").replace(",", ".")
        if match := re.search(r"(\d+\.?\d*)", clean_text):
            return {
                "price": float(match.group(1)),
                "currency": "€" if "€" in price_text else "EUR"
            }
        return None

    def is_valid_item(self, item):
        """ Consolidated validation checks """
        checks = [
            item.get('transaction_type') == "Pārdod",
            item.get('price', 0) >= self.min_price,
            "Bez mēbelēm" not in item.get('furniture_status', ""),
            bool(item.get('description'))
        ]
        
        if not all(checks):
            self.logger.warning(f"❌ Invalid item: {dict(item)}")
            return False
        return True

    def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure.value}")
