# -*- coding: utf-8 -*-
"""Build install.bat / uninstall.bat from templates.

- Embeds PowerShell snippets as -EncodedCommand base64 (UTF-16LE),
  immune to cmd quoting/escaping hell.
- Converts final files to ANSI/GBK (Chinese Windows native codepage),
  CRLF line endings, no BOM. Never save these bats as UTF-8.
- Runs a battery of static checks (no chcp 65001, no for /f,
  no bare parens outside quotes, labels defined, blob decode).
"""
import base64, os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blob(ps: str) -> str:
    return base64.b64encode(ps.encode("utf-16-le")).decode("ascii")


PS_GPU = (
    "$g = (Get-CimInstance Win32_VideoController).Name -join ' ; '\n"
    "Write-Host ('  GPU: ' + $g)\n"
    "if ($g -match 'RX 9[0-9][0-9]') { exit 0 } else { exit 1 }\n"
)

PS_DISK = (
    "$d = $env:RDNA4_DRIVE\n"
    "$f = (Get-PSDrive $d).Free / 1GB\n"
    "Write-Host ('  ' + $d + ': free ' + [int]$f + ' GB')\n"
    "if ($f -lt 20) { exit 1 } else { exit 0 }\n"
)

PS_SC = (
    "$inst = $env:RDNA4_INSTDIR\n"
    "$desk = [Environment]::GetFolderPath('Desktop')\n"
    "$w = New-Object -ComObject WScript.Shell\n"
    "$l = @(@('Applio \u63a8\u7406', 'run_infer.bat'), @('Applio \u8bad\u7ec3', 'run_train.bat'))\n"
    "foreach ($n in $l) {\n"
    "  $s = $w.CreateShortcut([IO.Path]::Combine($desk, $n[0] + '.lnk'))\n"
    "  $s.TargetPath = [IO.Path]::Combine($inst, $n[1])\n"
    "  $s.WorkingDirectory = $inst\n"
    "  $s.IconLocation = [IO.Path]::Combine($inst, 'runtime\\python.exe')\n"
    "  $s.Save()\n"
    "}\n"
    "Write-Host '  shortcuts ok'\n"
    "exit 0\n"
)

PS_DLCHK = (
    "$f = $env:RDNA4_DLFILE\n"
    "$u = $env:RDNA4_DLURL\n"
    "$l = (Get-Item -LiteralPath $f -ErrorAction SilentlyContinue).Length\n"
    "$r = 0\n"
    "try { $r = [long](Invoke-WebRequest -Uri $u -Method Head -UseBasicParsing).Headers['Content-Length'] } catch {}\n"
    "if ($l -and $r -gt 0 -and $l -eq $r) { exit 0 } else { exit 1 }\n"
)

PS_LNKDEL = (
    "$desk = [Environment]::GetFolderPath('Desktop')\n"
    "Remove-Item -LiteralPath ([IO.Path]::Combine($desk, 'Applio \u63a8\u7406.lnk')) -ErrorAction SilentlyContinue\n"
    "Remove-Item -LiteralPath ([IO.Path]::Combine($desk, 'Applio \u8bad\u7ec3.lnk')) -ErrorAction SilentlyContinue\n"
    "exit 0\n"
)

BLOBS = {
    "{{BLOB_GPU}}": blob(PS_GPU),
    "{{BLOB_DISK}}": blob(PS_DISK),
    "{{BLOB_SC}}": blob(PS_SC),
    "{{BLOB_DLCHK}}": blob(PS_DLCHK),
    "{{BLOB_LNKDEL}}": blob(PS_LNKDEL),
}


def build(tpl_path: str, out_path: str) -> bytes:
    with open(tpl_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    for k, v in BLOBS.items():
        text = text.replace(k, v)
    leftover = re.findall(r"\{\{BLOB_\w+\}\}", text)
    assert not leftover, "unresolved placeholders: %s" % leftover
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    out = "\r\n".join(lines) + "\r\n"
    data = out.encode("gbk")  # raises on unencodable chars - we want to know
    with open(out_path, "wb") as fh:
        fh.write(data)
    return data


def verify(name: str, data: bytes) -> list:
    problems = []
    t = data.decode("gbk")
    lines = t.split("\r\n")

    if data.startswith(b"\xef\xbb\xbf"):
        problems.append("UTF-8 BOM present")
    # chcp 65001 on executable lines (rem comments may mention it as a warning)
    for ln in lines:
        if ln.lstrip().lower().startswith("rem "):
            continue
        if "chcp 65001" in ln.lower():
            problems.append("chcp 65001 found: " + ln[:60])
    if re.search(r"for\s+/f", t, re.I):
        problems.append("for /f found")

    # bare LF anywhere?
    if b"\n" in data.replace(b"\r\n", b""):
        problems.append("bare LF found")

    # labels defined vs referenced
    labels = set()
    for ln in lines:
        m = re.match(r"^:([A-Za-z_]\w*)", ln)
        if m:
            labels.add(m.group(1))
    for ln in lines:
        for m in re.finditer(r"(?:goto|call)\s+:?([A-Za-z_]\w*)", ln, re.I):
            if m.group(1).lower() == "eof":  # builtin: end of file
                continue
            if m.group(1) not in labels:
                problems.append("undefined label ref: " + m.group(1))

    # per-line: quote parity + no bare parens outside quotes
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().lower().startswith("rem "):
            continue
        inq = False
        bare = False
        for ch in ln:
            if ch == '"':
                inq = not inq
            elif ch in "()" and not inq:
                bare = True
        if inq:
            problems.append("line %d: odd number of quotes: %s" % (i, ln[:60]))
        if bare:
            problems.append("line %d: bare paren outside quotes: %s" % (i, ln[:60]))

    # line length sanity
    for i, ln in enumerate(lines, 1):
        if len(ln) > 4000:
            problems.append("line %d too long (%d chars)" % (i, len(ln)))

    # blob lines: decode and show
    n_blobs = 0
    for i, ln in enumerate(lines, 1):
        m = re.match(r"^powershell -NoProfile -EncodedCommand ([A-Za-z0-9+/=]+)", ln)
        if m:
            n_blobs += 1
            ps = base64.b64decode(m.group(1)).decode("utf-16-le")
            print("  [blob line %d, %d chars] decodes to:" % (i, len(m.group(1))))
            for pl in ps.rstrip("\n").split("\n"):
                print("      " + pl)
    print("  %s: %d lines, %d bytes, %d blobs, %d labels" % (name, len(lines), len(data), n_blobs, len(labels)))
    return problems


def main() -> int:
    print("== build ==")
    jobs = [
        (ROOT + r"\builder\install.tpl.bat", ROOT + r"\install.bat", "install.bat"),
        (ROOT + r"\builder\uninstall.tpl.bat", ROOT + r"\uninstall.bat", "uninstall.bat"),
    ]
    all_problems = []
    for tpl, out, name in jobs:
        data = build(tpl, out)
        print("-- %s --" % name)
        problems = verify(name, data)
        for p in problems:
            print("  PROBLEM: " + p)
        all_problems += [(name, p) for p in problems]
    if all_problems:
        print("FAILED: %d problems" % len(all_problems))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
