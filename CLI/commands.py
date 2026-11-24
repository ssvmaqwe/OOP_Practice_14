from typing import Callable, Optional
from CLI.presenter import BaseCommandStrategy, Command, Args, CLI
from Core.characters import CharacterManager, CharacterProfile, CharacterService, ApiProfileMapper
from Core.combatant import CombatantFactory, EnemyLibrary
from Core.game import Game, GameConfig, GameStatus
from Core.actions import GameRuleError
from Core.skills import SkillLibrary
from Core.stats import Stats
from Core.interfaces import IProfileRepository, IGameRepository
from Infra.display import (CLIGraphic, ProfileConsoleRenderer, GameConsoleRenderer,
                           HistoryConsoleRenderer)

DEFAULT_ENEMIES = ["goblin", "slime"]


class CatalogStrategy(BaseCommandStrategy):
    def __init__(self, manager: CharacterManager, service: CharacterService,
                 repo: IProfileRepository, cli: CLI, reader: Callable[[str], str] = input):
        super().__init__()
        self.manager = manager
        self.service = service
        self.repo = repo
        self.cli = cli
        self.read = reader
        self.renderer = ProfileConsoleRenderer()

        self.register_command(Command("list", "Список персонажів у каталозі", self._cmd_list))
        self.register_command(Command("show", "Деталі персонажа (show <id>)", self._cmd_show))
        self.register_command(Command("create", "Створити власного персонажа", self._cmd_create))
        self.register_command(Command("import", "Завантажити персонажа з API (import <name>)", self._cmd_import))
        self.register_command(Command("sources", "Імена, доступні для імпорту", self._cmd_sources))
        self.register_command(Command("save", "Зберегти каталог персонажів", self._cmd_save))

    def _cmd_list(self, args: Args) -> bool:
        profiles = self.manager.get_all()
        if not profiles:
            print("Каталог порожній.")
            return True
        print(CLIGraphic.banner("КАТАЛОГ ПЕРСОНАЖІВ"))
        rows = [[p.id, p.name, p.char_class, str(p.stats.health), str(p.stats.damage),
                 str(p.stats.magic), str(p.stats.armor), str(p.stats.speed)] for p in profiles]
        print(CLIGraphic.table(["ID", "Ім'я", "Клас", "HP", "Шкода", "Магія", "Броня", "Шв."], rows))
        return True

    def _cmd_show(self, args: Args) -> bool:
        if not args.params:
            print("Вкажіть ID (напр. show warrior_1)")
            return True
        profile = self.manager.get_character(args.params[0])
        if not profile:
            print("Не знайдено.")
            return True
        profile.use_renderer(self.renderer)
        self.cli.display(profile)
        return True

    def _ask_int(self, prompt: str, default: int) -> int:
        raw = self.read(f"{prompt} [{default}]: ").strip()
        return int(raw) if raw else default

    def _cmd_create(self, args: Args) -> bool:
        print(CLIGraphic.banner("СТВОРЕННЯ ПЕРСОНАЖА"))
        char_id = self.read("ID: ").strip()
        name = self.read("Ім'я: ").strip()
        if not char_id or not name:
            print("ID та ім'я обов'язкові.")
            return True
        classes = ", ".join(SkillLibrary.CLASS_SKILLS)
        char_class = self.read(f"Клас ({classes}): ").strip() or "Воїн"
        try:
            stats = Stats(
                health=self._ask_int("Здоров'я", 100),
                damage=self._ask_int("Шкода", 15),
                magic=self._ask_int("Магія", 5),
                armor=self._ask_int("Броня", 5),
                resist=self._ask_int("Резист, %", 10) / 100,
                speed=self._ask_int("Швидкість", 100),
            )
        except ValueError:
            print("Характеристики мають бути числами!")
            return True
        if stats.health <= 0 or stats.speed <= 0:
            print("Здоров'я та швидкість мають бути більшими за 0.")
            return True
        gfx_url = self.read("Графіка (URL): ").strip() or "default.png"
        self.manager.add_character(CharacterProfile(char_id, name, char_class, stats, gfx_url=gfx_url))
        print(f"Персонажа {name} створено. Навички: {', '.join(SkillLibrary.for_class(char_class))}. "
              f"Напишіть 'save'.")
        return True

    def _cmd_import(self, args: Args) -> bool:
        if not args.params:
            print("Вкажіть ім'я (напр. import diluc). Список: sources")
            return True
        try:
            profile = self.service.import_character(args.params[0])
        except LookupError as e:
            print(e)
            return True
        print(f"Імпортовано: {profile.name} [{profile.id}] — клас {profile.char_class}")
        return True

    def _cmd_sources(self, args: Args) -> bool:
        names = self.service.available_names()
        print("Доступні для імпорту: " + (", ".join(names) if names else "немає"))
        return True

    def _cmd_save(self, args: Args) -> bool:
        self.repo.save_profiles(self.manager.export_to_list())
        print("Каталог збережено.")
        return True


