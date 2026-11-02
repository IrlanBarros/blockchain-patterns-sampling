# Evidências de validação da implementação

Ambiente utilizado: Python 3.13.5, pytest 8.3.3, setuptools 80.9.0.

## Normalização de commits_count — versão 1.2.1

```bash
python -m pytest -q --junitxml=outputs/reports/commits_count_normalization_final_tests.xml
python -m compileall -q src tests scripts
git diff --check
```

Resultado: **376 testes aprovados, 0 falhas**, em 11,47 segundos. A referência inicial desta tarefa tinha 284 testes aprovados. O [JUnit da normalização](../outputs/reports/commits_count_normalization_final_tests.xml) preserva os relatórios históricos. Compilação e verificação de whitespace passaram.

**`commits_count` deve ser exportado como inteiro não negativo quando válido e como célula vazia quando ausente ou inválido.** Zero é válido: `0`/`0.0` → `0`; `5.0` → `5`. Frações são rejeitadas sem arredondamento. Testes cobrem None/NaN/null/vazio/espaços, negativos, infinitos, texto inválido, booleanos, coleções, complexos, notação científica, inteiros além de 2^53, números de 5.001 dígitos e Decimal sob precisão/traps restritivos. Um float grande verifica a preservação do valor binário exato recebido, sem usar sua representação textual arredondada para calcular o inteiro.

As integrações verificam o exportador definitivo com dados sintéticos e o smoke: valores válidos/ausentes/inválidos, aliases de origem, 13 colunas na ordem, IDs, identidades lógicas repetidas, textos, comments_count, completos e metadados preservados. Manifestos e relatórios existentes registram export_audit.commits_count com totais, inteiros, decimais, zeros, ausentes, inválidos e IDs/valores/motivos dos inválidos. A adulteração da auditoria é rejeitada mesmo com checksums atualizados.

A validação exige o valor normalizado esperado para commits_count do pipeline; as outras colunas mantêm igualdade exata. Um teste impede qualquer chamada ao normalizador durante a seleção do smoke. Os módulos de ingestão, preparação, identidade, exclusão, estratificação, estatística, configuração e sorteio permanecem inalterados. As seções abaixo preservam os resultados e contratos históricos; a exportação atual usa contrato 4 e programa 1.2.1.

### Regeneração real com a mesma seleção

```bash
PYTHONPATH=src python -m web3blockset_sampling smoke \
  --config outputs/smoke_tests/smoke_15_integration_v1/config_snapshot.json \
  --size 15 --seed 20261102 --run-id smoke_15_commits_normalized_v2 \
  --authorize-technical-smoke
PYTHONPATH=src python -m web3blockset_sampling validate \
  --run-dir outputs/smoke_tests/smoke_15_commits_normalized_v2
```

A execução [smoke_15_commits_normalized_v2](../outputs/smoke_tests/smoke_15_commits_normalized_v2/smoke_15_manifest.json) completou as **40 verificações internas**. Auditou **15 válidos, 0 inteiros já representados sem decimal, 15 representações decimais convertidas, 5 zeros preservados, 0 ausentes e 0 inválidos**. O conjunto real não contém ausentes ou inválidos; esses casos estão cobertos pelos testes sintéticos. Os valores do pipeline são `0,4,0,3,2,2,3,2,0,8,1,0,0,12,10`; no completo permanecem as representações originais com `.0`.

A [comparação estruturada](../outputs/reports/commits_count_normalization_regeneration.json) aprovou **18 verificações** contra v1 e v1_replay: 15 IDs iguais e na mesma ordem, nove estratos, par real de identidade lógica repetida, textos e demais células do pipeline idênticos, completos e metadados iguais exceto o novo sampling_run_id, mesma configuração/semente, seleção/cobertura/população/planejamento idênticos. Os hashes anteriores e os datasets originais foram preservados. O planejamento continua em 3.408, sem sorteio definitivo.

A [revalidação independente completa](../outputs/reports/commits_count_normalization_smoke_validation.json) reconstruiu a população, repetiu a seleção, recuperou as células originais, recalculou manifesto/relatórios/auditoria e verificou os hashes: **42 verificações aprovadas**. O [relatório final desta tarefa](../outputs/reports/commits_count_normalization_implementation_report.md) reúne diagnóstico, arquivos alterados e entrega.

SHA-256 do novo pipeline: `979e5dcc389546107bb31099d4f24b7cfb2028ad2f34e044e9878be73c581d0c`. Os hashes atualizados dos demais artefatos estão no manifesto. A auditoria dos inválidos é mantida mesmo quando seu total é zero. A comparação também comprova que os métodos de metadados estatísticos estão idênticos e que a única alteração em smoke_selection troca o nome da função de projeção bruta.

