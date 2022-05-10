import itertools as it
import re
import sys
from collections import Counter
from dataclasses import dataclass
from functools import reduce
from typing import Iterator, List, Optional, Set, Tuple

from beets.autotag import TrackInfo
from ordered_set import OrderedSet as ordset  # type: ignore
from rich import print

from ._helpers import CATNUM_PAT, PATTERNS, Helpers, JSONDict

if sys.version_info.minor > 7:
    from functools import cached_property  # pylint: disable=ungrouped-imports
else:
    from cached_property import cached_property  # type: ignore

_comp = re.compile

DIGI_ONLY_PATTERNS = [
    _comp(r"^(DIGI(TAL)? ?[\d.]+|Bonus\W{2,})\W*"),
    _comp(r"[^\w)]+(bandcamp[^-]+|digi(tal)?)(\W*(\W+|only|bonus|exclusive)\W*$)", re.I),
    _comp(r"[^\w)]+(bandcamp exclusive )?bonus( track)?(\]\W*|\W*$)", re.I),
]
DELIMITER_PAT = _comp(r" ([^\w&()+/[\] ]) ")  # hi | bye; hi - bye
REMIXER_PAT = _comp(r"\W*\( *([^)]+) (?i:(re)?mix|edit)\)", re.I)  # hi (Bye Remix)
FT_PAT = _comp(
    r" *(([\[(])| )f(ea)?t([. ]|uring)((?![^()]*(?:(?(2)mix|(?:mix|- .*))))[^]\[()]+)(?(2)[]\)]) *",
    re.I,  # ft. Hello; (ft. Hello); [feat. Hello]; (bye ft. Hello)
)
ELP_ALBUM_PAT = _comp(r"[- ]*\[([^\]]+ [EL]P)\]+")  # Title [Some Album EP]
TRACK_ALT_PAT = PATTERNS["track_alt"]
# fmt: off
CLEAN_PATTERNS = [
    (_comp(r" -(\S)"), r" - \1"),                    # hi -bye    -> hi - bye
    (_comp(r"(\S)- "), r"\1 - "),                    # hi- bye    -> hi - bye
    (_comp(r"  +"), " "),                            # hi  bye    -> hi bye
    (_comp(r"\( +"), "("),                           # hi ( bye)  -> hi (bye)
    (_comp(r" \)+|\)+$"), ")"),                      # hi (bye )) -> hi (bye)
    (_comp(r'(^|- )"([^"]+)"( \(|$)'), r"\1\2\3"),  # "bye" -> bye; hi - "bye" -> hi - bye
    (_comp(r"([\[(][^(-]+) - ([^\]()]+[])])"), r"\1-\2"),  # (b - hi edit) -> (b-hi edit)
    (_comp(r"- Reworked"), "(Reworked)"),            # bye - Reworked -> bye (Reworked)
    (PATTERNS["clean_title"], ""),
    #     # Title - Some Remix -> Title (Some Remix)
    #     name = Track.BAD_REMIX_PAT.sub("(\\1)", name)
]
# fmt: on


