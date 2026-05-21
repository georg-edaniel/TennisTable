"""
============================================================
 AQIMS — Générateur de certificats TLS (CA + Serveur + Client)
 Utilise la bibliothèque cryptography (pip install cryptography)
 Compatible Windows / macOS / Linux
============================================================
"""

import os
import datetime
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

CERTS_DIR = Path(__file__).parent.parent / "certs"
VALIDITY_DAYS = 3650  # 10 ans


def generate_private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend(),
    )


def save_private_key(key, path: Path, password: bytes = None):
    encryption = (
        serialization.BestAvailableEncryption(password)
        if password
        else serialization.NoEncryption()
    )
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption,
        )
    )
    print(f"  ✅ Clé privée sauvegardée : {path.name}")


def save_certificate(cert, path: Path):
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"  ✅ Certificat sauvegardé   : {path.name}")


def build_subject(cn: str, org: str = "AQIMS") -> x509.Name:
    return x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CA"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Quebec"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Montreal"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
    ])


def create_ca_cert(ca_key) -> x509.Certificate:
    """Crée le certificat de l'autorité de certification (CA)."""
    subject = issuer = build_subject("AQIMS Root CA", "AQIMS CA")
    now = datetime.datetime.utcnow()

    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                key_cert_sign=True, crl_sign=True,
                digital_signature=False, key_encipherment=False,
                content_commitment=False, key_agreement=False,
                data_encipherment=False, encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256(), default_backend())
    )


def create_server_cert(ca_cert, ca_key, server_key, hostname: str = "emqx") -> x509.Certificate:
    """Crée le certificat du serveur EMQX."""
    now = datetime.datetime.utcnow()
    subject = build_subject(hostname)

    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("emqx"),
                x509.DNSName("localhost"),
                x509.DNSName("aqims.local"),
            ]),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_encipherment=True,
                key_cert_sign=False, crl_sign=False,
                content_commitment=False, key_agreement=False,
                data_encipherment=False, encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256(), default_backend())
    )


def create_client_cert(ca_cert, ca_key, client_key, client_name: str = "backend_client") -> x509.Certificate:
    """Crée le certificat client (backend ou ESP32)."""
    now = datetime.datetime.utcnow()
    subject = build_subject(client_name)

    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(client_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_encipherment=True,
                key_cert_sign=False, crl_sign=False,
                content_commitment=False, key_agreement=False,
                data_encipherment=False, encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256(), default_backend())
    )


def main():
    CERTS_DIR.mkdir(exist_ok=True)
    print("\n🔐 Génération des certificats TLS pour AQIMS\n")

    # 1. Autorité de Certification (CA)
    print("📋 Étape 1/4 — Autorité de Certification (CA)")
    ca_key = generate_private_key()
    ca_cert = create_ca_cert(ca_key)
    save_private_key(ca_key, CERTS_DIR / "ca.key")
    save_certificate(ca_cert, CERTS_DIR / "ca.crt")

    # 2. Certificat Serveur (EMQX + Nginx)
    print("\n📋 Étape 2/4 — Certificat Serveur (EMQX / Nginx)")
    server_key = generate_private_key()
    server_cert = create_server_cert(ca_cert, ca_key, server_key)
    save_private_key(server_key, CERTS_DIR / "server.key")
    save_certificate(server_cert, CERTS_DIR / "server.crt")

    # 3. Certificat Client — Backend FastAPI
    print("\n📋 Étape 3/4 — Certificat Client (Backend FastAPI)")
    client_key = generate_private_key()
    client_cert = create_client_cert(ca_cert, ca_key, client_key, "backend_client")
    save_private_key(client_key, CERTS_DIR / "client.key")
    save_certificate(client_cert, CERTS_DIR / "client.crt")

    # 4. Certificat Client — ESP32
    print("\n📋 Étape 4/4 — Certificat Client (ESP32)")
    esp32_key = generate_private_key()
    esp32_cert = create_client_cert(ca_cert, ca_key, esp32_key, "esp32_device")
    save_private_key(esp32_key, CERTS_DIR / "esp32.key")
    save_certificate(esp32_cert, CERTS_DIR / "esp32.crt")

    # Générer le fichier .h pour l'ESP32 (certificats embarqués dans le firmware)
    generate_esp32_certs_header(ca_cert, esp32_cert, esp32_key)

    print("\n✅ Tous les certificats ont été générés dans /certs/")
    print("⚠️  Ne jamais committer les fichiers .key dans git !\n")


def generate_esp32_certs_header(ca_cert, esp32_cert, esp32_key):
    """Génère un fichier .h Arduino avec les certificats intégrés."""
    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode()
    cert_pem = esp32_cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = esp32_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()

    def to_c_string(pem: str) -> str:
        lines = pem.strip().split("\n")
        return "\n".join(f'  "{line}\\n"' for line in lines)

    header_content = f"""// ============================================================
//  AQIMS — Certificats TLS pour ESP32
//  Généré automatiquement par generate_certs.py
//  NE PAS COMMITTER CE FICHIER DANS GIT
// ============================================================
#pragma once

// Certificat de l'Autorité de Certification (CA)
const char* CA_CERT = \\
{to_c_string(ca_pem)};

// Certificat client ESP32
const char* CLIENT_CERT = \\
{to_c_string(cert_pem)};

// Clé privée client ESP32
const char* CLIENT_KEY = \\
{to_c_string(key_pem)};
"""

    header_path = Path(__file__).parent.parent / "firmware" / "aqims_sensor" / "certs.h"
    header_path.write_text(header_content)
    print(f"\n  ✅ Header Arduino généré   : firmware/aqims_sensor/certs.h")


if __name__ == "__main__":
    main()
