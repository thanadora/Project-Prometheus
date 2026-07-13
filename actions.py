"""
actions.py — Constantes d'actions et tables de correspondance.

Importé par agent.py, policy.py, gui.py, etc.
"""

ACTION_UP           = 0
ACTION_DOWN         = 1
ACTION_LEFT         = 2
ACTION_RIGHT        = 3
ACTION_IDLE         = 4
ACTION_DRINK        = 5
ACTION_VOTE_MIGRATE = 6
ACTION_PICKUP       = 7
ACTION_EAT          = 8

TIMED_ACTIONS = {ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT,
                 ACTION_IDLE, ACTION_DRINK, ACTION_PICKUP, ACTION_EAT}
FREE_ACTIONS  = {ACTION_VOTE_MIGRATE}

# -----------------------------
# COMMUNICATION (lettres)
# -----------------------------
# Les actions "parler" sont encodées dynamiquement à partir de ACTION_SPEAK_BASE,
# une par lettre de config.ALPHABET (ex: ACTION_SPEAK_BASE + 0 = "dire la lettre 0").
# Ce sont des actions LIBRES (comme ACTION_VOTE_MIGRATE) : elles ne coûtent pas de tick
# et peuvent être combinées avec l'action principale (déplacement, boire, etc.).
ACTION_SPEAK_BASE = 100


def action_speak(letter_index):
    """Retourne le code d'action pour dire la lettre d'index `letter_index` (dans config.ALPHABET)."""
    return ACTION_SPEAK_BASE + letter_index


def is_speak_action(action):
    return action >= ACTION_SPEAK_BASE


def speak_letter_index(action):
    return action - ACTION_SPEAK_BASE


def action_label(action):
    """Label lisible pour une action, y compris les actions 'parler' dynamiques."""
    if action in ACTION_LABELS:
        return ACTION_LABELS[action]
    if is_speak_action(action):
        import config
        idx = speak_letter_index(action)
        if 0 <= idx < len(config.ALPHABET):
            return f"🗣 {config.ALPHABET[idx]}"
    return "?"

ACTION_TO_DELTA = {
    ACTION_UP:    (0, -1),
    ACTION_DOWN:  (0,  1),
    ACTION_LEFT:  (-1, 0),
    ACTION_RIGHT: (1,  0),
    ACTION_IDLE:  (0,  0),
    ACTION_DRINK: (0,  0),
}

# Indices dans le vecteur d'observation
OBS_FOOD_DX   = 0
OBS_FOOD_DY   = 1
OBS_FOOD_DIST = 2
OBS_ENERGY    = 3
OBS_THIRST    = 4
OBS_WATER_DX  = 5
OBS_WATER_DY  = 6
OBS_SIZE      = 7

# Labels lisibles (pour la GUI)
ACTION_LABELS = {
    ACTION_UP:           "↑ Haut",
    ACTION_DOWN:         "↓ Bas",
    ACTION_LEFT:         "← Gauche",
    ACTION_RIGHT:        "→ Droite",
    ACTION_IDLE:         "· Idle",
    ACTION_DRINK:        "💧 Boire",
    ACTION_PICKUP:       "🎒 Ramasser",
    ACTION_EAT:          "🍖 Manger poche",
    ACTION_VOTE_MIGRATE: "🚶 Vote migration",
}