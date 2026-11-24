from CLI.presenter import CLI, ArgParser
from CLI.commands import CatalogStrategy, GameStrategy, SystemStrategy
from Core.characters import CharacterManager, CharacterProfile, CharacterService
from Core.game import Game
from Core.stats import Stats
from Infra.data import JsonRepository
from Infra.api import StubCharacterSource


def test_arg_parser():
    args = ArgParser.parse_args('play_start "warrior_1" --enemies=goblin,wolf -v')
    assert args.command == "play_start"
    assert args.params == ["warrior_1"]
    assert args.flags == {"enemies": "goblin,wolf", "v": "true"}


def build(tmp_path):
    repo = JsonRepository(str(tmp_path / "test.json"))
    manager = CharacterManager()
    manager.add_character(CharacterProfile("w1", "Воїн", "Воїн", Stats(150, 30, 0, 8, 0.1, 0.0, 100)))
    cli = CLI()
    catalog = CatalogStrategy(manager, CharacterService(manager, StubCharacterSource()), repo, cli)
    game_strategy = GameStrategy(Game(), manager, repo, cli)
    cli.use_strategy(catalog)
    cli.use_strategy(game_strategy)
    cli.use_strategy(SystemStrategy(cli))
    return cli, manager, game_strategy, repo


def test_cli_game_cycle(tmp_path, capsys):
    cli, manager, gs, repo = build(tmp_path)
    assert cli.exec_command("import diluc")
    assert manager.get_character("diluc") is not None
    assert cli.exec_command("play_start w1 diluc --enemies=goblin")
    assert gs.game.is_active
    assert cli.exec_command("play_action attack e1")
    assert cli.exec_command("play_history")
    assert cli.exec_command("game_save")
    assert cli.exec_command("save")
    assert repo.load_game()["version"] == 2
    assert len(repo.load_profiles()) == 2

    turn_before = gs.game.current_turn.number
    assert cli.exec_command("game_load")
    assert gs.game.current_turn.number == turn_before
    out = capsys.readouterr().out
    assert "ІСТОРІЯ БОЮ" in out and "Гру відновлено" in out


def test_cli_rejects_unknown_enemy(tmp_path, capsys):
    cli, _, gs, _ = build(tmp_path)
    cli.exec_command("play_start w1 --enemies=dragon")
    assert not gs.game.is_active
    assert "Невідомі вороги" in capsys.readouterr().out


def test_create_character(tmp_path):
    answers = iter(["m1", "Маг", "Маг", "90", "8", "25", "2", "20", "110", ""])
    repo = JsonRepository(str(tmp_path / "t.json"))
    manager = CharacterManager()
    cli = CLI()
    cli.use_strategy(CatalogStrategy(manager, CharacterService(manager, StubCharacterSource()), repo, cli,
                                     reader=lambda _: next(answers)))
    cli.exec_command("create")
    p = manager.get_character("m1")
    assert p.stats.magic == 25 and p.stats.resist == 0.2 and p.skills == ["fireball", "curse"]
