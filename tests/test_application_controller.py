import pytest

import classes.ApplicationController as application_controller_module
from classes.ApplicationController import ApplicationController
from classes.streamer.streamers.IcecastStreamer import IcecastStreamer
from classes.streamer.streamers.ShoutcastStreamer import ShoutcastStreamer


class FakePrompt:
    """Input stand-in answering from a queue, then raising to end the test."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, text=''):
        self.prompts.append(text)
        if not self.answers:
            raise AssertionError('prompted more often than the test expected')
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer


class FakeFacade:
    """Facade stand-in recording what the controller publishes to it."""

    def __init__(self):
        self.icecast = 'unset'
        self.shoutcast = 'unset'
        self.protocols = None

    def set_icecast_streamer(self, relay):
        self.icecast = relay

    def set_shoutcast_streamer(self, relay):
        self.shoutcast = relay

    def set_protocols(self, protocols):
        self.protocols = protocols


@pytest.fixture
def controller():
    """A controller with a fake facade and relays that start successfully."""
    controller = ApplicationController()
    controller.audioHttpFacade = FakeFacade()
    controller._startRelay = lambda relay_class: f"{relay_class.__name__} relay"
    return controller


@pytest.fixture
def relays(request, monkeypatch):
    """Enable the relays named by the test's parameter and return their entries."""
    enabled = getattr(request, 'param', ('icecast', 'shoutcast'))
    monkeypatch.setattr(application_controller_module, 'ICECAST_ENABLED', 'icecast' in enabled)
    monkeypatch.setattr(application_controller_module, 'SHOUTCAST_ENABLED', 'shoutcast' in enabled)
    return ApplicationController()._configuredRelays()


def classes_of(entries):
    """Reduce relay entries to their classes, which is what the tests assert on."""
    return [entry[0] for entry in entries]


# -- _configuredRelays --

def test_no_relay_is_configured_when_both_are_disabled(monkeypatch):
    monkeypatch.setattr(application_controller_module, 'ICECAST_ENABLED', False)
    monkeypatch.setattr(application_controller_module, 'SHOUTCAST_ENABLED', False)

    assert ApplicationController()._configuredRelays() == []


def test_only_the_enabled_relay_is_configured(monkeypatch):
    monkeypatch.setattr(application_controller_module, 'ICECAST_ENABLED', False)
    monkeypatch.setattr(application_controller_module, 'SHOUTCAST_ENABLED', True)

    assert classes_of(ApplicationController()._configuredRelays()) == [ShoutcastStreamer]


def test_both_relays_are_configured_in_menu_order(monkeypatch):
    monkeypatch.setattr(application_controller_module, 'ICECAST_ENABLED', True)
    monkeypatch.setattr(application_controller_module, 'SHOUTCAST_ENABLED', True)

    assert classes_of(ApplicationController()._configuredRelays()) == [
        IcecastStreamer, ShoutcastStreamer
    ]


# -- _askForProtocol --

def test_first_choice_selects_the_direct_stream_only(controller, relays):
    assert controller._askForProtocol(relays, prompt=FakePrompt(['1'])) == []


def test_second_choice_selects_the_first_relay(controller, relays):
    selected = controller._askForProtocol(relays, prompt=FakePrompt(['2']))

    assert classes_of(selected) == [IcecastStreamer]


def test_third_choice_selects_the_second_relay(controller, relays):
    selected = controller._askForProtocol(relays, prompt=FakePrompt(['3']))

    assert classes_of(selected) == [ShoutcastStreamer]


def test_last_choice_selects_every_configured_relay(controller, relays):
    selected = controller._askForProtocol(relays, prompt=FakePrompt(['4']))

    assert classes_of(selected) == [IcecastStreamer, ShoutcastStreamer]


@pytest.mark.parametrize('relays', [('icecast',)], indirect=True)
def test_a_single_relay_is_not_offered_as_an_all_option(controller, relays):
    # With one relay there is nothing to combine, so 3 is out of range and the
    # menu asks again rather than quietly treating it as "all"
    prompt = FakePrompt(['3', '2'])

    selected = controller._askForProtocol(relays, prompt=prompt)

    assert classes_of(selected) == [IcecastStreamer]
    assert len(prompt.prompts) == 2
    assert prompt.prompts[0].endswith('(1-2): ')


@pytest.mark.parametrize('answer', ['', '0', '9', 'icecast', '-1'])
def test_an_invalid_choice_asks_again(controller, relays, answer):
    prompt = FakePrompt([answer, '1'])

    assert controller._askForProtocol(relays, prompt=prompt) == []
    assert len(prompt.prompts) == 2


def test_no_console_falls_back_to_every_configured_relay(controller, relays):
    # systemd units and containers run without stdin; the fallback has to leave
    # unattended deployments behaving exactly as their .env describes
    selected = controller._askForProtocol(relays, prompt=FakePrompt([EOFError()]))

    assert classes_of(selected) == [IcecastStreamer, ShoutcastStreamer]


def test_an_interrupt_falls_back_to_every_configured_relay(controller, relays):
    selected = controller._askForProtocol(relays, prompt=FakePrompt([KeyboardInterrupt()]))

    assert classes_of(selected) == [IcecastStreamer, ShoutcastStreamer]


# -- _startSelectedRelays --

