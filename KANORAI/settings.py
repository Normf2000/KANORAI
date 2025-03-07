# Add this at the top
import sys
sys.path.append('/app/python/lib/python3.11/site-packages')

BOT_NAME = 'kanorai'
SPIDER_MODULES = ['kanorai.spiders']
NEWSPIDER_MODULE = 'kanorai.spiders'

# Zyte configuration
ZYTE_SMARTPROXY_ENABLED = True
ZYTE_SMARTPROXY_URL = 'http://2dbd47209e994341a32756a599730a18'  # Replace API_KEY

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
