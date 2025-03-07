import scrapy
import re
from datetime import datetime
from urllib.parse import urlencode
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from pydantic import BaseModel, Field
from kanorai.items import ApartmentItem

class SsLvParams(BaseModel):
    check_today_only: bool = Field(default=False)
    min_bedrooms: int = Field(default=2, ge=2, le=6)
    max_bedrooms: int = Field(default=6, ge=2, le=6)

class SsLvSpider(CrawlSpider):
    name = 'kanorai_pro'
    allowed_domains = ['ss.lv']
    
    rules = (
        Rule(LinkExtractor(restrict_css='.navi')),
        Rule(LinkExtractor(
            restrict_css='tr[id^="tr_"]:not(.head_line)',
            deny=('/filter/',)
        ), callback='parse_item'),
    )

    def __init__(self, check_today_only=False, min_bedrooms=2, max_bedrooms=6, **kwargs):
        self.check_today_only = check_today_only
        self.bedroom_range = (min_bedrooms, max_bedrooms)
        self.start_urls = [self.build_start_url()]
        super().__init__(**kwargs)

    def build_start_url(self):
        base = 'https://www.ss.lv/lv/real-estate/flats/riga/centre/'
        params = {'sell_type': '2'}  # Izīrē filter
        if self.check_today_only:
            params['today'] = '1'
        return f"{base}?{urlencode(params)}"

def parse_item(self, response):
    # Validate critical element exists before parsing
    if not response.css('.ads_price::text').get():
        self.logger.warning(f"Skipping invalid listing: Missing price at {response.url}")
        return

    try:
        item = ApartmentItem()
        item['url'] = response.url
        
        # Core fields with validation
        item['price'] = self.parse_price(response.css('.ads_price::text').get())
        item['currency'] = '€' if '€' in response.css('.ads_price::text').get() else None
        item['bedrooms'] = response.xpath('//td[contains(., "Istabu skaits")]/following-sibling::td/text()').get()
        item['location'] = response.css('td.ads_opt_name:contains("Rajons") + td::text').get()
        
        # Description handling
        desc = response.css('#msg_div_msg::text').getall()
        item['description'] = ' '.join(desc).strip() if desc else None
        
        # Date filtering
        posted_date = response.css('.msg_footer::text').get()
        if self.check_today_only and 'šodien' not in posted_date.lower():
            return

        # Add other fields as needed...
        
        self.logger.debug(f"Successfully parsed: {response.url}")
        return item

    except Exception as e:
        self.logger.error(f"Failed to parse {response.url}: {str(e)}")
        self.logger.debug(f"HTML snippet:\n{response.text[:1000]}")  # First 1KB for debugging
        return None
        
        # Core data extraction
        item['property_type'] = response.css('td.ads_opt_name:contains("Darījuma veids") + td::text').get()
        item = self.extract_pricing(response, item)
        item = self.extract_rooms(response, item)
        item = self.extract_bathrooms(response, item)
        
        # Business logic
        item['is_daily_listing'] = 'šodien' in item.get('posted_date', '').lower()
        item['airbnb_potential'] = self.calculate_potential(item)
        
        if self.validate_item(item):
            yield item

    def extract_rooms(self, response, item):
        # Structured data
        item['true_bedrooms'] = response.xpath('//td[contains(., "Guļamistabas")]/following-sibling::td/text()').get()
        item['total_rooms'] = response.xpath('//td[contains(., "Istabu skaits")]/following-sibling::td/text()').get()
        
        # Fallback to description analysis
        if not item['true_bedrooms']:
            desc = response.text.lower()
            match = re.search(r'(\d+)\s*(guļamistabas|g\.ist)', desc)
            if match:
                item['true_bedrooms'] = int(match.group(1))
        
        # Final calculation
        try:
            item['true_bedrooms'] = int(item['true_bedrooms'] or 0)
            item['total_rooms'] = int(item['total_rooms'] or 0)
            if item['true_bedrooms'] == 0 and item['total_rooms'] > 0:
                item['true_bedrooms'] = max(1, item['total_rooms'] - 1)
        except:
            item['true_bedrooms'] = None
            item['total_rooms'] = None
            
        return item

    def extract_bathrooms(self, response, item):
        # Structured data
        item['bathrooms'] = response.xpath('//td[contains(., "Vannas istaba")]/following-sibling::td/text()').get()
        
        # Description fallback
        if not item['bathrooms']:
            desc = response.text
