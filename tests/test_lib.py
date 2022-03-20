import json
import os
import re
from collections import Counter, defaultdict, namedtuple
from functools import partial
from html import unescape
from itertools import groupby

import pytest
from beetsplug.bandcamp import BandcampPlugin
from beetsplug.bandcamp._metaguru import Metaguru
from rich.columns import Columns
from rich.traceback import install
from rich_tables.utils import border_panel, make_console, make_difftext, new_table, wrap

pytestmark = pytest.mark.lib

IGNORE_FIELDS = {
    "bandcamp_artist_id",
    "bandcamp_album_id",
    "art_url_id",
    "art_url",
    "tracks",
    "comments",
    "length",
    "price",
}

base_dir = "lib_tests"
target_dir = os.path.join(base_dir, "dev")
compare_against = os.path.join(base_dir, "4f5d074")
if not os.path.exists(target_dir):
    os.makedirs(target_dir)
install(show_locals=True, extra_lines=8, width=int(os.environ.get("COLUMNS", 150)))
console = make_console(stderr=True)

testfiles = sorted(filter(lambda x: x.endswith("json"), os.listdir("jsons")))


@pytest.fixture(params=testfiles)
def file(request):
    return request.param


Oldnew = namedtuple("Oldnew", ["old", "new", "diff"])
oldnew = defaultdict(list)


@pytest.fixture(scope="session")
def _report():
    yield
    cols = []
    for field in set(oldnew.keys()) - {"comments", "genre"}:
        field_diffs = sorted(oldnew[field], key=lambda x: x.new)
        if not field_diffs:
            continue
        tab = new_table()
        for new, all_old in groupby(field_diffs, lambda x: x.new):
            tab.add_row(
                " | ".join(
                    map(
                        lambda x: (f"{x[1]} x " if x[1] > 1 else "")
                        + wrap(x[0], "b s red"),
                        Counter(map(lambda x: x.old, all_old)).items(),
                    )
                ),
                wrap(new, "b green"),
            )
        cols.append(border_panel(tab, title=field))

    console.print("")
    console.print(Columns(cols, expand=True))

    stats_table = new_table("field", "#", border_style="white")
    for field, count in sorted(stats_map.items(), key=lambda x: x[1], reverse=True):
        stats_table.add_row(field, str(count))
    if stats_table.rows:
        stats_table.add_row("total", str(len(testfiles)))
        console.print(stats_table)


stats_map = defaultdict(lambda: 0)


@pytest.fixture(scope="module")
def config(request):
    yield BandcampPlugin().config.flatten()


def do_key(table, key: str, before, after) -> None:
    before = re.sub(r"^\s|\s$", "", str(before or ""))
    after = re.sub(r"^\s|\s$", "", str(after or ""))

    if (before or after) and (before != after):
        difftext = ""
        stats_map[key] += 1
        if key == "genre":
            before_set, after_set = set(before.split(", ")), set(after.split(", "))
            common, gone, added_new = (
                before_set & after_set,
                before_set - after_set,
                after_set - before_set,
            )
            diffparts = list(map(partial(wrap, tag="b #111111"), sorted(common)))
            if gone:
                gone = list(map(partial(wrap, tag="b strike red"), gone))
                diffparts.extend(gone)
            if added_new:
                added_new = list(map(partial(wrap, tag="b green"), added_new))
                diffparts.extend(added_new)
            if diffparts:
                difftext = " | ".join(diffparts)
        else:
            difftext = make_difftext(before, after)
        if difftext:
            oldnew[key].append(Oldnew(before, after, difftext))
            table.add_row(wrap(key, "b"), difftext)


def compare(old, new) -> None:
    every_new = [new]
    every_old = [old]
    if "/album/" in new["data_url"]:
        for entity in old, new:
            entity["albumartist"] = entity.pop("artist", "")

        every_new.extend(new.get("tracks"))
        every_old.extend(old.get("tracks"))
        desc = new.get("album")
        _id = new.get("album_id")
    else:
        desc = " - ".join([new.get("artist") or "", new.get("title") or ""])
        _id = new.get("track_id")

    table = new_table()
    for new, old in zip(every_new, every_old):
        for key in sorted(set(new.keys()).union(set(old.keys())) - IGNORE_FIELDS):
            do_key(table, key, str(old.get(key, "")), str(new.get(key, "")))

    if table.rows:
        console.print("")
        console.print(
            border_panel(table, title=wrap(desc, "b"), subtitle=wrap(_id, "dim"))
        )
        pytest.fail(pytrace=False)


@pytest.mark.usefixtures("_report")
def test_file(file, config):
    meta_file = os.path.join("jsons", file)
    tracks_file = os.path.join("jsons", file.replace(".json", ".tracks"))
    compare_file = os.path.join(compare_against, file)

    meta = open(meta_file).read() + (
        ("\n" + unescape(unescape(open(tracks_file).read())))
        if os.path.exists(tracks_file)
        else ""
    )
    guru = Metaguru.from_html(meta, config)
    new = guru.singleton if "_track_" in file else guru.album

    target = os.path.join(target_dir, file)
    json.dump(new, open(target, "w"), indent=2)

    try:
        old = json.load(open(compare_file))
    except FileNotFoundError:
        old = {}
    compare(old, new)
