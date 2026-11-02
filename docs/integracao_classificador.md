# Integração da amostra com o classificador

## Arquivos e responsabilidades

O projeto de amostragem entrega três CSVs com os mesmos `sampling_unit_id`, todos únicos e não vazios. Cada linha representa uma ocorrência selecionada. A quantidade é a seleção efetiva registrada no manifesto; não é ajustada para eliminar colisões de repository/número ou para atingir um total fixo.

| Arquivo | Consumidor | Conteúdo |
|---|---|---|
| final_sample_full.csv | Auditoria e reprodução | Todas as colunas originais + 14 metadados; 43 colunas no corpus atual |
| final_sample_pipeline.csv | Classificador | Exatamente 13 campos de identificação, contexto, datas e textos |
| final_sample_metadata.csv | Análise estatística posterior | Exatamente 14 metadados, sem textos; pesos e proveniência copiados do completo |

**O classificador recebe somente `final_sample_pipeline.csv`; não precisa receber estratos ou pesos estatísticos.** Os [contratos de dados](esquemas.md) definem as listas e a proveniência dos campos. O cabeçalho de entrada é exatamente:

```text
sampling_unit_id,repository,issue_number,artifact_type,repository_category,created_at,closed_at,state,comments_count,commits_count,issue_title,issue_body,concatenated_comments
```

O número original é preservado como string. `artifact_type` copia o valor original de `type`, preservando Issue/Pull Request. A categoria vem da própria linha, inclusive quando vazia. Datas e `comments_count` mantêm as células originais. **`commits_count` deve ser exportado como inteiro não negativo quando válido e como célula vazia quando ausente ou inválido.** Zero é válido: `0.0` → `0`, `5.0` → `5`; frações não são arredondadas, e negativos, infinitos e conteúdos não numéricos viram vazio. Ausências (`None`, NaN, vazio, espaços, `null`) também viram vazio, sem preenchimento por zero. Os completos mantêm a representação original e a auditoria `export_audit.commits_count` distingue ausentes e inválidos, registrando IDs/valores/motivos dos inválidos. A mesma regra vale no smoke e não modifica outras colunas nem a lógica do classificador. Campos temporais permitem as análises já previstas, como `resolution_days`, cujo cálculo e tratamento de ausências/inconsistências pertencem ao classificador e à análise posterior.

## Requisitos para Stage 1 e Stage 2

O fluxo possui somente **Stage 1 e Stage 2**. Esta integração não acrescenta etapas nem muda regras, prompts ou categorias de classificação.

1. Validar presença, preenchimento e unicidade de `sampling_unit_id` na entrada; preservar a string integral, sem substituí-la por repository/número ou por um índice de linha.
2. Aceitar `artifact_type` como campo de tipo de artefato. Se um nome interno diferente for necessário, usar um alias explícito na leitura; não exigir uma coluna adicional `type` na exportação.
3. Transportar `sampling_unit_id` nos objetos preparados, requisições, respostas e resultados de Stage 1 e Stage 2. IDs técnicos de requisições devem distinguir pelo menos etapa e ocorrência; se houver várias requisições por ocorrência, distinguir também a unidade interna existente, como o pattern.
4. Indexar checkpoints, estados de conclusão e retomadas pela ocorrência e pela etapa/unidade interna aplicável. Duas ocorrências com repository/número iguais devem ter estados independentes, inclusive quando seus textos forem idênticos.
5. Preservar o ID também nos resultados vazios, falhas e estados de processamento previstos pelo classificador. Uma retomada não pode omitir uma ocorrência por outra já ter o mesmo repository/número.
6. A saída final por ocorrência deve permitir uma junção um-para-um com os metadados. Se a saída analítica tiver várias linhas por ocorrência, manter o ID em todas e declarar essa granularidade; a tabela de controle por ocorrência deve continuar cobrindo exatamente a entrada, sem duplicidades.

`sampling_logical_id` e repository/número servem como atributos de rastreabilidade; podem se repetir e não são chaves de ocorrência. A seleção não deve ser refeita, deduplicada ou consolidada para contornar uma limitação do classificador.

