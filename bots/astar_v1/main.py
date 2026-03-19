# Packages
# 1. Official
from cambc import Controller, Direction, EntityType, Environment, Position
# 2. For BFS navigation algorithm
from collections import deque
# 3. For random movement (for testing purposes)
import random
# 4. For priority queue (if we later want to implement A*)
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

    def calculate_astar_path(self, ct: Controller, start: Position, target: Position) -> list[Direction] | None:
        """
        Zwraca listę kierunków za pomocą optymistycznego A* (A-Star).
        """
        w, h = ct.get_map_width(), ct.get_map_height()
        
        # Kolejka priorytetowa: trzyma krotki (priorytet, koszt_do_tej_pory, x, y, pozycja)
        queue = []
        heapq.heappush(queue, (0, 0, start.x, start.y, start))
        
        came_from = {start: None}
        cost_so_far = {start: 0}
        iterations = 0
        
        
        # Najpierw posortujmy kierunki tak, aby te najbliżej celu (minimalny dystans do targetu) były pierwsze - wyciągamy tylko pierwszy kierunek
        # DIRECTIONS_PREFERENCE = sorted(DIRECTIONS, key=lambda d: start.add(d).distance_squared(target))

        while queue:
            iterations += 1
            if iterations > 1500:
                return None
            
            # Wyciągamy kafelek, który ma NAJLEPSZY priorytet (najbliżej celu)
            priority, current_cost, _, _, curr = heapq.heappop(queue)

            if curr == target:
                break
            
            DIRECTIONS_PREFERENCE = sorted(DIRECTIONS, key=lambda d: max(abs((curr.add(d)).x - target.x), abs((curr.add(d)).y - target.y)))
            
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
                    
                    # 3. MAGIA A*: Obliczamy "Heurystykę" (Odległość Czebyszewa, bo bot chodzi na ukos)
                    heuristic = max(abs(next_pos.x - target.x), abs(next_pos.y - target.y))
                    
                    # Priorytet to suma tego, ile już przeszliśmy i ile (szacunkowo) nam zostało
                    priority = new_cost + heuristic
                    
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
        etype = ct.get_entity_type()
        my_pos = ct.get_position()
        my_id = ct.get_id()

        # ==========================================
        # 1. LOGIKA BAZY (CORE) - na razie tylko produkcja probek
        # ==========================================
        if etype == EntityType.CORE:
            print(f"Baza żyje, pozycja: {ct.get_position()}, spawned: {self.spawned_bots_count}")
            # Ograniczamy produkcję do 5 probek
            if self.spawned_bots_count < 5 and ct.get_action_cooldown() == 0:
                spawn_pos = ct.get_position().add(random.choice(DIRECTIONS))
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.spawned_bots_count += 1 
            return
        

        # ==========================================
        # 2. LOGIKA PROBY (BUILDER_BOT) - na razie tylko poruszanie się do losowego celu za pomocą BFS
        # ==========================================
        elif etype == EntityType.BUILDER_BOT:
            # INICJALIZACJA PAMIĘCI: Jeśli to nowy bot, dajemy mu własną pustą teczkę
            if my_id not in self.bot_targets:
                self.bot_targets[my_id] = None
                self.bot_paths[my_id] = []
            
            
            # 1. FAZA PLANOWANIA:
            # Czy stoimy na celu? Jeśli tak, resetujemy cel i ścieżkę, żeby wybrać nowy cel.
            if self.bot_targets[my_id] and my_pos == self.bot_targets[my_id]:
                self.bot_targets[my_id] = None
                self.bot_paths[my_id] = []
            
            # Nie mamy celu
            if not self.bot_targets[my_id]:
                self.bot_targets[my_id] = Position(random.randint(0, ct.get_map_width() - 1), random.randint(0, ct.get_map_height() - 1))
            
            # Mamy cel, ale nie mamy ścieżki
            if  self.bot_targets[my_id] and not self.bot_paths[my_id]: 
                self.bot_paths[my_id] = self.calculate_astar_path(ct, my_pos, self.bot_targets[my_id])
                
                # Jeśli A* nie znalazł ścieżki, resetujemy cel na następną turę
                if not self.bot_paths[my_id]:
                    self.bot_targets[my_id] = None
                    return  # Kończymy turę dla tego bota
            
            # Rysujemy linię do celu - debugowanie
            if self.bot_targets[my_id]:
                try:
                    ct.draw_indicator_dot(self.bot_targets[my_id], 255, 255, 0)
                    ct.draw_indicator_line(my_pos, self.bot_targets[my_id], 0, 200, 255)
                except Exception:
                    pass  # Target is outside vision range, skip visualization
            

            # 2. FAZA WYKONANIA: Jeśli mamy zapisaną ścieżkę, próbujemy iść
            if self.bot_paths[my_id]:
                # ZAGLĄDAMY jaki jest następny krok, ale go jeszcze NIE USUWAMY z listy
                next_dir = self.bot_paths[my_id][0]
                next_pos = my_pos.add(next_dir)

                # --- SPRAWDZANIE CO JEST PRZED NAMI ---
                # Czy to pole jest oficjalnie przejezdne (nasze drogi/core)?
                is_passable = ct.is_tile_passable(next_pos)
                
                # Czy to jest teren wroga, po którym można chodzić (conveyor/road)?
                can_walk_on_enemy = False
                b_id = ct.get_tile_building_id(next_pos)

                if b_id is not None and ct.get_team(b_id) != ct.get_team():
                    b_type = ct.get_entity_type(b_id)
                    if b_type in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.ROAD]:
                        can_walk_on_enemy = True

                # PRZYPADEK A: Możemy od razu wejść (jest Droga, Taśmociąg lub Rdzeń)
                if is_passable or can_walk_on_enemy:
                    if ct.can_move(next_dir):
                        ct.move(next_dir)
                        self.bot_paths[my_id].pop(0)  # Sukces!
                
                # PRZYPADEK B: Pusty teren, MOŻEMY wybudować Drogę (mamy Tytan i 0 cooldownu)
                elif ct.can_build_road(next_pos):
                    if ct.get_action_cooldown() == 0:
                        ct.build_road(next_pos)
                    
                    # Od razu wchodzimy, jeśli mamy też odnowiony move_cooldown
                    if ct.can_move(next_dir):
                        ct.move(next_dir)
                        self.bot_paths[my_id].pop(0)
                
                # PRZYPADEK C: Ścieżka zablokowana. Ale dlaczego?
                else:
                    # Sprawdzamy, co nas blokuje. 
                    env = ct.get_tile_env(next_pos)
                    
                    # Jeśli przed nami wyrosła wielka skała, ruda, albo obcy budynek (np. wieżyczka wroga):
                    if env in [Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE] or b_id is not None:
                        # TRWAŁA BLOKADA: Resetujemy pamięć, żeby A* policzył nową trasę!
                        self.bot_paths[my_id] = []
                        #self.bot_targets[my_id] = None na razie zostawiamy ten sam cel, bo może się okazać, że to tylko chwilowa przeszkoda (np. inny bot przechodził przed nami i zaraz pójdzie dalej)
                    else:
                        # TYMCZASOWA BLOKADA: (Brak tytanu, cooldown, albo przed nami stoi nasz kolega-bot).
                        # Bot po prostu cierpliwie stoi i CZEKA (nie robimy nic w tej turze).
                        pass