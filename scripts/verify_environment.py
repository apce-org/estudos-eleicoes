from __future__ import annotations

MODULES = [
    "pandas",
    "numpy",
    "polars",
    "duckdb",
    "requests",
    "unidecode",
    "rapidfuzz",
    "bs4",
    "lxml",
    "sidrapy",
    "basedosdados",
    "plotly",
    "altair",
    "matplotlib",
    "seaborn",
    "bokeh",
    "folium",
    "geopandas",
    "shapely",
    "pyproj",
    "pyogrio",
    "mapclassify",
    "contextily",
    "rasterio",
    "pydeck",
    "leafmap",
    "imageio",
    "jinja2",
    "sklearn",
    "statsmodels",
    "networkx",
    "religiao_politica.ibge_population",
]


def main() -> None:
    for module in MODULES:
        __import__(module)
        print(f"ok: {module}")


if __name__ == "__main__":
    main()
