"""Check install packaging of the actual ARM64 deliverable, not just debug builds."""
import hashlib
from pathlib import Path
import struct
import sys
import zipfile

path = Path(sys.argv[1])
with zipfile.ZipFile(path) as archive:
    assert archive.testzip() is None
    native = [name for name in archive.namelist() if name.startswith('lib/') and name.endswith('.so')]
    assert native and 'lib/arm64-v8a/libcontinuum_core.so' in native
    for name in native:
        assert name.startswith('lib/arm64-v8a/')
        info = archive.getinfo(name)
        assert info.compress_type == zipfile.ZIP_STORED, 'Native libraries must be directly mappable'
        data = archive.read(name)
        assert data[:6] == b'\x7fELF\x02\x01'
        assert struct.unpack_from('<H', data, 18)[0] == 183
        offset = struct.unpack_from('<Q', data, 32)[0]
        stride, count = struct.unpack_from('<HH', data, 54)
        loads = 0
        for index in range(count):
            start = offset + stride * index
            kind = struct.unpack_from('<I', data, start)[0]
            if kind != 1:
                continue
            loads += 1
            file_offset, virtual = struct.unpack_from('<QQ', data, start+8)
            alignment = struct.unpack_from('<Q', data, start+48)[0]
            assert alignment >= 16384 and (virtual-file_offset) % 16384 == 0, 'ELF is not 16 KB compatible'
        assert loads > 0
        with path.open('rb') as stream:
            stream.seek(info.header_offset)
            local = stream.read(30)
            name_length, extra_length = struct.unpack_from('<HH', local, 26)
            payload = info.header_offset+30+name_length+extra_length
            assert payload % 16384 == 0, 'APK native data is not 16 KB aligned'
        print('::notice title=Native packaging::'+name+'; uncompressed; ARM64; ELF and APK alignment >=16 KB')
print('::notice title=APK byte integrity::'+str(path.stat().st_size)+' bytes; SHA256 '+hashlib.sha256(path.read_bytes()).hexdigest())
