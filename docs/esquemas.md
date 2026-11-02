# Contratos de entrada e exportação

## Configuração JSON

`configs/sampling.json` está ajustado aos três arquivos reais fornecidos; não implica que todos os CSVs futuros tenham esses cabeçalhos. Todas as colunas mapeadas devem existir, mesmo quando uma célula pode estar vazia. Dados obrigatórios para chaves, origem ou estrato não podem estar vazios. Textos vazios são preservados, sem inventar títulos, comentários ou corpos.

O arquivo real de repositórios contém somente provider. `repository_scope: "provider"` declara esse escopo; não cria uma coluna no arquivo original. O nome completo é extraído de `html_url` pelo formato explícito `repository_formats.repositories: "github_url"`. São aceitas URLs HTTPS de github.com com owner/name, sem credenciais, query, fragmentos ou subcaminhos. A coluna `#` é um ordinal do CSV e não é usada como identidade do repositório. `repository_category_claude` não participa da junção nem da seleção: a categoria utilizada é `repository_category`.

Nesse escopo, `source` é obrigatório no esquema de issues. Todos os community seguem diretamente para o nono estrato, sem exigir metadados provider e sem mudar de origem quando há um repositório de mesmo nome nos dois grupos. A categoria técnica community é vazia; qualquer categoria bruta presente em sua linha permanece nas colunas originais e em sampling_original_category. O modo genérico `repository_scope: "all"` mantém a junção estrita para ambas as origens.

O campo opcional `methodology` aponta ao documento de referência; seu caminho e hash entram no manifesto e na verificação de imutabilidade. A identidade e a chave do piloto na configuração real utilizam repository, number, artifact_type e record_id, verificando o issue_id global junto à chave composta.

Campos internos suportados no esquema: `repository`, `owner`, `repository_id`, `number`, `artifact_type`, `record_id`, `source`, `category`. Os nomes à direita são cabeçalhos exatos do CSV. Campos extras originais não precisam ser declarados para serem preservados.

Os dicionários `source_values` e `artifact_values` mapeiam tokens de entrada em caixa baixa para provider/community e issue/pull_request. Tokens desconhecidos bloqueiam. A configuração padrão aceita Issue, Pull Request, pull_request e PR, sem inferir tipo pelo número ou pelos textos.

Exemplo para metadados com ID numérico:

```json
{
  "join_fields": ["repository_id", "source"],
  "schemas": {
    "issues": {
      "repository": "full_name", "repository_id": "repo_id",
      "number": "number", "artifact_type": "kind", "source": "origin"
    },
    "repositories": {
      "repository": "full_name", "repository_id": "id",
      "source": "origin", "category": "category"
    },
    "pilot": {
      "repository": "repository_full_name", "number": "issue_number", "artifact_type": "type"
    }
  }
}
```

Esse trecho deve ser combinado com os demais parâmetros. Mesmo com ID numérico, a igualdade dos nomes completos é verificada. Se um repositório aparece com ambas as origens, inclua `source` na chave e nos respectivos esquemas. Uma chave de metadados repetida não é resolvida por uma preferência arbitrária.

## Arquivo completo

`final_sample_full.csv` mantém cabeçalhos e valores originais na ordem original das colunas. A ordem das linhas passa a ser a ordenação dos IDs sorteados. A serialização CSV é UTF-8 com delimitador vírgula; a representação de aspas ou terminação de linhas do arquivo pode mudar, mas o conteúdo de cada célula, incluindo quebras de linha internas, permanece idêntico.

Acrescentam-se as colunas reservadas:

| Coluna | Significado |
|---|---|
| sampling_unit_id | Unidade sorteada, única na amostra |
| sampling_logical_id | Identidade lógica para detectar ocorrências do mesmo artefato |
| sampling_repository | Nome completo técnico do repositório |
| sampling_source | provider ou community |
| sampling_category | Categoria técnica oriunda de repositories |
| sampling_original_category | Categoria bruta de repositories para provider, ou da linha de issues para community quando presente |
| sampling_stratum | Um dos nove estratos |
| sampling_population | Nₕ após exclusões |
| sampling_sample_size | nₕ calculado |
| sampling_population_weight | Wₕ=Nₕ/N |
| sampling_design_weight | Nₕ/nₕ |
| sampling_provider_weight | Peso interno dos estratos provider, vazio para Community |
| sampling_inclusion_probability | nₕ/Nₕ |
| sampling_run_id | Execução que produziu a linha |

