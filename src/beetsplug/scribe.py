import re
from beets import config
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, decargs, print_
from beets.dbcore import types
from bs4 import BeautifulSoup
import confuse
import requests
import urllib

WORK_STYLE = "sc_work_style"
GENRE_CATEGORIES = "sc_genre_categories"
FIRST_PUBLICATION = "sc_first_publication"
GENRE = "genre"


class ScribePlugin(BeetsPlugin):

    item_types = {
        WORK_STYLE: types.STRING,
        GENRE_CATEGORIES: types.STRING,
        FIRST_PUBLICATION: types.STRING,
    }

    def __init__(self):
        super().__init__()

    def commands(self):
        command = Subcommand(
            "scribe",
            help="a plugin for beets to improve the quality of information related to western classical music",
        )
        command.parser.add_option(
            "-f",
            "--force",
            action="store_true",
            dest="force",
            help="overwrite existing values for fields",
        )
        command.parser.add_option(
            "-p",
            "--pretend",
            action="store_true",
            dest="pretend",
            help="preview changes",
        )
        command.parser.add_option(
            "-e",
            "--explain",
            action="store_true",
            dest="explain",
            help="details plugin activities",
        )
        command.parser.add_option(
            "-q",
            "--quiet",
            action="store_true",
            dest="quiet",
            help="decrease amount of information showed during activity",
        )
        command.parser.add_option(
            "-g",
            "--genre",
            action="store_true",
            dest="fields.genre",
            help='overwrite standard "genre" field value',
        )
        command.parser.add_option(
            "-c",
            "--genre-categories",
            action="store_true",
            dest="fields.sc_genre_categories",
            help=f'populate field "{GENRE_CATEGORIES}"',
        )
        command.parser.add_option(
            "-r",
            "--first-publication",
            action="store_true",
            dest="fields.sc_first_publication",
            help=f'populate field "{FIRST_PUBLICATION}"',
        )
        command.parser.add_option(
            "-i",
            "--interactive",
            action="store_true",
            dest="interactive",
            help="manual mode, no execution of google queries, instead expecting for each pair (composer, work) the url of the IMSLP's page to be scraped",
        )
        command.parser.add_option(
            "-l",
            "--list",
            action="store_true",
            dest="list_works",
            help="produce a list of all the distinct pairs (composer, work) resulting from the execution of the query",
        )
        command.parser.add_option(
            "-s",
            "--search",
            action="store",
            dest="search",
            help="use the parameter's value as a google search string for a specific pair (composer, work); the resulting data will be applied to all items matching the beets query. User is responsible to pass a query in which all items belong to same pair (composer, work)",
        )
        command.func = self.run
        return [command]

    def run(self, lib, opts, args):
        self.populate_cfg(opts)

        if self.config["explain"].get(False):
            explain()
            return

        items = self.do_query(lib, decargs(args))

        updated = 0
        if self.config["search"].get(""):
            updated += self.manual_search(items)
        else:
            works = self.collect_works(items)
            if self.config["list_works"].get(False):
                for work in works:
                    print_(f'{work[0]}:"{work[1]}", work:"{work[2]}"')
                return
            for work in works:
                updated += self.process_work(lib, work)
        if not self.config["interactive"].get(False):
            self.msg(f"{self.cs_call_count} google custom search call(s) executed")
        self.msg(f"{updated} item(s) {self.config['action'].as_str()}")

    def populate_cfg(self, opts):
        cfg = self.config
        cfg.set_args(opts, dots=True)
        custom_search_list = cfg["custom_search"]
        custom_search_list.redact = True
        cs_template = confuse.Sequence({"name": None, "api_key": str, "cse_id": str})
        custom_search_list.get(cs_template)
        self.cs_last_call = [0 for _ in range(len(list(custom_search_list)))]
        self.cs_call_count = 0
        cfg["action"].set(
            "potentially updated" if cfg["pretend"].get(False) else "updated"
        )

    def do_query(self, lib, query):
        force = self.config["force"].get(False)
        query = query if force else query + [WORK_STYLE + ":=~"]
        self._log.debug(f"query: {query}")
        items = lib.items(query)
        if not self.config["quiet"].get(False):
            print_(
                f"found {len(items)} item(s) matching{'' if force else ', excluding items already populated' }"
            )
        return items

    def collect_works(self, items):
        if not self.config["quiet"].get(False):
            for item in items:
                if not item["work"]:
                    print_(
                        f"item discarded, empty work field: {item['artist']} - {item['album']} - {item['title']}"
                    )
        works = {
            map_work(item)
            for item in items
            if item["work"] and (item["artist_sort"] or item["composer_sort"])
        }
        self._log.debug(f"works found: {*works,}")
        self.msg(
            f"found {len(works)} work(s) matching"
            + (
                ""
                if self.config["force"].get(False)
                else ", excluding works with items already populated"
            ),
        )
        return works

    def process_work(self, lib, work):
        updated = 0
        self.msg(
            f'\nprocess work: {work[0]}:"{work[1]}", work:"{work[2]}"',
        )
        res = self.find_data(f"{work[1]} {work[2]}")
        if res and res[WORK_STYLE]:
            work_query = (
                f"{work[0]}::^{re.escape(work[1])}",
                f"work::^{re.escape(work[2])}(\\s*:.+)?$",
            )
            items = lib.items(work_query)
            self._log.debug(f"found {len(items)} items for work query: {*work_query,}")
            self.msg(f"found {len(items)} item(s) matching the work")
            for item in items:
                updated += self.process_item(item, res)
        return updated

    def manual_search(self, items):
        updated = 0
        res = self.find_data(self.config["search"].as_str())
        if res and res[WORK_STYLE]:
            for item in items:
                updated += self.process_item(item, res)
        return updated

    def process_item(self, item, res):
        updated = 0
        apply = self.config["force"].get(False) or not item.get(WORK_STYLE)
        if apply:
            if not self.config["pretend"].get(False):
                self.modify_item(item, res)
            self.print_result(item, res)
            updated = 1
        return updated

    def modify_item(self, item, res):
        f = self.config["fields"]
        item[WORK_STYLE] = res[WORK_STYLE]
        if f[FIRST_PUBLICATION].get(False):
            item[FIRST_PUBLICATION] = res[FIRST_PUBLICATION]
        if f[GENRE_CATEGORIES].get(False):
            item[GENRE_CATEGORIES] = "; ".join(res[GENRE_CATEGORIES])
        if f[GENRE].get(False):
            item[GENRE] = calc_genre(res)
        if self.config["write"].get(config["import"]["write"].get(True)):
            item.try_sync(True, False)
        else:
            item.store()

    def find_data(self, query):
        if self.config["interactive"].get(False):
            search = "https://www.google.com/search?" + urllib.parse.urlencode(
                {"q": "site:imslp.org " + query}
            )
            url = input(
                f"Perform this search and paste link related to work:\n{search}\n"
            )
        else:
            url = self.call_custom_search(query)
        if url:
            result = imslp_scrape(self._log, url)
            self._log.debug('page scraped: "{0}", result: {1}', url, str(result))
            return result
        else:
            return None

    def call_custom_search(self, query):
        cs_list = self.config["custom_search"].get()
        cs_list_len = len(cs_list)
        cs_actives = [i for i in range(cs_list_len) if self.cs_last_call[i] != 429]
        cs_actives_len = len(cs_actives)
        retries = 0
        (status_code, res) = (429, [])
        while status_code == 429 and retries < cs_actives_len:
            cs_active_p = (self.cs_call_count + retries) % cs_actives_len
            cs_el = cs_list[cs_actives[cs_active_p]]
            if "name" not in cs_el:
                cs_el["name"] = f"custom-search-{cs_active_p}"
            self._log.debug(
                f"custom_search: {cs_el['name']}, retries: {retries}, count: {self.cs_call_count}"
            )
            (status_code, res) = google_search(
                self._log,
                query,
                cs_el["api_key"],
                cs_el["cse_id"],
            )
            self.cs_last_call[cs_actives[cs_active_p]] = status_code
            retries += 1
            cs_actives = [i for i in range(cs_list_len) if self.cs_last_call[i] != 429]
            cs_actives_len = len(cs_actives)
        self.cs_call_count += retries
        return res[0] if res else ""

    def print_result(self, item, res):
        f = self.config["fields"]
        data = ", ".join(
            filter(
                None,
                (
                    fmt(WORK_STYLE, res[WORK_STYLE], True, 30, True),
                    fmt(GENRE, calc_genre(res), f[GENRE].get(False), 40, True),
                    fmt(
                        FIRST_PUBLICATION,
                        res[FIRST_PUBLICATION],
                        f[FIRST_PUBLICATION].get(False),
                        20,
                        True,
                    ),
                    fmt(
                        GENRE_CATEGORIES,
                        str(res[GENRE_CATEGORIES]),
                        f[GENRE_CATEGORIES].get(False),
                        60,
                        False,
                    ),
                ),
            )
        )
        self.msg(
            f"{self.config['action'].as_str().capitalize()}: {item.artist} - {item.album} - {item.title}\n{data}",
        )

    def msg(self, message):
        if not self.config["quiet"].get(False) or self.config["interactive"].get(False):
            print_(message)


