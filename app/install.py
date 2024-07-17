import os
import pathlib
import sqlite3
from copy import deepcopy

import numpy as np
import pandas as pd
from pydantic import TypeAdapter

from app.config import settings
from app.schemas.film import HTMLFilmInDB
from app.utils.url import generate_unique_url


def update_db():
    """Create a SQLite database from the film CSV file."""
    # Define the column names explicitly
    df_column_names = [
        "dx_extract",
        "dx_full",
        "name",
        "og_film_or_information",
        "manufacturer",
        "reliability",
        "country",
        "begin_year",
        "end_year",
        "distributor",
        "availability",
        "picture",
    ]

    DB_TABLE_NAME = "films"
    db_column_names = deepcopy(df_column_names)
    db_column_names.append("url_name")

    # db_column_names = [
    #     "dx_extract",
    #     "dx_full",
    #     "name",
    #     "url_name",
    #     "og_film_or_information",
    #     "manufacturer",
    #     "reliability",
    #     "country",
    #     "begin_year",
    #     "end_year",
    #     "distributor",
    #     "availability",
    #     "picture",
    # ]

    print(f"db_column_names: {db_column_names}")
    # Load the CSV file
    df: pd.DataFrame = pd.read_csv(
        os.path.join(settings.FILM_DATABASE_REPO_DIR, "film_database.csv"),
        sep=";",
        names=df_column_names,
        skiprows=1,  # Skip the first row if it's a header
        na_values=["", " ", "NaN", "NULL"],
        on_bad_lines="warn",
        engine="python",
    )  # Use Python engine for better handling of irregular rows

    # If null values, fill with native python None instead of Numpy "NaN" values
    df = df.where(df.notnull(), None)

    # Availability in integer
    for column_name in ["availability"]:
        # df[column_name] = pd.to_numeric(df[column_name], errors='coerce', downcast="unsigned")
        df[column_name] = df[column_name].fillna(-1)
        df[column_name] = df[column_name].astype(int)
        df[column_name] = df[column_name].astype(str)
        df[column_name] = df[column_name].replace("-1", np.nan)

    # Reliability in float (might be useful later)
    for column_name in ["reliability"]:
        df[column_name] = df[column_name].astype(float)
        df[column_name] = df[column_name].fillna("")
        # df[column_name] = df[column_name].astype(str)

    #         df[col] = df[col].fillna(-1)
    # df[col] = df[col].astype(int)
    # df[col] = df[col].astype(str)
    # df[col] = df[col].replace('-1', np.nan)

    for column_name in ["dx_extract", "dx_full"]:
        df[column_name] = df[column_name].fillna(0)
        df[column_name] = df[column_name].astype(int)
        df[column_name] = df[column_name].fillna("").astype(int)
        df[column_name] = df[column_name].replace(0, "")
        df[column_name] = df[column_name].astype(str)
        # df[column_name] = df[column_name].fillna('').astype(int)
        # df[column_name] = df[column_name].fill

    # TODO reliability in float/int ?
    # df['reliability'] = df['reliability'].fillna('').astype(int)

    # Add leading zeros to DX codes
    df["dx_full"] = df["dx_full"].str.zfill(6)
    df["dx_extract"] = df["dx_extract"].str.zfill(4)
    # Remplacer les valeurs composées uniquement de zéros par None
    df["dx_full"] = df["dx_full"].apply(lambda x: None if x == "000000" else x)
    df["dx_extract"] = df["dx_extract"].apply(lambda x: None if x == "0000" else x)

    # Strip leading and trailing spaces from string columns
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    # Encode film name
    df["url_name"] = df["name"].apply(generate_unique_url)

    # Save the dataframe to a SQLite database
    pathlib.Path(settings.DB_SQLITE_FILEPATH).parent.mkdir(parents=True, exist_ok=True)
    # assert False, pathlib.Path(settings.DB_SQLITE_FILEPATH).parent
    # assert False, settings.DB_SQLITE_FILEPATH
    db_file_connection = sqlite3.connect(settings.DB_SQLITE_FILEPATH)
    # df.to_sql('films', db_file_connection, if_exists='replace', index=False)

    # # Convertir les NaN en chaînes vides et s'assurer que les colonnes sont des chaînes
    # df = df.fillna("").astype(str)

    # Convertir les NaN en NULL values en SQL et s'assurer que les colonnes sont des chaînes
    # df = df.replace("", None)
    # df = df.applymap(lambda x: None if isinstance(x, str) and x == "" else x)

    print(df[0:10])
    print(df[2700:2710])
    print(df.iloc[66]["reliability"])

    # Prepare database table with fulltext index
    cursor = db_file_connection.cursor()
    cursor.execute(f"DROP TABLE IF EXISTS {DB_TABLE_NAME}")
    create_table_query = f'CREATE VIRTUAL TABLE IF NOT EXISTS {DB_TABLE_NAME} USING FTS5({", ".join(db_column_names)});'
    print(create_table_query)
    cursor.execute(create_table_query)
    # cursor.execute('create virtual table films using fts5(title, genre, rating, tokenize="porter unicode61");')

    # Charger le DataFrame dans SQLite
    df.to_sql(name=DB_TABLE_NAME, con=db_file_connection, if_exists="append", index=False)

    # # Replace empty strings by null values
    # for column in db_column_names:
    #     db_query = f"UPDATE films SET {column} = CASE WHEN {column} = '' THEN NULL ELSE {column} END;"
    #     cursor.execute(db_query)

    db_file_connection.commit()

    # Check database integrity and film column format
    rows = cursor.execute("SELECT * from films").fetchall()
    column_names = [description[0] for description in cursor.description]
    films = [dict(zip(column_names, row, strict=False)) for row in rows]
    print(len(films))
    for film in films[47:49]:
        print(film)
    # ta = TypeAdapter(list[Film])
    # film_list = ta.validate_python(films)
    ta = TypeAdapter(list[HTMLFilmInDB])
    film_list = ta.validate_python(films)
    for film in film_list[47:49]:
        print(film)
    # print("Database integrity OK!")

    # Create the manufacturer table index
    cursor.execute("DROP TABLE IF EXISTS film_types")
    cursor.execute("CREATE TABLE IF NOT EXISTS film_types (dx_min INTEGER, dx_max INTEGER, label);")
    insert_film_type_query = """
    INSERT INTO film_types (dx_min, dx_max, label)
    VALUES
    (0, 1, 'Fuji Acros/Neopan type'),
    (5, 6, 'Orwo Owopan film'),
    (15, 22, 'Agfa Gevaert B&W film'),
    (21, 25, 'Agfa Gevaert APX or Ortho type film'),
    (24, 32, 'Agfa Gevaert B&W film'),
    (31, 46, 'Sakura & Konica film'),
    (45, 128, 'Agfa Gevaert chrome (slide) film'),
    (63, 80, 'Kodak Technical film'),
    (95, 112, 'Kodak IR film'),
    (127, 144, 'Fuji Fujicolor/Superia type film'),
    (143, 160, 'Svema Russian film'),
    (159, 176, 'Fuji Fujicolor Pro 160 type film'),
    (175, 192, 'Kodak Surveillance Film'),
    (191, 208, 'Fuji Fujicolor Superia/Venus type film'),
    (255, 272, 'Konica Minolta chrome film'),
    (271, 288, 'Agfa Gevaert color film'),
    (287, 304, 'Ferrania Scotch Color AT'),
    (319, 336, 'Kodak Ektachrome type film'),
    (367, 384, 'Kodak Ektachrome/Elitechrome type film'),
    (383, 400, 'Ferrania Imation Chrome'),
    (415, 432, 'Konica Minolta Centuria type film'),
    (447, 464, 'Konica Minolta VX type film'),
    (484, 501, 'Agfa / Perutz basic color film (Agfacolor type)'),
    (511, 528, 'Fuji Fujichrome Velvia/Provia type film'),
    (543, 560, 'Fuji Fujichrome Provia/Sensia type film'),
    (559, 576, 'Fuji Fujicolor Superia type film'),
    (575, 592, 'Fuji Fujicolor Super G/Superia/NP* type film'),
    (623, 640, 'Fuji Fujicolor Superia/Venus type film'),
    (639, 656, 'Konica Minolta IMPRESA film'),
    (671, 688, 'Fuji Fujichrome RSP type'),
    (687, 704, 'Kodak 800 ISO Max/Portra/Supra film'),
    (721, 741, 'Agfa Gevaert Agfacolor-N/Ultra technology'),
    (740, 753, 'Agfa Gevaert Optima films (and Polaroid branded film)'),
    (751, 768, 'Agfa Gevaert (and Perutz) Agfacolor type film'),
    (783, 801, 'Agfa Gevaert Optima type film'),
    (799, 816, 'Konica Minolta VX/LV/JX/XG type, and IMPRESA, Centuria First gen film'),
    (831, 864, 'Kodak Ektachrome type film'),
    (900, 976, 'Lucky Color'),
    (1023, 1040, 'Kodak "X" films : Plus-X, Double-X, Tri-X...'),
    (1055, 1072, 'Ferrania Scotch Color ATG/EXL'),
    (1071, 1088, 'Kodak T-grain (Tmax) film'),
    (1087, 1104, 'ERA Chinese film'),
    (1103, 1170, 'Kodak technical film ?'),
    (1247, 1263, 'Kodak B&W chromogenic films and Gold type film'),
    (1262, 1312, 'Kodak first generation Portra/VR type film'),
    (1311, 1344, 'Kodak first generation Gold/Max/Ultima type film'),
    (1343, 1360, 'Kodak Kodachrome film'),
    (1359, 1376, 'Ferrania Imation Color HP'),
    (1375, 1408, 'Ferrania Imaging Color FG (and Foma own films, or Foma cartridges for rebranded films)'),
    (1407, 1440, 'Chineses films : Shenguang, Shanghai, Seagull or Rainbow'),
    (1439, 1456, 'Lucky B&W Chinese film'),
    (1487, 1504, 'Kodak "Digital" film'),
    (1503, 1536, 'Kodak Royal/Elite/High Definition type film'),
    (1535, 1552, 'Kodak Max/Gold/Portra film, and cheap ColorPlus'),
    (1551, 1568, 'Kodak basic Color Negative film'),
    (1567, 1584, 'Xiamen FUDA chinese film'),
    (1599, 1616, 'Lucky Color Super'),
    (1727, 1735, 'Harman/Ilford Technical film'),
    (1734, 1744, 'SFX type film and Delta 3200'),
    (1743, 1760, 'Harman/Ilford Pan films, Delta, and HP5(+)/FP4(+)'),
    (1759, 1770, 'Harman/Ilford chromogenic XP type films'),
    (1769, 1775, 'Kentmere film'),
    (1791, 1808, 'Kodak Vericolor/Portra type film'),
    (1807, 1825, 'Agfa Gevaert Vista/HDC type film'),
    (1839, 1857, 'Perutz (Agfa) SC film & Agfa Vista. Used by a lot of rebranded film'),
    (1855, 1872, 'Kodak Kodachrome type film'),
    (1919, 1952, 'Orwo CNS type film'),
    (1951, 1968, 'Orwo CNN/OCN type film'),
    (1967, 1984, 'Orwo PAN film'),
    (2064, 2067, 'Kodak Codakolor II'),
    (2400, 2405, 'Kodak Vericolor'),
    (3296, 3364, 'Rebranded Kodak film for Jean Coutu Pharmacies in Canada');
    """.strip()
    cursor.execute(insert_film_type_query)
    cursor.execute("CREATE INDEX dx_min_max_IDX ON film_types(dx_min, dx_max);")
    db_file_connection.commit()

    cursor.execute("VACUUM;")

    # Don't need the dataframe anymore
    del df


if __name__ == "__main__":
    update_db()
    print("Done!")
