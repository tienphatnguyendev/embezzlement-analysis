"""Prepare the uploaded HI-Small inputs for direct execution in a Colab notebook."""

import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def prepare_colab(repo_root, drive_archive=None):
    root = Path(repo_root).resolve()
    loaded = {module: getattr(sys.modules.get(module), '__version__', None)
              for module in ['numpy', 'pandas', 'sklearn', 'plotly']}
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-e', str(root) + '[eda]'], check=True)
    distributions = {'numpy': 'numpy', 'pandas': 'pandas', 'sklearn': 'scikit-learn', 'plotly': 'plotly'}
    changed = [name for name, old in loaded.items()
               if old is not None and old != importlib.metadata.version(distributions[name])]
    if changed:
        raise RuntimeError('Installed versions changed for ' + ', '.join(changed)
                           + '. Restart the Colab session, then rerun this setup cell.')
    required = ['data/hi-small.sqlite', 'data/raw/full-hi-small/acquisition.json',
                'reports/hi-small-audit.json', 'reports/hi-small-scan.json',
                'reports/hi-small-candidates.jsonl', 'reports/hi-small-run-provenance.json']
    for name in ['HI-Small_Trans.csv', 'HI-Small_accounts.csv', 'HI-Small_Patterns.txt']:
        required += ['data/raw/full-hi-small/' + name, 'data/raw/full-hi-small/' + name + '.source.json']
    marker = root / 'work/colab-inputs-ready.json'
    ready = False
    if marker.is_file():
        try:
            saved = json.loads(marker.read_text())
        except (ValueError, OSError):
            saved = {}
        ready = all((root / name).is_file() and (root / name).stat().st_size == saved.get(name)
                    for name in required)
    if not ready:
        from google.colab import drive
        drive.mount('/content/drive')
        source = Path(drive_archive or '/content/drive/MyDrive/embezzlement-analysis/hi-small-colab-inputs.zip')
        if not source.is_file():
            raise FileNotFoundError('Upload hi-small-colab-inputs.zip to MyDrive/embezzlement-analysis/, '
                                    'or set COLAB_INPUT_ZIP to its mounted Drive path, then rerun this cell.')
        local = Path('/content/hi-small-colab-inputs.zip')
        print('Copying the input ZIP from Drive to Colab local storage…', flush=True)
        shutil.copy2(source, local)
        with zipfile.ZipFile(local) as archive:
            for member in archive.infolist():
                destination = (root / member.filename).resolve()
                if root not in destination.parents and destination != root:
                    raise ValueError('Archive member escapes the repository: ' + member.filename)
                if not (member.filename.startswith(('data/', 'reports/'))
                        or member.filename == 'COLAB_INPUTS_README.txt'):
                    raise ValueError('Input archive contains a non-input path: ' + member.filename)
            missing = set(required) - set(archive.namelist())
            if missing:
                raise ValueError('Input ZIP lacks required files: ' + ', '.join(sorted(missing)))
            archive.extractall(root)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({name: (root / name).stat().st_size for name in required}, indent=2))
    os.chdir(root)
    os.environ['EMBEZZLEMENT_REPO_ROOT'] = str(root)
    print('Ready. Run the analysis cells below in this notebook; variables and charts stay in this Colab session.')
    return root
