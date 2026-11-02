# Arquitetura e fluxo de dados

O desenho separa operações de I/O das funções estatísticas e de sorteio, sem frameworks ou dependências em outro projeto.

1. `config` valida uma configuração JSON explícita. A referência das 33 categorias acompanha o pacote e é independente do arquivo de mapeamento editável.
2. `ingestion` lê CSV com parser estrito, strings e controle de codificação/delimitador. Não interpreta `NA`, datas ou números como valores ausentes. Linhas de largura inválida e cabeçalhos repetidos são erros.
3. `identity` constrói somente atributos derivados, sem sobrescrever as células brutas. Repositórios são nomes completos, identificadores inteiros são normalizados e tipos/origens usam dicionários explícitos.
4. `preparation` indexa metadados por uma chave única, faz uma junção muitos-para-um e retém objetos compactos `Unit`, não corpos/títulos/comentários. O escopo provider permite os 381 metadados reais e encaminha community pelo data_source, sem associação arbitrária. Audita identidades e repetições exatas por SHA-256 do conteúdo completo da linha. Linhas inválidas aparecem no balanço e bloqueiam o sorteio.
5. `exclusions` resolve o piloto contra as identidades, detecta ambiguidades e exclui unidades antes de qualquer alocação definitiva. Cada remoção permanece rastreável no relatório.
6. `statistics` calcula a alocação e os pesos a partir da população elegível; `sampling` recebe somente unidades, alocação e semente.
7. `export` recupera apenas os registros sorteados numa segunda passagem. Uma impressão digital e uma ocorrência por conteúdo relacionam cada linha à sua unidade; todos os textos ficam na memória somente para a pequena amostra final. O arquivo completo mantém todas as colunas originais + 14 metadados. `contracts` define a projeção permitida de 13 colunas do pipeline e a projeção de 14 metadados; ambas são obtidas dos mesmos registros completos, sem novo sorteio ou recálculo de pesos.
8. `validation.check_preparation` verifica balanço, exclusões, fórmulas e pesos sem sortear. As demais validações repetem invariantes do desenho, exigem cabeçalhos exatos nos três CSVs e verificam contagens, unicidade e igualdade das chaves `sampling_unit_id`. Comparam cada célula original, alias e metadado para detectar perda, multiplicação ou alteração de conteúdo; somente commits_count no pipeline é comparado ao resultado da normalização. `workflow.validate_run` também reconstrói relatórios e verifica entradas, saídas, configuração e implementação.
9. `reports` resume distribuições, concentração, categorias, tipos e decisões. `workflow` organiza diretórios únicos, configurações efetivas e o manifesto que marca uma execução concluída.

## Exportação e fronteira com o classificador

`final_sample_full.csv` é a referência de auditoria, com 43 colunas no corpus atual. `final_sample_pipeline.csv` contém exatamente os 13 campos autorizados para classificação, incluindo textos integrais, datas e a chave da ocorrência. `commits_count` passa por `normalization.normalize_commits_count` somente no pipeline: inteiro não negativo quando válido, vazio quando ausente ou inválido. Zero é preservado; `5.0` vira `5`; frações não são arredondadas. O completo conserva a representação original. `final_sample_metadata.csv` contém exatamente os 14 metadados do completo. Novas colunas originais entram somente no completo, sem ampliar as projeções.

Os três arquivos compartilham `sampling_unit_id` como chave única. Repository/número e identidade lógica podem se repetir sem remover ou consolidar ocorrências. A política populacional de duplicidades continua controlada pela configuração já existente e não é alterada pelo exportador. A alteração do contrato não modifica a preparação, os nove estratos, as exclusões, Cochran, alocações, pesos, semente ou algoritmo de sorteio.

O classificador externo recebe somente o pipeline e preserva o ID em Stage 1, Stage 2, checkpoints, retomadas e saída final. Os pesos são associados posteriormente pelos metadados, sem integrar a entrada da LLM. Este projeto não implementa classificação nem altera o outro repositório. Veja os [esquemas exatos](esquemas.md) e os [requisitos de integração](integracao_classificador.md).

## Complexidade e memória

Leitura do corpus e recuperação são O(bytes do CSV). Ordenação dos IDs é O(N log N). Metadados, contadores de identidade/hash e unidades compactas são O(N); somente os textos selecionados ficam retidos ao exportar. Os metadados dos repositórios são O(R). Há passagens adicionais para checksums, que aumentam I/O mas permitem verificar alterações de qualquer entrada, inclusive durante a execução.

