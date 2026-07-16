import config
from actions import (
    ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_IDLE,
    ACTION_DRINK, ACTION_VOTE_MIGRATE, ACTION_PICKUP, ACTION_EAT,
    ACTION_TO_DELTA, TIMED_ACTIONS, FREE_ACTIONS, ACTION_SPEAK_BASE,
    action_speak, is_speak_action, speak_letter_index, action_label,
)


class TestSpeakEncoding:
    def test_roundtrip(self):
        for idx in range(len(config.ALPHABET)):
            action = action_speak(idx)
            assert is_speak_action(action)
            assert speak_letter_index(action) == idx

    def test_speak_actions_start_at_base(self):
        assert action_speak(0) == ACTION_SPEAK_BASE

    def test_non_speak_actions_are_not_speak(self):
        for a in (ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT,
                  ACTION_IDLE, ACTION_DRINK, ACTION_VOTE_MIGRATE,
                  ACTION_PICKUP, ACTION_EAT):
            assert not is_speak_action(a)


class TestActionSets:
    def test_timed_and_free_are_disjoint(self):
        assert TIMED_ACTIONS.isdisjoint(FREE_ACTIONS)

    def test_vote_migrate_is_free(self):
        assert ACTION_VOTE_MIGRATE in FREE_ACTIONS
        assert ACTION_VOTE_MIGRATE not in TIMED_ACTIONS

    def test_movement_and_survival_actions_are_timed(self):
        for a in (ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT,
                  ACTION_IDLE, ACTION_DRINK, ACTION_PICKUP, ACTION_EAT):
            assert a in TIMED_ACTIONS


class TestActionToDelta:
    def test_directions(self):
        assert ACTION_TO_DELTA[ACTION_UP] == (0, -1)
        assert ACTION_TO_DELTA[ACTION_DOWN] == (0, 1)
        assert ACTION_TO_DELTA[ACTION_LEFT] == (-1, 0)
        assert ACTION_TO_DELTA[ACTION_RIGHT] == (1, 0)

    def test_idle_and_drink_do_not_move(self):
        assert ACTION_TO_DELTA[ACTION_IDLE] == (0, 0)
        assert ACTION_TO_DELTA[ACTION_DRINK] == (0, 0)

    def test_pickup_eat_and_speak_have_no_delta_entry(self):
        # PICKUP/EAT/parler sont gérés hors de ACTION_TO_DELTA (logique dédiée)
        assert ACTION_PICKUP not in ACTION_TO_DELTA
        assert ACTION_EAT not in ACTION_TO_DELTA
        assert action_speak(0) not in ACTION_TO_DELTA


class TestActionLabel:
    def test_known_actions_have_labels(self):
        assert action_label(ACTION_UP) != "?"
        assert action_label(ACTION_DRINK) != "?"

    def test_speak_action_label_uses_alphabet_letter(self):
        label = action_label(action_speak(0))
        assert config.ALPHABET[0] in label

    def test_out_of_range_speak_index_falls_back_to_unknown(self):
        huge_index = len(config.ALPHABET) + 50
        assert action_label(action_speak(huge_index)) == "?"

    def test_unknown_action_returns_placeholder(self):
        assert action_label(-999) == "?"
