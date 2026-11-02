# Arquitetura e fluxo de dados

O desenho separa operações de I/O das funções estatísticas e de sorteio, sem frameworks ou dependências em outro projeto.

1. `config` valida uma configuração JSON explícita. A referência das 33 categorias acompanha o pacote e é independente do arquivo de mapeamento editável.
2. `ingestion` lê CSV com parser estrito, strings e controle de codificação/delimitador. Não interpreta `NA`, datas ou números como valores ausentes. Linhas de largura inválida e cabeçalhos repetidos são erros.
3. `identity` constrói somente atributos derivados, sem sobrescrever as células brutas. Repositórios são nomes completos, identificadores inteiros são normalizados e tipos/origens usam dicionários explícitos.
4. `preparation` indexa metadados por uma chave única, faz uma junção muitos-para-um e retém objetos compactos `Unit`, não corpos/títulos/comentários. O escopo provider permite os 381 metadados reais e encaminha community pelo data_source, sem associação arbitrária. Audita identidades e repetições exatas por SHA-256 do conteúdo completo da linha. Linhas inválidas aparecem no balanço e bloqueiam o sorteio.
5. `exclusions` resolve o piloto contra as identidades, detecta ambiguidades e exclui unidades antes de qualquer alocação definitiva. Cada remoção permanece rastreável no relatório.
6. `statistics` calcula a alocação e os pesos a partir da população elegível; `sampling` recebe somente unidades, alocação e semente.
7. `export` recupera apenas os registros sorteados numa segunda passagem. Uma impressão digital e uma ocorrência por conteúdo relacionam cada linha à sua unidade; todos os textos ficam na memória somente para a pequena amostra final.
8. `validation.check_preparation` verifica balanço, exclusões, fórmulas e pesos sem sortear. As demais validações repetem invariantes do desenho e comparam células/metadados exportados. `workflow.validate_run` também reconstrói relatórios e verifica entradas, saídas, configuração e implementação.
9. `reports` resume distribuições, concentração, categorias, tipos e decisões. `workflow` organiza diretórios únicos, configurações efetivas e o manifesto que marca uma execução concluída.

## Complexidade e memória

Leitura do corpus e recuperação são O(bytes do CSV). Ordenação dos IDs é O(N log N). Metadados, contadores de identidade/hash e unidades compactas são O(N); somente os textos selecionados ficam retidos ao exportar. Os metadados dos repositórios são O(R). Há passagens adicionais para checksums, que aumentam I/O mas permitem verificar alterações de qualquer entrada, inclusive durante a execução.

O desenho evita reter o DataFrame de aproximadamente 1,9 GB de texto. Não promete memória constante. A preparação completa com os metadados reais levou 39,49 segundos e atingiu 658.964 KiB de RSS máximo (aproximadamente 643,5 MiB) no ambiente desta auditoria, incluindo hashes e verificações. A medição é local e não inclui sorteio/exportação real, que não foram executados.

## Falhas e histórico

Cada execução usa um diretório exclusivo. Não há alteração em entradas, deduplicação automática ou substituição de saídas. Um manifesto `complete` só é escrito depois da recuperação, exportação, verificação de integridade e estabilidade das entradas. Preparações podem ter status `prepared` ou `blocked` e não geram amostras. Erros estruturais produzem diagnóstico sem inventar uma alocação.

Os hashes são controles de integridade contra alterações acidentais. Não são assinaturas nem substituem o arquivamento dos arquivos originais e sua proveniência. Para reproduzir, preserve o código registrado pelo hash da implementação e o ambiente Python registrado; uma nova versão do código não valida silenciosamente resultados de outra implementação.
