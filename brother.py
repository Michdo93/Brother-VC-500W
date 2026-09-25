import socket
import xml.etree.ElementTree as ET

PRINTER_IP = "192.168.0.48"  # Passe die IP deines VC-500W an
PORT = 51000

# XML-Statusanfrage (Brother VC-500W Format)
STATUS_REQUEST = (
    '<?xml version="1.0" encoding="utf-8"?>\r\n'
    '<pt:get_status xmlns:pt="http://schemas.brother.com/pt/2016/01/01"/>\r\n'
)

def get_printer_status():
    try:
        # 1. TCP-Socket erstellen und verbinden
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((PRINTER_IP, PORT))
        
        # 2. Anfrage senden
        sock.sendall(STATUS_REQUEST.encode('utf-8'))
        
        # 3. Antwort empfangen
        response = sock.recv(4096).decode('utf-8', errors='ignore')
        sock.close()
        
        print("--- Empfangene XML-Rohdaten ---")
        print(response)
        print("-------------------------------")

        # 4. XML parsen (Beispielhafte Extraktion)
        if response.startswith("<?xml"):
            root = ET.fromstring(response)
            
            # Brother nutzt XML-Namespaces
            ns = {'pt': 'http://schemas.brother.com/pt/2016/01/01'}
            
            status_code = root.find('.//pt:status_code', ns)
            tape_width = root.find('.//pt:tape_width', ns)
            media_type = root.find('.//pt:media_type', ns)
            
            print("\n--- Ausgewertete Daten ---")
            if status_code is not None:
                print(f"Status Code: {status_code.text}")
            if tape_width is not None:
                print(f"Bandbreite: {tape_width.text} mm")
            if media_type is not None:
                print(f"Medientyp: {media_type.text}")

    except Exception as e:
        print(f"Fehler bei der Statusabfrage: {e}")

if __name__ == "__main__":
    get_printer_status()
