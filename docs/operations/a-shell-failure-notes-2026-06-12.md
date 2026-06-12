# a-Shell Failure Notes 2026-06-12

## Scope

This note records the observed iPhone/a-Shell execution failures and their operational factors. It intentionally excludes private iOS container UUIDs and any local personal path fragments beyond the project-relative context.

## Observed facts

- `lg2 pull` completed and fast-forwarded `main`.
- `python3 -m py_compile scripts/mobile_operator.py` completed without output.
- `python3 scripts/mobile_operator.py self-test` printed `mobile operator self-test ok`.
- `python3 scripts/mobile_operator.py validate` returned without visible failure output.
- `python3 scripts/mobile_operator.py serve --port 8001` entered serving mode and therefore did not return a normal shell prompt until interrupted.
- `sh scripts/codex_cloud_setup.sh` failed after Python compile checks, dataset validation, mobile operator self-test and static server self-test had already passed.

## Root cause recorded

`repository_audit_report.py --output /tmp/upgraded-fiesta-audit.json` failed in a-Shell with `PermissionError: [Errno 1] Operation not permitted` while opening the output path for writing.

## Related factors

- a-Shell on iOS does not behave like a normal Linux shell for every filesystem path.
- `/tmp` is not a safe portable write target for this iPhone workflow.
- Setup scripts must prefer stdout or a project/Developer-owned path over `/tmp`.
- The local installer file under `~/Documents/ashell_onebash_installer.sh` can be stale even when the repository has been updated.

## Remediation applied

- `scripts/codex_cloud_setup.sh` now runs the audit report without writing to `/tmp`.
- `install/ashell_onebash_installer.sh` now avoids the tmp-dependent repository validator and calls the Codex cloud setup gate instead.

## Remaining check

After pulling the latest `main`, run:

```sh
sh scripts/codex_cloud_setup.sh
```

Then refresh the local installer copy before testing installer behavior:

```sh
python3 -c "import urllib.request,pathlib; p=pathlib.Path.home()/'Documents'/'ashell_onebash_installer.sh'; p.write_text(urllib.request.urlopen('https://raw.githubusercontent.com/benholl94-cmyk/upgraded-fiesta/main/install/ashell_onebash_installer.sh').read().decode('utf-8'), encoding='utf-8'); print(p)"
sh ~/Documents/ashell_onebash_installer.sh
```
