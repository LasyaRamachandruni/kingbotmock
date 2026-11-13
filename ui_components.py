"""Kingbot layout, copied from the library's Streamlit chatbot.

Visual source: sjsu-library/kingbotgpt (llamainchatbot.py and cbconfig.toml).
The CSS block below is the HIDEMENU stylesheet from that app. Result text
stays inside the same chat bubbles, avatars, sidebar, and button row.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import streamlit as st

from primo_search import TYPE_LABELS, build_expanded_search

ROOT = Path(__file__).resolve().parent
ASSISTANT_AVATAR = str(ROOT / "static" / "kingbot_icon.png")
USER_AVATAR = str(ROOT / "static" / "user_icon.png")
LIBRARY_LOGO = str(ROOT / "static" / "sjsu_library_logo.png")
KINGBOT_ICON = str(ROOT / "static" / "kingbot_icon.png")

# Preserved from llamainchatbot.py. Enter submits the question.
KINGBOT_CSS = """
<style>
.stApp [data-testid="stHeader"] {
 display:none;
}

p img{
 margin-bottom: 0.6rem;
}

[data-testid="stSidebarCollapseButton"] {
 display:none;
}

[data-testid="baseButton-headerNoPadding"] {
 display:none;
}

.stChatInput button{
 display:none;
}

