# Packages
# 1. Official
from cambc import Controller, Direction, EntityType, Environment, Position
# 2. For random movement (for testing purposes)
import random
# 3. For priority queue (if we later want to implement A*)
import heapq


DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]

class Player:
    def __init__(self):
        # CORE
        self.spawned_bots_count = 0

        # PROBES (Builder Bot)
        # PAMIĘĆ DLA BOTÓW
        # Kluczem w słowniku będzie ID bota (int)
        self.bot_targets: dict[int, Position | None] = {}
        self.bot_paths: dict[int, list[Direction]] = {}


    def calculate_astar_path(self, ct: Controller, start: Position, target: Position, w: int, h: int) -> list[Direction] | None:
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
                            elif b_type == EntityType.CORE and ct.get_team(b_id) != ct.get_team():
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
                    came_from[next_pos] = (curr, d)

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

    def run(self, ct: Controller) -> None:
        # Cache map dimensions to avoid repeated API calls
        map_width = ct.get_map_width()
        map_height = ct.get_map_height()
        
        etype = ct.get_entity_type()
        my_pos = ct.get_position()
        my_id = ct.get_id()

        # ==========================================
        # 1. LOGIKA BAZY (CORE) - na razie tylko produkcja probek
        # ==========================================
        if etype == EntityType.CORE:
            # Ograniczamy produkcję do 5 probek
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
                self.bot_targets[my_id] = None
                self.bot_paths[my_id] = []
            
            # --- PĘTLA DRUGIEJ SZANSY ---
            for _ in range(2): 
                
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
                    
                    can_walk_on_enemy = False
                    if b_id is not None and ct.get_team(b_id) != ct.get_team():
                        b_type = ct.get_entity_type(b_id)
                        if b_type in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.ROAD]:
                            can_walk_on_enemy = True

                    is_hard_obstacle = (env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE] or 
                                       (b_id is not None and not can_walk_on_enemy))
                    out_of_bounds = not (0 <= greedy_pos.x < map_width and 0 <= greedy_pos.y < map_height)
                    
                    if not is_hard_obstacle and not out_of_bounds:
                        # Droga wolna! Zapisujemy jeden zachłanny krok.
                        self.bot_paths[my_id] = [greedy_dir]
                    else:
                        # KROK 2: Uderzenie w przeszkodę -> Tryb Awaryjny (A*)
                        self.bot_paths[my_id] = self.calculate_astar_path(ct, my_pos, target_pos, map_width, map_height)
                        
                        if not self.bot_paths[my_id]:
                            self.bot_targets[my_id] = None
                            break  # Cel całkowicie zablokowany, w następnej turze losujemy nowy
                
                # Wizualizacja celu
                if self.bot_targets[my_id]:
                    try:
                        ct.draw_indicator_dot(self.bot_targets[my_id], 255, 255, 0)
                        ct.draw_indicator_line(my_pos, self.bot_targets[my_id], 0, 200, 255)
                    except Exception:
                        pass

                # 2. FAZA WYKONANIA: (Kod pozostaje ten sam, wykonuje krok z góry listy)
                if self.bot_paths[my_id]:
                    next_dir = self.bot_paths[my_id][0]
                    next_pos = my_pos.add(next_dir)

                    is_passable = ct.is_tile_passable(next_pos)
                    can_walk_on_enemy = False
                    b_id = ct.get_tile_building_id(next_pos)

                    if b_id is not None and ct.get_team(b_id) != ct.get_team():
                        b_type = ct.get_entity_type(b_id)
                        if b_type in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.ROAD]:
                            can_walk_on_enemy = True

                    # PRZYPADEK A: Możemy od razu wejść
                    if is_passable or can_walk_on_enemy:
                        if ct.can_move(next_dir):
                            ct.move(next_dir)
                            self.bot_paths[my_id].pop(0) 
                        break # SUKCES
                    
                    # PRZYPADEK B: Wybudowanie Drogi
                    elif ct.can_build_road(next_pos):
                        if ct.get_action_cooldown() == 0:
                            ct.build_road(next_pos)
                            if ct.can_move(next_dir):
                                ct.move(next_dir)
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