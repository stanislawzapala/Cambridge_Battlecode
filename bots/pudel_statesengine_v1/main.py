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








class Player:
    def __init__(self):
        # CORE
        self.spawned_bots_count = 0
        self.starting_protocol = False
        self.core_facts_to_report = []
        

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


    def calculate_astar_path(self, ct: Controller, start: Position, target: Position, w: int, h: int, bot_id: int, my_team: Team) -> list[Direction] | None:
        """
        Zwraca listę kierunków za pomocą optymistycznego A* (A-Star).
        """
        
        # Kolejka priorytetowa: trzyma krotki (priorytet, koszt_do_tej_pory, x, y, pozycja)
        queue = []
        heapq.heappush(queue, (0, 0, start.x, start.y, start))
        
        came_from = {start: None}
        cost_so_far = {start: 0}
        iterations = 0
        
        
        # Najpierw posortujmy kierunki tak, aby te najbliżej celu (minimalny dystans do targetu) były pierwsze - wyciągamy tylko pierwszy kierunek
        DIRECTIONS_PREFERENCE = sorted(DIRECTIONS, key=lambda d: start.add(d).distance_squared(target))

        while queue:
            iterations += 1
            if iterations > 1500:
                return None
            
            # Wyciągamy kafelek, który ma NAJLEPSZY priorytet (najbliżej celu)
            priority, current_cost, _, _, curr = heapq.heappop(queue)

            if curr == target:
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
                            passable_types = [EntityType.ROAD, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]
                            
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
        if target not in came_from:
            return None 

        path = []
        curr = target
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
        if ct.get_team(b_id) == my_team:  # Nasz budynek - nie liczy się
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
        # 1. LOGIKA BAZY (CORE) - na razie tylko produkcja probek
        # ==========================================
        if etype == EntityType.CORE:
            # PROTOKÓŁ ROZRUCHOWY 
            # Jednorazowo
            if not self.starting_protocol:
                found_walls = []
                found_ores = []

                for pos in ct.get_nearby_tiles():
                    env = ct.get_tile_env(pos)
                    # Rozdzielamy ściany od priorytetowych złóż
                    if env == Environment.WALL:
                        found_walls.append((pos, env, None, False))
                    elif env in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                        found_ores.append((pos, env, None, False))
                
                # Łączymy listy. Rudy są na końcu, więc .pop() zdejmie je jako pierwsze!
                self.core_facts_to_report = found_walls + found_ores
                self.starting_protocol = True
            
            # B) DYREKTYWA SYNAPSA ZER (cokolwiek to jest) - Zostawiamy ślady o najważniejszych odkryciach z protokołu rozruchowego (ściany i rudy)
            # Dopóki nie wyczerpiemy listy, bot będzie zostawiał markery z informacjami o tych kluczowych pozycjach
            if self.core_facts_to_report:
                # Patrzymy na ostatni element w kolejce
                rep_pos, rep_env, rep_btype, rep_is_enemy = self.core_facts_to_report[-1]
                
                place_pos = None
                # Rdzeń może działać w promieniu = 8
                for adj_pos in ct.get_nearby_tiles(8):
                    if ct.can_place_marker(adj_pos):
                        place_pos = adj_pos
                        break
                
                if place_pos:
                    marker_payload = self.pack_map_marker(current_round, rep_pos, rep_env, rep_btype, rep_is_enemy)
                    ct.place_marker(place_pos, marker_payload)
                    # Ślad zostawiony! Usuwamy fakt z kolejki.
                    self.core_facts_to_report.pop()
            
            # PRODUKCJA PROBEK
            if self.spawned_bots_count < 5 and ct.get_action_cooldown() == 0:
                spawn_pos = ct.get_position().add(random.choice(DIRECTIONS))
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.spawned_bots_count += 1 
            return
        


        # ==========================================
        # 2. LOGIKA PROBY (BUILDER_BOT) - Hybryda (Greedy + A*)
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
                # Każdy nowy bot rodzi się jako Zwiadowca
                self.bot_states[my_id] = BotState.EXPLORE


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
                    
                    # --- KTO WCHODZI NA LISTĘ VIP? ---
                    # 1. WSZYSTKIE budynki wroga
                    if b_team == enemy_team:
                        self.vip_facts[my_id][pos] = (Environment.EMPTY, b_type, True)
                    
                    # 2. NASZE strategiczne budynki (Kopalnie, Wieże, Huty)
                    elif b_team == my_team:
                        VIP_FRIENDLY = [EntityType.HARVESTER, EntityType.FOUNDRY, EntityType.GUNNER, EntityType.SENTINEL, EntityType.BREACH, EntityType.LAUNCHER]
                        if b_type in VIP_FRIENDLY:
                            self.vip_facts[my_id][pos] = (Environment.EMPTY, b_type, False)

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
                                # Zapamiętaj to w VIP Facts
                                if data['env'] in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                                    self.vip_facts[my_id][m_pos] = (data['env'], None, False)
                            
                            # B) Aktualizujemy budynki z markera (Zabezpieczenie Timestampem!)
                            known_b = self.bot_buildings[my_id].get(m_pos)
                            last_seen = known_b[2] if known_b else -1
                            
                            if m_turn > last_seen:
                                m_team = enemy_team if data['is_enemy'] else my_team
                                if not data['b_type']: m_team = None
                                self.bot_buildings[my_id][m_pos] = (data['b_type'], m_team, m_turn)
                                # Zapamiętaj do VIP Facts jeśli to budynek wroga
                                if data['is_enemy'] and data['b_type'] is not None:
                                    self.vip_facts[my_id][m_pos] = (Environment.EMPTY, data['b_type'], True)

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
            # 2. RUCH - Hybryda Zachłanny Insekt + A* z podwójną pętlą (2 próby ruchu)
            # ==========================================
            future_pos = my_pos # Do zapamiętania docelowej pozycji po ruchu (na potrzeby zostawiania markerów w odpowiednich miejscach)

            for _ in range(2): 
                
                
                # --- PRZEJŚCIA MIĘDZY STANAMI (Transitions) ---
                
                if current_state == BotState.EXPLORE:
                    # TODO: Napisać funkcję, która szuka wolnego złoża w vip_facts.
                    # Jeśli znajdzie:
                    # 1. self.bot_states[my_id] = BotState.BUILD_MINE
                    # 2. self.bot_targets[my_id] = znalezione_zloze
                    # 3. self.bot_paths[my_id] = []
                    



                    # Jeśli nie znajdzie wolnego złoża (lub zgubił stary losowy cel):

                    if not self.bot_targets[my_id] or my_pos == self.bot_targets[my_id]:
                        self.bot_targets[my_id] = Position(random.randint(0, map_width - 1), random.randint(0, map_height - 1))
                        self.bot_paths[my_id] = []

                elif current_state == BotState.BUILD_MINE:
                    # TODO: Sprawdź, czy cel nadal jest wolny (może inny bot już tam zbudował kopalnię?).
                    # Jeśli ktoś nas ubiegł -> wracamy do EXPLORE.
                    # Jeśli doszliśmy na miejsce -> budujemy HARVESTER i zmieniamy stan na BUILD_BELT.
                    pass

                elif current_state == BotState.BUILD_BELT:
                    # TODO: Odpal A* w stronę Bazy/Najbliższego Taśmociągu.
                    # Buduj drogę za sobą.
                    pass
                


                target_pos = self.bot_targets[my_id]
                #####################################################
                # 1. FAZA PLANOWANIA (Wybór celu)
                if self.bot_targets[my_id] and my_pos == self.bot_targets[my_id]:
                    self.bot_targets[my_id] = None
                    self.bot_paths[my_id] = []
                
                if not self.bot_targets[my_id]:
                    self.bot_targets[my_id] = Position(random.randint(0, map_width - 1), random.randint(0, map_height - 1))
                    self.bot_paths[my_id] = [] # Czyścimy trasę na wszelki wypadek
                
                target_pos = self.bot_targets[my_id]

                # --- NOWA LOGIKA: ZACHŁANNY INSEKT vs A* ---
                if target_pos and not self.bot_paths[my_id]: 
                    
                    # KROK 1: Próba Zachłanna (Prosto do celu)
                    greedy_dir = my_pos.direction_to(target_pos)
                    greedy_pos = my_pos.add(greedy_dir)
                    
                    # Sprawdzamy, z czym mamy do czynienia
                    env = ct.get_tile_env(greedy_pos)
                    b_id = ct.get_tile_building_id(greedy_pos)
                    can_walk_on_enemy = self.can_walk_on_building(b_id, my_team, ct) # type: ignore

                    # Sprawdzenie pamięci
                    memory_env = self.bot_memory[my_id].get(greedy_pos)
                    
                    is_hard_obstacle = (memory_env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE] or 
                                       (env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE] and memory_env is None) or 
                                       (b_id is not None and not can_walk_on_enemy))
                    
                    out_of_bounds = not (0 <= greedy_pos.x < map_width and 0 <= greedy_pos.y < map_height)
                    
                    if not is_hard_obstacle and not out_of_bounds:
                        # Droga wolna! Zapisujemy jeden zachłanny krok.
                        self.bot_paths[my_id] = [greedy_dir]
                    else:
                        # KROK 2: Uderzenie w przeszkodę -> Tryb Awaryjny (A*)
                        self.bot_paths[my_id] = self.calculate_astar_path(ct, my_pos, target_pos, map_width, map_height, my_id, my_team) # type: ignore
                        
                        if not self.bot_paths[my_id]:
                            self.bot_targets[my_id] = None
                            break  # Cel całkowicie zablokowany, w następnej turze losujemy nowy
                
                # Wizualizacja celu
                if self.bot_targets[my_id]:
                    try:
                        ct.draw_indicator_dot(self.bot_targets[my_id], 255, 255, 0) # type: ignore
                        ct.draw_indicator_line(my_pos, self.bot_targets[my_id], 0, 200, 255) # type: ignore
                    except Exception:
                        pass

                # 2. FAZA WYKONANIA: (Kod pozostaje ten sam, wykonuje krok z góry listy)
                if self.bot_paths[my_id]:
                    next_dir = self.bot_paths[my_id][0]
                    next_pos = my_pos.add(next_dir)

                    is_passable = ct.is_tile_passable(next_pos)
                    b_id = ct.get_tile_building_id(next_pos)
                    can_walk_on_enemy = self.can_walk_on_building(b_id, my_team, ct) # type: ignore

                    # PRZYPADEK A: Możemy od razu wejść
                    if is_passable or can_walk_on_enemy:
                        if ct.can_move(next_dir):
                            ct.move(next_dir)
                            future_pos = next_pos
                            self.bot_paths[my_id].pop(0) 
                        break # SUKCES
                    
                    # PRZYPADEK B: Wybudowanie Drogi
                    elif ct.can_build_road(next_pos):
                        if ct.get_action_cooldown() == 0:
                            ct.build_road(next_pos)
                            if ct.can_move(next_dir):
                                ct.move(next_dir)
                                future_pos = next_pos
                                self.bot_paths[my_id].pop(0)    
                        break # Zbudowaliśmy, czekamy/kończymy
                    
                    # PRZYPADEK C: Niespodziewana przeszkoda NA TRASIE z A*
                    else:
                        env = ct.get_tile_env(next_pos)
                        if env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE] or b_id is not None:
                            # TRWAŁA BLOKADA - Kasujemy listę. Pętla "for" obróci się drugi raz 
                            # i wywoła Tryb Zachłanny (który od razu potknie się o nową ścianę i odpali A*).
                            self.bot_paths[my_id] = []
                            continue 
                        else:
                            # Tymczasowa blokada (np. weszliśmy na innego bota)
                            break # Stoję i czekam
            
            
            # ==========================================
            # 3. ZOSTAWIANIE FEROMONÓW (GOSSIP PROTOCOL)
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
                
                # Szukamy NAJLEPSZEGO wolnego miejsca wokół bota
                place_pos = None
                nearby_tiles = ct.get_nearby_tiles(2)

                # PRZEBIEG 1: Szukamy miejsca IDEALNEGO (poza trasą)
                for adj_pos in nearby_tiles:
                    # Warunki idealnego miejsca:
                    # - Nie ma go na czarnej liście (nie zdepczemy go)
                    # - Silnik pozwala tam budować (brak przeszkód/innych markerów)
                    if adj_pos not in forbidden_tiles and ct.can_place_marker(adj_pos):
                        place_pos = adj_pos
                        break # Znaleźliśmy pierwsze wolne pobocze!
                # PRZEBIEG 2: Jeśli wciąż nie mamy miejsca, szukamy GDZIEKOLWIEK (nawet na trasie)
                if not place_pos:
                    for adj_pos in nearby_tiles:
                        if adj_pos != my_pos and ct.can_place_marker(adj_pos):
                            place_pos = adj_pos
                            break

                # 4. Jeśli po sprawdzeniu sąsiadów jest wolne miejsce -> Publikujemy
                if place_pos:
                    marker_payload = self.pack_map_marker(current_round, rep_pos, rep_env, rep_btype, rep_is_enemy)
                    ct.place_marker(place_pos, marker_payload)