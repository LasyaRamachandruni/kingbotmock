"""SJSU Library Kingbot prototype for collection search.

The page layout matches the library's Kingbot Streamlit app. Catalog
search is separate from this file: app.py calls build_local_search()
and the expanded-search button calls build_expanded_search(). Both go
through search_primo() in primo_search.py, which is the place to
connect the live Primo API later.
"""

from __future__ import annotations

import streamlit as st

from primo_search import build_local_search
from ui_components import (
    apply_page_style,
    render_header,
    render_messages,
    render_quick_buttons,
    render_sidebar,
)


def init_state() -> None:
    """Create conversation state once. Later reruns reuse these values."""
    defaults = {
        "messages": [],
        "current_question": "",
        "resource_type": None,
        "first_results": [],
        "expanded_requested": False,
        "expanded_results": [],
        "search_source": None,
        "error_message": None,
        "search_calls": 0,
        "debug": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def ask_catalog(query: str) -> None:
    """Search the SJSU collection once and store the reply."""
    st.session_state.current_question = query
    st.session_state.expanded_requested = False
    st.session_state.expanded_results = []
    st.session_state.error_message = None
    st.session_state.messages.append({"role": "user", "kind": "text", "content": query})
    try:
        with st.spinner("In progress..."):
            local = build_local_search(query)
        st.session_state.search_calls += 1
    except Exception:
        st.session_state.error_message = (
            "The catalog search could not be completed. Please try again."
        )
        st.session_state.messages.append(
            {
                "role": "assistant",
                "kind": "text",
                "content": st.session_state.error_message,
            }
        )
        return

    st.session_state.resource_type = local["resource_type"]
    st.session_state.first_results = local["results"]
    st.session_state.search_source = local["search_source"]
    st.session_state.messages.append(
        {
            "role": "assistant",
            "kind": "search",
            "parsed": local["parsed"],
            "local": local,
            "expanded_requested": False,
            "expanded": None,
        }
    )


def ask_canned(reply: dict) -> None:
    """Answer a Kingbot shortcut without calling the catalog search."""
    st.session_state.current_question = reply["question"]
    st.session_state.messages.append(
        {"role": "user", "kind": "text", "content": reply["question"]}
    )
    st.session_state.messages.append(
        {"role": "assistant", "kind": "text", "content": reply["answer"]}
    )


def main() -> None:
    st.set_page_config(
        page_title="Kingbot - SJSU Library",
        page_icon="🤖",
        initial_sidebar_state="expanded",
    )
    apply_page_style()
    init_state()
    render_sidebar()
    render_header()

    selected = render_quick_buttons()
    if selected:
        ask_canned(selected)

    if query := st.chat_input("Ask me about the SJSU Library!"):
        ask_catalog(query)

    if st.session_state.error_message and not st.session_state.messages:
        st.markdown(st.session_state.error_message)

    render_messages()


if __name__ == "__main__":
    main()