## Situação da implementação externa inspecionada

O código local em `../../llm_verify_pipeline/llm_pipeline/` foi consultado somente para leitura. Não foi modificado, importado ou executado por este projeto. A integração real permanece **pendente**, pois o contrato observado ainda não satisfaz os requisitos acima:

| Local externo | Comportamento observado | Adaptação necessária no outro projeto |
|---|---|---|
| data.py / validate_input_dataframe | Rejeita repository/número repetidos; monta issue_key com esse par | Validar unicidade por sampling_unit_id e permitir pares repetidos |
| data.py / prepare_issue | Lê type e cria custom_id_stage1 a partir de repository/número | Ler artifact_type e preservar o ID da ocorrência na preparação e nas requisições |
| models.py / PreparedIssue | Não contém sampling_unit_id | Transportar o ID sem perda entre as etapas |
| checkpoint.py | Valida chaves configuradas e deriva IDs técnicos dessas chaves | Configurar/implementar chaves por ocorrência e testar retomadas sem colisões |

A adaptação também precisa alcançar os escritores de Stage 1, Stage 2 e saída final. Esses requisitos documentam o trabalho posterior; não representam testes de integração aprovados no classificador. Neste repositório, testes contratuais verificam o esquema e simulam resultados reordenados para uma junção por ID, incluindo identidades lógicas repetidas.

## Exemplo de junção após classificação

Exemplo com a biblioteca padrão, sem inferência de tipos e sem dependências do classificador. `classification_results.csv` representa uma saída final com uma linha por ocorrência e coluna `sampling_unit_id`; os demais campos são resultados da classificação.

```python
import csv
from pathlib import Path

run = Path("outputs/IDENTIFICADOR_DA_EXECUCAO")

def by_occurrence(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "sampling_unit_id" not in reader.fieldnames:
            raise ValueError(f"Chave ausente: {path}")
        indexed = {}
        for row in reader:
            uid = row["sampling_unit_id"]
            if not uid or not uid.strip() or uid in indexed:
                raise ValueError(f"Chave vazia ou duplicada: {path}")
            indexed[uid] = row
        return indexed

results = by_occurrence(Path("classification_results.csv"))
metadata = by_occurrence(run / "final_sample_metadata.csv")
if results.keys() != metadata.keys():
    raise ValueError("Resultados e metadados não cobrem as mesmas ocorrências")

for uid in results:
    if (results[uid].keys() & metadata[uid].keys()) != {"sampling_unit_id"}:
        raise ValueError("Resultado contém colunas reservadas de metadados")

joined = [{**results[uid], **metadata[uid]} for uid in results]
assert len(joined) == len(results) == len(metadata)
# joined associa cada resultado aos pesos já calculados, sem multiplicar linhas.
```

Antes de disponibilizar a amostra ao classificador, validar a execução completa com `python -m web3blockset_sampling validate --run-dir outputs/IDENTIFICADOR_DA_EXECUCAO`. Essa validação confere os três CSVs, o manifesto, os originais e os relatórios. O exemplo de junção não executa classificação nem sorteia registros. Durante a refatoração dos contratos não foi executado sorteio definitivo do corpus real.

## Entrada técnica anterior ao sorteio definitivo

O [smoke de integração](smoke_integracao.md) entrega **smoke_15_pipeline.csv** para exercitar o contrato com somente 15 ocorrências reais. O cabeçalho é o mesmo contrato de 13 colunas, incluindo commits_count. As duas ocorrências do par lógico devem passar independentemente por Stage 1, Stage 2 quando houver candidatos, checkpoints e retomadas; sampling_unit_id é a chave em todos esses pontos.

smoke_15_full.csv e smoke_15_metadata.csv são referências de auditoria. Os campos estatísticos inaplicáveis ficam vazios, sem pesos de expansão ou probabilidades. O relatório registra apenas indícios lexicais e cobertura técnica. A extração não demonstra relevância semântica nem valida Stage 2; a integração efetiva continua a cargo do classificador. Não houve chamada a LLM nem modificação da arquitetura externa.
