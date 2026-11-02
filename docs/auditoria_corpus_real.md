# Auditoria da arquitetura e validação com o corpus real

Data: 2 de novembro de 2026. Pesquisa: **An Empirical Study of the Adoption and Challenges of Blockchain Design Patterns in OSS Projects**.

Este relatório registra a auditoria histórica da versão **1.0.0**, cujos artefatos e checksums permanecem intactos. A refatoração posterior da versão 1.1.0 separa as exportações em completo, pipeline de 12 campos e metadados de 14 campos, com chave obrigatória `sampling_unit_id`; a revisão 1.1.1 acrescenta `commits_count`, totalizando 13 campos no pipeline. Essas alterações não repetem o sorteio real nem alteram estes resultados. O contrato atual e a adaptação externa pendente constam de [esquemas](esquemas.md), [integração do classificador](integracao_classificador.md) e [evidências da refatoração](validacao.md).

**Resultado:** a preparação e os cálculos estão tecnicamente validados com os arquivos reais. Foram preservadas as 391.596 ocorrências originais, removidos somente os 200 casos autorizados do piloto e calculado um planejamento de 3.408 casos sobre 391.396 linhas elegíveis. Nenhum registro real foi sorteado ou exportado como amostra.

O universo original foi decidido pelo pesquisador. A auditoria não utilizou o corpus canonicalizado de 391.421 e não reabriu essa escolha. O status blocked e o código de saída 2 refletem os bloqueios metodológicos ainda ativos, não uma falha de processamento.

## 1 Estado da arquitetura

Todos os componentes estão implementados e integrados pela CLI. As correções preservaram os módulos existentes e acrescentaram o suporte necessário ao esquema real e a rastreabilidade da preparação.

| Componente | Responsabilidade | Validação nesta etapa |
|---|---|---|
| config e ingestion | Caminhos, esquemas explícitos, CSV estrito em fluxo e checksums | Três CSVs reais; perfis completos e datas sem filtros |
| identity e preparation | URLs, nomes completos, chaves, junção e população compacta | 383.387 provider associados; 8.209 community encaminhados por origem |
| stratification | 33 categorias, oito estratos provider e Community | Cobertura integral e correspondência com o DOCX |
| exclusions | Identificação e exclusão antes de calcular N_h | 200 chaves inequívocas; 200 linhas excluídas |
| statistics | Cochran, correção finita, ceil e pesos | Contagens reais e verificações independentes sem sorteio |
| sampling | SRS sem reposição, semente e ordenação determinística | Testes sintéticos; não executado sobre o corpus real |
| export e validation | Textos completos, aliases e integridade das amostras | Testes sintéticos de ponta a ponta e adulteração; sem exportação real |
| reports e workflow | Histórico, manifesto, diagnósticos e relatórios | Execução real com 21 verificações técnicas aprovadas |

A primeira passagem retém unidades compactas e impressões digitais, sem manter o texto completo do universo em memória. A segunda passagem para recuperar textos é utilizada somente quando houver sorteio autorizado.

## 2 Arquivos inspecionados e esquemas

Os CSVs e o documento foram encontrados nos caminhos abaixo. Os hashes foram calculados antes do processamento e conferidos ao final; a referência DOCX foi lida integralmente, incluindo fórmulas e as duas tabelas. Nenhum original foi alterado.

| Arquivo | Dimensão ou papel | SHA-256 |
|---|---|---|
| `data/raw/issues_prs.csv` | 391.596 linhas; 29 colunas | `cd1b402f43068ac2d2141a3c1ff3784dfd1569ee6932ffa70866735e2953dead` |
| `data/raw/repositories.csv` | 381 linhas; 17 colunas | `de0362320ddc1d172a52af6ceacf35446ad7db7ed67ba25fdacc7ea214e60d27` |
| `data/raw/pilot-200.csv` | 200 linhas; 20 colunas | `6334ebbaf097a971aca63b9ea91d718ef6dd717d10ebbeaeae26fe12511e3136` |
| `docs/Calculo_Amostragem_Final.docx` | Referência metodológica de 29/10/2026 | `6169868c734c3c7adfa79931235095f875ebd1a1d98c0dffd9b740b330aceb5f` |