Colisões de cabeçalhos com essas colunas são rejeitadas. Todas as entradas têm SHA-256 no manifesto, incluindo os metadados de repositórios e exclusões. O arquivo completo não é um arquivo byte a byte idêntico à origem: é uma seleção de células verificadas contra as impressões digitais das linhas originais.

No corpus atual são **29 colunas originais + 14 metadados = 43 colunas**. A refatoração não remove nem altera campos desse arquivo. Colunas originais adicionadas a outros corpora também permanecem no arquivo completo.

## Arquivo do classificador: exatamente 13 colunas

`final_sample_pipeline.csv` é uma projeção explícita do completo, com a seguinte ordem fixa:

| Coluna | Origem na configuração do corpus real |
|---|---|
| sampling_unit_id | Chave da ocorrência, copiada do completo automaticamente |
| repository | sampling_repository: nome completo técnico owner/name |
| issue_number | issue_number original, sem normalização numérica |
| artifact_type | type original, sem normalização dos tokens |
| repository_category | repository_category da própria linha original |
| created_at | created_at original |
| closed_at | closed_at original |
| state | state original |
| comments_count | comments_count original, sem recontagem |
| commits_count | Célula configurada de issues_prs.csv, normalizada para inteiro não negativo ou vazio; original preservado no completo |
| issue_title | issue_title integral |
| issue_body | issue_body integral |
| concatenated_comments | concatenated_comments integral |

Não entram outras colunas originais nem metadados estatísticos. Categoria ausente continua vazia, inclusive em Community; não se substitui a categoria bruta por `sampling_category`, por um estrato ou por uma categoria inventada. Datas, `comments_count` e números de identificação permanecem strings originais: `issue_number=0007.0` continua `0007.0`. Somente `commits_count` recebe a normalização descrita abaixo. Aspas, espaços, Unicode e quebras de linha internas dos textos são preservados. Células vazias continuam vazias; o leitor preserva strings como `NA`, `null` e `NaN`. A exportação trata os marcadores de ausência explicitamente somente em `commits_count`.

`pipeline_columns` descreve **destino → origem** para os 12 campos além do ID automático. Uma origem comum é um cabeçalho original. Os aliases explícitos são `@repository` (nome completo), `@number` (célula original mapeada em `schemas.issues.number`) e `@artifact_type` (célula original mapeada em `schemas.issues.artifact_type`). Essa projeção aceita nomes de entrada configuráveis e rejeita destinos extras ou ausentes; a ordem do dicionário não altera a ordem fixa do CSV. Não há preenchimento automático de colunas ausentes. Campos extras futuros nunca vazam para a entrada do classificador.

`pipeline_key_fields` deve ser exatamente `["sampling_unit_id"]`; o campo `pipeline_decision` registra a justificativa do contrato. A unicidade de repository/número não é exigida e não interfere no sorteio. O [guia de integração](integracao_classificador.md) documenta a adaptação pendente no projeto externo.

## Normalização exclusiva de commits_count

**`commits_count` deve ser exportado como inteiro não negativo quando válido e como célula vazia quando ausente ou inválido.** A função reutilizável `normalization.normalize_commits_count` é aplicada em `export.pipeline_row`, compartilhada pelas exportações definitiva e smoke. A projeção bruta `project_pipeline_row` continua sendo usada pela seleção do smoke para manter seus critérios.

| Original | Pipeline | Auditoria |
|---|---|---|
| `0`, `0.0`, `"0.0"` | `0` | válido; zero preservado |
| `5`, `5.0`, `"0005.00"` | `5` | válido; representação inteira |
| `None`, NaN, `""`, espaços, `"null"` | vazio | ausente |
| `"abc"`, `-1`, `2.5`, ±Infinity | vazio | inválido; ocorrência registrada |

Zero é válido e nunca deve ser convertido em vazio. Frações não são arredondadas nem truncadas. A validação usa `Decimal`, aceita notação científica quando o valor é integral, e evita conversões intermediárias para float. Inteiros grandes e strings decimais conservam precisão. Strings são aparadas para interpretar somente esse campo; os marcadores `null` e NaN ignoram caixa. Booleanos, coleções e números complexos são inválidos. Outras colunas, inclusive `comments_count`, mantêm seus contratos.

