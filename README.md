# web3blockset-sampling

Aplicação Python para preparar, auditar e extrair uma amostra aleatória estratificada do Web3BlockSet. Integra a pesquisa **An Empirical Study of the Adoption and Challenges of Blockchain Design Patterns in OSS Projects**, fornecendo registros, identificadores e pesos às análises de RQ1, RQ2 e RQ3.

O projeto realiza exclusivamente amostragem. Não há dependências de LLM, chamadas a serviços externos, classificação, limpeza semântica ou truncamento de textos.

## Referência e estado atual

A referência é **Cálculo da amostra final — Blockchain design patterns em issues e PRs do Web3BlockSet — 29 de outubro de 2026**, disponível em `docs/Calculo_Amostragem_Final.docx` e lida integralmente na auditoria. Seu hash acompanha as execuções. A implementação não substitui a aprovação do agrupamento pelos autores.

O universo decidido pelos pesquisadores é o **original MSR 2026**, com 391.596 linhas: 383.387 provider e 8.209 community. As atualizações do dashboard não integram esse universo. Todas as ocorrências são preservadas na preparação, exceto as exclusões do piloto. A soma amostral prevista de 3.410 é uma referência, nunca uma meta imposta. O DOCX descreve o período 2012–2024, mas o arquivo original contém datas de criação de 2011 a 2025; essa divergência documental foi registrada, sem aplicar filtro temporal.

A preparação foi validada com os três CSVs reais: 200 casos do piloto encontrados e excluídos sem ambiguidades, 391.396 linhas elegíveis e planejamento de **3.408 casos**. As 33 categorias e os nove estratos foram conferidos com o DOCX. A execução passou em 21 verificações técnicas. A versão 1.2.1 normaliza `commits_count` exclusivamente na exportação ao classificador, mantendo o smoke técnico de 15 ocorrências, as 13 colunas e o método estatístico. **O sorteio definitivo não foi executado.** Veja o [relatório técnico completo](docs/auditoria_corpus_real.md), as [evidências de validação](docs/validacao.md) e as [decisões pendentes](docs/decisoes_metodologicas.md).

## Instalação

Requer Python 3.11 ou superior. O processamento utiliza apenas a biblioteca padrão; `pytest` é uma dependência de desenvolvimento.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m web3blockset_sampling --help
```

Para usar diretamente o código, sem instalar o pacote:

```bash
PYTHONPATH=src python3 -m web3blockset_sampling --help
```

## Organização

```text
src/web3blockset_sampling/
  config.py                 # parâmetros e esquemas explícitos
  ingestion.py              # CSV em fluxo, inspeção e checksums
  identity.py                # chaves técnicas estáveis
  stratification.py         # cobertura das 33 categorias, nove estratos, aprovação
  preparation.py            # população compacta e junção muitos-para-um
  exclusions.py             # piloto e smoke opcional
  statistics.py             # Cochran, correção finita, ceil e pesos
  sampling.py               # sorteio independente por estrato
  contracts.py              # listas exatas de 13 e 14 colunas
  normalization.py          # commits_count inteiro ou vazio e auditoria da exportação
  export.py                 # recuperação de ocorrências e projeções compartilhadas
  smoke_selection.py        # cobertura técnica determinística, sem inferência
  smoke.py                  # extração técnica, artefatos e revalidação
  validation.py             # invariantes, textos e metadados
  reports.py                # distribuições e relatório metodológico
  workflow.py / cli.py      # histórico de execuções e interface
configs/strata.json          # agrupamento versionado, ainda sem aprovação real
configs/sampling.json        # configuração inicial para o esquema observado
data/raw/                    # issues_prs.csv, repositories.csv e pilot-200.csv
data/reference/              # aprovação e smoke opcional
outputs/<run_id>/            # resultados independentes de cada execução
outputs/smoke_tests/<run_id>/ # smoke técnico isolado do sorteio definitivo
tests/                      # testes pytest com dados sintéticos
docs/                       # método, contratos, diagnóstico e arquitetura
```

Dados, saídas, ambientes virtuais e credenciais são ignorados pelo Git. Os diretórios `outputs/samples` e `outputs/reports` também estão disponíveis para arquivos auxiliares; uma execução usa seu próprio diretório para manter os artefatos e seus checksums juntos.

## Receber e inspecionar os arquivos

Forneça os três CSVs oficiais por caminhos configuráveis. Eles não precisam ser copiados para o projeto. Inspecione-os antes de adaptar a configuração:

```bash
python -m web3blockset_sampling inspect --file data/raw/issues_prs.csv \
  --file data/raw/repositories.csv --file data/raw/pilot-200.csv