O CSV de issues contém repository, owner, issue_id, issue_number, type e data_source, além dos textos, estados, datas e demais metadados. Todos os campos são lidos como strings, preservando vazios, Unicode e quebras de linha; os perfis distinguem representações inteiras e datas ISO sem transformar as células.

O arquivo de repositórios tem 381 URLs únicas e 80 organizações. Usa-se html_url para extrair owner/name e organization para conferir o owner. A coluna # é um ordinal e não é usada como identidade. A categoria utilizada é repository_category; repository_category_claude não influencia a estratificação. Não há coluna source nem metadados community nesse arquivo, por isso o escopo provider é declarado explicitamente na configuração.

A identidade e a chave do piloto combinam **repository completo, issue_number, type e issue_id**. Normalizações técnicas derivadas incluem strip, casefold e representação inteira dos IDs; os campos originais permanecem inalterados. O identificador global está preenchido em todas as linhas e é consistente com a chave composta.

## 3 Integridade do universo e inconsistências observadas

| Origem | Registros originais | Issues | PRs | Depois do piloto |
|---|---|---|---|---|
| provider | 383.387 | 157.452 | 225.935 | 383.192 |
| community | 8.209 | 3.953 | 4.256 | 8.204 |
| Total | 391.596 | 161.405 | 230.191 | 391.396 |

A junção mantém o balanço **383.387 associados por chave provider + 8.209 community sem junção provider + 0 inválidos = 391.596**. Não houve correspondência ausente, multiplicação de linhas, conflito de origem/categoria ou registro sem estrato.

### Duplicidades auditadas e preservadas

Existem 391.421 identidades distintas, 175 grupos repetidos e 175 ocorrências adicionais. Em cada grupo há exatamente uma linha provider e uma community. Nenhuma linha inteira é idêntica a outra, embora os títulos, corpos, comentários e raw_text desses pares sejam iguais. As diferenças brutas aparecem em datas, data_source, owner_used e campos de palavras-chave. Não há conflitos de issue_id entre identidades distintas nem casos do mesmo repositório/número com tipos divergentes.

As 175 ocorrências adicionais permanecem elegíveis após excluir o piloto, pois nenhum desses grupos pertence ao piloto. O relatório duplicate_groups.csv permite conferir cada identidade, suas origens, estratos, variantes de linha e exclusões. A soma populacional e os pesos continuam calculados sobre **linhas originais**, não sobre um corpus canonicalizado.

A configuração conserva duplicate_policy=error para o futuro sorteio. A retenção do corpus já está decidida; falta formalizar a unidade de ocorrência e registrar a política preserve_rows e sua justificativa antes de habilitar uma execução definitiva. Essa formalização não deve eliminar ocorrências ou preferir provider a community.

### Período temporal divergente do documento

O DOCX descreve 2012–2024, mas created_at no corpus vai de **2011-09-20T03:02:33+00:00 a 2025-10-18T10:15:19+00:00**. São 3 registros de 2011 e 49.988 de 2025, totalizando 49.991 fora da descrição 2012–2024. Todos foram mantidos, conforme a decisão sobre o universo original. A descrição do período precisa ser corrigida ou esclarecida pelos autores; aplicar um filtro agora mudaria o universo autorizado.

Os campos de data preenchidos são ISO válidos e possuem timezone. Os resultados das verificações cronológicas e da coluna year estão no arquivo corpus_temporal_consistency_audit.json; eles não são usados como filtros.

- provider: closed_before_created=1; updated_before_created=1; closed_after_updated=9; state_closed_without_date=0; state_open_with_close_date=0; year_differs_from_created_year=0.
- community: closed_before_created=0; updated_before_created=0; closed_after_updated=0; state_closed_without_date=0; state_open_with_close_date=0; year_differs_from_created_year=0.

