import scrapy
from urllib.parse import urlencode
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import re
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
        "FEEDS": {
            "apartments.json": {
                "format": "json",
                "encoding": "utf-8",
                "overwrite": True
            }
        }
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
        item = ApartmentItem()
        item['url'] = response.url
        
        # Price extraction
        price_text = response.css('.ads_price::text').get('')
        if price_data := self.parse_pricing(price_text):
            if price_data['price'] < self.min_price:
                return
            item.update(price_data)
        else:
            return
        
        # Transaction type
        item['transaction_type'] = response.xpath('//td[contains(., "Darījuma veids")]/following-sibling::td/text()').get('').strip()
        if item['transaction_type'] != "Pārdod":
            return
        
        # Furniture status
        item['furniture_status'] = response.xpath('//td[contains(., "Mēbele")]/following-sibling::td/text()').get('').strip()
        if "Bez mēbelēm" in item['furniture_status']:
            return
        
        # Description
        item['description'] = ' '.join(response.css('#msg_div_msg::text').getall()).strip()
        
        # Date
        item['posted_date'] = response.css('.msg_footer::text').get('').strip()
        
        yield item

    def parse_pricing(self, text):
        clean = text.replace('\xa0', '').replace(' ', '').replace(',', '.')
        if match := re.search(r'(\d+\.?\d*)', clean):
            return {
                'price': float(match.group(1)),
                'currency': '€' if '€' in text else 'EUR'
            }
        return None

    def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure.value}")
