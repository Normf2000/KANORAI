# settings.py
import sys
import os

# Add project directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BOT_NAME = 'kanorai'
SPIDER_MODULES = ['kanorai.spiders']
NEWSPIDER_MODULE = 'kanorai.spiders'

# Replace old ZYTE_SMARTPROXY settings with:
ZYTE_SMARTPROXY_ENABLED = True
ZYTE_SMARTPROXY_APIKEY = "732570a902f048d9847b20f42ba1217e"  # Get from Zyte dashboard

DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy_user_agents.middlewares.RandomUserAgentMiddleware': 400,
    'scrapy_zyte_smartproxy.ZyteSmartProxyMiddleware': 610,
}

DOWNLOADER_MIDDLEWARES = {
    'scrapy_zyte_smartproxy.ZyteSmartProxyMiddleware': 610,
}

ITEM_PIPELINES = {
    'kanorai.pipelines.ValidationPipeline': 300,
    'kanorai.pipelines.ExportPipeline': 800,
}

FEEDS = {
    'apartments.json': {
        'format': 'json',
        'encoding': 'utf8',
        'indent': 2,
        'overwrite': True
    }
}

custom_settings = {
    'CONCURRENT_REQUESTS': 4,  # Increased from default 1
    'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    'DOWNLOAD_DELAY': 1.5,  # Reduced from 2 seconds
    'AUTOTHROTTLE_ENABLED': True,
    'ZYTE_SMARTPROXY_ENABLED': True,
    'RETRY_TIMES': 2,  # Reduced from default 3
    'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429]
}