Uma ocorrência provider (issue_id 1437325733) tem fechamento e atualização anteriores à criação. Outras nove apresentam fechamento posterior a updated_at. São inconsistências presentes no original, preservadas e documentadas para definir o tratamento nas análises posteriores de tempo de resolução de RQ3; elas não foram usadas para excluir casos ou alterar probabilidades.

Comparando os instantes temporais dos pares de identidade repetida, os números de grupos com datas efetivamente diferentes são: created_at=0; updated_at=0; closed_at=0. Essa comparação não substitui nem regrava as representações originais.

### Ausências e representações técnicas

| Campo no corpus | Células vazias |
|---|---|
| issue_title | 4 |
| issue_body | 10.589 |
| concatenated_comments | 151.456 |
| closed_at | 29.984 |
| labels | 201.512 |
| repository_category | 7.669 |

Nenhum identificador, repository, owner, type ou data_source está vazio. Há 22 descrições e 26 linguagens vazias nos metadados, sem efeito nas chaves ou nos estratos. Textos ausentes são preservados; não houve criação de conteúdo, descarte por ausência de texto nem uso de resultados do classificador.

Todos os 7.669 valores vazios de categoria bruta são community. Outros 540 community têm uma categoria preenchida na linha original, mas permanecem Community pela origem explícita. Há 105 categorias provider com espaço final; somente o token derivado recebe strip para conferir a categoria dos metadados.

## 4 Distribuição exata dos nove estratos

As 33 categorias provider dos metadados foram contempladas uma única vez, sem categoria desconhecida, fallback para Outros ou atribuição arbitrária. Os oito totais de repositórios nos metadados correspondem aos 42, 73, 25, 71, 89, 19, 53 e 9 indicados no DOCX.

| Estrato | Repos nos metadados | Repos com registros elegíveis | Antes do piloto | Excluídos | N_h |
|---|---|---|---|---|---|
| Blockchain Core | 42 | 42 | 117.683 | 45 | 117.638 |
| SDKs e bibliotecas | 73 | 73 | 52.210 | 27 | 52.183 |
| Wallets e extensões | 25 | 25 | 59.446 | 27 | 59.419 |
| Ferramentas de desenvolvimento | 71 | 70 | 51.991 | 26 | 51.965 |
| Documentação, educação e especificações | 89 | 88 | 46.195 | 26 | 46.169 |
| Infraestrutura e dados | 19 | 19 | 20.767 | 28 | 20.739 |
| Contratos e aplicações on-chain | 53 | 53 | 17.532 | 11 | 17.521 |
| Outros | 9 | 9 | 17.563 | 5 | 17.558 |
| Community | não fornecidos | 3.697 | 8.209 | 5 | 8.204 |
| Total | 381 provider | 379 provider + 3.697 community | 391.596 | 200 | 391.396 |

Os metadados incluem dois providers sem registros no corpus: cryptofinlabs/audit-checklist e moralisweb3/moralis-analytics-js. Por isso há 379 repositórios provider representados, sem perda na junção. O número de repositórios da tabela é contado por estrato/origem; não é uma união global quando um repositório aparece nas duas origens.

A referência informa 4.500 repositórios community, enquanto 3.697 aparecem efetivamente nos registros fornecidos. Sem metadados community, não se pode verificar a cobertura dos 4.500 ou atribuir a diferença a uma causa específica. O relatório usa a contagem observada e mantém todos os 8.209 registros community originais.

### Cobertura das 33 categorias provider

