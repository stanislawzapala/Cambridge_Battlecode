# Packages
# 1. Official
from cambc import Controller, Direction, EntityType, Environment, Position, Team, ResourceType, GameConstants
# 2. Koszty bazowe budynków (wartości dynamicznie pobierane z silnika gry)
CONVEYOR_BASE_COST = GameConstants.CONVEYOR_BASE_COST
SPLITTER_BASE_COST = GameConstants.SPLITTER_BASE_COST
BRIDGE_BASE_COST = GameConstants.BRIDGE_BASE_COST
ARMOURED_CONVEYOR_BASE_COST = GameConstants.ARMOURED_CONVEYOR_BASE_COST
HARVESTER_BASE_COST = GameConstants.HARVESTER_BASE_COST
ROAD_BASE_COST = GameConstants.ROAD_BASE_COST
BARRIER_BASE_COST = GameConstants.BARRIER_BASE_COST
GUNNER_BASE_COST = GameConstants.GUNNER_BASE_COST
SENTINEL_BASE_COST = GameConstants.SENTINEL_BASE_COST
BREACH_BASE_COST = GameConstants.BREACH_BASE_COST
LAUNCHER_BASE_COST = GameConstants.LAUNCHER_BASE_COST
FOUNDRY_BASE_COST = GameConstants.FOUNDRY_BASE_COST
BUILDER_BOT_BASE_COST = GameConstants.BUILDER_BOT_BASE_COST
# 2. For random movement (for testing purposes)
import random
# 3. For priority queue (if we later want to implement A*)
import heapq
# 4. For Enum states
from enum import Enum, auto
# 5. Math for explore logic
import math


# ==========================================
# MASZYNA STANÓW BOTA
# ==========================================
class BotState(Enum):
    EXPLORE = auto()         # Losowy zwiad i roznoszenie feromonów
    BUILD_MINE = auto()      # Znalazł złoże, idzie zbudować Harvester
    BUILD_BELT = auto()      # Zbudował kopalnię, ciągnie taśmociąg do Bazy/Sieci
    BUILD_DEFENSE = auto()   # (Rezerwa) Idzie postawić wieżyczkę w strategicznym miejscu
    REPAIR_NETWORK = auto()  # (Rezerwa) Idzie załatać przerwany taśmociąg
    BUILD_BUNKER = auto()    # (Rezerwa) Idzie zbudować Bunker w newralgicznym punkcie
    HARRAS = auto()          # (Rezerwa) Znalazł wroga, idzie go nękać i rozpraszać
    ROAD_LAYER = auto()      # Wczesny zwiad (tury 1-4): biega losowo i kładzie drogi
    KAMIKAZE = auto()        # Stawia sentinela przy wrogim harvesterze lub dokonuje autodestrukcji
    REPAIRMAN = auto()       # Leczy i naprawia naszą sieć conveyor/most/splitter
    FORTIFIER = auto()       # Obudowuje harvestery Sentinelami
    SMELTER = auto()         # Buduje Foundry i podłącza do sieci

# --- MAPA I KOMUNIKACJA MIĘDZY BOTAMI ---
ENV_TO_INT = {Environment.EMPTY: 0, Environment.WALL: 1, Environment.ORE_TITANIUM: 2, Environment.ORE_AXIONITE: 3}
INT_TO_ENV = {v: k for k, v in ENV_TO_INT.items()}

# 15 typów budynków/jednostek (0 rezerwujemy na "Brak budynku")
ENTITY_TYPES = [
    EntityType.BUILDER_BOT, EntityType.CORE, EntityType.GUNNER, EntityType.SENTINEL, 
    EntityType.BREACH, EntityType.LAUNCHER, EntityType.CONVEYOR, EntityType.SPLITTER, 
    EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.HARVESTER, 
    EntityType.FOUNDRY, EntityType.ROAD, EntityType.BARRIER, EntityType.MARKER
]
ENTITY_TO_INT = {e: i+1 for i, e in enumerate(ENTITY_TYPES)}
INT_TO_ENTITY = {i+1: e for i, e in enumerate(ENTITY_TYPES)}



# Kierunki (bez CENTRE)
DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]
ORTHOGONAL_DIRECTIONS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]


# Typy budynków, po których można chodzić (droga, taśmociąg, pancerna taśma, marker)
passable_types = {EntityType.ROAD, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.MARKER, EntityType.SPLITTER}


# --- GLOBALNE ZBIORY OPTYMALIZACYJNE  ---

# 1. ŚRODOWISKO I TEREN
ORES = {Environment.ORE_TITANIUM, Environment.ORE_AXIONITE}
HARD_OBSTACLES = {Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE}

# 2. PORUSZANIE SIĘ I NAWIGACJA (A* i uniki)
WALKABLE_TYPES = {EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.ROAD, EntityType.BRIDGE, EntityType.SPLITTER}
PASSABLE_TYPES_SET = {EntityType.ROAD, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.MARKER, EntityType.SPLITTER}

# 3. STANY BOTÓW (Maszyna stanów)
BUILDING_STATES = {BotState.BUILD_MINE, BotState.BUILD_BELT, BotState.BUILD_BUNKER, BotState.FORTIFIER, BotState.SMELTER}
# Uwaga: Dodałem tu BotState.HARRAS, o którym mówiliśmy wcześniej!
WANDERING_STATES = {BotState.EXPLORE, BotState.ROAD_LAYER, BotState.KAMIKAZE, BotState.REPAIRMAN, BotState.FORTIFIER, BotState.SMELTER, BotState.HARRAS}
LATE_STATES = [BotState.HARRAS, BotState.KAMIKAZE, BotState.EXPLORE, BotState.FORTIFIER, BotState.REPAIRMAN, BotState.SMELTER]

# 4. SIEĆ LOGISTYCZNA
# (NETWORK i NETWORK_TYPES_S to obecnie ten sam zbiór - docelowo zrób refactor i zostaw tylko NETWORK)
NETWORK = {EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.SPLITTER}
NETWORK_TYPES_S = {EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.SPLITTER}
# NETWORK_TYPES to to samo co wyżej, ale zawiera Harvestera
NETWORK_TYPES = {EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.SPLITTER, EntityType.HARVESTER}

# 5. PAMIĘĆ, STRATEGIA I CELE DO WALKI
VIP_FRIENDLY = {EntityType.HARVESTER, EntityType.FOUNDRY, EntityType.GUNNER, EntityType.SENTINEL, EntityType.BREACH, EntityType.LAUNCHER}
JUNK_ENEMY_BUILDINGS = {EntityType.ROAD, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE}
BUILDINGS_PRIO2 = {
    EntityType.HARVESTER, EntityType.FOUNDRY, EntityType.GUNNER,
    EntityType.SENTINEL, EntityType.BREACH, EntityType.LAUNCHER,
    EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR,
    EntityType.BRIDGE, EntityType.SPLITTER, EntityType.BARRIER, EntityType.CORE
}

# 6. EKONOMIA
COST_MAPPING = {
    'conveyor': CONVEYOR_BASE_COST,
    'splitter': SPLITTER_BASE_COST,
    'bridge': BRIDGE_BASE_COST,
    'armoured_conveyor': ARMOURED_CONVEYOR_BASE_COST,
    'harvester': HARVESTER_BASE_COST,
    'road': ROAD_BASE_COST,
    'barrier': BARRIER_BASE_COST,
    'gunner': GUNNER_BASE_COST,
    'sentinel': SENTINEL_BASE_COST,
    'breach': BREACH_BASE_COST,
    'launcher': LAUNCHER_BASE_COST,
    'foundry': FOUNDRY_BASE_COST,
    'builder_bot': BUILDER_BOT_BASE_COST
}




