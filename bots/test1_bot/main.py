import random
from cambc import Controller, Direction, EntityType, Position

DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]

class Player:
    def __init__(self):
        # Każdy bot ma swój własny, unikalny cel
        self.target_pos: Position | None = None
        self.is_hugging_wall = False
        self.hug_direction = 1  # 1 dla rotacji w prawo, -1 dla lewo
        # Licznik botów w bazie
        self.spawned_bots_count = 0

    def navigate_to(self, ct: Controller, target: Position) -> bool:
        """
        Zaawansowana funkcja nawigacji. 
        Zwraca True jeśli wykonano ruch lub budowę.
        """
        my_pos = ct.get_position()
        direct_dir = my_pos.direction_to(target)
        
        if direct_dir == Direction.CENTRE:
            return False

        # Sprawdzamy, czy droga na wprost jest wolna (pusta lub już z drogą)
        # W Battlecode 'is_tile_passable' to pola, po których można chodzić.
        # 'is_tile_empty' to pola, na których można zbudować drogę.
        
        # Próbujemy iść prosto, a jeśli się nie da - szukamy bocznej drogi (Bug-style)
        test_dirs = [
            direct_dir,
            direct_dir.rotate_right() if self.hug_direction == 1 else direct_dir.rotate_left(),
            direct_dir.rotate_left() if self.hug_direction == 1 else direct_dir.rotate_right(),
            direct_dir.rotate_right().rotate_right(),
            direct_dir.rotate_left().rotate_left(),
        ]

        for d in test_dirs:
            next_pos = my_pos.add(d)
            
            # Jeśli pole jest gotowe do przejścia
            if ct.is_tile_passable(next_pos):
                if ct.can_move(d):
                    ct.move(d)
                    return True
            
            # Jeśli musimy wybudować drogę, żeby przejść (omijając ściany/rudę)
            elif ct.is_tile_empty(next_pos):
                if ct.can_build_road(next_pos):
                    ct.build_road(next_pos)
                    return True
        
        # Jeśli bot utknął, zmień stronę omijania przeszkód na przyszłość
        self.hug_direction *= -1
        return False



    def run(self, ct: Controller) -> None:
        etype = ct.get_entity_type()
        my_pos = ct.get_position()

        # ==========================================
        # 1. LOGIKA BAZY (CORE)
        # ==========================================
        if etype == EntityType.CORE:
            # Spawnujemy boty tylko do limitu 5
            if self.spawned_bots_count < 5 and ct.get_action_cooldown() == 0:
                for d in DIRECTIONS:
                    spawn_pos = my_pos.add(d)
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        self.spawned_bots_count += 1
                        return

        # ==========================================
        # 2. LOGIKA BOTA (EXPLORER)
        # ==========================================
        elif etype == EntityType.BUILDER_BOT:
            # Jeśli bot nie ma celu, losuje go raz na całe swoje życie
            if self.target_pos is None:
                w = ct.get_map_width()
                h = ct.get_map_height()
                self.target_pos = Position(random.randint(0, w-1), random.randint(0, h-1))

            # Debug: rysujemy linię do celu bota
            ct.draw_indicator_line(my_pos, self.target_pos, 0, 200, 255)
            ct.draw_indicator_dot(self.target_pos, 255, 255, 0)

            # Jeśli dotarliśmy do celu (odległość 0), losujemy nowy cel
            if my_pos == self.target_pos:
                self.target_pos = None 
                return

            # Wykonaj ruch
            self.navigate_to(ct, self.target_pos)