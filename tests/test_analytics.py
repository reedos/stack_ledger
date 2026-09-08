import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build import analytics_tag


class AnalyticsTests(unittest.TestCase):
    def test_unconfigured_site_does_not_send_to_an_assumed_account(self):
        self.assertEqual(analytics_tag({'goatcounter_site':None},'./'),'')

    def test_nested_pages_use_correct_asset_path_and_endpoint(self):
        tag=analytics_tag({'goatcounter_site':'example-site'},'../../')
        self.assertIn('src="../../assets/analytics.js"',tag)
        self.assertIn('https://example-site.goatcounter.com/count',tag)

    def test_configuration_cannot_inject_markup_or_credentials(self):
        for code in ['', 'https://example.goatcounter.com', 'name:password', 'x" onload="alert(1)', '../x', True]:
            with self.subTest(code=code),self.assertRaises(ValueError):
                analytics_tag({'goatcounter_site':code},'./')
        with self.assertRaises(ValueError):analytics_tag({'goatcounter_site':'example','api_key':'secret'},'./')