```

`inspect` lê o arquivo completo e informa cabeçalhos, vazios, comprimentos máximos, valores com aparência de inteiros, distribuições de tokens, períodos observados nas datas e unicidade de possíveis chaves. Todos os dados são lidos como strings; inferência de tipo não transforma conteúdo. As chaves sugeridas pela inspeção usam valores brutos e **não são escolhidas automaticamente**.

Configure [configs/sampling.json](configs/sampling.json). Caminhos nesse arquivo são relativos ao próprio arquivo de configuração; caminhos passados pela CLI são relativos ao diretório de execução. A CLI também oferece `--issues`, `--repositories`, `--pilot`, `--mapping`, `--output`, `--approval`, `--seed`, `--z`, `--p`, `--error`, `--confidence`, `--duplicate-policy` e opções de decisão metodológica. Consulte `sample --help`.

## Esquemas e chaves

Os nomes reais de colunas são mapeados em `schemas.issues`, `schemas.repositories` e `schemas.pilot`. A configuração distribuída reflete os arquivos reais fornecidos: metadados somente provider, nome de repositório derivado de `html_url`, categoria final `repository_category` e piloto identificado também por `issue_id`.

| Papel | Campos internos necessários | Exemplo de colunas |
|---|---|---|
| Issues/PRs | repository, number, artifact_type e campos da junção | repository, owner, issue_number, type, data_source |
| Repositórios reais | repository, owner, category; origem declarada pelo escopo provider | html_url, organization, repository_category |
| Piloto real | campos de pilot_fields | repository_full_name, issue_number, type, issue_id |

`repository` deve representar `owner/name`. Nomes curtos exigem uma coluna `owner` explícita. Não são feitas buscas pelo nome curto. `repository_id` pode integrar a junção quando existir nos dois arquivos. Todo campo listado no esquema deve existir; remova mapeamentos opcionais que não existam, em vez de criar dados fictícios.

A junção padrão usa **(repository completo, source)**. No arquivo real, `repository_scope: "provider"` declara que as 381 linhas são metadados provider, e `repository_formats.repositories: "github_url"` define a extração técnica de owner/name da URL, sem acessar a internet. Registros community são identificados pelo seu `data_source` e seguem diretamente para Community, inclusive quando o mesmo repositório também aparece entre os providers. A origem nunca é inferida pela categoria. Outras chaves consistentes podem ser declaradas em `join_fields`; chaves repetidas nos metadados são rejeitadas. Para outros corpora com metadados de ambas as origens, use `repository_scope: "all"` e mapeie `source` no arquivo de repositórios. Nesse modo a origem pode vir exclusivamente dos metadados, com uma junção que não dependa dela.

A identidade lógica padrão da biblioteca é **(repository completo, número, tipo)**. A configuração real acrescenta `record_id` (coluna `issue_id`) à identidade e à chave do piloto, verificando conjuntamente os quatro campos. O piloto usa `pilot_fields`, subconjunto da identidade que deve incluir repository e number. Para outro arquivo de piloto com apenas os cinco campos do classificador, configure uma chave parcial explicitamente; ela só é aceita se resolver uma única identidade lógica. Um número de issue isolado nunca é aceito.

Somente as chaves derivadas passam por `strip`, caixa uniforme para repositórios/origens/tipos e conversão de identificadores como `001.0` para `1`. As colunas originais, espaços, Unicode, quebras de linha, campos vazios e demais textos são preservados. Consulte [contratos de dados](docs/esquemas.md).

## Preparar e revisar

```bash
python -m web3blockset_sampling prepare --config configs/sampling.json
python -m web3blockset_sampling sample --config configs/sampling.json --dry-run
```

Os dois comandos verificam dados, junção, agrupamento, exclusões e alocação **sem executar o sorteio**. Gravam relatórios provisórios e listam bloqueios. Código de saída `2` significa inconsistência ou decisão pendente; a localização dos relatórios aparece no JSON da CLI. Uma falha estrutural, como chave ambígua nos metadados, produz um diagnóstico e manifesto bloqueado, sem tabelas de alocação que não puderam ser calculadas.

Os anexos descritivos da auditoria real, incluindo comparação de ocorrências repetidas e inconsistências cronológicas, podem ser reproduzidos separadamente. O script confere os hashes e não altera a elegibilidade nem chama o sorteio:

```bash
PYTHONPATH=src python3 scripts/audit_corpus_details.py \
  --run-dir outputs/IDENTIFICADOR_DA_PREPARACAO \
  --output-dir outputs/reports/NOVO_DIRETORIO_DE_ANEXOS
