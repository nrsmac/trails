import os
import re
from types import NoneType
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import (
    BaseModel,
    HttpUrl,
    computed_field,
    field_validator,
    model_validator,
)
from tqdm import tqdm
from loguru import logger as log

load_dotenv()
OH_SOURCE_DIR = os.getenv("HIKE_SOURCE_DIR", "./")


class OregonHikersHike(BaseModel):
    # TODO strip 'Seasons: ', 'Family Friendly: ', 'Crowded: ', etc
    title: str
    url: HttpUrl
    start_point_name: Optional[str]
    start_point_url: Optional[HttpUrl]
    end_point_name: Optional[str]
    end_point_url: Optional[HttpUrl]
    trail_log_url: Optional[HttpUrl]
    hike_type: Optional[str]
    distance_in_miles: str
    elevation_gain_in_feet: int
    high_point_in_feet: Optional[int]
    difficulty: str
    seasons: str
    family_friendly: Optional[str]
    backpackable: Optional[str]
    crowded: str
    description: str
    # TODO parse warnings like Poison Oak, Falling (stored as a table)
    # TODO Capture any maps, coordinates

    @model_validator(mode="after")
    def strip_newlines(self):
        for key, value in self.model_dump().items():
            if isinstance(value, str):
                self.__dict__[key] = value.strip().replace("\n", " ")

    @field_validator("elevation_gain_in_feet", "high_point_in_feet", mode="before")
    def extract_ints(cls, v):
        if isinstance(v, str):
            match = re.search(r"\d+", v)
            if match:
                return int(match.group())
        return v

    @field_validator(
        "url", "start_point_url", "end_point_url", "trail_log_url", mode="before"
    )
    def cast_url(cls, v):
        if isinstance(v, NoneType):
            return None
        elif v:
            try:
                return HttpUrl(v)
            except ValueError:
                return v


class OregonHikersSearchResult(BaseModel):
    title: str
    uri: str

    @computed_field
    @property
    def url(self) -> str:
        return f"https://www.oregonhikers.org/{self.uri}"


def _parse_hike_page(soup: BeautifulSoup) -> dict:
    """Parse hike page from OregonHikers.org

    Parameters
    ----------
    soup : BeautifulSoup
        soup from OregonHikers.org hike page. Ex:
        https://www.oregonhikers.org/field_guide/Bells_Mountain_Hike

    Returns
    -------
    dict
        Parsed hike page from OregonHikers.org
    """
    # TODO fix this mess
    title = soup.find("h1").text
    main_content = soup.find("div", id="mw-content-text")
    summary_ul = main_content.find("ul")
    summary_lis = summary_ul.find_all("li")
    start_point_li = next((li for li in summary_lis if "Start point" in li.text), None)
    start_point_name = start_point_li.find("a")["title"] if start_point_li else None
    start_point_url = start_point_li.find("a")["href"] if start_point_li else None
    if start_point_url:
        start_point_url = f"https://www.oregonhikers.org{start_point_url}"
    end_point_li = next((li for li in summary_lis if "End point" in li.text), None)
    end_point_name = end_point_li.find("a")["title"] if end_point_li else None
    end_point_url = end_point_li.find("a")["href"] if end_point_li else None
    if end_point_url:
        end_point_url = f"https://www.oregonhikers.org{end_point_url}"
    trail_log_url = None
    _trail_log_url = next((li for li in summary_lis if "Trail Log" in li.text), None)
    if _trail_log_url and _trail_log_url.find("a"):
        trail_log_url = _trail_log_url.find("a")["href"]
        trail_log_url = f"https://www.oregonhikers.org{trail_log_url}"
    hike_type = next((li for li in summary_lis if "Hike Type" in li.text), None)
    hike_type = hike_type.text if hike_type else None
    distance_in_miles = next((li for li in summary_lis if "Distance" in li.text), None)
    distance_in_miles = distance_in_miles.text if distance_in_miles else None
    elevation_gain_in_feet = next(
        (li for li in summary_lis if "Elevation gain" in li.text), None
    )
    elevation_gain_in_feet = (
        elevation_gain_in_feet.text if elevation_gain_in_feet else None
    )
    high_point_in_feet = next(
        (li for li in summary_lis if "High point" in li.text), None
    )
    high_point_in_feet = high_point_in_feet.text if high_point_in_feet else None
    difficulty = next((li for li in summary_lis if "Difficulty" in li.text), None)
    difficulty = difficulty.text if difficulty else None
    seasons = next((li for li in summary_lis if "Seasons" in li.text), None)
    seasons = seasons.text if seasons else None
    family_friendly = next(
        (li for li in summary_lis if "Family Friendly" in li.text), None
    )
    family_friendly = family_friendly.text if family_friendly else None
    backpackable = next((li for li in summary_lis if "Backpackable" in li.text), None)
    if backpackable:
        backpackable = backpackable.text if backpackable else None
    else:
        backpackable = None
    crowded = next((li for li in summary_lis if "Crowded" in li.text), None)
    crowded = crowded.text if crowded else None
    description = main_content.find("p").text

    return dict(
        title=title,
        start_point_name=start_point_name,
        start_point_url=start_point_url,
        end_point_name=end_point_name,
        end_point_url=end_point_url,
        trail_log_url=trail_log_url,
        hike_type=hike_type,
        distance_in_miles=distance_in_miles,
        elevation_gain_in_feet=elevation_gain_in_feet,
        high_point_in_feet=high_point_in_feet,
        difficulty=difficulty,
        seasons=seasons,
        family_friendly=family_friendly,
        backpackable=backpackable,
        crowded=crowded,
        description=description,
    )


