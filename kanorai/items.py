from scrapy import Item, Field

class ApartmentItem(Item):
    url = Field()
    price = Field()
    currency = Field()
    true_bedrooms = Field()  # Actual bedroom count
    total_rooms = Field()
    bathrooms = Field()
    area = Field()
    location = Field()
    posted_date = Field()
    property_type = Field()
    description = Field()
    is_daily_listing = Field()
    airbnb_potential = Field()
