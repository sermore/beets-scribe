import json
import logging
from unittest.mock import patch
import pytest

from context import beetsplug
from beetsplug import scribe

logger = logging.getLogger()


@pytest.fixture
def mock_response():
    with patch("requests.get") as mock_get:
        yield mock_get


def test_google_search_ok(mock_response):
    with open(
        "tests/data/google_ok_resp.json",
        "rb",
    ) as data:
        mock_response.return_value.status_code = 200
        mock_response.return_value.json.return_value = json.load(data)

        res = scribe.google_search(
            logger, "beethoven op. 101", "XXX", "123", num_results=10
        )
        assert res == (
            200,
            [
                "https://imslp.org/wiki/Piano_Sonata_No.28,_Op.101_(Beethoven,_Ludwig_van)",
                "https://s9.imslp.org/files/imglnks/usimg/2/23/IMSLP03165-Beethoven-PianoSonataNo17Lebert.pdf",
                "https://imslp.org/wiki/Template:Piano_Sonatas_(Beethoven,_Ludwig_van)",
                "https://imslp.org/wiki/Adagios_de_L._van_Beethoven,_Op.101_(Brisson,_Fr%C3%A9d%C3%A9ric)",
                "https://vmirror.imslp.org/files/imglnks/usimg/6/63/IMSLP02019-Beethoven-op.101-cotta.pdf",
                "https://imslp.org/wiki/32_Piano_Sonatas_(Beethoven%2C_Ludwig_van)",
                "https://imslp.org/wiki/Category:Cornell,_John_Henry/Translator",
                "https://imslp.org/wiki/Category:Beethoven,_Ludwig_van/Collections_With",
                "https://imslp.org/wiki/Category:Scores_published_by_Ullstein",
                "https://imslp.org/wiki/Category:Schnabel,_Artur/Editor",
            ],
        )
        mock_response.assert_called_once()


def test_google_search_fail(mock_response):
    with open(
        "tests/data/google_failed_resp.json",
        "rb",
    ) as data:
        mock_response.return_value.status_code = 429
        mock_response.return_value.json.return_value = json.load(data)

        res = scribe.google_search(logger, "mozart La Bataille", "XXX", "123")
        assert res == (429, [])
        mock_response.assert_called_once()


def test_scrape_ok(mock_response):
    with open(
        "tests/data/Piano Sonata No.23, Op.57 (Beethoven, Ludwig van) - IMSLP.html",
        "rb",
    ) as data:
        mock_response.return_value.status_code = 200
        mock_response.return_value.text = data.read()

        res = scribe.imslp_scrape(
            logger,
            "https://imslp.org/wiki/Piano_Sonata_No.23,_Op.57_(Beethoven,_Ludwig_van)",
        )
        assert res == {
            "sc_genre_categories": [
                "Sonatas",
                "For piano",
                "Scores featuring the piano",
                "For 1 player",
                "For strings (arr)",
                "Scores featuring string ensemble (arr)",
                "For 2 violins, viola, cello, double bass, piano (arr)",
                "Scores featuring the violin (arr)",
                "Scores featuring the viola (arr)",
                "Scores featuring the cello (arr)",
                "Scores featuring the double bass (arr)",
                "Scores featuring the piano (arr)",
                "For 6 players (arr)",
                "For 2 pianos (arr)",
                "For 2 players (arr)",
                "For organ (arr)",
                "For 1 player (arr)",
                "Scores featuring the organ (arr)",
            ],
            "sc_first_publication": "1807",
            "sc_work_style": "Classical",
        }
        mock_response.assert_called_once()


def test_scrape_fail(mock_response):
    with open(
        "tests/data/Category_Cornell, John Henry∕Translator - IMSLP.html",
        "rb",
    ) as data:
        mock_response.return_value.status_code = 200
        mock_response.return_value.text = data.read()

        res = scribe.imslp_scrape(
            logger,
            "https://imslp.org/wiki/Category:Cornell,_John_Henry/Translator",
        )
        assert res == {}
        mock_response.assert_called_once()


def test_longest_repeating_non_overlapping():
    assert scribe.longest_substring("banana") == "an"
    assert scribe.longest_substring("BCD,BBB,ABCD,BBB,BBB,") == "BCD,BBB,"
    assert (
        scribe.longest_substring("Dal Pierotto,Piero,Dal Piero, Pierotto")
        == "Dal Piero"
    )


def test_strip_repeated_elements():
    assert (
        scribe.strip_repeated_elements(
            "Dal Pierotto,Piero,Dal Piero, Pierotto", len("Dal Pierotto Piero")
        )
        == "Dal Pierotto,Piero,Dal Piero, Pierotto"
    )
    # fail with "Dal Pierotto, Piero, Dal Piero, Pierotto, Dal Pierotto, Piero, Dal Pierotto, Pierotto"
    assert (
        scribe.strip_repeated_elements(
            "Dal Pierotto, Pierotto, Dal Piero, Pierotto, Dal Pierotto, Piero, Dal Pierotto, Pierotto",
            len("Piero Dal Pierotto"),
        )
        == "Dal Piero, Pierotto, Dal Pierotto, Pierotto"
    )
    assert (
        scribe.strip_repeated_elements(
            "Rossini, Gioachino, Rossini, Gioachino, Rossini, Gioachino",
            len("Gioachino Rossini"),
        )
        == "Rossini, Gioachino"
    )
