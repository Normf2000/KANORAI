import sys
import os

# Add project directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BOT_NAME = "kanorai"
SPIDER_MODULES = ["kanorai.spiders"]
NEWSPIDER_MODULE = "kanorai.spiders"

# Zyte Smart Proxy settings
ZYTE_SMARTPROXY_ENABLED = True
ZYTE_SMARTPROXY_APIKEY = "c531770e0c3b4db793a517d3a001a341"
ZYTE_SMARTPROXY_URL = "http://api.zyte.com:8011"  # Correct proxy URL

DOWNLOADER_MIDDLEWARES = {
    "scrapy_zyte_smartproxy.ZyteSmartProxyMiddleware": 610,
}

ITEM_PIPELINES = {
    "kanorai.pipelines.ValidationPipeline": 300,
    "kanorai.pipelines.ExportPipeline": 800,
}

FEEDS = {
    "apartments.json": {
        "format": "json",
        "encoding": "utf8",
        "indent": 2,
        "overwrite": True
    }
}

# Custom settings
CONCURRENT_REQUESTS = 4  # Increased from default 1
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 1.5  # Reduced from 2 seconds
AUTOTHROTTLE_ENABLED = True
RETRY_TIMES = 5
RETRY_HTTP_CODES = [407, 429, 503]
RETRY_PRIORITY_ADJUST = -1

# Save logs to a file
LOG_FILE = "scrapy_log.txt"

# Correct setting for REQUEST_FINGERPRINTER_IMPLEMENTATION
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"

FEEDS = {
    'apartments.json': {
        'format': 'json',
        'encoding': 'utf8',
        'store_empty': False,  # Ensures empty results are NOT saved
        'indent': 4,  # Pretty-print JSON
    }
}
