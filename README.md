# Religião e política no Brasil

Projeto para estudar o crescimento de políticos ligados a igrejas e religiões no processo eleitoral brasileiro.

## Estrutura

- `data/raw`: arquivos originais baixados de fontes públicas.
- `data/interim`: dados intermediários de limpeza.
- `data/processed`: bases prontas para análise e gráficos.
- `src/religiao_politica`: código reutilizável do projeto.
- `scripts`: tarefas executáveis de coleta, processamento e apresentação.
- `notebooks`: análises exploratórias.
- `reports/figures`: gráficos exportados.
- `reports/presentation`: apresentação HTML final.
- `docs`: notas metodológicas e fontes.

## Primeiros comandos

```powershell
.\.venv\Scripts\python.exe scripts\download_tse_candidates.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\download_ibge_municipal_population.py --years 2010 2022
.\.venv\Scripts\python.exe scripts\build_municipal_population_base.py --tcu-years 2012 2014 2016 2018 2020 2021 2022 2024 --pnad-periods last
.\.venv\Scripts\python.exe scripts\build_christian_candidates_base.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\download_tse_votes_finance.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\build_christian_votes_municipality_panel.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\build_christian_campaign_finance_summary.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\build_christian_integrated_panel.py
.\.venv\Scripts\python.exe scripts\build_all_legislative_candidates_base.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\build_all_campaign_finance_summary.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\run_religion_politics_analyses.py
.\.venv\Scripts\python.exe scripts\analyze_christian_expense_types.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\analyze_comparative_expense_types.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\analyze_comparative_receipt_types.py --years 2012 2014 2016 2018 2020 2022 2024
.\.venv\Scripts\python.exe scripts\build_public_property_propaganda_process_sample.py --years 2018 2020 2022 2024 --sample-size 385 --seed 20260511
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts\scrape_tse_pje_public_processes.py --limit 5 --open-sentence --captcha-retries 3
.\.venv\Scripts\python.exe scripts\scrape_tse_pje_public_processes_selenium.py --limit 5 --open-sentence --captcha-retries 3
.\.venv\Scripts\python.exe scripts\scrape_tse_pje_public_processes_selenium.py --limit 5 --open-sentence --captcha-retries 3 --manual-search
.\.venv\Scripts\python.exe scripts\scrape_tse_pje_public_processes_selenium.py --limit 5 --open-sentence --captcha-retries 3 --manual-search --pause-before-start
.\.venv\Scripts\python.exe scripts\scrape_tse_pje_public_processes_selenium.py --limit 5 --open-sentence --captcha-retries 3 --manual-search --chrome-user-data-dir "$env:LOCALAPPDATA\Google\Chrome\User Data" --profile-directory "Default"
.\.venv\Scripts\python.exe scripts\scrape_tse_pje_public_processes_selenium.py --limit 5 --open-sentence --captcha-retries 3 --manual-search --debugger-address 127.0.0.1:9222
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$PWD\.browser_state\chrome_debug_tse"
.\.venv\Scripts\python.exe scripts\capture_tse_pje_current_page_selenium.py --debugger-address 127.0.0.1:9222
.\.venv\Scripts\python.exe scripts\build_religion_growth_maps.py
.\.venv\Scripts\python.exe scripts\build_candidate_summary.py --years 2014 2018 2022 2024
.\.venv\Scripts\python.exe scripts\build_brazil_map_demo.py
.\.venv\Scripts\python.exe scripts\build_presentation_visual_assets.py --force-votes
.\.venv\Scripts\python.exe scripts\build_presentation.py
```

Abra `reports/presentation/religiao_politica_brasil.html` no navegador para ver a apresentação.

## Observação metodológica

O classificador inicial encontra sinais religiosos em campos públicos de candidatura. Ele é útil para uma primeira medição, mas deve ser validado com amostras manuais e fontes externas antes de sustentar conclusões fortes.

## Saídas analíticas

Os cruzamentos estatísticos são exportados para `outputs`. A subpasta `outputs/bases`
guarda as bases usadas nas análises, e os demais CSVs trazem resultados agregados,
testes-t de Welch e ANOVA por ano, esfera e grupo comparado.

Para incluir renda média e nível de instrução municipal nas análises, salve uma base
em `data/processed/municipios_socioeconomicos.csv` ou `.parquet` com a coluna
`codigo_ibge_municipio` e, se possível, `ano`. O script incorporará automaticamente
as colunas numéricas encontradas.
