"""Re-implementation of the feature extractor used to build malware.csv (pefile-based, 54 features)."""
import math, pefile
from collections import Counter

def entropy(data):
    if not data: return 0.0
    n = len(data); c = Counter(data)
    return -sum(v / n * math.log2(v / n) for v in c.values())

def get_resources(pe):
    out = []
    if hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
        for rtype in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if hasattr(rtype, 'directory'):
                for rid in rtype.directory.entries:
                    if hasattr(rid, 'directory'):
                        for rlang in rid.directory.entries:
                            try:
                                size = rlang.data.struct.Size
                                data = pe.get_data(rlang.data.struct.OffsetToData, size)
                                out.append((entropy(data), size))
                            except Exception:
                                pass
    return out

def version_info_size(pe):
    if not hasattr(pe, 'FileInfo'):
        return 0
    keys = set()
    for group in pe.FileInfo:
        for fi in (group if isinstance(group, list) else [group]):
            key = getattr(fi, 'Key', b'')
            key = key.decode() if isinstance(key, bytes) else key
            if key == 'StringFileInfo':
                for st in fi.StringTable:
                    keys.update(st.entries.keys())
            elif key == 'VarFileInfo':
                for var in fi.Var:
                    keys.update(list(var.entry.keys())[:1])
    if hasattr(pe, 'VS_FIXEDFILEINFO'):
        keys.update(['flags', 'os', 'type', 'file_version', 'product_version', 'signature', 'struct_version'])
    return len(keys)

def extract(path):
    pe = pefile.PE(path)
    try:
        return _extract_fields(pe)
    finally:
        # pefile mmaps the file; without an explicit close the handle stays
        # open and a caller can't delete/replace the file on Windows.
        pe.close()


def _extract_fields(pe):
    fh, oh = pe.FILE_HEADER, pe.OPTIONAL_HEADER
    r = {'Machine': fh.Machine, 'SizeOfOptionalHeader': fh.SizeOfOptionalHeader, 'Characteristics': fh.Characteristics}
    for f in ['MajorLinkerVersion', 'MinorLinkerVersion', 'SizeOfCode', 'SizeOfInitializedData', 'SizeOfUninitializedData',
              'AddressOfEntryPoint', 'BaseOfCode']:
        r[f] = getattr(oh, f)
    r['BaseOfData'] = getattr(oh, 'BaseOfData', 0)
    for f in ['ImageBase', 'SectionAlignment', 'FileAlignment', 'MajorOperatingSystemVersion', 'MinorOperatingSystemVersion',
              'MajorImageVersion', 'MinorImageVersion', 'MajorSubsystemVersion', 'MinorSubsystemVersion', 'SizeOfImage',
              'SizeOfHeaders', 'CheckSum', 'Subsystem', 'DllCharacteristics', 'SizeOfStackReserve', 'SizeOfStackCommit',
              'SizeOfHeapReserve', 'SizeOfHeapCommit', 'LoaderFlags', 'NumberOfRvaAndSizes']:
        r[f] = getattr(oh, f)
    secs = pe.sections
    r['SectionsNb'] = len(secs)
    ent = [s.get_entropy() for s in secs] or [0]
    raw = [s.SizeOfRawData for s in secs] or [0]
    vs = [s.Misc_VirtualSize for s in secs] or [0]
    r.update(SectionsMeanEntropy=sum(ent) / len(ent), SectionsMinEntropy=min(ent), SectionsMaxEntropy=max(ent),
             SectionsMeanRawsize=sum(raw) / len(raw), SectionsMinRawsize=min(raw), SectionMaxRawsize=max(raw),
             SectionsMeanVirtualsize=sum(vs) / len(vs), SectionsMinVirtualsize=min(vs), SectionMaxVirtualsize=max(vs))
    if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
        imps = [i for d in pe.DIRECTORY_ENTRY_IMPORT for i in d.imports]
        r.update(ImportsNbDLL=len(pe.DIRECTORY_ENTRY_IMPORT), ImportsNb=len(imps),
                 ImportsNbOrdinal=sum(1 for i in imps if i.name is None))
    else:
        r.update(ImportsNbDLL=0, ImportsNb=0, ImportsNbOrdinal=0)
    r['ExportNb'] = len(pe.DIRECTORY_ENTRY_EXPORT.symbols) if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT') else 0
    res = get_resources(pe)
    r['ResourcesNb'] = len(res)
    if res:
        e = [x[0] for x in res]; s = [x[1] for x in res]
        r.update(ResourcesMeanEntropy=sum(e) / len(e), ResourcesMinEntropy=min(e), ResourcesMaxEntropy=max(e),
                 ResourcesMeanSize=sum(s) / len(s), ResourcesMinSize=min(s), ResourcesMaxSize=max(s))
    else:
        r.update(ResourcesMeanEntropy=0, ResourcesMinEntropy=0, ResourcesMaxEntropy=0,
                 ResourcesMeanSize=0, ResourcesMinSize=0, ResourcesMaxSize=0)
    r['LoadConfigurationSize'] = pe.DIRECTORY_ENTRY_LOAD_CONFIG.struct.Size if hasattr(pe, 'DIRECTORY_ENTRY_LOAD_CONFIG') else 0
    r['VersionInformationSize'] = version_info_size(pe)
    return r
