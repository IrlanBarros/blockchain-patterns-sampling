# Smoke test técnico de integração com 15 ocorrências

A versão 1.2.0 acrescenta uma extração intencional para testar o contrato com o classificador independente, que possui somente **Stage 1 e Stage 2**. O arquivo fornecido ao classificador é **smoke_15_pipeline.csv**. Este projeto não executa classificação nem chamadas a APIs de LLM.

> Este conjunto de 15 registros foi selecionado para validação técnica de integração e cobertura de cenários. Não constitui uma amostra probabilística representativa do corpus e não deve ser utilizado para inferências populacionais.

Não usar para frequências de padrões, precisão/recall populacionais ou resultados definitivos de RQ1, RQ2 e RQ3. Termos lexicais não são rótulos de relevância nem comprovam que Stage 2 será executado. A validação efetiva das duas etapas, checkpoints, retomadas e resultados ocorrerá no projeto de classificação.

## Executar e validar

Com o pacote instalado, executar:

```bash
python -m web3blockset_sampling smoke \
  --config configs/sampling.json \
  --size 15 \
  --seed 20261102 \
  --run-id smoke_15_commits_normalized_v2 \
  --authorize-technical-smoke

python -m web3blockset_sampling validate \
  --run-dir outputs/smoke_tests/smoke_15_commits_normalized_v2
```

Sem instalação, usar `PYTHONPATH=src python3 -m web3blockset_sampling` nos mesmos comandos. `--output /caminho/raiz` substitui a raiz de saídas; o diretório criado será `/caminho/raiz/smoke_tests/<run-id>`. Caminhos da configuração continuam relativos ao JSON; o argumento da CLI é relativo ao diretório de execução. Omitir `--run-id` gera um identificador com horário UTC e UUID. Reutilizar um diretório existente falha, sem sobrescrever arquivos. Esta versão aceita somente `--size 15`; tamanhos diferentes exigem um contrato de cobertura próprio e falham com diagnóstico.

`validate` é a interface existente, ampliada para detectar o manifesto do smoke. Não há um segundo comando redundante de validação. O código de saída é zero para sucesso e 2 para erro/bloqueio. Uma extração inviável conserva `smoke_15_manifest.json` com status blocked e o diagnóstico; somente status complete é aceito na validação. Artefatos de uma execução bloqueada não devem ser enviados ao classificador.

## Autorização limitada e pendências

`--authorize-technical-smoke` é obrigatório e autoriza exclusivamente essa extração técnica. O comando reutiliza `prepare` com a configuração original, sem trocar duplicate_policy, identidade, semente do sorteio definitivo ou qualquer decisão metodológica. A preparação já conserva as ocorrências mesmo quando duplicate_policy=error; seus IDs existentes são mantidos integralmente, inclusive o sufixo da ocorrência.

Só podem permanecer como pendências autorizadas os bloqueios conhecidos de aprovação do agrupamento e formalização da unidade frente a identidades repetidas. Eles aparecem literalmente no manifesto e no relatório. Nenhuma aprovação humana é criada. Inconsistências de contagem, esquema, junção, exclusão, mapeamento ou integridade continuam bloqueando a extração. Uma configuração com exclusão adicional `smoke` é rejeitada neste modo; ele exige a população preparada com somente a exclusão do piloto.

Não se chama `draw`, não se exportam arquivos final_sample_*, não se alteram datasets nem a configuração definitiva. As 15 ocorrências continuam elegíveis para a seleção futura. Os cálculos definitivos são apenas recalculados pelos componentes existentes para verificar a preparação e registrar o planejamento inalterado, sem atribuí-lo ao smoke.

## Algoritmo intentional-coverage-v1

1. `prepare` identifica as ocorrências, faz a junção, estratifica e exclui o piloto usando os mecanismos existentes.
2. A recuperação por hash da linha e número de ocorrência faz uma passagem de leitura. Cada ocorrência recebe indicadores de cobertura a partir da projeção bruta dos aliases, antes da normalização de exportação, sem inferir tipo pelo título.
3. Os grupos de sampling_logical_id produzidos pela preparação identificam pares reais provider/community, com IDs distintos e ambos elegíveis. Todas as ocorrências desses grupos permanecem candidatas. A ausência de um par bloqueia o smoke.
4. Reserva-se um par, priorizando cobertura obrigatória, cobertura opcional, custo textual e desempate por semente.
5. A cada posição restante escolhe-se o maior ganho de cobertura obrigatória (estratos e tipos), depois de cenários opcionais, depois a contribuição para até três registros com indícios lexicais. Empates preferem menor excesso acima de 16.000 caracteres, seguido do hash SHA-256 de algoritmo/semente/ID.
6. A saída é ordenada lexicograficamente por sampling_unit_id. Selecionam-se exatamente 15 IDs distintos, sem reposição, verificando todos os requisitos obrigatórios.