| Categoria | Estrato | Repos nos metadados | Registros provider originais | Elegíveis |
|---|---|---|---|---|
| Blockchain Core / Protocol | Blockchain Core | 34 | 104.619 | 104.582 |
| Blockchain Core / Privacy Protocol | Blockchain Core | 8 | 13.064 | 13.056 |
| SDK / Library | SDKs e bibliotecas | 37 | 36.341 | 36.324 |
| Utility Library | SDKs e bibliotecas | 10 | 2.225 | 2.225 |
| Cryptography Library | SDKs e bibliotecas | 10 | 778 | 778 |
| ZK Library | SDKs e bibliotecas | 2 | 821 | 819 |
| UI / Frontend / Library | SDKs e bibliotecas | 14 | 12.045 | 12.037 |
| Wallet Dapp / Library / Browser | Wallets e extensões | 22 | 33.127 | 33.110 |
| Browser Extension | Wallets e extensões | 3 | 26.319 | 26.309 |
| Development Platform / Framework | Ferramentas de desenvolvimento | 19 | 23.977 | 23.966 |
| Testing Tool | Ferramentas de desenvolvimento | 9 | 3.070 | 3.068 |
| IDE / Development Environment | Ferramentas de desenvolvimento | 5 | 486 | 486 |
| Programming Language / Compiler | Ferramentas de desenvolvimento | 5 | 9.154 | 9.151 |
| Security Tool | Ferramentas de desenvolvimento | 10 | 13.572 | 13.565 |
| Analytics / Monitoring Tool | Ferramentas de desenvolvimento | 6 | 715 | 712 |
| Low-level Analysis Tool / Decoder | Ferramentas de desenvolvimento | 11 | 583 | 583 |
| Smart Contract Deployment Tool | Ferramentas de desenvolvimento | 4 | 265 | 265 |
| AI Tool | Ferramentas de desenvolvimento | 2 | 169 | 169 |
| Documentation | Documentação, educação e especificações | 24 | 7.721 | 7.719 |
| Education Resource / Boilerplate | Documentação, educação e especificações | 40 | 4.122 | 4.122 |
| Specification | Documentação, educação e especificações | 13 | 5.939 | 5.934 |
| Research | Documentação, educação e especificações | 4 | 456 | 456 |
| Metadata Repository | Documentação, educação e especificações | 8 | 27.957 | 27.938 |
| Storage Protocol | Infraestrutura e dados | 10 | 15.145 | 15.121 |
| Indexing Protocol / Tool | Infraestrutura e dados | 5 | 4.554 | 4.551 |
| Infrastructure | Infraestrutura e dados | 4 | 1.068 | 1.067 |
| Smart Contract Library | Contratos e aplicações on-chain | 25 | 12.066 | 12.058 |
| DeFi Protocol | Contratos e aplicações on-chain | 15 | 3.547 | 3.545 |
| NFT Protocol / Tool | Contratos e aplicações on-chain | 6 | 1.012 | 1.011 |
| Bridge Protocol | Contratos e aplicações on-chain | 2 | 138 | 138 |
| Staking Tool | Contratos e aplicações on-chain | 2 | 340 | 340 |
| Identity / Naming Protocol | Contratos e aplicações on-chain | 3 | 429 | 429 |
| Other | Outros | 9 | 17.563 | 17.558 |

## 5 Validação e exclusão do piloto

O arquivo contém 200 linhas e 200 chaves distintas. As 200 foram encontradas, correspondendo a 200 identidades e 200 linhas removidas. Há 0 chaves ausentes, 0 ambíguas e 0 repetidas no arquivo de piloto.

As exclusões somam 195 provider e 5 community e ocorrem antes de N_h. O conjunto elegível não contém nenhuma chave do piloto. O arquivo exclusions_audit.csv lista o resultado de cada uma das 200 chaves, com suas origens, estratos e quantidades. Não foi aplicada exclusão de smoke test.

## 6 Planejamento amostral e comparação com o DOCX

Parâmetros efetivos: confiança 95%, z=1,96, p=0,5 e e=0,05. n_0=384,16. Para cada estrato, n_h=min(N_h, ceil(n_0/[1+(n_0-1)/N_h])). Usa-se ceil, sem alocação proporcional, cotas por repositório ou ajustes para atingir o total previsto.

