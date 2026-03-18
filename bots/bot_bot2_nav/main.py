import random
from cambc import Controller, Direction, EntityType, Position

class Player:
    def __init__(self):
        self.target_pos = None
        self.start_pos = None
        self.spawned_bots_count = 0
        
        # Maszyna stanów: "DIR" (Direct/Dążenie) lub "WALL" (Wall-following)
        self.state = "DIR" 
        self.hit_point = None
        self.last_wall_dir = None
        
    def is_on_m_line(self, current: Position) -> bool:
        """Sprawdza, czy bot znajduje się na linii łączącej start z celem."""
        if self.start_pos is None or self.target_pos is None:
            return False
            
        # Matematycznie: sprawdzamy czy punkt (x,y) leży na odcinku.
        # W gridzie Battlecode sprawdzamy, czy kierunek ze startu do celu 
        # jest taki sam jak kierunek ze startu do bota.
        line_dir = self.start_pos.direction_to(self.target_pos)
        current_dir = self.start_pos.direction_to(current)
        return line_dir == current_dir

    def can_pass(self, ct: Controller, pos: Position) -> bool:
        """Pomocnicza funkcja: czy pole jest przejezdne lub puste pod drogę."""
        return ct.is_tile_passable(pos) or ct.is_tile_empty(pos)

    def execute_step(self, ct: Controller, d: Direction) -> bool:
        """Fizycznie wykonuje ruch: buduje drogę lub idzie."""
        target_p = ct.get_position().add(d)
        if ct.is_tile_passable(target_p):
            if ct.can_move(d):
                ct.move(d)
                return True
        elif ct.can_build_road(target_p):
            ct.build_road(target_p)
            return True
        return False

    def run(self, ct: Controller) -> None:
        if ct.get_entity_type() == EntityType.CORE:
            if ct.get_action_cooldown() == 0 and self.spawned_bots_count < 5:
                for d in [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]:
                    if ct.can_spawn(ct.get_position().add(d)):
                        ct.spawn_builder(ct.get_position().add(d))
                        self.spawned_bots_count += 1
                        return
            return

        # LOGIKA BOTA
        my_pos = ct.get_position()
        
        # 1. Inicjalizacja celu
        if self.target_pos is None:
            w, h = ct.get_map_width(), ct.get_map_height()
            self.target_pos = Position(random.randint(0, w-1), random.randint(0, h-1))
            self.start_pos = my_pos
            self.state = "DIR"

        ct.draw_indicator_line(my_pos, self.target_pos, 0, 255, 0) # m-line wizualna

        # 2. MASZYNA STANÓW BUG-2
        if self.state == "DIR":
            best_dir = my_pos.direction_to(self.target_pos)
            next_p = my_pos.add(best_dir)
            
            if self.can_pass(ct, next_p):
                self.execute_step(ct, best_dir)
            else:
                # Uderzyliśmy w ścianę!
                self.state = "WALL"
                self.hit_point = my_pos
                # Zaczynamy omijanie (zawsze w prawo)
                self.last_wall_dir = best_dir

        if self.state == "WALL":
            # Czy możemy wrócić na m-line?
            if self.is_on_m_line(my_pos) and my_pos.distance_squared(self.target_pos) < self.hit_point.distance_squared(self.target_pos):
                self.state = "DIR"
                return # W następnej turze pójdzie prosto

            # Logika "macania" ściany (Wall Following)
            # Próbujemy kierunki od "lewo-przód" do "prawo-tył"
            test_dir = self.last_wall_dir.rotate_left().rotate_left() 
            for _ in range(8):
                if self.can_pass(ct, my_pos.add(test_dir)):
                    if self.execute_step(ct, test_dir):
                        self.last_wall_dir = test_dir
                        return
                test_dir = test_dir.rotate_right()