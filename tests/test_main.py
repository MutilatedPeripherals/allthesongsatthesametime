import unittest
from pathlib import Path
from unittest import mock

import main


class BuildChallengeTest(unittest.TestCase):
    def setUp(self):
        self.confirm = mock.patch.object(main, "_confirm_songs", return_value=True)
        self.confirm.start()
        self.addCleanup(self.confirm.stop)

    def test_build_challenge_success(self):
        songs = ["Song A", "Song B", "Song C"]
        urls = [f"https://youtube.com/watch?v={i}" for i in range(3)]
        paths = [Path(f"/tmp/fake/{i}.mp3") for i in range(3)]
        m_search = mock.MagicMock(side_effect=urls)
        m_download = mock.MagicMock(side_effect=[(True, p) for p in paths])
        m_mix = mock.MagicMock(return_value=True)

        with (
            mock.patch.object(main, "fetch_song_names", return_value=songs),
            mock.patch.object(main, "search_youtube_url", m_search),
            mock.patch.object(main, "download_from_youtube_as_mp3", m_download),
            mock.patch.object(main, "mix_mp3s", m_mix),
        ):
            result = main.build_challenge("Wormrot", "Dirge")

        expected = Path.cwd().resolve() / "challenges" / "Dirge_challenge.mp3"
        self.assertEqual(result, expected)

        for song in songs:
            m_search.assert_any_call(f"{song} Wormrot")
        self.assertEqual(m_download.call_count, 3)

        mix_args = m_mix.call_args.args[0]
        self.assertEqual(sorted(map(str, mix_args)), sorted(map(str, paths)))

    def test_build_challenge_skips_failed_download(self):
        songs = ["Song A", "Song B"]
        paths = [Path("/tmp/fake/a.mp3")]
        m_download = mock.MagicMock(side_effect=[(True, paths[0]), (False, None)])
        m_mix = mock.MagicMock(return_value=True)

        with (
            mock.patch.object(main, "fetch_song_names", return_value=songs),
            mock.patch.object(
                main,
                "search_youtube_url",
                side_effect=["https://youtube.com/watch?v=1", "https://youtube.com/watch?v=2"],
            ),
            mock.patch.object(main, "download_from_youtube_as_mp3", m_download),
            mock.patch.object(main, "mix_mp3s", m_mix),
        ):
            result = main.build_challenge("Wormrot", "Dirge")

        self.assertTrue(result)
        mix_args = m_mix.call_args.args[0]
        self.assertEqual(list(map(str, mix_args)), [str(paths[0])])

    def test_build_challenge_skips_missing_url(self):
        songs = ["Song A", "Song B"]
        path = Path("/tmp/fake/b.mp3")
        m_download = mock.MagicMock(return_value=(True, path))
        m_mix = mock.MagicMock(return_value=True)

        with (
            mock.patch.object(main, "fetch_song_names", return_value=songs),
            mock.patch.object(main, "search_youtube_url", side_effect=[None, "https://youtube.com/watch?v=2"]),
            mock.patch.object(main, "download_from_youtube_as_mp3", m_download),
            mock.patch.object(main, "mix_mp3s", m_mix),
        ):
            result = main.build_challenge("Wormrot", "Dirge")

        self.assertTrue(result)
        m_download.assert_called_once_with("https://youtube.com/watch?v=2")

    def test_build_challenge_no_songs(self):
        with (
            mock.patch.object(main, "fetch_song_names", return_value=[]),
            mock.patch.object(main, "mix_mp3s") as mix,
        ):
            result = main.build_challenge("Unknown Band")
        self.assertEqual(result, Path())
        mix.assert_not_called()

    def test_build_challenge_aborts_when_not_confirmed(self):
        with mock.patch.object(main, "_confirm_songs", return_value=False) as confirm:
            with mock.patch.object(main, "fetch_song_names", return_value=["Song A"]) as fetch:
                with mock.patch.object(main, "mix_mp3s") as mix:
                    result = main.build_challenge("Wormrot", "Dirge")

        confirm.assert_called_once()
        fetch.assert_called_once()
        mix.assert_not_called()
        self.assertEqual(result, Path())

    def test_build_challenge_failed_mix(self):
        songs = ["Song A"]
        path = Path("/tmp/fake/a.mp3")

        with (
            mock.patch.object(main, "fetch_song_names", return_value=songs),
            mock.patch.object(main, "search_youtube_url", return_value="https://youtube.com/watch?v=1"),
            mock.patch.object(main, "download_from_youtube_as_mp3", return_value=(True, path)),
            mock.patch.object(main, "mix_mp3s", return_value=False),
        ):
            result = main.build_challenge("Wormrot", "Dirge")
        self.assertEqual(result, Path())


