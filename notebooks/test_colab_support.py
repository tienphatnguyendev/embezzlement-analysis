"""Optional EDA checks: run with the repository's .venv Python."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

from colab_setup import prepare_colab

REQUIRED = [
    'data/hi-small.sqlite', 'data/raw/full-hi-small/acquisition.json',
    'reports/hi-small-audit.json', 'reports/hi-small-scan.json',
    'reports/hi-small-candidates.jsonl', 'reports/hi-small-run-provenance.json',
    *['data/raw/full-hi-small/' + name + suffix
      for name in ['HI-Small_Trans.csv', 'HI-Small_accounts.csv', 'HI-Small_Patterns.txt']
      for suffix in ['', '.source.json']],
]


class ColabInputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = (Path(self.directory.name) / 'repo').resolve()
        self.root.mkdir()
        self.cwd = Path.cwd()
        self.environment = patch.dict(os.environ)
        self.environment.start()

    def tearDown(self):
        os.chdir(self.cwd)
        self.environment.stop()
        self.directory.cleanup()

    def archive(self, extra=None):
        source = self.root.parent / 'inputs.zip'
        with zipfile.ZipFile(source, 'w') as archive:
            for name in REQUIRED:
                archive.writestr(name, 'fixture')
            archive.writestr('COLAB_INPUTS_README.txt', 'Inputs only')
            if extra:
                archive.writestr(extra, 'must not extract')
        return source

    def run_setup(self, source):
        colab = types.ModuleType('google.colab')
        colab.drive = types.SimpleNamespace(mount=lambda path: None)
        original = zipfile.ZipFile
        with patch.dict(sys.modules, {'google.colab': colab}), \
             patch('colab_setup.subprocess.run') as install, \
             patch('colab_setup.shutil.copy2') as copy, \
             patch('colab_setup.zipfile.ZipFile', side_effect=lambda path: original(source)):
            prepare_colab(self.root, source)
        return install, copy

    def test_extract_then_reuse_without_drive_copy(self):
        source = self.archive()
        _, copy = self.run_setup(source)
        copy.assert_called_once()
        self.assertTrue(all((self.root / name).is_file() for name in REQUIRED))
        self.assertEqual(Path.cwd(), self.root)
        self.assertEqual(os.environ['EMBEZZLEMENT_REPO_ROOT'], str(self.root))
        _, copy = self.run_setup(source)
        copy.assert_not_called()

    def test_invalid_cache_recovers_by_extracting(self):
        marker = self.root / 'work/colab-inputs-ready.json'
        marker.parent.mkdir()
        marker.write_text('{broken')
        _, copy = self.run_setup(self.archive())
        copy.assert_called_once()
        self.assertEqual(len(json.loads(marker.read_text())), len(REQUIRED))

    def test_rejects_traversal_and_code_overwrite(self):
        for name in ['../outside.txt', 'notebooks/colab_setup.py']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.run_setup(self.archive(name))
            self.assertFalse((self.root.parent / 'outside.txt').exists())
            self.assertFalse((self.root / 'notebooks/colab_setup.py').exists())

    def test_missing_input_is_rejected_before_extraction(self):
        source = self.root.parent / 'incomplete.zip'
        with zipfile.ZipFile(source, 'w') as archive:
            archive.writestr('data/hi-small.sqlite', 'fixture')
        with self.assertRaisesRegex(ValueError, 'lacks required files'):
            self.run_setup(source)
        self.assertFalse((self.root / 'data/hi-small.sqlite').exists())

    def test_loaded_package_version_change_requests_restart(self):
        loaded = types.SimpleNamespace(__version__='old')
        with patch.dict(sys.modules, {'numpy': loaded}), \
             patch('colab_setup.subprocess.run'), \
             patch('colab_setup.importlib.metadata.version', return_value='new'), \
             self.assertRaisesRegex(RuntimeError, 'Restart the Colab session'):
            prepare_colab(self.root)


@unittest.skipUnless(importlib.util.find_spec('plotly') and importlib.util.find_spec('pandas'),
                     'Install .[eda] for rendering tests')
class ColabRenderingTests(unittest.TestCase):
    def test_each_isolated_colab_chart_contains_its_dependencies(self):
        import eda_design as design
        import plotly.graph_objects as go
        import IPython.display
        import pandas as pd
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {'COLAB_RELEASE_TAG': 'test'}), \
             patch.object(IPython.display, 'display') as display:
            os.environ.pop('EMBEZZLEMENT_NOTEBOOK_EXPORT', None)
            design.install_notebook_style()
            for name in ['first', 'second']:
                design.finish_figure(go.Figure(go.Bar(x=['A'], y=[2])), name,
                                     'Fixture', note='Fixture note', output_dir=directory)
                payload = display.call_args.args[0]
                self.assertEqual(set(payload), {'text/html'})
                markup = payload['text/html']
                for token in ['cdn.plot.ly/plotly-', '@font-face', 'Fixture note', design.SOURCE]:
                    self.assertIn(token, markup)
                self.assertIn('eda-' + name, markup)
            design.show_table(pd.DataFrame({'count': [1]}))
            self.assertIn('@font-face', display.call_args.args[0].data)

    def test_batch_export_overrides_colab_and_embeds_bundle_once(self):
        import eda_design as design
        import plotly.graph_objects as go
        import IPython.display
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {'COLAB_RELEASE_TAG': 'test', 'EMBEZZLEMENT_NOTEBOOK_EXPORT': '1'}), \
             patch.object(IPython.display, 'display') as display:
            design.install_notebook_style()
            fragments = []
            for name in ['first', 'second']:
                design.finish_figure(go.Figure(go.Bar(x=['A'], y=[2])), name,
                                     'Fixture', output_dir=directory)
                payload = display.call_args_list[-2].args[0]
                self.assertIn('application/vnd.plotly.v1+json', payload)
                fragments.append(payload['text/html'])
            self.assertIn('plotly.js v', fragments[0])
            self.assertNotIn('plotly.js v', fragments[1])
            design.install_notebook_style()
            self.assertFalse(design._bundle_shown)


if __name__ == '__main__':
    unittest.main()
