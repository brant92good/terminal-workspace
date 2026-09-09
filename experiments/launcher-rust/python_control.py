"""Same preselected-machine contract as Rust; reuse the installed focus logic."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'apps/port-forward-tui')]
from port_forward_tui.focus_settings import read_scope
from port_forward_tui.views import live_titles, mark_origin, native_focus


def prepare(plan):
    if plan['mode'] == 'ports':
        payload = live_titles(Path(plan['views']).parent)
        flag = '-TitlesBase64'
    elif plan['mode'] == 'records':
        # Importing the full Herdr launcher would also import machine/SSH code.
        # Only its record reader is needed at this preselected-machine seam.
        from port_forward_tui.views import process_alive
        payload = []
        for path in Path(plan['views']).glob('*.json'):
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                if process_alive(record['pid']):
                    payload.append(record)
                else:
                    path.unlink(missing_ok=True)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        flag = '-RecordsBase64'
    else:
        raise ValueError('Invalid mode')
    return {'scope': read_scope(Path(plan['settings'])), 'flag': flag, 'payload': payload}


def main():
    plan = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    prepared = prepare(plan)
    if sys.argv[2:] == ['--prepare']:
        print(json.dumps(prepared))
        return 0
    if not prepared['payload']:
        return 1
    import base64
    payload = base64.b64encode(json.dumps(prepared['payload']).encode()).decode('ascii')
    command = [plan['helper'], prepared['flag'], payload, '-Scope', prepared['scope'],
               '-OriginTitle', mark_origin()]
    if plan.get('trace'):
        command.extend(['-TracePath', plan['trace']])
    return 0 if native_focus(command) else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'Launcher experiment: {error}', file=sys.stderr)
        raise SystemExit(2)
