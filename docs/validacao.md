# Evidências de validação da implementação

Ambiente utilizado: Python 3.13.5, pytest 8.3.3, setuptools 80.9.0.

## Suíte automatizada

```bash
python3 -m pytest -q --junitxml=outputs/reports/audit_tests.xml
```

Resultado da suíte final: **168 testes aprovados**. São testes locais, determinísticos e sem chamadas a LLMs, GitHub ou serviços externos. O resultado estruturado está em `outputs/reports/audit_tests.xml`.

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

## Empacotamento e sintaxe

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
