# Religião e política no Brasil

Projeto para estudar o crescimento de candidaturas e políticos ligados a igrejas, lideranças religiosas e identidades cristãs no processo eleitoral brasileiro.

O repositório organiza rotinas de coleta, limpeza, classificação, cruzamento estatístico e geração de materiais de apresentação. A base empírica combina dados públicos do TSE, informações municipais do IBGE e, em um módulo específico, amostras de processos públicos do PJe/TSE relacionados à propaganda em bens públicos.

## O que o projeto produz

- Bases consolidadas de candidaturas legislativas com sinalização religiosa.
- Painéis de votos por candidato, município, UF, eleição e esfera.
- Resumos de receitas e despesas eleitorais por candidato e tipo de rubrica.
- Testes estatísticos comparando candidatos cristãos e não cristãos, eleitos e derrotados, e grupos por ideologia partidária.
- Mapas e gráficos interativos para exploração dos resultados.
- Uma apresentação HTML em `reports/presentation/religiao_politica_brasil.html`.

## Estrutura do repositório

- `src/religiao_politica`: código reutilizável do projeto.
- `scripts`: rotinas executáveis de coleta, transformação, análise e apresentação.
- `data/raw`: arquivos originais baixados de fontes públicas.
- `data/interim`: dados intermediários de limpeza e raspagem.
- `data/processed`: bases tratadas usadas pelos scripts analíticos.
- `outputs`: resultados agregados, testes estatísticos, mapas e bases auxiliares.
- `reports/figures`: gráficos exportados.
- `reports/presentation`: apresentação HTML final.
- `docs`: notas metodológicas e fontes de dados.

As pastas `data/raw`, `data/interim`, `data/processed`, `outputs/bases` e `.browser_state` não devem ser usadas como fonte de verdade no Git. Elas podem conter arquivos grandes, dados gerados ou estado local de navegador.

## Antes de clonar: instalar o Git

O Git é o programa que permite baixar o repositório, acompanhar mudanças e enviar contribuições de volta para o GitHub.

No Windows:

1. Acesse `https://git-scm.com/downloads/win`.
2. Baixe o instalador do Git for Windows.
3. Execute o instalador.
4. Pode manter as opções padrão na instalação.
5. Ao final, abra o PowerShell ou o Git Bash.
6. Verifique se o Git foi instalado:

```powershell
git --version
```

Se aparecer algo como `git version 2.x.x`, está tudo certo. Se o comando não for reconhecido, feche e abra novamente o terminal. Se ainda assim não funcionar, reinicie o computador.

## Como clonar o repositório

Para baixar o projeto na sua máquina, escolha uma pasta de trabalho e rode:

```powershell
git clone https://github.com/apce-org/estudos-eleicoes.git
cd estudos-eleicoes
```

Se você já usa chave SSH no GitHub, também pode clonar assim:

```powershell
git clone git@github.com:apce-org/estudos-eleicoes.git
cd estudos-eleicoes
```

Depois de clonar, todos os comandos abaixo devem ser executados dentro da pasta `estudos-eleicoes`.

## Instalação

Requisitos principais:

- Python 3.11 ou superior.
- Git.
- Acesso à internet para baixar dados públicos do TSE/IBGE.
- Chrome ou Chromium para rotinas de PJe/TSE com navegador.

