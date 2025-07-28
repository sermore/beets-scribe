# beets-scribe

A plugin for [beets](https://github.com/beetbox/beets) to improve the quality of information related to western classical music.

The plugin works in two different ways:

- **by work** (default):
  - collects items from a query passed by user
  - identifies all distinct pairs (composer, work)
  - for each pair makes a google search query on site [IMSLP](https://imslp.org), searching for the page containing details about that work
  - scrapes the first search result in order to collect the required information
  - applies collected information to all items matching the pair (composer, work)
- **by search**: using the parameter `-s / --search`
  - collect items from a query passed by user
  - execute the google search with a query string passed as parameter, the query is meant to identify the [IMSLP](https://imslp.org) page containing details about a specific work (of a specific composer)
  - scrapes the first search result in order to collect the required information
  - apply the collected information to all items identified in the first step

The information collected from [IMSLP](https://imslp.org) page is put in the following fields:

- `sc_work_style`: contains the **music period** as per [Classical Music](https://wikipedia.org/wiki/Classical_music), i.e. _Baroque_, _Classical_, ...
- `sc_first_publication`: contains informations about first publication of the work
- `sc_genre_categories`: contains a list of detailed music genres such as _Symphonies_, _Opera_, _Sonatas_, ....
- `genre`: this standard field is overwritten as a two element list composed by `sc_work_style` value and first element from `sc_genre_categories` list, i.e. `Romantic; Symphonies`

The default behaviour is to skip all items having field `sc_work_style` already filled. The `-f / --force` option extends the beets search to all items and eventually overwrites already present values.

The option `-i / --interactive` substitutes the automated execution of google search queries with a manual step for each pair (composer, work), expecting to receive the correct url for the [IMSLP](https://imslp.org) page to be scraped. This mode permits the execution of a refined query in case the standard search fails to find a correct result, and can be used as a workaround to avoid getting stuck with the google service free tier limit of 100 queries/day.

The option `-l / --list` produce the list of the distinct pairs (composer, work) identified from the collected items.

## Installation

Install the plugin using `pip`:

```shell
pip install git+https://github.com/sermore/beets-scribe.git
```

Then, [configure](#configuration) the plugin in your
[`config.yaml`](https://beets.readthedocs.io/en/latest/plugins/index.html) file.

### Google Custom Search API service setup

The automated google search queries are executed using google service [Custom Search JSON API](https://developers.google.com/custom-search/v1/overview). In order to use it it's therefore required to setup at least one of these services, using [Google Cloud Console](https://console.cloud.google.com).
At the end of the process, the service is identified by 2 keys, `api-key` and `cse-id`, to be put in the plugin`s configuration.

Quick procedure for google custom search api service creation:

- from [Google Cloud Console](https://console.cloud.google.com)
  - create a project
  - add API library: `Custom Search API`
  - enable the service
  - enable Custom Search API key (credentials), to be used as `api_key` inside config
- from [Programmable Search Engine Dashboard](https://programmablesearchengine.google.com/controlpanel/all) add an engine
  - in section "Sites to search" add `imslp.org/*`
  - once created, collect the `Search engine ID` from detail page, to be used as `cse_id` inside config

If you are interested in using free resources, check that the project you have just created is not linked to a billing account
otherwise you may encounter unpleasant surprises.

Here an example of a REST call to verify that the service is working:
```shell
curl -v --get --data-urlencode 'q=mozart wolfgang turk' --data-urlencode 'key=<GOOGLE API KEY>' --data-urlencode 'cx=<SEARCH ENGINE ID>'  'https://customsearch.googleapis.com/customsearch/v1'
```

## Configuration

Add `scribe` to your list of enabled plugins.

```yaml
plugins: scribe
```

Next, you can apply plugin configuration inside `scribe` config item.
A configuration item exists for nearly each options available in the command line.

```yaml
scribe:
    interactive: no
    custom_search:
      - name: custom-search-1
        api_key: <GOOGLE API KEY 1>
        cse_id: <SEARCH ENGINE ID 1>
      - name: custom-search-2
        api_key: <GOOGLE API KEY 2>
        cse_id: <SEARCH ENGINE ID 2>
    fields:
       genre: true
       sc_first_publication: true
       sc_genre_categories: false
```

## Plugin development

- details available [here](https://beets.readthedocs.io/en/stable/dev/index.html)

### Setup local environment

- create a virtual environment `python -m venv /path/to/new/virtual/environment` [see](https://docs.python.org/3/library/venv.html)
- activate venv `source <venv path>/bin/activate`
- install all needed dependacies in order to run `beet` commands
- Make sure package is not in pip list output. I.e. uninstall if necessary.
- Set `PYTHONPATH` to include the path to the local `src` directory containing source code
