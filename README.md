# SJSU Library Kingbot collection-search prototype

This is a Streamlit prototype of Kingbot, the Dr. Martin Luther King, Jr. Library chatbot. It shows a patron question being searched in the SJSU collection first. Expanded collections are searched only after the patron clicks **Search expanded collections**.

The page reuses the current Kingbot layout: sidebar, library logo, Kingbot icon, title, three shortcut buttons, chat avatars, and the stylesheet from the library's Streamlit app. Catalog answers appear in the same chat bubbles.

The catalog behind this prototype is demonstration data. It does not call the Primo API and it does not contain an API key.

## Run the prototype

From this folder:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

On macOS or Linux, activate the environment with `source .venv/bin/activate`.

Open the local URL Streamlit prints. Press Enter to send a question. The send button is hidden, matching the current Kingbot stylesheet.

Check the search logic without opening the browser:

```bash
python primo_search.py
```

That command runs the demonstration questions and prints `All demonstration searches passed.`

## Try these questions

1. `Find books about Chicano comics.`
2. `Find books about video-game history.`
3. `Find the dissertation titled Influences on Career Decisions of International Students Attending Community Colleges in the United States.`
4. `Do you have The Culture of Fengshui in Korea: An Exploration of East Asian Geomancy?`
5. `Find scholarly articles about artificial intelligence.`
6. `Do you have Borderlands Ink: A History of Chicano Comics in California?`
7. `Find books about lunar librarianship.`

Every catalog search lists the SJSU results first, then offers **Search expanded collections**. Questions 1, 2, 4, and 5 return SJSU demonstration records and still show that option. Questions 3, 6, and 7 do not find a useful local record, so the list starts with the no-match message and the same button. Question 6 returns a requestable expanded record. Question 7 stays empty after the expanded search. Question 3 finds the dissertation only in the expanded search.

This extra question checks the book-review filter:

`Do you have Artificial Intelligence: A Guide for Thinking Humans?`

Kingbot reports the related review and does not present that review as the book. Expanded search then shows the book as not held by SJSU.

The shortcut buttons (hours, research, and laptops) stay on the page so the prototype still looks like Kingbot. They do not call the catalog search.

Use **Start new search** in the sidebar to clear the conversation. **Debug mode** is off by default. When it is on, each reply shows the detected resource type, search scope, `pcAvailability` value, result count, and whether the set is local or expanded. It also labels the records as demonstration data. It does not show an API key.

## How the mock search works

1. The question is read once, when it is submitted. Streamlit reruns do not search again. The reply is stored in `st.session_state`.
2. Kingbot chooses one resource type: books, articles, dissertations, or a general search. A question that names more than one type is searched as the first type only.
3. A known-item question such as "Do you have ...?" or "titled ..." searches the title instead of mixing every format.
4. The first call is `search_primo(query, scope="Everything", pc_availability=False, resource_type=...)`. In this prototype, `Everything` represents **SJSU Collections / Everything**.
5. Results are validated before they are shown. The validator keeps the requested resource type, drops a book review that was classified as an article, prefers an exact title, and keeps SJSU-owned records for the first search.
6. The patron sees `Search source: SJSU Library collection`. SJSU-owned copies say **Available through SJSU Library**.
7. After the SJSU result list, **Search expanded collections** is always offered. That search does not run until the button is clicked. The loading message is `Searching expanded collections...`.
8. The second call is `search_primo(query, scope="Expanded Search", pc_availability=True, resource_type=...)`. Those records say they are not held by SJSU and may be requestable through CSU+ or interlibrary loan. The first reply stays on screen.

`search_primo()` in `primo_search.py` is the only function the interface uses. It currently returns `search_primo_mock()`.

## Connect the live Primo API later

Do this in `primo_search.py`. Leave `app.py` and `ui_components.py` on `search_primo()`.

1. Confirm the real values with the library. The visible OneSearch names are not assumed to be the API scope codes. Enter the codes in `SCOPE_IDENTIFIERS`:
   - `Everything` / `SJSU Collections / Everything` for the first search
   - `Expanded Search` for the second search
2. Confirm `PRIMO_VID`, the API host, the tab code, and `RESOURCE_TYPE_FACETS`.
3. Confirm what `pcAvailability` means in this tenant. This prototype sends `false` for the SJSU search and `true` for expanded search, as requested. In some Primo tenants that flag means "physically available only," which is a different search.
4. Store the key outside the code:
   - Environment variable: `PRIMO_API_KEY`
   - Or Streamlit secrets:

```toml
[primo]
api_key = "paste the key in the Streamlit secrets manager, not in git"
```

5. Implement `search_primo_live(query, scope, pc_availability, resource_type)`. A request sketch is in that function. Do not print the key or put it in the page.
6. Change the return line inside `search_primo()` from `search_primo_mock(...)` to `search_primo_live(...)`.
7. Map the Primo JSON into the fields the page already displays: title, author, publication year, resource type, availability, collection, ownership, request information, and URL.

The live function should keep the same parameters: `query`, `scope`, `pc_availability`, and `resource_type`.

## Files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit page, conversation state, and the first search |
| `ui_components.py` | Kingbot layout, CSS, chat bubbles, and the expanded-search button |
| `primo_search.py` | Question parsing, mock search, validation, and the live-API stub |
| `mock_primo_data.json` | Demonstration catalog records |
| `.streamlit/config.toml` | Kingbot theme colors and fonts |
| `static/` | Kingbot icon, user icon, and SJSU King Library logo |
| `requirements.txt` | Streamlit 1.40.2, the version used by the current Kingbot app |

## Limits to confirm with Jessie or the SJSU Library team

- The exact Primo scope identifiers, tab, view id, and resource-type facet codes.
- Whether `pcAvailability=true` is really the expanded-search switch for this tenant.
- Whether an expanded search should also repeat SJSU-owned records, or only show items that are not held locally. This prototype shows the non-local records.
- Whether CSU+ and interlibrary loan should stay as one label or be split.
- Ownership in the demonstration file is scripted for the demo. It is not a claim about the live SJSU collection. `Borderlands Ink` is a fictional demonstration title. The other titles use real bibliographic details so the examples are recognizable.
- Record links point at `library.sjsu.edu/kingbot-demo/...` and are not live catalog links.
- The public Kingbot site was not loading while this prototype was built, so the layout follows the [kingbotgpt](https://github.com/sjsu-library/kingbotgpt) source: `llamainchatbot.py`, `cbconfig.toml`, and `.streamlit/config.toml`.
- The hours and laptop shortcuts point patrons to the library website instead of stating today's hours or lending rules.