## Inclusão de commits_count — versão 1.1.1

```bash
python3 -m pytest -q --junitxml=outputs/reports/commits_count_tests.xml
python3 -m compileall -q src tests
```

Resultado: **209 testes aprovados, 0 falhas**, em 4,97 segundos; compilação sem erros. O [JUnit deste ajuste](../outputs/reports/commits_count_tests.xml) preserva os relatórios anteriores. O contrato de exportação 3 exige exatamente 13 colunas, com `commits_count` entre `comments_count` e `issue_title`, copiado diretamente da célula original. Os testes verificam valores preenchidos, vazio, zero, zeros à esquerda/representação decimal, espaços e detecção de adulteração mesmo com checksum atualizado. As verificações existentes continuam cobrindo o completo, os 14 metadados, IDs e pesos.

O ajuste preserva o exportador genérico e os módulos de preparação, exclusões, identidade, estratificação, estatística e sorteio. Os hashes desses módulos, dos três CSVs reais, do mapeamento e do DOCX foram conferidos contra a referência anterior ao ajuste. A configuração altera somente a projeção e sua descrição. O cabeçalho real contém `commits_count`; não há cálculo ou preenchimento de ausências. Não foi executado sorteio definitivo.

## Refatoração dos contratos de exportação — versão 1.1.0

```bash
python3 -m pytest -q --junitxml=outputs/reports/export_refactor_tests.xml
```

Resultado histórico desta etapa: **204 testes aprovados, 0 falhas**, em 4,32 segundos no ambiente local. O [JUnit da refatoração](../outputs/reports/export_refactor_tests.xml) é separado da evidência histórica da auditoria real. Toda seleção feita nos testes utiliza dados sintéticos; não houve sorteio definitivo do corpus real nem chamada ao classificador.

Além dos cenários existentes, os testes verificam os cabeçalhos exatos e ordenados de 12 campos do pipeline e 14 metadados; preservação de todas as colunas e células do completo, inclusive campos futuros; aliases de entrada configuráveis; IDs não vazios e únicos; contagens e conjuntos de chaves iguais nos três arquivos; textos, Unicode, espaços, aspas e quebras de linha; números e contagens com zeros/representação decimal; datas brutas e células vazias. Células CSV vazias permanecem vazias e strings como `NA`, `null` e `NaN` permanecem literais.

Provider, community, categorias vazias e pesos internos indefinidos estão cobertos. Casos com identidade lógica e repository/número repetidos verificam ocorrências distintas, com junção simulada de resultados reordenados exclusivamente por `sampling_unit_id`. Adulterações em conteúdo, pesos, chaves, quantidade, ordem de colunas ou manifesto são rejeitadas mesmo quando o checksum do CSV adulterado é atualizado. Um teste impede chamadas aos cálculos estatísticos durante a exportação, confirmando que os pesos separados são apenas copiados do completo.

O [relatório de integridade da refatoração](../outputs/reports/export_refactor_integrity.json) registra a comparação com uma referência salva antes das alterações:

- Os seis módulos `statistics`, `sampling`, `identity`, `stratification`, `exclusions` e `preparation` mantêm os mesmos SHA-256.
- As únicas diferenças na configuração real são `pipeline_columns`, `pipeline_key_fields` e `pipeline_decision`; semente, parâmetros, universo, política de ocorrências e exclusões permanecem iguais.
- Os três CSVs reais, o mapeamento e o DOCX mantêm os hashes anteriores.
- A alocação, todos os pesos e os 108 IDs de uma seleção sintética com semente 42 são idênticos aos da referência anterior. Essa seleção não usa o corpus real.
- Todas as origens de campos configuradas existem no cabeçalho real de 29 colunas; os contratos resultantes são completo com 43, pipeline com 12 e metadados com 14 colunas.
- Os artefatos da preparação real `20261102T134005Z-a23d68147b81` mantêm seus checksums; não há CSV de amostra real em `outputs`.

Também passaram `python3 -m compileall -q src tests scripts` e a construção do wheel `web3blockset_sampling-1.1.0-py3-none-any.whl`, sem dependências de execução. O wheel inclui o novo módulo de contratos e a referência JSON de categorias. Instalado em diretório temporário, fora do código-fonte, passou pela leitura da configuração real, conferência dos contratos 12/14, cálculo de Cochran e comando `--help`. Nenhum desses comandos sorteia registros reais.

O contrato informado pelo pesquisador é validado localmente. A integração real com o projeto externo permanece pendente: seu leitor ainda rejeita pares repository/número repetidos e lê `type`, e seus objetos/checkpoints precisam transportar a chave de ocorrência. O [guia de integração](integracao_classificador.md) especifica a adaptação em Stage 1, Stage 2, checkpoints, retomadas e resultados finais. Nenhum código desse outro projeto foi alterado e nenhuma regra de classificação foi modificada.

