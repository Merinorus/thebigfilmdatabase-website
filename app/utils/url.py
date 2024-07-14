import re


def url_safe_str(name: str):
    name = re.sub("[^a-z0-9-_]", "", name.lower().replace(" ", "-"))

    name = name.lower().replace(" ", "_")
    # result = ''.join(c for c in name if c.isalnum() or c == '_')
    return name


# Check each url is unique to avoid duplicates in database
class UniqueUrlGenerator:
    """Check each url is unique to avoid duplicates in database"""

    existing_urls: set[str] = set()

    def reset(cls):
        del cls.existing_urls
        cls.existing_urls = set()

    def generate(cls, name):
        counter = 1
        base_url = url_safe_str(name)
        unique_url = base_url
        while unique_url in cls.existing_urls:
            unique_url = f"{base_url}-{counter}"
            counter += 1
        cls.existing_urls.add(unique_url)
        return unique_url


unique_url_generator = UniqueUrlGenerator()


def generate_unique_url(name):
    return unique_url_generator.generate(name)
