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

## Adaptador do classificador

`pipeline_columns` descreve **destino → origem**. Uma origem comum é um cabeçalho original. Existem três fontes derivadas: `@repository` (nome completo), `@number` (número inteiro técnico), `@artifact_type` (tipo original). Não há preenchimento automático de campos ausentes. O adaptador conserva os campos extras e os metadados de amostragem; aliases podem substituir nomes apenas no arquivo do pipeline. O arquivo completo conserva os valores anteriores, permitindo reverter essa adaptação.

O contrato padrão exige repository, issue_number, issue_title, issue_body e concatenated_comments. O código de leitura do pipeline vizinho também aceita campos adicionais. Essa leitura foi inspecionada sem criar importações ou dependências entre repositórios; nenhuma classificação real foi executada.

`pipeline_key_fields` declara a chave exigida pelo classificador. O padrão é repository + issue_number, observado no pipeline local. Um contrato diferente exige `pipeline_decision`, e sua implementação no classificador cabe ao projeto correspondente. Não se ajusta o sorteio nem se descarta uma observação incompatível: a execução fica bloqueada e o contrato precisa ser resolvido.

## Inspeção e validação

As chaves candidatas de `inspect` são exploratórias e usam valores brutos. As datas são perfiladas sem alterar células nem aplicar filtros de período. A escolha efetiva e as normalizações constam de `config_snapshot.json` e do manifesto. `prepare` registra verificações de balanço, exclusões, fórmulas e pesos sem executar sorteio. `validate` verifica execuções definitivas, repete a escolha e compara os hashes de todas as células originais e os valores de cada metadado, além do adaptador do pipeline e dos relatórios recalculados.