Arquivos da refatoração:

| Grupo | Arquivos alterados ou criados |
|---|---|
| Contratos e exportação | src/web3blockset_sampling/contracts.py (novo), export.py |
| Configuração e integração interna | src/web3blockset_sampling/config.py, validation.py, workflow.py, reports.py; configs/sampling.json |
| Versão do pacote | src/web3blockset_sampling/__init__.py; pyproject.toml |
| Testes | tests/test_export_contracts.py (novo), conftest.py, test_sampling_export_workflow.py |
| Documentação | README.md; docs/arquitetura.md, esquemas.md, integracao_classificador.md (novo), validacao.md, decisoes_metodologicas.md, diagnostico.md, auditoria_corpus_real.md |

## Suíte automatizada da auditoria 1.0.0

```bash
python3 -m pytest -q --junitxml=outputs/reports/audit_tests.xml
```

Resultado histórico da auditoria: **168 testes aprovados**. São testes locais, determinísticos e sem chamadas a LLMs, GitHub ou serviços externos. O resultado estruturado está preservado em `outputs/reports/audit_tests.xml`.

A cobertura funcional inclui:

- Todas as 33 categorias, cobertura/exclusividade do mapeamento, Other, Community e categorias ausentes/desconhecidas.
- Junção por nome completo ou ID, conflitos de nome/origem/categoria, metadados ambíguos e balanço de linhas.
- Mesmo número em repositórios ou tipos diferentes, identidades repetidas, repetições exatas e ocorrências entre origens.
- Exclusões completas/parciais do piloto, chaves ausentes/ambíguas/repetidas, distinção entre identidades e linhas, exclusão opcional do smoke test.
- Fórmula de Cochran, correção finita, ceil, limites de censo, populações vazias e pequenas, pesos globais/internos e de expansão.
- Sorteio reproduzível e sem reposição, ordem física independente, geradores independentes por estrato e quantidades exatas.
- Exportação de células originais, Unicode, aspas, espaços, CRLF interno, textos vazios e metadados desconhecidos.
- Aprovação vinculada a hash, histórico de execuções, dry-run e o ciclo completo da CLI.
- Validação de adulterações em textos, IDs, pesos, manifesto e relatórios, inclusive quando o checksum de uma saída alterada é atualizado.
- Fluxo completo e casos com estratos vazios ou população totalmente inválida, sem inventar alocações.
- Esquema real de metadados somente provider, URLs GitHub, separação de origens e 21 verificações técnicas da preparação.
- Garantia de que prepare/dry-run não chama o sorteio, inclusive quando não há bloqueios; relatórios por identidade repetida e por chave do piloto.
- Inspeção de datas sem filtro de período e bloqueio quando a implementação muda durante a execução.
- Anexo reproduzível que diferencia representação textual de instantes temporais e relata cronologia inconsistente sem remover registros.

O cenário principal possui 360 ocorrências sintéticas distribuídas pelos nove estratos e dois casos de piloto. Sua margem configurada é maior para permitir uma seleção não censitária em um universo pequeno; não representa a configuração metodológica do corpus real.

## Empacotamento e sintaxe da auditoria 1.0.0

```bash
python3 -m compileall -q src tests
python3 -m pip --no-cache-dir wheel --no-deps --no-build-isolation \
  --wheel-dir /tmp/web3blockset-sampling-wheels .
```

Foi gerado o wheel `web3blockset_sampling-1.0.0-py3-none-any.whl`, incluindo a referência JSON das categorias. O pacote não declara dependências de execução. A instalação e o carregamento foram verificados em um diretório temporário, incluindo o comando principal, o mapeamento e o cálculo estatístico.

## Dados reais

A auditoria integrada usou `data/raw/issues_prs.csv`, `data/raw/repositories.csv`, `data/raw/pilot-200.csv` e a referência `docs/Calculo_Amostragem_Final.docx`. Foi executado somente o comando prepare, sem sorteio. A distribuição exata e as evidências constam de [auditoria_corpus_real.md](auditoria_corpus_real.md).

Resultados: 391.596 linhas resolvidas, nenhum erro de relacionamento, 200 chaves do piloto encontradas sem ambiguidades, 200 linhas excluídas e 391.396 elegíveis. Foram aprovadas as 21 verificações técnicas de contagens, exclusões, fórmulas, pesos, imutabilidade das entradas e estabilidade da implementação. O planejamento calculado é de 3.408 casos.

A execução real continua com status blocked porque o código conserva os bloqueios de definição da unidade frente às 175 identidades repetidas e de aprovação humana do agrupamento. Isso não indica falha técnica no processamento. O código de saída 2 é esperado nesse estado. Não houve canonicalização, remoção de duplicidades, sorteio definitivo nem execução do classificador. Os testes não concedem aprovação metodológica aos pesquisadores.

