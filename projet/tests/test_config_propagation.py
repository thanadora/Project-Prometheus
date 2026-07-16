"""
test_config_propagation.py — Documente un bug réel découvert en écrivant
cette suite de tests.

config.py est un module global mutable, et `config_gui.py` modifie ses
attributs à l'exécution (`setattr(config, "TOROIDAL_WORLD", ...)`) quand
l'utilisateur touche à un réglage dans l'écran de configuration.

Mais `agent.py` fait `from config import TOROIDAL_WORLD` — un import DIRECT,
qui copie la valeur au moment de l'import et la fige dans le namespace de
agent.py. Or `main.py` importe `world.py` (qui importe `agent.py`) tout en
haut du fichier, AVANT que `run_config_gui()` ne soit appelé. Résultat :
la case à cocher "Monde toroïdal" de l'écran de configuration n'a
strictement aucun effet sur la partie qui suit — TOROIDAL_WORLD vaut
toujours `False` (sa valeur par défaut dans config.py) côté agent.py, quoi
que l'utilisateur choisisse dans l'interface.

Ce test ne "valide" pas ce comportement comme souhaitable : il le fige pour
qu'une correction future (passer par `config.TOROIDAL_WORLD` partout, ou
relire la config après coup) soit un choix conscient, pas une régression
silencieuse de plus.
"""
import config


def test_toggling_config_toroidal_world_does_not_reach_agent_module():
    """Reproduit le bug : modifier config.TOROIDAL_WORLD (comme le fait
    config_gui.py au clic sur la case à cocher) ne change PAS le
    comportement de agent.py, car celui-ci a importé la constante par
    valeur avant que ce changement n'ait lieu."""
    import agent as agent_module

    original_config_value = config.TOROIDAL_WORLD
    original_agent_value = agent_module.TOROIDAL_WORLD
    try:
        config.TOROIDAL_WORLD = not original_agent_value
        # Le module config est bien mis à jour...
        assert config.TOROIDAL_WORLD != original_agent_value
        # ...mais agent.py ne le voit pas : c'est le bug.
        assert agent_module.TOROIDAL_WORLD == original_agent_value
    finally:
        config.TOROIDAL_WORLD = original_config_value


def test_other_constants_directly_imported_by_agent_share_the_same_issue():
    """Même piège pour toute constante numérique importée directement
    (MOVE_COST, MAX_ENERGY, THIRST_RATE...) plutôt que lue via `config.X`.
    Seuls les attributs préfixés `config.` dans agent.py (ex: ENABLE_THIRST,
    ENABLE_BIOMES, ENABLE_COMMUNICATION) réagissent bien aux changements
    faits par config_gui.py après coup. C'est un contraste utile à connaître :
    les booléens ENABLE_* fonctionnent, les seuils numériques directement
    importés non."""
    import agent as agent_module

    original = config.MOVE_COST
    try:
        config.MOVE_COST = original + 1000
        assert agent_module.MOVE_COST == original  # inchangé : bug identique
    finally:
        config.MOVE_COST = original


def test_enable_flags_accessed_via_config_prefix_do_propagate_correctly():
    """Contre-exemple positif : agent.py accède à `config.ENABLE_THIRST`
    (avec préfixe, à l'intérieur de ses fonctions) plutôt que via un nom
    importé directement. Ces attributs-là réagissent bien aux changements
    faits après coup — exactement ce qu'on attend d'un réglage utilisateur."""
    from agent import _update_thirst
    from tests.conftest import make_world, make_agent

    original = config.ENABLE_THIRST
    try:
        config.ENABLE_THIRST = False
        world = make_world(width=5, height=5)
        agent = make_agent(x=2, y=2, thirst=50)
        _update_thirst(agent, world)
        assert agent.thirst == 50  # bien pris en compte : pas de soif
    finally:
        config.ENABLE_THIRST = original
