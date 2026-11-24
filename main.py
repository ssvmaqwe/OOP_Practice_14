import sys
from CLI.presenter import CLI
from CLI.commands import CatalogStrategy, GameStrategy, SystemStrategy
from Core.characters import CharacterManager, CharacterProfile, CharacterService
from Core.game import Game, GameConfig
from Core.stats import Stats, Item, Modifier
from Infra.data import JsonRepository
from Infra.api import GenshinApiSource, StubCharacterSource, FallbackCharacterSource


def default_profiles():
    return [
        CharacterProfile("warrior_1", "Артур", "Воїн", Stats(130, 24, 0, 8, 0.10, 0.0, 100),
                         items=[Item("sword", "Сталевий меч", [Modifier("damage", 6)])]),
        CharacterProfile("mage_1", "Мерлін", "Маг", Stats(85, 10, 22, 2, 0.25, 0.10, 110),
                         items=[Item("staff", "Посох мудреця", [Modifier("magic", 5), Modifier("power", 0.1)])]),
        CharacterProfile("healer_1", "Ліра", "Цілитель", Stats(95, 9, 20, 4, 0.20, 0.0, 105)),
    ]


def main():
    repo = JsonRepository("repository.json")
    manager = CharacterManager()
    source = FallbackCharacterSource(GenshinApiSource(), StubCharacterSource())
    service = CharacterService(manager, source)
    game = Game()

    saved_profiles = repo.load_profiles()
    if saved_profiles:
        manager.load_from_list(saved_profiles)
    else:
        for profile in default_profiles():
            manager.add_character(profile)

    saved_game = repo.load_game()
    if saved_game:
        try:
            game = Game.from_config(GameConfig.from_dict(saved_game))
        except (ValueError, KeyError):
            pass

    cli = CLI()
    cli.use_strategy(CatalogStrategy(manager, service, repo, cli))
    cli.use_strategy(GameStrategy(game, manager, repo, cli))
    cli.use_strategy(SystemStrategy(cli))

    if len(sys.argv) > 1:
        cli.exec_command(" ".join(sys.argv[1:]))
        return

    cli.exec_command("help")
    while True:
        try:
            cmd = input("\n> ").strip()
            if cmd in ("exit", "quit"):
                break
            if cmd:
                cli.exec_command(cmd)
        except (KeyboardInterrupt, EOFError):
            break


if __name__ == "__main__":
    main()