São 11 indicadores obrigatórios: nove estratos, Issue e Pull Request. Reservar duas posições para o par e cobrir cada indicador ainda ausente requer no máximo 13 posições; com 15 ocorrências disponíveis, o procedimento não precisa relaxar cobertura obrigatória. Uma ocorrência atende a diversos indicadores simultaneamente e conta uma única vez.

A passagem retém no máximo 15 candidatos por assinatura equivalente (estrato, tipo e indicadores opcionais), além de todos os membros de identidades repetidas. Dentro de uma assinatura, retêm-se os melhores candidatos por custo textual e desempate. Candidatos equivalentes não oferecem ganho de cobertura diferente; nunca são necessárias mais de 15 unidades da mesma assinatura. A preparação permanece O(N) em memória, sem reter todos os textos do corpus.

Os critérios opcionais usam cobertura gulosa, sem alegação de ótimo global. Cada cenário registra quantos registros elegíveis o atendem, quantos foram escolhidos e, se ausente, se era indisponível ou não foi contemplado pela heurística nas 15 posições.

## Cenários técnicos

- commits_count vazio, zero numérico ou positivo: os critérios existentes usam Decimal sobre as células originais e permanecem inalterados. A normalização acontece somente depois da seleção, no exportador. Valores literais não numéricos não são convertidos em zero.
- Título, corpo e comentários presentes; corpo e comentários vazios. Espaços são considerados ausência para cobertura e permanecem intactos na exportação.
- Texto relativamente extenso: soma de título, corpo e comentários de pelo menos 8.000 caracteres. Há preferência por evitar excessos acima de 16.000 caracteres; não se trunca o conteúdo nem se promete um limite de tokens para a LLM.
- Estado open/closed e closed_at presente/ausente, a partir das células reais. Não se corrigem inconsistências cronológicas nem se aplica filtro temporal.
- Indícios lexicais superficiais, com limites de palavra e sem distinção de caixa: proxy, oracle, access control, state machine, factory, circuit breaker, commit reveal, commit-reveal, multisig, multi-signature, upgradeability, off-chain, on-chain, escrow, time lock, timelock. A lista efetiva é versionada no código e registrada no manifesto. Ela serve exclusivamente para priorizar entradas; não altera o catálogo do classificador nem implementa classificação.

## Artefatos e pesos inaplicáveis

Cada execução produz:

| Arquivo | Conteúdo |
|---|---|
| smoke_15_full.csv | Todas as células originais + 14 metadados, incluindo sampling_run_id do smoke |
| smoke_15_pipeline.csv | Exatamente as 13 colunas do contrato, na ordem existente; entrada do classificador |
| smoke_15_metadata.csv | Exatamente os 14 metadados; uma linha por ocorrência |
| smoke_15_manifest.json | Configuração, entradas e hashes, implementação, seleção, critérios, par, cobertura, pendências e validações |
| smoke_15_selection_report.md | Justificativa por ocorrência, distribuições, matriz de cobertura, limitações e advertência metodológica |
| smoke_15_validation.json | Resultado das verificações automáticas |
| config_snapshot.json | Configuração original efetiva, sem alterar parâmetros definitivos |

Nos três CSVs, a ordem e os 15 sampling_unit_id são idênticos. O completo reutiliza a recuperação de células do exportador definitivo; pipeline e metadados reutilizam suas projeções. Aspas e terminadores de linha podem ser serializados novamente, mas cada célula original, inclusive commits_count, datas, textos, espaços, Unicode e vazios, é preservada no completo. O pipeline mantém datas e textos e normaliza somente commits_count.

Os seguintes campos permanecem **células CSV vazias**, significando inaplicabilidade: sampling_sample_size, sampling_design_weight, sampling_provider_weight e sampling_inclusion_probability. Não se calcula n_h=quota de smoke, probabilidade de inclusão ou peso de expansão. sampling_population mantém o tamanho real do estrato elegível; sampling_population_weight mantém sua proporção descritiva no corpus elegível. Esses dois valores não autorizam inferência com o smoke.

## Reprodução e validação de integridade

