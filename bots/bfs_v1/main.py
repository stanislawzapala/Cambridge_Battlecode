import random
from collections import deque
from cambc import Controller, Direction, EntityType, Environment, Position

# Wykluczamy kierunek CENTRE, aby ułatwić pętle logiczne
DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]

class Player:
    def __init__(self):
        # Dla bazy (CORE): liczymy, ile botów już wyprodukowaliśmy
        self.num_spawned = 0
        
        # Dla bota (BUILDER_BOT): pamięć celu i zaplanowanej ścieżki
        self.target_pos: Position | None = None
        self.path: list[Direction] | None = []

    def calculate_bfs_path(self, ct: Controller, start: Position, target: Position) -> list[Direction] | None:
        """
        Zwraca listę kierunków (najkrótszą ścieżkę) do celu za pomocą BFS.
        Zwraca None, jeśli cel jest całkowicie odcięty.
        """
        w, h = ct.get_map_width(), ct.get_map_height()
        queue = deque([start])
        came_from = {start: None}

        while queue:
            curr = queue.popleft()

            if curr == target:
                break

            for d in DIRECTIONS:
                next_pos = curr.add(d)
                
                # 1. Sprawdzamy, czy nie wychodzimy poza mapę
                if not (0 <= next_pos.x < w and 0 <= next_pos.y < h):
                    continue
                
                # 2. Jeśli jeszcze tu nie byliśmy
                if next_pos not in came_from:
                    # 3. Przejezdne = wolna przestrzeń, istniejąca droga lub nasza baza
                    if ct.is_tile_passable(next_pos) or ct.is_tile_empty(next_pos):
                        came_from[next_pos] = (curr, d) # type: ignore
                        queue.append(next_pos)

        # Odtwarzanie ścieżki od tyłu
        if target not in came_from:
            return None # Droga nie istnieje

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

        # ==========================================
        # 1. LOGIKA BAZY (CORE) - Fabryka
        # ==========================================
        if etype == EntityType.CORE:
            # Ograniczamy produkcję do 10 botów
            if self.num_spawned < 10 and ct.get_action_cooldown() == 0:
                for d in DIRECTIONS:
                    spawn_pos = my_pos.add(d)
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        self.num_spawned += 1
                        return 

        # ==========================================
        # 2. LOGIKA BOTA (EXPLORER BFS)
        # ==========================================
        elif etype == EntityType.BUILDER_BOT:
            
            # KROK 1: Losowanie celu i OBLICZANIE TRASY
            # Robimy to, gdy nie mamy celu, dotarliśmy na miejsce, lub skończyła nam się trasa
            if self.target_pos is None or my_pos == self.target_pos or not self.path:
                w, h = ct.get_map_width(), ct.get_map_height()
                self.target_pos = Position(random.randint(0, w-1), random.randint(0, h-1))
                
                # Odpalamy ciężki algorytm BFS
                self.path = self.calculate_bfs_path(ct, my_pos, self.target_pos)
                
                # Jeśli trafiliśmy na środek ściany (brak trasy) - resetujemy i wylosujemy ponownie w kolejnej turze
                if self.path is None:
                    self.target_pos = None
                    return

            # Wizualizacja celu w symulatorze
            ct.draw_indicator_dot(self.target_pos, 255, 255, 0)
            ct.draw_indicator_line(my_pos, self.target_pos, 0, 200, 255)

            # KROK 2: Wykonanie kolejnego kroku ze ścieżki
            if self.path: 
                next_dir = self.path[0]
                next_pos = my_pos.add(next_dir)

                # SCENARIUSZ A: Droga wolna
                if ct.is_tile_passable(next_pos):
                    if ct.can_move(next_dir):
                        ct.move(next_dir)
                        self.path.pop(0) # Wykonaliśmy krok, wyrzucamy go z listy
                        
                # SCENARIUSZ B: Trzeba wybudować drogę
                elif ct.is_tile_empty(next_pos):
                    if ct.can_build_road(next_pos):
                        ct.build_road(next_pos)
                        # Celowo nie usuwamy kroku (pop), bo fizycznie nadal stoimy w starym miejscu
                        
                # SCENARIUSZ C: Ktoś nam zablokował trasę (np. inny bot stanął przed nami)
                else:
                    # Resetujemy ścieżkę - w następnej turze bot przeliczy BFS od nowa z uwzględnieniem nowej przeszkody
                    self.path = None