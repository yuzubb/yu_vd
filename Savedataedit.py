from __future__ import annotations # Discord id ba23d
import asyncio # Discord id ba23d
import time # Discord id ba23d
from typing import Any # Discord id ba23d
 # Discord id ba23d
from bcsfe import core # Discord id ba23d
from bcsfe.core.io.save import SaveFile, SaveError # Discord id ba23d
from bcsfe.core.country_code import CountryCode # Discord id ba23d
from bcsfe.core.server.server_handler import ServerHandler # Discord id ba23d
 # Discord id ba23d
if not hasattr(core.core_data, 'config'): # Discord id ba23d
    core.core_data.init_data() # Discord id ba23d
 # Discord id ba23d
class SaveEditorError(Exception): # Discord id ba23d
    pass # Discord id ba23d
 # Discord id ba23d
class CatEditor: # Discord id ba23d
    def __init__(self, cat: core.Cat, save: SaveFile): # Discord id ba23d
        self._cat = cat # Discord id ba23d
        self._save = save # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def id(self) -> int: # Discord id ba23d
        return self._cat.id # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def unlocked(self) -> bool: # Discord id ba23d
        return bool(self._cat.unlocked) # Discord id ba23d
 # Discord id ba23d
    @unlocked.setter # Discord id ba23d
    def unlocked(self, v: bool) -> None: # Discord id ba23d
        if v: # Discord id ba23d
            self._cat.unlock(self._save) # Discord id ba23d
        else: # Discord id ba23d
            self._cat.remove() # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def level(self) -> int: # Discord id ba23d
        return self._cat.upgrade.base + 1 # Discord id ba23d
 # Discord id ba23d
    @level.setter # Discord id ba23d
    def level(self, v: int) -> None: # Discord id ba23d
        self._cat.upgrade.base = max(0, v - 1) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def plus(self) -> int: # Discord id ba23d
        return self._cat.upgrade.plus # Discord id ba23d
 # Discord id ba23d
    @plus.setter # Discord id ba23d
    def plus(self, v: int) -> None: # Discord id ba23d
        self._cat.upgrade.plus = max(0, v) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def current_form(self) -> int: # Discord id ba23d
        return self._cat.current_form # Discord id ba23d
 # Discord id ba23d
    @current_form.setter # Discord id ba23d
    def current_form(self, v: int) -> None: # Discord id ba23d
        self._cat.current_form = v # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def unlocked_forms(self) -> int: # Discord id ba23d
        return self._cat.unlocked_forms # Discord id ba23d
 # Discord id ba23d
    @unlocked_forms.setter # Discord id ba23d
    def unlocked_forms(self, v: int) -> None: # Discord id ba23d
        self._cat.unlocked_forms = v # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def fourth_form(self) -> int: # Discord id ba23d
        return self._cat.fourth_form # Discord id ba23d
 # Discord id ba23d
    @fourth_form.setter # Discord id ba23d
    def fourth_form(self, v: int) -> None: # Discord id ba23d
        self._cat.fourth_form = v # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def catseyes_used(self) -> int: # Discord id ba23d
        return self._cat.catseyes_used # Discord id ba23d
 # Discord id ba23d
    @catseyes_used.setter # Discord id ba23d
    def catseyes_used(self, v: int) -> None: # Discord id ba23d
        self._cat.catseyes_used = v # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def catguide_collected(self) -> bool: # Discord id ba23d
        return self._cat.catguide_collected # Discord id ba23d
 # Discord id ba23d
    @catguide_collected.setter # Discord id ba23d
    def catguide_collected(self, v: bool) -> None: # Discord id ba23d
        self._cat.catguide_collected = v # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def talents(self) -> list[core.Talent] | None: # Discord id ba23d
        return self._cat.talents # Discord id ba23d
 # Discord id ba23d
    def set_talent(self, talent_id: int, level: int) -> CatEditor: # Discord id ba23d
        t = self._cat.get_talent_from_id(talent_id) # Discord id ba23d
        if t is not None: # Discord id ba23d
            t.level = level # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_talents(self, max_level: int = 10) -> CatEditor: # Discord id ba23d
        for t in self._cat.talents or []: # Discord id ba23d
            t.level = max_level # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unlock_true_form(self) -> CatEditor: # Discord id ba23d
        self._cat.true_form(self._save) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unlock_fourth_form(self) -> CatEditor: # Discord id ba23d
        self._cat.unlock_fourth_form(self._save) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def _get_max_plus(self) -> int: # Discord id ba23d
        unit_buy = self._save.cats.read_unitbuy(self._save) # Discord id ba23d
        ub = unit_buy.get_unit_buy(self._cat.id) # Discord id ba23d
        return ub.max_plus_upgrade_level if ub is not None else 0 # Discord id ba23d
 # Discord id ba23d
    def max_level(self) -> CatEditor: # Discord id ba23d
        from bcsfe.core.game.catbase.powerup import PowerUpHelper # Discord id ba23d
        self._cat.unlock(self._save) # Discord id ba23d
        helper = PowerUpHelper(self._cat, self._save) # Discord id ba23d
        helper.max_upgrade() # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max(self, level: int = 30, plus: int | None = None) -> CatEditor: # Discord id ba23d
        self._cat.unlock(self._save) # Discord id ba23d
        self._cat.upgrade.base = max(0, level - 1) # Discord id ba23d
        self._cat.upgrade.plus = self._get_max_plus() if plus is None else plus # Discord id ba23d
        self._cat.true_form(self._save) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def reset(self) -> CatEditor: # Discord id ba23d
        self._cat.reset() # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def to_dict(self) -> dict[str, Any]: # Discord id ba23d
        return { # Discord id ba23d
            "id": self.id, # Discord id ba23d
            "unlocked": self.unlocked, # Discord id ba23d
            "level": self.level, # Discord id ba23d
            "plus": self.plus, # Discord id ba23d
            "current_form": self.current_form, # Discord id ba23d
            "unlocked_forms": self.unlocked_forms, # Discord id ba23d
            "fourth_form": self.fourth_form, # Discord id ba23d
            "catseyes_used": self.catseyes_used, # Discord id ba23d
            "catguide_collected": self.catguide_collected, # Discord id ba23d
        } # Discord id ba23d
 # Discord id ba23d
