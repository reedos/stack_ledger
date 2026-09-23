import copy
import json
import sys
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import pdf_text
import research
from document_formats import CollectionGap

try:
    import pypdf  # noqa: F401
    HAVE_PYPDF=True
except ImportError:
    HAVE_PYPDF=False


def make_pdf(pages):
    """A minimal valid PDF: one Helvetica text line per entry of each page."""
    objects=['<< /Type /Catalog /Pages 2 0 R >>',None,'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    kids=[]
    for lines in pages:
        stream='BT /F1 11 Tf 72 720 Td 14 TL '+' '.join('('+line.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')+") '" for line in lines)+' ET'
        objects.append(f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream')
        content=len(objects)
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content} 0 R /Resources << /Font << /F1 3 0 R >> >> >>')
        kids.append(len(objects))
    objects[1]='<< /Type /Pages /Kids ['+' '.join(f'{k} 0 R' for k in kids)+f'] /Count {len(kids)} >>'
    out=b'%PDF-1.4\n';offsets=[]
    for i,body in enumerate(objects,1):
        offsets.append(len(out));out+=f'{i} 0 obj\n{body}\nendobj\n'.encode('latin-1')
    xref=len(out)
    out+=f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()+b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets)
    out+=f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return out


def readable(body,max_pages=10):
    parser=research.ReadableHTML();parser.feed(pdf_text.pdf_html(body,max_pages));return parser.readable()


POLICY={'version':1,'owner_decision':'Test decision: only the listed documents and paths are read as PDF text.',
        'max_bytes':1_000_000,'max_pages':10,'documents':[{'source':'grid','why':'Test report.'}],
        'prefixes':[{'host':'www.grid.example','path_prefix':'/reports/load-forecast/','why':'Test path.'}]}
REGISTRY={'sources':[{'id':'grid','url':'https://www.grid.example/files/2026-load-report.pdf'}]}


@unittest.skipUnless(HAVE_PYPDF,'pypdf not installed; PDFs stay collection gaps')
class PdfTextTests(unittest.TestCase):
    def test_pages_become_marked_text_a_reviewer_can_locate(self):
        text=readable(make_pdf([['Load Forecast Report'],['Summer peak could rise to 109 GW within ten years.']]))
        self.assertTrue(pdf_text.is_pdf_text(text))
        self.assertIn('[Page 2]',text)
        at=text.find('could rise to 109 GW')
        self.assertGreater(at,0)
        self.assertEqual(pdf_text.page_of(text,at),2)
        self.assertIsNone(pdf_text.page_of(text,-1))

    def test_unreadable_or_oversized_pdfs_stay_collection_gaps(self):
        for body,pages,kind in [(b'<html>not a pdf</html>',10,'not_a_pdf'),(make_pdf([['a'],['b'],['c']]),2,'pdf_too_many_pages'),
                                (b'%PDF-1.4 truncated',10,'pdf_unreadable')]:
            with self.subTest(kind=kind),self.assertRaises(CollectionGap) as caught:pdf_text.pdf_html(body,pages)
            self.assertEqual(caught.exception.kind,kind)
        with patch.dict(sys.modules,{'pypdf':None}),self.assertRaises(CollectionGap) as caught:
            pdf_text.pdf_html(make_pdf([['a']]),10)
        self.assertEqual(caught.exception.kind,'pdf_parser_unavailable')

    def test_fetcher_reads_an_approved_pdf_and_refuses_any_other(self):
        body=make_pdf([['PJM projects a summer peak of 222,106 MW in 2036, an increase of 65,733 MW over 2026.']*4])
        class Response:
            def __init__(self):self.headers=Message();self.headers['Content-Type']='application/pdf';self.sent=None
            def read(self,n):return body[:n]
            def __enter__(self):return self
            def __exit__(self,*a):return False
        class Opener:
            def __init__(self):self.requests=[]
            def open(self,request,timeout):self.requests.append(request);return Response()
        fetcher=research.Fetcher();fetcher._pdf=(POLICY,pdf_text.approved_urls(POLICY,REGISTRY))
        opener=Opener()
        with patch.object(research,'build_opener',return_value=opener),patch.object(research,'allowed_url'),patch.object(research.time,'sleep'):
            html=fetcher.get('https://www.grid.example/files/2026-load-report.pdf','www.grid.example')
            self.assertIn('222,106 MW',html)
            self.assertIn('application/pdf',opener.requests[-1].get_header('Accept'))  # spp.org answers 406 otherwise
            self.assertIn('[Page 1]',fetcher.get('https://www.grid.example/reports/load-forecast/2027.pdf','www.grid.example'))
            for url in ['https://www.grid.example/other/2026.pdf','https://www.grid.example/reports/load-forecast/2027.pdf?x=1']:
                with self.subTest(url=url),self.assertRaises(CollectionGap) as caught:fetcher.get(url,'www.grid.example')
                self.assertEqual(caught.exception.kind,'pdf_requires_reviewed_parser')


class PdfPolicyTests(unittest.TestCase):
    def test_repository_policy_matches_the_registry(self):
        registry=json.loads((ROOT/'research/sources.json').read_text(encoding='utf-8'))
        policy=pdf_text.load_policy(ROOT,registry)
        self.assertTrue(policy['documents'])
        for url in pdf_text.approved_urls(policy,registry):self.assertTrue(url.startswith('https://'))

    def test_policy_rejects_unregistered_sources_and_broad_paths(self):
        bad=copy.deepcopy(POLICY);bad['documents'][0]['source']='unknown'
        with self.assertRaisesRegex(ValueError,'not registered'):pdf_text.check_policy(bad,REGISTRY)
        for prefix in ['/','/a/','/reports/../x/']:
            bad=copy.deepcopy(POLICY);bad['prefixes'][0]['path_prefix']=prefix
            with self.subTest(prefix=prefix),self.assertRaisesRegex(ValueError,'specific path'):pdf_text.check_policy(bad,REGISTRY)
        bad=copy.deepcopy(POLICY);bad['extra']=1
        with self.assertRaises(ValueError):pdf_text.check_policy(bad,REGISTRY)

    def test_allowed_only_for_listed_documents_and_paths(self):
        urls=pdf_text.approved_urls(POLICY,REGISTRY)
        self.assertTrue(pdf_text.allowed('https://www.grid.example/files/2026-load-report.pdf',POLICY,urls))
        self.assertTrue(pdf_text.allowed('https://www.grid.example/reports/load-forecast/2027.pdf',POLICY,urls))
        for url in ['https://www.grid.example/files/other.pdf','https://evil.example/reports/load-forecast/2027.pdf',
                    'http://www.grid.example/reports/load-forecast/2027.pdf','https://www.grid.example/reports/load-forecast/page.html']:
            self.assertFalse(pdf_text.allowed(url,POLICY,urls),url)
        self.assertFalse(pdf_text.allowed('https://www.grid.example/files/2026-load-report.pdf',{},urls))

    def test_table_rows_are_told_apart_from_prose(self):
        for evidence in ['PJM projects summer peak of 222,106 MW in 2036, an increase of 65,733 MW.',
                         'SPP peak demand of 56 GW could rise to 109 GW within ten years.',
                         'data centers could add between 42 and 80 TWh by 2030']:
            self.assertFalse(pdf_text.looks_tabular(evidence),evidence)
        for evidence in ['2024 122 152 186','Summer Peak (MW) 2036 222,106 2046 253,077']:
            self.assertTrue(pdf_text.looks_tabular(evidence),evidence)

    def test_a_pdf_table_figure_is_held_for_review_not_published(self):
        data=json.loads((ROOT/'site/data/ledger.json').read_text(encoding='utf-8'))
        metrics={m['id']:m for m in data['metrics']};sources={s['id']:s for s in data['sources']}
        document='[Page 1]\nAdoption by year\n2024 78 82 85\n[Page 2]\nMore text follows here for the reader.'
        candidate={'metric':'ai-adoption','year':2024,'period':'2024','value':78,'upper':None,'status':'observation',
                   'precision':'eq','note':'','evidence':'2024 78 82 85'}
        quarantine=[]
        with patch.object(research,'ollama',return_value={'observations':[candidate]}),patch.object(research,'METRIC_EVIDENCE_MAX',400):
            research.extract_observations({'_instructions':'i','_coverage':'c','max_candidates_per_document':8},sources['stanford-2026'],
                                          document,[metrics['ai-adoption']],copy.deepcopy(data),metrics,dict(sources),{'model_calls':0},quarantine,{})
        self.assertEqual([q['reason'] for q in quarantine],['PDF table figure held for human review'])


if __name__=='__main__':
    unittest.main()
