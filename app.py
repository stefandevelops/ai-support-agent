"""Ridgeway Support Copilot — Streamlit UI. Nothing is emailed from this app."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape

import streamlit as st

from support_copilot.clock import today
from support_copilot.llm import engine_label, llm_configured
from support_copilot.models import Intent, ReviewCase, Ticket, TicketStatus, Urgency
from support_copilot.store import ReviewStore

st.set_page_config(
    page_title="Ridgeway Support Copilot",
    page_icon="🚲",
    layout="wide",
    initial_sidebar_state="expanded",
)

URGENCY_COLORS = {
    Urgency.LOW: ("#3F6F52", "#E4EFE8"),
    Urgency.MEDIUM: ("#8A5A12", "#F4E6CC"),
    Urgency.HIGH: ("#9A3412", "#F6D7C8"),
    Urgency.CRITICAL: ("#9B1C1C", "#F5D0D0"),
}

STATUS_LABELS = {
    TicketStatus.PENDING: "Pending review",
    TicketStatus.APPROVED: "Approved",
    TicketStatus.APPROVED_WITH_EDITS: "Approved (edited)",
    TicketStatus.REJECTED: "Rejected",
}


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,560;9..144,640&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
        html, body, [class*="css"] { font-family: "IBM Plex Sans", sans-serif; }
        .block-container { padding-top: 1.4rem; max-width: 1400px; }
        h1, h2, h3, .brand { font-family: Fraunces, Georgia, serif; }
        #MainMenu, footer, header { visibility: hidden; }
        .stDeployButton { display: none; }
        .hero {
            background: linear-gradient(180deg, #1F3D30 0%, #2F6B4F 100%);
            color: #F6F3EC;
            padding: 1.35rem 1.5rem 1.2rem;
            border-radius: 18px;
            margin-bottom: 1rem;
        }
        .hero h1 { font-size: 1.85rem; margin: 0 0 0.25rem; color: #F6F3EC; }
        .hero p { margin: 0; color: #D7E4DB; font-size: 0.98rem; }
        .mode-chip {
            display: inline-block;
            margin-top: 0.7rem;
            background: #F6F3EC;
            color: #1F3D30;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            padding: 0.22rem 0.55rem;
            border-radius: 999px;
        }
        .pill {
            display: inline-block;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.18rem 0.5rem;
            border-radius: 999px;
            margin-right: 0.35rem;
            margin-bottom: 0.25rem;
        }
        .card {
            background: #FFFcf7;
            border: 1px solid #E4D9C5;
            border-radius: 14px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.8rem;
        }
        .muted { color: #6B6560; font-size: 0.86rem; }
        .email-body {
            white-space: pre-wrap;
            font-size: 0.95rem;
            line-height: 1.45;
            color: #1C1917;
        }
        .notice {
            background: #EFE9DD;
            border-left: 4px solid #2F6B4F;
            padding: 0.65rem 0.85rem;
            border-radius: 0 10px 10px 0;
            font-size: 0.9rem;
            margin-bottom: 0.8rem;
        }
        div[data-testid="stMetric"] {
            background: #FFFcf7;
            border: 1px solid #E4D9C5;
            padding: 0.7rem 0.85rem;
            border-radius: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _pill(label: str, fg: str, bg: str) -> str:
    return f'<span class="pill" style="color:{fg};background:{bg}">{label}</span>'


def _urgency_pill(urgency: Urgency) -> str:
    fg, bg = URGENCY_COLORS[urgency]
    return _pill(urgency.value.upper(), fg, bg)


def _init_store() -> ReviewStore:
    if "store" not in st.session_state:
        st.session_state.store = ReviewStore()
    if "selected_id" not in st.session_state:
        pending = st.session_state.store.pending()
        st.session_state.selected_id = pending[0].ticket.id if pending else None
    return st.session_state.store


def _select(ticket_id: str) -> None:
    st.session_state.selected_id = ticket_id


def main() -> None:
    _inject_css()
    store = _init_store()
    metrics = store.metrics()
    demo_mode = not llm_configured()

    st.markdown(
        f"""
        <div class="hero">
          <div class="brand">Ridgeway</div>
          <h1>Support Copilot</h1>
          <p>Drafts a reply from the order and the policy. A person still has to send it.</p>
          <span class="mode-chip">{"Demo engine · no API key" if demo_mode else "LLM engine · " + engine_label()}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rate = f"{metrics.approval_rate:.0%}" if metrics.handled else "—"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("In queue", metrics.queued)
    c2.metric("Tickets handled", metrics.handled)
    c3.metric("Approval rate", rate)
    c4.metric("Edited before approve", metrics.approved_with_edits)

    st.caption(
        f"Demo clock is {today().isoformat()} so return windows stay stable. "
        "Approve / reject never sends email."
    )

    with st.sidebar:
        st.subheader("Inbox")
        view = st.radio("Show", ["Pending review", "Handled", "All"], label_visibility="collapsed")
        if view == "Pending review":
            visible = store.pending()
        elif view == "Handled":
            visible = store.decided()
        else:
            visible = list(store.cases.values())

        if not visible:
            st.info("Nothing in this list. Reset the demo or submit a new email.")
        for case in visible:
            ticket = case.ticket
            label = f"{ticket.id} · {ticket.subject}"
            if st.button(label, key=f"q-{ticket.id}", use_container_width=True):
                _select(ticket.id)

        st.divider()
        with st.expander("Paste a new customer email"):
            with st.form("new_ticket"):
                name = st.text_input("From name", "Alex Rivera")
                email = st.text_input("From email", "alex.rivera@example.com")
                subject = st.text_input("Subject", "Where is my order?")
                body = st.text_area(
                    "Body",
                    "Hi, I ordered RW-10510 last week and tracking hasn't updated. What's going on?",
                    height=140,
                )
                submitted = st.form_submit_button("Draft a reply")
            if submitted:
                new_id = f"T-{datetime.now(timezone.utc).strftime('%H%M%S')}"
                ticket = Ticket(
                    id=new_id,
                    received_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    from_name=name,
                    from_email=email,
                    subject=subject,
                    body=body,
                )
                case = store.add_ticket(ticket)
                _select(case.ticket.id)
                st.success(f"Drafted {new_id}. It is waiting in the queue.")
                st.rerun()

        if st.button("Reset demo data", use_container_width=True):
            st.session_state.store = ReviewStore()
            pending = st.session_state.store.pending()
            st.session_state.selected_id = pending[0].ticket.id if pending else None
            st.rerun()

        st.caption("Sample shop: Ridgeway e-bikes. All names and orders are fake.")

    selected_id = st.session_state.selected_id
    if not selected_id or selected_id not in store.cases:
        st.info("Select a ticket from the inbox.")
        return

    case = store.get(selected_id)
    _render_case(store, case)


