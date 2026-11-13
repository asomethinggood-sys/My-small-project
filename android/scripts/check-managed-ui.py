"""Fail release UI audits if consumer surfaces expose configuration details."""
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
text = ' '.join(node.get('text', '') + ' ' + node.get('content-desc', '') for node in root.iter('node')).lower()
assert 'continuum' in text and 'connect' in text, 'Consumer home did not render'
for bad in ('github', 'asomethinggood', 'repository', 'subscription', 'import profile', 'custom config', 'xray', 'vless', 'websocket', 'http://', 'https://', 'exit locations'):
    assert bad not in text, 'Forbidden consumer UI content: ' + bad
assert not any('EditText' in node.get('class', '') for node in root.iter('node'))
print('Consumer release UI allowlist passed')
