"""Plain-English phrasing for FileGuard's Event.reasons.

Maps the 54 raw PE feature names to short human descriptions, so the
console's "why" panel can show something a non-ML analyst can read
instead of a bare coefficient. Falls back to the raw name for anything
not in the map. MailGuard emits no reasons: it reports a score and a
clean / suspicious / malicious verdict only.
"""

# -- FileGuard: the 54 PE header features (see sentinel_ml/pe_features.py)
FILE_FEATURE_DESCRIPTIONS = {
    "Machine": "target CPU architecture",
    "SizeOfOptionalHeader": "size of the optional header",
    "Characteristics": "file characteristics flags (executable, DLL, etc.)",
    "MajorLinkerVersion": "linker version (major)",
    "MinorLinkerVersion": "linker version (minor)",
    "SizeOfCode": "size of the code section",
    "SizeOfInitializedData": "size of initialized data",
    "SizeOfUninitializedData": "size of uninitialized data",
    "AddressOfEntryPoint": "entry point address",
    "BaseOfCode": "base address of the code section",
    "BaseOfData": "base address of the data section",
    "ImageBase": "preferred load address (the model leans on this heavily; it may reflect how the training files were built, not behaviour)",
    "SectionAlignment": "section alignment in memory",
    "FileAlignment": "section alignment on disk",
    "MajorOperatingSystemVersion": "minimum OS version required (major)",
    "MinorOperatingSystemVersion": "minimum OS version required (minor)",
    "MajorImageVersion": "image version (major)",
    "MinorImageVersion": "image version (minor)",
    "MajorSubsystemVersion": "subsystem version required (major)",
    "MinorSubsystemVersion": "subsystem version required (minor)",
    "SizeOfImage": "total size of the file once loaded into memory",
    "SizeOfHeaders": "size of all the headers combined",
    "CheckSum": "PE checksum (often zero/unset in hand-built malware)",
    "Subsystem": "subsystem (GUI, console, driver, ...)",
    "DllCharacteristics": "DLL/security flags (ASLR, DEP, signing requirements, ...)",
    "SizeOfStackReserve": "reserved stack size",
    "SizeOfStackCommit": "committed stack size",
    "SizeOfHeapReserve": "reserved heap size",
    "SizeOfHeapCommit": "committed heap size",
    "LoaderFlags": "obsolete loader flags field",
    "NumberOfRvaAndSizes": "number of data-directory entries",
    "SectionsNb": "number of sections",
    "SectionsMeanEntropy": "average section entropy (high = compressed/encrypted-looking)",
    "SectionsMinEntropy": "lowest section entropy",
    "SectionsMaxEntropy": "highest section entropy (high = packed or encrypted code)",
    "SectionsMeanRawsize": "average section size on disk",
    "SectionsMinRawsize": "smallest section size on disk",
    "SectionMaxRawsize": "largest section size on disk",
    "SectionsMeanVirtualsize": "average section size in memory",
    "SectionsMinVirtualsize": "smallest section size in memory",
    "SectionMaxVirtualsize": "largest section size in memory",
    "ImportsNbDLL": "number of DLLs imported",
    "ImportsNb": "number of imported functions",
    "ImportsNbOrdinal": "functions imported by ordinal only (no name -- often obfuscation)",
    "ExportNb": "number of exported functions",
    "ResourcesNb": "number of embedded resources",
    "ResourcesMeanEntropy": "average resource entropy",
    "ResourcesMinEntropy": "lowest resource entropy",
    "ResourcesMaxEntropy": "highest resource entropy (high = a hidden compressed/encrypted payload)",
    "ResourcesMeanSize": "average resource size",
    "ResourcesMinSize": "smallest resource size",
    "ResourcesMaxSize": "largest resource size",
    "LoadConfigurationSize": "size of the load-configuration structure",
    "VersionInformationSize": "amount of version info present (legit software is usually well-populated)",
}

_HEX_FEATURES = {"ImageBase", "DllCharacteristics", "Characteristics", "Machine"}


def _fmt_file_value(feature: str, value: float) -> str:
    # address-like fields are read in hex (0x400000), not 4.1943e+06
    return hex(int(value)) if feature in _HEX_FEATURES else f"{value:g}"


def humanize_file_reason(feature: str, value: float, contrib: float) -> str:
    direction = "malicious" if contrib > 0 else "benign"
    strength = "strongly" if abs(contrib) > 2 else "moderately" if abs(contrib) > 0.5 else "slightly"
    phrase = FILE_FEATURE_DESCRIPTIONS.get(feature, feature)
    return f"{phrase} ({feature}={_fmt_file_value(feature, value)}) -- {strength} suggests {direction}"
