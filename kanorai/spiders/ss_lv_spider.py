import scrapy
from urllib.parse import urlencode
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import re
from datetime import datetime
from kanorai.items import ApartmentItem  # Ensure this import is correct

class EnhancedSsLvSpider(CrawlSpider):
    name = "kanorai_pro_enhanced"
    allowed_domains = ["ss.lv"]
    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS": 4,
        "RETRY_TIMES": 5,
        "ZYTE_SMARTPROXY_ENABLED": True,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    rules = (
        Rule(LinkExtractor(restrict_xpaths="//a[contains(text(), 'Nākamie')]"), follow=True),
        Rule(LinkExtractor(restrict_css="tr[id^='tr_']:not(.head_line)"), callback="parse_item"),
    )

    def __init__(self, min_price=450, scrape_today_only=False, **kwargs):
        self.min_price = float(min_price)
        self.scrape_today_only = scrape_today_only  # Add an argument to control scraping today's listings only
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
                errback=self.handle_error  # Add error handling
            )

    def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure.value}")

    def parse_item(self, response):
        # Price validation
        price_data = self.parse_pricing(response)
        if not price_data or price_data["price"] < self.min_price:
            return

        # Bedroom validation
        bedroom_data = self.parse_rooms(response)
        if not bedroom_data.get("true_bedrooms") or not (2 <= bedroom_data["true_bedrooms"] <= 6):
            return

        item = ApartmentItem(
            url=response.url,
            **price_data,
            **bedroom_data,
            **self.parse_bathrooms(response),
            **self.parse_utilities(response),
            description=self.parse_description(response),
            posted_date=self.parse_post_date(response),
            property_type=response.css("td.ads_opt_name:contains('Darījuma veids') + td::text").get(),
            is_daily_listing="šodien" in (response.css(".msg_footer::text").get() or "").lower(),
            airbnb_potential=self.calculate_potential(bedroom_data["true_bedrooms"])
        )

        if self.validate_item(item):
            yield item

    def parse_pricing(self, response):
        price_text = response.css(".ads_price::text").get("")
        clean_text = price_text.replace("\xa0", "").replace(" ", "")
        if match := re.search(r"(\d+[\d,.]*)", clean_text):
            price = float(match.group(1).replace(",", "."))
            return {
                "price": price,
                "currency": "€" if "€" in price_text else "EUR"
            }
        return None

    def parse_rooms(self, response):
        bedrooms = response.xpath("//td[contains(., 'Guļamistabas')]/following-sibling::td/text()").get()
        total_rooms = response.xpath("//td[contains(., 'Istabu skaits')]/following-sibling::td/text()").get()
        
        true_bedrooms = None
        if bedrooms and bedrooms.isdigit():
            true_bedrooms = int(bedrooms)
        elif total_rooms and total_rooms.isdigit():
            true_bedrooms = max(1, int(total_rooms) - 1)
        else:
            if match := re.search(r"(\d+)\s+(guļamistabas|istabas)", response.text, re.IGNORECASE):
                true_bedrooms = int(match.group(1))

        return {
            "true_bedrooms": true_bedrooms,
            "total_rooms": int(total_rooms) if total_rooms and total_rooms.isdigit() else None
        }

    def parse_bathrooms(self, response):
        bathrooms = response.xpath("//td[contains(., 'Vannas istaba')]/following-sibling::td/text()").get()
        if not bathrooms:
            text = response.text.lower()
            if match := re.search(r"(\d+)\s+(vannas|san\.?\s*mezgl)", text):
                bathrooms = match.group(1)
            elif any(kw in text for kw in ["vanna", "sanmezgls", "duša"]):
                bathrooms = 1

        return {"bathrooms": int(bathrooms) if bathrooms and bathrooms.isdigit() else None}

    def parse_utilities(self, response):
        utilities_text = response.xpath("//td[contains(., 'Komunālie')]/following-sibling::td/text()").get()
        if not utilities_text:
            utilities_text = response.text
            
        numbers = [float(n) for n in re.findall(r"\d+", utilities_text)]
        return {
            "utilities_min": min(numbers) if numbers else None,
            "utilities_max": max(numbers) if numbers else None
        }

    def parse_description(self, response):
        return " ".join([
            p.strip() for p in response.css("#msg_div_msg::text").getall()
            if p.strip()
        ]) or None

    def parse_post_date(self, response):
        date_str = response.css(".msg_footer::text").get("")
        if "šodien" in date_str.lower():
            return datetime.now().strftime("%Y-%m-%d")
        return date_str.strip() or None

    def calculate_potential(self, bedrooms):
        return "High" if bedrooms in (2, 3) else "Medium"

    def validate_item(self, item):
        return all([
            item.get("price") and item["price"] >= self.min_price,
            item.get("true_bedrooms") and 2 <= item["true_bedrooms"] <= 6,
            item.get("bathrooms") is not None,
            item.get("property_type")
        ])
