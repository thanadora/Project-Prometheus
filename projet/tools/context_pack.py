#!/usr/bin/env python3
"""
context_pack.py — Empaquette uniquement les fichiers nécessaires pour une
tâche, au lieu de zipper tout le projet.

Principe : on part d'un ou plusieurs fichiers "point d'entrée" (les modules
qui touchent au sujet dont on veut parler à une IA), et on résout
récursivement leurs imports locaux (les imports vers d'autres fichiers .py
du projet — les imports de bibliothèques externes comme `numpy` ou `tkinter`
sont ignorés). Le résultat est l'ensemble minimal de fichiers dont on a
besoin pour que le code soit compréhensible et cohérent hors contexte.

Usage
-----
    # Lister ce qui serait inclus, sans rien écrire :
    python3 tools/context_pack.py agent.py --dry-run

    # Copier les fichiers nécessaires dans un dossier :
    python3 tools/context_pack.py agent.py world.py --out context/

    # Idem, mais zippé, avec les tests correspondants inclus :
    python3 tools/context_pack.py migration.py --tests --zip context.zip

    # Inclure aussi les fichiers qui IMPORTENT le(s) point(s) d'entrée
    # (utile pour voir "qui dépend de ce module que je veux changer") :
    python3 tools/context_pack.py config.py --reverse --dry-run

Comment ça marche
------------------
Chaque fichier est parsé avec le module `ast` (pas d'exécution de code,
donc sans risque et sans avoir besoin des dépendances installées). On
extrait les noms de modules importés (`import X`, `from X import Y`,
`from .X import Y`), et pour chaque nom qui correspond à un fichier `X.py`
quelque part dans le projet, on l'ajoute à l'ensemble et on récidive dessus.
"""
from __future__ import annotations

import argparse
import ast
import shutil
import sys
import zipfile
from pathlib import Path


def find_project_root(start: Path) -> Path:
    """Remonte depuis `start` jusqu'à trouver un repère de racine de projet
    (.git, pyproject.toml, requirements*.txt) ; à défaut, utilise le dossier
    courant."""
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if any((candidate / marker).exists() for marker in
               (".git", "pyproject.toml", "requirements.txt", "requirements-dev.txt")):
            return candidate
    return start.resolve()


def local_modules_index(root: Path) -> dict[str, Path]:
    """Construit {nom_de_module: chemin_du_fichier} pour tous les .py du
    projet (hors dossiers usuels à ignorer)."""
    ignore_dirs = {".git", "__pycache__", "venv", ".venv", "node_modules", "build", "dist"}
    index: dict[str, Path] = {}
    for path in root.rglob("*.py"):
        if any(part in ignore_dirs for part in path.parts):
            continue
        module_name = path.stem
        # En cas de collision de nom, on garde le premier trouvé mais on
        # avertit — mieux vaut le signaler que de se tromper silencieusement.
        if module_name in index and index[module_name] != path:
            print(f"! avertissement : plusieurs fichiers '{module_name}.py' trouvés "
                  f"({index[module_name]} et {path}) — le premier est gardé", file=sys.stderr)
            continue
        index[module_name] = path
    return index


def extract_imported_module_names(py_file: Path) -> set[str]:
    """Retourne les noms de premier niveau importés par un fichier Python
    (import X -> 'X' ; from X.Y import Z -> 'X' ; from . import X -> 'X')."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"! impossible de parser {py_file}: {e}", file=sys.stderr)
        return set()

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
            elif node.names:  # "from . import X"
                for alias in node.names:
                    names.add(alias.name)
    return names


def resolve_dependencies(entry_files: list[Path], root: Path, follow_tests: bool) -> set[Path]:
    """Résout récursivement les dépendances locales des fichiers de départ."""
    index = local_modules_index(root)
    seen: set[Path] = set()
    queue: list[Path] = [f.resolve() for f in entry_files]

    while queue:
        current = queue.pop()
        if current in seen or not current.exists():
            continue
        seen.add(current)

        for name in extract_imported_module_names(current):
            target = index.get(name)
            if target and target.resolve() not in seen:
                queue.append(target)

        if follow_tests:
            test_candidate = current.parent.parent / "tests" / f"test_{current.stem}.py"
            if not test_candidate.exists():
                test_candidate = root / "tests" / f"test_{current.stem}.py"
            if test_candidate.exists():
                queue.append(test_candidate.resolve())

    if follow_tests:
        conftest = root / "tests" / "conftest.py"
        if conftest.exists():
            seen.add(conftest.resolve())

    return seen


def find_dependents(entry_files: list[Path], root: Path) -> set[Path]:
    """Trouve les fichiers du projet qui importent (directement) l'un des
    fichiers de départ — utile pour évaluer l'impact d'un changement."""
    entry_stems = {f.stem for f in entry_files}
    dependents: set[Path] = set()
    for path in root.rglob("*.py"):
        if path.stem in entry_stems:
            continue
        if extract_imported_module_names(path) & entry_stems:
            dependents.add(path.resolve())
    return dependents


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("entry_files", nargs="+", type=Path, help="Fichier(s) point d'entrée")
    parser.add_argument("--tests", action="store_true", help="Inclure les fichiers de test correspondants + conftest.py")
    parser.add_argument("--reverse", action="store_true", help="Inclure aussi les fichiers qui dépendent des points d'entrée")
    parser.add_argument("--out", type=Path, default=None, help="Dossier de sortie (copie les fichiers)")
    parser.add_argument("--zip", type=Path, default=None, help="Chemin du .zip de sortie")
    parser.add_argument("--dry-run", action="store_true", help="Affiche juste la liste, n'écrit rien")
    args = parser.parse_args()

    root = find_project_root(args.entry_files[0])
    files = resolve_dependencies(args.entry_files, root, follow_tests=args.tests)

    if args.reverse:
        files |= find_dependents(args.entry_files, root)

    rel_files = sorted(f.relative_to(root) for f in files)

    total_lines = sum(f.read_text(encoding="utf-8", errors="ignore").count("\n") for f in files)
    print(f"{len(rel_files)} fichier(s), ~{total_lines} lignes au total :\n")
    for rel in rel_files:
        print(f"  {rel}")

    if args.dry_run or (not args.out and not args.zip):
        if not args.dry_run:
            print("\n(aucune sortie demandée — utilisez --out ou --zip)")
        return

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for rel in rel_files:
            dest = args.out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, dest)
        print(f"\n→ copié dans {args.out}/")

    if args.zip:
        with zipfile.ZipFile(args.zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in rel_files:
                zf.write(root / rel, arcname=str(rel))
        print(f"\n→ écrit dans {args.zip}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # Sortie tronquée par un pipe (ex: `| head`) — rien d'anormal.
        sys.stderr.close()