```

O piloto é excluído antes de calcular `Nₕ`. O relatório diferencia chaves encontradas, identidades lógicas, linhas removidas, chaves inexistentes e ambiguidades. Chaves de exclusão inexistentes, ambíguas ou repetidas sempre bloqueiam. Uma divergência de quantidade exige uma decisão textual em `exclusion_decision`; mudar `expected_pilot` dos 200 casos também exige essa justificativa.

Existem nove estratos definidos, incluindo os que tiverem população zero. Um estrato vazio tem `nₕ=0`, peso populacional zero e peso de expansão indefinido (célula vazia). Não é criada uma décima categoria para registros desconhecidos.

### Duplicidades e corpus

O padrão `duplicate_policy: "error"` audita e bloqueia identidades lógicas repetidas. Não descarta nem funde linhas.

Se os pesquisadores definirem que a unidade do universo original é a **ocorrência de linha**, podem declarar `duplicate_policy: "preserve_rows"` e preencher `duplicate_decision`. Nesse caso cada ocorrência possui ID próprio, inclusive linhas idênticas; nenhuma é removida. Os pesos passam a estimar proporções de ocorrências, e um mesmo artefato lógico pode aparecer em mais de uma ocorrência. O piloto exclui todas as ocorrências correspondentes. A decisão tem consequências para a interpretação e precisa ser documentada pelos pesquisadores.

O suporte genérico a versões alternativas exige outro `corpus_version`, `corpus_decision` e suas próprias `expected_counts`. Essa alternativa **não será utilizada nesta pesquisa**, cuja decisão é manter o corpus original. A aplicação não produz um corpus canonicalizado.

A extração técnica descrita abaixo não exclui suas ocorrências de uma seleção futura. A funcionalidade preexistente de exclusão opcional não é ativada pela extração. O smoke test não é excluído por padrão. Para excluí-lo, forneça `smoke`, seu esquema se necessário e `smoke_decision`. A sobreposição com o piloto é registrada sem contar a mesma remoção duas vezes.

### Aprovação humana do agrupamento

Depois de os pesquisadores revisarem o mapeamento e os relatórios, **o pesquisador responsável** registra sua aprovação:

```bash
python -m web3blockset_sampling approve-mapping --mapping configs/strata.json \
  --output data/reference/mapping_approval.json --reviewer 'Nome do pesquisador'
```

O comando não avalia o mérito metodológico: registra a declaração de aprovação, o responsável, a data UTC e o SHA-256 do arquivo. Informe `"approval": "../data/reference/mapping_approval.json"` na configuração ou use `--approval`. Qualquer alteração de bytes no mapeamento invalida essa aprovação. Arquivos de aprovação existentes não são sobrescritos. Não há aprovação real incluída neste projeto; as aprovações dos testes são exclusivamente sintéticas.

## Smoke test de integração com 15 ocorrências

```bash
PYTHONPATH=src python3 -m web3blockset_sampling smoke \
  --config configs/sampling.json --size 15 --seed 20261102 \
  --run-id smoke_15_commits_normalized_v2 --authorize-technical-smoke

PYTHONPATH=src python3 -m web3blockset_sampling validate \
  --run-dir outputs/smoke_tests/smoke_15_commits_normalized_v2
```

A seleção intencional inclui os nove estratos, Issues e PRs e um par real provider/community com a mesma identidade lógica e IDs de ocorrência distintos. As execuções reais smoke_15_integration_v1 e smoke_15_integration_v1_replay geraram os mesmos 15 IDs e o mesmo pipeline. No corpus elegível não há commits_count vazio; essa limitação está registrada, sem fabricar valores. Amplia a cobertura de commits, textos, estados e indícios lexicais sem classificar registros. A autorização explícita vale somente para a extração técnica: preserva os bloqueios metodológicos do sorteio definitivo e não concede aprovação humana.

A regeneração `smoke_15_commits_normalized_v2` preservou os mesmos 15 IDs e sua ordem: 15 representações decimais convertidas, cinco zeros preservados e nenhum ausente ou inválido. Os completos mantêm os valores originais; os diretórios anteriores foram preservados. Para outra execução, use um novo `--run-id` ou omita o argumento. As [evidências de normalização](docs/validacao.md) registram os testes, a comparação e os hashes.

O classificador recebe **smoke_15_pipeline.csv**, com exatamente 13 colunas e 15 linhas de dados. Completo, metadados, manifesto e relatório ficam juntos em um diretório exclusivo. Os campos estatísticos inaplicáveis permanecem vazios; esse conjunto não admite inferências populacionais. As 15 ocorrências continuam elegíveis para a seleção definitiva. Veja o [guia do smoke test](docs/smoke_integracao.md) para critérios, reprodução, limitações e significado dos campos. A validação efetiva de Stage 1 e Stage 2 ocorrerá no classificador independente.

## Sorteio definitivo

```bash
python -m web3blockset_sampling sample --config configs/sampling.json \
  --approval data/reference/mapping_approval.json --seed 42
