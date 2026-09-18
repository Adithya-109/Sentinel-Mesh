"""Plain-English phrasing for Event.reasons.

Maps the 54 raw PE feature names (FileGuard) and a curated list of
phishing/legit cue words (MailGuard) to short human descriptions, so the
console's "why" panel can show something a non-ML analyst can read
instead of a bare coefficient. Falls back to the raw name for anything
not in the map -- these lists are illustrative, not exhaustive.
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
    "ImageBase": "preferred load address (packers/malware often pick unusual values)",
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

# -- MailGuard: placeholder tokens + a curated list of common phishing/legit
# cue words. Anything else falls back to the raw token.
PLACEHOLDER_WORD_DESCRIPTIONS = {
    "urltok": "contains a link",
    "emailtok": "contains an email address",
    "numtok": "contains a number",
}

WORD_DESCRIPTIONS = {
    "urgent": "urgency language ('urgent')",
    "immediately": "urgency language ('immediately')",
    "verify": "asks you to verify something",
    "suspend": "threatens suspension",
    "suspended": "claims an account is suspended",
    "password": "mentions a password",
    "click": "asks you to click something",
    "account": "mentions 'account'",
    "confirm": "asks you to confirm something",
    "login": "mentions logging in",
    "log in": "mentions logging in",
    "winner": "claims you've won something",
    "congratulations": "congratulatory bait language",
    "free": "'free' offer language",
    "limited": "artificial scarcity language ('limited')",
    "bitcoin": "mentions cryptocurrency payment",
    "wire": "mentions a wire transfer",
    "gift card": "asks for gift cards (a common scam payment method)",
    "ssn": "asks for a social security number",
    "bank": "mentions banking details",
    "invoice": "mentions an invoice/payment",
    "thanks": "casual sign-off, common in legitimate mail",
    "wrote": "reply/quote language, common in legitimate threads",
    "enron": "Enron corpus internal-mail marker (dataset artifact, not a real signal)",
}


def humanize_mail_reason(token: str, contrib: float) -> str:
    direction = "phishing" if contrib > 0 else "legitimate"
    strength = "strongly" if abs(contrib) > 1.0 else "moderately" if abs(contrib) > 0.4 else "slightly"
    phrase = WORD_DESCRIPTIONS.get(token) or PLACEHOLDER_WORD_DESCRIPTIONS.get(token)
    if phrase:
        return f"{phrase} -- {strength} suggests {direction}"
    return f"the word '{token}' {strength} suggests {direction}"


def humanize_file_reason(feature: str, value: float, contrib: float) -> str:
    direction = "malicious" if contrib > 0 else "benign"
    strength = "strongly" if abs(contrib) > 2 else "moderately" if abs(contrib) > 0.5 else "slightly"
    phrase = FILE_FEATURE_DESCRIPTIONS.get(feature, feature)
    return f"{phrase} ({feature}={value:g}) -- {strength} suggests {direction}"