| Estrato | N_h aproximado no DOCX | N_h elegível real | n_h no DOCX | n_h calculado | Diferença |
|---|---|---|---|---|---|
| Blockchain Core | 121.100 | 117.638 | 383 | 383 | +0 |
| SDKs e bibliotecas | 53.600 | 52.183 | 382 | 382 | +0 |
| Wallets e extensões | 51.900 | 59.419 | 382 | 382 | +0 |
| Ferramentas de desenvolvimento | 50.000 | 51.965 | 382 | 382 | +0 |
| Documentação, educação e especificações | 48.100 | 46.169 | 382 | 381 | -1 |
| Infraestrutura e dados | 23.300 | 20.739 | 378 | 378 | +0 |
| Contratos e aplicações on-chain | 18.200 | 17.521 | 377 | 376 | -1 |
| Outros | 17.200 | 17.558 | 376 | 376 | +0 |
| Community | 8.209 | 8.204 | 368 | 368 | +0 |
| Total amostral | populações provider aproximadas | 391.396 | 3.410 | 3.408 | -2 |

A diferença está em Documentação, educação e especificações (381 em vez de 382) e Contratos e aplicações on-chain (376 em vez de 377). Os demais tamanhos permanecem iguais. As populações reais do arquivo diferem das aproximações do dashboard e já descontam o piloto; a aplicação recalcula a correção finita e arredonda para cima. Nenhum resultado foi reduzido ou aumentado manualmente.

## 7 Pesos estatísticos

W_h=N_h/391.396; design_weight=N_h/n_h; fração de inclusão=n_h/N_h. O peso interno provider divide N_h pelo total elegível provider de 383.192, e é indefinido para Community. Estes valores são de planejamento, não evidência de que alguma observação tenha sido selecionada.

| Estrato | n_h | W_h | design_weight | Fração de inclusão | Peso interno provider |
|---|---|---|---|---|---|
| Blockchain Core | 383 | 0,30056005 | 307,148825 | 0,00325575 | 0,30699493 |
| SDKs e bibliotecas | 382 | 0,13332533 | 136,604712 | 0,00732039 | 0,13617977 |
| Wallets e extensões | 382 | 0,15181300 | 155,547120 | 0,00642892 | 0,15506326 |
| Ferramentas de desenvolvimento | 382 | 0,13276835 | 136,034031 | 0,00735110 | 0,13561087 |
| Documentação, educação e especificações | 381 | 0,11795982 | 121,178478 | 0,00825229 | 0,12048529 |
| Infraestrutura e dados | 378 | 0,05298726 | 54,865079 | 0,01822653 | 0,05412169 |
| Contratos e aplicações on-chain | 376 | 0,04476540 | 46,598404 | 0,02145996 | 0,04572381 |
| Outros | 376 | 0,04485994 | 46,696809 | 0,02141474 | 0,04582037 |
| Community | 368 | 0,02096087 | 22,293478 | 0,04485617 | não aplicável |

A soma de W_h e a soma dos pesos internos provider são 1 dentro da tolerância numérica. A soma de n_h × design_weight recupera 391.396. Proporções globais devem usar Σ W_h × p_h, e a comparação provider/community usa os pesos internos provider. Contagens brutas da amostra não representam a distribuição do universo.

A margem de ±5% corresponde à proporção de registros que discutem ao menos um pattern. Não mede erro da LLM, precisão por pattern, tempos de resolução ou poder para diferenças pequenas. A margem global aproximada de ±2,1% não foi copiada como constante nem recalculada nesta aplicação. Validação humana e Rogan–Gladen continuam fora do escopo.

### Issues e PRs na população elegível

| Estrato | Issues | PRs |
|---|---|---|
| Blockchain Core | 45.115 | 72.523 |
| SDKs e bibliotecas | 25.311 | 26.872 |
| Wallets e extensões | 24.844 | 34.575 |
| Ferramentas de desenvolvimento | 27.254 | 24.711 |
| Documentação, educação e especificações | 11.055 | 35.114 |
| Infraestrutura e dados | 10.808 | 9.931 |
| Contratos e aplicações on-chain | 6.459 | 11.062 |
| Outros | 6.519 | 11.039 |
| Community | 3.951 | 4.253 |

A concentração por repositório está em repository_distribution.csv. O relatório automatizado registra os maiores repositórios e suas participações por estrato; não há cotas nem estratificação adicional por tipo de artefato.

## 8 Testes e verificações executadas

