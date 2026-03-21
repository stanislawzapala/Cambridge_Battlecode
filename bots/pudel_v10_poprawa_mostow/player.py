# Packages
# 1. Official
from cambc import Controller, Direction, EntityType, Environment, Position, Team
# 2. For random movement (for testing purposes)
import random
# 3. For priority queue (if we later want to implement A*)
import heapq
# 4. For Enum states
from enum import Enum, auto


# ==========================================
# MASZYNA STANÓW BOTA
# ==========================================
class BotState(Enum):
    EXPLORE = auto()         # Losowy zwiad i roznoszenie feromonów
    SCOUT = auto()           # WIECZNY ZWIADOWCA - tylko biega i roznosi feromony
    BUILD_MINE = auto()      # Znalazł złoże, idzie zbudować Harvester
    BUILD_BELT = auto()      # Zbudował kopalnię, ciągnie taśmociąg do Bazy/Sieci
    BUILD_DEFENSE = auto()   # (Rezerwa) Idzie postawić wieżyczkę w strategicznym miejscu
    REPAIR_NETWORK = auto()  # (Rezerwa) Idzie załatać przerwany taśmociąg
    BUILD_BUNKER = auto()    # (Rezerwa) Idzie zbudować Bunker w newralgicznym punkcie
    HARRAS = auto()          # (Rezerwa) Znalazł wroga, idzie go nękać i rozpraszać

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
passable_types = [EntityType.ROAD, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.MARKER]


