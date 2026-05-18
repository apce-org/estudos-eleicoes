# Fontes de dados

## TSE

- Candidaturas: arquivos `consulta_cand_{ano}.zip` do repositório de dados eleitorais.
- Resultados: arquivos de votação por seção, município e zona podem ser adicionados na mesma lógica.
- Prestação de contas: receitas e despesas ajudam a mapear redes de financiamento.

## Complementares

- IBGE/SIDRA: população, religião do Censo quando disponível, indicadores territoriais e socioeconômicos.
- IBGE malhas territoriais: municípios, unidades da federação, regiões imediatas/intermediárias e limites oficiais.
- Base dos Dados: espelho organizado de bases públicas brasileiras, inclusive dados eleitorais e demográficos.
- Câmara, Senado e assembleias: frentes parlamentares, proposições, votações e perfis biográficos.

## Mapas

- API de malhas do IBGE: limites oficiais de Brasil, UFs, municípios e recortes territoriais em GeoJSON.
- `geopandas`, `shapely` e `pyproj`: leitura, transformação e cruzamento geoespacial.
- `folium` e `leafmap`: mapas interativos em HTML, incluindo camadas e mapas de calor.
- `plotly`, `pydeck`, `mapclassify` e `contextily`: coropléticos, animações, classificação de intervalos e mapas base.

## Hipótese de classificação inicial

A versão inicial identifica sinais religiosos declarados em nome de urna, nome civil e ocupação. Isso mede uma presença pública, não uma filiação religiosa real. O estudo deve separar:

- sinal religioso explícito no registro eleitoral;
- vínculo institucional confirmado por fonte externa;
- atuação legislativa relacionada a religião;
- autodeclaração pública sem vínculo institucional.