Medição da preparação completa: 39,49 segundos; RSS máximo de 658.964 KiB (aproximadamente 643,5 MiB). Essa medição local inclui hashes e verificações e não cobre sorteio/exportação reais. A integração com a versão definitiva do classificador continua pendente.

## Smoke técnico de integração — versão 1.2.0

```bash
python3 -m pytest -q --junitxml=outputs/reports/smoke_15_tests.xml
python3 -m compileall -q src tests
```

Resultado: **284 testes aprovados, 0 falhas**, incluindo os **209 testes preexistentes** e **75 testes novos** em tests/test_smoke.py. O [JUnit](../outputs/reports/smoke_15_tests.xml) registra a execução completa. Os testes usam dados sintéticos e não executam LLMs ou serviços externos.

Os novos cenários verificam cobertura simultânea dos nove estratos, Issues/PRs, exatamente 15 IDs existentes e únicos, par real provider/community, exclusão de ambas as ocorrências quando sua chave está no piloto, critérios sobrepostos, semente e independência da ordem de iteração. Ausência de estrato, tipo ou par e quantidade inviável falham com diagnóstico; cenários opcionais ausentes são relatados sem inventar valores.

Os contratos de 13/14 colunas são verificados com preservação de textos, Unicode, aspas, CRLF, datas, vazios, literais null/NA/NaN e commits_count vazio/zero/positivo. Há comparação de duas execuções independentes por IDs, pipeline byte a byte e completo/metadados desconsiderando somente sampling_run_id. Pesos/probabilidades/tamanho amostral inaplicáveis permanecem vazios.

A revalidação reconstrói a preparação, seleção e relatórios e rejeita adulterações de conteúdo, metadados, par, cabeçalhos, quantidade, ordem, manifesto, hashes, relatório e entradas, inclusive com checksums de saída atualizados. São testados bloqueios técnicos não dispensáveis, autorização limitada, manutenção dos bloqueios definitivos, configuração imutável, ausência de chamada ao sorteio definitivo, política preserve_rows já configurada, recusa de sobrescrita e modificação de código/entrada durante a execução.

O defeito detectado durante a implementação foi a aceitação de run-id vazio como geração automática. Foi corrigido para gerar ID somente quando o argumento é omitido; IDs vazios ou com caminhos são rejeitados. A suíte original não foi alterada para acomodar a funcionalidade. O [guia do smoke](smoke_integracao.md) descreve a execução e o significado dos campos.

### Execuções reais e reprodução

Foram geradas duas extrações independentes com a configuração real, semente 20261102 e run-ids smoke_15_integration_v1 e smoke_15_integration_v1_replay. Ambas têm status complete e 39 verificações aprovadas. A comparação dos três CSVs confirmou os mesmos 15 IDs na mesma ordem e as mesmas células, desconsiderando somente sampling_run_id nos arquivos que o contêm. Os pipelines são idênticos byte a byte, com SHA-256 `0b31e068427c03d554c9591a50ff8d4cfb6f208cfb85733d0264ae784e837576`.

As evidências estão em [smoke_15_real_reproducibility.json](../outputs/reports/smoke_15_real_reproducibility.json) e [smoke_15_protected_integrity.json](../outputs/reports/smoke_15_protected_integrity.json). Os 52 arquivos protegidos conferidos contra a referência anterior à implementação, incluindo os três CSVs de entrada, a configuração, o mapeamento, o DOCX, os seis módulos metodológicos e os artefatos históricos, permaneceram inalterados.

O conjunto contém 5 Issues, 10 PRs, 14 provider, 1 community e todos os nove estratos; o par real é fuellabs/fuels-ts#3347. Há cinco zeros e dez valores positivos de commits_count. Não há commits_count vazio em nenhuma das 391.396 ocorrências elegíveis; essa limitação está explicitada no relatório, sem fabricar uma célula vazia. Os demais cenários opcionais foram atendidos. Nenhum sorteio definitivo ou execução de LLM foi realizado.

A revalidação pelo comando `validate` foi executada posteriormente sobre ambas as extrações reais: **41 verificações aprovadas em cada execução**, incluindo reconstrução independente da preparação/seleção, comparação das células originais, recálculo dos relatórios e hashes. Os resultados estão em [smoke_15_primary_validation.json](../outputs/reports/smoke_15_primary_validation.json) e [smoke_15_replay_validation.json](../outputs/reports/smoke_15_replay_validation.json). O [relatório técnico final](../outputs/reports/smoke_15_implementation_report.md) reúne arquitetura, comandos, distribuição, todos os IDs, cobertura, integridade, testes, artefatos e pendências.