@dataclass
class Track:
    json_item: JSONDict
    track_id: str
    index: int

    _name: str = ""
    _artist: str = ""
    ft: str = ""
    album: str = ""
    catalognum: str = ""
    remixer: str = ""

    single: Optional[bool] = None
    track_alt: Optional[str] = None

    @classmethod
    def from_json(
        cls, json: JSONDict, name: str, delim: str, catalognum: str, label: str
    ) -> "Track":
        try:
            artist = json["inAlbum"]["byArtist"]["name"]
        except KeyError:
            artist = ""
        artist = artist or json.get("byArtist", {}).get("name", "")
        data = dict(
            json_item=json,
            _artist=artist,
            track_id=json["@id"],
            index=json["position"],
            catalognum=catalognum,
        )
        return cls(**cls.parse_name(data, name, delim, label=label))

    @staticmethod
    def parse_name(data: JSONDict, name: str, delim: str, label: str) -> JSONDict:
        name = name.replace(f" {delim} ", " - ")
        if name.endswith(label):
            name = name.replace(label, "").strip(" -")
        for pat, repl in CLEAN_PATTERNS:
            name = pat.sub(repl, name)
            data["_artist"] = pat.sub(repl, data["_artist"])
        name = name.strip().lstrip("-")
        m = TRACK_ALT_PAT.search(name)
        if m:
            data["track_alt"] = m.group(1)
            name = name.replace(m.group(), "")

        if not data["catalognum"]:
            m = CATNUM_PAT["delimited"].search(name)
            if m:
                data["catalognum"] = m.group(1)
                name = name.replace(m.group(), "")
        name = re.sub(fr"^0*{data['index']}(?!\W\d)\W+", "", name)

        m = REMIXER_PAT.search(name)
        if m:
            data["remixer"] = m.group(1)

        m = ELP_ALBUM_PAT.search(name)
        if m:
            data["album"] = m.group(1)
            name = name.replace(m.group(), "")

        data["_name"] = name
        for field in "_name", "_artist":
            m = FT_PAT.search(data[field])
            if m:
                data[field] = data[field].replace(m.group().rstrip(), "")
                if m.groups()[-1].strip() not in data["_artist"]:
                    data["ft"] = m.group().strip(" ([])")
                break
        return data

    @cached_property
    def duration(self) -> int:
        try:
            h, m, s = map(int, re.findall(r"[0-9]+", self.json_item["duration"]))
        except KeyError:
            return 0
        else:
            return h * 3600 + m * 60 + s

    @cached_property
    def lyrics(self) -> str:
        try:
            return self.json_item["recordingOf"]["lyrics"]["text"].replace("\r", "")
        except KeyError:
            return ""

    @cached_property
    def no_digi_name(self) -> str:
        """Return the track title which is clear from digi-only artifacts."""
        return reduce(lambda a, b: b.sub("", a), DIGI_ONLY_PATTERNS, self._name)

    @property
    def name(self) -> str:
        name = self.no_digi_name
        if self._artist and " - " not in name:
            name = f"{self._artist} - {name}"
        return name.strip()

    @cached_property
    def digi_only(self) -> bool:
        """Return True if the track is digi-only."""
        return self.name != self.no_digi_name

    @property
    def title(self) -> str:
        parts = self.name.split(" - ")
        for idx, maybe in enumerate(reversed(parts)):
            if maybe.strip(" -"):
                return " - ".join(parts[-idx - 1 :])
        return self.name

    @property
    def artist(self) -> str:
        artiststr = self.name.removesuffix(self.title).strip(", -")
        artiststr = REMIXER_PAT.sub("", artiststr)
        if self.remixer:
            split = Helpers.split_artists([artiststr])
            if len(split) > 1:
                try:
                    split.remove(self.remixer)
                except ValueError:
                    pass
                else:
                    artiststr = ", ".join(split)

        return artiststr.strip(" -")

    @artist.setter
    def artist(self, val: str) -> None:
        self._artist = val

    @property
    def artists(self) -> List[str]:
        # artists = ordset((next(orig) for _, orig in it.groupby(artists, str.lower)))
        return Helpers.split_artists(self.artist.split(", "))

    @cached_property
    def main_title(self) -> str:
        return PATTERNS["remix_or_ft"].sub("", self.title)

    @property
    def info(self) -> TrackInfo:
        return TrackInfo(
            index=self.index if not self.single else None,
            medium_index=self.index if not self.single else None,
            medium=None,
            track_id=self.track_id,
            artist=self.artist + (f" {self.ft}" if self.ft else ""),
            title=self.title,
            length=self.duration,
            track_alt=self.track_alt,
            lyrics=self.lyrics,
            catalognum=self.catalognum or None,
        )


