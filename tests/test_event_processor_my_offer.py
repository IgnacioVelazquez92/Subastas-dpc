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
    row = UIRow(id_renglon="1", desc="demo", mejor_id_proveedor="30718165", oferta_mia_slot=1)
    payload = {"alert_style": RowStyle.DANGER.value, "outbid": False}
    ev = Event(level=EventLevel.INFO, type=EventType.UPDATE, message="test", payload=payload)

    style = processor._apply_event_decorations(row, payload, ev)

    assert style == RowStyle.MY_OFFER_1.value


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
    assert row.oferta_mia_slot == 2


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
    assert row.oferta_mia_slot == 2


def test_update_keeps_different_style_for_first_and_second_provider_ids():
    processor = EventProcessor(
        table_mgr=DummyTableManager(),
        rows_cache={},
        status_label_setter=lambda _text: None,
        logger=lambda _msg: None,
        audio_bell_fn=lambda: None,
        my_provider_ids_getter=lambda: ("30842904", "30884734"),
    )
    ev = Event(level=EventLevel.INFO, type=EventType.UPDATE, message="test", payload={})
    row_id_1 = UIRow(id_renglon="1", desc="demo 1", mejor_id_proveedor="30842904", oferta_mia_slot=1)
    row_id_2 = UIRow(id_renglon="2", desc="demo 2", mejor_id_proveedor="30884734", oferta_mia_slot=2)

    style_1 = processor._apply_event_decorations(row_id_1, {"alert_style": RowStyle.WARNING.value, "outbid": False}, ev)
    style_2 = processor._apply_event_decorations(row_id_2, {"alert_style": RowStyle.WARNING.value, "outbid": False}, ev)

    assert style_1 == RowStyle.MY_OFFER_1.value
    assert style_2 == RowStyle.MY_OFFER_2.value


def test_update_marks_third_provider_slot_and_style():
    processor = EventProcessor(
        table_mgr=DummyTableManager(),
        rows_cache={},
        status_label_setter=lambda _text: None,
        logger=lambda _msg: None,
        audio_bell_fn=lambda: None,
        my_provider_ids_getter=lambda: ("111", "222", "333"),
    )
    row = UIRow(id_renglon="3", desc="demo 3")
    payload = {
        "mejor_id_proveedor": "333",
        "oferta_mia": False,
        "oferta_mia_auto": False,
        "matched_my_provider_slot": 3,
    }
    ev = Event(level=EventLevel.INFO, type=EventType.UPDATE, message="test", payload=payload)

    processor._update_row_from_payload(row, payload, ev)
    style = processor._apply_event_decorations(
        row,
        {"alert_style": RowStyle.WARNING.value, "outbid": False},
        ev,
    )

    assert row.oferta_mia_auto is True
    assert row.oferta_mia_slot == 3
    assert style == RowStyle.MY_OFFER_3.value