Crie e ative o ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
```

Para verificar dependências básicas:

```powershell
.\.venv\Scripts\python.exe scripts\verify_environment.py
```

Para as rotinas com Playwright:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Fluxo recomendado

Execute os scripts a partir da raiz do repositório.

1. Baixar candidaturas do TSE:

```powershell
.\.venv\Scripts\python.exe scripts\download_tse_candidates.py --years 2012 2014 2016 2018 2020 2022 2024
```

2. Baixar votos, prestação de contas e tabela de municípios TSE-IBGE:

```powershell
.\.venv\Scripts\python.exe scripts\download_tse_votes_finance.py --years 2012 2014 2016 2018 2020 2022 2024
```

3. Montar base municipal de população:

```powershell
.\.venv\Scripts\python.exe scripts\build_municipal_population_base.py --tcu-years 2012 2014 2016 2018 2020 2021 2022 2024 --pnad-periods last
```

4. Montar bases de candidaturas:

```powershell
.\.venv\Scripts\python.exe scripts\build_christian_candidates_base.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\build_all_legislative_candidates_base.py --years 2012 2014 2016 2018 2020 2022 2024
```

5. Montar painéis de votos e financiamento:

```powershell
.\.venv\Scripts\python.exe scripts\build_christian_votes_municipality_panel.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\build_christian_campaign_finance_summary.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\build_all_campaign_finance_summary.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\build_christian_integrated_panel.py
```

6. Rodar análises estatísticas:

```powershell
.\.venv\Scripts\python.exe scripts\run_religion_politics_analyses.py
.\.venv\Scripts\python.exe scripts\analyze_christian_expense_types.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\analyze_comparative_expense_types.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\analyze_comparative_receipt_types.py --years 2012 2014 2016 2018 2020 2022 2024
```

7. Gerar mapas, gráficos e apresentação:

```powershell
.\.venv\Scripts\python.exe scripts\build_religion_growth_maps.py
.\.venv\Scripts\python.exe scripts\build_presentation_visual_assets.py --force-votes
.\.venv\Scripts\python.exe scripts\build_presentation.py
```

Abra `reports/presentation/religiao_politica_brasil.html` no navegador para ver a apresentação.

## Módulos principais

### `src/religiao_politica/config.py`

Centraliza caminhos do projeto, como `data/raw`, `data/processed`, `outputs`, `reports/figures` e `reports/presentation`. Também define anos padrão e URLs-base do TSE.

### `src/religiao_politica/tse.py`

Funções de apoio para trabalhar com dados eleitorais:

- valida e baixa arquivos ZIP com retomada de download;
- consulta recursos no CKAN de dados abertos do TSE;
- baixa candidaturas, votação nominal, prestação de contas e tabela TSE-IBGE;
- lê CSVs e TXT dentro de ZIPs oficiais do TSE.

### `src/religiao_politica/religious_terms.py`

Contém o classificador textual inicial de sinais cristãos. Ele procura padrões como cargos religiosos, identidades cristãs, termos católicos e evangélicos em campos públicos das candidaturas. A saída informa se houve sinal, quais categorias apareceram, quais termos foram encontrados e a força do sinal.

### `src/religiao_politica/analysis.py`

Agrupa funções analíticas reutilizáveis:

- normalização de texto;
- classificação da esfera do cargo em municipal, estadual ou federal;
- classificação simplificada de ideologia partidária;
- remoção de duplicidades de candidaturas;
- cálculo de taxas seguras;
- testes t de Welch;
- ANOVA de um fator;
- escrita padronizada de CSV em UTF-8 com BOM.

### `src/religiao_politica/ibge_population.py`

Baixa e combina dados municipais do IBGE/SIDRA:

- cadastro oficial de municípios;
- estimativas populacionais usadas pelo TCU;
- população residente do Censo 2022;
- recortes municipais disponíveis na PNAD Contínua;
- painel final por município e ano.

## Scripts de coleta

- `download_tse_candidates.py`: baixa ZIPs de candidaturas do TSE para os anos selecionados.
- `download_tse_votes_finance.py`: baixa votação nominal, prestação de contas e tabela de correspondência TSE-IBGE.
- `download_ibge_municipal_population.py`: baixa dados municipais de população do IBGE/SIDRA em CSV bruto.

## Scripts de construção de bases

- `build_candidate_summary.py`: cria resumo exploratório de sinais religiosos nas candidaturas.
- `build_christian_candidates_base.py`: filtra candidaturas com sinal cristão e salva base detalhada e resumo agregado.
- `build_all_legislative_candidates_base.py`: monta o universo de candidaturas legislativas, com indicador de sinal cristão.
- `build_municipal_population_base.py`: monta painel municipal com população e metadados territoriais.
- `build_christian_votes_municipality_panel.py`: cruza candidaturas cristãs com votação nominal por município.
- `build_christian_campaign_finance_summary.py`: resume receitas e despesas de candidatos cristãos.
- `build_all_campaign_finance_summary.py`: resume receitas e despesas de todos os candidatos legislativos.
- `build_christian_integrated_panel.py`: integra candidaturas, votos e financiamento em uma base única.

## Scripts de análise

- `run_religion_politics_analyses.py`: gera cruzamentos centrais, testes estatísticos, bases de análise e saídas agregadas em `outputs`.
- `analyze_christian_expense_types.py`: analisa tipos de despesa dentro do grupo de candidatos cristãos, por resultado eleitoral e ideologia.
- `analyze_comparative_expense_types.py`: compara estrutura de despesas entre cristãos e não cristãos, além de recortes por resultado e ideologia.
- `analyze_comparative_receipt_types.py`: compara estrutura de receitas por religião, resultado eleitoral e ideologia.

## Scripts de mapas e apresentação

- `build_religion_growth_maps.py`: gera mapas HTML de crescimento de candidaturas cristãs por UF e município.
- `build_brazil_map_demo.py`: cria um mapa demonstrativo do Brasil para validação visual.
- `build_presentation_visual_assets.py`: gera mapas, gráficos e arquivos auxiliares usados na apresentação.
- `build_presentation.py`: monta a apresentação HTML final.
- `generate_qrcode.py`: gera QR Code em PNG para uma URL informada.

## Scripts de PJe/TSE

- `build_public_property_propaganda_process_sample.py`: monta amostra de processos de propaganda em bens públicos.
- `scrape_tse_pje_public_processes.py`: raspa páginas públicas do PJe/TSE usando Playwright, com intervenção manual para CAPTCHA quando necessário.
- `scrape_tse_pje_public_processes_selenium.py`: alternativa em Selenium para o mesmo fluxo, incluindo modos com busca manual, perfil do Chrome e debugger remoto.
- `capture_tse_pje_current_page_selenium.py`: captura texto e URL da página atualmente aberta em uma sessão Selenium/Chrome conectada.

Exemplo de Chrome com debugger remoto:

```powershell
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$PWD\.browser_state\chrome_debug_tse"
.\.venv\Scripts\python.exe scripts\capture_tse_pje_current_page_selenium.py --debugger-address 127.0.0.1:9222
```

## Saídas analíticas

Os resultados são exportados para `outputs`. Em geral:

- `outputs/*.csv`: tabelas agregadas, testes estatísticos e resumos.
- `outputs/maps`: mapas HTML.
- `outputs/presentation_assets`: dados intermediários usados pela apresentação.
- `outputs/bases`: bases largas usadas nas análises. Esta pasta é ignorada pelo Git porque pode conter arquivos muito grandes.

Para incluir renda média, escolaridade ou outras variáveis municipais nas análises, salve uma base em `data/processed/municipios_socioeconomicos.csv` ou `.parquet` com a coluna `codigo_ibge_municipio` e, se possível, `ano`. O script incorporará automaticamente as colunas numéricas encontradas.

## Observações metodológicas

O classificador de sinal religioso é uma aproximação baseada em termos presentes em campos públicos de candidatura. Ele é útil para medir padrões em escala, mas não substitui validação qualitativa.

Principais cuidados:

- termos como "Deus" ou "Jesus" podem indicar identidade religiosa, slogan, nome de localidade ou uso retórico;
- cargos religiosos declarados no nome de urna tendem a ser sinais mais fortes;
- partidos são classificados em grupos ideológicos simplificados, úteis para comparação exploratória, mas não para análise fina de trajetória partidária;
- resultados estatísticos dependem da qualidade dos dados baixados, da cobertura dos anos e da consistência das rubricas do TSE;
- conclusões substantivas devem ser sustentadas por revisão manual, documentação das regras e, quando possível, fontes externas.

## Colaboração

Antes de abrir mudanças grandes, combine o escopo com a equipe. Para contribuições:

1. Crie uma branch a partir de `main`.
2. Rode apenas os scripts necessários para sua tarefa.
3. Não versione bases grandes, arquivos de navegador, ambientes virtuais ou arquivos locais sensíveis.
4. Atualize este README ou `docs/` quando mudar metodologia, dependências ou fluxo de execução.
5. Abra um pull request descrevendo objetivo, arquivos alterados e saídas geradas.

O `.gitignore` já evita os principais arquivos gerados. Se algum CSV ou ZIP grande aparecer no `git status`, trate como artefato local e não como código-fonte.
