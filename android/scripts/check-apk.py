"""Validate the exact delivered APK's ABI completeness and direct-load alignment."""
import hashlib
from pathlib import Path
import struct
import sys
import zipfile

MACHINES = {'arm64-v8a': (2, 183), 'armeabi-v7a': (1, 40), 'x86_64': (2, 62), 'x86': (1, 3)}


def check(path, requested):
    expected = set(MACHINES) if requested == 'universal' else {requested}
    assert expected <= MACHINES.keys(), 'Unknown ABI'
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        native = [n for n in archive.namelist() if n.startswith('lib/') and n.endswith('.so')]
        assert {n.split('/')[1] for n in native} == expected, 'Wrong ABI set'
        for abi in expected:
            for library in ('libcontinuum_core.so', 'libgojni.so'):
                assert f'lib/{abi}/{library}' in native, f'Missing {abi}/{library}'
        for name in native:
            abi = name.split('/')[1]
            elf_class, machine = MACHINES[abi]
            info = archive.getinfo(name)
            assert info.compress_type == zipfile.ZIP_STORED, 'Native libraries must be directly mappable'
            data = archive.read(name)
            assert data[:6] == b'\x7fELF' + bytes([elf_class, 1])
            assert struct.unpack_from('<H', data, 18)[0] == machine
            if elf_class == 2:
                offset = struct.unpack_from('<Q', data, 32)[0]
                stride, count = struct.unpack_from('<HH', data, 54)
            else:
                offset = struct.unpack_from('<I', data, 28)[0]
                stride, count = struct.unpack_from('<HH', data, 42)
            loads = 0
            for index in range(count):
                start = offset + stride * index
                if struct.unpack_from('<I', data, start)[0] != 1:
                    continue
                loads += 1
                if elf_class == 2:
                    file_offset, virtual = struct.unpack_from('<QQ', data, start+8)
                    alignment = struct.unpack_from('<Q', data, start+48)[0]
                else:
                    file_offset, virtual = struct.unpack_from('<II', data, start+4)
                    alignment = struct.unpack_from('<I', data, start+28)[0]
                # Android's 16 KB devices use 64-bit ABIs. 32-bit devices use 4 KB.
                page = 16384 if elf_class == 2 else 4096
                assert alignment >= page and (virtual-file_offset) % page == 0, 'ELF page incompatibility'
            assert loads > 0
            with path.open('rb') as stream:
                stream.seek(info.header_offset)
                local = stream.read(30)
                name_length, extra_length = struct.unpack_from('<HH', local, 26)
                payload = info.header_offset+30+name_length+extra_length
                assert payload % page == 0, 'APK native data is not page aligned'
            print(f'::notice title=Native packaging::{name}; uncompressed; ELF and ZIP compatible with {page}-byte pages')
    print(f'::notice title=APK byte integrity::{path.stat().st_size} bytes; SHA256 '+hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    check(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else 'arm64-v8a')