`export_audit.commits_count` aparece no manifesto e no relatório JSON de validação, com resumo no relatório Markdown. `integers_preserved` conta representações inteiras; `decimal_representations_converted` conta representações com ponto/expoente. Sua soma é `valid`. `valid + missing + invalid = total`. `zeros_preserved` é um subconjunto dos válidos, não uma categoria adicional. `invalid_records` registra cada `sampling_unit_id`, `original_value` e `reason`, sem agrupar identidades lógicas repetidas. O completo mantém todas as células originais e permite recuperar cada representação. A auditoria de exportação é separada da auditoria da população e dos metadados estatísticos.

## Arquivo estatístico: exatamente 14 colunas

`final_sample_metadata.csv` contém exatamente as 14 colunas da tabela de metadados acima, na mesma ordem, começando por `sampling_unit_id` e terminando em `sampling_run_id`. Cada célula é copiada do arquivo completo; pesos não são recalculados na exportação. Não contém títulos, corpos ou comentários.

Há uma linha por ocorrência sorteada. `sampling_logical_id` pode se repetir, inclusive entre provider e community. Ele serve para rastreabilidade e não substitui a chave primária `sampling_unit_id`. O classificador não precisa receber esse arquivo; a análise posterior associa seus resultados aos estratos e pesos por `sampling_unit_id`.

## Contrato entre os três arquivos

Os três CSVs possuem contagens iguais e conjuntos idênticos de `sampling_unit_id`, sem chave vazia ou duplicada. As linhas são exportadas na ordem dos IDs, mas uma junção deve usar a chave, nunca a posição física. As validações exigem correspondência exata do pipeline e dos metadados com o completo, usando os aliases configurados e, exclusivamente para `commits_count`, o resultado da função de normalização. Também verificam a seleção e as impressões digitais das células originais.

O manifesto registra `export_contract.version: "4"`, a chave de ocorrência, as duas listas ordenadas de colunas e a regra de normalização. A versão 4 mantém as mesmas 13/14 colunas da versão 3 e altera somente a representação de `commits_count` no pipeline. Inclui checksums dos três CSVs. O contrato é independente da versão do algoritmo estatístico, que permanece inalterada. A versão do programa é 1.2.1; execuções históricas devem ser reproduzidas com a implementação registrada, sem migrar ou reescrever seus artefatos.

## Inspeção e validação

As chaves candidatas de `inspect` são exploratórias e usam valores brutos. As datas são perfiladas sem alterar células nem aplicar filtros de período. A escolha efetiva e as normalizações constam de `config_snapshot.json` e do manifesto. `prepare` registra verificações de balanço, exclusões, fórmulas e pesos sem executar sorteio nem gerar os três CSVs de amostra. `validate` verifica execuções definitivas, repete a escolha e compara os hashes de todas as células originais, os valores de cada metadado, os cabeçalhos exatos, os conjuntos de IDs e as projeções do pipeline e dos metadados, além dos relatórios recalculados. Falta de correspondência, IDs vazios, perda ou multiplicação de linhas e alterações de conteúdo bloqueiam a validação, mesmo que o checksum de uma saída adulterada tenha sido atualizado.

## Contrato técnico do smoke de integração

`smoke_15_pipeline.csv` reutiliza integralmente as 13 colunas, ordem, aliases e normalização exclusiva de `commits_count` descritos acima. O completo e os metadados usam o mesmo namespace de 14 campos. O identificador do smoke aparece em sampling_run_id. Os três arquivos contêm exatamente 15 ocorrências na mesma ordem, incluindo ambas as unidades do par de identidade lógica repetida. O manifesto tem run_type=integration_smoke e selection_nature=intentional_technical_coverage.

Por se tratar de seleção intencional, sampling_sample_size, sampling_design_weight, sampling_provider_weight e sampling_inclusion_probability são **células vazias** nos dois arquivos que contêm metadados. O vazio representa inaplicabilidade, sem pesos fictícios ou quotas convertidas em probabilidades. sampling_population é o N_h elegível real; sampling_population_weight é sua proporção descritiva N_h/N. Nenhuma dessas informações transforma o conjunto em amostra probabilística. Consulte [smoke_integracao.md](smoke_integracao.md).
