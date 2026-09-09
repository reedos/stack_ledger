import copy
import json
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate import validate, event_valid, validate_event_corrections, current_events
from source_policy import validate_excerpts
from research import validate_monitoring_delta


class NoteCorrectionTests(unittest.TestCase):
    def setUp(self):
        read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
        self.data=read('site/data/ledger.json')
        self.excerpts=read('site/data/excerpts.json')
        self.registry=read('research/sources.json')
        self.sources={s['id']:s for s in self.data['sources']}
        self.corrections=[e for e in self.data['events'] if e.get('correction_of')]

    def test_replacements_keep_originals_but_do_not_duplicate_current_notes(self):
        self.assertEqual(len(self.corrections),4)
        self.assertTrue(validate(self.data))
        visible={e['id'] for e in current_events(self.data['events'])}
        for e in self.corrections:
            self.assertIn(e['id'],visible);self.assertNotIn(e['correction_of'],visible)
            old=next(o for o in self.data['events'] if o['id']==e['correction_of'])
            self.assertEqual(old['method'],'automated')
            self.assertNotIn('superseded_by',old)
            for k in ['document_sha256','evidence_sha256','retrieved_at','date']:
                self.assertEqual(old[k],e[k])

    def test_bad_ancestry_forks_and_cycles_are_rejected(self):
        old=dict(self.corrections[0],id='old',correction_of='new')
        new=dict(old,id='new',correction_of='old')
        for rows in [[new],[old,new],self.data['events']+[dict(self.corrections[0],id='fork')]]:
            with self.assertRaises(ValueError):validate_event_corrections(rows)
        rows=copy.deepcopy(self.data['events']);rows[-1]['source']='lumentum-cpo'
        with self.assertRaises(ValueError):validate_event_corrections(rows)

    def test_automated_and_incomplete_corrections_rejected(self):
        for changes in [{'method':'automated'},{'corrected_at':'2099-01-01T00:00:00Z'},{'evidence_sha256':'bad'}]:
            with self.assertRaises(ValueError):event_valid(dict(self.corrections[0],**changes),self.sources)
        e=copy.deepcopy(self.corrections[0]);del e['correction_reason']
        with self.assertRaises(ValueError):event_valid(e,self.sources)

    def test_monitoring_cannot_publish_corrections_or_rewrite_existing_records(self):
        before=copy.deepcopy(self.data);before['events']=[e for e in before['events'] if not e.get('correction_of')]
        with self.assertRaisesRegex(ValueError,'curated'):
            validate_monitoring_delta(before,self.data,self.excerpts,self.excerpts)
        after=copy.deepcopy(self.data);after['events'][0]['summary']='Altered existing statement.'
        with self.assertRaisesRegex(ValueError,'rewrote'):
            validate_monitoring_delta(self.data,after,self.excerpts,self.excerpts)
        altered=copy.deepcopy(self.excerpts);altered['excerpts'][0]['notes']='Changed history.'
        with self.assertRaisesRegex(ValueError,'rewrote'):
            validate_monitoring_delta(self.data,self.data,self.excerpts,altered)
        validate_monitoring_delta(self.data,self.data,self.excerpts,self.excerpts)
        # Ordinary new monitoring remains allowed after the curated baseline lands.
        after=copy.deepcopy(self.data)
        after['events'].append(dict(next(e for e in after['events'] if e.get('method')=='automated'),id='note-'+'0'*20))
        validate_monitoring_delta(self.data,after,self.excerpts,self.excerpts)

    def test_excerpt_changes_retain_previous_values_and_valid_identity(self):
        validate_excerpts(self.excerpts,self.data,self.registry)
        by_source={e['source_id']:e for e in self.excerpts['excerpts']}
        for source,status in [('lumentum-cpo','observation'),('isomorphic-may2026','observation'),('nebius-msft-contract','company-commitment')]:
            e=by_source[source];self.assertEqual(e['status'],status)
            self.assertNotEqual(e['correction_history'][0]['previous']['status'],status)
        self.assertEqual(by_source['meta-awa-graduates']['company_id'],'meta')
        bad=copy.deepcopy(self.excerpts);bad['excerpts'][1]['correction_history'][0]['previous']['quote']='Extra quotation'
        with self.assertRaises(ValueError):validate_excerpts(bad,self.data,self.registry)

    def test_feed_uses_replacement_and_preserves_source_date(self):
        ns={'a':'http://www.w3.org/2005/Atom'}
        root=ET.parse(ROOT/'docs/feed.xml').getroot()
        entries={e.findtext('a:id',namespaces=ns).rsplit('#',1)[-1]:e for e in root.findall('a:entry',ns)}
        for record in self.corrections:
            self.assertNotIn(record['correction_of'],entries)
            e=entries[record['id']]
            self.assertEqual(e.findtext('a:updated',namespaces=ns),record['corrected_at'])
            self.assertIn('Correction:',e.findtext('a:summary',namespaces=ns))
            self.assertEqual(e.find('a:link[@rel="related"]',ns).get('href').split('#')[-1],record['correction_of'])
            if record['date']:self.assertEqual(e.findtext('a:published',namespaces=ns),record['date']+'T12:00:00Z')
            else:self.assertIsNone(e.find('a:published',ns))


if __name__=='__main__':unittest.main()
