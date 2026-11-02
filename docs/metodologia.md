# Decisões implementadas a partir da metodologia fornecida

## Universo e unidades

O universo padrão possui 391.596 ocorrências do snapshot original MSR 2026, sendo 383.387 provider e 8.209 community. A execução verifica essas contagens antes das exclusões. Não toma os 391.421 registros de uma canonicalização como substituto implícito. Versões alternativas devem ser identificadas, justificadas e ter contagens próprias.

Nesta pesquisa, o pesquisador confirmou definitivamente o universo original. A preparação real foi validada sem remover as 175 ocorrências adicionais. O DOCX descreve 2012–2024, enquanto as datas de criação observadas abrangem 2011–2025; essa divergência foi registrada sem mudar o universo ou aplicar filtros. A formalização da unidade de ocorrência para o sorteio e a aprovação humana do agrupamento permanecem registradas como pendências, sem qualquer sorteio real nesta etapa.

A identidade lógica padrão usa nome completo do repositório, número inteiro do artefato e tipo. É serializada como pares ordenados de nomes de campo e valores em JSON canônico, UTF-8, SHA-256. O identificador global pode ser acrescentado. A origem não pode distinguir identidades do mesmo artefato, o que impediria excluir suas demais ocorrências no piloto. Índices posicionais de DataFrame não são usados.

Na política padrão `error`, qualquer identidade repetida impede a amostra definitiva. Na alternativa aprovada `preserve_rows`, a unidade passa a ser uma ocorrência de linha: `row:SHA256(conteúdo bruto):ocorrência`. O conteúdo é o dicionário completo da linha serializado como JSON canônico com nomes de coluna ordenados. A ocorrência conta somente linhas de conteúdo idêntico, não sua posição no arquivo; permutações preservam o multiconjunto de IDs. Ocorrências idênticas são intercambiáveis, sem distinção física inferível dos dados.

Repetição exata, identidade lógica repetida, `issue_id` repetido e número compartilhado por tipos diferentes são diagnósticos separados. Um mesmo número em repositórios distintos representa unidades distintas. Um mesmo número/tipo com múltiplas origens exige a política explícita para ocorrências, ou a adoção de outro corpus aprovado; não se prefere provider silenciosamente.

## Nove estratos

`configs/strata.json` contém o agrupamento integral das 33 categorias em oito estratos provider e o estrato Community, sem categorias próprias. O pacote valida cobertura, exclusividade, os nove nomes e a correspondência exclusiva Other → Outros. Categorias provider vazias/desconhecidas não recebem um fallback.

Provider/community vêm de uma coluna configurada ou dos metadados associados de forma única. Havendo origem em ambas as entradas, divergências são bloqueadas. Categorias presentes em registros community não os transferem para provider. Espaços externos em tokens são removidos exclusivamente nos campos técnicos derivados; os campos brutos permanecem no arquivo completo.

O agrupamento exige declaração humana de aprovação vinculada ao SHA-256. A aplicação não escolhe nem concede essa aprovação aos pesquisadores.

## Exclusões

O piloto é resolvido antes do cálculo de Nₕ, utilizando uma chave completa ou um subconjunto configurado que encontre uma única identidade lógica. Todas as ocorrências dessa identidade são removidas. O relatório separa identificadores lógicos e linhas, chaves não encontradas, duplicadas, ambíguas e sobreposição com outras exclusões. Chaves inválidas/ambíguas/ausentes bloqueiam sempre. Divergência de quantidade exige uma decisão documentada e nunca é ocultada. O smoke test só é aplicado com caminho e decisão explícitos.

## Cálculo

Para cada Nₕ elegível:

```text
n₀ = z² p(1−p) / e²
n_contínuo = n₀ / [1 + (n₀−1)/Nₕ]
nₕ = min(Nₕ, ceil(n_contínuo))
```

Padrões: confiança 95%, z=1,96, p=0,5, e=0,05. p=0,5 maximiza p(1−p), adotando a variância conservadora quando a prevalência é desconhecida. Nₕ=0 implica nₕ=0; o censo é respeitado em populações pequenas. O cálculo usa ponto flutuante de precisão dupla e arredondamento `math.ceil`.

A tabela aproximada fornecida gera 383, 382, 382, 382, 382, 378, 377, 376 e 368 registros (soma 3.410). Esses valores são testados como referência e não entram como constantes da alocação real. Exclusões e populações exatas podem alterar a soma; o relatório registra a diferença.

## Aleatoriedade e probabilidades

Algoritmo versionado: `sorted-ids-python-random-sample-sha256-stratum-v1`.

1. Ordene os IDs elegíveis de cada estrato lexicograficamente.
2. Derive uma semente inteira do SHA-256 do JSON canônico `[nome_do_algoritmo, semente, nome_do_estrato]`.
3. Crie uma instância local de `random.Random`, que utiliza MT19937 na implementação Python registrada.
4. Utilize `random.sample` para selecionar exatamente nₕ IDs sem reposição.

Cada unidade possui probabilidade de inclusão πₕ=nₕ/Nₕ dentro do seu estrato. A independência dos geradores impede que uma alteração no tamanho de outro estrato consuma seu estado aleatório. A ordenação remove a dependência da ordem física dos registros. Não há gerador global nem reamostragem para atender a cotas, totais previstos ou ao contrato do classificador. Para reprodução, preserve a versão do programa, o hash do código e a versão major.minor do Python.

## Pesos

`sampling_population_weight` é Wₕ=Nₕ/N, comum a todas as observações do estrato. A estimativa global utiliza Σ Wₕ p̂ₕ. A soma dos Wₕ, por estrato, é 1; a soma desses valores repetidos em cada linha da amostra não é 1.

`sampling_design_weight` é Nₕ/nₕ, inverso da probabilidade de inclusão. Permite estimar totais e, com normalização apropriada, proporções. Não deve ser confundido com Wₕ. A soma dos pesos de expansão das observações selecionadas recupera N.

`sampling_provider_weight` é Nₕ dividido pelo total elegível dos oito estratos provider; é vazio para Community ou quando não há população provider. Esse peso permite combinar os estratos para a comparação provider/community.

## Escopo da precisão

±5% por estrato diz respeito à proporção de registros que discutem pelo menos um design pattern. Não é garantia sobre classificação, cada pattern, tempos de resolução ou detecção de pequenas diferenças. A margem global aproximada de ±2,1% não é calculada ou copiada como constante. Sensibilidade, especificidade, correção de Rogan–Gladen e revisão humana pertencem às etapas posteriores.

A concentração por repositório e o balanço entre issues e PRs são descritos para avaliar ameaças à validade; não são usados para criar estratos adicionais ou cotas. A versão oficial do corpus, a interpretação das repetições e o agrupamento permanecem decisões dos pesquisadores.
