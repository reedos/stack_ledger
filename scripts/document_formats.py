"""Non-executing text/feed adapters. No browser, macros, OCR or dependencies."""
import html
import json
import re
import xml.etree.ElementTree as ET


class CollectionGap(ValueError):
    def __init__(self, kind):
        self.kind = kind
        super().__init__('Collection gap: '+kind)


def as_html(text, content_type):
    if content_type in {'text/html','application/xhtml+xml'}: return text
    if content_type in {'text/plain','text/csv','text/tab-separated-values'}:
        return '<pre>'+html.escape(text)+'</pre>'
    if content_type == 'application/json':
        json.loads(text)  # Reject malformed bodies; preserve original tokens and structure.
        return '<pre>'+html.escape(text)+'</pre>'
    if content_type in {'application/rss+xml','application/atom+xml','application/xml','text/xml'}:
        if re.search(r'<!\s*(?:DOCTYPE|ENTITY)',text,re.I):
            raise CollectionGap('unsafe_xml_declaration')
        root = ET.fromstring(text)
        local = lambda tag: tag.rsplit('}',1)[-1]
        if local(root.tag) not in {'rss','feed'}: raise CollectionGap('unsupported_xml')
        parts = []
        for entry in root.iter():
            if local(entry.tag) not in {'item','entry'}: continue
            parts.append('<section>')
            for child in entry:
                tag = local(child.tag)
                value = ''.join(child.itertext())
                if tag == 'link':
                    # Links are only pointers; the existing URL policy decides eligibility.
                    target = child.get('href') or value.strip()
                    parts.append('<a href="'+html.escape(target,quote=True)+'">Source entry</a>')
                elif tag in {'title','summary','description','content','pubDate','published','updated'}:
                    # Escaping keeps even embedded markup/instructions inert.
                    parts.append('<p>'+html.escape(tag+': '+value)+'</p>')
            parts.append('</section>')
        return '\n'.join(parts)
    raise CollectionGap('unsupported_content_type')


def format_gap(content_type):
    if content_type == 'application/pdf': return 'pdf_requires_reviewed_parser'
    if content_type in {'application/vnd.ms-excel','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}:
        return 'workbook_requires_reviewed_parser'
    return 'unsupported_content_type'


SUPPORTED = {'text/html','application/xhtml+xml','text/plain','text/csv','text/tab-separated-values',
             'application/json','application/rss+xml','application/atom+xml','application/xml','text/xml'}