class FetchSongNamesTest(unittest.TestCase):
    def test_album_picks_fewest_track_release(self):
        detailed_full = {"media": [{"tracks": [{"title": f"F{i}"} for i in range(12)]}]}
        detailed_ep = {"media": [{"tracks": [{"title": f"E{i}"} for i in range(5)]}]}
        search = {"releases": [{"id": "full"}, {"id": "ep"}]}

        with (
            mock.patch.object(
                main, "fetch_song_names_wikipedia", return_value=[]
            ) as wiki,
            mock.patch.object(main, "_mb_get", side_effect=[search, detailed_full, detailed_ep]),
        ):
            songs = main.fetch_song_names("Wormrot", "Dirge")

        self.assertEqual(len(songs), 5)
        self.assertEqual(songs, [f"E{i}" for i in range(5)])
        wiki.assert_called_once_with("Wormrot", "Dirge")

    def test_wikipedia_is_primary_for_albums(self):
        wiki_songs = ["Wiki One", "Wiki Two"]
        with (
            mock.patch.object(
                main, "fetch_song_names_wikipedia", return_value=wiki_songs
            ) as wiki,
            mock.patch.object(main, "_fetch_song_names") as mb,
        ):
            songs = main.fetch_song_names("Death", "Leprosy")
        self.assertEqual(songs, wiki_songs)
        wiki.assert_called_once_with("Death", "Leprosy")
        mb.assert_not_called()

    def test_wiki_empty_falls_back_to_musicbrainz(self):
        with (
            mock.patch.object(main, "fetch_song_names_wikipedia", return_value=[]),
            mock.patch.object(main, "_mb_get", return_value={"releases": []}),
        ):
            songs = main.fetch_song_names("Wormrot", "Dirge")
        self.assertEqual(songs, [])

    def test_band_only_empty_has_no_fallback(self):
        with (
            mock.patch.object(main, "_fetch_song_names", return_value=[]),
            mock.patch.object(main, "fetch_song_names_wikipedia") as wiki,
        ):
            songs = main.fetch_song_names("Death")
        self.assertEqual(songs, [])
        wiki.assert_not_called()

    def test_album_empty_releases(self):
        with (
            mock.patch.object(main, "fetch_song_names_wikipedia", return_value=[]),
            mock.patch.object(main, "_mb_get", return_value={"releases": []}),
        ):
            songs = main.fetch_song_names("Wormrot", "Dirge")
        self.assertEqual(songs, [])

    def test_band_dedupes_tracks(self):
        artists = {"artists": [{"id": "m1"}]}
        releases = {
            "releases": [
                {
                    "media": [
                        {
                            "tracks": [
                                {"title": "A"},
                                {"title": "A"},
                                {"title": "B"},
                            ]
                        }
                    ]
                }
            ]
        }

        with mock.patch.object(main, "_mb_get", side_effect=[artists, releases]):
            songs = main.fetch_song_names("Wormrot")

        self.assertEqual(songs, ["A", "B"])

    def test_band_unknown_artist(self):
        with mock.patch.object(main, "_mb_get", return_value={"artists": []}):
            songs = main.fetch_song_names("No Such Band")
        self.assertEqual(songs, [])


class WikipediaParserTest(unittest.TestCase):
    def test_parses_simple_tracklist(self):
        page = """
        <table class="tracklist">
          <tr><th>No.</th><th>Title</th><th>Length</th></tr>
          <tr><td>1.</td><td>"Song One"</td><td>3:00</td></tr>
          <tr><td>2.</td><td>Song Two</td><td>4:30</td></tr>
        </table>
        """
        self.assertEqual(
            main._parse_wikipedia_tracklist(page), ["Song One", "Song Two"]
        )

    def test_row_scope_and_duplicate_halves(self):
        page = """
        <table class="tracklist">
          <tr><th>No.</th><th>Title</th><th>Length</th></tr>
          <tr><th colspan="3">Side A</th></tr>
          <tr><th scope="row">1.</th><td>"A Song"</td><td>2:00[1]</td></tr>
          <tr><th scope="row">2.</th><td>A Song</td><td>2:00</td></tr>
          <tr><th scope="row">3.</th><td>B Song<sup>[a]</sup></td><td>1:00</td></tr>
        </table>
        """
        self.assertEqual(
            main._parse_wikipedia_tracklist(page), ["A Song", "B Song"]
        )

    def test_header_missing_title_column(self):
        page = '<table class="tracklist"><tr><th>No.</th><th>Length</th></tr></table>'
        self.assertEqual(main._parse_wikipedia_tracklist(page), [])


class FormatElapsedTest(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(main.format_elapsed(42), "42s")
        self.assertEqual(main.format_elapsed(125), "2m 05s")
        self.assertEqual(main.format_elapsed(3725), "1h 02m")


class ConfirmSongsTest(unittest.TestCase):
    @mock.patch("builtins.input", return_value="y")
    def test_accepts(self, input_mock):
        self.assertTrue(main._confirm_songs(["A", "B"], "Album X"))
        input_mock.assert_called_once()

    @mock.patch("builtins.input", return_value="")
    def test_declines_empty(self, _input_mock):
        self.assertFalse(main._confirm_songs(["A"], "Album X"))

    @mock.patch("builtins.input", return_value="no")
    def test_declines_no(self, _input_mock):
        self.assertFalse(main._confirm_songs(["A"], "Album X"))


if __name__ == "__main__":
    unittest.main()