class Player:
    def __init__(self):
        # ---DANE WSPÓLNE DLA DRUŻYNY ---
        self.allied_core_tiles: set[Position] = set()
        self.allied_splitter_tiles: set[Position] = set()
        self.enemy_roads_near_core: set[Position] = set()
        self.my_core_center: Position | None = None
        self.my_core_cx: int = 0
        self.my_core_cy: int = 0
        
        # CORE
        self.spawned_bots_count: int = 0
        self.starting_protocol: bool = False
        self.core_facts_to_report: list = []
        self.replacement_bots_pending: int = 0
        self.bot_late_spawn_index: int = 0
        
        # --- PAMIĘĆ PROBKI ---
        self.memory: dict[Position, Environment] = {}
        self.buildings: dict[Position, tuple[EntityType | None, Team | None, int]] = {}
        # Lista VIP: słownik (pos -> (env, b_type, is_enemy)) dla każdego bota
        self.vip_facts: dict[Position, tuple[Environment, EntityType | None, bool]] = {}
        # ore_pos → tura ostatniej rezerwacji odczytanej z markera
        self.claimed_ores: dict[Position, int] = {}

        # --- STAN I RUCH ---
        self.bot_state: BotState | None = None
        self.target: Position | None = None
        self.path: list[Direction] = []
        self.spawn_round: int = 0 
        
        # --- WYDOBYCIE ---
        # Złoże które dany bot aktualnie obsługuje (BUILD_MINE / BUILD_BELT)
        self.assigned_ore: Position | None = None
        # Tura wejścia w BUILD_MINE — do bezpiecznika timeout
        self.mine_since: int = 0

        # --- BUDOWANIE ---
        # Węzeł, od którego bot aktualnie buduje sieć mostów
        self.last_bridge_node: Position | None = None
        # Historia węzłów bieżącej nitki mostów (do wykrywania pętli)
        self.belt_chain: set[Position] = set()
        # Pole Splittera do zbudowania w następnej turze po wylądowaniu mostu
        # (bot nie może zbudować mostu i Splittera w tej samej turze)
        self.pending_splitter: tuple[Position, Direction] | None = None
        # Licznik tur bez postępu w BUILD_BELT — po 3 turach porzucamy budowę
        self.belt_stuck_counter: int = 0
        
        # --- BEZPIECZNIKI RUCHU ---
        # Tura w której ustawiono aktualny cel ruchu; reset po 60 turach bez dotarcia
        self.target_since: int = 0
        self.target_last: Position | None = None
        
        # --- SPECJALNE STANY ---
        # KAMIKAZE: zapamiętana pozycja i kierunek sentinela do zbudowania
        self.kamikaze_sentinel_pos: Position | None = None
        self.kamikaze_sentinel_dir: Direction | None = None
        # FORTIFIER: aktualnie obudowywany harvester
        self.fortifier_harvest_target: Position | None = None
        # REPAIRMAN: śledzenie HP i reagowanie na obrażenia
        self.repairman_prev_hp: int = 30       # HP z poprzedniej tury
        self.repairman_danger_pos: Position | None = None  # gdzie dostał obrażenia
        self.repairman_flee_turns: int = 0     # ile tur jeszcze ucieka
        self.repairman_markers_placed: int = 0   # ile markerów alarmowych postawił
        # SMELTER: faza pracy ('scan'|'build'|'connect') i zapamiętana lokalizacja foundry
        self.smelter_phase: str = 'scan'
        self.smelter_foundry_pos:  Position | None = None
        self.smelter_titanium_src: Position | None = None
        self.smelter_axionite_src: Position | None = None

       

    def calculate_astar_path(self, ct: Controller, start: Position, target: Position, w: int, h: int, bot_id: int, my_team: Team, stop_adjacent: bool = False) -> list[Direction] | None:
        """
        Zwraca listę kierunków za pomocą optymistycznego Frontier A* (Frontier A-Star). 
        Możemy ustawić stop_adjacent=True, jeśli chcemy, żeby bot zatrzymał się na polu obok celu (przydatne np. do budowania).
        """
        
        # Kolejka priorytetowa: trzyma krotki (priorytet, koszt_do_tej_pory, x, y, pozycja)
        queue = []
        heapq.heappush(queue, (0, 0, start.x, start.y, start))
        
        came_from = {start: None}
        cost_so_far = {start: 0}
        iterations = 0
        
        target_node = None # Zmienna zapamiętująca, gdzie fizycznie skończyliśmy

        # Najpierw posortujmy kierunki tak, aby te najbliżej celu (minimalny dystans do targetu) były pierwsze - wyciągamy tylko pierwszy kierunek
        DIRECTIONS_PREFERENCE = sorted(DIRECTIONS, key=lambda d: start.add(d).distance_squared(target))

        while queue:
            iterations += 1
            if iterations > 2000:
                # FRONTIER A*: Skończył się limit czasu! 
                # Zamiast się poddawać, wyciągamy z kolejki NAJLEPSZY punkt, który A* zamierzał właśnie sprawdzić.
                if queue:
                    _, _, _, _, best_node = heapq.heappop(queue)
                    target_node = best_node
                break
            
            
            # Wyciągamy kafelek, który ma NAJLEPSZY priorytet (najbliżej celu)
            priority, current_cost, _, _, curr = heapq.heappop(queue)

            if stop_adjacent and curr.distance_squared(target) <= 2:
                target_node = curr
                break
            elif not stop_adjacent and curr == target:
                target_node = curr
                break
            
            
            for d in DIRECTIONS_PREFERENCE:
                next_pos = curr.add(d)
                
                if not (0 <= next_pos.x < w and 0 <= next_pos.y < h):
                    continue
                
                # Każdy krok kosztuje nas 1 punkt
                new_cost = current_cost + 1
                
                # Jeśli jeszcze tu nie byliśmy ALBO znaleźliśmy tańszą/szybszą ścieżkę do tego pola
                if next_pos not in cost_so_far or new_cost < cost_so_far[next_pos]:
                    
                    memory_env = self.memory.get(next_pos, Environment.EMPTY)
                    if memory_env in HARD_OBSTACLES:
                        continue # Pamiętamy, że tu jest mur lub ruda, omijamy!
                    
                    is_blocked = False

                    # 2. Czytamy budynki z pamięci bota
                    b_info = self.buildings.get(next_pos)
                    if b_info is not None:
                        b_type, b_team, _ = b_info
                        if b_type is not None:
                            # Jeśli to nie jest droga/taśmociąg i nie jest to nasz Rdzeń, to nas blokuje
                            if b_type not in passable_types and b_type != EntityType.CORE:
                                is_blocked = True
                            # Wrogi rdzeń też blokuje
                            elif b_type == EntityType.CORE and b_team != my_team:
                                is_blocked = True

                    if is_blocked:
                        continue

                    # 2. ZAPISUJEMY KOSZT
                    cost_so_far[next_pos] = new_cost
                    
                    # 3. A*: Podstawowa heurystyka (Czebyszew)
                    heuristic = max(abs(next_pos.x - target.x), abs(next_pos.y - target.y))
                    
                    # --- TIE-BREAKER (Lekarstwo na zygzaki) ---
                    # Obliczamy wektory, żeby sprawdzić, czy zjeżdżamy z idealnej prostej
                    dx1 = next_pos.x - target.x
                    dy1 = next_pos.y - target.y
                    dx2 = start.x - target.x
                    dy2 = start.y - target.y
                    
                    # Iloczyn wektorowy
                    cross_product = abs(dx1 * dy2 - dx2 * dy1)
                    
                    # Priorytet to: koszt + heurystyka + mała kara za zjazd z prostej linii
                    priority = new_cost + heuristic + (cross_product * 0.0001)
                    
                    # Wrzucamy do kolejki
                    heapq.heappush(queue, (priority, new_cost, next_pos.x, next_pos.y, next_pos))
                    came_from[next_pos] = (curr, d) # type: ignore

        # Odtwarzanie ścieżki
        if target_node is None or target_node not in came_from:
            return None 

        path = []
        curr = target_node
        while curr != start:
            prev_pos, move_dir = came_from[curr]
            path.append(move_dir)
            curr = prev_pos
            
        path.reverse() 
        return path

    
    def can_walk_on_building(self, b_id: int, my_team: Team, ct: Controller) -> bool:
        """
        Sprawdza, czy można chodzić po budynku wroga (droga/taśmociąg/pancerna taśma).
        Nie bierze pod uwagę obecności probki.
        """
        if b_id is None:
            return False
        b_type = ct.get_entity_type(b_id)
        return b_type in WALKABLE_TYPES
    

    def pack_map_marker(self, turn: int, pos: Position, env: Environment, b_type: EntityType | None, is_enemy: bool) -> int:
        """KANAŁ 0: Pakuje informacje o odkrytym terenie/budynku."""
        env_val = ENV_TO_INT.get(env, 0)
        entity_val = ENTITY_TO_INT.get(b_type, 0) if b_type else 0
        team_val = 1 if is_enemy else 0
        
        msg_type = 0
        turn &= 0b11111111111
        x = pos.x & 0b111111
        y = pos.y & 0b111111
        
        # Ostatnie 7 bitów: env (2), entity (4), team (1)
        payload = (env_val << 5) | (entity_val << 1) | team_val
        return (msg_type << 30) | (turn << 19) | (x << 13) | (y << 7) | payload

    def pack_claim_marker(self, turn: int, ore_pos: Position) -> int:
        """KANAŁ 1: Pakuje rezerwację złoża (bot idzie zająć się tym złożem)."""
        msg_type = 1
        turn &= 0b11111111111
        x = ore_pos.x & 0b111111
        y = ore_pos.y & 0b111111
        payload = 0  # kanał 1 nie potrzebuje dodatkowych danych w payload
        return (msg_type << 30) | (turn << 19) | (x << 13) | (y << 7) | payload
    
    
    def unpack_marker(self, value: int) -> dict:
        """Uniwersalny dekoder. Rozpoznaje typ i zwraca słownik z odpowiednimi kluczami."""
        # Najpierw czytamy NAGŁÓWEK (wspólny dla wszystkich)
        msg_type = (value >> 30) & 0b11
        turn = (value >> 19) & 0b11111111111
        x = (value >> 13) & 0b111111
        y = (value >> 7) & 0b111111
        pos = Position(x, y)
        
        # Ładunek (7 najmłodszych bitów)
        payload = value & 0b1111111
        
        data = {'type': msg_type, 'turn': turn, 'pos': pos}
        
        if msg_type == 0:
            data['is_enemy'] = (payload & 0b1) == 1
            data['b_type'] = INT_TO_ENTITY.get((payload >> 1) & 0b1111, None)
            data['env'] = INT_TO_ENV.get((payload >> 5) & 0b11, Environment.EMPTY)
        elif msg_type == 1:
            # KANAŁ 1: rezerwacja złoża — ore_pos i turn są już w nagłówku
            data['ore_pos'] = pos  # alias dla czytelności
            
        return data


    def find_nearest_vip_target(self, my_pos: Position, vip_facts: dict, 
                                target_envs: list[Environment] = None, # type: ignore
                                target_btypes: list[EntityType] = None, # type: ignore
                                ownership: str = 'empty') -> Position | None:
        """
        Uniwersalna wyszukiwarka w bazie VIP.
        ownership: 'empty' (brak budynku), 'mine' (nasz budynek), 'enemy' (wrogi budynek), 'any' (obojętnie)
        """
        nearest_pos = None
        min_distance = float('inf')
        
        for pos, (env, b_type, is_enemy) in vip_facts.items():
            # 1. FILTR TERENU (jeśli podano listę, sprawdzamy czy pasuje)
            if target_envs is not None and env not in target_envs:
                continue
                
            # 2. FILTR BUDYNKU (jeśli podano listę, sprawdzamy czy pasuje)
            if target_btypes is not None and b_type not in target_btypes:
                continue
                
            # 3. FILTR WŁASNOŚCI
            if ownership == 'empty' and b_type is not None:
                continue
            if ownership == 'mine' and (b_type is None or is_enemy):
                continue
            if ownership == 'enemy' and (b_type is None or not is_enemy):
                continue
                
            # Jeśli przeszliśmy wszystkie filtry, sprawdzamy odległość
            dist = my_pos.distance_squared(pos)
            if dist < min_distance:
                min_distance = dist
                nearest_pos = pos
                
        return nearest_pos


    def building_priority(self, b_id, ct: Controller) -> int:
        """Zwraca poziom ważności budynku na polu (0=brak, 1=marker, 2=droga, 3=reszta)."""
        if b_id is None:
            return 0
        b_type = ct.get_entity_type(b_id)
        if b_type == EntityType.MARKER:
            return 1
        if b_type == EntityType.ROAD:
            return 2
        return 3

    def can_replace_with(self, pos, new_priority: int, my_team, ct: Controller) -> bool:
        """Czy można zniszczyć co stoi na pos, żeby postawić coś o priorytecie new_priority?
        Można niszczyć tylko rzeczy o NIŻSZYM priorytecie (nie równym).
        Niszczymy własne budynki (jeśli mniej ważne) oraz markery przeciwnika."""
        if not ct.is_in_vision(pos):
            return True  # nie wiemy co tam stoi — optymistycznie OK
        b_id = ct.get_tile_building_id(pos)
        if b_id is None:
            return True  # puste
        if ct.get_team(b_id) != my_team:
            # Cudzy budynek — możemy zastąpić tylko marker przeciwnika
            return ct.get_entity_type(b_id) == EntityType.MARKER
        existing_priority = self.building_priority(b_id, ct)
        return new_priority > existing_priority

    def _can_afford_build(self, ct: Controller, build_mode: str) -> bool:
        """
        Sprawdza czy drużyna ma surowce na zbudowanie budynku,
        używając zewnętrznych stałych kosztów.
        """

        # Pobieramy aktualne zasoby i mnożnik
        titanium_owned, axionite_owned = ct.get_global_resources()
        scale = ct.get_scale_percent() / 100.0
        
        # Wyciągamy bazowe wartości z krotki przypisanej do danego trybu
        base_ti, base_ax = COST_MAPPING[build_mode]

        # Obliczamy realny koszt (rzutowanie na int, bo koszty są zazwyczaj całkowite)
        cost_ti = int(base_ti * scale)
        cost_ax = int(base_ax * scale)

        return titanium_owned >= cost_ti and axionite_owned >= cost_ax

    def _ore_already_claimed_by_other(self, ct: Controller, my_id: int, my_team, ore_pos: Position, current_round: int) -> bool:
        """Zwraca True jeśli złoże jest już obsługiwane przez innego bota:
        - aktywna rezerwacja w claimed_ores (< 20 tur temu), LUB
        - inny nasz bot fizycznie stoi na sąsiednim polu złoża (distance_sq <= 2).
        NIE liczymy siebie samego."""
        CLAIM_TTL = 20
        claim_turn = self.claimed_ores.get(ore_pos, -1)
        if claim_turn >= 0 and (current_round - claim_turn) < CLAIM_TTL:
            return True
        # Sprawdzamy fizyczną obecność innego bota w zasięgu wzroku
        if ct.is_in_vision(ore_pos):
            w = ct.get_map_width()
            h = ct.get_map_height()
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    nb = Position(ore_pos.x + dx, ore_pos.y + dy)
                    if not (0 <= nb.x < w and 0 <= nb.y < h):
                        continue
                    if not ct.is_in_vision(nb):
                        continue
                    try:
                        other_bot_id = ct.get_tile_builder_bot_id(nb)
                    except Exception:
                        continue
                    if other_bot_id is not None and other_bot_id != my_id:
                        try:
                            if ct.get_team(other_bot_id) == my_team:
                                return True
                        except Exception:
                            continue
        return False

    def _place_claim_marker_near_ore(self, ct: Controller, my_id: int, my_team, ore_pos: Position, current_round: int, forbidden_tiles: set) -> None:
        """
        Stawia marker-rezerwację złoża. Najpierw próbuje na samym polu złoża,
        potem na sąsiednich polach. Może zniszczyć blokujący marker (nasz lub wrogi)
        albo naszą drogę. Marker koduje pozycję złoża w kanale 1.
        """
        map_width = ct.get_map_width()
        map_height = ct.get_map_height()

        # Kandydaci: najpierw samo złoże, potem 8 sąsiadów
        candidates = [ore_pos] + [
            Position(ore_pos.x + dx, ore_pos.y + dy)
            for dx in range(-1, 2) for dy in range(-1, 2)
            if not (dx == 0 and dy == 0)
        ]

        for nb in candidates:
            if not (0 <= nb.x < map_width and 0 <= nb.y < map_height):
                continue
            if nb in forbidden_tiles:
                continue
            if not ct.is_in_vision(nb):
                continue
            # Dla sąsiednich pól (nie złoża) — nie budujemy na ścianie ani innej rudzie
            if nb != ore_pos:
                nb_env = ct.get_tile_env(nb)
                if nb_env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                    continue
            # Sprawdzamy co stoi — można zastąpić marker lub naszą drogę
            nb_b_id = ct.get_tile_building_id(nb)
            if nb_b_id is not None:
                nb_b_type = ct.get_entity_type(nb_b_id)
                nb_b_team = ct.get_team(nb_b_id)
                if nb_b_type == EntityType.MARKER:
                    if ct.can_destroy(nb):
                        ct.destroy(nb)
                elif nb_b_type == EntityType.ROAD and nb_b_team == my_team:
                    if ct.can_destroy(nb):
                        ct.destroy(nb)
                else:
                    continue  # inny budynek — pomijamy
            if ct.can_place_marker(nb):
                ct.place_marker(nb, self.pack_claim_marker(current_round, ore_pos))
                return

    def run(self, ct: Controller) -> None: # type: ignore
        current_round = ct.get_current_round()
        map_width = ct.get_map_width()
        map_height = ct.get_map_height()
        my_team = ct.get_team()
        enemy_team = Team.B if my_team == Team.A else Team.A
        scale = ct.get_scale_percent() / 100.0
        my_tit, my_ax = ct.get_global_resources()
        etype = ct.get_entity_type()
        my_pos = ct.get_position()
        my_id = ct.get_id()

        # ==========================================
        # 1. LOGIKA BAZY (CORE) 
        # ==========================================
        if etype == EntityType.CORE:
            # PROTOKÓŁ ROZRUCHOWY — jednorazowo
            if not self.starting_protocol:
                found_walls = []
                found_ores = []

                for pos in ct.get_nearby_tiles():
                    env = ct.get_tile_env(pos)
                    if env == Environment.WALL:
                        found_walls.append((pos, env, None, False))
                    elif env in ORES:
                        found_ores.append((pos, env, None, False))
                
                # Rudy są na końcu, więc .pop() zdejmie je jako pierwsze
                self.core_facts_to_report = found_walls + found_ores
                self.starting_protocol = True
            
            # B) DYREKTYWA SYNAPSA ZERO — markery z odkryciami z protokołu rozruchowego
            if self.core_facts_to_report:
                rep_pos, rep_env, rep_btype, rep_is_enemy = self.core_facts_to_report[-1]
                place_pos = None
                for adj_pos in ct.get_nearby_tiles(8):
                    if ct.can_place_marker(adj_pos):
                        place_pos = adj_pos
                        break
                if place_pos:
                    ct.place_marker(place_pos, self.pack_map_marker(current_round, rep_pos, rep_env, rep_btype, rep_is_enemy))
                    self.core_facts_to_report.pop()

            # D) REJESTR WROGICH DRÓG PRZY CORE — gdy zniknie droga = sygnał do spawnu zamiennika
            # Skanujemy wszystkie pola w zasięgu distance_sq ≤ 4 od centrum core (otoczka 5×5)
            current_enemy_roads: set[Position] = set()
            core_center_pos = ct.get_position()  # centrum core
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    p = Position(core_center_pos.x + dx, core_center_pos.y + dy)
                    if 0 <= p.x < map_width and 0 <= p.y < map_height:
                        if not ct.is_in_vision(p):
                            continue
                        b_id_p = ct.get_tile_building_id(p)
                        if (b_id_p is not None
                                and ct.get_entity_type(b_id_p) == EntityType.ROAD
                                and ct.get_team(b_id_p) != my_team):
                            current_enemy_roads.add(p)

            # Drogi które były w rejestrze a teraz zniknęły = zniszczone (autodestrukcja bota)
            destroyed_roads = self.enemy_roads_near_core - current_enemy_roads
            self.enemy_roads_near_core = current_enemy_roads

            # C) PRODUKCJA BOTÓW 
            number_of_bots_to_spawn = 3 # dostosowujemy skalę spawnu do wielkości mapy - dopracować obliczenie optymalnej liczby botów
            # PLUS boty specjalne od tury 300 co 12 tur, max 15 botów
            if ct.get_action_cooldown() == 0:
                if self.replacement_bots_pending > 0:
                    spawn_pos = ct.get_position().add(random.choice(DIRECTIONS))
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        self.replacement_bots_pending -= 1
                        self.spawned_bots_count += 1
                elif current_round >= 150 and (current_round - 150) % 12 == 0 and self.spawned_bots_count < 20:
                    # Bot specjalny — typ wyznaczany przez numer iteracji modulo 5
                    spawn_pos = ct.get_position().add(random.choice(DIRECTIONS))
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        self.bot_late_spawn_index += 1
                        self.spawned_bots_count += 1
                elif self.spawned_bots_count < number_of_bots_to_spawn:
                    spawn_pos = ct.get_position().add(random.choice(DIRECTIONS))
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        self.spawned_bots_count += 1
            return

            if current_round % 50 == 0 and number_of_bots_to_spawn < 4:
                number_of_bots_to_spawn += 1

            # Zamiana Axionite na Titanium
            if ct.get_

        # ==========================================
        # 2. LOGIKA SENTINELA
        # ==========================================
        elif etype == EntityType.SENTINEL:
            # Sentinel strzela gdy ma amunicję, cooldown = 0.
            # Priorytet celów: 1. boty wroga, 2. budynki wroga (nie drogi), 3. drogi wroga.
            # NIE strzelamy gdy cel stoi na naszym conveyorze/moście/splitterze.
            if ct.get_action_cooldown() == 0 and ct.get_ammo_amount() > 0:
                my_dir = ct.get_direction()

                def _sentinel_can_fire(target_pos):
                    b_id_on_target = ct.get_tile_building_id(target_pos)
                    b_team = ct.get_team(b_id_on_target)
                    if (b_id_on_target is not None
                            and b_team == my_team
                            and ct.get_entity_type(b_id_on_target) in NETWORK):
                        return False
                    
                    # Nie strzelamy w harvestera, z którego się zasilamy
                    if ct.get_entity_type(b_id_on_target) == EntityType.HARVESTER and b_team == enemy_team:
                        if my_pos.distance_squared(target_pos) == 1:
                            direction_to_harvester = my_pos.direction_to(target_pos)
                            if my_dir != direction_to_harvester:
                                return False
                    return ct.can_fire(target_pos)

                fired = False
                # Prio 1: boty wroga
                for nearby_id in ct.get_nearby_entities():
                    if ct.get_entity_type(nearby_id) != EntityType.BUILDER_BOT:
                        continue
                    if ct.get_team(nearby_id) != enemy_team:
                        continue
                    target_pos = ct.get_position(nearby_id)
                    if _sentinel_can_fire(target_pos):
                        ct.fire(target_pos)
                        fired = True
                        break
                # Prio 2: budynki wroga (nie drogi, nie markery), ale nie strzelamy w harvestera obok wieżyczki
                if not fired:
                    
                    for nearby_id in ct.get_nearby_entities():
                        if ct.get_entity_type(nearby_id) == EntityType.MARKER:
                            continue
                        if ct.get_team(nearby_id) != enemy_team:
                            continue
                        if ct.get_entity_type(nearby_id) not in BUILDINGS_PRIO2:
                            continue
                        target_pos = ct.get_position(nearby_id)
                        if _sentinel_can_fire(target_pos):
                            ct.fire(target_pos)
                            fired = True
                            break
                # Prio 3: drogi wroga
                if not fired:
                    for nearby_id in ct.get_nearby_entities():
                        if ct.get_entity_type(nearby_id) != EntityType.ROAD:
                            continue
                        if ct.get_team(nearby_id) != enemy_team:
                            continue
                        target_pos = ct.get_position(nearby_id)
                        if _sentinel_can_fire(target_pos):
                            ct.fire(target_pos)
                            break

        # ==========================================
        # 3. LOGIKA PROBY (BUILDER_BOT)
        # ==========================================
        elif etype == EntityType.BUILDER_BOT:
            
            # INICJALIZACJA PAMIĘCI
            if self.bot_state is None:
                
                # TURA I HP
                self.spawn_round = current_round
                self.repairman_prev_hp = ct.get_hp()

                # Początkowy stan — zależy od tury spawnu
                if current_round < 2:
                    self.bot_state = BotState.BUILD_BUNKER
                    self.target = Position(map_width // 2, map_height // 2)
                elif current_round in (8, 9):
                    self.bot_state = BotState.ROAD_LAYER
                elif current_round == 50:
                    self.bot_state = BotState.FORTIFIER
                elif current_round >= 150:
                    # Typ bota wyznaczany z tury spawnu modulo 4 (bez pamięci współdzielonej)
                    type_index = ((current_round - 150) // 12) % 6
                    self.bot_state = LATE_STATES[type_index]
                else:
                    self.bot_state = BotState.EXPLORE
                
                
            
            
            # ==========================================
            # 1. SKANOWANIE I AKTUALIZACJA MAPY W PAMIĘCI
            # ==========================================
            for pos in ct.get_nearby_tiles():
                # 1. PAMIĘĆ STATYCZNA (Teren - to się nigdy nie zmienia)
                if pos not in self.memory:
                    env = ct.get_tile_env(pos)
                    if env in HARD_OBSTACLES:
                        self.memory[pos] = env
                        # Jeśli to ważne odkrycie (ściana lub ruda), dodajemy do VIP Facts
                        if env in ORES:
                            self.vip_facts[pos] = (env, None, False)
                    
                # 2. PAMIĘĆ DYNAMICZNA i ODCZYT FEROMONÓW (BUDYNKI + MARKERY)
                b_id = ct.get_tile_building_id(pos)
                if b_id is not None:
                    # Ktoś tu coś zbudował (lub budynek nadal stoi) -> Nadpisujemy
                    b_type = ct.get_entity_type(b_id)
                    b_team = ct.get_team(b_id)
                    self.buildings[pos] = (b_type, b_team, current_round)
                    
                    # >>> Zapisujemy kafelki naszej bazy (widzimy je zaraz po spawnie) <<<
                    if b_type == EntityType.CORE and b_team == my_team:
                        self.allied_core_tiles.add(pos)
                    # >>> Zapisujemy nasze Splittery wokół bazy <<<
                    if b_type == EntityType.SPLITTER and b_team == my_team:
                        self.allied_splitter_tiles.add(pos)

                    # --- KTO WCHODZI NA LISTĘ VIP? ---
                    # Wyciągamy PRAWDZIWY teren z pamięci (żeby nie nadpisać rudy pustką!)
                    real_env = self.memory.get(pos, ct.get_tile_env(pos))
                    
                    # 1. WSZYSTKIE budynki wroga
                    if b_team == enemy_team:
                        if b_type not in JUNK_ENEMY_BUILDINGS:
                            self.vip_facts[pos] = (real_env, b_type, True)
                    
                    # 2. NASZE strategiczne budynki (Kopalnie, Wieże, Huty)
                    elif b_team == my_team:
                        if b_type in VIP_FRIENDLY:
                            self.vip_facts[pos] = (real_env, b_type, False)

                    # CZY TO NASZ MARKER? (Rozpakowujemy informację)
                    if b_type == EntityType.MARKER and b_team == my_team:
                        marker_val = ct.get_marker_value(b_id)
                        data = self.unpack_marker(marker_val)
                        
                        if data['type'] == 0:  # KANAŁ 0: AKTUALIZACJA MAPY
                            m_pos = data['pos']
                            m_turn = data['turn']
                            
                            # A) Aktualizujemy teren z markera (jeśli go jeszcze nie znamy)
                            if m_pos not in self.memory and data['env'] in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                                self.memory[m_pos] = data['env']
                            
                            # B) Aktualizujemy budynki z markera (Zabezpieczenie Timestampem!)
                            known_b = self.buildings.get(m_pos)
                            last_seen = known_b[2] if known_b else -1
                            
                            if m_turn > last_seen:
                                m_team = enemy_team if data['is_enemy'] else my_team
                                if not data['b_type']: m_team = None
                                self.buildings[m_pos] = (data['b_type'], m_team, m_turn)

                                # --- KOMPLEKSOWA AKTUALIZACJA VIP FACTS ---
                                real_env_marker = self.memory.get(m_pos, data['env'])

                                if data['b_type'] is not None:
                                    # Marker mówi, że ktoś coś tu zbudował
                                    if data['is_enemy']:
                                        if data['b_type'] not in JUNK_ENEMY_BUILDINGS:
                                            self.vip_facts[m_pos] = (real_env_marker, data['b_type'], True)
                                    else:
                                        # To NASZ budynek
                                        if data['b_type'] in VIP_FRIENDLY:
                                            self.vip_facts[m_pos] = (real_env_marker, data['b_type'], False)
                                else:
                                    # Marker mówi, że na polu NIE MA budynku. Czy pod spodem jest ruda?
                                    if data['env'] in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                                        self.vip_facts[m_pos] = (data['env'], None, False)
                                    elif m_pos in self.vip_facts:
                                        # Jeśli to zwykły pusty piach, czyścimy z VIP
                                        del self.vip_facts[m_pos]

                        elif data['type'] == 1:  # KANAŁ 1: REZERWACJA ZŁOŻA
                            # Inny bot zadeklarował, że idzie zająć się tym złożem.
                            # Zapisujemy rezerwację tylko jeśli jest nowsza niż dotychczas znana
                            # ORAZ dotyczy złoża innego niż nasze własne (nie blokujemy sami siebie).
                            ore_p = data['ore_pos']
                            ore_t = data['turn']
                            if ore_p != self.assigned_ore:
                                existing_claim = self.claimed_ores.get(ore_p, -1)
                                if ore_t > existing_claim:
                                    self.claimed_ores[ore_p] = ore_t

                else:
                    # Pole jest PUSTE. Usuwamy z pamięci budynków, jeśli wcześniej był tam jakiś budynek
                    self.buildings[pos] = (None, None, current_round) # Oznaczamy jako puste z aktualnym timestampem
                    
                    if pos in self.vip_facts:
                        # Budynku nie ma. Ale czy pod spodem jest ruda?
                        env_here = self.memory.get(pos, Environment.EMPTY)
                        if env_here in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                            # Zostawiamy/przywracamy informację o samej rudzie
                            self.vip_facts[pos] = (env_here, None, False)
                        else:
                            # To był budynek na pustym polu i został zniszczony. Kasujemy ducha.
                            del self.vip_facts[pos]

            # ==========================================
            # 1.5 GLOBALNE WYLICZENIE ŚRODKA BAZY (DLA WSZYSTKICH STANÓW)
            # ==========================================
            if not self.my_core_center and self.allied_core_tiles:
                core_xs = [p.x for p in self.allied_core_tiles]
                core_ys = [p.y for p in self.allied_core_tiles]
                
                self.my_core_cx = sum(core_xs) // len(core_xs)
                self.my_core_cy = sum(core_ys) // len(core_ys)
                self.my_core_center = Position(self.my_core_cx, self.my_core_cy)

            # ==========================================
            # 2. OBSŁUGA SPLITTERÓW (niezależna od stanu, od tury 100)
            # ==========================================
            # Budowa Foundry (SMELTER) ma pierwszeństwo — Smelter nie przerywa swojej misji
            if current_round >= 100 and self.my_core_center and self.bot_state != BotState.SMELTER:
                
                knight_offsets = [
                    ( 1, -2, Direction.SOUTH),  # NNE  → faces SOUTH
                    ( 2, -1, Direction.WEST),   # ENE  → faces WEST
                    ( 2,  1, Direction.WEST),   # ESE  → faces WEST
                    ( 1,  2, Direction.NORTH),  # SSE  → faces NORTH
                    (-1,  2, Direction.NORTH),  # SSW  → faces NORTH
                    (-2,  1, Direction.EAST),   # WSW  → faces EAST
                    (-2, -1, Direction.EAST),   # WNW  → faces EAST
                    (-1, -2, Direction.SOUTH),  # NNW  → faces SOUTH
                ]
                for ddx, ddy, faces in knight_offsets:
                    sp_pos = Position(self.my_core_cx + ddx, self.my_core_cy + ddy)
                    if not (0 <= sp_pos.x < map_width and 0 <= sp_pos.y < map_height):
                        continue
                    sp_env = self.memory.get(sp_pos, ct.get_tile_env(sp_pos) if ct.is_in_vision(sp_pos) else Environment.EMPTY)
                    if sp_env in HARD_OBSTACLES:
                        continue
                    # Aktualizujemy globalny set delivery tiles
                    self.allied_splitter_tiles.add(sp_pos)
                    # Czy ten Splitter już stoi?
                    if not ct.is_in_vision(sp_pos):
                        continue
                    b_id_sp = ct.get_tile_building_id(sp_pos)
                    already_built = (b_id_sp is not None and ct.get_entity_type(b_id_sp) == EntityType.SPLITTER)
                    if already_built:
                        continue
                    # Brakuje tego Splittera.
                    my_pos = ct.get_position()

                    # Sprawdź czy blokuje go wroga droga
                    enemy_road_blocks_sp = False
                    if ct.is_in_vision(sp_pos):
                        b_id_sp_check = ct.get_tile_building_id(sp_pos)
                        if (b_id_sp_check is not None
                                and ct.get_entity_type(b_id_sp_check) == NETWORK
                                and ct.get_team(b_id_sp_check) != my_team):
                            enemy_road_blocks_sp = True

                    if enemy_road_blocks_sp:
                        # Wroga droga blokuje Splittera — wejdź na nią i dokonaj autodestrukcji
                        if my_pos == sp_pos:
                            if ct.can_fire(sp_pos):
                                ct.fire(sp_pos)
                        else:
                            self.target = sp_pos
                            self.path = []
                        break
                    elif my_pos.distance_squared(sp_pos) <= 2 and ct.get_action_cooldown() == 0:
                        # Splitter (priorytet 3) może zastąpić marker i drogę (priorytety 1, 2)
                        if self.can_replace_with(sp_pos, 3, my_team, ct) and ct.can_destroy(sp_pos):
                            ct.destroy(sp_pos)
                        if ct.can_build_splitter(sp_pos, faces):
                            ct.build_splitter(sp_pos, faces)
                            self.allied_splitter_tiles.add(sp_pos)
                            break
                    elif self.bot_state == BotState.EXPLORE and self.target not in self.allied_core_tiles:
                        # Jesteśmy w EXPLORE i nie idziemy już do Core — wysyłamy się do pola Core
                        # z którego można zbudować ten Splitter
                        for core_tile in self.allied_core_tiles:
                            if core_tile.distance_squared(sp_pos) <= 2:
                                self.target = core_tile
                                self.path = []
                                break
                        break  # Jeden brakujący Splitter na raz wystarczy

            # ==========================================
            # 2b. OBSŁUGA SENTINELI WOKÓŁ CORE (od tury 300)
            # ==========================================
            # Budowa Foundry (SMELTER) ma pierwszeństwo
            if current_round >= 150 and self.my_core_center and self.bot_state != BotState.SMELTER:
                
                sentinel_offsets = [
                    ( 0, -2, Direction.NORTH),   # N
                    ( 2, -2, Direction.NORTHEAST),# NE
                    ( 2,  0, Direction.EAST),     # E
                    ( 2,  2, Direction.SOUTHEAST),# SE
                    ( 0,  2, Direction.SOUTH),    # S
                    (-2,  2, Direction.SOUTHWEST),# SW
                    (-2,  0, Direction.WEST),     # W
                    (-2, -2, Direction.NORTHWEST),# NW
                ]
                for ddx, ddy, facing in sentinel_offsets:
                    sn_pos = Position(self.my_core_cx + ddx, self.my_core_cy + ddy)
                    if not (0 <= sn_pos.x < map_width and 0 <= sn_pos.y < map_height):
                        continue
                    sn_env = self.memory.get(sn_pos, ct.get_tile_env(sn_pos) if ct.is_in_vision(sn_pos) else Environment.EMPTY)
                    if sn_env in HARD_OBSTACLES:
                        continue
                    # Czy ten Sentinel już stoi?
                    if not ct.is_in_vision(sn_pos):
                        continue
                    b_id_sn = ct.get_tile_building_id(sn_pos)
                    already_built = (b_id_sn is not None and ct.get_entity_type(b_id_sn) == EntityType.SENTINEL)
                    if already_built:
                        continue
                    # Brakuje tego Sentinela.
                    # Sprawdź czy blokuje go droga przeciwnika
                    enemy_road_blocks = False
                    if ct.is_in_vision(sn_pos):
                        b_id_sn_check = ct.get_tile_building_id(sn_pos)
                        if (b_id_sn_check is not None
                                and ct.get_entity_type(b_id_sn_check) in NETWORK
                                and ct.get_team(b_id_sn_check) != my_team):
                            enemy_road_blocks = True

                    if enemy_road_blocks:
                        # Droga przeciwnika blokuje — wejdź na nią i dokonaj autodestrukcji.
                        # Builder Bot zadaje 20 damage (droga ma 10 HP) — niszczy ją.
                        if my_pos == sn_pos:
                            if ct.can_fire(sn_pos):
                                ct.fire(sn_pos)  # kończy wykonanie natychmiast
                        else:
                            # Idź dokładnie NA sn_pos (nie obok) — w każdym stanie
                            self.target = sn_pos
                            self.path = []
                        break
                    elif my_pos.distance_squared(sn_pos) <= 2 and ct.get_action_cooldown() == 0:
                        # Sentinel (priorytet 3) może zastąpić marker i drogę (własną)
                        if self.can_replace_with(sn_pos, 3, my_team, ct) and ct.can_destroy(sn_pos):
                            ct.destroy(sn_pos)
                        if ct.can_build_sentinel(sn_pos, facing):
                            ct.build_sentinel(sn_pos, facing)
                            break
                    elif self.bot_state == BotState.EXPLORE and self.target not in self.allied_core_tiles:
                        # W EXPLORE — idź do pola Core obok brakującego Sentinela
                        for core_tile in self.allied_core_tiles:
                            if core_tile.distance_squared(sn_pos) <= 2:
                                self.target = core_tile
                                self.path = []
                                break
                        break  # Jeden brakujący Sentinel na raz wystarczy

            # ==========================================
            # 3. MASZYNA STANÓW (MÓZG) - Decyzje i Akcje
            # ==========================================
            current_state = self.bot_state

            # PRZEJŚCIE ROAD_LAYER → EXPLORE po turze 200
            if current_state == BotState.ROAD_LAYER and current_round >= 200:
                self.bot_state = BotState.EXPLORE
                self.target = None
                self.path = []
                current_state = BotState.EXPLORE

            # PO TURZE 400: istniejące boty (spawnione przed 400) przechodzą w REPAIRMAN
            # — ale tylko gdy są w stanach "wolnych" (nie przerywamy aktywnych misji)
            IDLE_STATES = {BotState.ROAD_LAYER}
            if (current_round >= 200
                    and current_state in IDLE_STATES
                    and self.spawn_round < 200):
                self.bot_state = BotState.REPAIRMAN
                self.target = None
                self.path = []
                current_state = BotState.REPAIRMAN

            # PRIORYTET: pending_splitter — bot zapamiętał w poprzedniej turze że musi
            # zbudować Splitter (nie mógł tego zrobić razem z mostem — osobny cooldown).
            # Obsługujemy to przed całą resztą maszyny stanów.
            if self.pending_splitter is not None:
                pend_pos, pend_dir = self.pending_splitter
                # Sprawdzamy czy Splitter już stoi (inny bot mógł go zbudować)
                b_id_pend = ct.get_tile_building_id(pend_pos) if ct.is_in_vision(pend_pos) else None
                if b_id_pend is not None and ct.get_entity_type(b_id_pend) == EntityType.SPLITTER:
                    # Już stoi — czyścimy i działamy normalnie
                    self.pending_splitter = None
                elif ct.get_action_cooldown() == 0 and my_pos.distance_squared(pend_pos) <= 2:
                    # Niszczymy co stoi na polu (marker nasz/wrogi, droga)
                    if ct.can_destroy(pend_pos):
                        ct.destroy(pend_pos)
                    if ct.can_build_splitter(pend_pos, pend_dir):
                        ct.build_splitter(pend_pos, pend_dir)
                        self.allied_splitter_tiles.add(pend_pos)
                        self.pending_splitter = None
                    # Jeśli build się nie udał — NIE czyścimy pending, spróbujemy w następnej turze
                else:
                    # Za daleko lub cooldown > 0 — idź do pend_pos
                    if self.target != pend_pos:
                        self.target = pend_pos
                        self.path = []
            
            elif current_state == BotState.ROAD_LAYER:
                # Wczesny zwiadowca-drogowiec (tury 1–199):
                # biega losowo po mapie i kładzie drogi na pustych polach
                # oraz na markerach (własnych i przeciwnika).
                # Gdy w zasięgu wzroku jest złoże rudy, nadaje mu priorytet
                # i stara się obudować je drogą dookoła (blokada dostępu dla wroga).
                # Budowanie drogi (nie obudowywanie) wymaga >= 200 Tytanu.

                has_titanium = my_tit > 1.2 * HARVESTER_BASE_COST[0]

                # --- PRIORYTET: obudowywanie złóż widzianych w tym momencie ---
                # (nie wymaga limitu surowcowego)
                ore_fence_target = None
                for ore_pos, (ore_env, ore_btype, _) in self.vip_facts.items():
                    if ore_env not in ORES:
                        continue
                    if not ct.is_in_vision(ore_pos):
                        continue

                    # Sprawdzamy samo złoże — czy ma już drogę lub harvester?
                    # Jeśli nie, dodajemy jako kandydata (droga na złożu = "rezerwacja")
                    ore_b_id = ct.get_tile_building_id(ore_pos)
                    if ore_b_id is None or ct.get_entity_type(ore_b_id) == EntityType.MARKER:
                        # Brak drogi/harvestera na złożu — to kandydat
                        if ore_fence_target is None or my_pos.distance_squared(ore_pos) < my_pos.distance_squared(ore_fence_target):
                            ore_fence_target = ore_pos

                    # Sprawdzamy wszystkich 8 sąsiadów złoża
                    for dx in range(-1, 2):
                        for dy in range(-1, 2):
                            if dx == 0 and dy == 0:
                                continue
                            nb = Position(ore_pos.x + dx, ore_pos.y + dy)
                            if not (0 <= nb.x < map_width and 0 <= nb.y < map_height):
                                continue
                            nb_env = self.memory.get(nb, ct.get_tile_env(nb) if ct.is_in_vision(nb) else Environment.EMPTY)
                            if nb_env in HARD_OBSTACLES:
                                continue
                            if not ct.is_in_vision(nb):
                                continue
                            nb_b_id = ct.get_tile_building_id(nb)
                            if nb_b_id is not None:
                                nb_b_type = ct.get_entity_type(nb_b_id)
                                if nb_b_type in [EntityType.ROAD, EntityType.HARVESTER]:
                                    continue
                                PROTECTED = {EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR,
                                             EntityType.BRIDGE, EntityType.SPLITTER,
                                             EntityType.FOUNDRY, EntityType.BARRIER,
                                             EntityType.GUNNER, EntityType.SENTINEL,
                                             EntityType.BREACH, EntityType.LAUNCHER}
                                if ct.get_team(nb_b_id) == my_team and nb_b_type in PROTECTED:
                                    continue
                                if nb_b_type != EntityType.MARKER:
                                    continue
                            if ore_fence_target is None or my_pos.distance_squared(nb) < my_pos.distance_squared(ore_fence_target):
                                ore_fence_target = nb

                if ore_fence_target is not None:
                    # Obudowujemy złoże — cel nadpisany, limit surowcowy nie obowiązuje
                    if self.target != ore_fence_target:
                        self.target = ore_fence_target
                        self.path = []
                elif has_titanium:
                    # Mamy surowce — losowy zwiad z kładzeniem drogi
                    target_pos = self.target
                    target_is_wall = (target_pos and
                        self.memory.get(target_pos) in
                        HARD_OBSTACLES)
                    if not target_pos or my_pos == target_pos or target_is_wall:
                        self.target = Position(
                            random.randint(0, map_width - 1),
                            random.randint(0, map_height - 1)
                        )
                        self.path = []
                else:
                    # Za mało surowców — zwykły eksplorer (losowy ruch, bez kładzenia drogi)
                    target_pos = self.target
                    target_is_wall = (target_pos and
                        self.memory.get(target_pos) in
                        HARD_OBSTACLES)
                    if not target_pos or my_pos == target_pos or target_is_wall:
                        self.target = Position(
                            random.randint(0, map_width - 1),
                            random.randint(0, map_height - 1)
                        )
                        self.path = []

                # --- AKCJA: kładziemy drogę NA POLU POD BOTEM lub NA ZŁOŻU ---
                # Dozwolone zawsze przy obudowywaniu złoża (ore_fence_target != None),
                # przy zwykłym zwiadzie tylko jeśli has_titanium.
                if ct.get_action_cooldown() == 0 and (ore_fence_target is not None or has_titanium):
                    # Jeśli celem jest samo złoże i jesteśmy obok — budujemy na złożu
                    build_road_pos = my_pos
                    if (ore_fence_target is not None
                            and ore_fence_target in self.vip_facts
                            and self.vip_facts[ore_fence_target][0] in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]
                            and my_pos.distance_squared(ore_fence_target) <= 2
                            and my_pos != ore_fence_target):
                        build_road_pos = ore_fence_target

                    tile_b_id = ct.get_tile_building_id(build_road_pos)
                    can_lay_road = False
                    if tile_b_id is None:
                        can_lay_road = True
                    else:
                        tb_type = ct.get_entity_type(tile_b_id)
                        if tb_type == EntityType.MARKER:
                            if ct.can_destroy(build_road_pos):
                                ct.destroy(build_road_pos)
                            can_lay_road = True
                    if can_lay_road and ct.can_build_road(build_road_pos):
                        ct.build_road(build_road_pos)

            elif current_state == BotState.KAMIKAZE:
                # ==========================================
                # KAMIKAZE: stawia Sentinela przy wrogim harvesterze lub dokonuje autodestrukcji
                # ==========================================
                # Szukamy celu — wrogi harvester
                target_pos = self.target
                if not target_pos or current_round % 10 == 0:
                    best_enemy_harv = None
                    best_dist = float('inf')
                    for pos, (env, b_type, is_enemy) in self.vip_facts.items():
                        if b_type == EntityType.HARVESTER and is_enemy:
                            d = my_pos.distance_squared(pos)
                            if d < best_dist:
                                best_dist = d
                                best_enemy_harv = pos
                    if best_enemy_harv:
                        if self.target != best_enemy_harv:
                            self.target = best_enemy_harv
                            self.path = []
                            self.kamikaze_sentinel_pos = None
                            self.kamikaze_sentinel_dir = None
                    else:
                        # Brak wroga w pamięci. Przechodzimy w tryb aktywnego szukania (zwiad).
                        target_is_wall = (self.target and self.memory.get(self.target) in HARD_OBSTACLES)
                        
                        # Losujemy nowy cel, jeśli nie mamy żadnego, jeśli dotarliśmy na miejsce, lub jeśli cel to ściana
                        if not self.target or my_pos == self.target or target_is_wall:
                            self.target = Position(
                                random.randint(0, map_width - 1),
                                random.randint(0, map_height - 1)
                            )
                            self.path = []
                            self.kamikaze_sentinel_pos = None
                            self.kamikaze_sentinel_dir = None

                if self.target and self.bot_state == BotState.KAMIKAZE:
                    harv_pos = self.target
                    # Cel bota to sąsiednie pole przy harvesterze (nie sam harvester — nie można wejść)
                    at_harv = my_pos.distance_squared(harv_pos) <= 2 and ct.is_in_vision(harv_pos)
                    if at_harv:
                        if self.kamikaze_sentinel_pos is None:
                            # Znajdź stronę sieci wroga
                            network_dir = None
                            enemy_network_pos = None
                            for d in ORTHOGONAL_DIRECTIONS:
                                nb = harv_pos.add(d)
                                if not ct.is_in_vision(nb):
                                    continue
                                nb_b_id = ct.get_tile_building_id(nb)
                                if nb_b_id is None:
                                    continue
                                nb_bt = ct.get_entity_type(nb_b_id)
                                if (ct.get_team(nb_b_id) == enemy_team and
                                        nb_bt in NETWORK):
                                    network_dir = d
                                    enemy_network_pos = nb
                                    break
                            if network_dir is not None:
                                # Szukamy pola prostopadłego do sieci wroga
                                perp_dirs = [d for d in ORTHOGONAL_DIRECTIONS if d != network_dir and d != network_dir.opposite()]
                                sentinel_placed = False
                                for pdir in perp_dirs:
                                    sp = harv_pos.add(pdir)
                                    if not (0 <= sp.x < map_width and 0 <= sp.y < map_height):
                                        continue
                                    if not ct.is_in_vision(sp):
                                        continue
                                    sp_env = ct.get_tile_env(sp)
                                    if sp_env in HARD_OBSTACLES:
                                        continue
                                    sp_b_id = ct.get_tile_building_id(sp)
                                    if sp_b_id is not None:
                                        sp_bt = ct.get_entity_type(sp_b_id)
                                        sp_team = ct.get_team(sp_b_id)
                                        if sp_bt == EntityType.MARKER:
                                            pass  # można zastąpić
                                        elif sp_bt == EntityType.ROAD and sp_team == my_team:
                                            pass  # nasza droga — można zastąpić
                                        else:
                                            continue
                                    # Kierunek SKOŚNY: kombinacja pdir (prostopadły) i network_dir
                                    # np. sieć od N, sentinel na E → facing = NE
                                    # Wyznaczamy: obracamy network_dir w stronę pdir
                                    # Jeśli pdir to rotacja_right(network_dir) → facing = network_dir.rotate_right()
                                    # Jeśli pdir to rotacja_left(network_dir) → facing = network_dir.rotate_left()
                                    if pdir == network_dir.rotate_right():
                                        facing_diag = network_dir.rotate_right()
                                    else:
                                        facing_diag = network_dir.rotate_left()
                                    self.kamikaze_sentinel_pos = sp
                                    self.kamikaze_sentinel_dir = facing_diag
                                    sentinel_placed = True
                                    break
                                if not sentinel_placed:
                                    # Brak miejsca na sentinela — wejdź na sieć wroga i atakuj
                                    if enemy_network_pos and my_pos == enemy_network_pos:
                                        if ct.can_fire(enemy_network_pos):
                                            ct.fire(enemy_network_pos)
                                    elif enemy_network_pos:
                                        self.target = enemy_network_pos
                                        self.path = []
                            else:
                                # Nie ma sieci wroga — szukamy nowego celu
                                self.target = None
                                self.kamikaze_sentinel_pos = None

                        # Buduj sentinela jeśli mamy obliczoną pozycję
                        spos = self.kamikaze_sentinel_pos
                        sdir = self.kamikaze_sentinel_dir
                        if spos is not None and sdir is not None:
                            if my_pos.distance_squared(spos) <= 2 and ct.get_action_cooldown() == 0:
                                sb_id = ct.get_tile_building_id(spos) if ct.is_in_vision(spos) else None
                                if sb_id is not None:
                                    sb_bt = ct.get_entity_type(sb_id)
                                    if sb_bt in {EntityType.MARKER, EntityType.ROAD} and ct.can_destroy(spos):
                                        ct.destroy(spos)
                                if ct.can_build_sentinel(spos, sdir):
                                    ct.build_sentinel(spos, sdir)
                                    # Misja zakończona
                                    self.bot_state = BotState.KAMIKAZE
                                    self.target = None
                                    self.kamikaze_sentinel_pos = None
                            elif my_pos.distance_squared(spos) > 2:
                                # Idź do pozycji sentinela
                                self.target = spos
                                self.path = []

            elif current_state == BotState.REPAIRMAN:
                # ==========================================
                # REPAIRMAN: leczy uszkodzone elementy sieci, naprawia przerwy.
                # Gdy otrzyma obrażenia — ucieka, stawia markery alarmowe przy core, wraca.
                # ==========================================

                # --- DETEKCJA OBRAŻEŃ ---
                current_hp = ct.get_hp()
                prev_hp = self.repairman_prev_hp
                if current_hp < prev_hp:
                    # Otrzymaliśmy obrażenia — zapisz pozycję zagrożenia i uciekaj
                    self.repairman_danger_pos = my_pos
                    self.repairman_flee_turns = 15  # uciekaj przez 15 tur
                    self.repairman_markers_placed = 0
                    self.target = None
                    self.path = []
                self.repairman_prev_hp = current_hp

                # --- TRYB UCIECZKI ---
                flee_turns = self.repairman_flee_turns
                if flee_turns > 0:
                    self.repairman_flee_turns = flee_turns - 1
                    danger_pos = self.repairman_danger_pos
                    # Uciekaj do core (najdalej od danger_pos)
                    if self.allied_core_tiles:
                        core_list = list(self.allied_core_tiles)
                        # Cel: pole core najdalej od danger_pos
                        if danger_pos:
                            flee_target = max(core_list, key=lambda p: p.distance_squared(danger_pos))
                        else:
                            flee_target = random.choice(core_list)
                        if self.target != flee_target:
                            self.target = flee_target
                            self.path = []
                    # Postaw markery alarmowe przy core (do 3 markerów)
                    markers_placed = self.repairman_markers_placed
                    if markers_placed < 3 and danger_pos and ct.get_action_cooldown() == 0:
                        for adj_pos in ct.get_nearby_tiles(2):
                            if ct.can_place_marker(adj_pos):
                                # Kodujemy pozycję zagrożenia w kanale 0 jako wrogi marker
                                ct.place_marker(adj_pos, self.pack_map_marker(
                                    current_round, danger_pos, Environment.EMPTY, EntityType.GUNNER, True))
                                self.repairman_markers_placed = markers_placed + 1
                                break
                else:
                    # --- TRYB NORMALNEJ PRACY ---
                    danger_pos = self.repairman_danger_pos
                    healed_this_turn = False

                    # Priorytet 1: Lecz pobliskie uszkodzone nasze budynki sieci
                    if ct.get_action_cooldown() == 0:
                        for adj_pos in ct.get_nearby_tiles(2):
                            if not ct.is_in_vision(adj_pos):
                                continue
                            b_id_r = ct.get_tile_building_id(adj_pos)
                            if b_id_r is None:
                                continue
                            if ct.get_team(b_id_r) != my_team:
                                continue
                            if ct.get_entity_type(b_id_r) not in NETWORK_TYPES:
                                continue
                            if ct.get_hp(b_id_r) < ct.get_max_hp(b_id_r):
                                if ct.can_heal(adj_pos):
                                    ct.heal(adj_pos)
                                    healed_this_turn = True
                                    break

                    # Priorytet 2: Wykryj i napraw przerwy w sieci (ślepy koniec conveyora/mostu)
                    if not healed_this_turn and ct.get_action_cooldown() == 0:
                        for adj_pos in ct.get_nearby_tiles():
                            if not ct.is_in_vision(adj_pos):
                                continue
                            b_id_r = ct.get_tile_building_id(adj_pos)
                            if b_id_r is None:
                                continue
                            if ct.get_team(b_id_r) != my_team:
                                continue
                            b_type_r = ct.get_entity_type(b_id_r)
                            # Sprawdź conveyor — jego wyjście (pole wskazywane) jest puste?
                            if b_type_r == EntityType.CONVEYOR:
                                try:
                                    out_dir = ct.get_direction(b_id_r)
                                    out_pos = adj_pos.add(out_dir)
                                    if not (0 <= out_pos.x < map_width and 0 <= out_pos.y < map_height):
                                        continue
                                    if not ct.is_in_vision(out_pos):
                                        continue
                                    out_b = ct.get_tile_building_id(out_pos)
                                    out_env = ct.get_tile_env(out_pos)
                                    if out_env in HARD_OBSTACLES:
                                        continue
                                    if out_b is None or (ct.get_entity_type(out_b) == EntityType.MARKER):
                                        # Ślepy koniec — napraw: postaw conveyor z out_pos w kierunku core
                                        if my_pos.distance_squared(out_pos) <= 2:
                                            if out_b is not None and ct.can_destroy(out_pos):
                                                ct.destroy(out_pos)
                                            # Buduj kolejny conveyor w kierunku core
                                            if self.my_core_center:
                                                repair_dir = out_pos.direction_to(Position(self.my_core_cx, self.my_core_cy))
                                                # Upewnij się że to kierunek ortogonalny
                                                for rd in ORTHOGONAL_DIRECTIONS:
                                                    if rd == repair_dir or rd == out_pos.direction_to(Position(ccx, ccy)):
                                                        if ct.can_build_conveyor(out_pos, rd):
                                                            ct.build_conveyor(out_pos, rd)
                                                            healed_this_turn = True
                                                            break
                                        else:
                                            self.target = out_pos
                                            self.path = []
                                        break
                                except Exception:
                                    pass
                            # Sprawdź most — jego target jest pusty lub zniszczony?
                            elif b_type_r == EntityType.BRIDGE:
                                try:
                                    bridge_target = ct.get_bridge_target(b_id_r)
                                    if not ct.is_in_vision(bridge_target):
                                        continue
                                    bt_b = ct.get_tile_building_id(bridge_target)
                                    bt_env = ct.get_tile_env(bridge_target)
                                    if bt_env in HARD_OBSTACLES:
                                        continue
                                    if bt_b is None or (ct.get_entity_type(bt_b) == EntityType.MARKER):
                                        # Most do naprawy — zbuduj conveyor na miejscu lądowania
                                        if my_pos.distance_squared(bridge_target) <= 2:
                                            if bt_b is not None and ct.can_destroy(bridge_target):
                                                ct.destroy(bridge_target)
                                            if self.my_core_center:
                                                repair_dir = bridge_target.direction_to(Position(self.my_core_cx, self.my_core_cy))
                                                for rd in ORTHOGONAL_DIRECTIONS:
                                                    if ct.can_build_conveyor(bridge_target, rd):
                                                        ct.build_conveyor(bridge_target, rd)
                                                        healed_this_turn = True
                                                        break
                                        else:
                                            self.target = bridge_target
                                            self.path = []
                                        break
                                except Exception:
                                    pass

                    # Priorytet 3: Znajdź uszkodzony budynek sieci w zasięgu wzroku
                    if not healed_this_turn:
                        best_repair_pos = None
                        best_repair_dist = float('inf')
                        for adj_pos in ct.get_nearby_tiles():
                            if not ct.is_in_vision(adj_pos):
                                continue
                            b_id_r = ct.get_tile_building_id(adj_pos)
                            if b_id_r is None:
                                continue
                            if ct.get_team(b_id_r) != my_team:
                                continue
                            if ct.get_entity_type(b_id_r) not in NETWORK_TYPES:
                                continue
                            if ct.get_hp(b_id_r) < ct.get_max_hp(b_id_r):
                                d = my_pos.distance_squared(adj_pos)
                                if d < best_repair_dist:
                                    best_repair_dist = d
                                    best_repair_pos = adj_pos
                        if best_repair_pos:
                            if self.target != best_repair_pos:
                                self.target = best_repair_pos
                                self.path = []
                        else:
                            # Priorytet 4: Losowy cel wśród elementów sieci,
                            # preferując kierunek z dala od strefy zagrożenia
                            network_tiles = []
                            for adj_pos in ct.get_nearby_tiles():
                                b_id_r = ct.get_tile_building_id(adj_pos)
                                if b_id_r and ct.get_team(b_id_r) == my_team and ct.get_entity_type(b_id_r) in NETWORK_TYPES:
                                    # Unikaj kierunku zagrożenia
                                    if danger_pos and adj_pos.distance_squared(danger_pos) < my_pos.distance_squared(danger_pos):
                                        continue
                                    network_tiles.append(adj_pos)
                            if not network_tiles:
                                # Jeśli wszystkie są bliżej zagrożenia — weź dowolne
                                for adj_pos in ct.get_nearby_tiles():
                                    b_id_r = ct.get_tile_building_id(adj_pos)
                                    if b_id_r and ct.get_team(b_id_r) == my_team and ct.get_entity_type(b_id_r) in NETWORK_TYPES:
                                        network_tiles.append(adj_pos)
                            if network_tiles:
                                if not self.target or self.target == my_pos:
                                    self.target = random.choice(network_tiles)
                                    self.path = []
                            else:
                                if not self.target or my_pos == self.target:
                                    self.target = Position(
                                        random.randint(0, map_width - 1),
                                        random.randint(0, map_height - 1))
                                    self.path = []

            elif current_state == BotState.FORTIFIER:
                # ==========================================
                # FORTIFIER: obudowuje harvestery Sentinelami skierowanymi na zewnątrz
                # Preferuje nasze harvestery, akceptuje wrogie (parazytycznie)
                # ==========================================
                harv_target = self.fortifier_harvest_target

                # Znajdź nowy cel jeśli brak lub co 15 tur
                if not harv_target or current_round % 15 == 0:
                    best_h = None
                    best_d = float('inf')
                    # Najpierw nasze
                    for pos, (env, b_type, is_enemy) in self.vip_facts.items():
                        if b_type != EntityType.HARVESTER or is_enemy:
                            continue
                        if not ct.is_in_vision(pos):
                            continue
                        # Sprawdź czy jest miejsce na Sentinela
                        has_slot = False
                        for d in ORTHOGONAL_DIRECTIONS:
                            nb = pos.add(d)
                            if not (0 <= nb.x < map_width and 0 <= nb.y < map_height):
                                continue
                            nb_b_id = ct.get_tile_building_id(nb) if ct.is_in_vision(nb) else None
                            if nb_b_id is None:
                                has_slot = True; break
                            nb_bt = ct.get_entity_type(nb_b_id)
                            if nb_bt in {EntityType.MARKER, EntityType.ROAD} and ct.get_team(nb_b_id) == my_team:
                                has_slot = True; break
                        if has_slot:
                            d_val = my_pos.distance_squared(pos)
                            if d_val < best_d:
                                best_d = d_val; best_h = pos
                    # Jeśli nie ma naszych — wrogie
                    if best_h is None:
                        for pos, (env, b_type, is_enemy) in self.vip_facts.items():
                            if b_type != EntityType.HARVESTER or not is_enemy:
                                continue
                            if not ct.is_in_vision(pos):
                                continue
                            has_slot = False
                            for d in ORTHOGONAL_DIRECTIONS:
                                nb = pos.add(d)
                                if not (0 <= nb.x < map_width and 0 <= nb.y < map_height):
                                    continue
                                nb_b_id = ct.get_tile_building_id(nb) if ct.is_in_vision(nb) else None
                                if nb_b_id is None:
                                    has_slot = True; break
                                nb_bt = ct.get_entity_type(nb_b_id)
                                if nb_bt in {EntityType.MARKER, EntityType.ROAD} and ct.get_team(nb_b_id) == my_team:
                                    has_slot = True; break
                            if has_slot:
                                d_val = my_pos.distance_squared(pos)
                                if d_val < best_d:
                                    best_d = d_val; best_h = pos
                    self.fortifier_harvest_target = best_h
                    harv_target = best_h

                if harv_target:
                    if not self.target or self.target == harv_target:
                        self.target = harv_target
                    if my_pos.distance_squared(harv_target) <= 2 and ct.get_action_cooldown() == 0 and ct.is_in_vision(harv_target):
                        # Sprawdź czy to wrogi harvester — jeśli tak, użyj kierunku sieci wroga (jak Kamikaze)
                        harv_b_id = ct.get_tile_building_id(harv_target)
                        is_enemy_harv = harv_b_id is not None and ct.get_team(harv_b_id) == enemy_team

                        if is_enemy_harv:
                            # Znajdź stronę sieci wroga przy tym harvesterze
                            network_dir_f = None
                            for d in ORTHOGONAL_DIRECTIONS:
                                nb = harv_target.add(d)
                                if not (0 <= nb.x < map_width and 0 <= nb.y < map_height): continue
                                if not ct.is_in_vision(nb): continue
                                nb_b = ct.get_tile_building_id(nb)
                                if nb_b and ct.get_team(nb_b) == enemy_team and ct.get_entity_type(nb_b) in {EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.SPLITTER}:
                                    network_dir_f = d; break
                            # Sentinele na polach prostopadłych, celują w network_dir
                            candidate_dirs = [d for d in ORTHOGONAL_DIRECTIONS if d != network_dir_f and d != (network_dir_f.opposite() if network_dir_f else None)]
                        else:
                            network_dir_f = None
                            candidate_dirs = list(ORTHOGONAL_DIRECTIONS)

                        # Buduj Sentinela na PIERWSZYM wolnym polu — tylko jeden per turę
                        built_sentinel = False
                        next_slot = None  # zapamiętaj kolejne pole do którego bot ma iść
                        for d in candidate_dirs:
                            sn = harv_target.add(d)
                            if not (0 <= sn.x < map_width and 0 <= sn.y < map_height): continue
                            if not ct.is_in_vision(sn): continue
                            sn_env = ct.get_tile_env(sn)
                            if sn_env in HARD_OBSTACLES: continue
                            sn_b_id = ct.get_tile_building_id(sn)
                            if sn_b_id is not None:
                                sn_bt = ct.get_entity_type(sn_b_id)
                                sn_team = ct.get_team(sn_b_id)
                                if sn_bt == EntityType.SENTINEL and sn_team == my_team:
                                    continue  # już stoi nasz sentinel
                                if sn_team == my_team and sn_bt not in {EntityType.MARKER, EntityType.ROAD}:
                                    continue  # nie niszczymy cennych budynków
                                if sn_b_id is not None and ct.can_destroy(sn):
                                    ct.destroy(sn)
                            # Wyznacz kierunek sentinela
                            if is_enemy_harv and network_dir_f:
                                facing_out = network_dir_f
                            else:
                                facing_out = d  # od harvestera na zewnątrz
                            if my_pos.distance_squared(sn) <= 2:
                                if ct.can_build_sentinel(sn, facing_out):
                                    ct.build_sentinel(sn, facing_out)
                                    built_sentinel = True
                                    # Ustaw bot_targets na sam harv_target żeby wrócić i zbadać kolejne pola
                                    self.target = harv_target
                                    self.path = []
                                    break
                            else:
                                # Pole istnieje i jest wolne ale bot za daleko — zapamiętaj jako cel ruchu
                                if next_slot is None:
                                    next_slot = sn

                        if not built_sentinel:
                            if next_slot is not None:
                                # Idź do następnego wolnego pola przy harvesterze
                                self.target = next_slot
                                self.path = []
                            else:
                                # Wszystkie pola zajęte lub brak dostępu.
                                # Sprawdź czy to kwestia surowców — jeśli tak, czekaj przy harvesterze
                                if my_tit < SENTINEL_BASE_COST[0]:
                                    # Brak surowców — stój przy harvesterze i czekaj
                                    self.target = harv_target
                                    self.path = []
                                else:
                                    # Naprawdę nie ma gdzie budować — szukaj nowego harvestera
                                    self.fortifier_harvest_target = None
                                    self.target = None
                else:
                    # Brak celu — losowy ruch
                    if not self.target or my_pos == self.target:
                        self.target = Position(
                            random.randint(0, map_width - 1),
                            random.randint(0, map_height - 1))
                        self.path = []

            elif current_state == BotState.SMELTER:
                # ==========================================
                # SMELTER: buduje Foundry i podłącza do sieci
                # ==========================================
                phase = self.smelter_phase

                if phase == 'scan':
                    # Sprawdź czy Foundry już istnieje — fizycznie w zasięgu lub w vip_facts
                    foundry_exists = False
                    existing_foundry_pos = None
                    for pos, (env, b_type, is_enemy) in self.vip_facts.items():
                        if b_type == EntityType.FOUNDRY and not is_enemy:
                            foundry_exists = True
                            existing_foundry_pos = pos
                            break
                    # Sprawdź też bezpośrednio w zasięgu wzroku
                    if not foundry_exists:
                        for adj_pos in ct.get_nearby_tiles():
                            b_id_f = ct.get_tile_building_id(adj_pos)
                            if b_id_f and ct.get_team(b_id_f) == my_team and ct.get_entity_type(b_id_f) == EntityType.FOUNDRY:
                                foundry_exists = True
                                existing_foundry_pos = adj_pos
                                break
                    if foundry_exists:
                        # Foundry już istnieje — podłącz się do niego zamiast budować nowe
                        self.smelter_foundry_pos = existing_foundry_pos
                        self.smelter_phase = 'connect'
                        self.target = None
                        self.path = []
                    else:
                        # Skanuj zasoby w sieci
                        ti_src = None
                        ax_src = None
                        for adj_pos in ct.get_nearby_tiles():
                            b_id_s = ct.get_tile_building_id(adj_pos)
                            if b_id_s is None:
                                continue
                            if ct.get_team(b_id_s) != my_team:
                                continue
                            if ct.get_entity_type(b_id_s) not in NETWORK_TYPES_S:
                                continue
                            try:
                                res = ct.get_stored_resource(b_id_s)
                            except Exception:
                                continue
                            if res == ResourceType.TITANIUM and ti_src is None:
                                ti_src = adj_pos
                            elif res == ResourceType.RAW_AXIONITE and ax_src is None:
                                ax_src = adj_pos
                        if ti_src:
                            self.smelter_titanium_src = ti_src
                        if ax_src:
                            self.smelter_axionite_src = ax_src

                        # Jeśli mamy obie rudy w zasięgu i jesteśmy blisko core — szukaj miejsca
                        if self.smelter_titanium_src and self.smelter_axionite_src:
                            self.smelter_phase = 'build'
                        elif self.allied_core_tiles:
                            # Idź do core żeby lepiej skanować
                            core_center = list(self.allied_core_tiles)[len(self.allied_core_tiles)//2]
                            if not self.target:
                                self.target = core_center
                                self.path = []
                            elif my_pos.distance_squared(core_center) <= 9:
                                # Przy core ale brak obu ruda — czekaj i skanuj
                                pass

                elif phase == 'build':
                    # Znajdź optymalne miejsce na Foundry blisko core
                    if not self.smelter_foundry_pos:
                        ti_src = self.smelter_titanium_src
                        ax_src = self.smelter_axionite_src
                        best_fpos = None
                        best_score = float('inf')
                        if self.my_core_center:
                            # Oblicz pola wejściowe splitterów — Foundry NIE może tam stanąć
                            KNIGHT_OFFSETS_FP = [
                                ( 1,-2, Direction.SOUTH), ( 2,-1, Direction.WEST),
                                ( 2, 1, Direction.WEST),  ( 1, 2, Direction.NORTH),
                                (-1, 2, Direction.NORTH), (-2, 1, Direction.EAST),
                                (-2,-1, Direction.EAST),  (-1,-2, Direction.SOUTH),
                            ]
                            splitter_input_positions: set[Position] = set()
                            for ddx, ddy, sp_faces in KNIGHT_OFFSETS_FP:
                                sp = Position(self.my_core_cx + ddx, self.my_core_cy + ddy)
                                splitter_input_positions.add(sp.add(sp_faces.opposite()))
                            for dx in range(-5, 6):
                                for dy in range(-5, 6):
                                    fp = Position(self.my_core_cx + dx, self.my_core_cy + dy)
                                    if not (0 <= fp.x < map_width and 0 <= fp.y < map_height):
                                        continue
                                    fp_env = self.memory.get(fp, Environment.EMPTY)
                                    if fp_env in HARD_OBSTACLES:
                                        continue
                                    if fp in self.allied_core_tiles:
                                        continue
                                    # Nie stawiamy Foundry na polu wejściowym Splittera
                                    if fp in splitter_input_positions:
                                        continue
                                    # Nie stawiamy Foundry na pozycji Splittera
                                    if fp in self.allied_splitter_tiles:
                                        continue
                                    d_core = fp.distance_squared(Position(ccx, ccy))
                                    d_ti = fp.distance_squared(ti_src) if ti_src else 999
                                    d_ax = fp.distance_squared(ax_src) if ax_src else 999
                                    score = d_core + d_ti + d_ax
                                    if score < best_score:
                                        best_score = score
                                        best_fpos = fp
                        self.smelter_foundry_pos = best_fpos

                    fpos = self.smelter_foundry_pos
                    if fpos:
                        if self.target != fpos:
                            self.target = fpos
                            self.path = []
                        if my_pos.distance_squared(fpos) <= 2 and ct.get_action_cooldown() == 0:
                            # Niszczymy co stoi TYLKO jeśli stać nas na Foundry
                            foundry_ti, foundry_ax = FOUNDRY_BASE_COST
                            can_afford_foundry = (my_tit >= foundry_ti and my_ax >= foundry_ax)
                            f_b_id = ct.get_tile_building_id(fpos) if ct.is_in_vision(fpos) else None
                            if f_b_id is not None and can_afford_foundry and ct.can_destroy(fpos):
                                ct.destroy(fpos)
                            if ct.can_build_foundry(fpos):
                                ct.build_foundry(fpos)
                                self.smelter_phase = 'connect'
                                self.target = None

                elif phase == 'connect':
                    fpos = self.smelter_foundry_pos
                    if not fpos:
                        self.bot_state = BotState.REPAIRMAN
                    else:
                        if not self.target or my_pos == self.target:
                            self.target = fpos
                            self.path = []
                        if my_pos.distance_squared(fpos) <= 2 and ct.get_action_cooldown() == 0 and ct.is_in_vision(fpos):
                            # Sprawdź podłączenia sąsiadów Foundry
                            # Sąsiad jest podłączony jeśli:
                            #   - sąsiad jest conveyorem/splitterem naszym wskazującym NA fpos, LUB
                            #   - sąsiad jest mostem naszym z bridge_target == fpos
                            connected_in = 0
                            has_output = False
                            for d in ORTHOGONAL_DIRECTIONS:
                                nb = fpos.add(d)
                                if not (0 <= nb.x < map_width and 0 <= nb.y < map_height): continue
                                if not ct.is_in_vision(nb): continue
                                nb_b = ct.get_tile_building_id(nb)
                                if nb_b is None: continue
                                if ct.get_team(nb_b) != my_team: continue
                                nb_bt = ct.get_entity_type(nb_b)
                                if nb_bt == EntityType.CONVEYOR:
                                    try:
                                        if nb.add(ct.get_direction(nb_b)) == fpos:
                                            connected_in += 1
                                    except Exception: pass
                                elif nb_bt == EntityType.BRIDGE:
                                    try:
                                        if ct.get_bridge_target(nb_b) == fpos:
                                            connected_in += 1
                                    except Exception: pass
                                elif nb_bt == EntityType.SPLITTER:
                                    connected_in += 1  # splitter rozdziela, liczymy
                                # Wyjście: conveyor z fpos wskazuje NA sąsiada
                            # Sprawdź wyjście — conveyor zbudowany NA fpos (pole Foundry)
                            # lub sąsiad który przyjmuje zasoby z fpos
                            fpos_b = ct.get_tile_building_id(fpos)
                            if fpos_b and ct.get_entity_type(fpos_b) == EntityType.FOUNDRY:
                                has_output = True  # Foundry samo wychodzi na wszystkich sąsiadów

                            if connected_in >= 2:
                                # Mamy dwa wejścia — przechodzimy do fortyfikacji
                                self.smelter_phase = 'fortify'
                                self.target = None
                            else:
                                # Brakuje wejść — buduj most z wyjściem NA fpos
                                # Szukamy elementu sieci z Ti lub Ax w zasięgu mostu (dist_sq <= 9 od fpos)
                                ti_src = self.smelter_titanium_src
                                ax_src = self.smelter_axionite_src
                                for src_pos in [ti_src, ax_src]:
                                    if src_pos is None: continue
                                    # Sprawdź czy już jest połączony
                                    already = False
                                    for d in ORTHOGONAL_DIRECTIONS:
                                        nb = fpos.add(d)
                                        if not (0 <= nb.x < map_width and 0 <= nb.y < map_height): continue
                                        if not ct.is_in_vision(nb): continue
                                        nb_b = ct.get_tile_building_id(nb)
                                        if nb_b and ct.get_team(nb_b) == my_team:
                                            nb_bt = ct.get_entity_type(nb_b)
                                            if nb_bt == EntityType.CONVEYOR:
                                                try:
                                                    if nb.add(ct.get_direction(nb_b)) == fpos:
                                                        already = True; break
                                                except Exception: pass
                                            elif nb_bt == EntityType.BRIDGE:
                                                try:
                                                    if ct.get_bridge_target(nb_b) == fpos:
                                                        already = True; break
                                                except Exception: pass
                                    if already: continue
                                    # Buduj most z src_pos z target=fpos jeśli dist <= 9
                                    if src_pos.distance_squared(fpos) <= 9:
                                        if my_pos.distance_squared(src_pos) <= 2:
                                            sb = ct.get_tile_building_id(src_pos)
                                            if sb and ct.can_destroy(src_pos): ct.destroy(src_pos)
                                            if ct.can_build_bridge(src_pos, fpos):
                                                ct.build_bridge(src_pos, fpos)
                                                break
                                        else:
                                            self.target = src_pos
                                            self.path = []
                                    else:
                                        # Za daleko na most — buduj conveyor krok po kroku (uproszczone)
                                        if my_pos.distance_squared(src_pos) <= 2:
                                            d_to_fpos = src_pos.direction_to(fpos)
                                            if ct.can_build_conveyor(src_pos, d_to_fpos):
                                                ct.build_conveyor(src_pos, d_to_fpos)
                                        else:
                                            self.target = src_pos
                                            self.path = []

                elif phase == 'fortify':
                    # Problem 6: ufortyfikuj Foundry Sentinelami z wolnych stron
                    fpos = self.smelter_foundry_pos
                    if not fpos:
                        self.bot_state = BotState.REPAIRMAN
                    else:
                        if not self.target or my_pos == self.target:
                            self.target = fpos
                            self.path = []
                        if my_pos.distance_squared(fpos) <= 2 and ct.get_action_cooldown() == 0 and ct.is_in_vision(fpos):
                            map_center = Position(map_width // 2, map_height // 2)
                            built = False
                            next_fort_slot = None
                            for d in ORTHOGONAL_DIRECTIONS:
                                sn = fpos.add(d)
                                if not (0 <= sn.x < map_width and 0 <= sn.y < map_height): continue
                                if not ct.is_in_vision(sn): continue
                                sn_env = ct.get_tile_env(sn)
                                if sn_env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]: continue
                                sn_b = ct.get_tile_building_id(sn)
                                if sn_b is not None:
                                    sn_bt = ct.get_entity_type(sn_b)
                                    sn_team = ct.get_team(sn_b)
                                    if sn_bt == EntityType.SENTINEL and sn_team == my_team: continue
                                    if sn_team == my_team and sn_bt in {EntityType.MARKER, EntityType.ROAD}:
                                        if ct.can_destroy(sn): ct.destroy(sn)
                                    else:
                                        continue
                                # Facing: od Foundry w kierunku środka mapy z tej strony
                                facing_f = d
                                if my_pos.distance_squared(sn) <= 2:
                                    if ct.can_build_sentinel(sn, facing_f):
                                        ct.build_sentinel(sn, facing_f)
                                        self.target = fpos
                                        self.path = []
                                        built = True
                                        break
                                else:
                                    if next_fort_slot is None:
                                        next_fort_slot = sn
                            if not built:
                                if next_fort_slot:
                                    self.target = next_fort_slot
                                    self.path = []
                                else:
                                    # Foundry ufortyfikowane — zostań Repairmanem
                                    self.bot_state = BotState.REPAIRMAN
                                    self.target = None

            elif current_state == BotState.EXPLORE:
                found_ore_pos = None
                if not self.target or current_round % 2 == 0: # było co 5
                    # Szuka pustej rudy, pomijając złoża zarezerwowane przez innych botów
                    # (rezerwacja ważna przez 20 tur od ostatniego odczytu markera).
                    CLAIM_TTL = 20
                    candidates = {}
                    

                    for pos, (env, b_type, is_enemy) in self.vip_facts.items():
                        if env not in ORES:
                            continue
                        if b_type is not None:
                            continue  # złoże już zajęte (harvester lub inny budynek)
                        # Pomijamy złoża zarezerwowane przez kogoś innego
                        claim_turn = self.claimed_ores.get(pos, -1)
                        if claim_turn >= 0 and (current_round - claim_turn) < CLAIM_TTL:
                            continue
                        candidates[pos] = my_pos.distance_squared(pos)
                    if candidates:
                        found_ore_pos = min(candidates, key=candidates.get)

                if found_ore_pos is not None:
                    self.bot_state = BotState.BUILD_MINE
                    self.target = found_ore_pos
                    self.path = []
                    self.assigned_ore = found_ore_pos
                    self.bot_mine_since = current_round
                        
                # Jeśli nadal eksploruje i nie ma celu (lub dotarł do celu), losuje nowy.
                # Wyjątek: jeśli cel jest polem Core, bot jest tam żeby zbudować Splitter
                # — nie resetuj celu, sekcja Splitterów obsłuży budowę.
                if self.bot_state == BotState.EXPLORE:
                    if not self.target or (
                            my_pos == self.target
                            and self.target not in self.allied_core_tiles):
                        # --- FALA SONARU (ROSNĄCE OKRĘGI WOKÓŁ BAZY) ---
                        
                        
                        # 2. Promień rośnie wraz z upływem gry. 
                        # Np. zaczynamy od promienia 6 i powiększamy okrąg o 1 kratkę co 5 tur
                        current_radius = 6 + (current_round // 5)
                        
                        # 3. Losujemy losowy kąt na tym okręgu (od 0 do 360 stopni, czyli 2*PI radianów)
                        angle = random.uniform(0, 2 * math.pi)
                        
                        # 4. Wyliczamy nową pozycję na obwodzie wyznaczonego koła
                        target_x = int(self.my_core_cx + current_radius * math.cos(angle))
                        target_y = int(self.my_core_cy + current_radius * math.sin(angle))
                        
                        # 5. ZABEZPIECZENIE: Docinamy cel, żeby nie wyszedł poza granice mapy
                        target_x = max(0, min(map_width - 1, target_x))
                        target_y = max(0, min(map_height - 1, target_y))
                        
                        self.target = Position(target_x, target_y)
                        self.path = []

            elif current_state == BotState.BUILD_MINE:
                target_pos = self.target

                # 0. ZABEZPIECZENIE: Jeśli zgubiliśmy cel
                if not target_pos:
                    self.bot_state = BotState.EXPLORE
                    self.path = []
                    self.assigned_ore = None
                else:
                    at_ore = my_pos.distance_squared(target_pos) <= 2

                    # 0b. TIMEOUT: jeśli nie dotarliśmy do złoża przez 60 tur — porzucamy
                    if not at_ore and (current_round - self.bot_mine_since) >= 60:
                        self.bot_state = BotState.EXPLORE
                        self.target = None
                        self.path = []
                        self.assigned_ore = None

                    # 1. SANITY CHECK: Czy ktoś nas ubiegł budynkiem?
                    else:
                        b_type_chk, b_team_chk, _ = self.buildings.get(target_pos, (None, None, -1))
                        # Droga WROGA na złożu → nie możemy zbudować harvestera, porzuć
                        enemy_road_on_ore = (b_type_chk == EntityType.ROAD and b_team_chk == enemy_team)
                        # Inny budynek (nie marker, nie nasza droga) → pole zajęte
                        alien_building = (b_type_chk is not None
                                          and b_type_chk not in (EntityType.MARKER, EntityType.ROAD))
                        if enemy_road_on_ore or alien_building:
                            self.bot_state = BotState.EXPLORE
                            self.target = None
                            self.path = []
                            self.assigned_ore = None

                        # 1b. SANITY CHECK: Inna jednostka zarezerwowała/czeka — ale TYLKO gdy
                        # jeszcze nie dotarliśmy do złoża (gdy already at_ore mamy pierwszeństwo)
                        elif not at_ore and self._ore_already_claimed_by_other(ct, my_id, my_team, target_pos, current_round):
                            self.bot_state = BotState.EXPLORE
                            self.target = None
                            self.path = []
                            self.assigned_ore = None

                        # 2. Jesteśmy przy rudzie? BUDUJEMY!
                        elif at_ore:
                            if ct.get_action_cooldown() == 0:
                                # Sprawdź czy stać nas na harvester (zanim zniszczymy drogę)
                                can_afford_harv = my_tit >= HARVESTER_BASE_COST[0]

                                # Jeśli na złożu stoi nasza droga — zniszcz ją TYLKO gdy stać
                                # na harvestera. Inaczej zostawiamy drogę jako blokadę.
                                road_on_ore = ct.get_tile_building_id(target_pos) if ct.is_in_vision(target_pos) else None
                                if (road_on_ore is not None
                                        and ct.get_entity_type(road_on_ore) == EntityType.ROAD
                                        and ct.get_team(road_on_ore) == my_team
                                        and can_afford_harv
                                        and ct.can_destroy(target_pos)):
                                    ct.destroy(target_pos)
                                if ct.can_build_harvester(target_pos):
                                    ct.build_harvester(target_pos)

                                    if target_pos in self.vip_facts:
                                        env = self.vip_facts[target_pos][0]
                                        self.vip_facts[target_pos] = (env, EntityType.HARVESTER, False)

                                    self.bot_state = BotState.BUILD_BELT
                                    self.last_bridge_node = target_pos
                                    self.target = target_pos
                                    self.belt_chain = set()
                                    self.belt_stuck_counter = 0
                                else:
                                    # Cooldown == 0 ale brak surowców —
                                    # budujemy drogę na złożu (blokada dla przeciwnika)
                                    # i ogłaszamy rezerwację na SĄSIEDNIM polu (nie na złożu, bo tam droga)
                                    ore_b_id = ct.get_tile_building_id(target_pos)
                                    if ore_b_id is not None and ct.can_destroy(target_pos):
                                        ore_bt = ct.get_entity_type(ore_b_id)
                                        if ore_bt == EntityType.MARKER:
                                            ct.destroy(target_pos)  # usuń marker żeby zbudować drogę
                                    if ct.can_build_road(target_pos):
                                        ct.build_road(target_pos)
                                    # Marker rezerwacji na sąsiednim polu (złoże już zajęte drogą)
                                    self._place_claim_marker_near_ore(ct, my_id, my_team, target_pos, current_round, forbidden_tiles={my_pos, target_pos})
                            else:
                                # Czekamy na cooldown — ogłaszamy rezerwację i budujemy drogę (jeśli możliwe)
                                # destroy i build_road nie wymagają cooldownu akcji
                                ore_b_id2 = ct.get_tile_building_id(target_pos)
                                if ore_b_id2 is not None:
                                    ore_bt2 = ct.get_entity_type(ore_b_id2)
                                    if ore_bt2 == EntityType.MARKER and ct.can_destroy(target_pos):
                                        ct.destroy(target_pos)
                                if ct.can_build_road(target_pos):
                                    ct.build_road(target_pos)
                                self._place_claim_marker_near_ore(ct, my_id, my_team, target_pos, current_round, forbidden_tiles={my_pos, target_pos})
                                self.path = []
            
            elif current_state == BotState.BUILD_BELT:
                # last_node = ostatni wybudowany element sieci (Harvester, conveyor lub most).
                # Zadanie: poprowadzić sieć od last_node do Core (lub istniejącej sieci).
                # Strategia: domyślnie conveyor krok po kroku; most jako objazd gdy pole
                # zablokowane (ściana, budynek wroga, ruda).
                last_node = self.last_bridge_node

                if not last_node:
                    # Brak last_node — nie wiemy skąd prowadzić sieć, uciekamy
                    self.bot_state = BotState.EXPLORE
                    self.target = None
                    self.assigned_ore = None
                elif not self.allied_core_tiles:
                    # Nie wiemy gdzie jest Core — idź go znajdź (losowy cel, jak EXPLORE)
                    if not self.target:
                        self.target = Position(
                            random.randint(0, map_width - 1),
                            random.randint(0, map_height - 1)
                        )
                        self.path = []
                else:
                    # --- PRIORYTET: pending_splitter ---
                    pending = self.pending_splitter
                    if pending is not None:
                        pend_pos, pend_dir = pending
                        b_id_pend = ct.get_tile_building_id(pend_pos) if ct.is_in_vision(pend_pos) else None
                        splitter_there = (b_id_pend is not None and ct.get_entity_type(b_id_pend) == EntityType.SPLITTER)
                        if splitter_there:
                            self.pending_splitter = None
                        elif ct.get_action_cooldown() == 0 and my_pos.distance_squared(pend_pos) <= 2:
                            # Niszczymy co stoi na polu (marker nasz/wrogi, droga)
                            if ct.can_destroy(pend_pos):
                                ct.destroy(pend_pos)
                            if ct.can_build_splitter(pend_pos, pend_dir):
                                ct.build_splitter(pend_pos, pend_dir)
                                self.allied_splitter_tiles.add(pend_pos)
                                self.pending_splitter = None
                            # Jeśli build się nie udał — NIE czyścimy pending, spróbujemy w następnej turze
                        else:
                            # Za daleko lub cooldown > 0 — idź do pend_pos
                            if self.target != pend_pos:
                                self.target = pend_pos
                                self.path = []

                    # delivery_tiles: TYLKO Splittery wokół Core.
                    # Surowce muszą być dostarczone przez Splittery — nie bezpośrednio do Core.
                    delivery_tiles = self.allied_splitter_tiles

                    # Centrum Core
                    core_xs = [p.x for p in self.allied_core_tiles]
                    core_ys = [p.y for p in self.allied_core_tiles]
                    core_cx = (min(core_xs) + max(core_xs)) // 2
                    core_cy = (min(core_ys) + max(core_ys)) // 2
                    core_center = Position(core_cx, core_cy)

                    # Zawsze uzupełniamy allied_splitter_tiles o wszystkie 8 pozycji knight-offset.
                    # Bot musi planować trasę do wejścia Splittera nawet jeśli Splitter jeszcze nie stoi.
                    KNIGHT_OFFSETS_DELIVERY = [
                        ( 1,-2, Direction.SOUTH), ( 2,-1, Direction.WEST),
                        ( 2, 1, Direction.WEST),  ( 1, 2, Direction.NORTH),
                        (-1, 2, Direction.NORTH), (-2, 1, Direction.EAST),
                        (-2,-1, Direction.EAST),  (-1,-2, Direction.SOUTH),
                    ]
                    for ddx, ddy, _ in KNIGHT_OFFSETS_DELIVERY:
                        sp_candidate = Position(core_cx + ddx, core_cy + ddy)
                        if not (0 <= sp_candidate.x < map_width and 0 <= sp_candidate.y < map_height):
                            continue
                        sp_env = self.memory.get(
                            sp_candidate,
                            ct.get_tile_env(sp_candidate) if ct.is_in_vision(sp_candidate) else Environment.EMPTY)
                        if sp_env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                            continue
                        self.allied_splitter_tiles.add(sp_candidate)

                    network_entry_types = {EntityType.BRIDGE, EntityType.CONVEYOR,
                                           EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER}
                    current_belt_chain = self.belt_chain

                    last_node_env = self.memory.get(
                        last_node,
                        ct.get_tile_env(last_node) if ct.is_in_vision(last_node) else Environment.EMPTY
                    )
                    last_node_is_ore = last_node_env in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]

                    # Gdy last_node jest Harvesterem (na rudzie), punktem startowym
                    # dla sieci jest jedno z czterech ortogonalnych pól obok.
                    # Gdy last_node nie jest wolne (inny bot coś tam postawił),
                    # też rozszerzamy source_candidates o sąsiadów — żeby bot nie
                    # blokował się na zawsze i szukał alternatywnej trasy.
                    if last_node_is_ore:
                        source_candidates = [
                            last_node.add(d) for d in ORTHOGONAL_DIRECTIONS
                            if (lambda p: 0 <= p.x < map_width and 0 <= p.y < map_height)(last_node.add(d))
                        ]
                    else:
                        # Sprawdzamy czy last_node jest wolne jako source.
                        # Jeśli nie (ktoś coś tam postawił), dodajemy sąsiadów jako
                        # alternatywne punkty startowe.
                        last_node_blocked = False
                        if ct.is_in_vision(last_node):
                            b_id_ln_check = ct.get_tile_building_id(last_node)
                            if b_id_ln_check is not None:
                                bt_ln = ct.get_entity_type(b_id_ln_check)
                                # Marker i droga → możemy zastąpić (tile_is_buildable to obsłuży)
                                # Cokolwiek innego (conveyor, most, itd.) → last_node zablokowane
                                if bt_ln not in (EntityType.MARKER, EntityType.ROAD):
                                    last_node_blocked = True
                        if last_node_blocked:
                            source_candidates = [
                                last_node.add(d) for d in ORTHOGONAL_DIRECTIONS
                                if (lambda p: 0 <= p.x < map_width and 0 <= p.y < map_height)(last_node.add(d))
                            ]
                        else:
                            source_candidates = [last_node]

                    # =========================================================
                    # FAZA 1: Szukamy najlepszego kroku — conveyor lub most
                    # Zwracamy: (build_pos, target_pos_or_dir, mode)
                    #   mode='conveyor': postaw conveyor na build_pos skierowany
                    #                    w kierunku target (Direction)
                    #   mode='bridge':   postaw most na build_pos celujący w target (Position)
                    # Priorytety:
                    #   1. Conveyor wprost na delivery_tile (Core/Splitter)
                    #   2. Conveyor wprost na istniejący element sieci
                    #   3. Conveyor na wolne pole (krok w kierunku Core)
                    #   4. Most na delivery_tile lub istniejący element sieci (objazd)
                    #   5. Most na wolne pole (objazd)
                    # =========================================================

                    # =========================================================
                    # Pomocnicze funkcje i stałe
                    # =========================================================

                    # Pola bezpośrednio otaczające Core (distance_sq <= 2 od dowolnego
                    # pola Core) — tam conveyor NIE może być stawiany.
                    near_core_tiles = set()
                    for ct_ in self.allied_core_tiles:
                        for dx in range(-1, 2):
                            for dy in range(-1, 2):
                                near_core_tiles.add(Position(ct_.x + dx, ct_.y + dy))
                    # Dodajemy też pola w odległości skoczka (gdzie są Splittery) —
                    # tylko pola Core i ich bezpośrednie otoczenie są zarezerwowane
                    near_core_tiles |= self.allied_core_tiles

                    # Mapa wejść Splitterów: splitter_pos → wymagane pole wejściowe
                    # Wejście = splitter_pos.add(faces.opposite())
                    KNIGHT_OFFSETS_SP = [
                        ( 1,-2, Direction.SOUTH), ( 2,-1, Direction.WEST),
                        ( 2, 1, Direction.WEST),  ( 1, 2, Direction.NORTH),
                        (-1, 2, Direction.NORTH), (-2, 1, Direction.EAST),
                        (-2,-1, Direction.EAST),  (-1,-2, Direction.SOUTH),
                    ]
                    splitter_input_map = {}  # splitter_pos → input_pos
                    for ddx, ddy, sp_faces in KNIGHT_OFFSETS_SP:
                        sp = Position(core_cx + ddx, core_cy + ddy)
                        if sp in self.allied_splitter_tiles:
                            splitter_input_map[sp] = sp.add(sp_faces.opposite())

                    def tile_is_buildable(pos):
                        if not (0 <= pos.x < map_width and 0 <= pos.y < map_height):
                            return False
                        env = self.memory.get(
                            pos, ct.get_tile_env(pos) if ct.is_in_vision(pos) else Environment.EMPTY)
                        if env in HARD_OBSTACLES:
                            return False
                        if ct.is_in_vision(pos):
                            b_id_t = ct.get_tile_building_id(pos)
                            if b_id_t is not None:
                                b_type_t = ct.get_entity_type(b_id_t)
                                # Markery (nasz lub wrogi) — można zastąpić
                                if b_type_t == EntityType.MARKER:
                                    return True
                                # Nasza droga — można zastąpić (destroy + build)
                                if b_type_t == EntityType.ROAD and ct.get_team(b_id_t) == my_team:
                                    return True
                                return False
                        return True

                    def is_existing_network(pos):
                        pass
                        if pos in current_belt_chain:
                            return False
                        mem = self.buildings.get(pos)
                        if mem is not None:
                            mt, mteam, _ = mem
                            if mteam == my_team and mt in network_entry_types:
                                return True
                        return False

                    # =========================================================
                    # Szukamy najlepszego kroku (build_pos, build_target, build_mode)
                    # Konwencja:
                    #   conveyor: build_pos = pole gdzie stanie conveyor (source),
                    #             build_target = Direction (na cand)
                    #             last_node po budowie = build_pos.add(build_target) = cand
                    #   bridge:   build_pos = pole gdzie stanie most (source),
                    #             build_target = Position (cel mostu)
                    #             last_node po budowie = build_target
                    #
                    # REGUŁY WPIĘCIA:
                    # Conveyor (ostatni element) może wskazywać na:
                    #   - Splitter: TYLKO od strony wejściowej (source == splitter_input_map[sp])
                    #   - Istniejący conveyor/most: OK
                    #   - NIE na pole Core
                    #   - NIE na pola bezpośrednio otaczające Core (near_core_tiles)
                    #     jako source (tam conveyor nie może stać)
                    # Bridge może mieć wyjście (build_target) na:
                    #   - Polu Core: OK (most dostarcza wprost)
                    #   - Splitterze: OK
                    #   - Istniejącym elemencie sieci: OK
                    #   - Wolnym polu: krok pośredni
                    # =========================================================

                    build_pos = None
                    build_target = None
                    build_mode = None
                    build_is_network = False
                    best_score = float('inf')

                    for source in source_candidates:
                        if not (0 <= source.x < map_width and 0 <= source.y < map_height):
                            continue
                        src_env = self.memory.get(
                            source, ct.get_tile_env(source) if ct.is_in_vision(source) else Environment.EMPTY)
                        if src_env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                            continue

                        src_dist = source.distance_squared(core_center)
                        source_buildable = tile_is_buildable(source)

                        # ---- CONVEYOR ----
                        # source NIE może leżeć w near_core_tiles
                        if source_buildable and source not in near_core_tiles:
                            for d in ORTHOGONAL_DIRECTIONS:
                                cand = source.add(d)
                                if not (0 <= cand.x < map_width and 0 <= cand.y < map_height):
                                    continue
                                if cand in current_belt_chain:
                                    continue

                                cand_dist = cand.distance_squared(core_center)

                                # Przypadek A: cand to Splitter — tylko od strony wejściowej
                                if cand in self.allied_splitter_tiles:
                                    required_input = splitter_input_map.get(cand)
                                    if required_input is None or source != required_input:
                                        continue  # zła strona Splittera
                                    # Sprawdź czy Splitter jest już zasilany
                                    # (czy jakiś sąsiad ma nasz conveyor/most wskazujący na niego)
                                    splitter_fed = False
                                    if ct.is_in_vision(cand):
                                        for d_feed in ORTHOGONAL_DIRECTIONS:
                                            feed_pos = cand.add(d_feed)
                                            # --- POPRAWKA: Zabezpieczenie przed wyjściem poza mapę ---
                                            if not (0 <= feed_pos.x < map_width and 0 <= feed_pos.y < map_height):
                                                continue
                                            # ----------------------------------------------------------
                                            if not ct.is_in_vision(feed_pos):
                                                continue
                                            b_id_feed = ct.get_tile_building_id(feed_pos)
                                            if b_id_feed is None:
                                                continue
                                            if ct.get_team(b_id_feed) != my_team:
                                                continue
                                            ft = ct.get_entity_type(b_id_feed)
                                            if ft == EntityType.CONVEYOR:
                                                try:
                                                    if feed_pos.add(ct.get_direction(b_id_feed)) == cand:
                                                        splitter_fed = True
                                                        break
                                                except Exception:
                                                    pass
                                            elif ft == EntityType.BRIDGE:
                                                try:
                                                    if ct.get_bridge_target(b_id_feed) == cand:
                                                        splitter_fed = True
                                                        break
                                                except Exception:
                                                    pass
                                    # Wolny Splitter → wyższy priorytet (score=0)
                                    # Zajęty Splitter → niższy priorytet (score=2)
                                    score = 2 if splitter_fed else 0
                                    if score < best_score:
                                        best_score = score
                                        build_pos = source
                                        build_target = d
                                        build_mode = 'conveyor'
                                        build_is_network = True

                                # Przypadek B: cand to istniejący element sieci (conveyor/most)
                                # NIE Core, NIE Splitter (już obsłużony)
                                # elif cand not in self.allied_core_tiles and is_existing_network(cand):
                                #     if not (cand_dist < src_dist):  # progress guard
                                #         continue
                                #     score = 1
                                #     if score < best_score:
                                #         best_score = score
                                #         build_pos = source
                                #         build_target = d
                                #         build_mode = 'conveyor'
                                #         build_is_network = True

                                
                                # Przypadek B: Wpięcie w istniejący element sieci (conveyor/most)
                                elif cand not in self.allied_core_tiles and is_existing_network(cand):
                                    if not (cand_dist < src_dist):  # Musi nas to zbliżać do bazy
                                        continue

                                    # --- INTELIGENTNY DETEKTOR KORKÓW ---
                                    is_clogged = False
                                    try:
                                        b_id_cand = ct.get_tile_building_id(cand)
                                        cand_type = ct.get_entity_type(b_id_cand)
                                        
                                        # Sprawdzamy zator głębiej, aby odróżnić jadący surowiec od stojącego korka
                                        if cand_type == EntityType.CONVEYOR and ct.get_stored_resource(b_id_cand) is not None:
                                            cand_dir = ct.get_direction(b_id_cand)
                                            next_pos = cand.add(cand_dir)
                                            if ct.is_in_vision(next_pos):
                                                b_id_next = ct.get_tile_building_id(next_pos)
                                                # Jeśli następny element taśmy też ma na sobie rudę, to przepustowość leży
                                                if b_id_next and ct.get_stored_resource(b_id_next) is not None:
                                                    is_clogged = True
                                    except Exception:
                                        pass

                                    if is_clogged:
                                        continue  # Autostrada pełna! Szukamy innej opcji (np. budowa nowej linii)

                                    # Taśma jest luźna (ma wolną przepustowość) - wpinamy się oszczędzając Tytan
                                    score = 150 + cand_dist
                                    if score < best_score:
                                        best_score = score
                                        build_pos = source
                                        build_target = d
                                        build_mode = 'conveyor'
                                        build_is_network = True

                                # Przypadek D: wolne pole — krok pośredni (Budowa nowej linii)
                                elif (cand not in near_core_tiles
                                        and tile_is_buildable(cand)
                                        and cand_dist < src_dist):
                                    # Puste pole ma wyższy (gorszy) score bazowy (200).
                                    # Jeśli taśma obok jest drożna (score 150), bot najpierw wepnie się w nią.
                                    score = 200 + cand_dist
                                    if score < best_score:
                                        best_score = score
                                        build_pos = source
                                        build_target = d
                                        build_mode = 'conveyor'
                                        build_is_network = False


                        # ---- MOST ----
                        # Most może startować z dowolnego buildable source (w tym near_core)
                        # Most szukamy zawsze (nie tylko gdy ortho_blocked) —
                        # ale priorytet niższy niż conveyor wpięcia (score >= 200)
                        if source_buildable:
                            # Sprawdzamy co stoi na source — nie nadbudowujemy innych budynków,
                            # ale markery (nasz lub wrogi) i nasze drogi można zastąpić mostem.
                            if ct.is_in_vision(source):
                                b_id_src = ct.get_tile_building_id(source)
                                if b_id_src is not None:
                                    bt_src = ct.get_entity_type(b_id_src)
                                    tm_src = ct.get_team(b_id_src)
                                    replaceable = (bt_src == EntityType.MARKER or
                                                   (bt_src == EntityType.ROAD and tm_src == my_team))
                                    if not replaceable:
                                        continue  # nie nadbudowujemy innych budynków

                            for dx in range(-3, 4):
                                for dy in range(-3, 4):
                                    end_pos = Position(source.x + dx, source.y + dy)
                                    if not (0 <= end_pos.x < map_width and 0 <= end_pos.y < map_height):
                                        continue
                                    d2 = source.distance_squared(end_pos)
                                    if d2 == 0 or d2 > 9:
                                        continue
                                    if end_pos in current_belt_chain:
                                        continue
                                    end_dist = end_pos.distance_squared(core_center)

                                    # Przypadek A: pole Core — niedozwolone jako cel mostu.
                                    # Surowce muszą płynąć przez Splittery.
                                    if end_pos in self.allied_core_tiles:
                                        pass  # pominięte

                                    # Przypadek B: end_pos to Splitter
                                    elif end_pos in self.allied_splitter_tiles:
                                        # Preferuj niezasilany Splitter
                                        splitter_fed_b = False
                                        if ct.is_in_vision(end_pos):
                                            for d_feed in ORTHOGONAL_DIRECTIONS:
                                                feed_pos = end_pos.add(d_feed)
                                                if not ct.is_in_vision(feed_pos):
                                                    continue
                                                if not (0 <= feed_pos.x < map_width and 0 <= feed_pos.y < map_height):
                                                    continue
                                                b_id_feed = ct.get_tile_building_id(feed_pos)
                                                if b_id_feed is None:
                                                    continue
                                                if ct.get_team(b_id_feed) != my_team:
                                                    continue
                                                ft = ct.get_entity_type(b_id_feed)
                                                if ft == EntityType.CONVEYOR:
                                                    try:
                                                        if feed_pos.add(ct.get_direction(b_id_feed)) == end_pos:
                                                            splitter_fed_b = True
                                                            break
                                                    except Exception:
                                                        pass
                                                elif ft == EntityType.BRIDGE:
                                                    try:
                                                        if ct.get_bridge_target(b_id_feed) == end_pos:
                                                            splitter_fed_b = True
                                                            break
                                                    except Exception:
                                                        pass
                                        score = 202 if splitter_fed_b else 200
                                        if score < best_score:
                                            best_score = score
                                            build_pos = source
                                            build_target = end_pos
                                            build_mode = 'bridge'
                                            build_is_network = True

                                    # Przypadek C: most w istniejącą sieć
                                    elif is_existing_network(end_pos):
                                        if end_dist >= src_dist:
                                            continue
                                        if end_pos in near_core_tiles:
                                            continue
                                            
                                        # Inteligentny detektor korków dla zrzutu z mostu
                                        is_clogged = False
                                        try:
                                            b_id_end = ct.get_tile_building_id(end_pos)
                                            end_type = ct.get_entity_type(b_id_end)
                                            
                                            if end_type == EntityType.CONVEYOR and ct.get_stored_resource(b_id_end) is not None:
                                                end_dir = ct.get_direction(b_id_end)
                                                next_pos = end_pos.add(end_dir)
                                                if ct.is_in_vision(next_pos):
                                                    b_id_next = ct.get_tile_building_id(next_pos)
                                                    if b_id_next and ct.get_stored_resource(b_id_next) is not None:
                                                        is_clogged = True
                                        except Exception:
                                            pass
                                            
                                        if is_clogged:
                                            continue # Cel zapchany, nie lądujemy tu mostem
                                            
                                        score = 250 + end_dist
                                        if score < best_score:
                                            best_score = score
                                            build_pos = source
                                            build_target = end_pos
                                            build_mode = 'bridge'
                                            build_is_network = True

                                    # Przypadek D: wolne pole — krok pośredni
                                    # NIE lądujemy na near_core_tiles (zarezerwowane dla Splitterów/Sentineli)
                                    elif (end_pos not in near_core_tiles
                                            and tile_is_buildable(end_pos)
                                            and end_dist < src_dist):
                                        score = 300 + end_dist
                                        if score < best_score:
                                            best_score = score
                                            build_pos = source
                                            build_target = end_pos
                                            build_mode = 'bridge'
                                            build_is_network = False

                    # =========================================================
                    # KROK 4: Sprawdź czy misja zakończona
                    # last_node ∈ delivery_tiles → zasoby dotarły do sieci
                    # =========================================================
                    # KROK 4: Sprawdź czy misja zakończona.
                    # Sprawdzamy zawsze — niezależnie od pending_splitter.
                    # Splitter liczy jako cel TYLKO gdy fizycznie stoi.
                    # =========================================================
                    mission_done = False
                    if last_node in delivery_tiles:
                        # Pozycja splittera — sprawdzamy czy faktycznie stoi
                        if ct.is_in_vision(last_node):
                            b_id_ln_sp = ct.get_tile_building_id(last_node)
                            if b_id_ln_sp is not None and ct.get_team(b_id_ln_sp) == my_team and ct.get_entity_type(b_id_ln_sp) == EntityType.SPLITTER:
                                mission_done = True
                            elif self.pending_splitter is None:
                                # Splitter nie stoi — musimy go zbudować; ustawiamy pending_splitter
                                for ddx, ddy, sp_faces in [
                                    ( 1,-2, Direction.SOUTH), ( 2,-1, Direction.WEST),
                                    ( 2, 1, Direction.WEST),  ( 1, 2, Direction.NORTH),
                                    (-1, 2, Direction.NORTH), (-2, 1, Direction.EAST),
                                    (-2,-1, Direction.EAST),  (-1,-2, Direction.SOUTH),
                                ]:
                                    if last_node == Position(core_cx + ddx, core_cy + ddy):
                                        self.pending_splitter = (last_node, sp_faces)
                                        break
                        # Jeśli nie w zasięgu wzroku — czekamy aż będzie widać
                    if not mission_done and ct.is_in_vision(last_node):
                        b_id_ln = ct.get_tile_building_id(last_node)
                        if b_id_ln is not None and ct.get_team(b_id_ln) == my_team:
                            if ct.get_entity_type(b_id_ln) in {EntityType.SPLITTER, EntityType.CORE}:
                                mission_done = True
                    if not mission_done:
                        if is_existing_network(last_node):
                            mission_done = True
                    if mission_done:
                        self.bot_state = BotState.EXPLORE
                        self.target = None
                        self.path = []
                        self.belt_chain = set()
                        self.pending_splitter = None
                        self.assigned_ore = None

                    
                    
                    
                    
                    # =========================================================
                    # FAZA WYKONANIA
                    # =========================================================
                    if self.bot_state == BotState.BUILD_BELT:

                        # --- TRYB SENTINEL: gdy stuck >= 20, ignoruj build_pos ---
                        if self.belt_stuck_counter >= 20:
                            # Jeśli nie stać na Sentinela — czekaj przy last_node zamiast porzucać
                            if not self._can_afford_build(ct, 'sentinel'):
                                if self.target != last_node:
                                    self.target = last_node
                                    self.path = []
                            else:
                                ready = (ct.get_action_cooldown() == 0
                                         and ct.is_in_vision(last_node)
                                         and my_pos.distance_squared(last_node) <= 2)
                                if not ready:
                                    # Idź do last_node i poczekaj
                                    self.belt_stuck_counter = 20
                                    if self.target != last_node:
                                        self.target = last_node
                                        self.path = []
                                else:
                                    # Buduj Sentinela — kierunek w stronę środka mapy
                                    map_center = Position(map_width // 2, map_height // 2)
                                    dx = map_center.x - last_node.x
                                    dy = map_center.y - last_node.y
                                    best_sentinel_dir = None
                                    best_dot = float('-inf')
                                    for cand_dir in DIRECTIONS:
                                        ddx, ddy = cand_dir.delta()
                                        dot = dx * ddx + dy * ddy
                                        if dot > best_dot:
                                            best_dot = dot
                                            best_sentinel_dir = cand_dir
                                    sentinel_dir = best_sentinel_dir or Direction.NORTH
                                    for d_check in ORTHOGONAL_DIRECTIONS:
                                        neighbor = last_node.add(d_check)
                                        if not (0 <= neighbor.x < map_width and 0 <= neighbor.y < map_height):
                                            continue
                                        if not ct.is_in_vision(neighbor):
                                            continue
                                        b_id_nb = ct.get_tile_building_id(neighbor)
                                        if b_id_nb is None:
                                            continue
                                        if ct.get_team(b_id_nb) == my_team and ct.get_entity_type(b_id_nb) == EntityType.CONVEYOR:
                                            try:
                                                conv_out_dir = ct.get_direction(b_id_nb)
                                                if neighbor.add(conv_out_dir) == last_node and sentinel_dir == d_check:
                                                    sentinel_dir = sentinel_dir.rotate_right()
                                            except Exception:
                                                pass
                                    if self.can_replace_with(last_node, 3, my_team, ct) and ct.can_destroy(last_node):
                                        ct.destroy(last_node)
                                    if ct.can_build_sentinel(last_node, sentinel_dir):
                                        ct.build_sentinel(last_node, sentinel_dir)
                                    # Niezależnie od wyniku — porzucamy nitkę
                                    self.bot_state = BotState.EXPLORE
                                    self.target = None
                                    self.path = []
                                    self.belt_chain = set()
                                    self.belt_stuck_counter = 0
                                    self.assigned_ore = None

                        elif build_pos is not None and build_target is not None:

                            if my_pos == build_pos:
                                # Stoimy NA build_pos — zejdź.
                                if build_mode == 'conveyor':
                                    away_pos = build_pos.add(build_target)
                                else:
                                    away_pos = build_target
                                for try_dir in sorted(DIRECTIONS, key=lambda d: my_pos.add(d).distance_squared(away_pos)):
                                    if ct.can_move(try_dir):
                                        ct.move(try_dir)
                                        self.path = []
                                        break
                                self.target = build_pos

                            elif my_pos.distance_squared(build_pos) <= 2:
                                # Stoimy obok — budujemy.
                                # KROK A: Conveyor/most (priorytet 3) może zastąpić marker i drogę
                                if self.can_replace_with(build_pos, 3, my_team, ct) and ct.can_destroy(build_pos):
                                    ct.destroy(build_pos)

                                if ct.get_action_cooldown() == 0:
                                    built = False
                                    if build_mode == 'conveyor':
                                        if ct.can_build_conveyor(build_pos, build_target):
                                            ct.build_conveyor(build_pos, build_target)
                                            built = True
                                    else:  # bridge
                                        if ct.can_build_bridge(build_pos, build_target):
                                            ct.build_bridge(build_pos, build_target)
                                            built = True

                                    if built:
                                        self.belt_stuck_counter = 0  # postęp — resetuj licznik
                                        if build_mode == 'conveyor':
                                            conv_output = build_pos.add(build_target)
                                            self.last_bridge_node = conv_output
                                            self.belt_chain.add(build_pos)
                                            # pending_splitter jeśli conveyor wskazuje na nieistniejący splitter
                                            if conv_output in self.allied_splitter_tiles:
                                                b_id_sp_cv = ct.get_tile_building_id(conv_output) if ct.is_in_vision(conv_output) else None
                                                splitter_there_cv = (b_id_sp_cv is not None and ct.get_entity_type(b_id_sp_cv) == EntityType.SPLITTER)
                                                if not splitter_there_cv and self.pending_splitter is None:
                                                    for ddx, ddy, sp_faces in [
                                                        ( 1,-2, Direction.SOUTH), ( 2,-1, Direction.WEST),
                                                        ( 2, 1, Direction.WEST),  ( 1, 2, Direction.NORTH),
                                                        (-1, 2, Direction.NORTH), (-2, 1, Direction.EAST),
                                                        (-2,-1, Direction.EAST),  (-1,-2, Direction.SOUTH),
                                                    ]:
                                                        if conv_output == Position(core_cx + ddx, core_cy + ddy):
                                                            self.pending_splitter = (conv_output, sp_faces)
                                                            break
                                        else:  # bridge
                                            # last_node = build_target (cel mostu)
                                            self.last_bridge_node = build_target
                                            self.belt_chain.add(build_pos)
                                            self.belt_chain.add(build_target)
                                            # pending_splitter jeśli most wylądował na Splitterze
                                            if build_target in self.allied_splitter_tiles:
                                                b_id_end = ct.get_tile_building_id(build_target) if ct.is_in_vision(build_target) else None
                                                splitter_there = (b_id_end is not None and ct.get_entity_type(b_id_end) == EntityType.SPLITTER)
                                                if not splitter_there:
                                                    sp_cx = (min(core_xs) + max(core_xs)) // 2
                                                    sp_cy = (min(core_ys) + max(core_ys)) // 2
                                                    knight_offsets = [
                                                        ( 1, -2, Direction.SOUTH),
                                                        ( 2, -1, Direction.WEST),
                                                        ( 2,  1, Direction.WEST),
                                                        ( 1,  2, Direction.NORTH),
                                                        (-1,  2, Direction.NORTH),
                                                        (-2,  1, Direction.EAST),
                                                        (-2, -1, Direction.EAST),
                                                        (-1, -2, Direction.SOUTH),
                                                    ]
                                                    for ddx, ddy, faces in knight_offsets:
                                                        if build_target == Position(sp_cx + ddx, sp_cy + ddy):
                                                            self.pending_splitter = (build_target, faces)
                                                            break

                                        if build_is_network:
                                            # Wpięliśmy się w sieć — misja zakończona
                                            self.bot_state = BotState.EXPLORE
                                            self.target = None
                                            self.path = []
                                            self.belt_chain = set()
                                            self.assigned_ore = None
                                        else:
                                            # Celujemy w nowy last_node (output conveyora
                                            # lub cel mostu) — skąd zbudujemy następny krok
                                            self.target = self.last_bridge_node
                                            self.path = []
                                    else:
                                        # Nie udało się zbudować.
                                        # Sprawdzamy czy to kwestia surowców — jeśli tak, czekamy.
                                        if not self._can_afford_build(ct, build_mode):
                                            # Brak surowców — stój przy build_pos i czekaj,
                                            # NIE inkrementuj stuck, NIE resetuj celu.
                                            self.target = build_pos
                                            self.path = []
                                        else:
                                            # Stać nas, ale can_build zwróciło False z innego powodu
                                            # (np. pole zajęte przez budynek którego nie widzieliśmy)
                                            # — resetuj cel i przelicz w następnej turze.
                                            self.target = None
                                            self.path = []
                                else:
                                    # Cooldown > 0 — czekaj
                                    self.target = build_pos

                            else:
                                # Za daleko — idź do build_pos
                                if self.target != build_pos:
                                    self.target = build_pos
                                    self.path = []

                        else:
                            # Brak opcji budowy geometrycznie.
                            # Sprawdzamy czy to kwestia surowców: obliczamy czy stać nas
                            # na conveyor i na bridge. Jeśli nie stać na żaden —
                            # czekamy bez inkrementacji stuck (nie jest to prawdziwy dead-end).
                            # Sentinel (tryb stuck) też wymaga surowców — sprawdzamy go osobno.
                            waiting_for_resources = (
                                not self._can_afford_build(ct, 'conveyor')
                                and not self._can_afford_build(ct, 'bridge')
                            )
                            if not waiting_for_resources:
                                # Brak opcji budowy — inkrementuj licznik stuck.
                                self.belt_stuck_counter = self.belt_stuck_counter + 1
                                # (gdy stuck >= 20, tryb Sentinela obsłuży to na początku
                                # FAZY WYKONANIA w następnej turze)
                            # W obu przypadkach: podejdź do last_node i czekaj.
                            # Jeśli last_node jest już w sieci, zakończ misję.
                            if last_node in delivery_tiles or is_existing_network(last_node):
                                self.bot_state = BotState.EXPLORE
                                self.target = None
                                self.path = []
                                self.belt_chain = set()
                                self.pending_splitter = None
                                self.assigned_ore = None
                            else:
                                wait_target = last_node
                                if last_node_is_ore:
                                    for d_wait in ORTHOGONAL_DIRECTIONS:
                                        wp = last_node.add(d_wait)
                                        if not (0 <= wp.x < map_width and 0 <= wp.y < map_height):
                                            continue
                                        wp_env = self.memory.get(wp, ct.get_tile_env(wp) if ct.is_in_vision(wp) else Environment.EMPTY)
                                        if wp_env not in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE, Environment.WALL]:
                                            wait_target = wp
                                            break
                                if self.target != wait_target:
                                    self.target = wait_target
                                    self.path = []


            elif current_state == BotState.BUILD_BUNKER:
                # ==========================================
                # BUILD_BUNKER: Tworzy ufortyfikowaną placówkę na środku mapy
                # ==========================================
                if current_round >= 60:
                    self.state = BotState.EXPLORE
                    self.target = None
                    self.path = []  

                if self.assigned_ore is None:
                    if not self.target:
                        self.target = Position(map_width // 2, map_height // 2)
                        self.path = []
                
                    if my_pos.distance_squared(self.target) <= 3:
                        found_ore = self.find_nearest_vip_target(my_pos, self.vip_facts, [Environment.ORE_TITANIUM])
                        if found_ore:
                            self.assigned_ore = found_ore
                            self.target = found_ore
                            self.path = []
                        else:
                            self.bot_state = BotState.EXPLORE
                            self.target = None
                            self.path = []
                            self.assigned_ore = None
                        

                # Krok 2: Obsługa złoża i budowa Harvestera (bezpieczny zakres)
                elif self.assigned_ore is not None:
                    ore_pos = self.assigned_ore
                    
                    harvester_built = False
                    if ct.is_in_vision(ore_pos):
                        ore_b_id = ct.get_tile_building_id(ore_pos)
                        harvester_built = (ore_b_id is not None and ct.get_entity_type(ore_b_id) == EntityType.HARVESTER)
                        
                        if not harvester_built:
                            if self.target != ore_pos:
                                self.target = ore_pos
                            if my_pos.distance_squared(ore_pos) <= 2:
                                if ct.get_action_cooldown() == 0:
                                    if ore_b_id is not None and ct.can_destroy(ore_pos):
                                        ct.destroy(ore_pos)
                                    elif self._can_afford_build(ct, 'harvester') and ct.can_build_harvester(ore_pos):
                                        ct.build_harvester(ore_pos)
                                        self.vip_facts[ore_pos] = (Environment.ORE_TITANIUM, EntityType.HARVESTER, False)
                            
                        else:
                            # Krok 3: Obudowa Sentinelami z weryfikacją granic (out_of_bounds)
                            missing_sentinels = []
                            for d in ORTHOGONAL_DIRECTIONS:
                                sn_pos = ore_pos.add(d)
                                env_sn = self.memory.get(sn_pos, ct.get_tile_env(sn_pos) if ct.is_in_vision(sn_pos) else Environment.EMPTY)
                                                                    
                                if not ct.is_in_vision(sn_pos):
                                    missing_sentinels.append((sn_pos, d))
                                    continue
                                    
                                sn_b_id = ct.get_tile_building_id(sn_pos)
                                if sn_b_id is not None:
                                    bt = ct.get_entity_type(sn_b_id)
                                    tm = ct.get_team(sn_b_id)
                                    if bt == EntityType.SENTINEL and tm == my_team:
                                        continue 
                                    elif bt not in [EntityType.MARKER, EntityType.ROAD]:
                                        continue 
                                        
                                missing_sentinels.append((sn_pos, d))
                                
                            if not missing_sentinels:
                                # Sukces! Placówka zbudowana
                                self.bot_state = BotState.EXPLORE
                                self.target = None
                                self.path = []
                                self.assigned_ore = None
                            else:
                                # Budujemy brakujące sentinele
                                sn_target, sn_dir = missing_sentinels[0]
                                if self.target != sn_target:
                                    self.target = sn_target
                                    self.path = []

                                dist = my_pos.distance_squared(sn_target)
                                if dist <= 2:
                                    if ct.get_action_cooldown() == 0:
                                        b_id_to_destroy = ct.get_tile_building_id(sn_target)
                                        if b_id_to_destroy is not None and ct.can_destroy(sn_target):
                                            ct.destroy(sn_target)
                                        elif self._can_afford_build(ct, 'sentinel') and ct.can_build_sentinel(sn_target, sn_dir):
                                            ct.build_sentinel(sn_target, sn_dir)
            
            elif current_state == BotState.HARRAS:
                # ==========================================
                # HARRAS: Niszczarka taśmociągów i mostów.
                # Szuka wrogiej infrastruktury logistycznej, wchodzi na nią i atakuje w nieskończoność.
                # ==========================================
                
                is_attacking = False
                
                # 1. Sprawdzamy, czy stoimy dokładnie na celu do zniszczenia
                b_id_here = ct.get_tile_building_id(my_pos)
                if b_id_here is not None and ct.get_team(b_id_here) == enemy_team:
                    b_type_here = ct.get_entity_type(b_id_here)
                    if b_type_here in NETWORK:
                        
                        # Jesteśmy na wrogiej infrastrukturze! Niszczymy.
                        if ct.get_action_cooldown() == 0 and ct.can_fire(my_pos):
                            ct.fire(my_pos)
                        
                        # Zatrzymujemy się w miejscu i tłuczemy aż pole będzie czyste
                        self.target = my_pos
                        self.path = []
                        is_attacking = True
                
                # 2. Jeśli nie atakujemy w tej turze, to szukamy nowego celu (lub odświeżamy stary)
                if not is_attacking:
                    # Szukamy nowego celu na starcie, albo po dotarciu na puste pole, albo co 10 tur (żeby namierzyć coś bliżej)
                    if not self.target or self.target == my_pos or current_round % 5 == 0:
                        # --- USTALAMY POZYCJĘ BAZY WROGA ---
                        enemy_core_pos = None
                        # Najpierw sprawdzamy, czy przypadkiem nie mamy fizycznej wrogiej bazy w pamięci
                        for p, (b_t, b_tm, _) in self.buildings.items():
                            if b_t == EntityType.CORE and b_tm == enemy_team:
                                enemy_core_pos = p
                                break
                        
                        # Jeśli nie widzieliśmy bazy, estymujemy ją na podstawie symetrii naszej bazy
                        if not enemy_core_pos and self.my_core_center:
                            enemy_core_pos = Position(map_width - 1 - self.my_core_cx, map_height - 1 - self.my_core_cy)
                            
                        # Ostateczność (rdzenie zniszczone) -> celujemy w środek mapy
                        if not enemy_core_pos:
                            enemy_core_pos = Position(map_width // 2, map_height // 2)

                        # --- SZUKAMY OPTYMALNEGO CELU ---
                        best_junk_pos = None
                        best_score = float('inf')
                        
                        # Przeszukujemy pełną pamięć budynków
                        for pos, (b_type, b_team, _) in self.buildings.items():
                            if b_team == enemy_team and b_type in NETWORK:
                                dist_to_bot = my_pos.distance_squared(pos)
                                dist_to_enemy_core = pos.distance_squared(enemy_core_pos)
                                
                                # FUNKCJA KOSZTU: dystans do wrogiej bazy ma wagę 2x, dystans do bota 1x.
                                score = dist_to_bot + (dist_to_enemy_core * 2)
                                
                                if score < best_score:
                                    best_score = score
                                    best_junk_pos = pos
                                    
                        if best_junk_pos:
                            # Znaleźliśmy wrogi taśmociąg/drogę o najlepszym stosunku bliskości bazy wroga!
                            if self.target != best_junk_pos:
                                self.target = best_junk_pos
                                self.path = []
                        elif not self.target or self.target == my_pos:
                            # 3. Brak wrogich celów w pamięci -> losowy patrol po terytorium wroga
                            target_is_wall = (self.target and self.memory.get(self.target) in HARD_OBSTACLES)
                            if not self.target or my_pos == self.target or target_is_wall:
                                # Obszar wielkości 1/3 mapy dookoła estymowanego punktu wrogiej bazy
                                rad_x = map_width // 3
                                rad_y = map_height // 3
                                
                                rx = random.randint(max(0, enemy_core_pos.x - rad_x), min(map_width - 1, enemy_core_pos.x + rad_x))
                                ry = random.randint(max(0, enemy_core_pos.y - rad_y), min(map_height - 1, enemy_core_pos.y + rad_y))
                                
                                self.target = Position(rx, ry)
                                self.path = []          



            # ==========================================
            # 3. RUCH (NOGI) - Wykonuje się tylko, gdy mamy gdzie iść
            # ==========================================
            future_pos = my_pos
            target_pos = self.target
            
            # Wizualizacja
            if target_pos:
                try:
                    ct.draw_indicator_dot(target_pos, 255, 255, 0) # type: ignore
                    ct.draw_indicator_line(my_pos, target_pos, 0, 200, 255) # type: ignore
                except Exception:
                    pass

            # BEZPIECZNIK: jeśli cel nie zmienił się przez 60 tur, resetuj go.
            # Działa tylko w stanach nie-budujących.
            WANDERING_STATES = {BotState.EXPLORE,  BotState.ROAD_LAYER, BotState.KAMIKAZE, 
                                BotState.REPAIRMAN, BotState.FORTIFIER, BotState.SMELTER}
            if target_pos is not None and self.bot_state in WANDERING_STATES:
                if self.target_last != target_pos:
                    # Nowy cel — zapamiętaj turę ustawienia
                    self.target_last = target_pos
                    self.target_since = current_round
                elif current_round - self.target_since >= 60:
                    # Ten sam cel przez 60 tur — reset
                    self.target = None
                    self.path = []
                    self.target_last = None
                    self.target_since = current_round
                    target_pos = None

            # Czy bot idzie budować? (zatrzymuje się krok przed celem, nie wchodzi na nie)
            is_building = (self.bot_state in [BotState.BUILD_MINE, BotState.BUILD_BELT, BotState.BUILD_BUNKER, BotState.FORTIFIER, BotState.SMELTER])

            
            if target_pos:
                # =======================================================
                # UNIWERSALNY ODBLOKOWYWACZ (Ewakuacja z placu budowy)
                # Jeśli bot ma zbudować coś na polu, na którym właśnie stoi - musi zrobić krok w bok!
                # =======================================================
                if is_building and my_pos == target_pos:
                    for try_dir in DIRECTIONS:
                        if ct.can_move(try_dir):
                            ct.move(try_dir)
                            future_pos = my_pos.add(try_dir)
                            self.path = []
                            break
                # HAMULEC: Zatrzymujemy się krok przed celem TYLKO, gdy idziemy budować.
                if not is_building or my_pos.distance_squared(target_pos) > 1:
                    
                    for _ in range(2): 
                        if not self.path: 
                            # KROK 1: Próba Zachłanna
                            greedy_dir = my_pos.direction_to(target_pos)
                            greedy_pos = my_pos.add(greedy_dir)
                            
                            out_of_bounds = not (0 <= greedy_pos.x < map_width and 0 <= greedy_pos.y < map_height)
                            
                            if out_of_bounds:
                                is_hard_obstacle = True
                            else:
                                env = ct.get_tile_env(greedy_pos)
                                memory_env = self.memory.get(greedy_pos)
                                b_id = ct.get_tile_building_id(greedy_pos)
                                b_type = ct.get_entity_type(b_id) if b_id is not None else None
                                can_walk_on_enemy = self.can_walk_on_building(b_id, my_team, ct) # type: ignore
                                is_allied_core = (b_type == EntityType.CORE and ct.get_team(b_id) == my_team)

                                # Twarda przeszkoda to: Ściana/Ruda ALBO budynek, który NIE JEST markerem i po którym nie da się chodzić
                                is_hard_obstacle = (memory_env in HARD_OBSTACLES or (env in HARD_OBSTACLES and memory_env is None) or 
                                                (b_id is not None and b_type not in passable_types and not can_walk_on_enemy and not is_allied_core))
                            
                            if not is_hard_obstacle and not out_of_bounds:
                                self.path = [greedy_dir]
                            else:
                                # KROK 2: Uderzenie w przeszkodę -> KAŻDY używa A*, żeby ładnie omijać ściany
                                self.path = self.calculate_astar_path(
                                    ct, my_pos, target_pos, map_width, map_height, my_id, my_team, 
                                    stop_adjacent=is_building # <--- Używamy zmiennej, żeby budowniczowie stawali krok przed, a zwiadowcy wchodzili na cel
                                ) or [] # Jeśli A* nie znajdzie ścieżki, zostawiamy pustą listę, żeby nie próbować chodzić w ciemno
                    
                        # FAZA WYKONANIA
                        if self.path:
                            next_dir = self.path[0]
                            next_pos = my_pos.add(next_dir)

                            # 1. Próbujemy iść optymalnie
                            if ct.can_move(next_dir):
                                ct.move(next_dir)
                                future_pos = next_pos
                                self.path.pop(0) 
                                break # Ruch wykonany, wyskakujemy z pętli range(2)

                            # 2. Nie możemy iść optymalnie bez budowania? Próbujemy zbudować drogę
                            elif ct.can_build_road(next_pos):
                                if ct.get_action_cooldown() == 0:
                                    ct.build_road(next_pos)
                                    if ct.can_move(next_dir):
                                        ct.move(next_dir)
                                        future_pos = next_pos
                                        self.path.pop(0)
                                break # Zbudowaliśmy drogę (lub czekamy na cooldown), koniec akcji w tej turze

                            # 3. Nie możemy iść optymalnie i nie możemy zbudować drogi - sprawdzamy, co nas blokuje
                            else:
                                # PYTAMY WPROST: Czy na tym polu fizycznie stoi jakiś bot?
                                if not (0 <= next_pos.x < map_width and 0 <= next_pos.y < map_height):
                                    self.path = []
                                    break
                                blocking_bot_id = ct.get_tile_builder_bot_id(next_pos)
                                
                                if blocking_bot_id is not None:
                                    # Blokuje nas ruchoma jednostka (Miękka przeszkoda)
                                    # Odpalamy unik (Reaktywne omijanie)
                                    alt_directions = sorted(DIRECTIONS, key=lambda d: my_pos.add(d).distance_squared(target_pos))
                                    
                                    for alt_dir in alt_directions:
                                        if alt_dir != next_dir and ct.can_move(alt_dir):
                                            ct.move(alt_dir)
                                            future_pos = my_pos.add(alt_dir)
                                            self.path = [] # Reset trasy, po uniku liczymy A* od nowa
                                            break
                                    else:
                                        self.path = [] # Jeśli nie udało się znaleźć żadnego wolnego pola do uniku, resetujemy trasę, żeby w następnej turze przeliczyć A* z aktualną sytuacją na mapie        
                                    
                                    break # Kończymy turę ruchu
                                else:
                                    # Blokuje nas twarda przeszkoda, której nie wykryliśmy (może to być np. nowo zbudowany budynek, którego jeszcze nie ma w pamięci)
                                    # Resetujemy trasę, żeby w następnej turze przeliczyć A* z aktualną sytuacją na mapie
                                    self.path = []
                                    break # Kończymy turę ruchu


            # ==========================================
            # 4. ZOSTAWIANIE FEROMONÓW (GOSSIP PROTOCOL)
            # ==========================================
            # Losujemy jedną nowinę z VIP Facts (tylko ważne odkrycia).
            # Wyjątek: boty w BUILD_MINE/BUILD_BELT z 50% szansą nadają rezerwację
            # swojego złoża (kanał 1) zamiast losowego VIP.
            forbidden_tiles = {my_pos, future_pos}
            # Przewidujemy też krok do przodu na następną turę:
            if self.path:
                next_planned_pos = future_pos.add(self.path[0])
                forbidden_tiles.add(next_planned_pos)

            # Szukamy miejsca na marker (wspólne dla obu gałęzi)
            PROTECTED_BUILDING_TYPES = {
                EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR,
                EntityType.SPLITTER, EntityType.HARVESTER, EntityType.FOUNDRY,
                EntityType.ROAD, EntityType.BARRIER
            }
            def find_marker_slot():
                place_pos = None
                backup_pos = None
                for adj_pos in ct.get_nearby_tiles(2):
                    if ct.can_place_marker(adj_pos):
                        b_id_adj = ct.get_tile_building_id(adj_pos)
                        if b_id_adj is not None:
                            b_type_adj = ct.get_entity_type(b_id_adj)
                            b_team_adj = ct.get_team(b_id_adj)
                            if b_team_adj == my_team and b_type_adj in PROTECTED_BUILDING_TYPES:
                                continue
                        if adj_pos not in forbidden_tiles:
                            place_pos = adj_pos
                            break
                        elif backup_pos is None and adj_pos != my_pos:
                            backup_pos = adj_pos
                return place_pos or backup_pos

            # Decydujemy co nadajemy
            emit_claim = False
            claim_ore_pos = None
            current_state_now = self.bot_state
            if current_state_now in [BotState.BUILD_MINE, BotState.BUILD_BELT]:
                claim_ore_pos = self.assigned_ore
                if claim_ore_pos is not None and random.random() < 0.5:
                    emit_claim = True

            final_pos = find_marker_slot()
            if final_pos:
                if emit_claim and claim_ore_pos is not None:
                    # Emitujemy rezerwację złoża (kanał 1)
                    ct.place_marker(final_pos, self.pack_claim_marker(current_round, claim_ore_pos))
                elif self.vip_facts:
                    # Emitujemy losowy VIP (kanał 0)
                    rep_pos = random.choice(list(self.vip_facts.keys()))
                    rep_env, rep_btype, rep_is_enemy = self.vip_facts[rep_pos]
                    ct.place_marker(final_pos, self.pack_map_marker(current_round, rep_pos, rep_env, rep_btype, rep_is_enemy))