# Diagnóstico dos arquivos e da preparação real

## Estado atual em 2 de novembro de 2026

Os arquivos indicados pelo pesquisador estão no repositório: `data/raw/issues_prs.csv`, `data/raw/repositories.csv`, `data/raw/pilot-200.csv` e `docs/Calculo_Amostragem_Final.docx`. O DOCX foi integralmente lido e conferido. A configuração foi ajustada ao esquema real e a preparação foi executada sem sortear registros.

- Universo confirmado: 391.596 linhas, sendo 383.387 provider e 8.209 community.
- Metadados: 381 repositórios provider de 80 organizações; chave única por nome completo extraído de html_url. A coluna # é um ordinal, não uma identidade. Community utiliza sua origem explícita e dispensa associação com metadados provider.
- Todas as linhas foram resolvidas, sem falhas de relacionamento ou estratificação.
- Piloto: 200 chaves encontradas, nenhuma ausente ou ambígua, 200 linhas removidas antes do cálculo (195 provider e 5 community).
- População elegível: 391.396 ocorrências; planejamento amostral: 3.408 casos.
- Foram aprovadas 21 verificações técnicas e 168 testes. Nenhuma ocorrência repetida foi removida e nenhum registro real foi sorteado.
- Os arquivos originais permanecem com os hashes registrados. O [relatório técnico completo](auditoria_corpus_real.md) apresenta distribuições, pesos e pendências.

A descrição temporal do DOCX (2012–2024) difere das datas de criação observadas (2011–2025). A divergência foi documentada e não se aplicou um filtro temporal. Há 105 categorias provider com espaço final e 540 registros community com categoria bruta preenchida; essas representações são preservadas nas colunas originais, e community permanece no nono estrato.

Há 381 metadados provider, mas 379 repositórios aparecem nos registros. cryptofinlabs/audit-checklist e moralisweb3/moralis-analytics-js não têm registros no corpus. Community contém 3.697 repositórios representados, enquanto a referência informa 4.500 selecionados a montante. Essas diferenças de cobertura não são perdas na junção.

Para reproduzir sem sorteio, execute inspect e prepare com `configs/sampling.json`. O código 2 de prepare registra os bloqueios metodológicos ativos, embora todas as verificações técnicas tenham passado.

## Histórico da etapa inicial sem arquivos locais

As observações abaixo descrevem o diagnóstico anterior à entrega dos arquivos. As limitações de ausência dos metadados e do documento foram superadas. O candidato a piloto encontrado no projeto vizinho tinha hash diferente de pilot-200.csv e não foi utilizado na preparação atual.

O diretório de trabalho estava vazio, sem módulos reutilizáveis, arquivo metodológico completo, datasets ou instruções AGENTS.md. O Git encontrado pertence ao diretório pai, contendo outros projetos; nenhum arquivo desses projetos foi alterado. O nome do pacote/projeto implementado é web3blockset-sampling, mantendo o diretório solicitado pelo usuário.

Foram encontrados arquivos candidatos nos projetos vizinhos `web3blockset_audit_v3`, `llm_verify_pipeline` e `pipeline-llm-verification`. A inspeção foi somente leitura. Nenhum deles foi incorporado ao Git ou promovido automaticamente a entrada oficial da amostragem. Não foi encontrado repositories.csv.

## Corpus candidato inspecionado integralmente

Arquivo relativo ao diretório pai: `web3blockset_audit_v3/data/raw/issues_prs.csv`.

- Tamanho: 1.904.740.858 bytes.
- SHA-256: `cd1b402f43068ac2d2141a3c1ff3784dfd1569ee6932ffa70866735e2953dead`.
- 391.596 linhas; provider 383.387, community 8.209.
- Tipos: 161.405 Issue e 230.191 Pull Request, considerando ambas as origens.
- 391.421 issue_id distintos e 391.421 chaves brutas distintas (owner, repository, issue_number, type); 175 grupos repetidos, com 175 ocorrências adicionais em cada chave candidata.
- 4.019 pares brutos distintos (owner, repository) representados nos registros. Essa contagem observada não substitui as contagens metodológicas dos repositórios selecionados na construção do dataset; metadados podem incluir repositórios sem registros elegíveis.
- Nenhum repository, owner, issue_id, issue_number, type ou data_source vazio.
- 7.669 categorias vazias no conjunto completo; a distribuição por origem deve ser validada na integração com os metadados oficiais.
- 105 valores `Development Platform / Framework ` com espaço final, além da variante sem espaço. A normalização técnica utiliza strip; o campo original é preservado.

As 29 colunas observadas foram:

```text
repository, owner, issue_id, issue_number, issue_title, issue_body, state,
created_at, updated_at, closed_at, author, author_id, locked, comments_count,
commits_count, labels, type, concatenated_comments, comment_authors,
comments_count_filtered, repository_category, year, raw_text, clean_text,
stemmed_text, data_source, owner_used, matching_keywords,
matching_mandatory_keywords
```

Todos os campos são tratados como strings. Os identificadores estão preenchidos com representação inteira nesse arquivo. Os exemplos iniciais de repository são nomes curtos e precisam de owner para formar a chave. Não foi aplicada deduplicação nem foram calculados Nₕ definitivos sem o arquivo oficial de repositórios e sem decisões sobre duplicidades e piloto.

## Candidato a piloto

Arquivo: `llm_verify_pipeline/data/pilot/pilot_annotation_sample.csv`.

- SHA-256: `411d66b08d2f2838d313c7a19b8d50f4628447e510c263a93ea8adffd4875617`.
- 200 linhas e 200 issue_id distintos; 200 chaves (repository_full_name, issue_number, type) distintas.
- 195 provider e 5 community; 89 Issue e 111 Pull Request.
- Possui repository_full_name, issue_number e type, além dos textos e metadados de anotação.

Há também `pipeline-llm-verification/data/pilot_pipeline_input_200.csv`, com apenas repository, issue_number, issue_title, issue_body e concatenated_comments. Foi inspecionado seu cabeçalho e exemplos de chave, sem adotá-lo como piloto oficial. Não se presume que arquivos de nomes semelhantes sejam intercambiáveis; o pesquisador precisa indicar o conjunto efetivamente utilizado.

## Pipeline observado

Foi examinada a leitura em `llm_verify_pipeline/llm_pipeline/data.py` e suas colunas obrigatórias em config.py. Esse leitor requer repository, issue_number, issue_title e issue_body, aceita concatenated_comments e demais campos e rejeita colisões de repository + issue_number. O perfil exportado inclui os cinco campos solicitados e conserva todos os metadados de amostragem. Nenhum módulo do pipeline foi importado pela aplicação ou executado.

## Evidência e reprodução da inspeção

O relatório local completo está em `outputs/reports/real_corpus_profile.json` (ignorado pelo Git). Pode ser recriado sem qualquer sorteio:

```bash
PYTHONPATH=src python3 -m web3blockset_sampling inspect \
  --file ../web3blockset_audit_v3/data/raw/issues_prs.csv \
  --file ../llm_verify_pipeline/data/pilot/pilot_annotation_sample.csv
```

Essas observações históricas descrevem os candidatos daquela etapa. A preparação integrada atual utiliza somente os arquivos locais indicados pelo pesquisador, conforme o estado atualizado no início deste documento. O classificador não foi executado.
