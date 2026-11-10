"""VPN Jantit public OpenVPN discovery; claims are not working exits.

Account creation and verification are deliberately not automated. Private user
credentials must be supplied through a separate private provisioning mechanism.
"""
import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

from scripts.egress_catalog import MAX_BYTES, NoRedirect

URL = 'https://www.vpnjantit.com/free-openvpn-7-days'
COUNTRIES = {
    'united states': 'US', 'usa': 'US', 'canada': 'CA', 'mexico': 'MX',
    'brazil': 'BR', 'argentina': 'AR', 'united kingdom': 'GB', 'uk': 'GB',
    'ireland': 'IE', 'france': 'FR', 'germany': 'DE', 'netherlands': 'NL',
    'belgium': 'BE', 'switzerland': 'CH', 'austria': 'AT', 'italy': 'IT',
    'spain': 'ES', 'portugal': 'PT', 'sweden': 'SE', 'norway': 'NO',
    'denmark': 'DK', 'finland': 'FI', 'poland': 'PL', 'czech republic': 'CZ',
    'czechia': 'CZ', 'romania': 'RO', 'turkey': 'TR', 'türkiye': 'TR',
    'japan': 'JP', 'south korea': 'KR', 'korea': 'KR', 'singapore': 'SG',
    'india': 'IN', 'australia': 'AU', 'new zealand': 'NZ',
}


def official_slug(href, path):
    try:
        url = urlsplit(urljoin(URL, href))
        if (url.scheme != 'https' or url.hostname != 'www.vpnjantit.com'
                or url.username or url.password or url.port not in (None, 443)
                or url.path != path or url.fragment):
            return None
        query = parse_qs(url.query, keep_blank_values=True)
        if path == '/download-openvpn.php':
            if set(query) != {'server'}: return None
        elif path == '/create-free-account':
            if set(query) != {'server', 'type'} or query['type'] != ['OpenVPN']: return None
        else:
            return None
        slug = query.get('server', [])
        return slug[0].lower() if len(slug) == 1 and re.fullmatch('[a-z0-9]{1,32}', slug[0].lower()) else None
    except (ValueError, TypeError):
        return None


class Cards(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.in_heading = False
        self.heading = []
        self.current = None
        self.cards = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
            return
        if self.hidden:
            return
        if tag in ('h1', 'h2', 'h3'):
            self.in_heading = True
            self.heading = []
        if tag == 'a' and self.current is not None:
            href = dict(attrs).get('href', '')
            download = official_slug(href, '/download-openvpn.php')
            account = official_slug(href, '/create-free-account')
            if download: self.current['downloads'].add(download)
            if account: self.current['accounts'].add(account)

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if tag in ('h1', 'h2', 'h3') and self.in_heading:
            title = ' '.join(' '.join(self.heading).split())
            match = re.fullmatch(r'FREE\s+OpenVPN\s+(.+?)\s+([0-9]+)', title, re.I)
            self.in_heading = False
            if match:
                self.current = {'country': COUNTRIES.get(match[1].lower()), 'body': [],
                                'downloads': set(), 'accounts': set()}
                self.cards.append(self.current)
            else:
                self.current = None

    def handle_data(self, data):
        if self.hidden: return
        if self.in_heading: self.heading.append(data)
        elif self.current is not None: self.current['body'].append(data)


def parse_directory(text, targets):
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Directory exceeds size budget')
    parser = Cards()
    parser.feed(text)
    if not parser.cards:
        raise ValueError('Provider page did not contain recognizable server cards')
    results = {}
    for card in parser.cards:
        country = card['country']
        if country not in targets: continue
        body = ' '.join(' '.join(card['body']).split()).lower()
        hosts = set(re.findall(r'\b([a-z0-9]{1,32})\.vpnjantit\.com\b', body))
        slugs = card['downloads'] & card['accounts'] & hosts
        if len(slugs) != 1: continue
        slug = next(iter(slugs))
        if slug in results and results[slug]['country'] != country:
            raise ValueError('Conflicting country labels for one server')
        results[slug] = {'id': hashlib.sha256(('vpnjantit:' + slug).encode()).hexdigest()[:24],
                         'provider': 'vpnjantit', 'country': country,
                         'protocol': 'openvpn', 'status': 'discovered_unverified',
                         'advertised_tcp_udp': bool(re.search(r'\btcp\s*/\s*udp\b', body, re.I)),
                         'provider_reports_available': bool(re.search(r'\bavailable\b', body, re.I))}
    return sorted(results.values(), key=lambda item: (item['country'], item['id']))


def fetch_directory():
    import urllib.request
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(URL, headers={'User-Agent': 'Nyx-Repository-Research/1.0'})
    with opener.open(request, timeout=20) as response:
        if response.status != 200: raise ValueError('Directory HTTP failure')
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES: raise ValueError('Directory exceeds size budget')
    return data.decode('utf-8', errors='strict')
