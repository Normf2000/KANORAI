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
        Rule(  # Pagination rule - CHANGED
            LinkExtractor(
                restrict_css='a.d1:has(img[alt="Nākošā lapa"])',
            ),
            follow=True
        ),
        Rule(  # Item detail rule - KEEP THIS
            LinkExtractor(
                restrict_css='tr[id^="tr_"]:not(.head_line)',
                deny=('/filter/',)
            ),
            callback='parse_item'
        ),
    )

    # PROPERLY INDENTED __init__ METHOD
    def __init__(self, check_today_only="False", min_bedrooms="2", max_bedrooms="6", **kwargs):
        # Convert string arguments to proper types
        self.check_today_only = check_today_only.lower() == "true"
        self.min_bedrooms = int(min_bedrooms)
        self.max_bedrooms = int(max_bedrooms)
        
        # Validate arguments
        self.validate_arguments()
        
        # Existing initialization
        self.start_urls = [self.build_start_url()]
        super().__init__(**kwargs)

    # VALIDATION METHOD (PROPER INDENTATION)
    def validate_arguments(self):
        if not (2 <= self.min_bedrooms <= 6):
            raise ValueError("min_bedrooms must be between 2-6")
        if not (2 <= self.max_bedrooms <= 6):
            raise ValueError("max_bedrooms must be between 2-6")
        if self.min_bedrooms > self.max_bedrooms:
            raise ValueError("min_bedrooms cannot exceed max_bedrooms")
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
        params = {'sell_type': '2'}
        
        # Add today param if needed
        if self.check_today_only:  # Now using converted boolean
            params['today'] = '1'
            
        return f"{base}?{urlencode(params)}"

    def parse_item(self, response):
        # Validate critical element exists before parsing
        if not response.css('.ads_price::text').get():
            self.logger.warning(f"Skipping invalid listing: Missing price at {response.url}")
            return
        # Date filtering (update this check)
        if self.check_today_only:  # Use instance variable
            if not posted_date or 'šodien' not in posted_date.lower():
                return
        
        try:
            item = ApartmentItem()
            item['url'] = response.url
            
            # Core fields with validation
            item['property_type'] = response.css('td.ads_opt_name:contains("Darījuma veids") + td::text').get()
            item = self.parse_pricing(response, item)
            item = self.parse_rooms(response, item)
            item = self.parse_bathrooms(response, item)
            
            # Description handling
            desc = response.css('#msg_div_msg::text').getall()
            item['description'] = ' '.join(desc).strip() if desc else None
            
            # Date handling
            posted_date = response.css('.msg_footer::text').get()
            item['posted_date'] = posted_date.strip() if posted_date else None
            
            # Business logic
            item['is_daily_listing'] = 'šodien' in (item.get('posted_date') or '').lower()
            item['airbnb_potential'] = self.calculate_potential(item)
            
            if self.validate_item(item):
                self.logger.debug(f"Successfully parsed: {response.url}")
                yield item

        except Exception as e:
            self.logger.error(f"Failed to parse {response.url}: {str(e)}")
            self.logger.debug(f"HTML snippet:\n{response.text[:1000]}")
            return

    def parse_pricing(self, response, item):
        price_text = response.css('.ads_price::text').get()
        if price_text:
            price = re.sub(r'[^\d.]', '', price_text.replace(' ', '').replace('\xa0', ''))
            item['price'] = float(price) if price else None
            item['currency'] = '€' if '€' in price_text else None
        return item

    def parse_rooms(self, response, item):
        # Structured data
        bedrooms = response.xpath('//td[contains(., "Guļamistabas")]/following-sibling::td/text()').get()
        total_rooms = response.xpath('//td[contains(., "Istabu skaits")]/following-sibling::td/text()').get()
        
        # Fallback to description analysis
        if not bedrooms:
            desc = response.text.lower()
            match = re.search(r'(\d+)\s*(guļamistabas|g\.?\s*ist\.?)', desc)
            if match:
                bedrooms = int(match.group(1))
        
        try:
            item['true_bedrooms'] = int(bedrooms) if bedrooms else None
            item['total_rooms'] = int(total_rooms) if total_rooms else None
            
            # Calculate bedrooms from total rooms if missing
            if not item['true_bedrooms'] and item['total_rooms']:
                item['true_bedrooms'] = max(1, item['total_rooms'] - 1)
                
        except ValueError:
            item['true_bedrooms'] = None
            item['total_rooms'] = None
            
        return item

    def parse_bathrooms(self, response, item):
        # Structured data
        bathrooms = response.xpath('//td[contains(., "Vannas istaba")]/following-sibling::td/text()').get()
        
        # Fallback to description analysis
        if not bathrooms:
            desc = response.text.lower()
            patterns = [
                r'(\d+)\s*(vannas istabas|vannas)',
                r'(\d+)\s*san\.?\s*mezgl',
                r'(\d+)\s*wc'
            ]
            for pattern in patterns:
                match = re.search(pattern, desc)
                if match:
                    bathrooms = int(match.group(1))
                    break
            else:
                if any(x in desc for x in ['vanna', 'sanmezgls']):
                    bathrooms = 1

        try:
            item['bathrooms'] = int(bathrooms) if bathrooms else None
        except ValueError:
            item['bathrooms'] = None
            
        return item

    def calculate_potential(self, item):
        # Your business logic here
        if item.get('true_bedrooms') and 2 <= item['true_bedrooms'] <= 3:
            return "High"
        return "Medium"

    def validate_item(self, item):
        required_fields = [
            'property_type',
            'price',
            'true_bedrooms',
            'bathrooms'
        ]
        return all(item.get(field) for field in required_fields)
