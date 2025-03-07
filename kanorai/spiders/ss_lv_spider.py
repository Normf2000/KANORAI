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
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'ZYTE_SMARTPROXY_ENABLED': True
    }
    
rules = (
    Rule(  # Pagination rule
        LinkExtractor(
            restrict_xpaths='//a[contains(text(), "Nākamie")]',
            tags=['a'], 
            attrs=['href']
        ),
        follow=True
    ),
    Rule(  # Item detail rule
        LinkExtractor(
            restrict_css='tr[id^="tr_"]:not(.head_line)',
            deny=('/filter/',)
        ),
        callback='parse_item'
    ),
)

    def __init__(self, check_today_only=False, min_price=450, **kwargs):
        self.check_today_only = check_today_only
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
                    'proxy_country': 'lv'  # Target Latvian IPs
                }
            }
        )
    
def handle_error(self, failure):
    self.logger.error(f"Proxy error: {failure.value}")
    
    def build_start_url(self):
        params = {'sell_type': '2'}
        if self.check_today_only:
            params['today'] = '1'
        return f"{self.base_url}?{urlencode(params)}"

    def parse_item(self, response):
        # Price validation first
        price_data = self.parse_pricing(response)
        if not price_data or price_data['price'] < self.min_price:
            return

        # Bedroom validation
        bedroom_data = self.parse_rooms(response)
        if not (2 <= bedroom_data['true_bedrooms'] <= 6):
            return

        # Main item parsing
        item = ApartmentItem(
            url=response.url,
            **price_data,
            **bedroom_data,
            **self.parse_bathrooms(response),
            **self.parse_utilities(response),
            description=self.parse_description(response),
            posted_date=self.parse_post_date(response),
            property_type=response.css('td.ads_opt_name:contains("Darījuma veids") + td::text').get(),
            is_daily_listing='šodien' in (item.get('posted_date') or '').lower(),
            airbnb_potential=self.calculate_potential(bedroom_data['true_bedrooms'])
        )

        if self.validate_item(item):
            yield item

    def parse_pricing(self, response):
        price_text = response.css('.ads_price::text').get('')
        price_match = re.search(r'[\d,.\s]+', price_text.replace('\xa0', ''))
        if not price_match:
            return None
            
        price = float(price_match.group().replace(',', '.').replace(' ', ''))
        return {
            'price': price,
            'currency': '€' if '€' in price_text else None
        }

    def parse_rooms(self, response):
        # Direct bedroom extraction
        bedrooms = response.xpath('//td[contains(., "Guļamistabas")]/following-sibling::td/text()').get()
        total_rooms = response.xpath('//td[contains(., "Istabu skaits")]/following-sibling::td/text()').get()

        # Intelligent bedroom calculation
        if bedrooms:
            true_bedrooms = int(bedrooms)
        elif total_rooms:
            true_bedrooms = max(1, int(total_rooms) - 1)  # Assume last room is living area
        else:
            # Fallback to description analysis
            desc = response.text.lower()
            match = re.search(r'(?:guļamistabas|istabas)\D*(\d+)', desc)
            true_bedrooms = int(match.group(1)) if match else None

        return {
            'true_bedrooms': true_bedrooms,
            'total_rooms': int(total_rooms) if total_rooms else None
        }

    def parse_bathrooms(self, response):
        # Structured data extraction
        bathrooms = response.xpath('//td[contains(., "Vannas istaba")]/following-sibling::td/text()').get()
        
        if not bathrooms:
            desc = response.text.lower()
            # Improved Latvian bathroom terminology matching
            patterns = [
                r'(?:(?:san\.? mezgls?|vannas)\D*)(\d+)',
                r'(\d+)\s*(?:vannas istabas|vannas|wc)',
                r'san\.?\s*mezgls?\D*(\d+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, desc)
                if match:
                    bathrooms = int(match.group(1))
                    break
            else:
                bathrooms = 1 if any(kw in desc for kw in ['vanna', 'sanmezgls', 'duša']) else None

        return {'bathrooms': int(bathrooms) if bathrooms else None}

    def parse_utilities(self, response):
        utilities_text = response.xpath('//td[contains(., "Komunālie")]/following-sibling::td/text()').get()
        if not utilities_text:
            desc = response.text.lower()
            utilities_match = re.search(r'komunālie.*?(\d+)\s*-\s*(\d+)\s*€', desc, re.IGNORECASE)
            if utilities_match:
                return {
                    'utilities_min': float(utilities_match.group(1)),
                    'utilities_max': float(utilities_match.group(2))
                }
            return {'utilities_min': None, 'utilities_max': None}
        
        # Handle different utility formats
        numbers = re.findall(r'\d+', utilities_text)
        if len(numbers) >= 2:
            return {
                'utilities_min': float(numbers[0]),
                'utilities_max': float(numbers[1])
            }
        return {'utilities_min': None, 'utilities_max': None}

    def parse_description(self, response):
        desc_parts = response.css('#msg_div_msg::text').getall()
        return ' '.join(part.strip() for part in desc_parts if part.strip())

    def parse_post_date(self, response):
        date_str = response.css('.msg_footer::text').get('')
        if 'šodien' in date_str.lower():
            return datetime.today().strftime('%Y-%m-%d')
        return date_str.strip()

    def calculate_potential(self, bedrooms):
        return "High" if 2 <= bedrooms <= 3 else "Medium"

    def validate_item(self, item):
        required = [
            item['price'] >= self.min_price,
            2 <= item['true_bedrooms'] <= 6,
            item.get('bathrooms') is not None,
            item.get('property_type')
        ]
        return all(required)
