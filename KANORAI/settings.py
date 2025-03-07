# Add this at the top
import sys
sys.path.append('/app/python/lib/python3.11/site-packages')

BOT_NAME = 'kanorai'
SPIDER_MODULES = ['kanorai.spiders']
NEWSPIDER_MODULE = 'kanorai.spiders'

# Replace old ZYTE_SMARTPROXY settings with:
ZYTE_SMARTPROXY_APIKEY = "732570a902f048d9847b20f42ba1217e"  # Get from Zyte dashboard
DOWNLOADER_MIDDLEWARES = {
    'scrapy_zyte_smartproxy.ZyteSmartProxyMiddleware': 610
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

AUTOTHROTTLE_ENABLED = True
CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 1.5
