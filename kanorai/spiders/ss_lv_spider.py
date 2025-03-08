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
        "CONCURRENT_REQUESTS": 4,
        "RETRY_TIMES": 5,
        "ZYTE_SMARTPROXY_ENABLED": True,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "COOKIES_ENABLED": True
    }

    rules = (
        Rule(LinkExtractor(restrict_xpaths="//a[contains(text(), 'Nākamie')]"), follow=True),
        Rule(LinkExtractor(restrict_css="tr[id^='tr_']:not(.head_line)"), callback="parse_item"),
    )

    def __init__(self, min_price=450, scrape_today_only=False, **kwargs):
        self.min_price = float(min_price)
        self.scrape_today_only = scrape_today_only
        self.base_url = "https://www.ss.lv/lv/real-estate/flats/riga/centre/filter/"
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
                        "javascript": True,  # Enable JavaScript execution
                        "headers": {"Accept-Language": "lv, en-US;q=0.7"}
                    }
                },
                errback=self.handle_error
            )

    def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure.value}")

    def parse(self, response):
        self.logger.info(f"Parsing URL: {response.url}")
        listings = response.css("tr[id^='tr_']:not(.head_line)")
        self.logger.info(f"Found {len(listings)} listings")
        for listing in listings:
            item = {
                'transaction_type': listing.xpath(".//td[3]/text()").get(),
                'price': listing.xpath(".//td[5]/text()").get(),
                'url': response.urljoin(listing.css("a.am::attr(href)").get())
            }
            self.logger.info(f"Extracted item: {item}")  # Debugging Log

            # Ensure the listing is for "Izīrē" only
            transaction_type = item['transaction_type']
            if transaction_type != "Izīrē":
                continue

            # Price validation
            price_data = self.parse_pricing(item['price'])
            if not price_data or price_data["price"] < self.min_price:
                continue

            # Bedroom validation
            bedroom_data = self.parse_rooms(listing)
            if not bedroom_data.get("true_bedrooms") or not (2 <= bedroom_data["true_bedrooms"] <= 3):
                continue

            # Bathroom validation
            bathroom_data = self.parse_bathrooms(listing)
            if not bathroom_data or not (1 <= bathroom_data["bathrooms"] <= 2):
                continue

            item.update(price_data)
            item.update(bedroom_data)
            item.update(bathroom_data)
            item.update(self.parse_utilities(listing))
            item['description'] = self.parse_description(listing)
            item['posted_date'] = self.parse_post_date(listing)
            item['property_type'] = transaction_type
            item['is_daily_listing'] = "šodien" in (listing.css(".msg_footer::text").get() or "").lower()
            item['airbnb_potential'] = self.calculate_potential(bedroom_data["true_bedrooms"])

            if self.validate_item(item):
                yield item

    def parse_pricing(self, price_text):
        clean_text = price_text.replace("\xa0", "").replace(" ", "")
        if match := re.search(r"(\d+[\d,.]*)", clean_text):
            price = float(match.group(1).replace(",", "."))
            return {
                "price": price,
                "currency": "€" if "€" in price_text else "EUR"
            }
        return None

    def parse_rooms(self, listing):
        bedrooms = listing.xpath(".//td[contains(text(), 'Guļamistabas')]/following-sibling::td/text()").get()
        total_rooms = listing.xpath(".//td[contains(text(), 'Istabu skaits')]/following-sibling::td/text()").get()
        
        true_bedrooms = None
        if bedrooms and bedrooms.isdigit():
            true_bedrooms = int(bedrooms)
        elif total_rooms and total_rooms.isdigit():
            true_bedrooms = max(1, int(total_rooms) - 1)
        else:
            if match := re.search(r"(\d+)\s+(guļamistabas|istabas)", listing.get(), re.IGNORECASE):
                true_bedrooms = int(match.group(1))

        return {
            "true_bedrooms": true_bedrooms,
            "total_rooms": int(total_rooms) if total_rooms and total_rooms.isdigit() else None
        }

    def parse_bathrooms(self, listing):
        bathrooms = listing.xpath(".//td[contains(text(), 'Vannas istaba')]/following-sibling::td/text()").get()
        if not bathrooms:
            text = listing.get().lower()
            if match := re.search(r"(\d+)\s+(vannas|san\.?\s*mezgl)", text):
                bathrooms = match.group(1)
            elif any(kw in text for kw in ["vanna", "sanmezgls", "duša"]):
                bathrooms = 1

        return {"bathrooms": int(bathrooms) if bathrooms and bathrooms.isdigit() else None}

    def parse_utilities(self, listing):
        utilities_text = listing.xpath(".//td[contains(text(), 'Komunālie')]/following-sibling::td/text()").get()
        if not utilities_text:
            utilities_text = listing.get()
            
        numbers = [float(n) for n in re.findall(r"\d+", utilities_text)]
        return {
            "utilities_min": min(numbers) if numbers else None,
            "utilities_max": max(numbers) if numbers else None
        }

    def parse_description(self, listing):
        return " ".join([
            p.strip() for p in listing.css("#msg_div_msg::text").getall()
            if p.strip()
        ]) or None

    def parse_post_date(self, listing):
        date_str = listing.css(".msg_footer::text").get("")
        if "šodien" in date_str.lower():
            return datetime.now().strftime("%Y-%m-%d")
        return date_str.strip() or None

    def calculate_potential(self, bedrooms):
        return "High" if bedrooms in (2, 3) else "Medium"

    def validate_item(self, item):
        return all([
            item.get("price") and item["price"] >= self.min_price,
            item.get("true_bedrooms") and 2 <= item["true_bedrooms"] <= 3,
            item.get("bathrooms") and 1 <= item["bathrooms"] <= 2,
            item.get("property_type") == "Izīrē"
        ])
