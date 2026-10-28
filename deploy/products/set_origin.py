"""Set the test URL without relying on Bash read or GNU/BSD sed differences."""
import argparse
from pathlib import Path
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=Path('.env.prod'))
    parser.add_argument('--origin')
    args = parser.parse_args()
    origin = (args.origin or input('URL do teste (http://IP_DO_SERVIDOR:8088): ')).strip().rstrip('/')
    parsed = urlsplit(origin)
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment):
        parser.error('Informe somente http(s)://IP-ou-dominio:porta, sem caminho ou credenciais.')
    try:
        parsed.port
    except ValueError:
        parser.error('Porta inválida.')
    if not args.env_file.is_file():
        parser.error(f'Arquivo não encontrado: {args.env_file}')
    lines = args.env_file.read_text(encoding='utf-8').splitlines()
    found = any(line.startswith('PUBLIC_ORIGIN=') for line in lines)
    lines = [f'PUBLIC_ORIGIN={origin}' if line.startswith('PUBLIC_ORIGIN=') else line for line in lines]
    if not found:
        lines.append(f'PUBLIC_ORIGIN={origin}')
    args.env_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'PUBLIC_ORIGIN atualizado em {args.env_file}.')


if __name__ == '__main__':
    main()