```

Somente uma preparação sem bloqueios permite o sorteio. Cada estrato recebe amostragem aleatória simples sem reposição, com IDs ordenados e um gerador independente derivado de SHA-256 da semente e do nome do estrato. Não há cotas por repositório, por tipo de artefato nem ajustes para obter 3.410 registros. Detalhes estão em [metodologia](docs/metodologia.md).

As fórmulas são:

```text
n₀ = z² × p × (1−p) / e²
nₕ = min(Nₕ, ceil(n₀ / (1 + (n₀−1)/Nₕ)))
Wₕ = Nₕ / N
design_weightₕ = Nₕ / nₕ
provider_weightₕ = Nₕ / Σ Nₖ, para os oito estratos provider
```

Padrões: confiança 0,95, z=1,96, p=0,5, e=0,05. Confiança e z precisam ser consistentes, considerando o arredondamento publicado de z. O cálculo utiliza a população real após todas as exclusões.

## Resultados e integração

Cada execução cria um diretório novo, sem sobrescrever entradas ou resultados anteriores:

| Arquivo | Uso |
|---|---|
| final_sample_full.csv | Referência principal: todas as colunas originais + 14 metadados; 43 colunas no corpus atual |
| final_sample_pipeline.csv | Entrada do classificador: exatamente 13 colunas, com textos integrais e chave da ocorrência |
| final_sample_metadata.csv | Exatamente 14 metadados, incluindo pesos, proveniência e chave da ocorrência; sem textos |
| sampling_manifest.json | Status, hashes dos três CSVs, contrato de exportação, ambiente, código, corpus, decisões, semente e alocação |
| config_snapshot.json | Configuração efetiva com caminhos resolvidos |
| strata_summary.csv | População antes/depois, exclusões, nₕ, pesos, fração e repositórios distintos |
| repository_distribution.csv | Distribuição completa por repositório, na população e na amostra |
| duplicate_groups.csv | Todas as identidades repetidas, variantes de linha, origens, estratos e exclusões |
| exclusions_audit.csv | Resultado individual de cada chave do piloto e smoke, se configurado |
| validation_report.json | Diagnósticos, distribuições, exclusões e verificações |
| sampling_report.md | Relatório legível, com valores efetivamente calculados e limitações |

**Forneça somente `final_sample_pipeline.csv` ao classificador.** O cabeçalho segue esta ordem fixa:

```text
sampling_unit_id,repository,issue_number,artifact_type,repository_category,created_at,closed_at,state,comments_count,commits_count,issue_title,issue_body,concatenated_comments
```

`repository` usa o nome completo correto; `issue_number` mantém sua representação original, e `artifact_type` copia o valor original de `type`. Categoria, datas, estado, `comments_count` e textos são copiados integralmente, incluindo campos vazios. A projeção usa uma lista explícita de campos permitidos: novas colunas do corpus permanecem no arquivo completo e não entram automaticamente no pipeline.

**`commits_count` deve ser exportado como inteiro não negativo quando válido e como célula vazia quando ausente ou inválido.** Essa regra se aplica a `final_sample_pipeline.csv` e `smoke_15_pipeline.csv`: `0` e `0.0` → `0`; `5.0` → `5`. Zero é válido e nunca vira vazio. Frações como `2.5` não são arredondadas; negativos, infinitos e conteúdos não numéricos viram vazio. `None`, NaN, strings vazias, espaços e `null` são ausentes. A validação usa Decimal sem passar strings/inteiros por float, preservando números grandes. Nenhum campo é estimado pela quantidade de comentários.

Os arquivos completos conservam a representação original de `commits_count`. Manifestos e relatórios existentes registram `export_audit.commits_count`: válidos, inteiros preservados, representações decimais convertidas, zeros preservados, ausentes, inválidos e IDs/valores/motivos dos inválidos. Zeros são um subconjunto dos válidos. O contrato de exportação passa à versão 4, sem mudar cabeçalhos ou regras estatísticas. A validação compara `commits_count` do pipeline ao resultado da normalização do completo e recalcula a auditoria; as demais células continuam exigindo correspondência exata.

**O classificador não precisa receber os metadados estatísticos.** Eles são copiados do arquivo completo para `final_sample_metadata.csv`, sem recalcular pesos, nesta ordem:

```text
sampling_unit_id,sampling_logical_id,sampling_repository,sampling_source,sampling_category,sampling_original_category,sampling_stratum,sampling_population,sampling_sample_size,sampling_population_weight,sampling_design_weight,sampling_provider_weight,sampling_inclusion_probability,sampling_run_id
```

Os três arquivos possuem uma linha por ocorrência selecionada, os mesmos IDs únicos e não vazios e a mesma quantidade de linhas. A junção dos resultados classificados com os metadados utiliza **exclusivamente `sampling_unit_id`**. Repository/número e identidade lógica podem se repetir; nenhuma ocorrência é consolidada ou sorteada novamente para evitar colisões.

O classificador externo inspecionado ainda usa repository/número como identidade e lê `type`. Sua integração real permanece pendente: deverá aceitar `artifact_type` e preservar `sampling_unit_id` em Stage 1, Stage 2, checkpoints, retomadas e resultados finais. Esse repositório externo não foi alterado. Os [contratos completos](docs/esquemas.md) e o [guia de integração com exemplo de junção](docs/integracao_classificador.md) detalham a adaptação necessária, sem mudar regras de classificação.

Proporções globais devem usar **Σ Wₕ p̂ₕ**, e comparações internas de provider devem usar `sampling_provider_weight`. Contagens brutas da amostra não representam proporções do corpus. `Wₕ` e `Nₕ/nₕ` são pesos diferentes.

## Validar e reproduzir

```bash
python -m web3blockset_sampling validate --run-dir outputs/IDENTIFICADOR_DA_EXECUCAO
python -m web3blockset_sampling sample \
  --config outputs/IDENTIFICADOR_DA_EXECUCAO/config_snapshot.json