Preservar os mesmos datasets, configuração, código, versão major.minor de Python e semente. O manifesto registra o hash da implementação instalada, as entradas com seus caminhos/hashes, as escolhas, as 33 categorias/nove estratos via hash do mapeamento e o planejamento definitivo recalculado. Os hashes de saídas cobrem todos os artefatos exceto o próprio manifesto, evitando autorreferência.

`validate` confere os hashes, reconstrói a população, reexecuta a seleção, recupera as ocorrências originais e compara todas as células dos três CSVs, inclusive metadados, ordem e campos estatísticos vazios. Para commits_count no pipeline exige exatamente o resultado de normalize_commits_count aplicado à célula original, sem exigir igualdade textual com o completo. Recalcula também export_audit, incluindo os IDs inválidos. Reconstrói também as evidências do manifesto e os dois relatórios. Alterar um CSV e atualizar seu checksum não contorna essa comparação.

Para duas execuções independentes, usar outro run-id e repetir o comando com a mesma configuração/semente. Os IDs devem coincidir na mesma ordem e os pipelines devem ter hashes idênticos. Nos completos e metadados, ignorar somente sampling_run_id para comparar as células; no manifesto, horários e IDs de execução são legitimamente diferentes. Essa comparação é coberta nos testes automatizados e deve ser registrada na execução com o corpus real.

## Primeira extração com o corpus real

A extração smoke_15_integration_v1 usou semente 20261102, os 391.596 registros originais e os 200 casos excluídos do piloto, resultando na população elegível de 391.396. Foram selecionadas 15 ocorrências: 5 Issues e 10 PRs; 14 provider e 1 community. Os nove estratos estão cobertos, incluindo o par provider/community de fuellabs/fuels-ts#3347 com os IDs originais distintos.

O relatório registra commits_count zero em 5 ocorrências, positivo em 10 e vazio em nenhuma. A passagem completa encontrou **zero valores vazios de commits_count na população elegível**, portanto esse cenário é indisponível no corpus real e não foi fabricado. Sua preservação continua coberta pelos testes sintéticos. Há corpo vazio (2), comentários vazios (6), texto extenso (3), estado aberto (1), fechado (14), closed_at vazio (1) e preenchido (14), além de indícios lexicais (3 ocorrências, incluindo as duas do par).

Os textos somam 52.122 caracteres; o maior registro tem 14.693 caracteres. Nenhum texto foi truncado. O planejamento definitivo permanece em 3.408 registros sem execução do sorteio. A aprovação do mapeamento e a formalização da unidade frente às 175 identidades repetidas continuam pendentes no manifesto.

A segunda extração independente, smoke_15_integration_v1_replay, reproduziu os mesmos IDs e a mesma ordem. O pipeline teve conteúdo e hash idênticos; o completo e os metadados coincidiram após ignorar somente sampling_run_id. A evidência comparativa está em [smoke_15_real_reproducibility.json](../outputs/reports/smoke_15_real_reproducibility.json). A referência de integridade preserva os hashes de 52 arquivos anteriores à implementação em [smoke_15_protected_integrity.json](../outputs/reports/smoke_15_protected_integrity.json).

## Exportação normalizada — versão 1.2.1

**`commits_count` deve ser exportado como inteiro não negativo quando válido e como célula vazia quando ausente ou inválido.** Zero é válido: `0.0` → `0`; `5.0` → `5`. Valores fracionários não são arredondados. Ausências (`None`, NaN, vazio, espaços, `null`) e inválidos (texto não numérico, negativos, frações e infinitos) resultam em células vazias, distinguíveis na auditoria. `comments_count` e todos os textos mantêm o comportamento anterior.

Os completos preservam os valores originais. Manifesto e relatório de validação registram `export_audit.commits_count`, com inteiros preservados, decimais convertidos, zeros preservados, ausentes, inválidos e IDs/valores/motivos dos inválidos; o relatório de seleção contém o resumo legível. A transformação não participa do cálculo dos critérios de seleção nem altera a semente.

A regeneração `smoke_15_commits_normalized_v2` usa o snapshot de `smoke_15_integration_v1` e sua semente 20261102, em um novo diretório. Os artefatos v1 e replay são históricos e não são reescritos; sua validação exige a implementação antiga registrada. A comparação entre versões ignora somente sampling_run_id nos completos e metadados, pois a nova execução precisa de proveniência própria. No pipeline, somente commits_count pode diferir. Veja [validação](validacao.md) para as evidências da regeneração.
