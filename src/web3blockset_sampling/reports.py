"""Researcher-readable reports computed from the actual population and selection."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from .ingestion import write_csv, write_json
from .preparation import Prepared
from .statistics import Allocation, cochran_n0
from .stratification import STRATA


def distributions(units: list) -> dict:
    by_stratum = {}
    for stratum in STRATA:
        group = [u for u in units if u.stratum == stratum]
        repos = Counter(u.repository for u in group)
        by_stratum[stratum] = {"records": len(group), "repositories": len(repos),
                               "artifact_types": dict(Counter(u.artifact_type for u in group)),
                               "top_repositories": [{"repository": r, "records": n, "share": n / len(group)}
                                                    for r, n in repos.most_common(10)]}
    return {"total": len(units), "sources": dict(Counter(u.source for u in units)),
            "strata": by_stratum, "categories": dict(Counter(u.category for u in units))}


def write_reports(directory: Path, prepared: Prepared, allocation: dict[str, Allocation],
                  selected: set[str] | None, run_id: str, checks: dict | None = None) -> dict:
    eligible = prepared.eligible
    chosen = [u for u in eligible if selected is not None and u.unit_id in selected]
    population = distributions(eligible)
    sample = distributions(chosen)
    summary = []
    for stratum in STRATA:
        a = allocation[stratum]
        summary.append({**a.to_dict(), "before_exclusions": prepared.audit["strata_before_exclusions"][stratum],
                        "excluded": prepared.audit["strata_before_exclusions"][stratum] - a.population,
                        "metadata_repositories": prepared.audit["join"]["metadata_repositories_by_stratum"].get(stratum, 0)
                        if stratum != "Community" or prepared.config.repository_scope == "all" else None,
                        "population_repositories": population["strata"][stratum]["repositories"],
                        "sample_repositories": sample["strata"][stratum]["repositories"]})
    write_csv(directory / "strata_summary.csv", list(summary[0]), summary)
    concentration = []
    for scope, group in (("population", eligible), ("sample", chosen)):
        counts = Counter((u.stratum, u.repository) for u in group)
        totals = Counter(u.stratum for u in group)
        for (stratum, repository), n in sorted(counts.items()):
            concentration.append({"scope": scope, "stratum": stratum, "repository": repository,
                                  "records": n, "share": n / totals[stratum]})
    write_csv(directory / "repository_distribution.csv", ["scope", "stratum", "repository", "records", "share"], concentration)
    logical_counts = Counter(u.logical_id for u in prepared.units)
    groups = defaultdict(list)
    for unit in prepared.units:
        if logical_counts[unit.logical_id] > 1:
            groups[unit.logical_id].append(unit)
    duplicate_records = []
    for lid, units in sorted(groups.items()):
        duplicate_records.append({
            "logical_id": lid, "repository": units[0].repository,
            "record_ids": json.dumps(sorted({u.record_id for u in units})),
            "occurrences": len(units), "content_variants": len({u.row_hash for u in units}),
            "source_counts": json.dumps(dict(Counter(u.source for u in units)), sort_keys=True),
            "stratum_counts": json.dumps(dict(Counter(u.stratum for u in units)), ensure_ascii=False, sort_keys=True),
            "rows_excluded": sum(u.unit_id in prepared.excluded for u in units),
        })
    write_csv(directory / "duplicate_groups.csv", ["logical_id", "repository", "record_ids", "occurrences", "content_variants",
              "source_counts", "stratum_counts", "rows_excluded"], duplicate_records)
    exclusion_records = []
    for role in ("pilot", "smoke"):
        for result in prepared.audit.get(role + "_exclusion", {}).get("key_results", []):
            exclusion_records.append({"role": role, **{k: json.dumps(v, ensure_ascii=False, sort_keys=True)
                                                      if isinstance(v, (list, dict)) else v for k, v in result.items()}})
    write_csv(directory / "exclusions_audit.csv", ["role", "key", "input_occurrences", "status", "matched_rows",
              "logical_identifiers", "rows_removed", "sources", "strata"], exclusion_records)
    validation = {"run_id": run_id, "definitive": selected is not None and not prepared.blockers,
                  "blockers": prepared.blockers, "audit": prepared.audit,
                  "population": population, "sample": sample, "checks": checks or {}}
    write_json(directory / "validation_report.json", validation)
    total_sample = sum(a.sample for a in allocation.values())
    pilot = prepared.audit.get("pilot_exclusion", {})
    smoke = prepared.audit.get("smoke_exclusion")
    lines = ["# Relatório de amostragem — Web3BlockSet", "", f"Execução: `{run_id}`.", "",
             "Status: " + ("definitivo, verificações aprovadas." if validation["definitive"] else "preparação provisória; não constitui amostra definitiva."),
             "", "## Universo e integridade", "", f"Versão: {prepared.config.corpus_version}.",
             f"Registros lidos: {prepared.audit['input_rows']}; elegíveis: {len(eligible)}.",
             f"Política de duplicidades: {prepared.config.duplicate_policy}. Decisão: {prepared.config.duplicate_decision or 'bloquear identidades repetidas'}.",
             f"Decisão de corpus alternativo: {prepared.config.corpus_decision or 'universo original MSR 2026'}.",
             "Junção muitos-para-um; chaves repetidas nos metadados são proibidas. Não há descarte silencioso.",
             f"Escopo dos metadados: {prepared.config.repository_scope}. "
             f"Linhas associadas por junção: {prepared.audit['join']['matched_rows']}; "
             f"community encaminhadas sem junção provider: {prepared.audit['join']['community_rows_without_provider_join']}.",
             "As verificações de preparação estão registradas em validation_report.json; não requerem sorteio.",
             "", "## Estratificação e exclusões", "",
             f"Mapeamento: {prepared.mapping.version}; SHA-256: `{prepared.mapping.sha256}`.",
             "33 categorias provider, oito estratos provider e um Community. Other é a única categoria de Outros.",
             f"Piloto: {pilot.get('input_rows', 0)} linhas de entrada; {pilot.get('found_keys', 0)} chaves encontradas; "
             f"{pilot.get('logical_identifiers_excluded', 0)} identidades lógicas; {pilot.get('rows_removed', 0)} linhas removidas.",
             f"Diagnóstico do piloto: {pilot.get('missing_count', 0)} ausentes; {pilot.get('ambiguous_count', 0)} ambíguas; {pilot.get('duplicate_keys', 0)} repetidas.",
             f"Decisão de divergência de exclusões: {prepared.config.exclusion_decision or 'nenhuma'}.",
             f"Smoke test: {str(smoke['rows_removed']) + ' linhas adicionais removidas; decisão: ' + prepared.config.smoke_decision if smoke else 'não excluído'}.",
             "", "## Fórmula e distribuição", "", "n₀ = z² p(1−p) / e²; nₕ = ceil(n₀ / (1+(n₀−1)/Nₕ)), limitado a Nₕ.",
             f"Confiança: {prepared.config.confidence}; z={prepared.config.z}; p={prepared.config.p}; e={prepared.config.error}; n₀={cochran_n0(prepared.config.z, prepared.config.p, prepared.config.error):.8f}.",
             f"Tamanho calculado: {total_sample}; diferença para a previsão de 3.410: {total_sample - 3410:+d}.",
             "A diferença decorre de populações elegíveis reais, exclusões e arredondamento para cima; não se força o total previsto.",
             "", "| Estrato | Antes | Excluídos | Nₕ | nₕ | Wₕ | Nₕ/nₕ |", "|---|---:|---:|---:|---:|---:|---:|"]
    lines += [f"| {s['stratum']} | {s['before_exclusions']} | {s['excluded']} | {s['population']} | {s['sample']} | {s['population_weight']:.8f} | {s['design_weight']} |" for s in summary]
    lines += ["", "## Pesos e tipos de artefato", "", "Estime proporções globais por Σ Wₕ p̂ₕ. Para provider use sampling_provider_weight (soma 1 entre os oito estratos).",
              "sampling_design_weight = Nₕ/nₕ é o peso de expansão por observação; não é Wₕ.",
              "", "| Estrato | Issues população | PRs população | Issues amostra | PRs amostra |", "|---|---:|---:|---:|---:|"]
    for s in STRATA:
        a = population["strata"][s]["artifact_types"]
        b = sample["strata"][s]["artifact_types"]
        lines.append(f"| {s} | {a.get('issue', 0)} | {a.get('pull_request', 0)} | {b.get('issue', 0)} | {b.get('pull_request', 0)} |")
    lines += ["", "## Categorias originais (população elegível)", ""]
    lines += [f"- {category or '(ausente/community)'}: {n}" for category, n in sorted(population["categories"].items())]
    lines += ["", "## Concentração por repositório", "", "A distribuição completa está em repository_distribution.csv; não se aplicam cotas por repositório."]
    for stratum in STRATA:
        info = population["strata"][stratum]
        top = "; ".join(f"{r['repository']}: {r['share']:.2%}" for r in info["top_repositories"][:5])
        lines.append(f"- {stratum}: {info['repositories']} repositórios; maiores participações: {top or 'nenhum'}.")
    lines += ["", "## Limitações e reprodução", "", "A margem de ±5% do método de referência por estrato refere-se à proporção que discute pelo menos um pattern. A margem configurada nesta execução consta dos parâmetros acima. Não mede erro da LLM, precisão de cada pattern, tempos de resolução nem poder para pequenas diferenças.",
              "A margem global aproximada de ±2,1% não é utilizada como constante nem é calculada por esta aplicação. Avaliação da LLM e Rogan–Gladen ficam no projeto de análise.",
              "O universo é definido pelos arquivos originais e seus hashes. O período observado nas datas deve ser conferido com o documento metodológico; não se aplica um filtro temporal implícito. Contagens iguais não comprovam a proveniência.",
              "Consulte sampling_manifest.json e config_snapshot.json para caminhos, hashes, ambiente, semente, parâmetros e decisões. Use validate --run-dir para repetir as verificações.",
              "", "## Bloqueios", ""]
    lines += [f"- {b}" for b in prepared.blockers] or ["Nenhum."]
    (directory / "sampling_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return validation
