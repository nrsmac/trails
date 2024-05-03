import os
from unittest.mock import patch

from bs4 import BeautifulSoup
from pydantic_core import Url

from trails.sources.oregon_hikers import (
    OH_SOURCE_DIR,
    OregonHikersHike,
    _parse_hike_soup_to_dict,
)

example_hike_data = {
    "title": "Test Hike",
    "url": "https://www.oregonhikers.org/test",
    "start_point_name": "Start Point",
    "start_point_url": "https://www.oregonhikers.org/start",
    "end_point_name": "End Point",
    "end_point_url": "https://www.oregonhikers.org/end",
    "trail_log_url": "https://www.oregonhikers.org/log",
    "hike_type": "Loop",
    "distance_in_miles": "5 miles",
    "elevation_gain_in_feet": "500 feet",
    "high_point_in_feet": "1000 feet",
    "difficulty": "Moderate",
    "seasons": "All",
    "family_friendly": "Yes",
    "backpackable": "No",
    "crowded": "No",
    "description": "A test hike",
}


def test_OregonHikersHikePage_model():
    hike = OregonHikersHike(**example_hike_data)
    assert hike.title == "Test Hike"
    assert hike.start_point_url == Url("https://www.oregonhikers.org/start")
    assert hike.end_point_url == Url("https://www.oregonhikers.org/end")
    assert hike.trail_log_url == Url("https://www.oregonhikers.org/log")
    assert hike.elevation_gain_in_feet == 500
    assert hike.high_point_in_feet == 1000


def test_parse_hike_page():
    html = """
    <html>
        <body>
            <h1>Test Hike</h1>
            <div id="mw-content-text">
                <ul>
                    <li>Start point: <a href="/start" title="Start Point">Start Point</a></li>
                    <li>End point: <a href="/end" title="End Point">End Point</a></li>
                    <li>Trail Log: <a href="/log">Log</a></li>
                    <li>Hike Type: Loop</li>
                    <li>Distance: 5 miles</li>
                    <li>Elevation gain: 500 feet</li>
                    <li>High point: 1000 feet</li>
                    <li>Difficulty: Moderate</li>
                    <li>Seasons: All</li>
                    <li>Family Friendly: Yes</li>
                    <li>Backpackable: No</li>
                    <li>Crowded: No</li>
                </ul>
                <p>Description</p>
            </div>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    result = _parse_hike_soup_to_dict(soup)

    assert result == {
        "title": "Test Hike",
        "start_point_name": "Start Point",
        "start_point_url": "https://www.oregonhikers.org/start",
        "end_point_name": "End Point",
        "end_point_url": "https://www.oregonhikers.org/end",
        "trail_log_url": "https://www.oregonhikers.org/log",
        "hike_type": "Hike Type: Loop",
        "distance_in_miles": "Distance: 5 miles",
        "elevation_gain_in_feet": "Elevation gain: 500 feet",
        "high_point_in_feet": "High point: 1000 feet",
        "difficulty": "Difficulty: Moderate",
        "seasons": "Seasons: All",
        "family_friendly": "Family Friendly: Yes",
        "backpackable": "Backpackable: No",
        "crowded": "Crowded: No",
        "description": "Description",
    }
