"""Command line entry point; domain failures return exit status 2."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .errors import ValidationError
from .ingestion import inspect_csv, write_json
from .stratification import load_mapping
from .workflow import run, validate_run


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Amostragem estratificada reproduzível do Web3BlockSet")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("inspect", "prepare", "sample"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, default=Path("configs/sampling.json"))
        for option in ("issues", "repositories", "pilot", "mapping", "output", "approval", "smoke"):
            command.add_argument("--" + option, type=Path)
        if name == "inspect":
            command.add_argument("--file", type=Path, action="append", help="Inspecionar um ou mais CSVs sem configuração")
        if name in {"prepare", "sample"}:
            command.add_argument("--seed", type=int)
            for option in ("z", "p", "error", "confidence"):
                command.add_argument("--" + option, type=float)
            command.add_argument("--duplicate-policy", choices=["error", "preserve_rows"])
            for option in ("corpus-version", "corpus-decision", "duplicate-decision", "exclusion-decision", "smoke-decision"):
                command.add_argument("--" + option)
            command.add_argument("--dry-run", action="store_true")
    validate = commands.add_parser("validate")
    validate.add_argument("--run-dir", type=Path, required=True)
    approval = commands.add_parser("approve-mapping", help="Registrar uma aprovação humana vinculada ao hash do agrupamento")
    approval.add_argument("--mapping", type=Path, required=True)
    approval.add_argument("--output", type=Path, required=True)
    approval.add_argument("--reviewer", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "approve-mapping":
            if not args.reviewer.strip():
                raise ValidationError("Informe o nome do pesquisador que aprovou o agrupamento")
            mapping = load_mapping(args.mapping)
            write_json(args.output, {"mapping_sha256": mapping.sha256, "mapping_version": mapping.version,
                                     "approved_by": args.reviewer, "approved_at": datetime.now(timezone.utc).isoformat()})
            print(json.dumps({"approval": str(args.output)}, ensure_ascii=False))
            return 0
        if args.command == "validate":
            print(json.dumps(validate_run(args.run_dir), ensure_ascii=False, indent=2))
            return 0
        if args.command == "inspect" and args.file:
            print(json.dumps([inspect_csv(p) for p in args.file], ensure_ascii=False, indent=2))
            return 0
        excluded = {"command", "config", "dry_run", "file"}
        overrides = {k: v.resolve() if isinstance(v, Path) else v for k, v in vars(args).items() if k not in excluded}
        config = load_config(args.config, overrides)
        if args.command == "inspect":
            profiles = {role: inspect_csv(getattr(config, role), config.encoding, config.delimiter)
                        for role in ("issues", "repositories", "pilot")}
            print(json.dumps(profiles, ensure_ascii=False, indent=2))
            return 0
        directory, manifest = run(config, definitive=args.command == "sample" and not args.dry_run)
        print(json.dumps({"run_directory": str(directory.resolve()), "status": manifest["status"],
                          "eligible_population": manifest.get("eligible_population"),
                          "calculated_sample": manifest.get("calculated_sample"),
                          "blockers": manifest["blockers"]}, ensure_ascii=False, indent=2))
        return 2 if manifest["status"] == "blocked" else 0
    except (ValidationError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

