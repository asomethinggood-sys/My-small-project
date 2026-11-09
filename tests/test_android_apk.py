"""Synthetic ELF fixtures test packaging checks, never Android execution."""
import contextlib
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('check_apk', Path(__file__).resolve().parents[1]/'android/scripts/check-apk.py')
apk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apk)


class ApkTests(unittest.TestCase):
    def make(self, path, abis, missing=False, wrong_machine=False, compressed=False, misaligned=False):
        with zipfile.ZipFile(path, 'w') as archive:
            for abi in abis:
                bits, machine = apk.MACHINES[abi]
                for lib in ['libcontinuum_core.so', 'libgojni.so']:
                    if missing and lib == 'libgojni.so': continue
                    data = bytearray(256)
                    data[:6] = b'\x7fELF'+bytes([bits, 1])
                    struct.pack_into('<H', data, 18, 0 if wrong_machine else machine)
                    if bits == 2:
                        struct.pack_into('<Q', data, 32, 64)
                        struct.pack_into('<HH', data, 54, 56, 1)
                        struct.pack_into('<I', data, 64, 1)
                        struct.pack_into('<Q', data, 112, 16384)
                    else:
                        struct.pack_into('<I', data, 28, 52)
                        struct.pack_into('<HH', data, 42, 32, 1)
                        struct.pack_into('<I', data, 52, 1)
                        struct.pack_into('<I', data, 80, 4096)
                    info = zipfile.ZipInfo(f'lib/{abi}/{lib}')
                    info.compress_type = zipfile.ZIP_DEFLATED if compressed else zipfile.ZIP_STORED
                    padding = (-archive.fp.tell()-30-len(info.filename)) % 16384
                    if padding < 4: padding += 16384
                    if not misaligned: info.extra = struct.pack('<HH', 0xffff, padding-4)+bytes(padding-4)
                    archive.writestr(info, data)

    def test_all_four_abis_and_single_abi(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            path = Path(directory)/'candidate.apk'
            for abi in apk.MACHINES:
                self.make(path, [abi]); apk.check(path, abi)
            self.make(path, list(apk.MACHINES)); apk.check(path, 'universal')

    def test_incomplete_or_unloadable_packages_rejected(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            path = Path(directory)/'candidate.apk'
            for flag in ['missing', 'wrong_machine', 'compressed', 'misaligned']:
                with self.subTest(flag=flag):
                    self.make(path, ['arm64-v8a'], **{flag: True})
                    with self.assertRaises(AssertionError): apk.check(path, 'arm64-v8a')
            self.make(path, ['arm64-v8a'])
            with self.assertRaises(AssertionError): apk.check(path, 'universal')
