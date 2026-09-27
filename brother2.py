#!/usr/bin/env python3
"""Diagnose: fragt beim Brother VC-500W ab, welche Informationen er liefert.

Protokoll (rohes XML über TCP, Port 9100):
  Anfrage:  <?xml ...?>\n<read>\n<path>/status.xml</path>\n</read>
  Antwort:  <?xml ...?>\n<status>...<code>0</code><datasize>N</datasize></status>\n
            \x00 + N Bytes Payload-XML
"""

import argparse
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_PATHS = ["/status.xml", "/config.xml"]


def recv_until(sock, buf, marker):
    """Liest, bis marker im Puffer steht. Gibt (puffer, index_nach_marker) zurück."""
    while (idx := buf.find(marker)) == -1:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Verbindung vom Drucker geschlossen")
        buf += chunk
    return buf, idx + len(marker)


def recv_exact(sock, buf, n):
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Verbindung vom Drucker geschlossen")
        buf += chunk
    return buf


def read_file(sock, path):
    """Sendet <read> für path, gibt (header_bytes, payload_bytes) zurück."""
    req = f'<?xml version="1.0" encoding="UTF-8"?>\n<read>\n<path>{path}</path>\n</read>'
    sock.sendall(req.encode())

    buf, end = recv_until(sock, b"", b"</status>")
    header = buf[:end]
    rest = buf[end:]

    hdr = ET.fromstring(header)
    code = int(hdr.findtext("code", "-1"))
    size = int(hdr.findtext("datasize", "-1"))
    if code != 0 or size <= 0:
        return header, b""

    # Nach </status> folgen "\n\x00", dann exakt `size` Bytes Payload
    rest = recv_exact(sock, rest, 2 + size)
    if rest[:2] != b"\n\x00":
        print(f"  Warnung: unerwarteter Trenner {rest[:2]!r}", file=sys.stderr)
    return header, rest[2:2 + size]


def flatten(elem, prefix=""):
    """XML-Baum -> Liste von (pfad, wert) für alle Blätter."""
    path = f"{prefix}/{elem.tag}"
    children = list(elem)
    if not children:
        return [(path, (elem.text or "").strip())]
    out = []
    for child in children:
        out.extend(flatten(child, path))
    return out


def drain(sock, timeout=1.0):
    """Liest alles, was der Drucker nach dem Verbinden ungefragt schickt."""
    sock.settimeout(timeout)
    data = b""
    try:
        while chunk := sock.recv(4096):
            data += chunk
    except socket.timeout:
        pass
    return data


def main():
    ap = argparse.ArgumentParser(description="VC-500W Info-Abfrage")
    ap.add_argument("host", help="IP/Hostname des Druckers")
    ap.add_argument("-p", "--port", type=int, default=9100)
    ap.add_argument("--path", action="append",
                    help=f"abzufragender Pfad (mehrfach möglich), Standard: {DEFAULT_PATHS}")
    ap.add_argument("--raw", action="store_true", help="Rohantworten zusätzlich ausgeben")
    ap.add_argument("--save", type=Path, help="Rohantworten in dieses Verzeichnis schreiben")
    ap.add_argument("--timeout", type=float, default=5.0)
    args = ap.parse_args()

    paths = args.path or DEFAULT_PATHS
    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)

    with socket.create_connection((args.host, args.port), timeout=args.timeout) as sock:
        print(f"Verbunden mit {args.host}:{args.port}")

        greeting = drain(sock)
        if greeting:
            print(f"\n[Ungefragte Daten nach Verbindungsaufbau, {len(greeting)} Bytes]")
            print(greeting.decode("utf-8", "replace"))
        sock.settimeout(args.timeout)

        for path in paths:
            print(f"\n=== {path} ===")
            try:
                header, payload = read_file(sock, path)
            except Exception as e:
                print(f"  Fehler: {e}")
                continue

            hdr = ET.fromstring(header)
            print(f"  code={hdr.findtext('code')}  datasize={hdr.findtext('datasize')}  "
                  f"comment={hdr.findtext('comment', '')!r}")

            if args.raw:
                print("--- Header ---\n" + header.decode("utf-8", "replace"))
                print("--- Payload ---\n" + payload.decode("utf-8", "replace"))
            if args.save:
                name = path.strip("/").replace("/", "_")
                (args.save / f"{name}.resp.bin").write_bytes(header + b"\n\x00" + payload)

            if payload:
                try:
                    for key, value in flatten(ET.fromstring(payload)):
                        print(f"  {key:<45} {value}")
                except ET.ParseError as e:
                    print(f"  Payload kein gültiges XML: {e}")


if __name__ == "__main__":
    main()
