from setuptools import setup, find_packages

setup(
    name='kanorai',
    version='2.0',
    packages=find_packages(),
    install_requires=[
        'Scrapy>=2.11',
        'pydantic>=2.6',
        'scrapy-zyte-smartproxy>=1.2',
    ],
    entry_points={'scrapy': ['settings = kanorai.settings']},
    python_requires='>=3.7',
)
