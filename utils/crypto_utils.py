from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import os

def generate_data_encryption_key() -> bytes:
    return os.urandom(32)

def encrypt_data(data: bytes, key: bytes) -> bytes:
    backend = default_backend()
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
    encryptor = cipher.encryptor()
    
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    return iv + encrypted_data

def decrypt_data(encrypted_data: bytes, key: bytes) -> bytes:
    backend = default_backend()
    iv, encrypted_data = encrypted_data[:16], encrypted_data[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
    decryptor = cipher.decryptor()
    
    data = decryptor.update(encrypted_data) + decryptor.finalize()
    
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(data) + unpadder.finalize()

def encrypt_key(key: bytes, master_key: bytes) -> bytes:
    backend = default_backend()
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(master_key), modes.CBC(iv), backend=backend)
    encryptor = cipher.encryptor()
    encrypted_key = encryptor.update(key) + encryptor.finalize()
    return iv + encrypted_key

def decrypt_key(encrypted_key: bytes, master_key: bytes) -> bytes:
    backend = default_backend()
    iv, encrypted_key = encrypted_key[:16], encrypted_key[16:]
    cipher = Cipher(algorithms.AES(master_key), modes.CBC(iv), backend=backend)
    decryptor = cipher.decryptor()
    return decryptor.update(encrypted_key) + decryptor.finalize()

def envelope_encrypt(data: bytes, master_key: bytes) -> bytes:
    data_encryption_key = generate_data_encryption_key()
    encrypted_data = encrypt_data(data, data_encryption_key)
    encrypted_data_key = encrypt_key(data_encryption_key, master_key)  # <-- Fixed
    return encrypted_data_key + encrypted_data

def envelope_decrypt(encrypted_data: bytes, master_key: bytes) -> bytes:
    encrypted_data_key, encrypted_data = encrypted_data[:48], encrypted_data[48:]  # <-- This is correct
    data_encryption_key = decrypt_key(encrypted_data_key, master_key)  # <-- Fixed
    return decrypt_data(encrypted_data, data_encryption_key)