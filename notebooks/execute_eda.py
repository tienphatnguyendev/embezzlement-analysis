"""Execute the EDA with this Python environment and export a static HTML view."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=int, default=300, help='Timeout per cell in seconds')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')

    runtime = root / 'work/jupyter-runtime'
    for directory in ['runtime', 'ipython', 'matplotlib']:
        (runtime / directory).mkdir(parents=True, exist_ok=True)
    os.environ['JUPYTER_PATH'] = str(runtime / 'share/jupyter') + os.pathsep + os.environ.get('JUPYTER_PATH', '')
    os.environ['JUPYTER_RUNTIME_DIR'] = str(runtime / 'runtime')
    os.environ['IPYTHONDIR'] = str(runtime / 'ipython')
    os.environ['MPLCONFIGDIR'] = str(runtime / 'matplotlib')
    os.environ['EMBEZZLEMENT_REPO_ROOT'] = str(root)
    subprocess.run([sys.executable, '-m', 'ipykernel', 'install', '--prefix', str(runtime),
                    '--name', 'embezzlement-eda', '--display-name', 'Python (Embezzlement EDA)'],
                   check=True, capture_output=True, text=True)

    import nbformat
    from nbclient import NotebookClient
    from nbconvert import HTMLExporter

    source = root / 'notebooks/hi_small_eda.ipynb'
    output_dir = root / 'reports/eda'
    output_dir.mkdir(parents=True, exist_ok=True)
    notebook = nbformat.read(source, as_version=4)
    client = NotebookClient(notebook, timeout=args.timeout, kernel_name='embezzlement-eda',
                            allow_errors=False, resources={'metadata': {'path': str(root)}})
    started = time.monotonic()
    print('Executing EDA notebook against read-only HI-Small database', flush=True)
    try:
        client.execute()
    except Exception:
        nbformat.write(notebook, output_dir / 'hi_small_eda.failed.ipynb')
        raise
    nbformat.validate(notebook)
    errors = [output for cell in notebook.cells for output in cell.get('outputs', [])
              if output.output_type == 'error']
    if errors:
        raise RuntimeError('Notebook contains error outputs')
    executed = output_dir / 'hi_small_eda.executed.ipynb'
    nbformat.write(notebook, executed)
    exporter = HTMLExporter(template_name='classic')
    exporter.exclude_input_prompt = True
    exporter.exclude_output_prompt = True
    html, _ = exporter.from_notebook_node(notebook)
    preview = output_dir / 'hi_small_eda.html'
    preview.write_text(html, encoding='utf-8')
    report = {
        'status': 'passed', 'elapsed_seconds': round(time.monotonic() - started, 3),
        'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'executed_notebook': str(executed), 'html_preview': str(preview),
        'cell_count': len(notebook.cells),
        'executed_code_cells': sum(cell.cell_type == 'code' and cell.execution_count is not None for cell in notebook.cells),
        'error_outputs': len(errors),
        'embedded_figure_outputs': sum('image/png' in output.get('data', {})
                                      for cell in notebook.cells for output in cell.get('outputs', [])),
    }
    (output_dir / 'execution-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