def _render_case(store: ReviewStore, case: ReviewCase) -> None:
    output = case.output
    ticket = case.ticket
    intent = output.classification.intent
    urgency = output.classification.urgency
    left, right = st.columns((1.35, 1), gap="large")

    with left:
        st.markdown(
            _urgency_pill(urgency)
            + _pill(intent.value.replace("_", " "), "#1F3D30", "#D7E4DB")
            + _pill(output.resolution.code.value, "#1C1917", "#E4D9C5")
            + _pill(STATUS_LABELS[case.status], "#1C1917", "#EFE9DD"),
            unsafe_allow_html=True,
        )
        st.markdown(f"### {ticket.subject}")
        st.caption(
            f"{ticket.id} · {ticket.from_name} · {ticket.from_email} · {ticket.received_at}"
        )
        with st.container(border=True):
            st.markdown("**Customer email**")
            st.markdown(ticket.body)
        st.caption(
            f"{output.classification.rationale} Engine: {output.classification.engine} "
            f"→ draft: {output.draft.engine}."
        )

        reply = st.text_area("Draft reply", value=case.reply, height=200, key=f"reply-{ticket.id}")
        note = st.text_area(
            "Internal note (not sent to the customer)",
            value=case.internal_note,
            height=120,
            key=f"note-{ticket.id}",
        )

        if case.status == TicketStatus.PENDING:
            a, b, c = st.columns(3)
            with a:
                if st.button("Approve", type="primary", use_container_width=True):
                    store.approve(ticket.id, reply, note)
                    st.toast("Approved — still not emailed. Copy it into the helpdesk to send.")
                    st.rerun()
            with b:
                reject_reason = st.text_input("Reject reason", placeholder="Optional", key=f"rej-{ticket.id}")
            with c:
                if st.button("Reject", use_container_width=True):
                    store.reject(ticket.id, reject_reason)
                    st.toast("Rejected. Draft stays on the record.")
                    st.rerun()
        else:
            st.success(
                f"{STATUS_LABELS[case.status]}"
                + (f" · {case.rejection_reason}" if case.rejection_reason else "")
                + ". This app does not send mail."
            )

    with right:
        st.markdown("**Order**")
        order = output.order
        if order is None:
            st.warning("No order matched. Resolution is escalate.")
        else:
            with st.container(border=True):
                st.markdown(f"**{order.id}** · {order.product}")
                c_a, c_b = st.columns(2)
                c_a.markdown(f"Customer  \n**{order.customer_name}**")
                c_b.markdown(f"Email  \n**{order.email}**")
                c_a.markdown(f"Amount  \n**${order.amount:,.2f}**")
                c_b.markdown(f"Status  \n**{order.status}**")
                c_a.markdown(f"Ordered  \n**{order.ordered_at}**")
                c_b.markdown(f"Shipped  \n**{order.shipped_at or '—'}**")
                c_a.markdown(f"Delivered  \n**{order.delivered_at or '—'}**")
                c_b.markdown(f"Tracking  \n**{(order.carrier or '') + ' ' + (order.tracking or '—')}**")
                c_a.markdown(f"Custom  \n**{'yes' if order.is_custom else 'no'}**")
                c_b.markdown(f"In stock  \n**{'yes' if order.in_stock else 'no'}**")
                c_a.markdown(f"Serial  \n**{order.serial or '—'}**")
                if order.notes:
                    st.caption(order.notes)

        st.markdown("**Policy used**")
        if not output.policies:
            st.caption("No policy chunks retrieved.")
        for chunk in output.policies:
            with st.expander(f"{chunk.title} · {chunk.topic}", expanded=chunk == output.policies[0]):
                st.markdown(escape(chunk.body))

        st.markdown("**Resolution**")
        with st.container(border=True):
            st.code(output.resolution.code.value, language=None)
            st.markdown(output.resolution.reason)

        if intent == Intent.BILLING:
            st.info("Billing stays with a person on purpose. The draft only acknowledges the ticket.")


if __name__ == "__main__":
    main()