def _parse_search_results(
    soup: BeautifulSoup,
) -> list[OregonHikersSearchResult]:
    """Parse search result table from OregonHikers.org

    Parameters
    ----------
    soup : BeautifulSoup
        soup from OregonHikers.org search results page. Ex:
        https://www.oregonhikers.org/field_guide/Special:Ask?q=[[Category%3ABackpackable%20Hikes]]&po=Difficulty%0D%0ADistance%0D%0AElevation%20gain&sort=&order=ASC&limit=50&usersearch=yes

    Returns
    -------
    list[OregonHikersSearchResult]
        List of search results from OregonHikers.org as they appear from semantic search results.
    """
    search_results = []
    table = soup.find("table", class_="wikitable")
    for row in table.find_all("tr")[1:]:
        row_link = row.find("a")
        title = row_link.text
        link = row_link["href"]
        search_results.append(
            OregonHikersSearchResult(
                title=title,
                uri=link,
            )
        )
    return search_results


def get_oh_sample_hikes_df() -> pd.DataFrame:
    """Return a df of sample hikes"""
    sample_hike_urls = [
        "https://www.oregonhikers.org/field_guide/Bells_Mountain_Hike",
        "https://www.oregonhikers.org/field_guide/Triple_Falls_Hike",
        "https://www.oregonhikers.org/field_guide/Acker_Lake_Loop_Hike",
        "https://www.oregonhikers.org/field_guide/Goat_Rocks_Traverse_Hike",
        "https://www.oregonhikers.org/field_guide/Broken_Top_Loop_Hike",
    ]
    df = pd.DataFrame()
    for url in sample_hike_urls:
        parsed_hike = get_hike_from_url(url)
        df = pd.concat([df, pd.DataFrame([parsed_hike.model_dump()])])
    return df


def get_oh_backpackable_hikes_df() -> pd.DataFrame:
    """Return a df of sample hikes"""
    search_results: list[OregonHikersSearchResult] = _get_backpackable_search_results()

    df = pd.DataFrame()
    for result in tqdm(search_results, desc="Getting hike: ", leave=True):
        parsed_hike = get_hike_from_url(result.url)
        df = pd.concat([df, pd.DataFrame([parsed_hike.model_dump()])])
    return df


def _get_backpackable_search_results() -> list[OregonHikersSearchResult]:
    """Get backpackable trails from OregonHikers.org"""
    backpackable_hikes_url = "https://www.oregonhikers.org/w/index.php?title=Special:Ask&limit=500&q=%5B%5BCategory%3ABackpackable+Hikes%5D%5D&p=format%3Dbroadtable&po=%3FDifficulty%0A%3FDistance%0A%3FElevation+gain%0A&sort=&order=ASC"

    try:
        response = requests.get(backpackable_hikes_url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)
    return _parse_search_results(BeautifulSoup(response.text, "html.parser"))


def _parse_exmaple_hike(example_hike_html_path: str) -> OregonHikersHike:
    with open(example_hike_html_path) as f:
        source = f.read()
    soup = BeautifulSoup(source, "html.parser")
    hike_contents = _parse_hike_page(soup)
    return OregonHikersHike(
        url="https://www.oregonhikers.org/field_guide/Bells_Mountain_Hike",
        **hike_contents,
    )


def _download_hike_source(url):
    """Download hike page from OregonHikers.org

    Parameters
    ----------
    url : str
        URL of the hike page to download. Ex: https://www.oregonhikers.org/field_guide/Bells_Mountain_Hike

    Returns
    -------
    str
        Path to the downloaded hike page"""
    if not os.path.exists(OH_SOURCE_DIR):
        os.makedirs(OH_SOURCE_DIR)
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)

    hike_name = url.split("/")[-1]
    source_file_name = f"{hike_name}.html"
    with open(os.path.join(OH_SOURCE_DIR, source_file_name), "w") as f:
        f.write(response.text)


def get_hike_from_url(url: str) -> OregonHikersHike:
    hike_name = url.split("/")[-1]
    hike_path = os.path.join(OH_SOURCE_DIR, f"{hike_name}.html")

    if os.path.exists(hike_path):
        log.info(f"[OregonHikers]: Hike {hike_name} already downloaded")
    else:
        log.info(f"[OregonHikers]: Downloading {hike_name}: {url}")
        _download_hike_source(url)

    with open(hike_path) as f:
        source = f.read()

    soup = BeautifulSoup(source, "html.parser")
    hike_contents = _parse_hike_page(soup)
    return OregonHikersHike(
        url=url,
        **hike_contents,
    )
