import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from urllib.request import Request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import api_access as aa


class ApiAccessTests(unittest.TestCase):
    def test_policy_is_reviewed_importer_only_and_out_of_prompts(self):
        p=aa.policy(ROOT)
        self.assertTrue(p['importers_only'] and p['never_in_prompts'])
        self.assertIn('api.bls.gov',p['hosts']);self.assertIn('api.census.gov',p['hosts']);self.assertIn('data.bls.gov',p['hosts'])

    def test_only_listed_hosts_and_paths_qualify(self):
        p=aa.policy(ROOT)
        self.assertIsNotNone(aa.allowed('https://data.bls.gov/cew/data/api/2026/1/industry/518210.csv',p))
        self.assertIsNotNone(aa.allowed('https://api.bls.gov/publicAPI/v2/timeseries/data/',p))
        self.assertIsNone(aa.allowed('https://data.bls.gov/cew/downloads/other.zip',p))       # not a documented API path
        self.assertIsNone(aa.allowed('https://www.bls.gov/oes/tables.htm',p))                  # web host: robots rule applies
        self.assertIsNone(aa.allowed('http://data.bls.gov/cew/data/api/x.csv',p))              # plain http never
        self.assertIsNone(aa.allowed('https://user:pw@data.bls.gov/cew/data/api/x.csv',p))

    def test_missing_key_is_none_and_keys_never_read_from_repo(self):
        self.assertIsNone(aa.key('bls',root=ROOT/'nonexistent'))
        self.assertIsNone(aa.key(None))
        self.assertFalse((ROOT/'api-keys.json').exists());self.assertFalse((ROOT/'research/api-keys.json').exists())


if __name__=='__main__':unittest.main()


class HostAgentTests(unittest.TestCase):
    def test_sec_hosts_declare_their_own_agent_and_fetch_uses_it(self):
        import api_access as aa
        from unittest.mock import patch, MagicMock
        p=aa.policy()
        self.assertTrue(p['hosts']['data.sec.gov']['user_agent'].startswith('Stack Ledger research'))
        response=MagicMock();response.read.return_value=b'{}';response.__enter__.return_value=response
        opener=MagicMock();opener.open.return_value=response
        with patch.object(aa,'build_opener',return_value=opener):
            aa.fetch('https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json','StackLedgerBot/1.0 (+x; y)',p)
        request=opener.open.call_args.args[0]
        self.assertEqual(request.get_header('User-agent'),p['hosts']['data.sec.gov']['user_agent'])


# Shaped like a registered EIA key (40 alphanumerics) but not one; no test ever holds a real key.
FAKE='fakeEIAkeyFAKEfakeFAKE0000000000000000ab'


