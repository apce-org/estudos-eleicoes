"""Gera um QR Code para uma URL informada por parâmetro."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera um arquivo PNG com QR Code para uma URL."
    )
    parser.add_argument("url", help="URL que será codificada no QR Code.")
    parser.add_argument(
        "-o",
        "--output",
        default="outputs/qrcode.png",
        help="Caminho do arquivo de saída. Padrão: outputs/qrcode.png",
    )
    parser.add_argument(
        "--box-size",
        type=int,
        default=16,
        help="Tamanho, em pixels, de cada quadrado do QR Code. Padrão: 16",
    )
    parser.add_argument(
        "--border",
        type=int,
        default=4,
        help="Margem, em quadrados, ao redor do QR Code. Padrão: 4",
    )
    parser.add_argument(
        "--fill-color",
        default="#3c3c47",
        help="Cor dos módulos do QR Code. Padrão: #3c3c47",
    )
    parser.add_argument(
        "--back-color",
        default="#fbf7f4",
        help="Cor de fundo do QR Code. Padrão: #fbf7f4",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_H
    except ImportError as exc:
        raise SystemExit(
            "Dependência ausente. Instale com: pip install 'qrcode[pil]'"
        ) from exc

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=args.box_size,
        border=args.border,
    )
    qr.add_data(args.url)
    qr.make(fit=True)

    image = qr.make_image(fill_color=args.fill_color, back_color=args.back_color)
    image.save(output_path)

    print(f"QR Code salvo em: {output_path}")


if __name__ == "__main__":
    main()
