import re


def normalize_slug(slug: str) -> str:
    """Normalize only hyphens, preserving the identity of legacy slugs."""
    return re.sub(r"-+", "-", slug).strip("-")


def normalize_unique_slugs(slugs: list[str]) -> list[str]:
    """Reject ambiguous normalization before replacing any database contents."""
    normalized = [normalize_slug(slug) for slug in slugs]
    seen = set()
    for slug in normalized:
        if not slug or slug in seen:
            raise ValueError(f"Empty or conflicting normalized film slug: {slug!r}")
        seen.add(slug)
    return normalized


def url_safe_str(name: str, *, normalize: bool = True):
    name = re.sub("[^a-z0-9-_]", "", name.lower().replace(" ", "-"))

    return normalize_slug(name) if normalize else name


# Check each url is unique to avoid duplicates in database
class UniqueUrlGenerator:
    """Check each url is unique to avoid duplicates in database"""

    def __init__(self, *, normalize: bool = True):
        self.existing_urls: set[str] = set()
        self.normalize = normalize

    def reset(cls):
        del cls.existing_urls
        cls.existing_urls = set()

    def generate(cls, name):
        counter = 1
        base_url = url_safe_str(name, normalize=cls.normalize)
        unique_url = base_url
        while unique_url in cls.existing_urls:
            unique_url = f"{base_url}-{counter}"
            counter += 1
        cls.existing_urls.add(unique_url)
        return unique_url


unique_url_generator = UniqueUrlGenerator()


def generate_unique_url(name):
    return unique_url_generator.generate(name)