class SecretHygieneTests(unittest.TestCase):
    """The owner's standing rule: a registered key lives in .local/api-keys.json and reaches
    nothing else -- no retained snapshot, no receipt, no log line, no other host."""

    def setUp(self):
        aa._last.clear()                      # the per-host 1s spacing would otherwise sleep between these
        self.policy=aa.policy(ROOT)
        self.dir=tempfile.TemporaryDirectory();self.addCleanup(self.dir.cleanup)
        self.root=Path(self.dir.name);(self.root/'.local').mkdir()
        (self.root/'.local/api-keys.json').write_text(json.dumps({'eia':FAKE}),encoding='utf-8')

    def _fetch(self,url,body):
        response=MagicMock();response.read.return_value=body;response.__enter__.return_value=response
        opener=MagicMock();opener.open.return_value=response
        with patch.object(aa,'build_opener',return_value=opener) as built:
            got=aa.fetch(url,'StackLedgerBot/1.0 (+x; y)',self.policy,root=self.root)
        return got,opener.open.call_args.args[0],built.call_args.args

    def test_a_retained_response_body_cannot_hold_the_key(self):
        """EIA v2 echoes the request URL back in response.request.params and the importers write
        that body to .local/eia/*.json verbatim, which is how 159 files came to hold the live key."""
        echoed=json.dumps({'request':{'params':{'api_key':FAKE}},'response':{'data':[{'period':'2026-01'}]}}).encode('utf-8')
        got,request,_=self._fetch('https://api.eia.gov/v2/steo/data/?frequency=annual',echoed)
        self.assertIn(f'api_key={FAKE}',request.full_url)                            # the key does go out on the wire
        snapshot=self.root/'.local/eia-steo-0000.json';snapshot.write_bytes(got)     # exactly what import_eia.pull does
        self.assertNotIn(FAKE,snapshot.read_text(encoding='utf-8'))
        self.assertEqual(json.loads(got)['response']['data'],[{'period':'2026-01'}])

    def test_every_registered_key_is_redacted_not_only_the_one_used(self):
        (self.root/'.local/api-keys.json').write_text(json.dumps({'eia':FAKE,'census':FAKE[::-1]}),encoding='utf-8')
        got,_,_=self._fetch('https://api.eia.gov/v2/steo/data/',f'{{"a":"{FAKE}","b":"{FAKE[::-1]}"}}'.encode('utf-8'))
        self.assertEqual(json.loads(got),{'a':'[redacted]','b':'[redacted]'})

    def test_fetch_guards_its_own_redirects(self):
        _,_,handlers=self._fetch('https://api.eia.gov/v2/steo/data/',b'{}')
        self.assertTrue(any(isinstance(h,aa._Redirect) for h in handlers),'fetch built an opener that follows redirects unguarded')

    def test_a_redirect_off_the_listed_api_surface_is_refused(self):
        hop=aa._Redirect(self.policy,'api_key')
        here=Request(f'https://api.eia.gov/v2/steo/data/?api_key={FAKE}')
        for target in [f'https://api.eia.gov.evil.example/v2/steo/data/?api_key={FAKE}',
                       f'https://evil.example/v2/steo/data/?api_key={FAKE}',
                       'https://api.eia.gov/notv2/steo/?x=1']:
            with self.assertRaises(ValueError):hop.redirect_request(here,None,302,'Found',{},target)

    def test_a_redirect_to_another_listed_host_drops_the_key(self):
        hop=aa._Redirect(self.policy,'api_key')
        here=Request(f'https://api.eia.gov/v2/steo/data/?api_key={FAKE}')
        moved=hop.redirect_request(here,None,302,'Found',{},f'https://api.census.gov/data/x?api_key={FAKE}&get=Emp')
        self.assertNotIn(FAKE,moved.full_url);self.assertIn('get=Emp',moved.full_url)

    def test_a_redirect_within_the_same_host_still_follows(self):
        hop=aa._Redirect(self.policy,'api_key')
        here=Request(f'https://api.eia.gov/v2/steo/data/?api_key={FAKE}')
        moved=hop.redirect_request(here,None,302,'Found',{},f'https://api.eia.gov/v2/steo/data/page2/?api_key={FAKE}')
        self.assertIn(FAKE,moved.full_url)

    def test_key_injection_keeps_repeated_facet_parameters(self):
        """EIA takes facets[x][] more than once; dict(parse_qsl(...)) kept only the last one."""
        _,request,_=self._fetch('https://api.eia.gov/v2/electricity/retail-sales/data/'
                                 '?facets%5Bstateid%5D%5B%5D=TX&facets%5Bstateid%5D%5B%5D=VA',b'{}')
        self.assertEqual(request.full_url.count('stateid'),2)

    def test_no_key_reaches_a_receipt_through_a_failed_call(self):
        """Importers record a failed call as type(e).__name__; neither that nor the exception text
        may carry the keyed URL into the receipt."""
        opener=MagicMock();opener.open.side_effect=HTTPError(f'https://api.eia.gov/v2/steo/data/?api_key={FAKE}',403,'Forbidden',{},None)
        with patch.object(aa,'build_opener',return_value=opener):
            with self.assertRaises(HTTPError) as caught:
                aa.fetch('https://api.eia.gov/v2/steo/data/','UA',self.policy,root=self.root)
        self.assertNotIn(FAKE,f'{type(caught.exception).__name__}: {caught.exception}')
