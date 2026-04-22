from app.core.alert_engine import RowStyle
from app.core.events import Event, EventLevel, EventType
from app.models.domain import UIRow
from app.ui.event_handler import EventProcessor


class DummyTableManager:
    iids: dict[str, str] = {}


def test_update_keeps_my_offer_style_when_provider_matches_runtime_id():
    processor = EventProcessor(
        table_mgr=DummyTableManager(),
        rows_cache={},
        status_label_setter=lambda _text: None,
        logger=lambda _msg: None,
        audio_bell_fn=lambda: None,
        my_provider_ids_getter=lambda: ("30718165", "69728"),
    )
    row = UIRow(id_renglon="1", mejor_id_proveedor="30718165")
    payload = {"alert_style": RowStyle.DANGER.value, "outbid": False}
    ev = Event(level=EventLevel.INFO, type=EventType.UPDATE, message="test", payload=payload)

    style = processor._apply_event_decorations(row, payload, ev)

    assert style == RowStyle.MY_OFFER.value


def test_update_row_marks_auto_my_offer_when_provider_matches_runtime_id():
    processor = EventProcessor(
        table_mgr=DummyTableManager(),
        rows_cache={},
        status_label_setter=lambda _text: None,
        logger=lambda _msg: None,
        audio_bell_fn=lambda: None,
        my_provider_ids_getter=lambda: ("30718165", "69728"),
    )
    row = UIRow(id_renglon="1")
    payload = {
        "mejor_id_proveedor": "69728",
        "oferta_mia": False,
        "oferta_mia_auto": False,
    }
    ev = Event(level=EventLevel.INFO, type=EventType.UPDATE, message="test", payload=payload)

    processor._update_row_from_payload(row, payload, ev)

    assert row.oferta_mia_auto is True
    assert row.oferta_mia is True


def test_update_row_resolves_display_for_second_provider_id():
    processor = EventProcessor(
        table_mgr=DummyTableManager(),
        rows_cache={},
        status_label_setter=lambda _text: None,
        logger=lambda _msg: None,
        audio_bell_fn=lambda: None,
        my_provider_ids_getter=lambda: ("30718165", "69728"),
        provider_label_resolver=lambda provider_id: "Empresa Alias" if provider_id == "69728" else str(provider_id),
    )
    row = UIRow(id_renglon="1", desc="demo")
    payload = {
        "mejor_id_proveedor": "69728",
        "mejor_proveedor_txt": "Prov. 69728",
        "oferta_mia": False,
        "oferta_mia_auto": False,
    }
    ev = Event(level=EventLevel.INFO, type=EventType.UPDATE, message="test", payload=payload)

    processor._update_row_from_payload(row, payload, ev)

    assert row.oferta_mia_auto is True
    assert row.ultimo_oferente_txt == "Empresa Alias"