```

`validate` exige status `complete`, verifica hashes das entradas e saídas, recria a população e as exclusões, recalcula alocações e pesos, repete o sorteio e compara cada campo original exportado com sua impressão digital. Exige os três CSVs, os cabeçalhos exatos e a correspondência de todas as chaves e células, detectando perdas, multiplicações, textos alterados e metadados divergentes. Também reconstrói os relatórios para detectar inconsistências. Não modifica a execução validada. Uma nova execução terá outro ID e data, mas os mesmos IDs selecionados quando arquivos, configuração, código e ambiente forem iguais.

Guarde os arquivos originais, os relatórios, o código de mesma versão/impressão digital e a mesma versão major.minor do Python. O PRNG utilizado pertence à biblioteca padrão; mudanças de implementação exigem uma nova versão do algoritmo e validação específica. Hashes detectam alterações, mas não fornecem assinatura digital ou prova da proveniência científica do corpus.

Considere definitiva apenas uma execução cujo `sampling_manifest.json` tenha `status: "complete"`. Uma execução bloqueada pode conter artefatos parciais após uma falha de I/O ou validação; esses arquivos não devem ser utilizados como amostra final.

## Testes

```bash
python -m pytest -q
```

A suíte usa universos sintéticos e cobre as 33 categorias, nove estratos, junções, origens conflitantes, identificadores, exclusões, duplicidades, Cochran, arredondamento, pesos, determinismo, ordem física, conteúdo textual, CLI, histórico, aprovação e validação independente de adulterações. Inclui um fluxo completo de preparação → exclusão → alocação → sorteio → três exportações → validação, além de junção simulada com resultados de classificação por ocorrência. Consulte o [resultado atual dos testes](docs/validacao.md).

## Limitações metodológicas

A margem de ±5% por estrato é o erro amostral da proporção de registros que discutem pelo menos um pattern. Ela não mede erro da LLM, precisão individual de cada pattern, precisão de tempos de resolução ou poder para diferenças pequenas. A aplicação não utiliza ±2,1% como uma constante global e não calcula essa margem. Sensibilidade, especificidade, Rogan–Gladen e validação humana ficam fora deste repositório.

Concentração por repositório e distribuição de issues/PRs são reportadas como ameaças à validade; não modificam os nove estratos nem o sorteio. A unidade de ocorrência, se aprovada, pode repetir artefatos lógicos e precisa ser considerada nas análises posteriores.