O desenho evita reter o DataFrame de aproximadamente 1,9 GB de texto. Não promete memória constante. A preparação completa com os metadados reais levou 39,49 segundos e atingiu 658.964 KiB de RSS máximo (aproximadamente 643,5 MiB) no ambiente desta auditoria, incluindo hashes e verificações. A medição é local e não inclui sorteio/exportação real, que não foram executados.

## Falhas e histórico

Cada execução usa um diretório exclusivo. Não há alteração em entradas, deduplicação automática ou substituição de saídas. Um manifesto `complete` só é escrito depois da recuperação, exportação, verificação de integridade e estabilidade das entradas. Preparações podem ter status `prepared` ou `blocked` e não geram amostras. Erros estruturais produzem diagnóstico sem inventar uma alocação.

Os hashes são controles de integridade contra alterações acidentais. Não são assinaturas nem substituem o arquivamento dos arquivos originais e sua proveniência. Para reproduzir, preserve o código registrado pelo hash da implementação e o ambiente Python registrado; uma nova versão do código não valida silenciosamente resultados de outra implementação.

A versão 1.1.1 registra o contrato de exportação 3 e checksums dos três CSVs no manifesto. A revisão acrescenta `commits_count` à projeção anterior, mantendo as demais decisões. A validação exige esse contrato e a lista completa de artefatos. Os relatórios descrevem as três responsabilidades e a chave de ocorrência. A preparação real da versão 1.0.0 permanece arquivada, sem migração, alteração de artefatos ou sorteio definitivo durante este ajuste.

## Extração técnica de integração — versão 1.2.0

`smoke_selection` acrescenta seleção intencional por cobertura, com reserva de um par real provider/community por logical_id, nove estratos e dois tipos. Perfila os valores reais da projeção existente e retém candidatos compactos por assinatura; não mantém o texto de toda a população em memória. A semente entra no hash de desempate, com ordem final por sampling_unit_id. O [guia específico](smoke_integracao.md) documenta os limites, as prioridades e a natureza não probabilística.

`smoke` coordena preparação, autorização técnica explícita, seleção, exportação, manifesto, relatório e revalidação. Reutiliza `prepare`, `check_preparation`, `allocate` apenas como verificação do planejamento, recuperação de ocorrências e projeções de `export`, contratos e I/O existentes. A recuperação compartilhada foi extraída de selected_rows em occurrence_rows/recover_rows; o exportador definitivo preserva seu comportamento, verificado pela suíte de regressão. Os módulos de identidade, preparação, exclusões, estratificação, estatística e sorteio não foram alterados.

O comando `smoke` exige --authorize-technical-smoke e aceita somente size=15. A autorização deixa explícitas as pendências de aprovação do mapeamento e formalização das ocorrências, sem alterar Config nem registrar aprovação. Outros bloqueios continuam fatais. `workflow.validate_run` identifica o manifesto técnico e delega a revalidação a `smoke.validate_smoke`. Os diretórios são outputs/smoke_tests/<run-id>, sem sobrescrita ou arquivos final_sample_*. Não há chamada a draw nem exclusão dos 15 registros de uma seleção futura.

O metadata de smoke mantém as mesmas 14 colunas, com campos de desenho/probabilidade, peso provider e tamanho amostral vazios. Os tamanhos populacionais e as proporções dos estratos têm significado descritivo. O manifesto distingue explicitamente seleção intencional, autorizações técnicas, pendências metodológicas e planejamento definitivo sem sorteio.

## Normalização de exportação — versão 1.2.1

O contrato de exportação 4 mantém os cabeçalhos 13/14 e explicita a normalização de commits_count. `export.project_pipeline_row` resolve aliases sem transformar células e continua alimentando `smoke_selection`, preservando os critérios de cobertura. `export.pipeline_row` aplica a função pura de normalização somente após essa projeção; os dois exportadores reutilizam esse ponto. Decimal mantém a precisão das strings/inteiros e usa o valor exato de floats recebidos.

`normalization.audit_commits_count` particiona valores válidos, ausentes e inválidos, conta inteiros/representações decimais e zeros, e registra sampling_unit_id, valor original e motivo para cada inválido. `pipeline_export_audit` respeita a origem configurada do campo. O resultado fica em export_audit nos manifestos e relatórios JSON existentes, com resumo Markdown; não é inserido em Prepared.audit ou nos metadados estatísticos.

As validações refazem a transformação e a auditoria usando as células originais já verificadas por hash, rejeitando inconsistências mesmo com checksums de saídas atualizados. Os completos, comments_count, textos, configurações, métodos de seleção e cálculos estatísticos mantêm seus contratos anteriores. A nova extração usa outro run-id e preserva os diretórios históricos.
