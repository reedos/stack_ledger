import sys
import unittest
from pathlib import Path

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