class GameStrategy(BaseCommandStrategy):
    def __init__(self, game: Game, manager: CharacterManager, repo: IGameRepository, cli: CLI):
        super().__init__()
        self.game = game
        self.manager = manager
        self.repo = repo
        self.cli = cli
        self.game_renderer = GameConsoleRenderer()
        self.history_renderer = HistoryConsoleRenderer()

        self.register_command(Command("play_start",
                                      "Почати бій (play_start <id> [<id>...] [--enemies=goblin,wolf])",
                                      self._cmd_start))
        self.register_command(Command("play_action", "Дія героя (play_action <дія> [ціль])", self._cmd_action))
        self.register_command(Command("play_status", "Стан бою і доступні дії", self._cmd_status))
        self.register_command(Command("play_history", "Історія кроків (play_history [--last=N])", self._cmd_history))
        self.register_command(Command("game_save", "Зберегти стан гри", self._cmd_save))
        self.register_command(Command("game_load", "Завантажити збережений стан гри", self._cmd_load))
        self.register_command(Command("enemies", "Список типів ворогів", self._cmd_enemies))
        self.register_command(Command("skills", "Довідник навичок", self._cmd_skills))

    def _print_records(self, records) -> None:
        for r in records:
            prefix = f"[Крок {r.turn}] " if r.actor != "system" else ""
            print(f"{prefix}{r.text}")

    def _cmd_start(self, args: Args) -> bool:
        if not args.params:
            print("Вкажіть ID персонажів (напр. play_start warrior_1).")
            return True
        heroes = []
        for i, pid in enumerate(args.params, start=1):
            profile = self.manager.get_character(pid)
            if not profile:
                print(f"Персонажа '{pid}' не знайдено.")
                return True
            heroes.append(CombatantFactory.from_profile(profile, f"h{i}"))
        enemy_ids = [e for e in args.flags.get("enemies", ",".join(DEFAULT_ENEMIES)).split(",") if e]
        unknown = [e for e in enemy_ids if not EnemyLibrary.exists(e)]
        if unknown:
            print(f"Невідомі вороги: {', '.join(unknown)}. Див. 'enemies'.")
            return True
        enemies = [CombatantFactory.from_template(t, f"e{i}") for i, t in enumerate(enemy_ids, start=1)]
        print(CLIGraphic.banner("ТЕКСТОВА ГРА"))
        self._print_records(self.game.start(heroes, enemies))
        self._cmd_status(args)
        return True

    def _cmd_action(self, args: Args) -> bool:
        if not args.params:
            print("Вкажіть дію (напр. play_action attack e1).")
            return True
        target = args.params[1] if len(args.params) > 1 else None
        try:
            records = self.game.act(args.params[0], target)
        except GameRuleError as e:
            print(f"[Неможливо] {e}")
            return True
        self._print_records(records)
        if self.game.is_active:
            actor = self.game.current_actor
            print(f"\nХід героя: {actor.name} ({actor.uid}). 'play_status' — деталі.")
        else:
            print(f"\nГру завершено. Рахунок: {self.game.score}")
        return True

    def _cmd_status(self, args: Args) -> bool:
        self.game.use_renderer(self.game_renderer)
        self.cli.display(self.game)
        return True

    def _cmd_history(self, args: Args) -> bool:
        records = self.game.all_records()
        last: Optional[str] = args.flags.get("last")
        if last and last.isdigit():
            turns = sorted({r.turn for r in records})[-int(last):]
            records = [r for r in records if r.turn in turns]
        print(CLIGraphic.banner("ІСТОРІЯ БОЮ"))
        print(self.history_renderer.render(records))
        return True

    def _cmd_save(self, args: Args) -> bool:
        if self.game.status == GameStatus.IDLE:
            print("Немає гри для збереження.")
            return True
        self.repo.save_game(self.game.to_config().to_dict())
        print("Стан гри збережено.")
        return True

    def _cmd_load(self, args: Args) -> bool:
        data = self.repo.load_game()
        if not data:
            print("Збереженої гри немає.")
            return True
        try:
            config = GameConfig.from_dict(data)
        except (ValueError, KeyError) as e:
            print(f"Не вдалося завантажити: {e}")
            return True
        self.game = Game.from_config(config, self.game.calculator, self.game.behavior)
        print("Гру відновлено.")
        self._cmd_status(args)
        return True

    def _cmd_enemies(self, args: Args) -> bool:
        rows = []
        for tid in EnemyLibrary.ids():
            t = EnemyLibrary.describe(tid)
            s = t["stats"]
            rows.append([tid, t["name"], str(s.health), str(s.damage), str(s.magic),
                         str(s.armor), f"{int(s.resist * 100)}%", str(s.speed)])
        print(CLIGraphic.table(["ID", "Назва", "HP", "Шкода", "Магія", "Броня", "Резист", "Шв."], rows))
        return True

    def _cmd_skills(self, args: Args) -> bool:
        rows = [[s.skill_id, s.name, s.kind, str(s.power), str(s.cooldown), s.description]
                for s in SkillLibrary.all()]
        print(CLIGraphic.table(["ID", "Назва", "Тип", "Сила", "Перезар.", "Опис"], rows))
        return True


class SystemStrategy(BaseCommandStrategy):
    def __init__(self, cli: CLI):
        super().__init__()
        self.cli = cli
        self.register_command(Command("help", "Довідка", self._cmd_help))

    def _cmd_help(self, args: Args) -> bool:
        print(CLIGraphic.banner("ДОВІДКА"))
        rows = [[selector, desc] for selector, desc in self.cli.get_all_commands().items()]
        rows.append(["exit", "Вийти"])
        print(CLIGraphic.table(["Команда", "Опис"], rows))
        return True
