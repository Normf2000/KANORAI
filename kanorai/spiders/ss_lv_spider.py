import scrapy
import re
from datetime import datetime
from urllib.parse import urljoin, urlencode
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from kanorai.items import ApartmentItem

class EnhancedSsLvSpider(CrawlSpider):
    name = 'kanorai_pro_enhanced'
    allowed_domains = ['ss.lv']
    custom_settings = {
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS': 4,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'ZYTE_SMARTPROXY_ENABLED': True,
        'RETRY_TIMES': 2
    }

    rules = (
        Rule(
            LinkExtractor(
                restrict_xpaths='//a[contains(text(), "Nākamie")]',
                tags=['a'],
                attrs=['href']
            ),
            follow=True
        ),
        Rule(
            LinkExtractor(
                restrict_css='tr[id^="tr_"]:not(.head_line)',
                deny=('/filter/',)
            ),
            callback='parse_item'
        ),
    )

    def __init__(self, min_price=450, **kwargs):
        self.min_price = float(min_price)
        self.base_url = 'https://www.ss.lv/lv/real-estate/flats/riga/centre/'
        super().__init__(**kwargs)
        self.start_urls = [self.build_start_url()]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                errback=self.handle_error,
                meta={
                    'zyte_smartproxy': True,
                    'zyte_smartproxy_extra': {
                        'proxy_country': 'lv'
                    }
                }
            )

    def handle_error(self, failure):
        self.logger.error(f"Proxy error: {failure.value}")

    def build_start_url(self):
        return f"{self.base_url}?{urlencode({'sell_type': '2'})"

    # Keep all other methods (parse_item, parse_pricing, etc.) 
    # from previous answer unchanged - just remove any "today" checks
