from __future__ import annotations

from build._mechanism import classify, BINDING_ACTION, SIGNAL, CONTEXT


def test_enforcement_is_binding():
    assert classify("enforcement") == BINDING_ACTION


def test_final_rule_is_binding():
    assert classify("final rule") == BINDING_ACTION


def test_proposed_rule_is_signal():
    assert classify("proposed rule") == SIGNAL


def test_advisory_is_signal():
    assert classify("advisory") == SIGNAL


def test_guidance_is_signal():
    assert classify("guidance") == SIGNAL


def test_comment_request_is_signal():
    assert classify("comment request") == SIGNAL


def test_speech_is_context():
    assert classify("speech") == CONTEXT


def test_press_release_is_context():
    assert classify("press release") == CONTEXT


def test_bulletin_is_context():
    assert classify("bulletin") == CONTEXT


def test_trend_report_is_context():
    assert classify("trend report") == CONTEXT


def test_standard_is_context():
    assert classify("standard") == CONTEXT


def test_insights_is_context():
    assert classify("insights") == CONTEXT


def test_event_announcement_is_context():
    assert classify("event announcement") == CONTEXT


def test_newsletter_is_context():
    assert classify("newsletter") == CONTEXT


def test_unknown_defaults_to_context():
    assert classify("something_new") == CONTEXT


def test_empty_string_defaults_to_context():
    assert classify("") == CONTEXT