def test_nothing_is_asked_when_no_relay_is_configured(controller, monkeypatch):
    monkeypatch.setattr(application_controller_module, 'ICECAST_ENABLED', False)
    monkeypatch.setattr(application_controller_module, 'SHOUTCAST_ENABLED', False)

    def fail(*args, **kwargs):
        raise AssertionError('a direct-only station must not be asked to choose')

    controller._askForProtocol = fail

    controller._startSelectedRelays()

    assert controller.protocols == ['direct']
    assert controller.icecastStreamer is None
    assert controller.shoutcastStreamer is None


def test_the_selected_relay_is_started_and_published(controller, relays):
    controller._askForProtocol = lambda entries, **kwargs: [entries[0]]

    controller._startSelectedRelays()

    assert controller.icecastStreamer == 'IcecastStreamer relay'
    assert controller.audioHttpFacade.icecast == 'IcecastStreamer relay'
    assert controller.protocols == ['direct', 'icecast']


def test_an_unselected_relay_is_left_alone(controller, relays):
    controller._askForProtocol = lambda entries, **kwargs: [entries[0]]

    controller._startSelectedRelays()

    assert controller.shoutcastStreamer is None
    assert controller.audioHttpFacade.shoutcast == 'unset'
    assert 'shoutcast' not in controller.protocols


def test_every_relay_is_started_when_all_are_selected(controller, relays):
    controller._askForProtocol = lambda entries, **kwargs: list(entries)

    controller._startSelectedRelays()

    assert controller.icecastStreamer == 'IcecastStreamer relay'
    assert controller.shoutcastStreamer == 'ShoutcastStreamer relay'
    assert controller.protocols == ['direct', 'icecast', 'shoutcast']


def test_a_relay_that_cannot_start_is_published_as_absent(controller, relays):
    # _startRelay reports a failure as None rather than raising, so the station
    # stays on the air and the dashboard shows the relay as disconnected
    controller._startRelay = lambda relay_class: None
    controller._askForProtocol = lambda entries, **kwargs: [entries[0]]

    controller._startSelectedRelays()

    assert controller.icecastStreamer is None
    assert controller.audioHttpFacade.icecast is None
    # and it is not advertised as an active protocol either
    assert controller.protocols == ['direct']


def test_relay_labels_read_the_way_the_manual_does():
    assert ApplicationController._relayLabel(IcecastStreamer) == 'Icecast'
    assert ApplicationController._relayLabel(ShoutcastStreamer) == 'Shoutcast'


# -- startup visibility (#61) --
#
# Logger suppresses every level, errors included, unless AUDIO_STREAMER_DEBUG is
# set, so anything the operator must see at startup has to be printed.

def test_a_direct_only_station_is_told_it_is_direct_only(controller, capsys, monkeypatch):
    monkeypatch.setattr(application_controller_module, 'ICECAST_ENABLED', False)
    monkeypatch.setattr(application_controller_module, 'SHOUTCAST_ENABLED', False)

    controller._startSelectedRelays()

    output = capsys.readouterr().out
    assert 'Streaming protocol: Direct' in output
    assert 'no relay is configured' in output


def test_a_direct_only_station_is_told_how_to_enable_a_relay(controller, capsys, monkeypatch):
    monkeypatch.setattr(application_controller_module, 'ICECAST_ENABLED', False)
    monkeypatch.setattr(application_controller_module, 'SHOUTCAST_ENABLED', False)

    controller._startSelectedRelays()

    output = capsys.readouterr().out
    assert 'ICECAST_ENABLED' in output
    assert 'SHOUTCAST_ENABLED' in output
    assert '.env.example' in output


def test_the_active_protocols_are_printed_after_the_relays_start(controller, relays, capsys):
    controller._askForProtocol = lambda entries, **kwargs: [entries[0]]

    controller._startSelectedRelays()

    assert 'Streaming protocol: Direct + Icecast' in capsys.readouterr().out


def test_every_active_protocol_is_printed(controller, relays, capsys):
    controller._askForProtocol = lambda entries, **kwargs: list(entries)

    controller._startSelectedRelays()

    assert 'Streaming protocol: Direct + Icecast + Shoutcast' in capsys.readouterr().out


def test_a_dropped_relay_is_not_printed_as_active(controller, relays, capsys):
    controller._startRelay = lambda relay_class: None
    controller._askForProtocol = lambda entries, **kwargs: [entries[0]]

    controller._startSelectedRelays()

    output = capsys.readouterr().out
    assert 'Streaming protocol: Direct' in output
    assert 'Icecast' not in output.split('Streaming protocol:')[1]


def test_a_relay_that_cannot_start_is_reported_on_the_console(capsys, mocker):
    # The Logger line alone is invisible without debug logging, which is how a
    # station could silently fall back to direct-only
    controller = ApplicationController()
    controller.audioStreamer = object()
    mocker.patch.object(IcecastStreamer, 'test_connection')
    mocker.patch.object(IcecastStreamer, '__init__',
                        side_effect=RuntimeError('Could not connect to Icecast'))

    assert controller._startRelay(IcecastStreamer) is None

    output = capsys.readouterr().out
    assert 'WARNING: Icecast relay disabled: Could not connect to Icecast' in output


def test_the_unattended_fallback_says_why_it_chose(controller, relays, capsys):
    controller._askForProtocol(relays, prompt=FakePrompt([EOFError()]))

    assert 'No console to choose on' in capsys.readouterr().out
