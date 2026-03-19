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

    def calculate_bfs_path(self, ct: Controller, start: Position, target: Position, w: int, h: int) -> list[Direction] | None:
        """
        Zwraca listę kierunków (najkrótszą ścieżkę) do celu za pomocą BFS.
        Zwraca None, jeśli cel jest całkowicie odcięty.
        """
        queue = deque([start])
        came_from = {start: None}
        iterations = 0 # bezpiecznik czasowy, żeby nie wpaść w za długą pętlę
        vision_range = 20  # Limit BFS to vision range

        while queue:
            iterations += 1
            if iterations > 200:
                # Szukaliśmy za długo, odpuszczamy ten cel.
                return None
            
            curr = queue.popleft()

            if curr == target:
                break

            for d in DIRECTIONS:
                next_pos = curr.add(d)
                
                # 1. Sprawdzamy, czy nie wychodzimy poza mapę
                if not (0 <= next_pos.x < w and 0 <= next_pos.y < h):
                    continue
                
                # 2. Jeśli jeszcze nie odwiedziliśmy tego pola
                if next_pos not in came_from:
                    # 3. OPTYMISTYCZNY BFS - jeśli nie widzimy pola, zakładamy, że jest  przejezdne, żeby nie blokować bota mgłą wojny.
                    if ct.is_in_vision(next_pos):
                        # Jeśli WIDZIMY to pole, sprawdzamy, czy jest tam droga lub czy możemy ją zbudować
                        # Ściany i wrogie jednostki zwrócą False, więc bot je bezpiecznie ominie.
                        if ct.is_tile_passable(next_pos) or ct.can_build_road(next_pos):
                            came_from[next_pos] = (curr, d)
                            queue.append(next_pos)
                    else:
                        # Jeśli NIE WIDZIMY pola (jest we mgle wojny), zakładamy w ciemno, że jest super przejezdne!
                        came_from[next_pos] = (curr, d)
                        queue.append(next_pos)
                        
        # Odtwarzanie ścieżki od tyłu
        if target not in came_from:
            return None # Droga nie istnieje, bo nie dotarliśmy do celu

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
                self.bot_targets[my_id] = Position(random.randint(0, map_width - 1), random.randint(0, map_height - 1))
            
            # Mamy cel, ale nie mamy ścieżki
            if  self.bot_targets[my_id] and not self.bot_paths[my_id]: 
                self.bot_paths[my_id] = self.calculate_bfs_path(ct, my_pos, self.bot_targets[my_id], map_width, map_height)
                
                # Jeśli BFS nie znalazł ścieżki, resetujemy cel na następną turę
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

                # PRZYPADEK A: Możemy od razu wejść (jest Droga, Taśmociąg lub Rdzeń)
                if ct.is_tile_passable(next_pos):
                    if ct.can_move(next_dir):
                        ct.move(next_dir)
                        self.bot_paths[my_id].pop(0)  # Zrobiliśmy krok, usuwamy go ze ścieżki
                
                # PRZYPADEK B: Aby przejść, trzeba wybudować Drogę
                elif ct.can_build_road(next_pos):
                    if ct.get_action_cooldown() == 0:
                        ct.build_road(next_pos)

                    # Zbudowaliśmy drogę, jeśli możemy, to wchodzimy
                    if ct.can_move(next_dir):
                        ct.move(next_dir)
                        self.bot_paths[my_id].pop(0)  # Zbudowano i ruszono się, usuwamy go ze ścieżki
                        # UWAGA: Jeśli nie mamy move_cooldown, bot zbuduje drogę, ale krok 
                        # zostaje na liście path[0]. W następnej turze bot wejdzie w PRZYPADEK A!
                
                # PRZYPADEK C: Ścieżka zablokowana
                else:
                    # Resetujemy pamięć - zarówno cel, jak i ścieżkę.
                    self.bot_paths[my_id] = []
                    self.bot_targets[my_id] = None