@dataclass
class Tracks(list):
    tracks: List[Track]

    def __iter__(self) -> Iterator[Track]:
        return iter(self.tracks)

    def __len__(self) -> int:
        return len(self.tracks)

    @classmethod
    def from_json(cls, meta: JSONDict) -> "Tracks":
        try:
            tracks = meta["track"]["itemListElement"]
        except KeyError:
            tracks = [{"item": meta, "position": 1}]
        for track in tracks:
            track.update(**track["item"])
        try:
            label = meta["albumRelease"][0]["recordLabel"]["name"]
        except (KeyError, IndexError):
            label = meta["publisher"]["name"]
        names = [i["name"] for i in tracks]
        delim = cls.track_delimiter(names)
        catalognum, names = cls.common_catalognum(names, delim)
        return cls(
            [
                Track.from_json(t, n, delim, catalognum, label)
                for n, t in zip(names, tracks)
            ]
        )

    @staticmethod
    def common_catalognum(names: List[str], delim: str) -> Tuple[str, List[str]]:
        """Split each track name into words, find the list of words that are common
        to all tracks, and check the *first* and the *last* word for a catalog number.

        If found, remove that word / catalog number from each track name.
        Return the catalog number and the new list of names.
        """
        names_tokens = list(map(str.split, names))
        common_words = ordset.intersection(*names_tokens) - {delim}
        if common_words:
            for word in set([common_words[0], common_words[-1]]):
                m = CATNUM_PAT["anywhere"].search(word)
                if m:
                    for tokens in names_tokens:
                        tokens.remove(word)
                    return m.group(1), list(map(" ".join, names_tokens))
        return "", names

    @property
    def artists(self) -> List[str]:
        return list(ordset(it.chain(*(j.artists for j in self.tracks))))

    @cached_property
    def raw_names(self) -> List[str]:
        return [j.name for j in self.tracks]

    @property
    def raw_artists(self) -> List[str]:
        return list(ordset(it.chain(*(j.artists for j in self.tracks))))
        # return list(ordset(t.artist for t in self.tracks))

    @cached_property
    def raw_remixers(self) -> Set[str]:
        remixers = [j.remixer for j in self.tracks if j.remixer]
        ft = [j.ft for j in self.tracks if j.ft]
        return set(it.chain(remixers, ft))

    def adjust_artists(self, aartist: str, single=bool) -> None:
        track_alts = {t.track_alt for t in self.tracks if t.track_alt}
        artists = [t.artist for t in self.tracks if t.artist]
        count = len(self)
        for idx, t in enumerate(self):
            t.single = single
            # if t.track_alt and len(track_alts) == 1:
            #     # the only track that parsed a track alt - it's most likely a mistake
            #     if t.artist:
            #         # one title was confused for a track alt, like 'C4'
            #         # this would have shifted the artist to become the title as well
            #         # so let's reverse it all
            #         t.title, t.artist = t.track_alt, t.title
            #     else:
            #         # one artist was confused for a track alt, like 'B2', - reverse this
            #         t.artist = t.track_alt
            #     t.track_alt = None

            if not t.artist:
                if len(artists) == count - 1:
                    # this is the only artist that didn't get parsed - relax the rule
                    # and try splitting with '-' without spaces
                    split = t.title.split("-")
                    if len(split) > 1:
                        t.artist, t.title = split
                if not t.artist:
                    # use the albumartist
                    t.artist = aartist

    @staticmethod
    def track_delimiter(names: List[str]) -> str:
        """Return the track parts delimiter that is in effect in the current release.
        In some (unusual) situations track parts are delimited by a pipe character
        instead of dash.

        This checks every track looking for the first character (see the regex for
        exclusions) that splits it. The character that split the most and
        at least half of the tracklist is the character we need.
        """

        def get_delim(string: str) -> str:
            match = DELIMITER_PAT.search(string)
            return match.group(1) if match else "-"

        most_common = Counter(map(get_delim, names)).most_common(1)
        if not most_common:
            return ""
        delim, count = most_common.pop()
        return delim if (len(names) == 1 or count > len(names) / 2) else "-"
