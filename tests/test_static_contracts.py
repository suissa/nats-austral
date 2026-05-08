"""Static contract tests for the Austral NATS client.

The execution environment used by this repository does not currently provide an
Austral compiler.  These tests therefore lock down the source-level API and the
safety/lifecycle invariants that the implementation promises to uphold.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT_INTERFACE = ROOT / "src" / "Nats" / "Client.aui"
CLIENT_BODY = ROOT / "src" / "Nats" / "Client.aum"
DESIGN_DOC = ROOT / "docs" / "DESIGN.md"
README = ROOT / "README.md"
EXAMPLE = ROOT / "examples" / "Subscribe.aum"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def without_austral_comments(source: str) -> str:
    return "\n".join(line.split("--", 1)[0] for line in source.splitlines())


def test_expected_repository_files_exist() -> None:
    """The client, design notes, example, and test suite must be versioned."""
    for path in (CLIENT_INTERFACE, CLIENT_BODY, DESIGN_DOC, README, EXAMPLE):
        assert path.is_file(), f"missing expected file: {path.relative_to(ROOT)}"


def test_public_api_exposes_linear_client_and_event_without_event_escape_hatches() -> None:
    """Event is linear, but public code must not receive or destroy it directly."""
    interface_source = read(CLIENT_INTERFACE)

    assert "type Client: Linear;" in interface_source
    assert "type Event: Linear;" in interface_source

    public_function_lines = [
        line.strip()
        for line in interface_source.splitlines()
        if line.strip().startswith("function ")
    ]

    functions_that_mention_event = [
        line for line in public_function_lines if re.search(r"\bEvent\b", line)
    ]
    assert functions_that_mention_event == [], (
        "public functions must not accept or return Event; subscribe owns the "
        "linear event lifecycle internally"
    )

    assert "destroyEvent" not in interface_source


def test_typeclasses_and_algebraic_data_types_are_declared() -> None:
    """The API must keep bounded polymorphism and ADT-based error handling."""
    interface_source = read(CLIENT_INTERFACE)

    for expected in (
        "union NatsError: Free is",
        "case ConnectionFailed;",
        "case PublishFailed;",
        "case SubscribeFailed;",
        "case InboxFull;",
        "case PayloadTooLarge;",
        "case NoMessageAvailable;",
        "case AlreadyClosed;",
        "union NatsResult[T: Type]: Type is",
        "case Ok(T);",
        "case Err(NatsError);",
        "union MessageKind: Free is",
        "case PlainMessage;",
        "case RequestMessage;",
        "case ReplyMessage;",
        "typeclass Encodable(T: Free) is",
        "typeclass Decodable(T: Free) is",
        "typeclass HandlesMessage(H: Linear) is",
    ):
        assert expected in interface_source


def test_subscribe_auto_consumes_event_before_returning_to_application_code() -> None:
    """subscribe must construct a linear Event and consume it at the module boundary."""
    body_source = read(CLIENT_BODY)

    assert "record Event: Linear is" in body_source
    assert "function copyPayloadAndAutoDestroyEvent(client: Client, event: Event): Client is" in body_source
    assert "let { subject: Subject, reply_to: Subject, payload: Payload, kind: MessageKind } := event;" in body_source

    subscribe_match = re.search(
        r"generic \[H: Linear\]\s+function subscribe\(.*?\): NatsResult\[Client\] is(?P<body>.*?)\n    end;",
        body_source,
        flags=re.DOTALL,
    )
    assert subscribe_match is not None, "subscribe implementation not found"
    subscribe_body = subscribe_match.group("body")

    event_creation_index = subscribe_body.find("let event: Event := Event(")
    copy_index = subscribe_body.find("copyPayloadAndAutoDestroyEvent(")
    handler_index = subscribe_body.find("handleMessage(handler, copied_client)")

    assert event_creation_index != -1, "subscribe must wrap the native message as Event"
    assert copy_index != -1, "subscribe must copy payload and consume Event internally"
    assert handler_index != -1, "subscribe must invoke the user handler after copying"
    assert event_creation_index < copy_index < handler_index
    assert "destroyEvent" not in subscribe_body


def test_safe_arithmetic_is_used_for_inbox_accounting() -> None:
    """Inbox accounting must use explicit trapping arithmetic instead of infix math."""
    body_source = read(CLIENT_BODY)

    assert "trappingAdd" in body_source
    assert "let next_count: Index := trappingAdd(inbox_count, 1);" in body_source
    assert "inbox_count + 1" not in body_source
    assert "1 + inbox_count" not in body_source


def test_no_forbidden_runtime_features_are_introduced() -> None:
    """Lock down the repository against constructs rejected by the design goals."""
    source_files = [CLIENT_INTERFACE, CLIENT_BODY, EXAMPLE]
    combined_source = without_austral_comments("\n".join(read(path) for path in source_files))

    forbidden_patterns = {
        "try/catch blocks": r"\btry\b|\bcatch\b",
        "exceptions/throws": r"\bthrow\b|\braise\b|\bexception\b",
        "macros": r"\bmacro\b",
        "reflection": r"\breflect\b|\breflection\b",
        "Java-style annotations": r"@[A-Za-z_]",
        "pre/post increment": r"\+\+|--",
        "first-class async": r"\basync\b|\bawait\b",
        "global declarations": r"\bglobal\b",
    }

    for description, pattern in forbidden_patterns.items():
        assert re.search(pattern, combined_source, flags=re.IGNORECASE) is None, (
            f"forbidden construct found: {description}"
        )


def test_documentation_records_the_linear_event_contract() -> None:
    """Docs must describe the lifecycle guaranteed by the source-level contract."""
    design_source = read(DESIGN_DOC)
    readme_source = read(README)

    for expected in (
        "Linear events",
        "Automatic event disposal at the subscribe boundary",
        "copy payload bytes into Client inbox",
        "consume Event by destructuring in module body",
    ):
        assert expected in design_source

    assert "Linear event policy" in readme_source
    assert "Application\ncode therefore does not need" in readme_source