**168 testes aprovados, 0 falhas/erros.** A suíte inclui determinismo por semente, independência da ordem de leitura e entre estratos, ausência de reposição, pilotos, preservação dos textos, pesos, CLI, hashes e adulterações. Também valida o esquema provider-only, URLs, categorias desconhecidas em repositórios sem registros e bloqueio por alteração da implementação durante uma execução.

Um teste impede qualquer chamada a draw durante prepare/dry-run, mesmo quando a configuração sintética está aprovada. Testes de sorteio e exportação utilizaram somente dados sintéticos; não se executou uma amostragem real para testar a reprodutibilidade.

Comandos principais:

```bash
python3 -m pytest -q --junitxml=outputs/reports/audit_tests.xml
python3 -m compileall -q src tests
PYTHONPATH=src python3 -m web3blockset_sampling inspect --config configs/sampling.json
PYTHONPATH=src python3 -m web3blockset_sampling prepare --config configs/sampling.json
```

Os anexos descritivos podem ser reproduzidos com o script versionado, que confere os hashes do corpus, da configuração e do relatório de duplicidades, preservando todas as linhas:

```bash
PYTHONPATH=src python3 scripts/audit_corpus_details.py \
  --run-dir outputs/20261102T134005Z-a23d68147b81 \
  --output-dir outputs/reports/NOVO_DIRETORIO_DE_ANEXOS
```

As 21 verificações técnicas da execução real foram aprovadas:

- input_rows_accounted: aprovada.
- no_invalid_rows: aprovada.
- join_balance_preserved: aprovada.
- no_join_multiplication: aprovada.
- metadata_keys_unique: aprovada.
- unique_unit_ids: aprovada.
- exclusions_accounted: aprovada.
- eligible_population_has_no_pilot_or_smoke: aprovada.
- nine_expected_strata: aprovada.
- population_sum: aprovada.
- population_per_stratum: aprovada.
- weights_sum_to_one: aprovada.
- provider_weights_sum_to_one: aprovada.
- provider_weight_consistency: aprovada.
- community_stratum: aprovada.
- provider_mapping: aprovada.
- formula_consistency: aprovada.
- weight_consistency: aprovada.
- expansion_weights_recover_population: aprovada.
- inputs_unchanged: aprovada.
- implementation_unchanged: aprovada.

A preparação completa levou 39,49 segundos e atingiu RSS máximo de 658.964 KiB, aproximadamente 643,5 MiB, no ambiente desta auditoria. Inclui leitura, hashes e verificações; não inclui sorteio/exportação reais. Essas medidas não são uma garantia para outros ambientes.

## 9 Problemas encontrados e correções realizadas

1. A configuração apontava para outro nome/local de piloto e supunha metadados com repository, owner e source. Foi ajustada aos caminhos reais, html_url e organization, com escopo provider e conversão de URL explicitamente configurados.
2. A junção estrita para ambas as origens exigiria metadados community inexistentes. O escopo provider passou a encaminhar community por data_source, conforme a seção 7 do DOCX, sem inferir categorias ou alterar origens.
3. O contador de linhas associadas incluía community encaminhadas diretamente. Agora o relatório separa 383.387 junções provider, 8.209 encaminhamentos community e 0 inválidos, e verifica seu balanço.
4. Os pesos e invariantes só eram registrados após sorteio. Foi criado check_preparation, com validações independentes sem chamar o gerador aleatório; essas verificações estão integradas ao comando prepare.
5. A auditoria de duplicidades e do piloto era resumida em contagens. Foram acrescentados duplicate_groups.csv e exclusions_audit.csv com evidências individuais, além da comparação entre repositórios dos metadados e representados na população.
6. Categorias de repositórios sem registros não eram integralmente conferidas. Todo o índice de metadados agora passa pelo mapeamento, mesmo que não participe de uma linha do corpus.
7. A inspeção não mostrava o período efetivo e poderia deixar a descrição 2012–2024 sem contestação. Foram acrescentados perfis de datas, e a divergência foi documentada sem aplicar filtros.
8. O hash do código era registrado somente no fim. Agora ele é capturado antes do trabalho e comparado ao final, bloqueando uma execução cuja implementação tenha mudado durante o processamento.
9. A documentação ainda descrevia metadados e DOCX ausentes. README, esquemas, diagnóstico, validação e decisões foram atualizados para o estado real, sem modificar o documento original.