class Player:
    def __init__(self):
        # CORE
        self.spawned_bots_count = 0
        self.starting_protocol = False
        self.core_facts_to_report = []
        
        # MAPA BAZY (Rdzeń + otoczenie)
        self.allied_core_tiles: set[Position] = set()
        # Pola Splitterów wokół bazy (dodatkowe cele dla wyjść mostów)
        self.allied_splitter_tiles: set[Position] = set()

        # PROBES (Builder Bot)
        # PAMIĘĆ DLA BOTÓW
        # Kluczem w słowniku będzie ID bota (int)
        self.bot_targets: dict[int, Position | None] = {}
        self.bot_paths: dict[int, list[Direction]] = {}

        # Pamięć Topograficzna (Niezmienna)
        self.bot_memory: dict[int, dict[Position, Environment]] = {}
        
        # Pamięć Taktyczna (Dynamiczna) - (Typ Budynku, Drużyna, Ostatnio Widziane w Turze)
        # Typ i Drużyna mogą być None, jeśli pole jest aktualnie puste.
        self.bot_buildings: dict[int, dict[Position, tuple[EntityType | None, Team | None, int]]] = {}
        
        # Lista VIP: słownik (pos -> (env, b_type, is_enemy)) dla każdego bota
        self.vip_facts: dict[int, dict[Position, tuple[Environment, EntityType | None, bool]]] = {}

        # Maszyna Stanów: W jakim trybie jest obecnie dany bot?
        self.bot_states: dict[int, BotState] = {}

        # Węzeł, od którego bot aktualnie buduje sieć mostów
        self.last_bridge_node: dict[int, Position] = {}
        # Historia węzłów bieżącej nitki mostów (do wykrywania pętli)
        self.belt_chain: dict[int, set[Position]] = {}
        # Pole Splittera do zbudowania w następnej turze po wylądowaniu mostu
        # (bot nie może zbudować mostu i Splittera w tej samej turze)
        self.pending_splitter: dict[int, tuple[Position, Direction] | None] = {}
       

    def calculate_astar_path(self, ct: Controller, start: Position, target: Position, w: int, h: int, bot_id: int, my_team: Team, stop_adjacent: bool = False) -> list[Direction] | None:
        """
        Zwraca listę kierunków za pomocą optymistycznego Frontier A* (Frontier A-Star). 
        Możemy ustawić stop_adjacent=True, jeśli chcemy, żeby bot zatrzymał się na polu obok celu (przydatne np. do budowania).
        Możemy dodać blocked_directions, czyli listę kierunków, których bot ma unikać.
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
            if iterations > 300:
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
                    
                    memory_env = self.bot_memory[bot_id].get(next_pos)
                    if memory_env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                        continue # Pamiętamy, że tu jest mur lub ruda, omijamy!
                    
                    is_blocked = False

                    # 1. OPTYMISTYCZNE SPRAWDZANIE MGŁY WOJNY
                    if ct.is_in_vision(next_pos):
                        env = ct.get_tile_env(next_pos)
                        b_id = ct.get_tile_building_id(next_pos)
                        
                        # Twarde przeszkody (Ściany i Rudy)
                        if env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                            is_blocked = True
                        
                        # Budynki
                        elif b_id is not None:
                            b_type = ct.get_entity_type(b_id)
                            
                            # Jeśli to nie jest droga/taśmociąg i nie jest to nasz Rdzeń, to nas blokuje
                            if b_type not in passable_types and b_type != EntityType.CORE:
                                is_blocked = True
                            # Wrogi rdzeń też blokuje
                            elif b_type == EntityType.CORE and ct.get_team(b_id) != my_team:
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
        """Sprawdza, czy można chodzić po budynku wroga (droga/taśmociąg/pancerna taśma)."""
        if b_id is None:
            return False
        b_type = ct.get_entity_type(b_id)
        return b_type in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.ROAD]
    

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
            data['priority'] = payload & 0b111
            data['command_id'] = (payload >> 3) & 0b1111
            
        return data


    def find_nearest_vip_target(self, my_pos: Position, vip_facts: dict, 
                                target_envs: list[Environment] = None, 
                                target_btypes: list[EntityType] = None, 
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


    def run(self, ct: Controller) -> None:
        # Current round (for memory timestamping)
        current_round = ct.get_current_round()
        
        # Cache map dimensions and team to avoid repeated API calls
        map_width = ct.get_map_width()
        map_height = ct.get_map_height()
        my_team = ct.get_team()
        enemy_team = Team.B if my_team == Team.A else Team.A
        
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
                    elif env in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
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
            
            # C) PRODUKCJA BOTÓW
            if self.spawned_bots_count < 10 and ct.get_action_cooldown() == 0:
                spawn_pos = ct.get_position().add(random.choice(DIRECTIONS))
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.spawned_bots_count += 1
            return
        


        # ==========================================
        # 2. LOGIKA PROBY (BUILDER_BOT)
        # ==========================================
        elif etype == EntityType.BUILDER_BOT:
            
            # INICJALIZACJA PAMIĘCI
            if my_id not in self.bot_targets:
                # Cel i trasa ruchu proby
                self.bot_targets[my_id] = None
                self.bot_paths[my_id] = []
                # Mapa topograficzna (Environment)
                self.bot_memory[my_id] = {}
                # Mapa budynkow (Typ Budynku + Drużyna + Timestamp Ostatniego Widzenia)
                self.bot_buildings[my_id] = {}
                # Najważniejsze odkrycia
                self.vip_facts[my_id] = {}
                
                # Początkowy stan — zawsze EXPLORE
                self.bot_states[my_id] = BotState.EXPLORE
                self.pending_splitter[my_id] = None
                self.belt_chain[my_id] = set()
            
            
            # ==========================================
            # 1. SKANOWANIE I AKTUALIZACJA MAPY W PAMIĘCI
            # ==========================================
            for pos in ct.get_nearby_tiles():
                # 1. PAMIĘĆ STATYCZNA (Teren - to się nigdy nie zmienia)
                if pos not in self.bot_memory[my_id]:
                    env = ct.get_tile_env(pos)
                    if env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                        self.bot_memory[my_id][pos] = env
                        # Jeśli to ważne odkrycie (ściana lub ruda), dodajemy do VIP Facts
                        if env in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                            self.vip_facts[my_id][pos] = (env, None, False)
                    
                # 2. PAMIĘĆ DYNAMICZNA i ODCZYT FEROMONÓW (BUDYNKI + MARKERY)
                b_id = ct.get_tile_building_id(pos)
                if b_id is not None:
                    # Ktoś tu coś zbudował (lub budynek nadal stoi) -> Nadpisujemy
                    b_type = ct.get_entity_type(b_id)
                    b_team = ct.get_team(b_id)
                    self.bot_buildings[my_id][pos] = (b_type, b_team, current_round)
                    
                    # >>> Zapisujemy kafelki naszej bazy (widzimy je zaraz po spawnie) <<<
                    if b_type == EntityType.CORE and b_team == my_team:
                        self.allied_core_tiles.add(pos)
                    # >>> Zapisujemy nasze Splittery wokół bazy <<<
                    if b_type == EntityType.SPLITTER and b_team == my_team:
                        self.allied_splitter_tiles.add(pos)

                    # --- KTO WCHODZI NA LISTĘ VIP? ---
                    # Wyciągamy PRAWDZIWY teren z pamięci (żeby nie nadpisać rudy pustką!)
                    real_env = self.bot_memory[my_id].get(pos, ct.get_tile_env(pos))
                    
                    # 1. WSZYSTKIE budynki wroga
                    if b_team == enemy_team:
                        JUNK_ENEMY_BUILDINGS = [EntityType.ROAD, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE]
                        if b_type not in JUNK_ENEMY_BUILDINGS:
                            self.vip_facts[my_id][pos] = (real_env, b_type, True)
                    
                    # 2. NASZE strategiczne budynki (Kopalnie, Wieże, Huty)
                    elif b_team == my_team:
                        VIP_FRIENDLY = [EntityType.HARVESTER, EntityType.FOUNDRY, EntityType.GUNNER, EntityType.SENTINEL, EntityType.BREACH, EntityType.LAUNCHER]
                        if b_type in VIP_FRIENDLY:
                            self.vip_facts[my_id][pos] = (real_env, b_type, False)

                    # CZY TO NASZ MARKER? (Rozpakowujemy informację)
                    if b_type == EntityType.MARKER and b_team == my_team:
                        marker_val = ct.get_marker_value(b_id)
                        data = self.unpack_marker(marker_val)
                        
                        if data['type'] == 0:  # KANAŁ 0: AKTUALIZACJA MAPY
                            m_pos = data['pos']
                            m_turn = data['turn']
                            
                            # A) Aktualizujemy teren z markera (jeśli go jeszcze nie znamy)
                            if m_pos not in self.bot_memory[my_id] and data['env'] in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                                self.bot_memory[my_id][m_pos] = data['env']
                            
                            # B) Aktualizujemy budynki z markera (Zabezpieczenie Timestampem!)
                            known_b = self.bot_buildings[my_id].get(m_pos)
                            last_seen = known_b[2] if known_b else -1
                            
                            if m_turn > last_seen:
                                m_team = enemy_team if data['is_enemy'] else my_team
                                if not data['b_type']: m_team = None
                                self.bot_buildings[my_id][m_pos] = (data['b_type'], m_team, m_turn)

                                # --- KOMPLEKSOWA AKTUALIZACJA VIP FACTS ---
                                real_env_marker = self.bot_memory[my_id].get(m_pos, data['env'])

                                if data['b_type'] is not None:
                                    # Marker mówi, że ktoś coś tu zbudował
                                    if data['is_enemy']:
                                        JUNK_ENEMY_BUILDINGS = [EntityType.ROAD, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE]
                                        if data['b_type'] not in JUNK_ENEMY_BUILDINGS:
                                            self.vip_facts[my_id][m_pos] = (real_env_marker, data['b_type'], True)
                                    else:
                                        # To NASZ budynek
                                        VIP_FRIENDLY = [EntityType.HARVESTER, EntityType.FOUNDRY, EntityType.GUNNER, EntityType.SENTINEL, EntityType.BREACH, EntityType.LAUNCHER]
                                        if data['b_type'] in VIP_FRIENDLY:
                                            self.vip_facts[my_id][m_pos] = (real_env_marker, data['b_type'], False)
                                else:
                                    # Marker mówi, że na polu NIE MA budynku. Czy pod spodem jest ruda?
                                    if data['env'] in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                                        self.vip_facts[my_id][m_pos] = (data['env'], None, False)
                                    elif m_pos in self.vip_facts[my_id]:
                                        # Jeśli to zwykły pusty piach, czyścimy z VIP
                                        del self.vip_facts[my_id][m_pos]

                else:
                    # Pole jest PUSTE. Usuwamy z pamięci budynków, jeśli wcześniej był tam jakiś budynek
                    self.bot_buildings[my_id][pos] = (None, None, current_round) # Oznaczamy jako puste z aktualnym timestampem
                    
                    if pos in self.vip_facts[my_id]:
                        # Budynku nie ma. Ale czy pod spodem jest ruda?
                        env_here = self.bot_memory[my_id].get(pos, Environment.EMPTY)
                        if env_here in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                            # Zostawiamy/przywracamy informację o samej rudzie
                            self.vip_facts[my_id][pos] = (env_here, None, False)
                        else:
                            # To był budynek na pustym polu i został zniszczony. Kasujemy ducha.
                            del self.vip_facts[my_id][pos]

            
            # ==========================================
            # 2. OBSŁUGA SPLITTERÓW (niezależna od stanu, od tury 7)
            # ==========================================
            # Od tury 7 każdy bot sprawdza czy wszystkie Splittery wokół bazy stoją.
            # Jeśli brakuje:
            #   - bot stoi przy odpowiednim polu Core → buduje od razu
            #   - bot jest w stanie EXPLORE i nie ma aktualnego celu → idzie do Core żeby zbudować
            if current_round >= 7 and self.allied_core_tiles:
                core_xs = [p.x for p in self.allied_core_tiles]
                core_ys = [p.y for p in self.allied_core_tiles]
                cx = (min(core_xs) + max(core_xs)) // 2
                cy = (min(core_ys) + max(core_ys)) // 2

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
                    sp_pos = Position(cx + ddx, cy + ddy)
                    if not (0 <= sp_pos.x < map_width and 0 <= sp_pos.y < map_height):
                        continue
                    sp_env = self.bot_memory[my_id].get(sp_pos, ct.get_tile_env(sp_pos) if ct.is_in_vision(sp_pos) else Environment.EMPTY)
                    if sp_env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
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
                    if my_pos.distance_squared(sp_pos) <= 2 and ct.get_action_cooldown() == 0:
                        # Jesteśmy przy nim — budujemy od razu
                        if ct.can_destroy(sp_pos):
                            ct.destroy(sp_pos)
                        if ct.can_build_splitter(sp_pos, faces):
                            ct.build_splitter(sp_pos, faces)
                            self.allied_splitter_tiles.add(sp_pos)
                            break
                    elif self.bot_states[my_id] == BotState.EXPLORE and self.bot_targets[my_id] not in self.allied_core_tiles:
                        # Jesteśmy w EXPLORE i nie idziemy już do Core — wysyłamy się do pola Core
                        # z którego można zbudować ten Splitter
                        for core_tile in self.allied_core_tiles:
                            if core_tile.distance_squared(sp_pos) <= 2:
                                self.bot_targets[my_id] = core_tile
                                self.bot_paths[my_id] = []
                                break
                        break  # Jeden brakujący Splitter na raz wystarczy

            # ==========================================
            # 3. MASZYNA STANÓW (MÓZG) - Decyzje i Akcje
            # ==========================================
            current_state = self.bot_states[my_id]

            # PRIORYTET: pending_splitter — bot zapamiętał w poprzedniej turze że musi
            # zbudować Splitter (nie mógł tego zrobić razem z mostem — osobny cooldown).
            # Obsługujemy to przed całą resztą maszyny stanów.
            if self.pending_splitter[my_id] is not None:
                pend_pos, pend_dir = self.pending_splitter[my_id]
                # Sprawdzamy czy Splitter już stoi (inny bot mógł go zbudować)
                b_id_pend = ct.get_tile_building_id(pend_pos) if ct.is_in_vision(pend_pos) else None
                if b_id_pend is not None and ct.get_entity_type(b_id_pend) == EntityType.SPLITTER:
                    # Już stoi — czyścimy i działamy normalnie
                    self.pending_splitter[my_id] = None
                elif ct.get_action_cooldown() == 0 and my_pos.distance_squared(pend_pos) <= 2:
                    # Możemy budować — ewentualnie niszczymy marker i stawiamy Splitter
                    if ct.can_destroy(pend_pos):
                        ct.destroy(pend_pos)
                    if ct.can_build_splitter(pend_pos, pend_dir):
                        ct.build_splitter(pend_pos, pend_dir)
                        self.allied_splitter_tiles.add(pend_pos)
                    self.pending_splitter[my_id] = None
                    # Kończymy turę — Splitter zbudowany, ruch zostawiamy sekcji RUCH
                else:
                    # Cooldown > 0 lub za daleko — czekamy, nie robimy nic innego
                    pass
            
            elif current_state == BotState.SCOUT:
                target_pos = self.bot_targets[my_id]
                
                # ZABEZPIECZENIE: Sprawdzamy z pamięci, czy cel nie wypadł w skale
                target_is_wall = target_pos and self.bot_memory[my_id].get(target_pos) in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]
                
                # Wieczny zwiad - resetujemy cel, jeśli doszliśmy, nie mamy go, ALBO jest on w ścianie!
                if not target_pos or my_pos == target_pos or target_is_wall:
                    self.bot_targets[my_id] = Position(random.randint(0, map_width - 1), random.randint(0, map_height - 1))
                    self.bot_paths[my_id] = []

            elif current_state == BotState.EXPLORE:
                found_ore_pos = None
                if not self.bot_targets[my_id] or current_round % 5 == 0:
                    # Szuka pustej rudy
                    found_ore_pos = self.find_nearest_vip_target(
                        my_pos, 
                        self.vip_facts[my_id], 
                        target_envs=[Environment.ORE_TITANIUM, Environment.ORE_AXIONITE],
                        ownership='empty'
                    )
                if found_ore_pos is not None:
                    self.bot_states[my_id] = BotState.BUILD_MINE
                    self.bot_targets[my_id] = found_ore_pos
                    self.bot_paths[my_id] = []
                        
                # Jeśli nadal eksploruje i nie ma celu (lub dotarł do celu), losuje nowy
                if self.bot_states[my_id] == BotState.EXPLORE:
                    if not self.bot_targets[my_id] or my_pos == self.bot_targets[my_id]:
                        self.bot_targets[my_id] = Position(random.randint(0, map_width - 1), random.randint(0, map_height - 1))
                        self.bot_paths[my_id] = []

            elif current_state == BotState.BUILD_MINE:
                target_pos = self.bot_targets[my_id]

                # 0. ZABEZPIECZENIE: Jeśli zgubiliśmy cel (np. A* skasowało go z powodu braku drogi)
                if not target_pos:
                    self.bot_states[my_id] = BotState.EXPLORE
                    self.bot_paths[my_id] = []
                else:
                    # 1. SANITY CHECK: Czy ktoś nas ubiegł?
                    b_type, b_team, _ = self.bot_buildings[my_id].get(target_pos, (None, None, -1))
                    if b_type is not None and b_type != EntityType.MARKER:
                        # Cel zajęty, wracamy do zwiadu
                        self.bot_states[my_id] = BotState.EXPLORE
                        self.bot_targets[my_id] = None
                        self.bot_paths[my_id] = []
                    
                    # 2. Jesteśmy przy rudzie? BUDUJEMY!
                    elif my_pos.distance_squared(target_pos) <= 2:
                        if ct.get_action_cooldown() == 0:
                            if ct.can_build_harvester(target_pos):
                                ct.build_harvester(target_pos)
                                
                                if target_pos in self.vip_facts[my_id]:
                                    env = self.vip_facts[my_id][target_pos][0]
                                    self.vip_facts[my_id][target_pos] = (env, EntityType.HARVESTER, False)
                                
                                self.bot_states[my_id] = BotState.BUILD_BELT
                                self.last_bridge_node[my_id] = target_pos
                                self.bot_targets[my_id] = target_pos
                                self.belt_chain[my_id] = set()  # wypełniany przy budowie każdego mostu
                        else:
                            # Czekamy na cooldown. Kasujemy path, żeby przypadkiem nie chodzić wokół rudy.
                            self.bot_paths[my_id] = []
                            # Nie ruszamy target_pos, żeby bot wiedział, gdzie ma stać
                        

            elif current_state == BotState.BUILD_BELT:
                # last_node to punkt, NA KTÓRYM stoi ostatni most (lub Harvester na początku).
                # Zasoby wychodzą Z last_node i trafiają na pole best_end.
                # Następny most budujemy DOKŁADNIE na best_end, żeby odebrać te zasoby.
                last_node = self.last_bridge_node.get(my_id)
                
                if not self.allied_core_tiles or not last_node:
                    self.bot_states[my_id] = BotState.EXPLORE
                    self.bot_targets[my_id] = None
                else:
                    # --- PRIORYTET: pending_splitter ---
                    # Jeśli w poprzedniej turze most wylądował na polu Splittera i Splitter
                    # tam jeszcze nie stoi, budujemy go teraz (zanim cokolwiek innego).
                    pending = self.pending_splitter.get(my_id)
                    if pending is not None:
                        pend_pos, pend_dir = pending
                        # Sprawdzamy czy Splitter już stoi (mógł go zbudować inny bot)
                        b_id_pend = ct.get_tile_building_id(pend_pos) if ct.is_in_vision(pend_pos) else None
                        splitter_there = (b_id_pend is not None and ct.get_entity_type(b_id_pend) == EntityType.SPLITTER)
                        if splitter_there:
                            # Stoi — czyścimy i idziemy dalej
                            self.pending_splitter[my_id] = None
                        elif ct.get_action_cooldown() == 0 and my_pos.distance_squared(pend_pos) <= 2:
                            # Możemy budować — niszczymy ewentualny marker i stawiamy Splitter
                            if ct.can_destroy(pend_pos):
                                ct.destroy(pend_pos)
                            if ct.can_build_splitter(pend_pos, pend_dir):
                                ct.build_splitter(pend_pos, pend_dir)
                                self.allied_splitter_tiles.add(pend_pos)
                            self.pending_splitter[my_id] = None
                        else:
                            # Cooldown > 0 lub za daleko — czekamy, nie ruszamy się
                            self.bot_paths[my_id] = []
                            # (sekcja RUCH nie zadziała bo bot_targets wskazuje na pend_pos
                            # i distance_squared <= 2, więc hamulec zatrzyma bota)

                    # delivery_tiles: pola Core + Splittery
                    delivery_tiles = self.allied_core_tiles | self.allied_splitter_tiles

                    # Centrum Core — stały punkt odniesienia
                    core_xs = [p.x for p in self.allied_core_tiles]
                    core_ys = [p.y for p in self.allied_core_tiles]
                    core_cx = (min(core_xs) + max(core_xs)) // 2
                    core_cy = (min(core_ys) + max(core_ys)) // 2
                    core_center = Position(core_cx, core_cy)

                    # ---- KROK 1: Znajdź najbliższe wejście do naszej sieci ----
                    # Kwalifikuje się tylko budynek który płynie KU Core:
                    # jego wyjście (bridge_target / output) jest bliżej Core niż on sam.
                    # Gwarantuje to że wpięcie nie stworzy pętli.
                    network_entry_types = {EntityType.BRIDGE, EntityType.CONVEYOR,
                                           EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER}
                    nearest_entry = None
                    nearest_entry_dist = float('inf')
                    for pos, (b_type, b_team, _) in self.bot_buildings[my_id].items():
                        if b_team != my_team or b_type not in network_entry_types:
                            continue
                        if pos == last_node:
                            continue
                        # Sprawdzamy kierunek tylko gdy budynek jest w zasięgu wzroku
                        if not ct.is_in_vision(pos):
                            continue
                        b_id_check = ct.get_tile_building_id(pos)
                        if b_id_check is None:
                            continue
                        # Wyjście budynku musi być bliżej Core niż on sam
                        flows_toward_core = False
                        try:
                            if b_type == EntityType.BRIDGE:
                                bt = ct.get_bridge_target(b_id_check)
                                # Wyjście musi być bliżej Core niż wejście
                                # ORAZ nie może prowadzić z powrotem na last_node (pętla 2-mostów)
                                if bt.distance_squared(core_center) < pos.distance_squared(core_center) and bt != last_node:
                                    flows_toward_core = True
                            elif b_type in {EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR}:
                                out = pos.add(ct.get_direction(b_id_check))
                                if out.distance_squared(core_center) < pos.distance_squared(core_center) and out != last_node:
                                    flows_toward_core = True
                            elif b_type == EntityType.SPLITTER:
                                # Splittery zawsze przy Core — zawsze płyną ku Core
                                flows_toward_core = True
                        except Exception:
                            pass
                        if not flows_toward_core:
                            continue
                        d = last_node.distance_squared(pos)
                        if d < nearest_entry_dist:
                            nearest_entry_dist = d
                            nearest_entry = pos

                    # ---- KROK 2: Metryka zawsze minimalizuje odległość do Core ----
                    # nearest_entry jest używane w KROKU 4 do wykrycia zakończenia misji.

                    # ---- KROK 4: Sprawdź czy misja zakończona ----
                    # Zakończona gdy last_node dotarł do delivery_tiles LUB jest naszym budynkiem sieci
                    if self.pending_splitter.get(my_id) is None:
                        mission_done = last_node in delivery_tiles
                        if not mission_done and ct.is_in_vision(last_node):
                            b_id_ln = ct.get_tile_building_id(last_node)
                            if b_id_ln is not None and ct.get_team(b_id_ln) == my_team:
                                if ct.get_entity_type(b_id_ln) in network_entry_types:
                                    mission_done = True
                        if mission_done:
                            self.bot_states[my_id] = BotState.EXPLORE
                            self.bot_targets[my_id] = None
                            self.belt_chain[my_id] = set()

                    if self.bot_states[my_id] == BotState.BUILD_BELT:
                        best_start = None
                        best_end = None
                        min_dist_to_target = float('inf')

                        last_node_env = self.bot_memory[my_id].get(last_node, ct.get_tile_env(last_node) if ct.is_in_vision(last_node) else Environment.EMPTY)
                        last_node_is_ore = last_node_env in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]

                        if last_node_is_ore:
                            candidate_starts = [last_node.add(d_start) for d_start in ORTHOGONAL_DIRECTIONS]
                        else:
                            candidate_starts = [last_node]

                        for start_pos in candidate_starts:
                            if not (0 <= start_pos.x < map_width and 0 <= start_pos.y < map_height):
                                continue
                            start_env = self.bot_memory[my_id].get(start_pos, ct.get_tile_env(start_pos) if ct.is_in_vision(start_pos) else Environment.EMPTY)
                            if start_env in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE, Environment.WALL]:
                                continue

                            for dx in range(-3, 4):
                                for dy in range(-3, 4):
                                    end_pos = Position(start_pos.x + dx, start_pos.y + dy)

                                    if not (0 <= end_pos.x < map_width and 0 <= end_pos.y < map_height):
                                        continue
                                    if start_pos.distance_squared(end_pos) > 9 or start_pos == end_pos:
                                        continue

                                    # ---- KROK 5: Walidacja end_pos ----
                                    # Akceptowalne:
                                    # (A) delivery_tiles (Core/Splitter) — zawsze OK
                                    # (B) nasz budynek sieci (wejście do istniejącej sieci) — OK
                                    # (C) wolne pole — nie przy Core, nie ściana/ruda
                                    # W każdym przypadku end_pos musi zbliżać nas do final_target

                                    end_is_valid = False

                                    if end_pos in delivery_tiles:
                                        # (A)
                                        end_is_valid = True
                                    elif ct.is_in_vision(end_pos):
                                        b_id_end = ct.get_tile_building_id(end_pos)
                                        if b_id_end is not None and ct.get_team(b_id_end) == my_team:
                                            if ct.get_entity_type(b_id_end) in network_entry_types:
                                                # (B) wejście do sieci — akceptowalne jeśli zbliża do Core
                                                if end_pos.distance_squared(core_center) < last_node.distance_squared(core_center):
                                                    end_is_valid = True
                                        elif b_id_end is None:
                                            # (C) puste, widoczne
                                            end_env = self.bot_memory[my_id].get(end_pos, ct.get_tile_env(end_pos))
                                            if end_env not in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE, Environment.WALL]:
                                                near_core = any(end_pos.distance_squared(ct_) <= 2 for ct_ in self.allied_core_tiles)
                                                if not near_core:
                                                    end_is_valid = True
                                    else:
                                        # (C) poza zasięgiem wzroku
                                        end_env = self.bot_memory[my_id].get(end_pos, Environment.EMPTY)
                                        if end_env not in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE, Environment.WALL]:
                                            near_core = any(end_pos.distance_squared(ct_) <= 2 for ct_ in self.allied_core_tiles)
                                            if not near_core:
                                                end_is_valid = True

                                    if not end_is_valid:
                                        continue

                                    # FILTR ANTY-PĘTLOWY: jeśli end_pos jest już w historii
                                    # tej nitki mostów, prowadzi to do pętli — odrzucamy
                                    if end_pos in self.belt_chain.get(my_id, set()):
                                        continue

                                    # Metryka: zawsze minimalizujemy odległość do core_center.
                                    # final_target wpływa tylko na walidację end_pos (case B),
                                    # nie na metrykę — bot zawsze posuwa się ku Core.
                                    d = end_pos.distance_squared(core_center)
                                    if d < min_dist_to_target:
                                        min_dist_to_target = d
                                        best_start = start_pos
                                        best_end = end_pos
                        
                        # --- FAZA WYKONANIA ---
                        if best_start and best_end:
                            self.bot_targets[my_id] = best_start

                            # SYTUACJA 1: Bot stoi centralnie na polu, z którego chce zacząć budować most
                            if my_pos == best_start:
                                # Musimy z niego zejść! Robimy krok obok (najlepiej w kierunku końca mostu)
                                step_dir = my_pos.direction_to(best_end)
                                if ct.can_move(step_dir):
                                    ct.move(step_dir)
                                    self.bot_paths[my_id] = [] # Resetujemy A*, żeby system ruchu nas nie cofnął

                            # SYTUACJA 2: Bot stoi idealnie, obok pola startowego (odległość 1)
                            elif my_pos.distance_squared(best_start) <= 2:
                                
                                # KROK A: Czyszczenie terenu (DARMOWA AKCJA)
                                if ct.can_destroy(best_start):
                                    ct.destroy(best_start)
                                
                                # KROK B: Właściwa budowa mostu (W TEJ SAMEJ TURZE)
                                if ct.get_action_cooldown() == 0:
                                    if ct.can_build_bridge(best_start, best_end):
                                        ct.build_bridge(best_start, best_end)
                                        self.last_bridge_node[my_id] = best_end
                                        self.bot_targets[my_id] = best_end
                                        self.belt_chain[my_id].add(best_start)
                                        self.belt_chain[my_id].add(best_end)
                                        # KROK C: Jeśli most wylądował na planowanym polu Splittera
                                        # i Splittera tam jeszcze nie ma — zapamiętujemy żeby zbudować
                                        # go w następnej turze (cooldown nie pozwala w tej samej).
                                        if best_end in self.allied_splitter_tiles:
                                            b_id_end = ct.get_tile_building_id(best_end) if ct.is_in_vision(best_end) else None
                                            splitter_there = (b_id_end is not None and ct.get_entity_type(b_id_end) == EntityType.SPLITTER)
                                            if not splitter_there:
                                                # Obliczamy kierunek Splittera
                                                core_xs = [p.x for p in self.allied_core_tiles]
                                                core_ys = [p.y for p in self.allied_core_tiles]
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
                                                    if best_end == Position(sp_cx + ddx, sp_cy + ddy):
                                                        self.pending_splitter[my_id] = (best_end, faces)
                                                        break

                            # SYTUACJA 3: Bot jest za daleko
                            else:
                                pass
                                
                        else:
                            # Kompletny ślepy zaułek - nie da się pociągnąć mostu z last_node.
                            self.bot_states[my_id] = BotState.EXPLORE
                            self.bot_targets[my_id] = None

                


            # ==========================================
            # 3. RUCH (NOGI) - Wykonuje się tylko, gdy mamy gdzie iść
            # ==========================================
            future_pos = my_pos
            target_pos = self.bot_targets[my_id]
            
            # Wizualizacja
            if target_pos:
                try:
                    ct.draw_indicator_dot(target_pos, 255, 255, 0) # type: ignore
                    ct.draw_indicator_line(my_pos, target_pos, 0, 200, 255) # type: ignore
                except Exception:
                    pass

            # Czy bot idzie budować? (zatrzymuje się krok przed celem, nie wchodzi na nie)
            is_building = (self.bot_states[my_id] in [BotState.BUILD_MINE, BotState.BUILD_BELT])

            # HAMULEC: Zatrzymujemy się krok przed celem TYLKO, gdy idziemy budować.
            # Zwiadowcy muszą wejść na sam punkt, żeby go zresetować!
            if target_pos:
                if not is_building or my_pos.distance_squared(target_pos) > 2:
                    
                    for _ in range(2): 
                        if not self.bot_paths[my_id]: 
                            # KROK 1: Próba Zachłanna
                            greedy_dir = my_pos.direction_to(target_pos)
                            greedy_pos = my_pos.add(greedy_dir)
                            
                            out_of_bounds = not (0 <= greedy_pos.x < map_width and 0 <= greedy_pos.y < map_height)
                            
                            if out_of_bounds:
                                is_hard_obstacle = True
                            else:
                                env = ct.get_tile_env(greedy_pos)
                                memory_env = self.bot_memory[my_id].get(greedy_pos)
                                b_id = ct.get_tile_building_id(greedy_pos)
                                b_type = ct.get_entity_type(b_id) if b_id is not None else None
                                can_walk_on_enemy = self.can_walk_on_building(b_id, my_team, ct) # type: ignore
                                is_allied_core = (b_type == EntityType.CORE and ct.get_team(b_id) == my_team)

                                # Twarda przeszkoda to: Ściana/Ruda ALBO budynek, który NIE JEST markerem i po którym nie da się chodzić
                                is_hard_obstacle = (memory_env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE] or 
                                                (env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE] and memory_env is None) or 
                                                (b_id is not None and b_type not in passable_types and not can_walk_on_enemy and not is_allied_core))
                            
                            if not is_hard_obstacle and not out_of_bounds:
                                self.bot_paths[my_id] = [greedy_dir]
                            else:
                                # KROK 2: Uderzenie w przeszkodę -> KAŻDY używa A*, żeby ładnie omijać ściany
                                self.bot_paths[my_id] = self.calculate_astar_path(
                                    ct, my_pos, target_pos, map_width, map_height, my_id, my_team, 
                                    stop_adjacent=is_building # <--- Używamy zmiennej, żeby budowniczowie stawali krok przed, a zwiadowcy wchodzili na cel
                                ) or [] # Jeśli A* nie znajdzie ścieżki, zostawiamy pustą listę, żeby nie próbować chodzić w ciemno
                    
                        # FAZA WYKONANIA
                        if self.bot_paths[my_id]:
                            next_dir = self.bot_paths[my_id][0]
                            next_pos = my_pos.add(next_dir)

                            # 1. Próbujemy iść optymalnie
                            if ct.can_move(next_dir):
                                ct.move(next_dir)
                                future_pos = next_pos
                                self.bot_paths[my_id].pop(0) 
                                break # Ruch wykonany, wyskakujemy z pętli range(2)

                            # 2. Nie możemy iść optymalnie bez budowania? Próbujemy zbudować drogę
                            elif ct.can_build_road(next_pos):
                                if ct.get_action_cooldown() == 0:
                                    ct.build_road(next_pos)
                                    if ct.can_move(next_dir):
                                        ct.move(next_dir)
                                        future_pos = next_pos
                                        self.bot_paths[my_id].pop(0)
                                break # Zbudowaliśmy drogę (lub czekamy na cooldown), koniec akcji w tej turze

                            # 3. Nie możemy iść optymalnie i nie możemy zbudować drogi - sprawdzamy, co nas blokuje
                            else:
                                # PYTAMY WPROST: Czy na tym polu fizycznie stoi jakiś bot?
                                if not (0 <= next_pos.x < map_width and 0 <= next_pos.y < map_height):
                                    self.bot_paths[my_id] = []
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
                                            self.bot_paths[my_id] = [] # Reset trasy, po uniku liczymy A* od nowa
                                            break
                                    else:
                                        self.bot_paths[my_id] = [] # Jeśli nie udało się znaleźć żadnego wolnego pola do uniku, resetujemy trasę, żeby w następnej turze przeliczyć A* z aktualną sytuacją na mapie        
                                    
                                    break # Kończymy turę ruchu
                                else:
                                    # Blokuje nas twarda przeszkoda, której nie wykryliśmy (może to być np. nowo zbudowany budynek, którego jeszcze nie ma w pamięci)
                                    # Resetujemy trasę, żeby w następnej turze przeliczyć A* z aktualną sytuacją na mapie
                                    self.bot_paths[my_id] = []
                                    break # Kończymy turę ruchu


            # ==========================================
            # 4. ZOSTAWIANIE FEROMONÓW (GOSSIP PROTOCOL)
            # ==========================================
            # Losujemy jedną nowinę z VIP Facts (tylko ważne odkrycia)
            forbidden_tiles = {my_pos, future_pos}
            # Przewidujemy też krok do przodu na następną turę:
            if self.bot_paths[my_id]:
                next_planned_pos = future_pos.add(self.bot_paths[my_id][0])
                forbidden_tiles.add(next_planned_pos)

            if self.vip_facts[my_id]:
                rep_pos = random.choice(list(self.vip_facts[my_id].keys()))
                rep_env, rep_btype, rep_is_enemy = self.vip_facts[my_id][rep_pos]
                
                # Szukamy miejsca w JEDNYM przebiegu
                place_pos = None
                backup_pos = None
                
                for adj_pos in ct.get_nearby_tiles(2):
                    if ct.can_place_marker(adj_pos):
                        if adj_pos not in forbidden_tiles:
                            place_pos = adj_pos
                            break # Mamy ideał, kończymy pętlę!
                        elif backup_pos is None and adj_pos != my_pos:
                            backup_pos = adj_pos # Zapisujemy Plan B, ale szukamy dalej
                
                # Używamy ideału, a jak go nie ma (None), bierzemy Plan B
                final_pos = place_pos or backup_pos
                
                if final_pos:
                    ct.place_marker(final_pos, self.pack_map_marker(current_round, rep_pos, rep_env, rep_btype, rep_is_enemy))