class SaveEditor: # Discord id ba23d
    def __init__(self, data: bytes | str, cc: str | None = None): # Discord id ba23d
        try: # Discord id ba23d
            if isinstance(data, str): # Discord id ba23d
                raw = core.Data.from_file(core.Path(data)) # Discord id ba23d
            else: # Discord id ba23d
                raw = core.Data(data) # Discord id ba23d
            country = CountryCode(cc) if cc else None # Discord id ba23d
            self._save: SaveFile = SaveFile(dt=raw, cc=country) # Discord id ba23d
        except SaveError as e: # Discord id ba23d
            raise SaveEditorError(str(e)) from e # Discord id ba23d
 # Discord id ba23d
    @classmethod # Discord id ba23d
    async def async_from_bytes(cls, data: bytes, cc: str | None = None) -> SaveEditor: # Discord id ba23d
        return await asyncio.to_thread(cls, data, cc) # Discord id ba23d
 # Discord id ba23d
    @classmethod # Discord id ba23d
    async def async_from_file(cls, path: str, cc: str | None = None) -> SaveEditor: # Discord id ba23d
        return await asyncio.to_thread(cls, path, cc) # Discord id ba23d
 # Discord id ba23d
    @classmethod # Discord id ba23d
    def from_bytes(cls, data: bytes, cc: str | None = None) -> SaveEditor: # Discord id ba23d
        return cls(data, cc=cc) # Discord id ba23d
 # Discord id ba23d
    @classmethod # Discord id ba23d
    def from_file(cls, path: str, cc: str | None = None) -> SaveEditor: # Discord id ba23d
        return cls(path, cc=cc) # Discord id ba23d
 # Discord id ba23d
    async def async_to_bytes(self) -> bytes: # Discord id ba23d
        return await asyncio.to_thread(self.to_bytes) # Discord id ba23d
 # Discord id ba23d
    async def async_to_file(self, path: str) -> None: # Discord id ba23d
        await asyncio.to_thread(self.to_file, path) # Discord id ba23d
 # Discord id ba23d
    def to_bytes(self) -> bytes: # Discord id ba23d
        try: # Discord id ba23d
            return bytes(self._save.to_data()) # Discord id ba23d
        except Exception as e: # Discord id ba23d
            raise SaveEditorError(str(e)) from e # Discord id ba23d
 # Discord id ba23d
    def to_file(self, path: str) -> None: # Discord id ba23d
        try: # Discord id ba23d
            self._save.to_file(core.Path(path)) # Discord id ba23d
        except Exception as e: # Discord id ba23d
            raise SaveEditorError(str(e)) from e # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def raw(self) -> SaveFile: # Discord id ba23d
        return self._save # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def cc(self) -> str: # Discord id ba23d
        return str(self._save.cc) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def game_version(self) -> int: # Discord id ba23d
        return self._save.game_version.game_version # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def inquiry_code(self) -> str: # Discord id ba23d
        return self._save.inquiry_code # Discord id ba23d
 # Discord id ba23d
    @inquiry_code.setter # Discord id ba23d
    def inquiry_code(self, v: str) -> None: # Discord id ba23d
        self._save.inquiry_code = v # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def transfer_code(self) -> str: # Discord id ba23d
        return self._save.transfer_code # Discord id ba23d
 # Discord id ba23d
    @transfer_code.setter # Discord id ba23d
    def transfer_code(self, v: str) -> None: # Discord id ba23d
        self._save.transfer_code = v # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def confirmation_code(self) -> str: # Discord id ba23d
        return self._save.confirmation_code # Discord id ba23d
 # Discord id ba23d
    @confirmation_code.setter # Discord id ba23d
    def confirmation_code(self, v: str) -> None: # Discord id ba23d
        self._save.confirmation_code = v # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def transfer_flag(self) -> bool: # Discord id ba23d
        return self._save.transfer_flag # Discord id ba23d
 # Discord id ba23d
    @transfer_flag.setter # Discord id ba23d
    def transfer_flag(self, v: bool) -> None: # Discord id ba23d
        self._save.transfer_flag = v # Discord id ba23d
 # Discord id ba23d
    def _sync_create_new_account(self) -> None: # Discord id ba23d
        handler = ServerHandler(self._save, print=False) # Discord id ba23d
        success = handler.create_new_account() # Discord id ba23d
        if not success: # Discord id ba23d
            raise SaveEditorError("Network error") # Discord id ba23d
 # Discord id ba23d
    async def create_new_account(self) -> SaveEditor: # Discord id ba23d
        await asyncio.to_thread(self._sync_create_new_account) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def _sync_issue_transfer_codes(self) -> tuple[str, str]: # Discord id ba23d
        handler = ServerHandler(self._save, print=False) # Discord id ba23d
        result = handler.get_codes() # Discord id ba23d
        if result is None: # Discord id ba23d
            raise SaveEditorError("Network error") # Discord id ba23d
        transfer_code, confirmation_code = result # Discord id ba23d
        self._save.transfer_code = transfer_code # Discord id ba23d
        self._save.confirmation_code = confirmation_code # Discord id ba23d
        self._save.transfer_flag = True # Discord id ba23d
        return transfer_code, confirmation_code # Discord id ba23d
 # Discord id ba23d
    async def issue_transfer_codes(self) -> tuple[str, str]: # Discord id ba23d
        return await asyncio.to_thread(self._sync_issue_transfer_codes) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def catfood(self) -> int: # Discord id ba23d
        return self._save.get_catfood() # Discord id ba23d
 # Discord id ba23d
    @catfood.setter # Discord id ba23d
    def catfood(self, v: int) -> None: # Discord id ba23d
        self._save.set_catfood(v) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def xp(self) -> int: # Discord id ba23d
        return self._save.get_xp() # Discord id ba23d
 # Discord id ba23d
    @xp.setter # Discord id ba23d
    def xp(self, v: int) -> None: # Discord id ba23d
        self._save.set_xp(v) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def normal_tickets(self) -> int: # Discord id ba23d
        return self._save.get_normal_tickets() # Discord id ba23d
 # Discord id ba23d
    @normal_tickets.setter # Discord id ba23d
    def normal_tickets(self, v: int) -> None: # Discord id ba23d
        self._save.set_normal_tickets(v) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def rare_tickets(self) -> int: # Discord id ba23d
        return self._save.get_rare_tickets() # Discord id ba23d
 # Discord id ba23d
    @rare_tickets.setter # Discord id ba23d
    def rare_tickets(self, v: int) -> None: # Discord id ba23d
        self._save.set_rare_tickets(v) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def platinum_tickets(self) -> int: # Discord id ba23d
        return self._save.get_platinum_tickets() # Discord id ba23d
 # Discord id ba23d
    @platinum_tickets.setter # Discord id ba23d
    def platinum_tickets(self, v: int) -> None: # Discord id ba23d
        self._save.set_platinum_tickets(v) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def legend_tickets(self) -> int: # Discord id ba23d
        return self._save.get_legend_tickets() # Discord id ba23d
 # Discord id ba23d
    @legend_tickets.setter # Discord id ba23d
    def legend_tickets(self, v: int) -> None: # Discord id ba23d
        self._save.set_legend_tickets(v) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def platinum_shards(self) -> int: # Discord id ba23d
        return self._save.get_platinum_shards() # Discord id ba23d
 # Discord id ba23d
    @platinum_shards.setter # Discord id ba23d
    def platinum_shards(self, v: int) -> None: # Discord id ba23d
        self._save.set_platinum_shards(v) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def hundred_million_ticket(self) -> int: # Discord id ba23d
        return self._save.hundred_million_ticket # Discord id ba23d
 # Discord id ba23d
    @hundred_million_ticket.setter # Discord id ba23d
    def hundred_million_ticket(self, v: int) -> None: # Discord id ba23d
        self._save.hundred_million_ticket = v # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def np(self) -> int: # Discord id ba23d
        return self._save.get_np() # Discord id ba23d
 # Discord id ba23d
    @np.setter # Discord id ba23d
    def np(self, v: int) -> None: # Discord id ba23d
        self._save.set_np(v) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def leadership(self) -> int: # Discord id ba23d
        return self._save.get_leadership() # Discord id ba23d
 # Discord id ba23d
    @leadership.setter # Discord id ba23d
    def leadership(self, v: int) -> None: # Discord id ba23d
        self._save.set_leadership(v) # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def catfruit(self) -> list[int]: # Discord id ba23d
        return self._save.catfruit # Discord id ba23d
 # Discord id ba23d
    @catfruit.setter # Discord id ba23d
    def catfruit(self, v: list[int]) -> None: # Discord id ba23d
        self._save.catfruit = v # Discord id ba23d
 # Discord id ba23d
    def set_catfruit(self, index: int, amount: int) -> SaveEditor: # Discord id ba23d
        self._save.catfruit[index] = amount # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_all_catfruit(self, amount: int) -> SaveEditor: # Discord id ba23d
        self._save.catfruit = [amount] * len(self._save.catfruit) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def catseyes(self) -> list[int]: # Discord id ba23d
        return self._save.catseyes # Discord id ba23d
 # Discord id ba23d
    @catseyes.setter # Discord id ba23d
    def catseyes(self, v: list[int]) -> None: # Discord id ba23d
        self._save.catseyes = v # Discord id ba23d
 # Discord id ba23d
    def set_catseye(self, index: int, amount: int) -> SaveEditor: # Discord id ba23d
        self._save.catseyes[index] = amount # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_all_catseyes(self, amount: int) -> SaveEditor: # Discord id ba23d
        self._save.catseyes = [amount] * len(self._save.catseyes) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_all_catseyes(self) -> SaveEditor: # Discord id ba23d
        from bcsfe.core.max_value_helper import MaxValueType # Discord id ba23d
        max_val = core.core_data.max_value_manager.get(MaxValueType.CATSEYES) # Discord id ba23d
        self._save.catseyes = [max_val] * len(self._save.catseyes) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def catamins(self) -> list[int]: # Discord id ba23d
        return self._save.catamins # Discord id ba23d
 # Discord id ba23d
    @catamins.setter # Discord id ba23d
    def catamins(self, v: list[int]) -> None: # Discord id ba23d
        self._save.catamins = v # Discord id ba23d
 # Discord id ba23d
    def set_catamin(self, index: int, amount: int) -> SaveEditor: # Discord id ba23d
        self._save.catamins[index] = amount # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_all_catamins(self, amount: int) -> SaveEditor: # Discord id ba23d
        self._save.catamins = [amount] * len(self._save.catamins) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def energy_drinks(self) -> list[int]: # Discord id ba23d
        return self._save.catamins # Discord id ba23d
 # Discord id ba23d
    @energy_drinks.setter # Discord id ba23d
    def energy_drinks(self, v: list[int]) -> None: # Discord id ba23d
        self._save.catamins = v # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def battle_items(self) -> list[core.BattleItem]: # Discord id ba23d
        return self._save.battle_items.items # Discord id ba23d
 # Discord id ba23d
    def set_battle_item(self, index: int, amount: int) -> SaveEditor: # Discord id ba23d
        self._save.battle_items.items[index].amount = amount # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_all_battle_items(self, amount: int) -> SaveEditor: # Discord id ba23d
        for item in self._save.battle_items.items: # Discord id ba23d
            item.amount = amount # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def labyrinth_medals(self) -> list[int]: # Discord id ba23d
        return self._save.labyrinth_medals # Discord id ba23d
 # Discord id ba23d
    def set_all_labyrinth_medals(self, amount: int) -> SaveEditor: # Discord id ba23d
        for i in range(len(self._save.labyrinth_medals)): # Discord id ba23d
            self._save.labyrinth_medals[i] = amount # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def gamatoto_xp(self) -> int: # Discord id ba23d
        return self._save.gamatoto.xp # Discord id ba23d
 # Discord id ba23d
    @gamatoto_xp.setter # Discord id ba23d
    def gamatoto_xp(self, v: int) -> None: # Discord id ba23d
        self._save.gamatoto.xp = v # Discord id ba23d
 # Discord id ba23d
    def max_gamatoto_helpers(self) -> SaveEditor: # Discord id ba23d
        from bcsfe.core.game.gamoto.gamatoto import Helper # Discord id ba23d
        self._save.gamatoto.helpers = [Helper(4) for _ in range(10)] # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def ototo_engineers(self) -> int: # Discord id ba23d
        return self._save.ototo.engineers # Discord id ba23d
 # Discord id ba23d
    @ototo_engineers.setter # Discord id ba23d
    def ototo_engineers(self, v: int) -> None: # Discord id ba23d
        self._save.ototo.engineers = v # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def base_materials(self) -> list[int]: # Discord id ba23d
        return self._save.ototo.base_materials # Discord id ba23d
 # Discord id ba23d
    @base_materials.setter # Discord id ba23d
    def base_materials(self, v: list[int]) -> None: # Discord id ba23d
        self._save.ototo.base_materials = v # Discord id ba23d
 # Discord id ba23d
    def max_base_materials(self, amount: int = 9999) -> SaveEditor: # Discord id ba23d
        for i in range(len(self._save.ototo.base_materials)): # Discord id ba23d
            self._save.ototo.base_materials[i] = amount # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_cannon_level(self, cannon_id: int, levels: list[int], development: int = 2) -> SaveEditor: # Discord id ba23d
        cannons = self._save.ototo.cannons # Discord id ba23d
        if cannons is None: # Discord id ba23d
            from bcsfe.core.game.gamoto.ototo import Cannons # Discord id ba23d
            self._save.ototo.cannons = Cannons.init(self._save.game_version) # Discord id ba23d
            cannons = self._save.ototo.cannons # Discord id ba23d
        from bcsfe.core.game.gamoto.ototo import Cannon # Discord id ba23d
        cannons.cannons[cannon_id] = Cannon(development, levels) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_talent_orb(self, orb_id: int, value: int) -> SaveEditor: # Discord id ba23d
        self._save.talent_orbs.set_orb(orb_id, value) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_talent_orbs(self, orb_ids: list[int], value: int) -> SaveEditor: # Discord id ba23d
        for orb_id in orb_ids: # Discord id ba23d
            self._save.talent_orbs.set_orb(orb_id, value) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_all_talent_orbs(self) -> SaveEditor: # Discord id ba23d
        from bcsfe.core.max_value_helper import MaxValueType # Discord id ba23d
        from bcsfe.core.game.catbase.talent_orbs import OrbInfoList # Discord id ba23d
        max_val = core.core_data.max_value_manager.get(MaxValueType.TALENT_ORBS) # Discord id ba23d
        orb_info_list = OrbInfoList.create(self._save) # Discord id ba23d
        if orb_info_list is not None: # Discord id ba23d
            for orb in orb_info_list.orb_info_list: # Discord id ba23d
                self._save.talent_orbs.set_orb(orb.raw_orb_info.orb_id, max_val) # Discord id ba23d
        else: # Discord id ba23d
            for orb_id in list(self._save.talent_orbs.orbs.keys()): # Discord id ba23d
                self._save.talent_orbs.set_orb(orb_id, max_val) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def get_talent_orbs(self) -> dict[int, int]: # Discord id ba23d
        return {orb_id: orb.value for orb_id, orb in self._save.talent_orbs.orbs.items()} # Discord id ba23d
 # Discord id ba23d
    def max_all_catfruit(self) -> SaveEditor: # Discord id ba23d
        from bcsfe.core.max_value_helper import MaxValueType # Discord id ba23d
        if self._save.game_version < 110400: # Discord id ba23d
            max_val = core.core_data.max_value_manager.get_old(MaxValueType.CATFRUIT) # Discord id ba23d
        else: # Discord id ba23d
            max_val = core.core_data.max_value_manager.get_new(MaxValueType.CATFRUIT) # Discord id ba23d
        self._save.catfruit = [max_val] * len(self._save.catfruit) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_all_catamins(self) -> SaveEditor: # Discord id ba23d
        from bcsfe.core.max_value_helper import MaxValueType # Discord id ba23d
        max_val = core.core_data.max_value_manager.get(MaxValueType.CATAMINS) # Discord id ba23d
        self._save.catamins = [max_val] * len(self._save.catamins) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def get_cat(self, cat_id: int) -> CatEditor | None: # Discord id ba23d
        cats = self._save.cats.cats # Discord id ba23d
        if 0 <= cat_id < len(cats): # Discord id ba23d
            return CatEditor(cats[cat_id], self._save) # Discord id ba23d
        return None # Discord id ba23d
 # Discord id ba23d
    def get_all_cats(self) -> list[CatEditor]: # Discord id ba23d
        return [CatEditor(c, self._save) for c in self._save.cats.cats] # Discord id ba23d
 # Discord id ba23d
    def get_unlocked_cats(self) -> list[CatEditor]: # Discord id ba23d
        return [CatEditor(c, self._save) for c in self._save.cats.cats if c.unlocked] # Discord id ba23d
 # Discord id ba23d
    def find_cats(self, name: str) -> list[CatEditor]: # Discord id ba23d
        results = self._save.cats.get_cats_name(self._save, name) # Discord id ba23d
        return [CatEditor(c, self._save) for c in results] # Discord id ba23d
 # Discord id ba23d
    def unlock_cat(self, cat_id: int) -> SaveEditor: # Discord id ba23d
        cat = self.get_cat(cat_id) # Discord id ba23d
        if cat is None: # Discord id ba23d
            raise SaveEditorError(f"cat_id {cat_id} not found") # Discord id ba23d
        cat.unlocked = True # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unlock_cats(self, *cat_ids: int) -> SaveEditor: # Discord id ba23d
        for cat_id in cat_ids: # Discord id ba23d
            self.unlock_cat(cat_id) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def remove_cat(self, cat_id: int) -> SaveEditor: # Discord id ba23d
        cat = self.get_cat(cat_id) # Discord id ba23d
        if cat is None: # Discord id ba23d
            raise SaveEditorError(f"cat_id {cat_id} not found") # Discord id ba23d
        cat._cat.remove(reset=True, save_file=self._save) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def remove_cats(self, *cat_ids: int) -> SaveEditor: # Discord id ba23d
        for cat_id in cat_ids: # Discord id ba23d
            self.remove_cat(cat_id) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def remove_all_cats(self) -> SaveEditor: # Discord id ba23d
        for cat in self._save.cats.cats: # Discord id ba23d
            cat.remove(reset=True, save_file=self._save) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_cat_level(self, cat_id: int, level: int, plus: int | None = None) -> SaveEditor: # Discord id ba23d
        cat = self.get_cat(cat_id) # Discord id ba23d
        if cat is None: # Discord id ba23d
            raise SaveEditorError(f"cat_id {cat_id} not found") # Discord id ba23d
        cat.unlocked = True # Discord id ba23d
        cat.level = level # Discord id ba23d
        cat.plus = cat._get_max_plus() if plus is None else plus # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_cat(self, cat_id: int, level: int = 30, plus: int | None = None) -> SaveEditor: # Discord id ba23d
        cat = self.get_cat(cat_id) # Discord id ba23d
        if cat is None: # Discord id ba23d
            raise SaveEditorError(f"cat_id {cat_id} not found") # Discord id ba23d
        cat.max(level, plus) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unlock_all_cats(self) -> SaveEditor: # Discord id ba23d
        for cat in self._save.cats.cats: # Discord id ba23d
            cat.unlock(self._save) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_level_cat(self, cat_id: int) -> SaveEditor: # Discord id ba23d
        cat = self.get_cat(cat_id) # Discord id ba23d
        if cat is None: # Discord id ba23d
            raise SaveEditorError(f"cat_id {cat_id} not found") # Discord id ba23d
        cat.max_level() # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_level_all_cats(self) -> SaveEditor: # Discord id ba23d
        for cat in self._save.cats.cats: # Discord id ba23d
            if cat.unlocked: # Discord id ba23d
                CatEditor(cat, self._save).max_level() # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_all_cats(self, level: int = 30, plus: int = 0) -> SaveEditor: # Discord id ba23d
        from bcsfe.core.game.catbase.cat import NyankoPictureBook # Discord id ba23d
        pic_book = NyankoPictureBook(self._save) # Discord id ba23d
        unit_buy = self._save.cats.read_unitbuy(self._save) # Discord id ba23d
        for cat in self._save.cats.cats: # Discord id ba23d
            cat.unlock(self._save) # Discord id ba23d
            cat.upgrade.base = max(0, level - 1) # Discord id ba23d
            ub = unit_buy.get_unit_buy(cat.id) # Discord id ba23d
            cat.upgrade.plus = ub.max_plus_upgrade_level if ub is not None else plus # Discord id ba23d
            pic_book_cat = pic_book.get_cat(cat.id) # Discord id ba23d
            if pic_book_cat is not None and pic_book_cat.total_forms >= 3: # Discord id ba23d
                cat.true_form(self._save) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_facilities(self) -> SaveEditor: # Discord id ba23d
        from bcsfe.core.game.gamoto.ototo import Cannons, CastleRecipeUnlock # Discord id ba23d
        if self._save.ototo.cannons is None: # Discord id ba23d
            self._save.ototo.cannons = Cannons.init(self._save.game_version) # Discord id ba23d
        recipe_unlock = CastleRecipeUnlock(self._save) # Discord id ba23d
        for cannon_id, cannon in self._save.ototo.cannons.cannons.items(): # Discord id ba23d
            if cannon_id != 0: # Discord id ba23d
                cannon.development = 3 # Discord id ba23d
            for part_id in range(len(cannon.levels)): # Discord id ba23d
                max_level = recipe_unlock.get_max_level(cannon_id, part_id) # Discord id ba23d
                if max_level is not None: # Discord id ba23d
                    cannon.levels[part_id] = max_level - 1 if part_id == 0 else max_level # Discord id ba23d
        self._save.ototo.engineers = self._save.ototo.get_max_engineers(self._save) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_special_skill_level(self, skill_id: int, base: int, plus: int = 0) -> SaveEditor: # Discord id ba23d
        skill = self._save.special_skills.get_from_id(skill_id) # Discord id ba23d
        if skill is None: # Discord id ba23d
            raise SaveEditorError(f"special_skill_id {skill_id} not found") # Discord id ba23d
        skill.upgrade.base = max(0, base - 1) # Discord id ba23d
        skill.upgrade.plus = plus # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_special_skills(self, level: int = 10) -> SaveEditor: # Discord id ba23d
        for skill in self._save.special_skills.get_valid_skills(): # Discord id ba23d
            skill.upgrade.base = max(0, level - 1) # Discord id ba23d
            skill.upgrade.plus = 0 # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_story_stage(self, chapter: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.story.clear_stage(chapter, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_story_chapter(self, chapter: int) -> SaveEditor: # Discord id ba23d
        ch = self._save.story.chapters[chapter] # Discord id ba23d
        for i in range(len(ch.stages)): # Discord id ba23d
            ch.clear_stage(i, 1) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_story(self, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        for chapter in self._save.story.get_real_chapters(): # Discord id ba23d
            for i in range(len(chapter.stages)): # Discord id ba23d
                chapter.clear_stage(i, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_story_treasure(self, chapter: int, stage: int, treasure: int) -> SaveEditor: # Discord id ba23d
        self._save.story.set_treasure(chapter, stage, treasure) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_story_treasures(self, treasure: int = 3) -> SaveEditor: # Discord id ba23d
        for chapter in self._save.story.get_real_chapters(): # Discord id ba23d
            for stage in chapter.get_valid_treasure_stages(): # Discord id ba23d
                stage.set_treasure(treasure) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_event_stage(self, type: int, map: int, star: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.event_stages.clear_stage(type, map, star, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unclear_event_stage(self, type: int, map: int, star: int, stage: int) -> SaveEditor: # Discord id ba23d
        self._save.event_stages.unclear_stage(type, map, star, stage) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_event_map(self, type: int, map: int, star: int) -> SaveEditor: # Discord id ba23d
        self._save.event_stages.clear_map(type, map, star) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_event_chapter(self, type: int, map: int) -> SaveEditor: # Discord id ba23d
        self._save.event_stages.clear_chapter(type, map) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_event_group(self, type: int) -> SaveEditor: # Discord id ba23d
        self._save.event_stages.clear_group(type) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_events(self) -> SaveEditor: # Discord id ba23d
        for type_idx in range(len(self._save.event_stages.chapters)): # Discord id ba23d
            self._save.event_stages.clear_group(type_idx) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_uncanny_stage(self, map: int, star: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.uncanny.chapters.clear_stage(map, star, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unclear_uncanny_stage(self, map: int, star: int, stage: int) -> SaveEditor: # Discord id ba23d
        self._save.uncanny.chapters.unclear_stage(map, star, stage) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_uncanny(self) -> SaveEditor: # Discord id ba23d
        ch = self._save.uncanny.chapters # Discord id ba23d
        for map_idx, chapters_stars in enumerate(ch.chapters): # Discord id ba23d
            for star_idx, chapter in enumerate(chapters_stars.chapters): # Discord id ba23d
                for stage_idx in range(len(chapter.stages)): # Discord id ba23d
                    ch.clear_stage(map_idx, star_idx, stage_idx, 1) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_catamin_stage(self, map: int, star: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.catamin_stages.chapters.clear_stage(map, star, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_catamin_stages(self) -> SaveEditor: # Discord id ba23d
        ch = self._save.catamin_stages.chapters # Discord id ba23d
        for map_idx, chapters_stars in enumerate(ch.chapters): # Discord id ba23d
            for star_idx, chapter in enumerate(chapters_stars.chapters): # Discord id ba23d
                for stage_idx in range(len(chapter.stages)): # Discord id ba23d
                    ch.clear_stage(map_idx, star_idx, stage_idx, 1) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_gauntlet_stage(self, map: int, star: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.gauntlets.clear_stage(map, star, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unclear_gauntlet_stage(self, map: int, star: int, stage: int) -> SaveEditor: # Discord id ba23d
        self._save.gauntlets.unclear_stage(map, star, stage) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_gauntlets(self) -> SaveEditor: # Discord id ba23d
        for mi, m in enumerate(self._save.gauntlets.chapters): # Discord id ba23d
            for si in range(len(m.chapters)): # Discord id ba23d
                for stgi in range(len(m.chapters[si].stages)): # Discord id ba23d
                    self._save.gauntlets.clear_stage(mi, si, stgi, 1) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_collab_gauntlet_stage(self, map: int, star: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.collab_gauntlets.clear_stage(map, star, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_collab_gauntlets(self) -> SaveEditor: # Discord id ba23d
        for mi, m in enumerate(self._save.collab_gauntlets.chapters): # Discord id ba23d
            for si in range(len(m.chapters)): # Discord id ba23d
                for stgi in range(len(m.chapters[si].stages)): # Discord id ba23d
                    self._save.collab_gauntlets.clear_stage(mi, si, stgi, 1) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_behemoth_culling_stage(self, map: int, star: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.behemoth_culling.clear_stage(map, star, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_behemoth_culling(self) -> SaveEditor: # Discord id ba23d
        for mi, m in enumerate(self._save.behemoth_culling.chapters): # Discord id ba23d
            for si in range(len(m.chapters)): # Discord id ba23d
                for stgi in range(len(m.chapters[si].stages)): # Discord id ba23d
                    self._save.behemoth_culling.clear_stage(mi, si, stgi, 1) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_enigma_stage(self, map: int, star: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.enigma_clears.clear_stage(map, star, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_enigma(self) -> SaveEditor: # Discord id ba23d
        for mi, m in enumerate(self._save.enigma_clears.chapters): # Discord id ba23d
            for si in range(len(m.chapters)): # Discord id ba23d
                for stgi in range(len(m.chapters[si].stages)): # Discord id ba23d
                    self._save.enigma_clears.clear_stage(mi, si, stgi, 1) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_aku_stage(self, map: int, star: int, stage: int, clear_count: int = 1) -> SaveEditor: # Discord id ba23d
        if map < len(self._save.aku.chapters): # Discord id ba23d
            cs = self._save.aku.chapters[map] # Discord id ba23d
            if star < len(cs.chapters) and stage < len(cs.chapters[star].stages): # Discord id ba23d
                cs.chapters[star].stages[stage].clear_stage(clear_count) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_aku(self) -> SaveEditor: # Discord id ba23d
        for cs in self._save.aku.chapters: # Discord id ba23d
            for ch in cs.chapters: # Discord id ba23d
                for stage in ch.stages: # Discord id ba23d
                    stage.clear_stage(1) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_zero_legends_stage(self, map: int, star: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.zero_legends.clear_stage(map, star, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unclear_zero_legends_stage(self, map: int, star: int, stage: int) -> SaveEditor: # Discord id ba23d
        self._save.zero_legends.unclear_stage(map, star, stage) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_zero_legends(self) -> SaveEditor: # Discord id ba23d
        for map_idx, cs in enumerate(self._save.zero_legends.chapters): # Discord id ba23d
            for star_idx, ch in enumerate(cs.chapters): # Discord id ba23d
                for stage_idx in range(len(ch.stages)): # Discord id ba23d
                    self._save.zero_legends.clear_stage(map_idx, star_idx, stage_idx, 1) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_dojo_chapter_stage(self, map: int, star: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.dojo_chapters.clear_stage(map, star, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_tower_stage(self, map: int, star: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.tower.chapters.clear_stage(map, star, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unclear_tower_stage(self, map: int, star: int, stage: int) -> SaveEditor: # Discord id ba23d
        self._save.tower.chapters.unclear_stage(map, star, stage) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_legend_quest_stage(self, map: int, star: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        self._save.legend_quest.clear_stage(map, star, stage, clear_amount) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unclear_legend_quest_stage(self, map: int, star: int, stage: int) -> SaveEditor: # Discord id ba23d
        self._save.legend_quest.unclear_stage(map, star, stage) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_legend_quest(self) -> SaveEditor: # Discord id ba23d
        for map_idx, cs in enumerate(self._save.legend_quest.chapters): # Discord id ba23d
            for star_idx, ch in enumerate(cs.chapters): # Discord id ba23d
                for stage_idx in range(len(ch.stages)): # Discord id ba23d
                    self._save.legend_quest.clear_stage(map_idx, star_idx, stage_idx, 1) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_outbreak(self, chapter_id: int, stage_id: int, cleared: bool = True) -> SaveEditor: # Discord id ba23d
        self._save.outbreaks.clear_outbreak(chapter_id, stage_id, cleared) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_outbreaks(self) -> SaveEditor: # Discord id ba23d
        for chapter in self._save.outbreaks.chapters.values(): # Discord id ba23d
            for stage in chapter.outbreaks.values(): # Discord id ba23d
                stage.cleared = True # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_ex_stage(self, chapter: int, stage: int, clear_amount: int = 1) -> SaveEditor: # Discord id ba23d
        if chapter < len(self._save.ex_stages.chapters): # Discord id ba23d
            ch = self._save.ex_stages.chapters[chapter] # Discord id ba23d
            if stage < len(ch.stages): # Discord id ba23d
                ch.stages[stage].clear_amount = clear_amount # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_ex_stages(self) -> SaveEditor: # Discord id ba23d
        for ch in self._save.ex_stages.chapters: # Discord id ba23d
            for stage in ch.stages: # Discord id ba23d
                stage.clear_amount = 1 # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_stages(self) -> SaveEditor: # Discord id ba23d
        self.clear_all_story() # Discord id ba23d
        self.max_story_treasures() # Discord id ba23d
        self.clear_all_events() # Discord id ba23d
        self.clear_all_uncanny() # Discord id ba23d
        self.clear_all_catamin_stages() # Discord id ba23d
        self.clear_all_gauntlets() # Discord id ba23d
        self.clear_all_collab_gauntlets() # Discord id ba23d
        self.clear_all_behemoth_culling() # Discord id ba23d
        self.clear_all_enigma() # Discord id ba23d
        self.clear_all_aku() # Discord id ba23d
        self.clear_all_zero_legends() # Discord id ba23d
        self.clear_all_legend_quest() # Discord id ba23d
        self.clear_all_ex_stages() # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def max_all_items(self) -> SaveEditor: # Discord id ba23d
        from bcsfe.core.max_value_helper import MaxValueType # Discord id ba23d
        mv = core.core_data.max_value_manager # Discord id ba23d
        self._save.catfood = mv.get(MaxValueType.CATFOOD) # Discord id ba23d
        self._save.xp = mv.get(MaxValueType.XP) # Discord id ba23d
        self._save.normal_tickets = mv.get(MaxValueType.NORMAL_TICKETS) # Discord id ba23d
        self._save.rare_tickets = mv.get(MaxValueType.RARE_TICKETS) # Discord id ba23d
        self._save.platinum_tickets = mv.get(MaxValueType.PLATINUM_TICKETS) # Discord id ba23d
        self._save.legend_tickets = mv.get(MaxValueType.LEGEND_TICKETS) # Discord id ba23d
        self._save.platinum_shards = 10 * mv.get(MaxValueType.PLATINUM_TICKETS) # Discord id ba23d
        self._save.np = mv.get(MaxValueType.NP) # Discord id ba23d
        self._save.leadership = mv.get(MaxValueType.LEADERSHIP) # Discord id ba23d
        for item in self._save.battle_items.items: # Discord id ba23d
            item.amount = mv.get(MaxValueType.BATTLE_ITEMS) # Discord id ba23d
        for i in range(len(self._save.catseyes)): # Discord id ba23d
            self._save.catseyes[i] = mv.get(MaxValueType.CATSEYES) # Discord id ba23d
        for i in range(len(self._save.catamins)): # Discord id ba23d
            self._save.catamins[i] = mv.get(MaxValueType.CATAMINS) # Discord id ba23d
        for i in range(len(self._save.labyrinth_medals)): # Discord id ba23d
            self._save.labyrinth_medals[i] = mv.get(MaxValueType.LABYRINTH_MEDALS) # Discord id ba23d
        self._save.hundred_million_ticket = mv.get(MaxValueType.HUNDRED_MILLION_TICKETS) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_tutorial_cleared(self) -> SaveEditor: # Discord id ba23d
        self._save.tutorial_state = 1 # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unlock_equip_menu(self) -> SaveEditor: # Discord id ba23d
        self._save.unlock_equip_menu() # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def remove_rank_up_sale(self) -> SaveEditor: # Discord id ba23d
        self._save.rank_up_sale_value = 0 # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def get_user_rank(self) -> int: # Discord id ba23d
        return self._save.calculate_user_rank() # Discord id ba23d
 # Discord id ba23d
    @property # Discord id ba23d
    def equip_slots(self) -> int: # Discord id ba23d
        return self._save.lineups.equip_slots # Discord id ba23d
 # Discord id ba23d
    @equip_slots.setter # Discord id ba23d
    def equip_slots(self, v: int) -> None: # Discord id ba23d
        self._save.lineups.equip_slots = v # Discord id ba23d
 # Discord id ba23d
    def unlock_enemy_guide(self) -> SaveEditor: # Discord id ba23d
        if hasattr(self._save, 'enemy_guide'): # Discord id ba23d
            for enemy in self._save.enemy_guide.enemies: # Discord id ba23d
                enemy.unlocked = True # Discord id ba23d
                enemy.killed = True # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def unlock_all_medals(self) -> SaveEditor: # Discord id ba23d
        if hasattr(self._save, 'medals'): # Discord id ba23d
            for i in range(len(self._save.medals.medals)): # Discord id ba23d
                self._save.medals.medals[i] = 1 # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def clear_all_missions(self) -> SaveEditor: # Discord id ba23d
        if hasattr(self._save, 'missions'): # Discord id ba23d
            for mission_id in self._save.missions.missions.keys(): # Discord id ba23d
                self._save.missions.missions[mission_id].state = 2 # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_cat_shrine(self, level: int, xp_donated: int) -> SaveEditor: # Discord id ba23d
        if hasattr(self._save, 'cat_shrine'): # Discord id ba23d
            self._save.cat_shrine.level = level # Discord id ba23d
            self._save.cat_shrine.xp_offered = xp_donated # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_dojo_score(self, dojo_id: int, score: int) -> SaveEditor: # Discord id ba23d
        if hasattr(self._save, 'dojo_scores'): # Discord id ba23d
            self._save.dojo_scores[dojo_id] = score # Discord id ba23d
        elif hasattr(self._save, 'dojo') and hasattr(self._save.dojo, 'scores'): # Discord id ba23d
            self._save.dojo.scores[dojo_id] = score # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_gold_pass(self, days: int = 300) -> SaveEditor: # Discord id ba23d
        if hasattr(self._save, 'officers_club'): # Discord id ba23d
            self._save.officers_club.expiry_date = int(time.time()) + (days * 86400) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def set_play_time(self, hours: int, minutes: int = 0) -> SaveEditor: # Discord id ba23d
        if hasattr(self._save, 'play_time'): # Discord id ba23d
            if hasattr(self._save.play_time, 'play_time'): # Discord id ba23d
                self._save.play_time.play_time = (hours * 3600) + (minutes * 60) # Discord id ba23d
            else: # Discord id ba23d
                self._save.play_time = (hours * 3600) + (minutes * 60) # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def remove_ban_flags(self) -> SaveEditor: # Discord id ba23d
        if hasattr(self._save, 'cheat_flags'): # Discord id ba23d
            self._save.cheat_flags = [0] * len(self._save.cheat_flags) # Discord id ba23d
        if hasattr(self._save, 'account_banned'): # Discord id ba23d
            self._save.account_banned = False # Discord id ba23d
        if hasattr(self._save, 'is_banned'): # Discord id ba23d
            self._save.is_banned = False # Discord id ba23d
        if hasattr(self._save, 'game_hacks'): # Discord id ba23d
            self._save.game_hacks = 0 # Discord id ba23d
        if hasattr(self._save, 'time_manipulation_flags'): # Discord id ba23d
            self._save.time_manipulation_flags = 0 # Discord id ba23d
        if hasattr(self._save, 'rank_up_sale_value'): # Discord id ba23d
            self._save.rank_up_sale_value = 0 # Discord id ba23d
        return self # Discord id ba23d
 # Discord id ba23d
    def get_summary(self) -> dict[str, Any]: # Discord id ba23d
        return { # Discord id ba23d
            "cc": self.cc, # Discord id ba23d
            "game_version": self.game_version, # Discord id ba23d
            "inquiry_code": self.inquiry_code, # Discord id ba23d
            "transfer_code": self.transfer_code, # Discord id ba23d
            "confirmation_code": self.confirmation_code, # Discord id ba23d
            "catfood": self.catfood, # Discord id ba23d
            "xp": self.xp, # Discord id ba23d
            "normal_tickets": self.normal_tickets, # Discord id ba23d
            "rare_tickets": self.rare_tickets, # Discord id ba23d
            "platinum_tickets": self.platinum_tickets, # Discord id ba23d
            "legend_tickets": self.legend_tickets, # Discord id ba23d
            "platinum_shards": self.platinum_shards, # Discord id ba23d
            "np": self.np, # Discord id ba23d
            "leadership": self.leadership, # Discord id ba23d
            "user_rank": self.get_user_rank(), # Discord id ba23d
        } # Discord id ba23d
 # Discord id ba23d
def _sync_load_from_transfer( # Discord id ba23d
    transfer_code: str, # Discord id ba23d
    confirmation_code: str, # Discord id ba23d
    cc: str, # Discord id ba23d
) -> SaveEditor: # Discord id ba23d
    gv = core.GameVersion(120200) # Discord id ba23d
    country = CountryCode(cc) # Discord id ba23d
    handler, result = ServerHandler.from_codes( # Discord id ba23d
        transfer_code, # Discord id ba23d
        confirmation_code, # Discord id ba23d
        country, # Discord id ba23d
        gv, # Discord id ba23d
        print=False, # Discord id ba23d
        save_backup=False, # Discord id ba23d
    ) # Discord id ba23d
    if handler is None: # Discord id ba23d
        if result is not None and result.response is not None: # Discord id ba23d
            body = result.response.content.decode("utf-8", errors="replace") # Discord id ba23d
            raise SaveEditorError(f"HTTP {result.response.status_code}: {body}") # Discord id ba23d
        raise SaveEditorError("Network error") # Discord id ba23d
    editor = SaveEditor.__new__(SaveEditor) # Discord id ba23d
    editor._save = handler.save_file # Discord id ba23d
    return editor # Discord id ba23d
 # Discord id ba23d
async def load_from_transfer( # Discord id ba23d
    transfer_code: str, # Discord id ba23d
    confirmation_code: str, # Discord id ba23d
    cc: str = "en", # Discord id ba23d
) -> SaveEditor: # Discord id ba23d
    return await asyncio.to_thread( # Discord id ba23d
        _sync_load_from_transfer, transfer_code, confirmation_code, cc # Discord id ba23d
    ) # Discord id ba23d
 # Discord id ba23d
def _sync_create_account(save_path: str, cc: str) -> SaveEditor: # Discord id ba23d
    editor = SaveEditor.from_file(save_path, cc=cc) # Discord id ba23d
    handler = ServerHandler(editor._save, print=False) # Discord id ba23d
    success = handler.create_new_account() # Discord id ba23d
    if not success: # Discord id ba23d
        raise SaveEditorError("Network error") # Discord id ba23d
    return editor # Discord id ba23d
 # Discord id ba23d
async def create_account(save_path: str, cc: str = "en") -> SaveEditor: # Discord id ba23d
    return await asyncio.to_thread(_sync_create_account, save_path, cc) # Discord id ba23d