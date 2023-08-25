from unittest import mock
import pytest

from pymm_eventserver.data_structures import MMSettings




def test_java_settings_event(java_settings_event):
    assert java_settings_event.get_settings() is not None
    assert isinstance(java_settings_event.get_datastore(), mock.MagicMock)


def test_event_bus(event_bus):
    assert event_bus.acquisition_started_event
    assert event_bus.initialized