#chat-with-sjsu-library-s-kingbot a {
 display:none;
}
</style>
"""

SIDEBAR_INTRO = (
    "KingbotGPT is an experimental python-based bot created by the university "
    "library's artificial intelligence (AI) team at San Jose State University. "
    "It is our newest model of the original After-Hours Kingbot Chatbot. "
    "Kingbot is intended to provide basic information about the library and "
    "library resources. Kingbot is not a research tool or a replacement for "
    "librarian and library staff expertise."
)

SIDEBAR_SEARCH_NOTE = (
    "This prototype can also search demonstration catalog records. It checks "
    "the SJSU collection first. Expanded collections are searched only when "
    "you choose that option."
)

POLICY_URL = "https://www.sjlibrary.org/policy/chatbot-policy"

QUICK_REPLIES = [
    {
        "label": "SJSU Library Hours",
        "question": "What are the SJSU library hours?",
        "answer": (
            "Current hours are posted on the library website, and they can "
            "change for finals and holidays. Please check the library site "
            "for today's building hours.\n\n"
            "https://library.sjsu.edu/"
        ),
    },
    {
        "label": "Start Your Research",
        "question": "How do I start my research?",
        "answer": (
            "OneSearch is the library's main search for books, articles, and "
            "more. Tell me whether you need a book, an article, or a "
            "dissertation, and I will check the SJSU collection first.\n\n"
            "[OneSearch](https://csu-sjsu.primo.exlibrisgroup.com/discovery/search?vid=01CALS_SJO:01CALS_SJO&lang=en)"
        ),
    },
    {
        "label": "Borrow A Laptop",
        "question": "How do I borrow a laptop from the SJSU library?",
        "answer": (
            "The library lends laptops and other equipment. See the library "
            "website or ask at a service desk for what is available today.\n\n"
            "https://library.sjsu.edu/"
        ),
    },
]


def apply_page_style() -> None:
    st.markdown(KINGBOT_CSS, unsafe_allow_html=True)


def render_sidebar() -> None:
    st.sidebar.image(LIBRARY_LOGO, use_container_width=True)
    st.sidebar.markdown("[SJSU Library](https://library.sjsu.edu/)")
    st.sidebar.markdown(SIDEBAR_INTRO)
    st.sidebar.markdown(SIDEBAR_SEARCH_NOTE)
    st.sidebar.markdown("\n\n")
    st.sidebar.link_button("See Kingbot Policy", POLICY_URL)
    st.sidebar.button("Start new search", on_click=reset_conversation)
    st.sidebar.checkbox(
        "Debug mode",
        key="debug",
        help="Shows the detected resource type, scope, and demonstration-data details. Off by default.",
    )
    if st.session_state.get("debug"):
        st.sidebar.caption(
            "Debug mode is on. These catalog records are demonstration data. No API key is loaded."
        )


def reset_conversation() -> None:
    """Clear the conversation without dropping the debug preference."""
    debug = st.session_state.get("debug", False)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.debug = debug


def render_header() -> None:
    _left, logo, title = st.columns([0.25, 0.12, 0.63], vertical_alignment="bottom")
    with logo:
        st.image(KINGBOT_ICON, width=78)
    with title:
        st.title("Kingbot GPT")
    st.markdown("\n\n")


def render_quick_buttons() -> str | None:
    columns = st.columns(3)
    selected = None
    for column, reply in zip(columns, QUICK_REPLIES):
        with column:
            if st.button(reply["label"], key=f"quick_{reply['label']}"):
                selected = reply
    return selected


def _inline(text: str) -> str:
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("*", "\\*")
        .replace("_", "\\_")
        .replace("`", "\\`")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def _render_debug(debug_info: dict) -> None:
    origin = "expanded" if debug_info["origin"] == "expanded" else "local"
    pc_value = "true" if debug_info["pc_availability"] else "false"
    resource = debug_info["resource_type"].replace("_", " ")
    st.caption(
        "\n".join(
            [
                f"Detected resource type: {resource}",
                f"Search scope: {debug_info['scope_label']}",
                f"pcAvailability value: {pc_value}",
                f"Number of results: {debug_info['result_count']}",
                f"Result set: {origin}",
                "Demonstration data: yes",
                f"API scope identifier: {debug_info['api_scope_identifier']}",
            ]
        )
    )


def _render_record(record: dict, debug: bool) -> None:
    st.markdown(f"**{_inline(record['title'])}**")
    st.markdown(f"{_inline(record['author'])} · {record['publication_year']}")
    st.markdown(f"Resource type: {record.get('display_type', TYPE_LABELS.get(record['resource_type'], 'Resource'))}")
    st.markdown(record["availability_label"])
    st.markdown(f"Collection: {_inline(record['collection'])}")
    if record.get("request_note"):
        st.markdown(record["request_note"])
    # Streamlit 1.40 link buttons do not take a key. The record URL keeps each one distinct.
    st.link_button("View record", record["url"])
    if debug:
        origin = "expanded" if record.get("result_origin") == "expanded" else "local"
        st.caption(f"Demonstration data. This result is {origin}.")


def _pause_for_expanded_search() -> None:
    """Keep the loading message on screen long enough to read."""
    if os.environ.get("KINGBOT_SKIP_DELAY") == "1":
        return
    time.sleep(0.6)


def render_messages() -> None:
    """Draw stored turns. The expanded search runs only from its button."""
    debug = bool(st.session_state.get("debug"))
    for index, message in enumerate(st.session_state.messages):
        role = message["role"]
        avatar = USER_AVATAR if role == "user" else ASSISTANT_AVATAR
        with st.chat_message(role, avatar=avatar):
            if message["kind"] == "text":
                st.markdown(message["content"])
                continue

            local = message["local"]
            if local.get("lead"):
                st.markdown(local["lead"])
            if local.get("notice") and local["notice"] not in local.get("lead", ""):
                st.markdown(local["notice"])
            if local.get("followup"):
                st.markdown(local["followup"])
            st.caption(f"Search source: {local['search_source']}")
            for record_index, record in enumerate(local["results"]):
                if record_index:
                    st.markdown("---")
                _render_record(record, debug)
            if debug:
                _render_debug(local["debug"])

            expanded = message.get("expanded")
            if expanded:
                st.markdown("---")
                st.markdown(f"**{expanded['heading']}**")
                st.markdown(expanded["explanation"])
                if expanded.get("notice"):
                    st.markdown(expanded["notice"])
                if expanded.get("followup"):
                    st.markdown(expanded["followup"])
                for record_index, record in enumerate(expanded["results"]):
                    if record_index:
                        st.markdown("---")
                    _render_record(record, debug)
                if debug:
                    _render_debug(expanded["debug"])
            elif local.get("show_expand"):
                if st.button(
                    "Search expanded collections",
                    key=f"expand_{index}",
                    help="Search CSU+ and interlibrary loan collections. This does not run automatically.",
                ):
                    with st.spinner("Searching expanded collections..."):
                        _pause_for_expanded_search()
                        try:
                            expanded = build_expanded_search(message["parsed"])
                        except Exception:
                            st.session_state.error_message = (
                                "The expanded search could not be completed. Please try again."
                            )
                            expanded = None
                    if expanded is not None:
                        message["expanded_requested"] = True
                        message["expanded"] = expanded
                        st.session_state.expanded_requested = True
                        st.session_state.expanded_results = expanded["results"]
                        st.session_state.search_source = expanded["search_source"]
                        st.session_state.search_calls = st.session_state.get("search_calls", 0) + 1
                        st.session_state.error_message = None
                    st.rerun()
