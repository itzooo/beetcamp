import pytest

from beetsplug.bandcamp._metaguru import Metaguru

pytestmark = pytest.mark.parsing


def test_style(beets_config):
    guru = Metaguru({"publisher": {"genre": "bandcamp.com/tag/folk"}}, beets_config)
    assert guru.style == "folk"


@pytest.mark.parametrize(
    ("keywords", "expected"),
    [
        ([], None),
        (["crazy music"], None),
        (["ambient. techno. industrial"], "ambient, techno, industrial"),
        (["Drum & Bass"], "drum and bass"),
        (["Techno."], "techno"),
        (["E.B.M"], "ebm"),
        (["#House #Techno #Trance"], "house, techno, trance"),
        (["90's House"], "90's house"),
        (["hardcore"], "hardcore"),
        (["hardtrance", "hard trance"], "hard trance"),
        (["hard trance", "trance"], "hard trance"),
        (["hard trance", "hardtrance"], "hard trance"),
    ],
)
def test_genre_variations(keywords, expected, beets_config):
    beets_config["genre"]["mode"] = "psychedelic"
    beets_config["genre"]["always_include"] = ["^hard", "core$"]
    guru = Metaguru({"keywords": keywords}, beets_config)
    assert guru.genre == expected


TEST_KEYWORDS = dict(
    single_word_valid_kw=["house"],
    double_word_valid_kw=["tech house"],
    double_word_valid_separately=["techno house"],
    only_last_word_valid=["crazy techno"],
)


@pytest.fixture(params=TEST_KEYWORDS.keys())
def keyword_type(request):
    return request.param


@pytest.fixture
def keywords(keyword_type):
    return TEST_KEYWORDS[keyword_type]


@pytest.fixture(scope="module")
def modes_spec():
    base_spec = dict(
        single_word_valid_kw=True,
        double_word_valid_kw=True,
        double_word_valid_separately=False,
        only_last_word_valid=False,
    )
    modes = {}
    modes["classical"] = base_spec
    modes["progressive"] = {**base_spec, "double_word_valid_separately": True}
    modes["psychedelic"] = {**modes["progressive"], "only_last_word_valid": True}
    return modes


@pytest.fixture(params=["classical", "progressive", "psychedelic"])
def mode(request):
    return request.param


@pytest.fixture
def mode_result(keywords, keyword_type, modes_spec, mode):
    return keywords if modes_spec[mode][keyword_type] else []


def test_genre(keywords, mode, mode_result, beets_config):
    config = beets_config["genre"]
    config["mode"] = mode
    assert list(Metaguru.get_genre(keywords, config)) == mode_result


@pytest.mark.parametrize(
    ("capitalize", "maximum", "expected"),
    [
        (True, 0, "Folk, House, Grime, Trance"),
        (True, 3, "Folk, House, Grime"),
        (False, 2, "folk, house"),
    ],
)
def test_beets_config(capitalize, maximum, expected, beets_config):
    meta = {
        "keywords": ["paris", "dubstep", "folk", "House", "grime", "Trance"],
        "publisher": {"genre": "https://bandcamp.com/tag/dubstep"},
    }
    beets_config["genre"]["capitalize"] = capitalize
    beets_config["genre"]["maximum"] = maximum
    guru = Metaguru(meta, beets_config)

    assert guru.style == ("Dubstep" if capitalize else "dubstep")
    assert guru.genre == expected
