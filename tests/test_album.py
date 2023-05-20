import pytest
from beetsplug.bandcamp.album import AlbumName


@pytest.mark.parametrize(
    ("name", "extras", "expected"),
    [
        ("Album - Various Artists", [], "Album"),
        ("Various Artists - Album", [], "Album"),
        ("Various Artists Album", [], "Various Artists Album"),
        ("Label Various Artists Album", [], "Label Various Artists Album"),
        ("Album EP", [], "Album EP"),
        ("Album [EP]", [], "Album EP"),
        ("Album (EP)", [], "Album EP"),
        ("Album E.P.", [], "Album E.P."),
        ("Album LP", [], "Album LP"),
        ("Album [LP]", [], "Album LP"),
        ("Album (LP)", [], "Album LP"),
        ("[Label] Album EP", ["Label"], "Album EP"),
        ("Artist - Album EP", ["Artist"], "Album EP"),
        ("Label | Album", ["Label"], "Album"),
        ("Tweaker-229 [PRH-002]", ["PRH-002", "Tweaker-229"], ""),
        ("Album (limited edition)", [], "Album"),
        ("Album - VARIOUS ARTISTS", [], "Album"),
        ("Drepa Mann", [], "Drepa Mann"),
        ("Some ft. Some ONE - Album", ["Some ft. Some ONE"], "Album"),
        ("Some feat. Some ONE - Album", ["Some feat. Some ONE"], "Album"),
        ("Healing Noise (EP) (Free Download)", [], "Healing Noise EP"),
        ("[MCVA003] - VARIOUS ARTISTS", ["MCVA003"], ""),
        ("Drepa Mann [Vinyl]", [], "Drepa Mann"),
        ("Drepa Mann  [Vinyl]", [], "Drepa Mann"),
        ("The Castle [BLCKLPS009] Incl. Remix", ["BLCKLPS009"], "The Castle"),
        ("The Castle [BLCKLPS009] Incl. Remix", [], "The Castle [BLCKLPS009]"),
        ('Anetha - "Ophiuchus EP"', ["Anetha"], "Ophiuchus EP"),
        ("Album (FREE DL)", [], "Album"),
        ("Album (Single)", [], "Album"),
        (
            "Dax J - EDLX.051 Illusions Of Power",
            ["EDLX.051", "Dax J"],
            "Illusions Of Power",
        ),
        ("WEAPONS 001 - VARIOUS ARTISTS", ["WEAPONS 001"], ""),
        ("Diva Hello", [], "Diva Hello"),
        ("RR009 - Various Artist", ["RR009"], ""),
        ("Diva (Incl. some sort of Remixes)", [], "Diva"),
        ("HWEP010 - MEZZ - COLOR OF WAR", ["HWEP010", "MEZZ"], "COLOR OF WAR"),
        ("O)))Bow 1", [], "O)))Bow 1"),
        ("hi'Hello", ["hi"], "'Hello"),
        # only remove VA if album name starts or ends with it
        ("Album VA", [], "Album"),
        ("VA Album", [], "Album"),
        ("Album VA001", [], "Album VA001"),
        ("Album VA 03", [], "Album VA 03"),
        # remove (weird chars too) regardless of its position if explicitly excluded
        ("Album †INVI VA006†", ["INVI VA006"], "Album"),
        # keep label name
        ("Album (Label Refix)", [], "Album (Label Refix)"),
        ("Label-Album", [], "Label-Album"),
        # and remove brackets
        ("Album", [], "Album"),
    ],
)
def test_clean_name(name, extras, expected):
    assert AlbumName.clean(name, extras, label="Label") == expected