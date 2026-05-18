from __future__ import annotations

import folium
import geopandas as gpd
import requests

from religiao_politica.config import FIGURES_DIR, RAW_DIR

IBGE_STATES_GEOJSON_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    "?intrarregiao=UF&formato=application/vnd.geo+json&qualidade=minima"
)


def main() -> None:
    geojson_path = RAW_DIR / "ibge_malha_ufs_minima.geojson"
    if not geojson_path.exists():
        response = requests.get(IBGE_STATES_GEOJSON_URL, timeout=120)
        response.raise_for_status()
        geojson_path.write_text(response.text, encoding="utf-8")

    states = gpd.read_file(geojson_path)
    states = states.to_crs(epsg=4326)
    states["uf"] = states["codarea"].astype(str)
    states["uf_code"] = states["codarea"].astype(int)

    center = [-14.235, -51.9253]
    brazil_map = folium.Map(location=center, zoom_start=4, tiles="cartodbpositron")
    folium.Choropleth(
        geo_data=states,
        data=states,
        columns=["uf", "uf_code"],
        key_on="feature.properties.codarea",
        fill_color="YlOrRd",
        fill_opacity=0.75,
        line_opacity=0.35,
        legend_name="Código IBGE da UF",
    ).add_to(brazil_map)

    folium.GeoJson(
        states,
        tooltip=folium.GeoJsonTooltip(fields=["codarea"]),
        name="Estados",
    ).add_to(brazil_map)

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    output = FIGURES_DIR / "mapa_brasil_demo.html"
    brazil_map.save(output)
    print(output)


if __name__ == "__main__":
    main()