def map_work(item):
    (author_field, author) = (
        ("composer_sort", item["composer_sort"])
        if item["composer_sort"]
        else ("artist_sort", item["artist_sort"])
    )
    author = strip_repeated_elements(author, len(item["artist"]))
    return (
        author_field,
        author.strip(" ,"),
        item["work"].split(":")[0].strip(),
    )


def google_search(_log, query, api_key, cse_id, num_results=5):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "key": api_key,
        "cx": cse_id,
        "num": num_results,
    }
    response = requests.get(url, params=params)
    data = response.json()
    results = (
        [item["link"] for item in data.get("items", [])]
        if response.status_code == 200
        else []
    )
    _log.debug(
        'google query: "{0}", found pages: {1}, status_code: {2}',
        query,
        len(results),
        response.status_code,
    )
    return (response.status_code, results)


def imslp_scrape(_log, url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.find(id="General_Information")
    if not text:
        _log.debug("page content not matching")
        return {}
    th = soup.find("th", string=re.compile("Piece Style"))
    piece_style = th.parent.find("td").a.string if th is not None else None
    if not piece_style:
        _log.debug("piece style information not found on page")
        return {}
    text = soup.find(string=re.compile("Genre Categories"))
    if text:
        th = text.parent
        genre_categories = (
            list(filter(lambda x: x != ";", th.parent.find("td").stripped_strings))
            if th is not None
            else ()
        )
    else:
        genre_categories = ()
    text = soup.find(string=re.compile("First Pub"))
    if text:
        th = text.parent
        first_publication = (
            next(th.parent.find("td").stripped_strings) if th is not None else ""
        )
    else:
        first_publication = ""
    return {
        GENRE_CATEGORIES: genre_categories,
        FIRST_PUBLICATION: first_publication,
        WORK_STYLE: piece_style,
    }


def calc_genre(res):
    return (
        "; ".join((res[WORK_STYLE], res[GENRE_CATEGORIES][0]))
        if res[GENRE_CATEGORIES]
        else res[WORK_STYLE]
    )


def fmt(key, value, condition, max_len, quote):
    if condition:
        value_str = (
            f'"{truncate(value, max_len)}"' if quote else f"{truncate(value, max_len)}"
        )
        res = f"{key} = {value_str}"
    else:
        res = ""
    return res


def truncate(str, size):
    return str[: size - 3] + "..." if len(str) > size else str


def explain():
    print_(
        '''
A plugin to improve the quality of information related to western classical music.

The plugin works in two different ways:

• [1m[23m[39m[49m[24m[29mby work[0m (default):

  • collects items from a query passed by user

  • identifies all distinct pairs (composer, work)

  • for each pair makes a google search query on site [22m[23m[36m[49m[4m[29m]8;;https://imslp.org\IMSLP[0m]8;;\, searching
    for the page containing details about that work

  • scrapes the first search result in order to collect the required
    information

  • applies collected information to all items matching the pair
    (composer, work)

• [1m[23m[39m[49m[24m[29mby search[0m: using the parameter [22m[23m[31m[47m[24m[29m -s / --search [0m

  • collect items from a query passed by user

  • execute the google search with a query string passed as parameter,
    the query is meant to identify the [22m[23m[36m[49m[4m[29m]8;;https://imslp.org\IMSLP[0m]8;;\ page containing details
    about a specific work (of a specific composer)

  • scrapes the first search result in order to collect the required
    information

  • apply the collected information to all items identified in the first
    step

The information collected from [22m[23m[36m[49m[4m[29m]8;;https://imslp.org\IMSLP[0m]8;;\ page is put in the following
fields:

• [22m[23m[31m[47m[24m[29m sc_work_style [0m: contains the [1m[23m[39m[49m[24m[29mmusic period[0m as per [22m[23m[36m[49m[4m[29m]8;;https://wikipedia.org/wiki/Classical_music\Classical Music[0m]8;;\,
  i.e. [22m[3m[39m[49m[24m[29mBaroque[0m, [22m[3m[39m[49m[24m[29mClassical[0m, …

• [22m[23m[31m[47m[24m[29m sc_first_publication [0m: contains informations about first publication
  of the work

• [22m[23m[31m[47m[24m[29m sc_genre_categories [0m: contains a list of detailed music genres such
  as [22m[3m[39m[49m[24m[29mSymphonies[0m, [22m[3m[39m[49m[24m[29mOpera[0m, [22m[3m[39m[49m[24m[29mSonatas[0m, ….

• [22m[23m[31m[47m[24m[29m genre [0m: this standard field is overwritten as a two element list
  composed by [22m[23m[31m[47m[24m[29m sc_work_style [0m value and first element from
  [22m[23m[31m[47m[24m[29m sc_genre_categories [0m list, i.e. [22m[23m[31m[47m[24m[29m Romantic; Symphonies [0m

The default behaviour is to skip all items having field [22m[23m[31m[47m[24m[29m sc_work_style [0m
already filled. The [22m[23m[31m[47m[24m[29m -f / --force [0m option extends the beets search to
all items and eventually overwrites already present values.

The option [22m[23m[31m[47m[24m[29m -i / --interactive [0m substitutes the automated execution of
google search queries with a manual step for each pair (composer, work),
expecting to receive the correct url for the [22m[23m[36m[49m[4m[29m]8;;https://imslp.org\IMSLP[0m]8;;\ page to be scraped.
This mode permits the execution of a refined query in case the standard
search fails to find a correct result, and can be used as a workaround
to avoid getting stuck with the google service free tier limit of 100
queries/day.

The option [22m[23m[31m[47m[24m[29m -l / --list [0m produce the list of the distinct pairs
(composer, work) identified from the collected items.
        '''
    )


def print_configuration_error(cfg):
    keys = ", ".join(
        filter(
            None,
            (
                "api_key" if not cfg.api_key else "",
                "cse_id" if not cfg.cse_id else "",
            ),
        )
    )
    print_(f"configuration error: {__name__.split('.')[-1]}: missing {keys}")


def strip_repeated_elements(content, min_len):
    repeating_substr = longest_substring(content)
    rs_len = len(repeating_substr)
    while rs_len > min_len:
        content = content.replace(repeating_substr, "", 1).strip(" ,;")
        repeating_substr = longest_substring(content)
        rs_len = len(repeating_substr)
    return content


# Python program to find longest repeating
# and non-overlapping substring
# using space optimised
# from https://www.geeksforgeeks.org/dsa/longest-repeating-and-non-overlapping-substring/#using-space-optimized-dp-on2-time-and-on-space
def longest_substring(s):
    n = len(s)
    dp = [0] * (n + 1)

    ans = ""
    ans_len = 0

    # find length of non-overlapping
    # substrings for all pairs (i, j)
    for i in range(n - 1, -1, -1):
        for j in range(i, n):

            # if characters match, set value
            # and compare with ansLen.
            if s[i] == s[j]:
                dp[j] = 1 + min(dp[j + 1], j - i - 1)

                if dp[j] >= ans_len:
                    ans_len = dp[j]
                    ans = s[i : i + ans_len]
            else:
                dp[j] = 0

    return ans if ans_len > 0 else ""
