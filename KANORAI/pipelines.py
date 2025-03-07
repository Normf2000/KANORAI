from scrapy.exceptions import DropItem

class ValidationPipeline:
    def process_item(self, item, spider):
        if not all([item['true_bedrooms'], item['bathrooms'], item['price']]):
            raise DropItem("Missing critical fields")
        return item

class ExportPipeline:
    def process_item(self, item, spider):
        # Add any final export formatting here
        return item