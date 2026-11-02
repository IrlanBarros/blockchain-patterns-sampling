# Estado das decisões metodológicas

Atualização da auditoria de 2 de novembro de 2026. A decisão do pesquisador é utilizar o universo original de 391.596 registros, mantendo todas as ocorrências e sem utilizar o corpus canonicalizado de 391.421. Essa decisão não está em aberto.

| Tema | Estado | Resultado ou ação necessária |
|---|---|---|
| Universo | Decidido | Original MSR 2026, 391.596 linhas, 383.387 provider e 8.209 community. Nenhum filtro de duplicidades ou período foi aplicado. |
| Arquivos e junção | Verificado | Os três CSVs e o DOCX foram localizados e tiveram hashes registrados. Os 381 metadados são provider; os 383.387 registros provider foram associados sem ambiguidades. Community mantém sua origem explícita. |
| Piloto | Verificado | pilot-200.csv é a entrada indicada. As 200 chaves compostas, incluindo issue_id, foram encontradas; 200 linhas excluídas, sendo 195 provider e 5 community. Nenhuma chave ausente ou ambígua. |
| Retenção das duplicidades | Decidida e respeitada | As 175 ocorrências adicionais permanecem. Cada identidade repetida tem uma ocorrência provider e outra community; não houve deduplicação ou preferência por uma origem. |
| Unidade do sorteio | Registro formal pendente | A configuração conserva duplicate_policy=error. Antes do sorteio, é preciso formalizar a unidade de ocorrência original em preserve_rows e sua justificativa, coerente com a retenção já decidida. Não se propõe trocar o corpus ou eliminar ocorrências. |
| Agrupamento | Aprovação humana pendente | O mapeamento cobre as 33 categorias e corresponde integralmente ao DOCX. O documento exige validação pelos autores antes do sorteio. Registre responsável, data e hash da versão aprovada. |
| Período descrito | Divergência documental | O DOCX informa 2012–2024, mas created_at no original vai de 20/09/2011 a 18/10/2025. Há 3 registros de 2011 e 49.988 de 2025. Corrigir ou esclarecer a descrição no texto científico, preservando o universo decidido. |
| Smoke test | Sem exclusão adicional | A metodologia não determina excluir os 30 casos. O comportamento permanece não excluir; qualquer mudança exige solicitação e justificativa explícitas. |
| Contrato do classificador | Confirmação pendente | O perfil observado exige repository + issue_number únicos. Se duas ocorrências do mesmo artefato forem selecionadas, esse contrato precisa de adaptação explícita, como usar sampling_unit_id. Não se refaz o sorteio para contornar colisões. |

Os campos de decisão armazenam declarações para auditoria e não substituem a revisão da pesquisa. O comando approve-mapping registra a aprovação humana do agrupamento; nenhuma aprovação real foi criada nesta etapa. As declarações sintéticas dos testes não têm validade para o corpus real.

Esta etapa está limitada à auditoria e ao planejamento: nenhum registro real foi sorteado. O relatório técnico detalha as verificações e separa capacidade técnica dos bloqueios metodológicos remanescentes.