## 10 Prontidão técnica e pendências para o sorteio

**O sistema está tecnicamente preparado para realizar o sorteio depois dos registros metodológicos e da autorização da etapa definitiva.** A preparação real, a integridade, as exclusões, as fórmulas e os pesos estão validados; sorteio e exportação foram testados com dados sintéticos. Nenhum arquivo de amostra real foi criado.

- Formalizar a unidade como ocorrência original e registrar preserve_rows com a justificativa correspondente, mantendo todas as 391.596 linhas antes do piloto. Isso formaliza a retenção já decidida e não reabre a escolha de corpus.
- Obter a aprovação humana do agrupamento, exigida pelo DOCX, vinculada ao hash do mapeamento. A correspondência técnica com o documento não substitui essa aprovação.
- Corrigir ou esclarecer a descrição do período no texto metodológico e distinguir repositórios selecionados a montante dos efetivamente representados nos registros. O universo original permanece inalterado.
- Confirmar a versão e a chave aceitas pelo classificador. O leitor observado exige repository + issue_number únicos; se forem selecionadas as duas ocorrências de um artefato, é necessária uma adaptação explícita para sampling_unit_id ou outro contrato aprovado. Não se refaz o sorteio para contornar a colisão.
- Manter o smoke test sem exclusão adicional, conforme o procedimento atual. Qualquer mudança depende de decisão específica.

A solicitação desta etapa proíbe sorteio definitivo. Não foi criado arquivo de aprovação humana, não se usou saída de LLM e não se modificaram os CSVs ou o DOCX originais.

## Evidências e reprodução

Execução: `20261102T134005Z-a23d68147b81`; versão do programa: 1.0.0; Python: 3.13.5.

Hash da implementação: `2b4285f137ad41121a87ab1652a0b06c4701e9f0e0d30616a6a6f7e24d72d629`.
Hash do mapeamento: `fe6f7d86210686c971243568da3f6c9f1ed1b63429cadffdcf1701be677bf472`.

Artefatos desta execução, preservada com status blocked:

- [sampling_manifest.json](../outputs/20261102T134005Z-a23d68147b81/sampling_manifest.json).
- [config_snapshot.json](../outputs/20261102T134005Z-a23d68147b81/config_snapshot.json).
- [strata_summary.csv](../outputs/20261102T134005Z-a23d68147b81/strata_summary.csv).
- [validation_report.json](../outputs/20261102T134005Z-a23d68147b81/validation_report.json).
- [sampling_report.md](../outputs/20261102T134005Z-a23d68147b81/sampling_report.md).
- [duplicate_groups.csv](../outputs/20261102T134005Z-a23d68147b81/duplicate_groups.csv).
- [exclusions_audit.csv](../outputs/20261102T134005Z-a23d68147b81/exclusions_audit.csv).
- [repository_distribution.csv](../outputs/20261102T134005Z-a23d68147b81/repository_distribution.csv).

Arquivos complementares:

- [Perfis completos dos três CSVs](../outputs/reports/real_inputs_audit_profiles.json).
- [Auditoria adicional de categorias, tipos, ausências e pares repetidos](../outputs/reports/corpus-real-annex/corpus_additional_audit.json).
- [Consistência temporal](../outputs/reports/corpus-real-annex/corpus_temporal_consistency_audit.json).
- [Resultado estruturado dos testes](../outputs/reports/audit_tests.xml).
- [Medição local de recursos](../outputs/reports/real_audit_resources.txt).

Datasets e saídas estão ignorados pelo Git. Este relatório versionável resume os resultados reais; os artefatos locais permitem conferir cada número e reproduzir a preparação com a configuração efetiva e os mesmos hashes.
